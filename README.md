# SAT-Based Automated Timetable Generation and Optimization

**Academic Project for M.Tech Machine Reasoning**  
**Core Technologies:** Python 3.11+, PySAT (`python-sat`), Glucose4, CaDiCaL, Minisat, RC2 MaxSAT, Streamlit, Plotly, Pytest.

---

## 1. Project Overview

University timetabling is an NP-complete combinatorial scheduling problem. This project implements an automated, mathematically rigorous timetabling system using **Boolean Satisfiability (SAT)** and **Partial Weighted Maximum Satisfiability (MaxSAT)**.

All scheduling constraints—including faculty allocations, room capacities, specialized laboratories, double-period contiguous lab sessions, student cohort non-overlap, and daily lecture spreading—are formulated in propositional logic and translated into Conjunctive Normal Form (CNF).

When instances are over-constrained, the system extracts **UNSAT Cores** and applies **deletion-based Minimal Unsatisfiable Subset (MUS) minimization** to provide clear, human-readable explanations of why the problem is infeasible.

---

## 2. Key Features

- **Multiple Cardinality Encodings:**
  - **Pairwise Encoding:** $O(N^2)$ clauses, 0 auxiliary variables.
  - **Sequential Counter Encoding (Sinz, 2005):** $O(N)$ clauses, $O(N)$ auxiliary variables, preserving arc consistency under unit propagation.
  - **Commander Encoding (Klieber & Kwon, 2007):** $O(N)$ clauses, $O(N/k)$ auxiliary variables.
- **Modern CDCL SAT Solving:** Direct C-extension bindings via PySAT to `Glucose4`, `Minisat22`, and `CaDiCaL153`.
- **Soft Constraint Optimization (MaxSAT):** Core-guided **RC2** MaxSAT solver balancing student idle gaps, avoiding extreme early/late periods, and honoring faculty preferences.
- **Explainable Infeasibility (UNSAT Core & MUS):** Assumption-based selector literals identify conflicting constraint groups, mapping them to actionable recommendations.
- **Decoupled Independent Verification:** An auditor module (`TimetableValidator`) independently verifies every generated schedule against ground-truth institutional rules.
- **Interactive Web Interface:** Streamlit dashboard with dynamic weekly timetable grids (filterable by Student Batch, Faculty, Room, or Full University), analytics charts, and CSV export.
- **Automated Regression Suite:** 43 tests passing in under 3 seconds via `pytest`.

---

## 3. Directory Layout

```
sat_timetable_project/
├── app.py                      # Interactive Streamlit application
├── config.py                   # System configuration and default weights
├── requirements.txt            # Project dependencies
├── README.md                   # This documentation guide
│
├── core/                       # Core reasoning algorithms
│   ├── models.py               # Pydantic data schemas
│   ├── data_loader.py          # CSV/JSON ingestion and template generators
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
├── visualization/              # UI presentation and analytics
│   ├── timetable_view.py       # Grid formatters (Batch/Faculty/Room/All)
│   └── analytics.py            # Plotly analytics charts
│
├── experiments/                # Empirical evaluation scripts
│   ├── run_encoding_comparison.py  # Pairwise vs Sequential vs Commander
│   ├── run_solver_comparison.py    # Glucose4 vs Minisat22 vs Cadical153
│   ├── run_scalability.py          # Scalability benchmark (10 to 60+ courses)
│   └── results/                    # Recorded CSV result files
│
├── tests/                      # Automated test suite (43 Pytest cases)
│   ├── test_cardinality.py     # Truth-table correctness of ALO, AMO, Exactly-One
│   ├── test_sat_solver.py      # SAT feasibility and independent audit
│   ├── test_unsat_core.py      # UNSAT detection and core extraction
│   ├── test_maxsat.py          # Soft preference optimization and hard safety
│   └── test_validator.py       # Tamper tests verifying validator catches corruptions
│
└── docs/                       # Academic documentation
    ├── mathematical_model.md   # Mathematical formulations and proofs
    ├── architecture.md         # Component specifications and data flow
    ├── project_report.md       # Full academic paper-style report
    └── viva_questions.md       # Comprehensive viva preparation guide
```

---

## 4. Installation & Setup

### Prerequisites
- Python 3.11 or Python 3.12/3.13 (64-bit).
- Compatible with Windows 11, Ubuntu/Linux, and macOS.

### Quick Start
```bash
# 1. Clone repository and navigate to root directory
cd NEW_MR_project

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## 5. Running the Application

Launch the interactive Streamlit dashboard:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

### Application Features:
1. **Dashboard:** Select preset scenarios (Feasible Master's Curriculum vs. Infeasible Bottleneck) and click:
   - **Generate Timetable (SAT Feasibility):** Computes a conflict-free schedule in ~0.02s.
   - **Optimize Timetable (RC2 MaxSAT):** Minimizes student idle gaps and honors faculty preferences.
   - **Diagnose Infeasibility (UNSAT Core):** Pinpoints conflicting constraints if over-constrained.
2. **Timetable Grid:** View weekly schedules filterable by **Student Batch**, **Faculty Member**, or **Room / Laboratory**, and export to CSV.
3. **Infeasibility (UNSAT Core):** Inspect extracted minimal unsatisfiable subsets and recommendations.
4. **Analytics & Benchmarks:** Interactive Plotly charts comparing cardinality encodings, solver latencies, and scalability curves.
5. **Machine Reasoning Theory:** Formulations, equations, and algorithms explained.

---

## 6. Running Automated Tests & Experiments

### Run Complete Test Suite
```bash
pytest -v
```
*Executes all 43 unit and integration tests across cardinality encodings, solvers, MaxSAT, UNSAT cores, and independent verification.*

### Run Empirical Benchmarks
```bash
# Experiment 1: Cardinality Encoding Comparison
python experiments/run_encoding_comparison.py

# Experiment 2: Solver Backend Comparison (Glucose4 vs Minisat vs CaDiCaL)
python experiments/run_solver_comparison.py

# Experiment 3: Scalability Benchmark (10 to 60+ courses)
python experiments/run_scalability.py
```
Results are saved to `experiments/results/*.csv`.

---

## 7. Key Empirical Findings

1. **Clause Footprint:** The Sequential Sinz encoding achieved an **88.2% reduction in clauses** compared to pairwise encoding (29,266 vs 248,688 clauses on the Master's instance), accelerating solve times from 94.1 ms down to 16.9 ms.
2. **Scalability:** Solving times scale near-linearly. An instance with 60 courses and 108 weekly sessions (over 530,000 clauses) solved in **0.41 seconds**.
3. **SAT vs. SMT:** Pure CDCL SAT solving via PySAT was **~793x faster** than an equivalent Z3 SMT formulation (0.018s vs 14.68s) on identical inputs.
4. **MaxSAT Optimization:** RC2 reduced soft preference penalty cost from 125 to 72 (a 42.4% penalty reduction) with a 99.97% soft clause satisfaction rate, while maintaining 100% hard constraint compliance.

---

## 8. Academic References

- **Sinz, C. (2005).** *Towards an Optimal CNF Encoding of Boolean Cardinality Constraints.* CP 2005.
- **Klieber, W., & Kwon, G. (2007).** *Efficient CNF Encoding for Selecting at Most One from N.*
- **Audemard, G., & Simon, L. (2009).** *Predicting Learnt Clauses Quality in Modern SAT Solvers (Glucose).* IJCAI 2009.
- **Morgado, A. et al. (2013).** *Iterative and Core-Guided MaxSAT Solving (RC2).* JSAT 2013.
- **Ignatiev, A. et al. (2018).** *PySAT: A Python Library for SAT and MaxSAT Solving.* SAT 2018.
