"""Propositional CNF Constraint Generator for Timetabling."""

import time
from typing import List, Dict, Tuple, Set, Optional, Any
from dataclasses import dataclass, field

from core.models import SchedulingInstance, SessionToken, TimeSlot, Room, Faculty, Course
from core.variable_manager import VariableManager
from core.cardinality import encode_exactly_one, encode_at_most_one
from core.data_validator import get_valid_slot_room_pairs, compute_consecutive_slot


@dataclass
class EncodingResult:
    """Encapsulates the generated CNF formula and metadata."""
    clauses: List[List[int]]
    var_mgr: VariableManager
    primary_vars: Dict[Tuple[str, str, str], int] = field(default_factory=dict)  # (session_id, slot_id, room_id) -> var_id
    assumption_vars: List[int] = field(default_factory=list)
    assumption_to_group: Dict[int, str] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)


class ConstraintEncoder:
    """
    Transforms scheduling domain constraints into Conjunctive Normal Form (CNF).
    Supports Pairwise, Sequential Sinz, and Commander cardinality encodings.
    Optionally instruments clauses with assumption selector literals for UNSAT core extraction.
    """

    def __init__(
        self,
        instance: SchedulingInstance,
        cardinality_strategy: str = "sequential",
        enable_assumptions: bool = False
    ):
        self.instance = instance
        self.strategy = cardinality_strategy.lower()
        self.enable_assumptions = enable_assumptions
        self.var_mgr = VariableManager()

        # Build slot lookup maps
        self.slots_map: Dict[str, TimeSlot] = {s.slot_id: s for s in instance.time_slots}
        self.slots_by_day_period: Dict[Tuple[str, int], TimeSlot] = {
            (s.day, s.period): s for s in instance.time_slots
        }

        # Track clauses and assumptions
        self.clauses: List[List[int]] = []
        self.primary_vars: Dict[Tuple[str, str, str], int] = {}
        self.assumption_vars: List[int] = []
        self.assumption_to_desc: Dict[int, str] = {}

    def _guard_clauses(self, raw_clauses: List[List[int]], group_name: str, *details: Any) -> None:
        """Appends clauses to formula, optionally guarding them with an assumption selector literal."""
        if not self.enable_assumptions:
            self.clauses.extend(raw_clauses)
            return

        # Allocate selector literal: (Clause \lor \neg alpha)
        alpha = self.var_mgr.allocate_assumption_var(group_name, *details)
        self.assumption_vars.append(alpha)
        desc = self.var_mgr.get_assumption_description(alpha)
        self.assumption_to_desc[alpha] = desc or f"{group_name}"

        for clause in raw_clauses:
            self.clauses.append(clause + [-alpha])

    def encode(self) -> EncodingResult:
        """Executes full propositional CNF encoding across all hard constraints."""
        start_time = time.perf_counter()
        session_tokens = self.instance.create_session_tokens()

        # Grouping indices for mutual exclusion
        session_vars_map: Dict[str, List[int]] = {}  # session_id -> list of x_vars
        room_slot_occupancy: Dict[Tuple[str, str], List[int]] = {}  # (room_id, slot_id) -> list of x_vars
        faculty_slot_occupancy: Dict[Tuple[str, str], List[int]] = {}  # (faculty_id, slot_id) -> list of x_vars
        batch_slot_occupancy: Dict[Tuple[str, str], List[int]] = {}  # (batch_id, slot_id) -> list of x_vars
        course_day_occupancy: Dict[Tuple[str, str], List[int]] = {}  # (course_id, day) -> list of x_vars

        # 1. Allocate primary decision variables x[s, t, r] using domain pre-filtering
        for session in session_tokens:
            valid_pairs = get_valid_slot_room_pairs(
                session, self.instance, self.slots_map, self.slots_by_day_period
            )
            s_vars: List[int] = []
            for slot_id, room_id in valid_pairs:
                x_var = self.var_mgr.get_var("x", session.session_id, slot_id, room_id)
                self.primary_vars[(session.session_id, slot_id, room_id)] = x_var
                s_vars.append(x_var)

                # Determine all slots occupied by this session starting at slot_id
                start_slot = self.slots_map[slot_id]
                occupied_slots = [slot_id]
                if session.duration == 2:
                    next_slot_id = compute_consecutive_slot(
                        slot_id, self.slots_map, self.slots_by_day_period
                    )
                    if next_slot_id:
                        occupied_slots.append(next_slot_id)

                # Index into occupancy buckets for mutual exclusion
                for occ_slot in occupied_slots:
                    room_slot_occupancy.setdefault((room_id, occ_slot), []).append(x_var)
                    faculty_slot_occupancy.setdefault((session.faculty_id, occ_slot), []).append(x_var)
                    batch_slot_occupancy.setdefault((session.batch_id, occ_slot), []).append(x_var)

                course_day_occupancy.setdefault((session.course_id, start_slot.day), []).append(x_var)

            session_vars_map[session.session_id] = s_vars

        # -------------------------------------------------------------
        # Hard Constraint 1: Session Assignment (Exactly-One)
        # Every session must start in exactly one valid slot and room
        # -------------------------------------------------------------
        for session in session_tokens:
            s_vars = session_vars_map.get(session.session_id, [])
            if not s_vars:
                # If domain pruning left 0 valid slots/rooms, instance is trivially UNSAT
                dummy_unsat = [[]]
                self._guard_clauses(
                    dummy_unsat, 
                    "SESSION_ASSIGNMENT", 
                    f"No valid slots/rooms for {session.session_id}"
                )
                continue

            eo_clauses = encode_exactly_one(
                s_vars, strategy=self.strategy, var_mgr=self.var_mgr
            )
            self._guard_clauses(
                eo_clauses, 
                "SESSION_ASSIGNMENT", 
                f"Course {session.course_id} session {session.session_index}"
            )

        # -------------------------------------------------------------
        # Hard Constraint 2: Room Non-Overlap (Mutual Exclusion)
        # At most one session occupying (room, slot)
        # -------------------------------------------------------------
        for (room_id, slot_id), x_vars in room_slot_occupancy.items():
            if len(x_vars) > 1:
                amo_clauses = encode_at_most_one(
                    x_vars, strategy=self.strategy, var_mgr=self.var_mgr
                )
                self._guard_clauses(
                    amo_clauses, 
                    "ROOM_CONFLICT", 
                    f"Room {room_id} at {slot_id}"
                )

        # -------------------------------------------------------------
        # Hard Constraint 3: Faculty Non-Clash (Mutual Exclusion)
        # At most one session taught by faculty member at slot
        # -------------------------------------------------------------
        for (faculty_id, slot_id), x_vars in faculty_slot_occupancy.items():
            if len(x_vars) > 1:
                amo_clauses = encode_at_most_one(
                    x_vars, strategy=self.strategy, var_mgr=self.var_mgr
                )
                self._guard_clauses(
                    amo_clauses, 
                    "FACULTY_CONFLICT", 
                    f"Faculty {faculty_id} at {slot_id}"
                )

        # -------------------------------------------------------------
        # Hard Constraint 4: Batch Non-Clash (Mutual Exclusion)
        # At most one session attended by student batch at slot
        # -------------------------------------------------------------
        for (batch_id, slot_id), x_vars in batch_slot_occupancy.items():
            if len(x_vars) > 1:
                amo_clauses = encode_at_most_one(
                    x_vars, strategy=self.strategy, var_mgr=self.var_mgr
                )
                self._guard_clauses(
                    amo_clauses, 
                    "BATCH_CONFLICT", 
                    f"Batch {batch_id} at {slot_id}"
                )

        # -------------------------------------------------------------
        # Hard Constraint 5: Course Daily Spreading
        # Prevent multiple sessions of same lecture course on same day
        # -------------------------------------------------------------
        for (course_id, day), x_vars in course_day_occupancy.items():
            course = self.instance.get_course(course_id)
            if course and course.course_type == "lecture" and course.sessions_per_week > 1:
                if len(x_vars) > 1:
                    amo_clauses = encode_at_most_one(
                        x_vars, strategy=self.strategy, var_mgr=self.var_mgr
                    )
                    self._guard_clauses(
                        amo_clauses, 
                        "COURSE_DAILY_SPREAD", 
                        f"Course {course_id} on {day}"
                    )

        gen_time = time.perf_counter() - start_time
        stats = {
            "num_primary_vars": len(self.primary_vars),
            "num_aux_vars": self.var_mgr.aux_variables_count,
            "total_vars": self.var_mgr.total_variables,
            "total_clauses": len(self.clauses),
            "generation_time_sec": round(gen_time, 4),
            "strategy": self.strategy,
            "assumptions_enabled": self.enable_assumptions,
            "num_assumptions": len(self.assumption_vars),
        }

        return EncodingResult(
            clauses=self.clauses,
            var_mgr=self.var_mgr,
            primary_vars=self.primary_vars,
            assumption_vars=self.assumption_vars,
            assumption_to_group=self.assumption_to_desc,
            stats=stats
        )
