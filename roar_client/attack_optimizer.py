from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.algorithms.moo.nsga2 import NSGA2
import numpy as np
import os
import time

from text_perturbation_tool import run_workload_burst

class RoarOptimizationProblem(ElementwiseProblem):
    def __init__(self):
        super().__init__(
            n_var=2,
            n_obj=2,
            xl=np.array([1, 0.2]),
            xu=np.array([50, 20.0]),
        )

    def _evaluate(self, x, out, *args, **kwargs):
        chars_per_step = int(x[0])
        delay = float(x[1])

        total_modified = run_workload_burst(
            chars_per_step, delay, test_duration_sec=10.0
        )

        # Objective 1: maximize throughput (as minimization objective)
        f1 = -1.0 * total_modified
        # Objective 2: minimize busy/contended signal
        f2 = self.get_system_busy_signal()

        out["F"] = [f1, f2]

    def get_system_busy_signal(self):
        detection_status_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "detection_status.txt",
        )
        try:
            with open(detection_status_path, "r", encoding="utf-8") as f:
                status = f.read().strip()
            if status == "1":
                return 1.0
            return 0.0
        except (FileNotFoundError, OSError):
            return 0.0


if __name__ == "__main__":
    WARMUP_DURATION = 120
    print(f"Waiting for server warmup ({WARMUP_DURATION}s) to establish baseline...")
    time.sleep(WARMUP_DURATION)

    problem = RoarOptimizationProblem()
    algorithm = NSGA2(pop_size=10)

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
