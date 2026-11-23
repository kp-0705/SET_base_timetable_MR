# Mathematical and Propositional Logic Model for Automated Timetable Generation

**Course:** M.Tech Machine Reasoning  
**Subject:** Propositional Satisfiability (SAT) & Maximum Satisfiability (MaxSAT)

---

## 1. Domain Sets and Parameters

Let the scheduling universe be defined by the following finite sets:

1. **Courses ($C$):** $C = \{c_1, c_2, \dots, c_{|C|}\}$.
   - Each course $c \in C$ requires $k_c \in \mathbb{N}^+$ weekly sessions.
   - Each course $c$ is assigned an instructor $f(c) \in \mathcal{F}$, a student batch $b(c) \in \mathcal{B}$, an enrolled student count $E(c) \in \mathbb{N}^+$, a session duration $d(c) \in \{1, 2\}$, and a required room type $\tau(c) \in \{\text{lecture}, \text{lab}\}$.
   - We decompose course $c$ into discrete **session tokens**:
     $$\mathcal{S}_c = \{ s_{c, 1}, s_{c, 2}, \dots, s_{c, k_c} \}$$
     $$\mathcal{S} = \bigcup_{c \in C} \mathcal{S}_c$$

2. **Time Slots ($\mathcal{T}$):**
   - Let $\mathcal{D} = \{\text{Monday}, \text{Tuesday}, \text{Wednesday}, \text{Thursday}, \text{Friday}\}$ be the working days.
   - Let $\mathcal{P} = \{1, 2, \dots, P_{\max}\}$ be the daily academic periods (where $P_{\max} = 6$).
   - A time slot $t = (d, p) \in \mathcal{T} = \mathcal{D} \times \mathcal{P}$.

3. **Rooms ($\mathcal{R}$):**
   - Each room $r \in \mathcal{R}$ has capacity $\text{Cap}(r)$ and room type $\text{Type}(r) \in \{\text{lecture}, \text{lab}\}$.
   - An optional subset $\mathcal{T}_{\text{avail}}(r) \subseteq \mathcal{T}$ designates room availability.

4. **Faculty Members ($\mathcal{F}$):**
   - Each faculty $f \in \mathcal{F}$ has a maximum daily teaching load $L_{\text{day}}(f)$, a maximum weekly load $L_{\text{week}}(f)$, an availability set $\mathcal{T}_{\text{avail}}(f) \subseteq \mathcal{T}$, and a preferred slot set $\mathcal{T}_{\text{pref}}(f) \subseteq \mathcal{T}$.

5. **Student Batches ($\mathcal{B}$):**
   - Each batch $b \in \mathcal{B}$ represents a cohort of students taking a fixed curriculum of courses.

---

## 2. Boolean Decision Variables and Domain Pruning

### 2.1 Primary Decision Variables
For each session token $s \in \mathcal{S}$, slot $t \in \mathcal{T}$, and room $r \in \mathcal{R}$:
$$x_{s, t, r} \in \{0, 1\}$$
where $x_{s, t, r} = 1$ if and only if session $s$ is scheduled to **start** at time slot $t$ in room $r$.

### 2.2 Domain Pruning (Pre-Filtering)
To avoid generating redundant propositional variables, $x_{s, t, r}$ is instantiated only if the tuple $(s, t, r)$ satisfies the validity predicate $\text{Allowed}(s, t, r)$:
1. $\text{Type}(r) = \tau(s)$ (Room type compatibility).
2. $\text{Cap}(r) \ge E(s)$ (Capacity sufficiency).
3. If $t = (d, p)$ and $d(s) = 2$, then $p + 1 \le P_{\max}$ (Double-period boundary check).
4. For all periods $p' \in [p, p + d(s) - 1]$, $(d, p') \in \mathcal{T}_{\text{avail}}(r)$.
5. For all periods $p' \in [p, p + d(s) - 1]$, $(d, p') \in \mathcal{T}_{\text{avail}}(f(s))$.

### 2.3 Slot Occupation Relation
A session $s$ starting at slot $t = (d, p)$ occupies slot $t' = (d', p')$ if and only if:
$$\text{Occupies}(s, t', t) \iff (d' = d) \land (p \le p' < p + d(s))$$

---

## 3. Cardinality Encodings in Propositional Logic

A key challenge in SAT modeling is expressing cardinality constraints over a set of Boolean literals $X = \{u_1, u_2, \dots, u_n\}$.

### 3.1 At-Least-One (ALO): $\sum_{i=1}^n u_i \ge 1$
Represented as a single positive clause:
$$\text{ALO}(X) \equiv \bigvee_{i=1}^n u_i$$

### 3.2 Pairwise At-Most-One (AMO): $\sum_{i=1}^n u_i \le 1$
Enforces mutual exclusion for all pairs:
$$\text{AMO}_{\text{pair}}(X) \equiv \bigwedge_{1 \le i < j \le n} (\neg u_i \lor \neg u_j)$$
- **Clauses:** $\binom{n}{2} = \frac{n(n-1)}{2} = O(n^2)$.
- **Auxiliary Variables:** $0$.

### 3.3 Sequential Counter AMO (Sinz, 2005)
Introduces $n-1$ prefix sum auxiliary variables $s_1, s_2, \dots, s_{n-1}$:
1. $(\neg u_1 \lor s_1)$
2. $(\neg s_{n-1} \lor \neg u_n)$
3. For each $i \in \{2, \dots, n-1\}$:
   - $(\neg u_i \lor s_i)$
   - $(\neg s_{i-1} \lor s_i)$
   - $(\neg u_i \lor \neg s_{i-1})$
- **Clauses:** $3n - 4 = O(n)$.
- **Auxiliary Variables:** $n - 1 = O(n)$.
- **Unit Propagation:** Guarantees arc consistency (setting any $u_i = 1$ immediately propagates $\neg u_j$ for all $j \neq i$).

### 3.4 Commander-Variable AMO (Klieber & Kwon, 2007)
Partitions $X$ into subsets $G_1, \dots, G_m$ of size $k \approx 3$. Each group introduces a commander literal $c_g \iff \bigvee_{u \in G_g} u$:
1. Intra-group pairwise: $\text{AMO}_{\text{pair}}(G_g)$ for each group.
2. Implication to commander: $(\neg u \lor c_g)$ for all $u \in G_g$.
3. Commander expansion: $(\neg c_g \lor \bigvee_{u \in G_g} u)$.
4. Inter-group mutual exclusion: recursively enforce $\text{AMO}(\{c_1, \dots, c_m\})$.
- **Clauses:** $O(n)$.
- **Auxiliary Variables:** $O(n/k)$.

### 3.5 Exactly-One (EO): $\sum_{i=1}^n u_i = 1$
$$\text{EO}(X) \equiv \text{ALO}(X) \land \text{AMO}(X)$$

---

## 4. Hard Constraints Formulation (DIMACS CNF)

### Hard Constraint 1: Mandatory Session Assignment
Every session $s \in \mathcal{S}$ must start in exactly one valid time slot and room:
$$\bigwedge_{s \in \mathcal{S}} \text{EO}\left(\{ x_{s, t, r} \mid (t, r) \in \text{Allowed}(s) \}\right)$$

### Hard Constraint 2: Room Non-Overlap
For every room $r \in \mathcal{R}$ and slot $t' \in \mathcal{T}$, at most one occupying session can be scheduled:
$$\bigwedge_{r \in \mathcal{R}} \bigwedge_{t' \in \mathcal{T}} \text{AMO}\left(\{ x_{s, t, r} \mid s \in \mathcal{S}, \text{Occupies}(s, t', t) \}\right)$$

### Hard Constraint 3: Faculty Non-Clash
No faculty member $f \in \mathcal{F}$ may teach two sessions simultaneously at any slot $t'$:
$$\bigwedge_{f \in \mathcal{F}} \bigwedge_{t' \in \mathcal{T}} \text{AMO}\left(\{ x_{s, t, r} \mid s \in \mathcal{S}, f(s) = f, \text{Occupies}(s, t', t) \}\right)$$

### Hard Constraint 4: Student Batch Non-Clash
No student batch $b \in \mathcal{B}$ may attend two sessions simultaneously at any slot $t'$:
$$\bigwedge_{b \in \mathcal{B}} \bigwedge_{t' \in \mathcal{T}} \text{AMO}\left(\{ x_{s, t, r} \mid s \in \mathcal{S}, b(s) = b, \text{Occupies}(s, t', t) \}\right)$$

### Hard Constraint 5: Course Daily Spreading
For lecture courses with $k_c > 1$ and $d=1$, at most one session may be scheduled per day:
$$\bigwedge_{c \in C, \tau(c)=\text{lecture}} \bigwedge_{d \in \mathcal{D}} \text{AMO}\left(\{ x_{s, (d, p), r} \mid s \in \mathcal{S}_c, p \in \mathcal{P}, r \in \mathcal{R} \}\right)$$

---

## 5. MaxSAT Soft Constraints Formulation (WCNF)

In Partial Weighted MaxSAT, hard clauses carry infinite weight ($\infty$), while soft clauses are associated with positive penalty weights $w \in \mathbb{N}^+$.

### Soft Constraint A: Avoid Extreme Periods (Weight $w = 2$)
Penalize scheduling sessions in Period 1 (09:00 AM) or Period 6 (15:15 PM):
$$\forall (s, (d, p), r) \text{ with } p \in \{1, 6\}: \quad (\neg x_{s, (d, p), r}), \quad \text{weight } = 2$$

### Soft Constraint B: Faculty Preferred Slots (Weight $w = 5$)
If faculty member $f$ specifies preferred slots $\mathcal{T}_{\text{pref}}(f)$, penalize scheduling outside this set:
$$\forall (s, t, r) \text{ with } f(s) = f \text{ and } t \notin \mathcal{T}_{\text{pref}}(f): \quad (\neg x_{s, t, r}), \quad \text{weight } = 5$$

### Soft Constraint C: Minimize Student Idle Gaps (Weight $w = 3$)
If student batch $b$ attends classes in period $p$ and period $p+2$ on day $d$, penalize having period $p+1$ empty:
Let $Y_{b, d, p} = \bigvee x_{s, (d, p), r}$ denote batch $b$ having class at $(d, p)$.
The preference clause enforces:
$$(\neg x_{s_1, (d, p), r_1} \lor \neg x_{s_2, (d, p+2), r_2} \lor Y_{b, d, p+1}), \quad \text{weight } = 3$$

---

## 6. Assumption-Based UNSAT Core Extraction & MUS Minimization

To explain why a scheduling instance is unsatisfiable, each constraint group $g$ is instrumented with an assumption selector literal $\alpha_g$:
$$(C_j \lor \neg \alpha_g)$$
Solving under the assumption vector $\mathcal{A} = [\alpha_1, \alpha_2, \dots]$ produces:
1. An initial **UNSAT Core** $\mathcal{C}_{\text{raw}} \subseteq \mathcal{A}$.
2. **Deletion-Based MUS Minimization:**
   ```
   For each alpha in C:
       If Solve(C \ {alpha}) == UNSAT:
           C = C \ {alpha}  # Redundant constraint removed
   Return C  # Minimal Unsatisfiable Subset (MUS)
   ```
The resulting MUS literals are mapped back to human-readable domain entities (e.g., room capacities, availability windows) for natural-language diagnostic explanation.
