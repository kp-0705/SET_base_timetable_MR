"""Partial Weighted MaxSAT Optimization Engine using PySAT's RC2 solver."""

import time
from typing import List, Dict, Tuple, Set, Optional, Any
from dataclasses import dataclass, field

from pysat.formula import WCNF
from pysat.examples.rc2 import RC2

from core.models import SchedulingInstance, TimetableEntry, SessionToken
from core.constraint_encoder import ConstraintEncoder, EncodingResult
from core.timetable_decoder import decode_timetable
from core.timetable_validator import TimetableValidator
from config import DEFAULT_SOFT_WEIGHTS


@dataclass
class MaxSATResult:
    """Encapsulates the MaxSAT optimization results and comparison metrics."""
    status: str  # "OPTIMIZED" or "UNSAT"
    optimized_entries: List[TimetableEntry] = field(default_factory=list)
    initial_entries: List[TimetableEntry] = field(default_factory=list)
    optimal_cost: int = 0
    initial_cost: int = 0
    total_soft_clauses: int = 0
    satisfied_soft_clauses: int = 0
    violated_soft_clauses: int = 0
    optimization_time_sec: float = 0.0
    soft_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)


class MaxSATOptimizer:
    """
    Formulates Weighted Partial MaxSAT problems where:
    - Institutional scheduling constraints are strictly HARD (weight = top / infinity).
    - Pedagogical and faculty preferences are SOFT (penalized by positive weights).
    """

    def __init__(
        self,
        instance: SchedulingInstance,
        weights: Optional[Dict[str, int]] = None,
        cardinality_strategy: str = "sequential"
    ):
        self.instance = instance
        self.weights = weights or DEFAULT_SOFT_WEIGHTS.copy()
        self.strategy = cardinality_strategy

    def optimize(self, initial_sat_model: Optional[List[int]] = None) -> MaxSATResult:
        """
        Builds the WCNF formula, invokes RC2, and decodes the Pareto-optimal timetable.
        """
        start_time = time.perf_counter()

        # 1. Encode all Hard Constraints
        encoder = ConstraintEncoder(
            self.instance,
            cardinality_strategy=self.strategy,
            enable_assumptions=False
        )
        enc_res: EncodingResult = encoder.encode()

        # 2. Initialize Weighted CNF (WCNF)
        wcnf = WCNF()
        for clause in enc_res.clauses:
            wcnf.append(clause)  # Appending without weight marks clause as HARD

        # 3. Formulate Soft Constraints with Weights
        soft_clause_metadata: List[Tuple[List[int], int, str]] = []  # (clause, weight, rule_name)

        w_idle = self.weights.get("minimize_student_idle_gaps", 3)
        w_extreme = self.weights.get("avoid_extreme_periods", 2)
        w_pref = self.weights.get("faculty_preferred_slots", 5)
        w_balance = self.weights.get("balance_faculty_daily_load", 4)

        slots_map = {s.slot_id: s for s in self.instance.time_slots}
        slots_by_day_period = {(s.day, s.period): s for s in self.instance.time_slots}

        # Index primary variables for fast soft-clause construction
        # batch_day_period_vars[(batch_id, day, period)] -> list of primary vars
        batch_period_vars: Dict[Tuple[str, str, int], List[int]] = {}
        for (session_id, slot_id, room_id), var_id in enc_res.primary_vars.items():
            session = next(t for t in self.instance.create_session_tokens() if t.session_id == session_id)
            slot = slots_map[slot_id]
            batch_period_vars.setdefault((session.batch_id, slot.day, slot.period), []).append(var_id)
            if session.duration == 2:
                next_tuple = (slot.day, slot.period + 1)
                if next_tuple in slots_by_day_period:
                    batch_period_vars.setdefault((session.batch_id, slot.day, slot.period + 1), []).append(var_id)

        # Soft Constraint A: Avoid Extreme Periods (Period 1 and Period 6)
        if w_extreme > 0:
            for (session_id, slot_id, room_id), var_id in enc_res.primary_vars.items():
                slot = slots_map[slot_id]
                if slot.period in {1, 6}:
                    # Penalize scheduling in period 1 or 6
                    soft_clause = [-var_id]
                    wcnf.append(soft_clause, weight=w_extreme)
                    soft_clause_metadata.append((soft_clause, w_extreme, "avoid_extreme_periods"))

        # Soft Constraint B: Faculty Preferred Slots
        if w_pref > 0:
            for fac in self.instance.faculty:
                if fac.preferred_slots:
                    pref_set = set(fac.preferred_slots)
                    for (session_id, slot_id, room_id), var_id in enc_res.primary_vars.items():
                        session = next(t for t in self.instance.create_session_tokens() if t.session_id == session_id)
                        if session.faculty_id == fac.faculty_id and slot_id not in pref_set:
                            soft_clause = [-var_id]
                            wcnf.append(soft_clause, weight=w_pref)
                            soft_clause_metadata.append((soft_clause, w_pref, "faculty_preferred_slots"))

        # Soft Constraint C: Student Idle Gaps (Minimize gaps between lectures on the same day)
        if w_idle > 0:
            for batch in self.instance.batches:
                for day in {s.day for s in self.instance.time_slots}:
                    for p in range(1, 5):  # check periods p, p+1, p+2
                        vars_p = batch_period_vars.get((batch.batch_id, day, p), [])
                        vars_p1 = batch_period_vars.get((batch.batch_id, day, p + 1), [])
                        vars_p2 = batch_period_vars.get((batch.batch_id, day, p + 2), [])

                        # If batch has class at p and class at p+2, but no class at p+1:
                        # Clause: \neg x_p \lor \neg x_{p+2} \lor x_{p+1}
                        if vars_p and vars_p2:
                            # For each pair (x_p, x_{p+2}), we prefer \neg x_p \lor \neg x_{p+2} \lor \bigvee vars_p1
                            for xp in vars_p:
                                for xp2 in vars_p2:
                                    gap_clause = [-xp, -xp2] + vars_p1
                                    wcnf.append(gap_clause, weight=w_idle)
                                    soft_clause_metadata.append((gap_clause, w_idle, "minimize_student_idle_gaps"))

        # 4. Invoke RC2 MaxSAT Solver
        with RC2(wcnf) as rc2:
            model = rc2.compute()
            if model is None:
                opt_time = time.perf_counter() - start_time
                return MaxSATResult(
                    status="UNSAT",
                    optimization_time_sec=round(opt_time, 4)
                )

            opt_cost = rc2.cost
            opt_time = time.perf_counter() - start_time

        # 5. Decode Timetables
        opt_entries = decode_timetable(model, enc_res.primary_vars, self.instance)
        init_entries = decode_timetable(initial_sat_model, enc_res.primary_vars, self.instance) if initial_sat_model else []

        # 6. Evaluate Soft Constraints Satisfaction
        model_set = set(model)
        satisfied_count = 0
        violated_count = 0
        rule_breakdown: Dict[str, Dict[str, int]] = {}

        for clause, weight, rule_name in soft_clause_metadata:
            rule_breakdown.setdefault(rule_name, {"satisfied": 0, "violated": 0, "weight": weight})
            # A clause is satisfied if at least one literal is True under the model
            is_satisfied = any((lit > 0 and lit in model_set) or (lit < 0 and -lit not in model_set) for lit in clause)
            if is_satisfied:
                satisfied_count += 1
                rule_breakdown[rule_name]["satisfied"] += 1
            else:
                violated_count += 1
                rule_breakdown[rule_name]["violated"] += 1

        # Calculate initial cost if initial model was provided
        init_cost = 0
        if initial_sat_model:
            init_set = set(initial_sat_model)
            for clause, weight, rule_name in soft_clause_metadata:
                is_sat = any((lit > 0 and lit in init_set) or (lit < 0 and -lit not in init_set) for lit in clause)
                if not is_sat:
                    init_cost += weight
        else:
            init_cost = opt_cost

        return MaxSATResult(
            status="OPTIMIZED",
            optimized_entries=opt_entries,
            initial_entries=init_entries,
            optimal_cost=opt_cost,
            initial_cost=init_cost,
            total_soft_clauses=len(soft_clause_metadata),
            satisfied_soft_clauses=satisfied_count,
            violated_soft_clauses=violated_count,
            optimization_time_sec=round(opt_time, 4),
            soft_breakdown=rule_breakdown
        )
