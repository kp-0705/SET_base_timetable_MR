# SAT-Based Automated Timetable Generation and Optimization for Master's Curriculum

**Course:** M.Tech Machine Reasoning  
**Academic Year:** 2026–2027  
**Author:** M.Tech Candidate, Machine Reasoning Specialization  

---

## Abstract

Constructing an academic timetable for university Master's curricula is an NP-complete combinatorial scheduling problem subject to tight multi-dimensional constraints spanning courses, instructors, student cohorts, lecture halls, and specialized laboratories. While traditional approaches rely on stochastic meta-heuristics (genetic algorithms, simulated annealing) or Integer Linear Programming (ILP), these methods either fail to provide mathematical guarantees of feasibility or scale poorly when proving unsatisfiability. This project develops a complete, mathematically rigorous system based on modern Boolean Satisfiability (SAT) and Maximum Satisfiability (MaxSAT) solving. All academic scheduling constraints are formalized in propositional logic and translated into Conjunctive Normal Form (CNF) using multiple cardinality encoding algorithms (Pairwise, Sinz's Sequential Counter, and Commander-variable encodings). We integrate PySAT state-of-the-art CDCL solvers (Glucose4, Minisat22, and CaDiCaL) for feasibility detection and the RC2 core-guided MaxSAT solver for soft preference optimization. Furthermore, to overcome the traditional "black-box" nature of SAT solving, we implement assumption-based UNSAT core extraction augmented with deletion-based Minimal Unsatisfiable Subset (MUS) minimization, providing grounded, human-readable explanations when over-constrained scenarios occur. Empirical evaluation across synthetic and realistic curricula demonstrates that the Sequential Sinz encoding achieves an 88% reduction in CNF clause footprint compared to pairwise encoding, solving realistic Master's timetables in under 20 milliseconds, scaling to 60 courses in 0.41 seconds, and outperforming an SMT/Z3 baseline by nearly two orders of magnitude.

---

## 1. Introduction & Motivation

University timetabling is an essential administrative task that directly affects teaching efficiency and student learning. At the Master's level (M.Tech/M.S.), curriculum timetabling poses unique combinatorial difficulties:
- Courses have diverse credit structures and weekly session requirements (e.g., 3 one-hour lectures vs. 2-hour contiguous lab sessions).
- Instructors have individualized availability windows and preferred teaching slots.
- Classrooms and laboratories vary significantly in seating capacity and specialized infrastructure.
- Student cohorts (e.g., M.Tech Computer Science, M.Tech Artificial Intelligence) attend common compulsory courses, requiring zero scheduling overlap.

Historically, academic institutions relied on manual compilation or greedy heuristic tools. Such approaches are:
1. **Error-prone and Fragile:** Small modifications often trigger cascading scheduling conflicts.
2. **Unable to Prove Infeasibility:** When no clash-free timetable exists, heuristic searches iterate indefinitely or terminate with high penalty scores without explaining *why* the instance is unsolvable.
3. **Hard to Optimize:** Balancing student idle gaps and faculty teaching load while satisfying hard constraints is difficult to calibrate with ad-hoc heuristics.

This project addresses these challenges through the formal lens of **Machine Reasoning**. By expressing timetabling requirements as propositional formulas in Conjunctive Normal Form (CNF), we leverage the power of Conflict-Driven Clause Learning (CDCL) SAT solvers to produce guaranteed conflict-free academic timetables, prove unsatisfiability, and optimize soft pedagogical preferences.

---

## 2. Problem Formulation & Universe of Discourse

The timetabling universe is formalized as a tuple $\mathcal{U} = \langle C, \mathcal{S}, \mathcal{T}, \mathcal{R}, \mathcal{F}, \mathcal{B} \rangle$:
- **Courses ($C$):** Each course $c$ is assigned an instructor $f(c) \in \mathcal{F}$, a student cohort $b(c) \in \mathcal{B}$, student enrollment $E(c)$, weekly sessions $k_c$, and session duration $d(c) \in \{1, 2\}$.
- **Session Tokens ($\mathcal{S}$):** To avoid non-linear propositional expressions, we decompose course $c$ into discrete weekly tokens $\mathcal{S}_c = \{s_{c, 1}, \dots, s_{c, k_c}\}$.
- **Time Slots ($\mathcal{T}$):** $\mathcal{T} = \mathcal{D} \times \mathcal{P}$, where $\mathcal{D}$ contains 5 working days (Monday–Friday) and $\mathcal{P} = \{1, 2, \dots, 6\}$ denotes daily periods.
- **Rooms ($\mathcal{R}$):** Lecture halls and computing laboratories with defined capacities $\text{Cap}(r)$ and room types $\text{Type}(r)$.
- **Faculty ($\mathcal{F}$):** Instructors with daily load ceilings $L_{\text{day}}(f)$, weekly limits $L_{\text{week}}(f)$, and availability sets $\mathcal{T}_{\text{avail}}(f)$.
- **Batches ($\mathcal{B}$):** Student cohorts with enrolled course subsets.

### 2.1 Decision Variable Formulation & Domain Pruning
The primary Boolean decision variable is defined as:
$$x_{s, t, r} \in \{0, 1\}$$
where $x_{s, t, r} = 1$ if and only if session token $s$ starts at slot $t \in \mathcal{T}$ in room $r \in \mathcal{R}$.

To prevent a combinatorial blowup in propositional variable allocation ($|\mathcal{S}| \times |\mathcal{T}| \times |\mathcal{R}|$), the system applies **Domain Pre-filtering**:
A variable $x_{s, t, r}$ is instantiated only if:
1. $\text{Type}(r) = \tau(s)$ (Room type compatibility).
2. $\text{Cap}(r) \ge E(s)$ (Room capacity sufficiency).
3. If $d(s) = 2$ starting at $(d, p)$, then $p + 1 \le P_{\max}$ (Double-period boundary check).
4. Room $r$ and faculty $f(s)$ are marked available across all periods occupied by session $s$.

---

## 3. Propositional CNF Cardinality Encodings

Cardinality constraints enforce that at most one, at least one, or exactly one variable in a set $X = \{u_1, \dots, u_n\}$ is assigned True.

### 3.1 Pairwise AMO Encoding
$$\text{AMO}_{\text{pair}}(X) \equiv \bigwedge_{1 \le i < j \le n} (\neg u_i \lor \neg u_j)$$
- **Clauses:** $\binom{n}{2} = O(n^2)$.
- **Auxiliary Variables:** $0$.
- **Behavior:** Simple, but produces large clause footprints on large candidate sets.

### 3.2 Sequential Counter AMO Encoding (Sinz, 2005)
Introduces $n-1$ auxiliary prefix variables $s_1, \dots, s_{n-1}$ representing the running accumulation of True literals:
1. $(\neg u_1 \lor s_1)$
2. $(\neg s_{n-1} \lor \neg u_n)$
3. Intermediate clauses for $2 \le i \le n-1$:
   - $(\neg u_i \lor s_i)$
   - $(\neg s_{i-1} \lor s_i)$
   - $(\neg u_i \lor \neg s_{i-1})$
- **Clauses:** $3n - 4 = O(n)$.
- **Auxiliary Variables:** $n - 1 = O(n)$.
- **Behavior:** Maintains arc consistency under Unit Propagation (UP).

### 3.3 Commander-Variable AMO Encoding (Klieber & Kwon, 2007)
Partitions $X$ into disjoint groups $G_1, \dots, G_m$ of size $k \approx 3$. Each group elects an auxiliary commander variable $c_g \iff \bigvee_{u \in G_g} u$. Mutual exclusion is enforced within each group and recursively across commander variables.
- **Clauses:** $O(n)$.
- **Auxiliary Variables:** $O(n/k)$.

---

## 4. Institutional Hard Constraints (Satisfiability)

1. **Session Assignment (Exactly-One):**
   $$\bigwedge_{s \in \mathcal{S}} \text{EO}\left(\{ x_{s, t, r} \mid (t, r) \in \text{Allowed}(s) \}\right)$$
2. **Room Mutual Exclusion:**
   $$\bigwedge_{r \in \mathcal{R}} \bigwedge_{t' \in \mathcal{T}} \text{AMO}\left(\{ x_{s, t, r} \mid s \in \mathcal{S}, \text{Occupies}(s, t', t) \}\right)$$
3. **Faculty Non-Clash:**
   $$\bigwedge_{f \in \mathcal{F}} \bigwedge_{t' \in \mathcal{T}} \text{AMO}\left(\{ x_{s, t, r} \mid s \in \mathcal{S}, f(s) = f, \text{Occupies}(s, t', t) \}\right)$$
4. **Student Batch Non-Clash:**
   $$\bigwedge_{b \in \mathcal{B}} \bigwedge_{t' \in \mathcal{T}} \text{AMO}\left(\{ x_{s, t, r} \mid s \in \mathcal{S}, b(s) = b, \text{Occupies}(s, t', t) \}\right)$$
5. **Course Daily Spreading:**
   $$\bigwedge_{c \in C, \text{lecture}} \bigwedge_{d \in \mathcal{D}} \text{AMO}\left(\{ x_{s, (d, p), r} \mid s \in \mathcal{S}_c, p \in \mathcal{P}, r \in \mathcal{R} \}\right)$$

---

## 5. Partial Weighted MaxSAT Soft Constraints

Pedagogical preferences are expressed as weighted soft clauses in a Weighted CNF (WCNF) formula:
- **Avoid Extreme Periods ($w = 2$):** Penalizes assigning core lectures to Period 1 (09:00 AM) or Period 6 (15:15 PM): $(\neg x_{s, t, r})$.
- **Faculty Preferred Slots ($w = 5$):** Penalizes assigning instructor $f$ outside their preferred time windows: $(\neg x_{s, t, r})$.
- **Minimize Student Idle Gaps ($w = 3$):** Penalizes assigning classes in periods $p$ and $p+2$ with period $p+1$ remaining idle: $(\neg x_p \lor \neg x_{p+2} \lor x_{p+1})$.

The PySAT **RC2** core-guided algorithm solves the WCNF formula, finding a timetable satisfying all hard constraints while minimizing cumulative penalty cost.

---

## 6. Infeasibility Diagnosis & UNSAT Core Extraction

When a scheduling problem is over-constrained, standard solvers return `UNSAT` without context. To provide explainability:
1. Each constraint group $g$ is guarded by an assumption selector literal $\alpha_g$: $(C \lor \neg \alpha_g)$.
2. The solver computes satisfiability under assumptions: $\text{solve}(\text{assumptions}=[\alpha_1, \alpha_2, \dots])$.
3. If UNSAT, the solver returns the raw assumption core $\mathcal{C}_{\text{raw}} = \text{get\_core}()$.
4. **Deletion-Based MUS Minimization:** For each $\alpha \in \mathcal{C}$, the system tests if $\mathcal{C} \setminus \{\alpha\}$ remains UNSAT. Redundant assumptions are pruned, leaving a Minimal Unsatisfiable Subset (MUS).
5. The MUS literals are translated into natural-language explanations (e.g., identifying specific room bottlenecks or instructor availability conflicts).

---

## 7. Decoupled Independent Timetable Verification

To maintain rigorous software quality and academic validity, the decoded schedule is subjected to an **Independent Auditor** (`TimetableValidator`). This module audits the decoded schedule against the original institutional parameters, asserting:
- Zero room double-bookings.
- Zero faculty overlapping assignments.
- Zero student cohort clashes.
- Adherence to room capacities and specialized lab types.
- Strict contiguity of double-period laboratory sessions.
- Strict adherence to faculty and room availability calendars.

---

## 8. Empirical Benchmarking & Experimental Results

All experiments were executed on an AMD64 Windows 11 platform running Python 3.13.5 and PySAT 1.9.

### Experiment 1: Cardinality Encoding Comparison
*Instance:* Master's Curriculum (8 courses, 18 weekly sessions, 6 rooms, 4 faculty, 30 slots).

| Metric | Pairwise AMO | Sequential Sinz AMO | Commander AMO |
| :--- | :---: | :---: | :---: |
| **Primary Variables** | 2,020 | 2,020 | 2,020 |
| **Auxiliary Variables** | **0** | 9,872 | 4,780 |
| **Total Variables** | 2,020 | 11,892 | 6,800 |
| **Total CNF Clauses** | 248,688 | **29,266** | 33,608 |
| **CNF Generation Time** | 0.0959 s | **0.0182 s** | 0.0175 s |
| **SAT Solving Time** | 0.0941 s (94.1 ms) | **0.0169 s (16.9 ms)** | 0.0209 s (20.9 ms) |
| **Independent Verification**| **Valid (True)** | **Valid (True)** | **Valid (True)** |

*Observation:* Sequential Sinz encoding reduces total clause count by **88.2%** compared to Pairwise encoding, achieving the lowest solve time (16.9 ms) through superior unit propagation.

### Experiment 2: SAT Solver Backend Comparison
*Instance:* Sequential Sinz encoding (11,892 variables, 29,266 clauses). Averaged over 3 runs.

| Solver Engine | Status | Mean Solve Time (ms) | Conflicts | Propagations | Decisions |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Minisat22** | SAT | **16.97 ms** | 62.0 | 24,968.0 | 1,238.0 |
| **Glucose4** | SAT | 18.20 ms | 62.0 | 20,548.0 | 1,102.0 |
| **CaDiCaL153** | SAT | 19.43 ms | N/A | N/A | N/A |

*Observation:* All three modern CDCL engines solve the university curriculum instance in under 20 milliseconds, confirming consistent performance across solvers.

### Experiment 3: Scalability Analysis (10 to 60 Courses)

| Courses Count | Total Sessions | Total Variables | Total Clauses | Solve Time (s) | Status |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **10** | 18 | 11,164 | 27,394 | 0.0101 s | UNSAT |
| **20** | 36 | 23,244 | 57,352 | 0.0385 s | SAT |
| **30** | 54 | 52,146 | 129,228 | 0.0951 s | SAT |
| **40** | 72 | 94,138 | 233,984 | 0.1808 s | SAT |
| **50** | 90 | 146,510 | 364,630 | 0.2444 s | SAT |
| **60** | 108 | 212,712 | 530,016 | **0.4147 s** | SAT |

*Observation:* Solving time scales near-linearly with problem size. An instance with 60 courses (108 weekly sessions and over 530,000 clauses) is solved in **0.4147 seconds**.

### Experiment 4: Pure SAT (PySAT) vs SMT (Z3) Baseline Comparison
On identical input instances:
- **PySAT (Glucose4, CNF Sinz):** **0.0185 seconds** (11,892 variables, 29,266 clauses).
- **Z3 SMT Solver:** **14.6842 seconds** (2,020 variables, 186,288 assertions).
- **Speedup:** Pure Propositional SAT CDCL solving is **~793x faster** than the SMT solver baseline.

### Experiment 5: MaxSAT Soft Preference Optimization
- Initial Feasible SAT Penalty Cost: **125**
- RC2 Optimal MaxSAT Penalty Cost: **72** (42.4% penalty reduction)
- Evaluated Soft Clauses: **53,012**
- Satisfied Soft Clauses: **52,997 (99.97% satisfaction rate)**
- Optimization Latency: **1.2001 seconds**
- Independent Verification: **100% Valid (0 Hard Violations)**

---

## 9. Conclusion & Academic Contributions

This project demonstrates the practical application of propositional satisfiability to Master's curriculum timetabling:
1. **Mathematical Soundness:** Formulates multi-period contiguous events, room compatibilities, and mutual exclusion using verified propositional logic.
2. **Cardinality Encoding Insights:** Proves that Sinz's Sequential Counter drastically outperforms naive pairwise encoding in both clause size and solver latency.
3. **Core-Guided Explainability:** Integrates assumption-based UNSAT cores and MUS deletion minimization to identify conflicting constraints when an instance is infeasible.
4. **Bi-Objective Optimization:** Demonstrates that partial weighted MaxSAT can improve schedule quality without compromising hard constraint compliance.
5. **Reproducibility:** Supported by an automated 43-test regression suite, decoupled independent verification, and a modern Streamlit demonstration interface.

---

## References

1. **Sinz, C. (2005).** *Towards an Optimal CNF Encoding of Boolean Cardinality Constraints.* In Principles and Practice of Constraint Programming (CP 2005), LNCS 3709, pp. 827–831.
2. **Klieber, W., & Kwon, G. (2007).** *Efficient CNF Encoding for Selecting at Most One from N.* In International Workshop on Constraints in Formal Verification.
3. **Audemard, G., & Simon, L. (2009).** *Predicting Learnt Clauses Quality in Modern SAT Solvers.* In Proceedings of the 21st International Joint Conference on Artificial Intelligence (IJCAI 2009), pp. 399–404.
4. **Biere, A., Heule, M., van Maaren, H., & Walsh, T. (Eds.). (2009).** *Handbook of Satisfiability.* IOS Press.
5. **Morgado, A., Heras, F., Liffiton, M., Jordi, J., & Marques-Silva, J. (2013).** *Iterative and Core-Guided MaxSAT Solving.* Journal on Satisfiability, Boolean Modeling and Computation (JSAT), 9, pp. 73–96.
6. **Ignatiev, A., Morgado, A., & Marques-Silva, J. (2018).** *PySAT: A Python Library for SAT and MaxSAT Solving.* In SAT 2018, LNCS 10929, pp. 428–437.
