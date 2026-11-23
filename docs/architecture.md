# System Architecture & Technical Specifications

**Project Title:** SAT-Based Automated Timetable Generation and Optimization  
**Architecture Style:** Decoupled Modular Reasoning Pipeline with Streamlit Presentation

---

## 1. High-Level Architecture Overview

The system strictly decouples knowledge modeling and propositional encoding from solving mechanics and user-interface presentation:

```
[ Input Layer ]           CSV / JSON Specifications (Courses, Faculty, Rooms, Batches, Slots)
                                 │
                                 ▼
[ Ingestion & Validation ] Pydantic Schemas & Domain Pruner (core/data_validator.py)
                                 │
                                 ▼
[ Propositional Encoding ] VariableManager + Cardinality Engine (core/constraint_encoder.py)
                                 │
                                 ├───────────────────────────────────┐
                                 ▼                                   ▼
[ Reasoning Engines ]     PySAT CDCL Solver (Glucose4/Minisat)   PySAT RC2 MaxSAT Optimizer
                                 │                                   │
                                 ▼                                   ▼
[ Output Processing ]     Timetable Decoder (Positive Literals)  Decoupled Auditor (Validator)
                                 │                                   │
                                 ▼                                   ▼
[ Presentation Layer ]    Streamlit Web Dashboard + Plotly Analytics (app.py)
```

---

## 2. Component Directory Layout & Responsibilities

```
sat_timetable_project/
├── app.py                      # Streamlit application UI entry point
├── config.py                   # Global configuration, weights, and paths
├── requirements.txt            # Dependency specifications
├── README.md                   # Quick start and project manual
│
├── core/                       # Core reasoning and logic engine
│   ├── models.py               # Pydantic domain schemas (Course, Room, Faculty, Slot, etc.)
│   ├── data_loader.py          # CSV/JSON parsers and template exporters
│   ├── data_validator.py       # Domain pre-filtering and consistency checker
│   ├── variable_manager.py     # Bijective mapping: (Domain Tuple) <-> SAT Integer Literal
│   ├── cardinality.py          # Pairwise, Sequential Sinz, Commander implementations
│   ├── constraint_encoder.py   # Propositional CNF generator for all hard constraints
│   ├── sat_solver.py           # PySAT solver abstraction (Glucose4, Minisat22, Cadical153)
│   ├── maxsat_solver.py        # Partial Weighted MaxSAT optimizer (RC2 algorithm)
│   ├── unsat_explainer.py      # Assumption core extractor and MUS deletion minimizer
│   ├── timetable_decoder.py    # Translates SAT model literals to TimetableEntry records
│   ├── timetable_validator.py  # Decoupled independent verification auditor
│   └── smt_baseline.py         # Optional Z3 comparative implementation
│
├── visualization/              # Data visualization utilities
│   ├── timetable_view.py       # Interactive grid formatter (Batch/Faculty/Room/All)
│   └── analytics.py            # Plotly analytics charts (comparison, scalability, loads)
│
├── experiments/                # Empirical evaluation scripts
│   ├── run_encoding_comparison.py  # Pairwise vs Sequential vs Commander benchmark
│   ├── run_solver_comparison.py    # Glucose4 vs Minisat22 vs Cadical153 benchmark
│   ├── run_scalability.py          # Scaling test across 10 to 60+ courses
│   └── results/                    # Recorded CSV benchmark data files
│
├── tests/                      # Automated test suite (43 Pytest cases)
│   ├── test_cardinality.py     # Truth-table correctness of ALO, AMO, Exactly-One
│   ├── test_sat_solver.py      # SAT feasibility and independent audit
│   ├── test_unsat_core.py      # UNSAT detection and core extraction
│   ├── test_maxsat.py          # Soft preference optimization and hard safety
│   └── test_validator.py       # Tamper tests verifying validator catches corruptions
│
└── docs/                       # Academic documentation suite
    ├── mathematical_model.md   # Mathematical equations and proofs
    ├── architecture.md         # Component specifications and data flow
    ├── project_report.md       # Full academic paper-style report
    └── viva_questions.md       # Comprehensive viva preparation guide
```

---

## 3. Data Flow and Execution Pipeline

1. **Step 1: Ingestion & Domain Pruning:**  
   The user selects a preset scenario or uploads custom CSV/JSON files. `data_validator.py` applies domain checks, discarding invalid `(session, slot, room)` combinations before variable allocation.

2. **Step 2: Bijective Variable Allocation:**  
   `VariableManager` assigns unique integer IDs to valid `x[s, t, r]` tuples and tracks auxiliary variables allocated during cardinality encoding.

3. **Step 3: Propositional CNF Generation:**  
   `ConstraintEncoder` generates clauses for the hard constraints:
   - Session allocation (Exactly-One)
   - Room non-overlap (At-Most-One)
   - Faculty non-clash (At-Most-One)
   - Batch non-clash (At-Most-One)
   - Course daily spreading (At-Most-One)

4. **Step 4: Solving & Feasibility:**  
   `SATSolverService` calls PySAT (Glucose4 / Minisat22 / CaDiCaL):
   - **If SAT:** Positive literals are decoded by `timetable_decoder.py`.
   - **If UNSAT:** `unsat_explainer.py` extracts the minimal conflicting assumption core (MUS) and generates actionable recommendations.

5. **Step 5: Decoupled Independent Validation:**  
   `TimetableValidator` independently audits the decoded schedule without trusting the solver. It asserts zero room, faculty, or batch double-bookings, capacity compliance, and proper contiguous double-period lab scheduling.

6. **Step 6: Soft Preference Optimization (MaxSAT):**  
   If enabled, `MaxSATOptimizer` builds a Weighted CNF (WCNF) formula and runs RC2 to minimize student idle windows, avoid extreme periods, and honor faculty preferences.
