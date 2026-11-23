"""Global configuration parameters for the SAT-based timetabling system."""

from pathlib import Path
from typing import Dict, List

# Base Directory Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SAMPLE_DATA_DIR = DATA_DIR / "sample_data"
TEMPLATES_DIR = DATA_DIR / "templates"
EXPERIMENTS_DIR = BASE_DIR / "experiments"
RESULTS_DIR = EXPERIMENTS_DIR / "results"
DOCS_DIR = BASE_DIR / "docs"

# Ensure directories exist
for directory in [DATA_DIR, SAMPLE_DATA_DIR, TEMPLATES_DIR, EXPERIMENTS_DIR, RESULTS_DIR, DOCS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Standard Academic Week Configuration
WORKING_DAYS: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS_PER_DAY: int = 6

# Time slot labels (Period number -> Time label)
PERIOD_LABELS: Dict[int, str] = {
    1: "09:00 - 10:00",
    2: "10:00 - 11:00",
    3: "11:15 - 12:15",
    4: "12:15 - 13:15",
    5: "14:15 - 15:15",
    6: "15:15 - 16:15",
}

# Solver Options
SUPPORTED_SAT_SOLVERS = ["glucose4", "cadical153", "minisat22"]
DEFAULT_SAT_SOLVER = "glucose4"

# Cardinality Encoding Options
CARDINALITY_ENCODINGS = ["sequential", "pairwise", "commander"]
DEFAULT_CARDINALITY_ENCODING = "sequential"

# Soft Constraint Weights (for RC2 MaxSAT Optimization)
DEFAULT_SOFT_WEIGHTS = {
    "minimize_student_idle_gaps": 3,
    "avoid_extreme_periods": 2,       # Period 1 (early) and Period 6 (late)
    "faculty_preferred_slots": 5,     # Honor faculty preferred times
    "balance_faculty_daily_load": 4,  # Penalize > 3 lectures per day per faculty
}

# Room Types
ROOM_TYPE_LECTURE = "lecture"
ROOM_TYPE_LAB = "lab"
VALID_ROOM_TYPES = [ROOM_TYPE_LECTURE, ROOM_TYPE_LAB]

# Course Types
COURSE_TYPE_LECTURE = "lecture"
COURSE_TYPE_LAB = "lab"
VALID_COURSE_TYPES = [COURSE_TYPE_LECTURE, COURSE_TYPE_LAB]
