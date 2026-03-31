from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga2 import NSGA2
import csv
import json
import numpy as np
import os
import threading
import time
from datetime import datetime, timezone

from text_perturbation_tool import TARGET_DIR, list_text_files, run_workload_burst

POP_SIZE = 10
N_VAR = 2


def make_stealth_warm_start_X(problem: ElementwiseProblem, pop_size: int) -> np.ndarray:
    """
    Initial population for generation 0: every individual at the most conservative
    corner of the box — minimum chars/step, maximum delay (within problem bounds).
    NSGA2 default would use FloatRandomSampling() uniformly in [xl, xu]; passing
    this array as sampling= overrides that.
    """
    # Explicit conservative warm-start point for reproducible benchmarking.
    stealth = np.array([[1.0, 60.0]], dtype=float)
    return np.tile(stealth, (pop_size, 1))


class RoarOptimizationProblem(ElementwiseProblem):
    def __init__(self):
        super().__init__(
            n_var=N_VAR,
            n_obj=2,
            xl=np.array([1, 5.0]),
            xu=np.array([15, 60.0]),
        )
        self._script_dir = os.path.dirname(os.path.abspath(__file__))
        self.detection_status_path = os.path.join(
            self._script_dir, "detection_status.txt"
        )
        self.threshold_log_path = os.path.join(
            self._script_dir, "threshold_log.csv"
        )
        self.research_csv_path = os.path.join(
            self._script_dir, "attack_research_data.csv"
        )
        # Avoid duplicate CSV rows when the server snapshot is unchanged.
        self._last_logged_feedback_key = None

        # Paper / experiment metrics (throughput vs. threshold, time to first detection).
        self.total_modified_cumulative = 0
        self.start_time = time.time()
        self.first_detection_seconds = None
        self.stop_requested = False
        self._research_lock = threading.Lock()
        self.total_files_baseline = max(1, len(list_text_files(TARGET_DIR)))
        self.files_processed_estimate = 0

    def _parse_server_feedback_raw(self, raw: str) -> dict:
        """
        Parse local feedback mirrored from the server (via client socket → file).

        Supports:
        - Legacy plain text: '0' / '1'
        - JSON: {"detection_status": 0|1, "anomaly_score": ..., "threshold": ...}
        """
        raw = (raw or "").strip()
        if not raw:
            return {"status": 0, "threshold": None, "score": None}

        if raw.startswith("{"):
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                return {"status": 0, "threshold": None, "score": None}
            st = d.get("detection_status", d.get("status", 0))
            try:
                status = 1 if int(st) == 1 else 0
            except (TypeError, ValueError):
                status = 1 if str(st).strip() == "1" else 0
            threshold = d.get("anomaly_score_threshold", d.get("threshold"))
            score = d.get("anomaly_score", d.get("score"))
            return {"status": status, "threshold": threshold, "score": score}

        return {
            "status": 1 if raw == "1" else 0,
            "threshold": None,
            "score": None,
        }

    def read_server_feedback(self) -> dict:
        """Read detection_status.txt; does not mutate f2 logic beyond parsing."""
        try:
            with open(self.detection_status_path, "r", encoding="utf-8") as f:
                return self._parse_server_feedback_raw(f.read())
        except (FileNotFoundError, OSError):
            return {"status": 0, "threshold": None, "score": None}

    def log_threshold_snapshot_if_changed(self, feedback: dict) -> None:
        """
        Append a row to threshold_log.csv when status/threshold/score changes.
        Prepares a persistent timeline of server threshold/score updates.
        """
        key = (
            feedback.get("status"),
            feedback.get("threshold"),
            feedback.get("score"),
        )
        if key == self._last_logged_feedback_key:
            return
        self._last_logged_feedback_key = key

        new_file = not os.path.exists(self.threshold_log_path)
        line = "{},{},{},{}\n".format(
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            feedback.get("status", ""),
            feedback.get("threshold", ""),
            feedback.get("score", ""),
        )
        try:
            with open(self.threshold_log_path, "a", encoding="utf-8") as f:
                if new_file:
                    f.write("utc_timestamp,status,threshold,anomaly_score\n")
                f.write(line)
        except OSError:
            pass

    def _append_attack_research_row(
        self,
        *,
        chars_per_step: int,
        delay: float,
        throughput_this_burst: int,
        cumulative_throughput: int,
        percent_files_processed: float,
        is_detected: int,
        server_threshold,
        anomaly_score,
        seconds_since_start: float,
    ) -> None:
        """One row per _evaluate for throughput vs. threshold analysis."""
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        new_file = not os.path.exists(self.research_csv_path)
        row = [
            timestamp,
            f"{seconds_since_start:.6f}",
            chars_per_step,
            f"{delay:.6f}",
            throughput_this_burst,
            cumulative_throughput,
            f"{percent_files_processed:.4f}",
            is_detected,
            "" if server_threshold is None else server_threshold,
            "" if anomaly_score is None else anomaly_score,
        ]
        fieldnames = [
            "timestamp",
            "seconds_since_start",
            "chars_per_step",
            "delay",
            "throughput_this_burst",
            "cumulative_throughput",
            "percent_files_processed",
            "is_detected",
            "server_threshold",
            "anomaly_score",
        ]
        try:
            with open(self.research_csv_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(fieldnames)
                writer.writerow(row)
        except OSError:
            pass

    def get_system_busy_signal(self) -> float:
        """
        Contention / detection signal for objective f2 (1.0 = high, 0.0 = low).
        Also records threshold and raw score when present in the feedback file.
        """
        feedback = self.read_server_feedback()
        self.log_threshold_snapshot_if_changed(feedback)
        return 1.0 if feedback["status"] == 1 else 0.0

    def _evaluate(self, x, out, *args, **kwargs):
        chars_per_step = int(x[0])
        delay = float(x[1])

        throughput_this_burst = run_workload_burst(
            chars_per_step, delay, test_duration_sec=10.0
        )

        with self._research_lock:
            self.total_modified_cumulative += throughput_this_burst
            cumulative_throughput = self.total_modified_cumulative
            seconds_since_start = time.time() - self.start_time

            feedback = self.read_server_feedback()
            self.log_threshold_snapshot_if_changed(feedback)

            is_detected = 1 if feedback["status"] == 1 else 0
            server_threshold = feedback.get("threshold")
            anomaly_score = feedback.get("score")
            if throughput_this_burst > 0:
                self.files_processed_estimate += 1
            percent_files_processed = min(
                100.0,
                (self.files_processed_estimate / self.total_files_baseline) * 100.0,
            )

            if feedback["status"] == 1 and self.first_detection_seconds is None:
                self.first_detection_seconds = seconds_since_start
                self.stop_requested = True
                print(
                    f"[DETECTION EVENT] First detection at {self.first_detection_seconds:.3f} seconds"
                )

            self._append_attack_research_row(
                chars_per_step=chars_per_step,
                delay=delay,
                throughput_this_burst=throughput_this_burst,
                cumulative_throughput=cumulative_throughput,
                percent_files_processed=percent_files_processed,
                is_detected=is_detected,
                server_threshold=server_threshold,
                anomaly_score=anomaly_score,
                seconds_since_start=seconds_since_start,
            )

            # Efficiency kill-switch for benchmarking: once busy/detected, skip
            # further scoring work for this evaluation and penalize contention.
            if self.stop_requested:
                out["F"] = [0.0, 1.0]
                return
            f2 = 1.0 if feedback["status"] == 1 else 0.0

        # Objective 1: maximize throughput (as minimization objective)
        f1 = -1.0 * throughput_this_burst
        out["F"] = [f1, f2]


if __name__ == "__main__":
    WARMUP_DURATION = 120
    print(f"Waiting for server warmup ({WARMUP_DURATION}s) to establish baseline...")
    time.sleep(WARMUP_DURATION)

    problem = RoarOptimizationProblem()

    X_initial = make_stealth_warm_start_X(problem, POP_SIZE)
    print(
        f"[NSGA2] Warm-start: all {POP_SIZE} individuals at "
        f"chars_per_step={int(X_initial[0, 0])}, delay={X_initial[0, 1]:.3f} "
        f"(not random sampling within bounds)."
    )

    # sampling=X_initial → pymoo Initialization builds Population.new(X=X_initial).
    # eliminate_duplicates=False: default duplicate elimination would collapse
    # identical rows to a single individual before generation 1.
    algorithm = NSGA2(
        pop_size=POP_SIZE,
        sampling=X_initial,
        eliminate_duplicates=False,
    )

    res = minimize(
        problem,
        algorithm,
        ("n_gen", 5),
        seed=1,
        verbose=True,
    )

    print("--- Optimization Results (Pareto Front) ---")
    if res.X is None or res.F is None:
        print("No feasible solutions were produced.")
    else:
        for params, outcomes in zip(res.X, res.F):
            chars_per_step = int(params[0])
            delay = float(params[1])
            throughput = -1.0 * float(outcomes[0])
            contention = float(outcomes[1])
            print(
                "chars_per_step={}, delay={:.3f} -> throughput={:.1f}, contention={:.1f}".format(
                    chars_per_step,
                    delay,
                    throughput,
                    contention,
                )
            )
