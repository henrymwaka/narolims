# lims_core/workflows/__init__.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


# ===============================================================
# Canonical workflow definitions
# ===============================================================

SAMPLE_STATES: Set[str] = {
    "REGISTERED",
    "IN_PROCESS",
    "QC_PENDING",
    "QC_PASSED",
    "QC_FAILED",
    "ARCHIVED",
}

SAMPLE_TRANSITIONS: Dict[str, Set[str]] = {
    "REGISTERED": {"IN_PROCESS"},
    "IN_PROCESS": {"QC_PENDING"},
    "QC_PENDING": {"QC_PASSED", "QC_FAILED"},
    "QC_PASSED": {"ARCHIVED"},
    "QC_FAILED": {"ARCHIVED"},
    "ARCHIVED": set(),
}

EXPERIMENT_STATES: Set[str] = {
    "PLANNED",
    "RUNNING",
    "COMPLETED",
    "CANCELLED",
}

EXPERIMENT_TRANSITIONS: Dict[str, Set[str]] = {
    "PLANNED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


# ===============================================================
# Role normalization and permission rules
# ===============================================================

ROLE_ALIASES: Dict[str, str] = {
    "ADMIN": "ADMIN",
    "SYSTEM_ADMIN": "ADMIN",
    "SUPERUSER": "ADMIN",
    "LAB_MANAGER": "LAB_MANAGER",
    "MANAGER": "LAB_MANAGER",
    "LAB_TECH": "LAB_TECH",
    "TECHNICIAN": "LAB_TECH",
    "QA": "QA",
    "QUALITY_ASSURANCE": "QA",
    "SCIENTIST": "SCIENTIST",
    "PI": "SCIENTIST",
    "READONLY": "READONLY",
    "VIEWER": "READONLY",
}


def normalize_state(value: str) -> str:
    return str(value or "").strip().upper()


def normalize_role(value: str) -> str:
    raw = str(value or "").strip().upper()
    return ROLE_ALIASES.get(raw, raw or "READONLY")


def _transitions_for_kind(kind: str) -> Dict[str, Set[str]]:
    k = normalize_state(kind)
    if k == "SAMPLE":
        return SAMPLE_TRANSITIONS
    if k == "EXPERIMENT":
        return EXPERIMENT_TRANSITIONS
    return {}


def _states_for_kind(kind: str) -> Set[str]:
    k = normalize_state(kind)
    if k == "SAMPLE":
        return SAMPLE_STATES
    if k == "EXPERIMENT":
        return EXPERIMENT_STATES
    return set()


def _role_allows(kind: str, current: str, target: str, role: str) -> bool:
    """
    Centralized role gating. Keep policy decisions here only.
    """
    k = normalize_state(kind)
    cur = normalize_state(current)
    tgt = normalize_state(target)
    r = normalize_role(role)

    if r == "ADMIN":
        return True

    if r == "READONLY":
        return False

    if r == "LAB_MANAGER":
        # Example restriction carried from your prior policy
        if k == "EXPERIMENT" and tgt == "CANCELLED":
            return False
        return True

    if r == "LAB_TECH":
        if k == "SAMPLE":
            if cur == "REGISTERED" and tgt == "IN_PROCESS":
                return True
            if cur == "IN_PROCESS" and tgt == "QC_PENDING":
                return True
            # From QC_PENDING, LAB_TECH should not be able to pass/fail QC
            return False

        if k == "EXPERIMENT":
            if cur == "PLANNED" and tgt == "RUNNING":
                return True
            if cur == "RUNNING" and tgt == "COMPLETED":
                return True
            return False

        return False

    if r == "QA":
        if k == "SAMPLE":
            if cur == "QC_PENDING" and tgt in {"QC_PASSED", "QC_FAILED"}:
                return True
            return False
        return False

    if r == "SCIENTIST":
        if k == "EXPERIMENT":
            if cur == "PLANNED" and tgt == "RUNNING":
                return True
            if cur == "RUNNING" and tgt == "COMPLETED":
                return True
            return False
        if k == "SAMPLE":
            return False
        return False

    return False


# ===============================================================
# Public workflow API
# ===============================================================

def validate_transition(
    kind: str,
    current: Optional[str] = None,
    target: Optional[str] = None,
    old: Optional[str] = None,
    new: Optional[str] = None,
) -> None:
    """
    Raises ValueError if the transition is invalid for the canonical workflow.

    Supports both parameter styles:
      validate_transition(kind, current, target)
      validate_transition(kind=..., old=..., new=...)
    """
    k = normalize_state(kind)

    cur = current if current is not None else old
    tgt = target if target is not None else new

    cur = normalize_state(cur or "")
    tgt = normalize_state(tgt or "")

    states = _states_for_kind(k)
    trans = _transitions_for_kind(k)

    if not states or not trans:
        raise ValueError(f"Unknown workflow kind: {kind}")

    if cur not in states:
        if k == "SAMPLE":
            raise ValueError(f"Unknown sample state: {cur}")
        raise ValueError(f"Unknown experiment state: {cur}")

    if tgt not in states:
        if k == "SAMPLE":
            raise ValueError(f"Unknown sample state: {tgt}")
        raise ValueError(f"Unknown experiment state: {tgt}")

    if tgt not in trans.get(cur, set()):
        if k == "SAMPLE":
            raise ValueError(f"Invalid sample transition: {cur} -> {tgt}")
        raise ValueError(f"Invalid experiment transition: {cur} -> {tgt}")


def validate_transition_with_role(
    kind: str,
    current: Optional[str] = None,
    target: Optional[str] = None,
    role: str = "READONLY",
    old: Optional[str] = None,
    new: Optional[str] = None,
) -> None:
    """
    Raises ValueError if the transition is invalid OR not permitted for the role.
    """
    validate_transition(kind=kind, current=current, target=target, old=old, new=new)

    cur = normalize_state((current if current is not None else old) or "")
    tgt = normalize_state((target if target is not None else new) or "")

    if not _role_allows(kind, cur, tgt, role):
        r = normalize_role(role)
        k = normalize_state(kind).lower()
        raise ValueError(f"Role {r} cannot perform {k} transition: {cur} -> {tgt}")


def allowed_next_states(kind: str, current: str) -> List[str]:
    """
    Canonical next states only, independent of role.
    """
    k = normalize_state(kind)
    cur = normalize_state(current)

    trans = _transitions_for_kind(k)
    if not trans:
        return []
    return sorted(trans.get(cur, set()))


def allowed_transitions(
    kind: str,
    current: Optional[str] = None,
    role: Optional[str] = None,
) -> Any:
    """
    Backwards compatible API.

    1) Old-style usage (introspection / UI):
         allowed_transitions("sample") -> Dict[str, List[str]]

    2) Role-aware usage (views_workflow_api expects this):
         allowed_transitions("sample", "QC_PENDING", "QA") -> List[str]
    """
    k = normalize_state(kind)

    # Mode 1: full map
    if current is None and role is None:
        trans = _transitions_for_kind(k)
        return {state: sorted(list(nxt)) for state, nxt in trans.items()}

    # Mode 2: role-aware list for a specific state
    cur = normalize_state(current or "")
    nxt = allowed_next_states(k, cur)
    if role is None:
        return nxt

    r = normalize_role(role)
    out: List[str] = []
    for tgt in nxt:
        if _role_allows(k, cur, tgt, r):
            out.append(tgt)
    return sorted(out)


def workflow_definition(kind: Optional[str] = None) -> Dict[str, Any]:
    """
    Stable JSON-serializable definition for UI.
    """
    def _one(k: str) -> Dict[str, Any]:
        kk = normalize_state(k)
        if kk == "SAMPLE":
            return {
                "kind": "sample",
                "states": sorted(SAMPLE_STATES),
                "transitions": allowed_transitions("sample"),
            }
        if kk == "EXPERIMENT":
            return {
                "kind": "experiment",
                "states": sorted(EXPERIMENT_STATES),
                "transitions": allowed_transitions("experiment"),
            }
        raise ValueError(f"Unsupported workflow kind: {k}")

    if kind is None:
        return {
            "sample": _one("sample"),
            "experiment": _one("experiment"),
        }
    return _one(kind)


def required_roles(kind: str, current: str, target: str) -> List[str]:
    """
    Returns roles that can perform current -> target for the canonical workflow.
    """
    validate_transition(kind=kind, current=current, target=target)

    candidates = ["LAB_TECH", "QA", "SCIENTIST", "LAB_MANAGER", "ADMIN"]
    allowed: List[str] = []
    for r in candidates:
        if _role_allows(kind, current, target, r):
            allowed.append(normalize_role(r))
    return allowed


__all__ = [
    "SAMPLE_STATES",
    "SAMPLE_TRANSITIONS",
    "EXPERIMENT_STATES",
    "EXPERIMENT_TRANSITIONS",
    "normalize_state",
    "normalize_role",
    "validate_transition",
    "validate_transition_with_role",
    "allowed_next_states",
    "allowed_transitions",
    "workflow_definition",
    "required_roles",
]
