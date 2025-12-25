"""
Authoritative workflow rules for LIMS entities.

Defines:
- Status universes
- Allowed transitions
- Role requirements per transition
- Introspection helpers used by UI and API
"""

from __future__ import annotations
from typing import Dict, Set, List


# ===============================================================
# ROLE NORMALIZATION
# ===============================================================
# Your DB/tests use human roles like "Technician"
# Workflow engine uses canonical roles like "LAB_TECH"
ROLE_ALIASES: Dict[str, str] = {
    "TECHNICIAN": "LAB_TECH",
    "LAB_TECHNICIAN": "LAB_TECH",
    "LAB_TECH": "LAB_TECH",
    "SCIENTIST": "SCIENTIST",
    "RESEARCHER": "SCIENTIST",
    "QA": "QA",
    "ADMIN": "ADMIN",
    "SUPERUSER": "ADMIN",
}


def normalize_role(role: str) -> str:
    r = (role or "").strip().upper()
    return ROLE_ALIASES.get(r, r)


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

# IMPORTANT:
# Your tests use role "Technician" and expect RUNNING to be allowed.
# That means LAB_TECH must be allowed for PLANNED -> RUNNING.
EXPERIMENT_TRANSITION_ROLES: Dict[str, Dict[str, Set[str]]] = {
    "PLANNED": {
        "RUNNING": {"SCIENTIST", "LAB_TECH", "ADMIN"},
        "CANCELLED": {"ADMIN"},
    },
    "RUNNING": {
        "PAUSED": {"SCIENTIST", "LAB_TECH", "ADMIN"},
        "COMPLETED": {"SCIENTIST", "LAB_TECH", "ADMIN"},
        "CANCELLED": {"ADMIN"},
    },
    "PAUSED": {
        "RUNNING": {"SCIENTIST", "LAB_TECH", "ADMIN"},
        "CANCELLED": {"ADMIN"},
    },
}


# ===============================================================
# VALIDATION
# ===============================================================

def validate_transition(kind: str, old: str, new: str) -> None:
    kind = (kind or "").strip().lower()
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
    kind = (kind or "").strip().lower()
    current = (current or "").strip().upper()

    if kind == "sample":
        return sorted(SAMPLE_TRANSITIONS.get(current, set()))
    if kind == "experiment":
        return sorted(EXPERIMENT_TRANSITIONS.get(current, set()))

    raise ValueError("Unknown workflow kind")


def required_roles(kind: str, current: str, target: str) -> Set[str]:
    kind = (kind or "").strip().lower()
    current = (current or "").strip().upper()
    target = (target or "").strip().upper()

    if kind == "sample":
        roles = SAMPLE_TRANSITION_ROLES.get(current, {}).get(target, set())
    elif kind == "experiment":
        roles = EXPERIMENT_TRANSITION_ROLES.get(current, {}).get(target, set())
    else:
        raise ValueError("Unknown workflow kind")

    return {normalize_role(r) for r in roles}


def workflow_definition(kind: str) -> Dict:
    kind = (kind or "").strip().lower()

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


def allowed_transitions(kind: str, current: str, role: str) -> List[str]:
    role = normalize_role(role)
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
    "normalize_role",
]
