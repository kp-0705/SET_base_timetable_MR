"""Optional Z3 SMT (Satisfiability Modulo Theories) baseline for comparison."""

import time
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass

try:
    import z3
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False

from core.models import SchedulingInstance, TimetableEntry, SessionToken
from core.data_validator import get_valid_slot_room_pairs, compute_consecutive_slot


@dataclass
class SMTResult:
    status: str  # "SAT", "UNSAT", or "UNAVAILABLE"
    solving_time_sec: float = 0.0
    variables_count: int = 0
    assertions_count: int = 0
    model_entries_count: int = 0


class Z3SMTSolver:
    """
    Implements university timetabling using Z3 SMT formulation.
    Serves as an academic baseline to compare First-Order Theories vs Pure Propositional SAT.
    """

    def __init__(self, instance: SchedulingInstance):
        self.instance = instance

    def solve(self) -> SMTResult:
        if not Z3_AVAILABLE:
            return SMTResult(status="UNAVAILABLE")

        start_time = time.perf_counter()
        solver = z3.Solver()

        session_tokens = self.instance.create_session_tokens()
        slots = self.instance.time_slots
        rooms = self.instance.rooms

        slots_map = {s.slot_id: s for s in slots}
        slots_by_day_period = {(s.day, s.period): s for s in slots}

        # Boolean decision variables in Z3: x[s, t, r]
        x_vars: Dict[Tuple[str, str, str], z3.BoolRef] = {}

        for session in session_tokens:
            valid_pairs = get_valid_slot_room_pairs(
                session, self.instance, slots_map, slots_by_day_period
            )
            for slot_id, room_id in valid_pairs:
                name = f"x_{session.session_id}_{slot_id}_{room_id}"
                x_vars[(session.session_id, slot_id, room_id)] = z3.Bool(name)

        # 1. Exactly-One slot and room per session
        for session in session_tokens:
            s_lits = [
                var for (s_id, _, _), var in x_vars.items()
                if s_id == session.session_id
            ]
            if not s_lits:
                solver.add(z3.BoolVal(False))
                continue
            # Exactly one in Z3: AtLeastOne and AtMostOne
            solver.add(z3.Or(s_lits))
            # Pairwise AMO in Z3
            for i in range(len(s_lits)):
                for j in range(i + 1, len(s_lits)):
                    solver.add(z3.Or(z3.Not(s_lits[i]), z3.Not(s_lits[j])))

        # 2. Room, Faculty, Batch Mutual Exclusion
        room_slot_vars: Dict[Tuple[str, str], List[z3.BoolRef]] = {}
        fac_slot_vars: Dict[Tuple[str, str], List[z3.BoolRef]] = {}
        batch_slot_vars: Dict[Tuple[str, str], List[z3.BoolRef]] = {}

        for (session_id, slot_id, room_id), var in x_vars.items():
            session = next(t for t in session_tokens if t.session_id == session_id)
            occupied = [slot_id]
            if session.duration == 2:
                next_slot = compute_consecutive_slot(slot_id, slots_map, slots_by_day_period)
                if next_slot:
                    occupied.append(next_slot)

            for occ in occupied:
                room_slot_vars.setdefault((room_id, occ), []).append(var)
                fac_slot_vars.setdefault((session.faculty_id, occ), []).append(var)
                batch_slot_vars.setdefault((session.batch_id, occ), []).append(var)

        for group in [room_slot_vars, fac_slot_vars, batch_slot_vars]:
            for _, var_list in group.items():
                if len(var_list) > 1:
                    for i in range(len(var_list)):
                        for j in range(i + 1, len(var_list)):
                            solver.add(z3.Or(z3.Not(var_list[i]), z3.Not(var_list[j])))

        # Solve
        check_res = solver.check()
        solve_time = time.perf_counter() - start_time

        if check_res == z3.sat:
            model = solver.model()
            # Count active assignments
            active = sum(1 for var in x_vars.values() if z3.is_true(model.eval(var)))
            return SMTResult(
                status="SAT",
                solving_time_sec=round(solve_time, 4),
                variables_count=len(x_vars),
                assertions_count=len(solver.assertions()),
                model_entries_count=active
            )
        else:
            return SMTResult(
                status="UNSAT",
                solving_time_sec=round(solve_time, 4),
                variables_count=len(x_vars),
                assertions_count=len(solver.assertions()),
                model_entries_count=0
            )
