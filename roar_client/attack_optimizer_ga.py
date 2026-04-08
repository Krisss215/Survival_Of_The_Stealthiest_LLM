from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.algorithms.soo.nonconvex.ga import GA
import csv
import json
import numpy as np
import os
import threading
import time
from datetime import datetime, timezone

from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM

from text_perturbation_tool import TARGET_DIR, list_text_files, run_workload_burst

POP_SIZE = 10
N_VAR = 2


def make_stealth_warm_start_X(problem: ElementwiseProblem, pop_size: int) -> np.ndarray:
    """
    Initial population for generation 0: every individual at the most conservative
    corner of the box — minimum chars/step, maximum delay (within problem bounds).
    Passing this array as sampling= overrides random sampling in [xl, xu].
    """
    stealth = np.array([[1.0, 60.0]], dtype=float)
    return np.tile(stealth, (pop_size, 1))


def _continuous_detection_constraint(
    server_threshold, anomaly_score, feedback_status: int
) -> float:
    """
    Inequality constraint g <= 0 means feasible.

    g = threshold - anomaly_score:
    - score below threshold => g > 0 (violation / "hot")
    - score above threshold => g < 0 (feasible margin)
    """
    if server_threshold is None or anomaly_score is None:
        return 1.0 if feedback_status == 1 else 0.0
    try:
        thr = float(server_threshold)
        scr = float(anomaly_score)
    except (TypeError, ValueError):
        return 1.0 if feedback_status == 1 else 0.0
    return thr - scr


class RoarOptimizationProblemGA(ElementwiseProblem):
    def __init__(self):
        super().__init__(
            n_var=N_VAR,
            n_obj=1,
            n_ieq_constr=1,
            xl=np.array([1, 5.0]),
            xu=np.array([15, 60.0]),
        )
        self._script_dir = os.path.dirname(os.path.abspath(__file__))
        self.detection_status_path = os.path.join(
            self._script_dir, "detection_status.txt"
        )
        # Separate logs from attack_optimizer.py so runs do not interleave rows.
        self.threshold_log_path = os.path.join(
            self._script_dir, "threshold_log_ga.csv"
        )
        self.research_csv_path = os.path.join(
            self._script_dir, "attack_research_data_ga.csv"
        )
        self._last_logged_feedback_key = None

        self.total_modified_cumulative = 0
        self.start_time = time.time()
        self.first_detection_seconds = None
        self.stop_requested = False
        self._research_lock = threading.Lock()
        self.total_files_baseline = max(1, len(list_text_files(TARGET_DIR)))
        self.files_processed_estimate = 0

    def _parse_server_feedback_raw(self, raw: str) -> dict:
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
        try:
            with open(self.detection_status_path, "r", encoding="utf-8") as f:
                return self._parse_server_feedback_raw(f.read())
        except (FileNotFoundError, OSError):
            return {"status": 0, "threshold": None, "score": None}

    def log_threshold_snapshot_if_changed(self, feedback: dict) -> None:
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
        g_detection: float,
    ) -> None:
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
            f"{g_detection:.6f}",
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
            "g_detection",
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

            g_detection = _continuous_detection_constraint(
                server_threshold, anomaly_score, feedback["status"]
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
                g_detection=g_detection,
            )

            if self.stop_requested:
                out["F"] = [0.0]
                out["G"] = [1.0]
                return

            f1 = -1.0 * throughput_this_burst

        out["F"] = [f1]
        out["G"] = [g_detection]


if __name__ == "__main__":
    WARMUP_DURATION = 120
    print(f"Waiting for server warmup ({WARMUP_DURATION}s) to establish baseline...")
    time.sleep(WARMUP_DURATION)

    problem = RoarOptimizationProblemGA()

    X_initial = make_stealth_warm_start_X(problem, POP_SIZE)
    print(
        f"[GA] Warm-start: all {POP_SIZE} individuals at "
        f"chars_per_step={int(X_initial[0, 0])}, delay={X_initial[0, 1]:.3f} "
        f"(not random sampling within bounds)."
    )

    crossover = SBX(prob=0.9, eta=30)
    mutation = PM(prob=1.0, eta=50)

    algorithm = GA(
        pop_size=POP_SIZE,
        sampling=X_initial,
        crossover=crossover,
        mutation=mutation,
        eliminate_duplicates=False,
    )

    res = minimize(
        problem,
        algorithm,
        ("n_gen", 50),
        seed=1,
        verbose=True,
    )

    print("--- Optimization Results (GA) ---")
    if res.X is None or res.F is None:
        print("No feasible solutions were produced.")
    else:
        # GA best solution: res.X is shape (n_var,), not (n_solutions, n_var).
        X2 = np.atleast_2d(res.X)
        F2 = np.atleast_2d(res.F)
        G2 = np.atleast_2d(res.G) if res.G is not None else None

        for i in range(X2.shape[0]):
            params = X2[i]
            outcomes = F2[i] if F2.shape[0] > i else F2[0]
            chars_per_step = int(params[0])
            delay = float(params[1])
            throughput = -1.0 * float(np.atleast_1d(outcomes)[0])
            if G2 is None:
                print(
                    "chars_per_step={}, delay={:.3f} -> throughput={:.1f}, g=N/A".format(
                        chars_per_step,
                        delay,
                        throughput,
                    )
                )
            else:
                g_row = G2[i] if G2.shape[0] > i else G2[0]
                g0 = float(np.atleast_1d(g_row)[0])
                feasible = g0 <= 0.0
                print(
                    "chars_per_step={}, delay={:.3f} -> throughput={:.1f}, "
                    "g_detection={:.6f}, feasible={}".format(
                        chars_per_step,
                        delay,
                        throughput,
                        g0,
                        feasible,
                    )
                )
