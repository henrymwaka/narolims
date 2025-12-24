# lims_core/workflows.py
"""
Authoritative workflow engine for LIMS entities.

This module defines:
- Valid states
- Allowed transitions
- Role-based enforcement
- Introspection helpers for UI and API

Do not bypass these rules at model or view level.
"""

from __future__ import annotations
from typing import Dict, Set, List


# ===============================================================
# SAMPLE WORKFLOW
# ===============================================================

SAMPLE_STATUSES: Set[str] = {
    "REGISTERED",
    "IN_PROCESS",
    "QC_PENDING",
    "QC_PASSED",
    "QC_FAILED",
    "ARCHIVED",
}

SAMPLE_TRANSITIONS: Dict[str, Set[str]] = {
    "REGISTERED": {"IN_PROCESS", "ARCHIVED"},
    "IN_PROCESS": {"QC_PENDING", "ARCHIVED"},
    "QC_PENDING": {"QC_PASSED", "QC_FAILED"},
    "QC_PASSED": {"ARCHIVED"},
    "QC_FAILED": {"IN_PROCESS", "ARCHIVED"},
    "ARCHIVED": set(),  # terminal
}

SAMPLE_TRANSITION_ROLES: Dict[str, Dict[str, Set[str]]] = {
    "REGISTERED": {
        "IN_PROCESS": {"LAB_TECH", "ADMIN"},
        "ARCHIVED": {"ADMIN"},
    },
    "IN_PROCESS": {
        "QC_PENDING": {"LAB_TECH", "ADMIN"},
        "ARCHIVED": {"ADMIN"},
    },
    "QC_PENDING": {
        "QC_PASSED": {"QA", "ADMIN"},
        "QC_FAILED": {"QA", "ADMIN"},
    },
    "QC_PASSED": {
        "ARCHIVED": {"ADMIN"},
    },
    "QC_FAILED": {
        "IN_PROCESS": {"LAB_TECH", "ADMIN"},
        "ARCHIVED": {"ADMIN"},
    },
}


# ===============================================================
# EXPERIMENT WORKFLOW
# ===============================================================

EXPERIMENT_STATUSES: Set[str] = {
    "PLANNED",
    "RUNNING",
    "PAUSED",
    "COMPLETED",
    "CANCELLED",
}

EXPERIMENT_TRANSITIONS: Dict[str, Set[str]] = {
    "PLANNED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"PAUSED", "COMPLETED", "CANCELLED"},
    "PAUSED": {"RUNNING", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}

EXPERIMENT_TRANSITION_ROLES: Dict[str, Dict[str, Set[str]]] = {
    "PLANNED": {
        "RUNNING": {"SCIENTIST", "ADMIN"},
        "CANCELLED": {"ADMIN"},
    },
    "RUNNING": {
        "PAUSED": {"SCIENTIST", "ADMIN"},
        "COMPLETED": {"SCIENTIST", "ADMIN"},
        "CANCELLED": {"ADMIN"},
    },
    "PAUSED": {
        "RUNNING": {"SCIENTIST", "ADMIN"},
        "CANCELLED": {"ADMIN"},
    },
}


# ===============================================================
# VALIDATION
# ===============================================================

def validate_transition(kind: str, old: str, new: str) -> None:
    old = (old or "").strip().upper()
    new = (new or "").strip().upper()

    if kind == "sample":
        transitions = SAMPLE_TRANSITIONS
        universe = SAMPLE_STATUSES
    elif kind == "experiment":
        transitions = EXPERIMENT_TRANSITIONS
        universe = EXPERIMENT_STATUSES
    else:
        raise ValueError("Unknown workflow kind")

    if old not in universe:
        raise ValueError(f"Unknown {kind} status: {old}")

    if new not in universe:
        raise ValueError(f"Unknown {kind} status: {new}")

    if old == new:
        return

    if new not in transitions.get(old, set()):
        raise ValueError(f"Invalid {kind} status transition: {old} -> {new}")


# ===============================================================
# INTROSPECTION HELPERS
# ===============================================================

def allowed_next_states(kind: str, current: str) -> List[str]:
    current = (current or "").strip().upper()

    if kind == "sample":
        return sorted(SAMPLE_TRANSITIONS.get(current, set()))

    if kind == "experiment":
        return sorted(EXPERIMENT_TRANSITIONS.get(current, set()))

    raise ValueError("Unknown workflow kind")


def required_roles(kind: str, current: str, target: str) -> Set[str]:
    current = (current or "").strip().upper()
    target = (target or "").strip().upper()

    if kind == "sample":
        return SAMPLE_TRANSITION_ROLES.get(current, {}).get(target, set())

    if kind == "experiment":
        return EXPERIMENT_TRANSITION_ROLES.get(current, {}).get(target, set())

    raise ValueError("Unknown workflow kind")


def workflow_definition(kind: str) -> Dict:
    if kind == "sample":
        return {
            "kind": "sample",
            "statuses": sorted(SAMPLE_STATUSES),
            "transitions": {k: sorted(v) for k, v in SAMPLE_TRANSITIONS.items()},
            "terminal_states": sorted(
                state for state, nexts in SAMPLE_TRANSITIONS.items() if not nexts
            ),
        }

    if kind == "experiment":
        return {
            "kind": "experiment",
            "statuses": sorted(EXPERIMENT_STATUSES),
            "transitions": {k: sorted(v) for k, v in EXPERIMENT_TRANSITIONS.items()},
            "terminal_states": sorted(
                state for state, nexts in EXPERIMENT_TRANSITIONS.items() if not nexts
            ),
        }

    raise ValueError("Unknown workflow kind")


# ===============================================================
# ROLE-AWARE TRANSITION RESOLUTION
# ===============================================================

def allowed_transitions(kind: str, current: str, role: str) -> List[str]:
    """
    Return all target states the given role is allowed to transition to
    from the current state.
    """
    current = (current or "").strip().upper()
    role = (role or "").strip().upper()

    allowed: List[str] = []

    for target in allowed_next_states(kind, current):
        roles = required_roles(kind, current, target)
        if role in roles:
            allowed.append(target)

    return sorted(allowed)


__all__ = [
    "validate_transition",
    "allowed_next_states",
    "required_roles",
    "allowed_transitions",
    "workflow_definition",
]
