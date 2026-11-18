from pymoo.core.problem import ElementwiseProblem
from pymoo.core.callback import Callback
from pymoo.optimize import minimize
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



BASELINE_DIR = "/home/kristina2/clean_corpus_baseline"

POP_SIZE = 10
N_VAR = 2

# Minimization objective: use a large constant when server reports detection (binary feedback only).
DETECTED_FITNESS_PENALTY = 1.0e6


class OptimizationHistoryCallback(Callback):
    """
    Called by pymoo after each generation (Algorithm._post_advance).
    Appends one row per generation to optimization_history.csv and flushes so
    progress is visible while the run continues.
    """

    def __init__(self, log_dir: str) -> None:
        super().__init__()
        self._path = os.path.join(log_dir, "optimization_history.csv")
        self._generation = 0
        self._header_written = os.path.exists(self._path) and os.path.getsize(self._path) > 0

    def _append_row(
        self,
        generation: int,
        best_fitness: float,
        chars_per_step: float,
        delay: float,
        best_g: str,
    ) -> None:
        fieldnames = [
            "generation",
            "best_fitness",
            "chars_per_step",
            "delay",
            "best_g",
        ]
        need_header = not self._header_written
        try:
            with open(self._path, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if need_header:
                    writer.writeheader()
                    self._header_written = True
                writer.writerow(
                    {
                        "generation": generation,
                        "best_fitness": f"{best_fitness:.8g}",
                        "chars_per_step": f"{chars_per_step:.8g}",
                        "delay": f"{delay:.8g}",
                        "best_g": best_g,
                    }
                )
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            print(f"[OptimizationHistoryCallback] Failed to write log: {e}")

    def notify(self, algorithm) -> None:
        opt = algorithm.opt
        if opt is None or len(opt) == 0:
            return

        self._generation += 1
        X = np.atleast_2d(opt.get("X"))
        F = np.atleast_2d(opt.get("F"))
        G = opt.get("G")
        best_x = X[0]
        best_f = float(np.atleast_1d(F[0])[0])
        if G is not None:
            G2 = np.atleast_2d(G)
            best_g = f"{float(np.atleast_1d(G2[0])[0]):.8g}"
        else:
            best_g = ""

        chars = float(best_x[0])
        delay = float(best_x[1]) if best_x.size > 1 else float("nan")
        self._append_row(self._generation, best_f, chars, delay, best_g)


def make_stealth_warm_start_X(problem: ElementwiseProblem, pop_size: int) -> np.ndarray:
    """
    Initial population for generation 0: every individual at the most conservative
    corner of the box — minimum chars/step, maximum delay (within problem bounds).
    Passing this array as sampling= overrides random sampling in [xl, xu].
    """
    stealth = np.array([[1.0, 60.0]], dtype=float)
    return np.tile(stealth, (pop_size, 1))


def _binary_detection_constraint(feedback_status: int) -> float:
    """
    Inequality constraint g <= 0 means feasible.
    Uses only detection_status (0/1), not anomaly_score or threshold.
    """
    return 1.0 if feedback_status == 1 else 0.0


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

            g_detection = _binary_detection_constraint(feedback["status"])

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

            # Binary feedback only: no use of raw score for F or G.
            if self.stop_requested:
                out["F"] = [DETECTED_FITNESS_PENALTY]
                out["G"] = [1.0]
                return

            if is_detected:
                out["F"] = [DETECTED_FITNESS_PENALTY]
                out["G"] = [1.0]
                return

            f1 = -1.0 * throughput_this_burst

        out["F"] = [f1]
        out["G"] = [0.0]


if __name__ == "__main__":
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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

    history_cb = OptimizationHistoryCallback(_SCRIPT_DIR)

    res = minimize(
        problem,
        algorithm,
        ("n_gen", 50),
        seed=1,
        verbose=True,
        callback=history_cb,
    )

    # Final best solution (separate small artifact; overwrite each run).
    _final_path = os.path.join(_SCRIPT_DIR, "final_best_params.csv")
    try:
        with open(_final_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "finished_utc",
                    "best_chars_per_step",
                    "best_delay",
                    "best_fitness",
                    "best_g",
                ]
            )
            if res.X is not None and res.F is not None:
                x = np.atleast_1d(res.X).flatten()
                fv = float(np.atleast_1d(res.F).flatten()[0])
                gv = ""
                if res.G is not None:
                    gv = f"{float(np.atleast_1d(res.G).flatten()[0]):.8g}"
                w.writerow(
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        f"{float(x[0]):.8g}",
                        f"{float(x[1]):.8g}" if x.size > 1 else "",
                        f"{fv:.8g}",
                        gv,
                    ]
                )
            else:
                w.writerow(
                    [
                        datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "",
                        "",
                        "",
                        "",
                    ]
                )
            f.flush()
            os.fsync(f.fileno())
        print(f"[GA] Wrote final best solution to {_final_path}")
    except OSError as e:
        print(f"[GA] Failed to write final_best_params.csv: {e}")

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
