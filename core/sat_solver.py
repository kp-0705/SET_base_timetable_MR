"""SAT Solver interface using PySAT backends (Glucose4, CaDiCaL, Minisat)."""

import time
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from pysat.solvers import Glucose4, Minisat22

# Dynamically import Cadical if supported on current platform
try:
    from pysat.solvers import Cadical153
    CADICAL_AVAILABLE = True
except (ImportError, Exception):
    CADICAL_AVAILABLE = False


@dataclass
class SolverResult:
    status: str  # "SAT" or "UNSAT"
    model: Optional[List[int]] = None
    core: Optional[List[int]] = None
    solving_time_sec: float = 0.0
    solver_name: str = ""
    conflicts: int = 0
    propagations: int = 0
    decisions: int = 0


def create_pysat_solver(solver_name: str = "glucose4", clauses: Optional[List[List[int]]] = None):
    """Factory creating the appropriate PySAT solver instance."""
    s_name = solver_name.lower().strip()
    bootstrap = clauses if clauses is not None else []

    if s_name == "cadical153" and CADICAL_AVAILABLE:
        return Cadical153(bootstrap_with=bootstrap), "cadical153"
    elif s_name == "glucose4":
        return Glucose4(bootstrap_with=bootstrap), "glucose4"
    elif s_name == "minisat22":
        return Minisat22(bootstrap_with=bootstrap), "minisat22"
    else:
        # Fallback to Glucose4 or Minisat22
        return Glucose4(bootstrap_with=bootstrap), "glucose4"


class SATSolverService:
    """Orchestrates solving CNF formulas and collecting solver telemetry."""

    def __init__(self, solver_name: str = "glucose4"):
        self.solver_name = solver_name

    def solve(
        self,
        clauses: List[List[int]],
        assumptions: Optional[List[int]] = None
    ) -> SolverResult:
        """
        Solves CNF formula. If assumptions are provided, solves under assumptions
        and extracts the assumption core on UNSAT.
        """
        start_time = time.perf_counter()
        solver, actual_solver_name = create_pysat_solver(self.solver_name, clauses)

        try:
            is_sat = solver.solve(assumptions=assumptions) if assumptions else solver.solve()
            solve_time = time.perf_counter() - start_time

            # Collect available solver stats
            stats = getattr(solver, "accum_stats", lambda: {})()
            conflicts = stats.get("conflicts", 0) if isinstance(stats, dict) else 0
            propagations = stats.get("propagations", 0) if isinstance(stats, dict) else 0
            decisions = stats.get("decisions", 0) if isinstance(stats, dict) else 0

            if is_sat:
                model = solver.get_model()
                return SolverResult(
                    status="SAT",
                    model=model,
                    solving_time_sec=round(solve_time, 4),
                    solver_name=actual_solver_name,
                    conflicts=conflicts,
                    propagations=propagations,
                    decisions=decisions
                )
            else:
                core = solver.get_core() if assumptions else None
                return SolverResult(
                    status="UNSAT",
                    core=core,
                    solving_time_sec=round(solve_time, 4),
                    solver_name=actual_solver_name,
                    conflicts=conflicts,
                    propagations=propagations,
                    decisions=decisions
                )
        finally:
            solver.delete()
