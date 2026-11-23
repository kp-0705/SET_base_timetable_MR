"""Experiment 2: Solver Backend Benchmarking (Glucose4 vs CaDiCaL vs Minisat22)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from core.data_loader import load_from_json
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService, CADICAL_AVAILABLE
import config


def run_experiment() -> pd.DataFrame:
    instance_path = config.SAMPLE_DATA_DIR / "feasible_instance.json"
    instance = load_from_json(instance_path)

    # Encode once using sequential counter
    encoder = ConstraintEncoder(instance, cardinality_strategy="sequential")
    enc_res = encoder.encode()

    solvers_to_test = ["glucose4", "minisat22"]
    if CADICAL_AVAILABLE:
        solvers_to_test.append("cadical153")

    results = []
    # Perform 3 warmup/repetition runs for statistical stability
    for solver_name in solvers_to_test:
        solve_times = []
        conflicts_list = []
        propagations_list = []
        decisions_list = []
        status = "UNKNOWN"

        for _ in range(3):
            svc = SATSolverService(solver_name)
            sol_res = svc.solve(enc_res.clauses)
            status = sol_res.status
            solve_times.append(sol_res.solving_time_sec)
            conflicts_list.append(sol_res.conflicts)
            propagations_list.append(sol_res.propagations)
            decisions_list.append(sol_res.decisions)

        avg_time = sum(solve_times) / len(solve_times)
        results.append({
            "Solver": solver_name.upper(),
            "Status": status,
            "Mean Solve Time (s)": round(avg_time, 5),
            "Mean Solve Time (ms)": round(avg_time * 1000.0, 2),
            "Total Clauses": enc_res.stats["total_clauses"],
            "Total Variables": enc_res.stats["total_vars"],
            "Conflicts": round(sum(conflicts_list) / len(conflicts_list), 1),
            "Propagations": round(sum(propagations_list) / len(propagations_list), 1),
            "Decisions": round(sum(decisions_list) / len(decisions_list), 1)
        })

    df = pd.DataFrame(results)
    out_file = config.RESULTS_DIR / "solver_comparison.csv"
    df.to_csv(out_file, index=False)
    print(f"Saved solver comparison results to: {out_file}")
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    run_experiment()
