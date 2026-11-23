"""Unit tests verifying mathematical correctness of cardinality encodings."""

import pytest
from pysat.solvers import Minisat22
from core.variable_manager import VariableManager
from core.cardinality import (
    encode_at_least_one,
    encode_at_most_one_pairwise,
    encode_at_most_one_sequential,
    encode_at_most_one_commander,
    encode_at_most_one,
    encode_exactly_one
)


def count_satisfying_assignments(clauses, primary_vars):
    """Enumerates all satisfying models projected onto primary variables."""
    models = set()
    # Add tautologies for primary_vars so the solver is aware of variables even if clauses=[]
    tautologies = [[v, -v] for v in primary_vars]
    full_clauses = list(clauses) + tautologies
    with Minisat22(bootstrap_with=full_clauses) as solver:
        for model in solver.enum_models():
            # Project onto primary variables
            proj = tuple(1 if v in model else 0 for v in primary_vars)
            models.add(proj)
    return models


@pytest.mark.parametrize("n", [1, 2, 4, 6])
def test_at_least_one(n):
    lits = list(range(1, n + 1))
    clauses = encode_at_least_one(lits)
    models = count_satisfying_assignments(clauses, lits)
    # Total models should be 2^n - 1 (all except all zeros)
    assert len(models) == (2 ** n) - 1
    assert tuple([0] * n) not in models


@pytest.mark.parametrize("strategy", ["pairwise", "sequential", "commander"])
@pytest.mark.parametrize("n", [1, 2, 3, 5, 7])
def test_at_most_one_encodings(strategy, n):
    vm = VariableManager(start_id=n + 1)
    lits = list(range(1, n + 1))
    clauses = encode_at_most_one(lits, strategy=strategy, var_mgr=vm)
    
    models = count_satisfying_assignments(clauses, lits)
    
    # Valid assignments: all zeros, or exactly one 1. Total: n + 1
    expected_models = set()
    expected_models.add(tuple([0] * n))
    for i in range(n):
        row = [0] * n
        row[i] = 1
        expected_models.add(tuple(row))
        
    assert models == expected_models
    assert len(models) == n + 1


@pytest.mark.parametrize("strategy", ["pairwise", "sequential", "commander"])
@pytest.mark.parametrize("n", [1, 2, 4, 5])
def test_exactly_one_encodings(strategy, n):
    vm = VariableManager(start_id=n + 1)
    lits = list(range(1, n + 1))
    clauses = encode_exactly_one(lits, strategy=strategy, var_mgr=vm)
    
    models = count_satisfying_assignments(clauses, lits)
    
    # Valid assignments: exactly one variable is 1. Total: n
    expected_models = set()
    for i in range(n):
        row = [0] * n
        row[i] = 1
        expected_models.add(tuple(row))
        
    assert models == expected_models
    assert len(models) == n
