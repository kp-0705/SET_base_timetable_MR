"""Cardinality encoding algorithms: Pairwise, Sequential Counter (Sinz), and Commander."""

from typing import List
from core.variable_manager import VariableManager


def encode_at_least_one(lits: List[int]) -> List[List[int]]:
    r"""
    At-Least-One (ALO) constraint: sum(lits) >= 1.
    Translates to a single positive clause: (lits[0] \lor lits[1] \lor ...).
    """
    if not lits:
        return [[]]  # Empty clause is unsatisfiable
    return [[lit for lit in lits]]


def encode_at_most_one_pairwise(lits: List[int]) -> List[List[int]]:
    """
    Pairwise At-Most-One (AMO) constraint: sum(lits) <= 1.
    Generates N*(N-1)/2 binary mutual exclusion clauses.
    No auxiliary variables introduced.
    """
    n = len(lits)
    if n <= 1:
        return []
    clauses: List[List[int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            clauses.append([-lits[i], -lits[j]])
    return clauses


def encode_at_most_one_sequential(lits: List[int], var_mgr: VariableManager) -> List[List[int]]:
    """
    Sequential Counter At-Most-One (AMO) constraint by Carsten Sinz (2005).
    Introduces N - 1 auxiliary variables s_1, ..., s_{N-1}.
    Generates 3N - 4 clauses.
    Preserves full unit propagation (arc consistency).
    """
    n = len(lits)
    if n <= 1:
        return []
    if n == 2:
        return [[-lits[0], -lits[1]]]

    # Allocate N - 1 auxiliary variables
    s = [var_mgr.allocate_aux_var("seq_amo", idx) for idx in range(n - 1)]
    clauses: List[List[int]] = []

    # 1. (\neg x_0 \lor s_0)
    clauses.append([-lits[0], s[0]])

    # 2. (\neg s_{n-2} \lor \neg x_{n-1})
    clauses.append([-s[n - 2], -lits[n - 1]])

    # 3. Intermediate clauses for 1 <= i < n - 1:
    for i in range(1, n - 1):
        # (\neg x_i \lor s_i)
        clauses.append([-lits[i], s[i]])
        # (\neg s_{i-1} \lor s_i)
        clauses.append([-s[i - 1], s[i]])
        # (\neg x_i \lor \neg s_{i-1})
        clauses.append([-lits[i], -s[i - 1]])

    return clauses


def encode_at_most_one_commander(
    lits: List[int], 
    var_mgr: VariableManager, 
    group_size: int = 3
) -> List[List[int]]:
    """
    Commander-variable AMO encoding by Klieber & Kwon (2007).
    Partitions literals into disjoint groups of size <= group_size.
    Assigns a 'commander' auxiliary variable for each group and recurses.
    Produces O(N) clauses and O(N/k) auxiliary variables.
    """
    n = len(lits)
    if n <= 1:
        return []
    if n <= group_size:
        return encode_at_most_one_pairwise(lits)

    clauses: List[List[int]] = []
    commanders: List[int] = []

    # Partition into groups
    groups = [lits[i : i + group_size] for i in range(0, n, group_size)]

    for g_idx, group in enumerate(groups):
        if len(group) == 1:
            commanders.append(group[0])
            continue

        # Intra-group AMO
        clauses.extend(encode_at_most_one_pairwise(group))

        # Group commander variable: c = 1 iff at least one element in group is 1
        c = var_mgr.allocate_aux_var("cmd", g_idx)
        commanders.append(c)

        # For all x in group: x -> c  <=>  (\neg x \lor c)
        for x in group:
            clauses.append([-x, c])

        # c -> \lor_{x in group} x  <=>  (\neg c \lor x_1 \lor x_2 ...)
        or_clause = [-c] + group
        clauses.append(or_clause)

    # Recursively enforce AMO on the commander variables
    clauses.extend(encode_at_most_one_commander(commanders, var_mgr, group_size))
    return clauses


def encode_at_most_one(
    lits: List[int], 
    strategy: str = "sequential", 
    var_mgr: VariableManager = None
) -> List[List[int]]:
    """
    Dispatcher for At-Most-One encoding.
    Supported strategies: 'sequential', 'pairwise', 'commander'.
    """
    strat = strategy.lower().strip()
    if strat == "pairwise":
        return encode_at_most_one_pairwise(lits)
    elif strat == "commander":
        if var_mgr is None:
            raise ValueError("VariableManager is required for Commander encoding")
        return encode_at_most_one_commander(lits, var_mgr)
    elif strat == "sequential":
        if var_mgr is None:
            raise ValueError("VariableManager is required for Sequential encoding")
        return encode_at_most_one_sequential(lits, var_mgr)
    else:
        raise ValueError(f"Unknown cardinality encoding strategy: '{strategy}'")


def encode_exactly_one(
    lits: List[int], 
    strategy: str = "sequential", 
    var_mgr: VariableManager = None
) -> List[List[int]]:
    r"""
    Exactly-One (EO) constraint: sum(lits) == 1.
    Conjunctive combination of ALO and AMO: ALO(lits) \land AMO(lits).
    """
    clauses: List[List[int]] = []
    clauses.extend(encode_at_least_one(lits))
    clauses.extend(encode_at_most_one(lits, strategy=strategy, var_mgr=var_mgr))
    return clauses
