# Viva Voce Preparation Guide: SAT-Based Automated Timetabling

**Course:** M.Tech Machine Reasoning  
**Topic:** Boolean Satisfiability (SAT), MaxSAT, Cardinality Encodings, and Explainable Infeasibility (UNSAT Cores)

---

## Section 1: Propositional Logic & CNF Encoding Fundamentals

### Q1: Why translate the timetabling problem into Conjunctive Normal Form (CNF)? Why not solve it directly as high-level constraints?
**Answer:**  
Conjunctive Normal Form (a conjunction of disjunctions $\bigwedge \bigvee l_i$) is the standard representation for modern CDCL (Conflict-Driven Clause Learning) SAT solvers. By compiling high-level requirements into CNF:
1. We separate the declarative domain modeling from the operational search engine.
2. We leverage decades of C++ algorithmic optimizations in CDCL solvers (two-watched literals, VSIDS decision heuristics, learned clause database management).
3. We obtain an exhaustive, complete solver: if a schedule exists, it is found; if no schedule exists, the solver returns a formal proof of unsatisfiability ($\text{UNSAT}$).

---

### Q2: What is the Tseitin Transformation, and when is it required?
**Answer:**  
The Tseitin transformation converts an arbitrary propositional formula into an equisatisfiable CNF formula in linear time and space $O(N)$ by introducing auxiliary variables for each internal logical gate/subformula.  
Without Tseitin, converting an arbitrary formula with nested conjunctions and disjunctions using the distributive law can cause an exponential explosion in clause count ($O(2^N)$).

---

### Q3: What is the primary Boolean decision variable in your timetabling formulation?
**Answer:**  
The decision variable is $x_{s, t, r} \in \{0, 1\}$, where:
$$x_{s, t, r} = 1 \iff \text{session token } s \text{ begins at time slot } t \text{ in room } r$$
By decomposing each multi-session course $c$ into discrete session tokens $\mathcal{S}_c = \{s_{c, 1}, s_{c, 2}, \dots, s_{c, k_c}\}$, every session token is subject to an **Exactly-One** constraint $\sum_{(t, r)} x_{s, t, r} = 1$. This eliminates non-linear multiplications and provides a clean 1-to-1 propositional mapping.

---

### Q4: How do you model double-period laboratory sessions without non-linear logic?
**Answer:**  
We treat decision variable $x_{s, (d, p), r}$ as the **starting slot** of lab session $s$.  
If $d(s) = 2$:
1. **Domain Pruning:** Variable $x_{s, (d, p), r}$ is instantiated only if $p + 1 \le P_{\max}$ and both periods $(d, p)$ and $(d, p+1)$ are available.
2. **Occupancy Projection:** A single variable $x_{s, (d, p), r}$ registers as occupying both $(d, p)$ and $(d, p+1)$. The mutual exclusion constraints for room, faculty, and batch index this variable under both periods, making overlapping bookings impossible.

---

## Section 2: Cardinality Encodings (AMO and Exactly-One)

### Q5: Compare Pairwise, Sequential Counter, and Commander encodings for At-Most-One ($\sum x_i \le 1$).
**Answer:**  

| Property | Pairwise Encoding | Sequential Sinz Counter | Commander Encoding |
| :--- | :---: | :---: | :---: |
| **Clause Complexity** | $\binom{n}{2} = O(n^2)$ | $3n - 4 = O(n)$ | $O(n)$ |
| **Auxiliary Variables** | $0$ | $n - 1 = O(n)$ | $O(n/k)$ |
| **Unit Propagation** | Direct pairwise mutex | Complete (Arc-consistent) | Complete |
| **Best Used For** | Small sets ($n \le 5$) | Large sets ($n > 10$) | Hierarchical groupings |

---

### Q6: What is "Arc Consistency under Unit Propagation", and why does Sinz's Sequential Counter achieve it?
**Answer:**  
An encoding is arc-consistent under unit propagation if, whenever a single variable is assigned True ($u_i = 1$), unit propagation alone (without solver branching or search) forces all other variables $u_j$ ($j \neq i$) in the mutual exclusion set to False.  
In Sinz's sequential counter, setting $u_i = 1$ forces the prefix accumulator variable $s_i = 1$. This cascades through clauses $(\neg s_{k-1} \lor s_k)$ to set $s_{i+1}, \dots, s_{n-1} = 1$, which immediately forces $\neg u_{i+1}, \dots, \neg u_n$ via $(\neg u_k \lor \neg s_{k-1})$. Simultaneously, backward clauses force $\neg u_1, \dots, \neg u_{i-1}$, eliminating the need for solver backtracking.

---

### Q7: Why did Pairwise encoding produce 248,688 clauses in your benchmark while Sequential encoding produced only 29,266 clauses?
**Answer:**  
In university timetabling, room, faculty, and batch mutual exclusion constraints group many candidate sessions across 30 time slots. For a conflict group with $N = 30$ candidates:
- Pairwise produces $\binom{30}{2} = 435$ clauses per group.
- Sequential Sinz produces $3(30) - 4 = 86$ clauses per group.
Across hundreds of room-slot and faculty-slot combinations, the quadratic growth of pairwise encoding inflates the clause count by an order of magnitude (an 88.2% reduction using Sequential encoding).

---

## Section 3: Modern CDCL SAT Solvers

### Q8: What are the core components of modern CDCL SAT solvers like Glucose and CaDiCaL?
**Answer:**  
1. **Two-Watched Literals (2WL):** Allows efficient unit propagation without examining every clause during variable assignment.
2. **VSIDS / CHB Decision Heuristics:** Variable State Independent Decaying Sum prioritizes variables frequently involved in recent conflicts.
3. **Conflict Analysis & 1-UIP Clause Learning:** Derives learned clauses by traversing the implication graph back to the First Unique Implication Point (1-UIP).
4. **Non-Chronological Backtracking (Backjumping):** Jumps back multiple decision levels directly to the second-highest decision level in the learned clause.
5. **LBD (Literal Block Distance):** Introduced by Glucose; measures the quality of learned clauses based on the number of distinct decision levels in the clause. Low-LBD clauses are protected from database reduction.

---

### Q9: Why did Glucose4 and Minisat22 perform almost identically in your benchmarks (~17–18 ms)?
**Answer:**  
For smaller instances (8 courses, 29k clauses), modern CDCL solvers resolve the formula within dozens of conflicts (62 conflicts in our test). Advanced learned clause management algorithms like LBD provide greater differentiation on industrial instances with millions of clauses and long search horizons.

---

## Section 4: Maximum Satisfiability (MaxSAT) & Optimization

### Q10: What is Partial Weighted MaxSAT, and how does it differ from standard SAT?
**Answer:**  
In standard SAT, all clauses are mandatory; the problem is purely decision-based ($\{ \text{SAT}, \text{UNSAT} \}$).  
In Partial Weighted MaxSAT:
- **Hard clauses ($C_{\text{hard}}$):** Must be satisfied (penalty for violation = $\infty$).
- **Soft clauses ($C_{\text{soft}}$):** May be violated, but each carries an associated penalty weight $w_i > 0$.  
The goal is to find an assignment satisfying all hard clauses while minimizing the sum of weights of violated soft clauses:
$$\min \sum_{C_i \in C_{\text{soft}}, \text{ violated}} w_i$$

---

### Q11: How does the RC2 MaxSAT algorithm work in PySAT?
**Answer:**  
RC2 is a **core-guided** MaxSAT solver. Rather than searching linearly through penalty costs, RC2:
1. Assumes all soft clauses are satisfied.
2. Invokes an underlying SAT solver. If SAT, the optimal solution is found.
3. If UNSAT, the solver returns an **UNSAT core** of soft clauses that cannot be simultaneously satisfied.
4. RC2 relaxes this core by introducing relaxation/blocking variables and kardinality constraints (Totalizer/OLL), incrementing the lower bound.
5. It repeats this process until the formula becomes satisfiable, guaranteeing optimal cost without exploring irrelevant regions of the search space.

---

## Section 5: UNSAT Cores, MUS, and Explainability

### Q12: What is an UNSAT Core? How does it differ from a Minimal Unsatisfiable Subset (MUS)?
**Answer:**  
- **UNSAT Core:** An unsatisfiable subset of clauses extracted from an infeasible formula. It is *not* guaranteed to be minimal and may contain irrelevant constraints.
- **Minimal Unsatisfiable Subset (MUS):** An unsatisfiable subset of clauses where every single clause is necessary for unsatisfiability. Removing even one clause from an MUS renders the remaining subset satisfiable.

---

### Q13: How did you implement assumption-based UNSAT core extraction?
**Answer:**  
We guard each constraint group $g$ with an assumption literal $\alpha_g$:
$$(C \lor \neg \alpha_g)$$
We pass the assumption literals vector $\mathcal{A} = [\alpha_1, \alpha_2, \dots]$ to the solver:
`solver.solve(assumptions=A)`.
When the formula is UNSAT, `solver.get_core()` returns a subset of assumption literals $\mathcal{C} \subseteq \mathcal{A}$ responsible for the conflict.

---

### Q14: Explain your Deletion-Based Core Minimization algorithm.
**Answer:**  
Given the raw core $\mathcal{C}$:
1. Iterate through each assumption literal $\alpha \in \mathcal{C}$.
2. Test whether $\mathcal{C} \setminus \{\alpha\}$ is still unsatisfiable by invoking `solver.solve(assumptions=C \ {alpha})`.
3. If it remains UNSAT, $\alpha$ is redundant and is permanently discarded: $\mathcal{C} \leftarrow \mathcal{C} \setminus \{\alpha\}$.
4. If it becomes SAT, $\alpha$ is essential and is retained.  
This polynomial-time procedure produces a guaranteed Minimal Unsatisfiable Subset (MUS) using at most $|\mathcal{C}|$ solver calls.

---

## Section 6: Comparative Paradigms (SAT vs SMT vs ILP vs CP)

### Q15: Why did PySAT solve the timetable in 0.018 seconds while Z3 SMT took 14.68 seconds on the exact same problem?
**Answer:**  
Z3 is an SMT (Satisfiability Modulo Theories) solver built to handle first-order theories (linear integer arithmetic, arrays, bit-vectors) alongside propositional logic.  
When presented with thousands of propositional cardinality constraints, Z3's general theory solvers, model checkers, and Python expression trees introduce significant overhead compared to a dedicated, cache-optimized C++ CDCL engine like Glucose4, which operates directly on primitive integer arrays.

---

### Q16: When would Integer Linear Programming (ILP) or Constraint Programming (CP) be preferred over SAT?
**Answer:**  
- **ILP (e.g., Gurobi, CPLEX):** Preferred when problems involve large numerical sums, continuous cost variables, or complex fractional bounds (e.g., budget allocations, network flows).
- **CP (e.g., OR-Tools, Choco):** Preferred when rich global constraints like `AllDifferent`, `Cumulative`, or `Circuit` can exploit specialized domain filtering algorithms without exploding into thousands of propositional clauses.
- **SAT/MaxSAT (PySAT):** Preferred when the problem is combinatorial and discrete, when proof of unsatisfiability is required, or when cardinality encodings can exploit CDCL clause learning.

---

## Section 7: Software Engineering & Validation

### Q17: Why did you implement an independent TimetableValidator? Why not simply trust the solver output?
**Answer:**  
A solver can only be as correct as the CNF formula it is given. If the CNF generator contains an off-by-one error or omits a constraint, the solver may return SAT with a schedule that violates institutional rules.  
Our `TimetableValidator` acts as a decoupled auditor that takes the decoded schedule and original institutional inputs, independently asserting zero room double-bookings, zero faculty clashes, capacity compliance, and proper double-period lab scheduling.

---

### Q18: What automated tests were implemented, and what do they verify?
**Answer:**  
We implemented a 43-test automated regression suite using `pytest`:
1. **Truth-Table Tests (31 cases):** Verifies ALO, AMO (Pairwise, Sequential, Commander), and Exactly-One across various $N$.
2. **SAT Feasibility Tests:** Verifies schedule generation and independent audit across all three cardinality encodings.
3. **UNSAT Core Tests:** Verifies infeasibility detection and non-empty core extraction on over-constrained instances.
4. **MaxSAT Tests:** Asserts that soft preference optimization reduces penalty costs while strictly preserving hard constraints.
5. **Tamper Tests:** Injects simulated room clashes, faculty double-bookings, capacity violations, and split lab sessions to ensure `TimetableValidator` catches corruptions.
