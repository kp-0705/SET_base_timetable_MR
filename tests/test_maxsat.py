"""Tests verifying MaxSAT soft constraint optimization and hard constraint safety."""

import pytest
from core.data_loader import load_from_json
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService
from core.maxsat_solver import MaxSATOptimizer
from core.timetable_validator import TimetableValidator
import config


def test_maxsat_optimizes_and_preserves_hard_constraints():
    instance = load_from_json(config.SAMPLE_DATA_DIR / "feasible_instance.json")
    
    # 1. Get initial SAT model
    enc_res = ConstraintEncoder(instance).encode()
    sat_res = SATSolverService("glucose4").solve(enc_res.clauses)
    assert sat_res.status == "SAT"

    # 2. Run MaxSAT optimizer
    optimizer = MaxSATOptimizer(instance)
    res = optimizer.optimize(initial_sat_model=sat_res.model)

    assert res.status == "OPTIMIZED"
    assert res.optimal_cost <= res.initial_cost
    assert res.total_soft_clauses > 0
    assert res.satisfied_soft_clauses > 0

    # 3. CRITICAL: Hard constraints must NEVER be violated
    validator = TimetableValidator(instance)
    is_valid, violations = validator.validate(res.optimized_entries)
    assert is_valid, f"MaxSAT violated hard constraints! Violations: {violations}"
