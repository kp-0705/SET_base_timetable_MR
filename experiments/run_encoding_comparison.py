"""Experiment 1: Empirical Comparison of Cardinality Encodings (Pairwise vs Sequential vs Commander)."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from core.data_loader import load_from_json
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService
from core.timetable_decoder import decode_timetable
from core.timetable_validator import TimetableValidator
import config


def run_experiment() -> pd.DataFrame:
    instance_path = config.SAMPLE_DATA_DIR / "feasible_instance.json"
    instance = load_from_json(instance_path)

    results = []
    strategies = ["pairwise", "sequential", "commander"]

    for strat in strategies:
        encoder = ConstraintEncoder(instance, cardinality_strategy=strat)
        enc_res = encoder.encode()

        solver = SATSolverService("glucose4")
        sol_res = solver.solve(enc_res.clauses)

        is_valid = False
        if sol_res.status == "SAT":
            entries = decode_timetable(sol_res.model, enc_res.primary_vars, instance)
            validator = TimetableValidator(instance)
            is_valid, _ = validator.validate(entries)

        results.append({
            "Strategy": strat.capitalize(),
            "Primary Variables": enc_res.stats["num_primary_vars"],
            "Auxiliary Variables": enc_res.stats["num_aux_vars"],
            "Total Variables": enc_res.stats["total_vars"],
            "Total Clauses": enc_res.stats["total_clauses"],
            "CNF Generation Time (s)": enc_res.stats["generation_time_sec"],
            "Solving Time (s)": sol_res.solving_time_sec,
            "Solving Time (ms)": sol_res.solving_time_sec * 1000.0,
            "Status": sol_res.status,
            "Independent Audit Valid": is_valid
        })

    df = pd.DataFrame(results)
    out_file = config.RESULTS_DIR / "encoding_comparison.csv"
    df.to_csv(out_file, index=False)
    print(f"Saved encoding comparison results to: {out_file}")
    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    run_experiment()
