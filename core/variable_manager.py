"""Bijective mapping between domain entities and DIMACS SAT integer variables."""

from typing import Dict, Tuple, Any, Optional


class VariableManager:
    """
    Manages integer literal allocation for DIMACS CNF formulas.
    Guarantees a strict 1-to-1 bijection: (tuple_key) <--> integer_id > 0.
    """

    def __init__(self, start_id: int = 1):
        self._next_id: int = start_id
        self._name_to_id: Dict[Tuple[Any, ...], int] = {}
        self._id_to_name: Dict[int, Tuple[Any, ...]] = {}
        self._aux_count: int = 0
        self._assumption_vars: Dict[int, str] = {}

    def get_var(self, *key_parts: Any) -> int:
        """
        Retrieves or allocates an integer ID for the given key tuple.
        Example: get_var('x', session_id, slot_id, room_id)
        """
        key = tuple(key_parts)
        if key not in self._name_to_id:
            vid = self._next_id
            self._next_id += 1
            self._name_to_id[key] = vid
            self._id_to_name[vid] = key
            if str(key[0]).startswith("aux"):
                self._aux_count += 1
        return self._name_to_id[key]

    def allocate_aux_var(self, prefix: str = "aux", *tag: Any) -> int:
        """Allocates a fresh auxiliary variable guaranteed to be unique."""
        key = (f"aux_{prefix}", self._aux_count, *tag)
        return self.get_var(*key)

    def allocate_assumption_var(self, group_name: str, *details: Any) -> int:
        r"""
        Allocates an assumption selector literal for UNSAT core tracking.
        Clauses guarded by this assumption literal take the form: (C \lor \neg alpha).
        """
        key = ("assume", group_name, *details)
        var_id = self.get_var(*key)
        self._assumption_vars[var_id] = f"{group_name}: {' '.join(str(d) for d in details)}"
        return var_id

    def get_assumption_description(self, var_id: int) -> Optional[str]:
        """Returns human-readable text for an assumption literal."""
        return self._assumption_vars.get(abs(var_id))

    def get_key(self, var_id: int) -> Optional[Tuple[Any, ...]]:
        """Returns the semantic tuple key associated with an integer variable ID."""
        return self._id_to_name.get(abs(var_id))

    def has_var(self, *key_parts: Any) -> bool:
        """Checks if a key has already been registered."""
        return tuple(key_parts) in self._name_to_id

    @property
    def total_variables(self) -> int:
        """Total number of Boolean variables allocated."""
        return self._next_id - 1

    @property
    def aux_variables_count(self) -> int:
        """Total count of auxiliary variables generated."""
        return self._aux_count

    @property
    def assumption_variables(self) -> Dict[int, str]:
        """Dictionary of assumption variable IDs to their descriptions."""
        return self._assumption_vars.copy()
