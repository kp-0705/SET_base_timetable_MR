"""UNSAT Core Extraction and Human-Readable Infeasibility Explanation Engine."""

import time
from typing import List, Dict, Tuple, Set, Optional, Any
from dataclasses import dataclass, field

from core.models import SchedulingInstance
from core.constraint_encoder import ConstraintEncoder, EncodingResult
from core.sat_solver import create_pysat_solver


@dataclass
class UnsatExplanationResult:
    """Encapsulates UNSAT diagnosis and human-readable explanations."""
    is_infeasible: bool
    raw_core_literals: List[int] = field(default_factory=list)
    minimal_core_literals: List[int] = field(default_factory=list)
    raw_core_descriptions: List[str] = field(default_factory=list)
    minimal_core_descriptions: List[str] = field(default_factory=list)
    conflicting_categories: Dict[str, List[str]] = field(default_factory=dict)
    summary_explanation: str = ""
    suggested_relaxations: List[str] = field(default_factory=list)
    diagnosis_time_sec: float = 0.0


class UnsatExplainer:
    """
    Performs assumption-based UNSAT core extraction and deletion-based
    Minimal Unsatisfiable Subset (MUS) minimization.
    Produces grounded, non-hallucinated explanations.
    """

    def __init__(self, instance: SchedulingInstance, cardinality_strategy: str = "sequential"):
        self.instance = instance
        self.strategy = cardinality_strategy

    def diagnose(self, minimize_core: bool = True) -> UnsatExplanationResult:
        """
        Executes UNSAT core extraction and optional MUS minimization.
        """
        start_time = time.perf_counter()

        # 1. Encode with assumption selector literals guarding constraint groups
        encoder = ConstraintEncoder(
            self.instance,
            cardinality_strategy=self.strategy,
            enable_assumptions=True
        )
        enc_res: EncodingResult = encoder.encode()

        # 2. Initialize SAT solver and solve under assumptions
        solver, actual_solver_name = create_pysat_solver("glucose4", enc_res.clauses)

        try:
            is_sat = solver.solve(assumptions=enc_res.assumption_vars)
            if is_sat:
                diag_time = time.perf_counter() - start_time
                return UnsatExplanationResult(
                    is_infeasible=False,
                    summary_explanation="The scheduling problem is feasible; no conflict exists.",
                    diagnosis_time_sec=round(diag_time, 4)
                )

            # 3. Extract raw assumption core
            raw_core = solver.get_core() or []
            raw_descriptions = [
                enc_res.assumption_to_group.get(lit, f"Constraint #{lit}")
                for lit in raw_core
            ]

            # 4. Deletion-Based Core Minimization (Extract Minimal Unsatisfiable Subset)
            minimal_core = list(raw_core)
            if minimize_core and len(raw_core) > 1:
                # Iteratively attempt removing each assumption literal
                i = 0
                while i < len(minimal_core):
                    candidate_removal = minimal_core[i]
                    test_assumptions = [lit for lit in minimal_core if lit != candidate_removal]
                    
                    # If still UNSAT without candidate_removal, it was non-minimal -> drop it
                    if not solver.solve(assumptions=test_assumptions):
                        minimal_core = test_assumptions
                    else:
                        i += 1

            minimal_descriptions = [
                enc_res.assumption_to_group.get(lit, f"Constraint #{lit}")
                for lit in minimal_core
            ]

            # 5. Group conflicts by categories
            categories: Dict[str, List[str]] = {}
            for desc in minimal_descriptions:
                parts = desc.split(":", 1)
                cat = parts[0].strip() if len(parts) == 2 else "GENERAL_CONSTRAINT"
                detail = parts[1].strip() if len(parts) == 2 else desc
                categories.setdefault(cat, []).append(detail)

            # 6. Generate human-readable explanation and recommendations
            explanation_lines: List[str] = [
                "No valid timetable could be generated because the schedule is over-constrained."
            ]
            suggestions: List[str] = []

            if "SESSION_ASSIGNMENT" in categories:
                explanation_lines.append(
                    f"- Session Demand: {len(categories['SESSION_ASSIGNMENT'])} course session(s) "
                    f"cannot find an unallocated, compatible room and time slot."
                )
                suggestions.append("Check room capacity, room type (lecture vs lab), or add more available time slots.")

            if "ROOM_CONFLICT" in categories:
                explanation_lines.append(
                    f"- Room Bottleneck: Simultaneous requests compete for: {', '.join(categories['ROOM_CONFLICT'])}."
                )
                suggestions.append("Increase room capacity, assign different rooms, or distribute courses across other days.")

            if "FACULTY_CONFLICT" in categories:
                explanation_lines.append(
                    f"- Faculty Overlap: An instructor is double-booked across: {', '.join(categories['FACULTY_CONFLICT'])}."
                )
                suggestions.append("Adjust faculty teaching assignments or broaden faculty availability windows.")

            if "BATCH_CONFLICT" in categories:
                explanation_lines.append(
                    f"- Student Batch Clash: Cohort has concurrent compulsory courses: {', '.join(categories['BATCH_CONFLICT'])}."
                )
                suggestions.append("Stagger courses for this student batch across non-overlapping periods.")

            if "COURSE_DAILY_SPREAD" in categories:
                explanation_lines.append(
                    f"- Daily Lecture Limits: Violations in spreading courses across days: {', '.join(categories['COURSE_DAILY_SPREAD'])}."
                )
                suggestions.append("Allow multiple sessions per day or add more teaching days.")

            diag_time = time.perf_counter() - start_time

            return UnsatExplanationResult(
                is_infeasible=True,
                raw_core_literals=raw_core,
                minimal_core_literals=minimal_core,
                raw_core_descriptions=raw_descriptions,
                minimal_core_descriptions=minimal_descriptions,
                conflicting_categories=categories,
                summary_explanation="\n".join(explanation_lines),
                suggested_relaxations=suggestions,
                diagnosis_time_sec=round(diag_time, 4)
            )

        finally:
            solver.delete()
