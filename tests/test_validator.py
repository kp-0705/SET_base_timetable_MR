"""Tests verifying that the decoupled TimetableValidator reliably catches corruptions."""

import pytest
import copy
from core.data_loader import load_from_json
from core.constraint_encoder import ConstraintEncoder
from core.sat_solver import SATSolverService
from core.timetable_decoder import decode_timetable
from core.timetable_validator import TimetableValidator
import config


@pytest.fixture
def valid_entries():
    instance = load_from_json(config.SAMPLE_DATA_DIR / "feasible_instance.json")
    enc_res = ConstraintEncoder(instance).encode()
    sat_res = SATSolverService("glucose4").solve(enc_res.clauses)
    return decode_timetable(sat_res.model, enc_res.primary_vars, instance), instance


def test_validator_detects_room_clash(valid_entries):
    entries, instance = valid_entries
    corrupted = copy.deepcopy(entries)
    # Corrupt: assign entry 1 to the same room and slot as entry 0
    corrupted[1].room_id = corrupted[0].room_id
    corrupted[1].slots_occupied = list(corrupted[0].slots_occupied)
    corrupted[1].day = corrupted[0].day
    corrupted[1].start_period = corrupted[0].start_period

    validator = TimetableValidator(instance)
    is_valid, violations = validator.validate(corrupted)
    assert not is_valid
    assert any("Room Clash" in v for v in violations)


def test_validator_detects_faculty_clash(valid_entries):
    entries, instance = valid_entries
    corrupted = copy.deepcopy(entries)
    # Corrupt: assign same faculty to different sessions at the same slot
    corrupted[1].faculty_id = corrupted[0].faculty_id
    corrupted[1].slots_occupied = list(corrupted[0].slots_occupied)
    corrupted[1].day = corrupted[0].day

    validator = TimetableValidator(instance)
    is_valid, violations = validator.validate(corrupted)
    assert not is_valid
    assert any("Faculty Clash" in v for v in violations)


def test_validator_detects_batch_clash(valid_entries):
    entries, instance = valid_entries
    corrupted = copy.deepcopy(entries)
    # Corrupt: assign same batch to two sessions at the same slot
    corrupted[1].batch_id = corrupted[0].batch_id
    corrupted[1].slots_occupied = list(corrupted[0].slots_occupied)
    corrupted[1].day = corrupted[0].day

    validator = TimetableValidator(instance)
    is_valid, violations = validator.validate(corrupted)
    assert not is_valid
    assert any("Batch Clash" in v for v in violations)


def test_validator_detects_missing_session(valid_entries):
    entries, instance = valid_entries
    corrupted = copy.deepcopy(entries)[:-1]  # remove one session

    validator = TimetableValidator(instance)
    is_valid, violations = validator.validate(corrupted)
    assert not is_valid
    assert any("Missing sessions" in v for v in violations)


def test_validator_detects_non_contiguous_lab(valid_entries):
    entries, instance = valid_entries
    corrupted = copy.deepcopy(entries)
    lab_entry = next(e for e in corrupted if e.course_type == "lab")
    # Separate slots to non-consecutive
    lab_entry.slots_occupied = ["Mon_1", "Mon_3"]

    validator = TimetableValidator(instance)
    is_valid, violations = validator.validate(corrupted)
    assert not is_valid
    assert any("Non-contiguous Lab" in v for v in violations)
