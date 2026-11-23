"""Tests verifying UNSAT detection, core extraction, and infeasibility explanation."""

import pytest
from core.data_loader import load_from_json
from core.unsat_explainer import UnsatExplainer
import config


def test_infeasible_instance_detection():
    instance = load_from_json(config.SAMPLE_DATA_DIR / "infeasible_instance.json")
    explainer = UnsatExplainer(instance, cardinality_strategy="sequential")
    diag = explainer.diagnose(minimize_core=True)

    assert diag.is_infeasible is True
    assert len(diag.raw_core_literals) > 0
    assert len(diag.minimal_core_literals) > 0
    assert len(diag.minimal_core_literals) <= len(diag.raw_core_literals)

    # Assert that room conflict or session assignment was identified in core
    cats = diag.conflicting_categories
    assert "ROOM_CONFLICT" in cats or "SESSION_ASSIGNMENT" in cats
    assert len(diag.suggested_relaxations) > 0
    assert "No valid timetable" in diag.summary_explanation


def test_feasible_instance_returns_feasible():
    instance = load_from_json(config.SAMPLE_DATA_DIR / "feasible_instance.json")
    explainer = UnsatExplainer(instance, cardinality_strategy="sequential")
    diag = explainer.diagnose()

    assert diag.is_infeasible is False
    assert len(diag.raw_core_literals) == 0
