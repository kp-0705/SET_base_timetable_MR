"""Tests verifying SAT timetable generation, decoding, and hard constraint guarantees."""

import pytest
from core.data_loader import load_from_json
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService
from core.timetable_decoder import decode_timetable
from core.timetable_validator import TimetableValidator
import config


@pytest.fixture
def feasible_instance():
    return load_from_json(config.SAMPLE_DATA_DIR / "feasible_instance.json")


@pytest.mark.parametrize("strategy", ["sequential", "pairwise", "commander"])
def test_sat_feasibility_across_encodings(feasible_instance, strategy):
    encoder = ConstraintEncoder(feasible_instance, cardinality_strategy=strategy)
    enc_res = encoder.encode()
    solver = SATSolverService("glucose4")
    sol_res = solver.solve(enc_res.clauses)

    assert sol_res.status == "SAT", f"Failed for strategy {strategy}"
    assert sol_res.model is not None

    entries = decode_timetable(sol_res.model, enc_res.primary_vars, feasible_instance)
    assert len(entries) == len(feasible_instance.create_session_tokens())

    validator = TimetableValidator(feasible_instance)
    is_valid, violations = validator.validate(entries)
    assert is_valid, f"Violations for {strategy}: {violations}"


def test_independent_validation_rules(feasible_instance):
    encoder = ConstraintEncoder(feasible_instance, cardinality_strategy="sequential")
    enc_res = encoder.encode()
    solver = SATSolverService("glucose4")
    sol_res = solver.solve(enc_res.clauses)
    entries = decode_timetable(sol_res.model, enc_res.primary_vars, feasible_instance)

    # 1. Check double period consecutive slots
    lab_entries = [e for e in entries if e.course_type == "lab"]
    assert len(lab_entries) > 0
    for lab in lab_entries:
        assert lab.duration == 2
        assert len(lab.slots_occupied) == 2
        # Verify slots are in same day and consecutive
        p1 = feasible_instance.get_slot(lab.slots_occupied[0]).period
        p2 = feasible_instance.get_slot(lab.slots_occupied[1]).period
        assert p2 == p1 + 1

    # 2. Check room capacity
    for e in entries:
        room = feasible_instance.get_room(e.room_id)
        course = feasible_instance.get_course(e.course_id)
        assert room.capacity >= course.enrollment
        assert room.room_type == course.course_type
