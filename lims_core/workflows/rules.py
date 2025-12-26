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
import re


# ===============================================================
# ROLE NORMALIZATION
# ===============================================================
# Normalize user-provided / DB roles into canonical workflow roles.
#
# Examples handled:
# - "Technician" -> LAB_TECH
# - "Lab Technician" -> LAB_TECH
# - "LAB TECHNICIAN" -> LAB_TECH
# - "lab-tech" -> LAB_TECH
# - "lab_tech" -> LAB_TECH
ROLE_ALIASES: Dict[str, str] = {
    "TECHNICIAN": "LAB_TECH",
    "LAB_TECHNICIAN": "LAB_TECH",
    "LAB_TECH": "LAB_TECH",
    "LABTECH": "LAB_TECH",
    "LAB_TECHNOLOGIST": "LAB_TECH",  # optional, harmless
    "SCIENTIST": "SCIENTIST",
    "RESEARCHER": "SCIENTIST",
    "QA": "QA",
    "Q_A": "QA",
    "ADMIN": "ADMIN",
    "SUPERUSER": "ADMIN",
}


def normalize_role(role: str) -> str:
    """
    Canonicalize role strings so that small formatting differences
    do not break permission logic.

    Steps:
    1) Uppercase and strip
    2) Convert whitespace and hyphens to underscores
    3) Collapse repeated underscores
    4) Apply alias mapping
    """
    r = (role or "").strip().upper()
    if not r:
        return r

    # Convert runs of spaces and hyphens into underscores
    r = re.sub(r"[\s\-]+", "_", r)

    # Collapse multiple underscores
    r = re.sub(r"_+", "_", r)

    # Some people type "LABTECH" without separators
    r = r.replace("LABTECHNICIAN", "LAB_TECHNICIAN").replace("LABTECH", "LABTECH")

    return ROLE_ALIASES.get(r, r)


# ===============================================================
# SAMPLE WORKFLOW (canonical lifecycle)
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
def _universe_and_transitions(kind: str):
    kind = (kind or "").strip().lower()
    if kind == "sample":
        return SAMPLE_STATUSES, SAMPLE_TRANSITIONS
    if kind == "experiment":
        return EXPERIMENT_STATUSES, EXPERIMENT_TRANSITIONS
    raise ValueError("Unknown workflow kind")


def validate_transition(kind: str, old: str, new: str) -> None:
    kind = (kind or "").strip().lower()
    old = (old or "").strip().upper()
    new = (new or "").strip().upper()

    universe, transitions = _universe_and_transitions(kind)

    if old not in universe:
        raise ValueError(f"Unknown {kind} status: {old}")

    if new not in universe:
        raise ValueError(f"Unknown {kind} status: {new}")

    if old == new:
        return

    if new not in transitions.get(old, set()):
        raise ValueError(f"Invalid {kind} status transition: {old} -> {new}")


def validate_transition_with_role(kind: str, old: str, new: str, role: str) -> None:
    """
    Canonical enforcement:
    - Transition must be valid
    - Role must be permitted for (old -> new)
    """
    validate_transition(kind, old, new)

    kind = (kind or "").strip().lower()
    old = (old or "").strip().upper()
    new = (new or "").strip().upper()

    if old == new:
        return

    role_norm = normalize_role(role)

    required = required_roles(kind, old, new)
    if required and role_norm not in required:
        req = ", ".join(sorted(required))
        raise ValueError(
            f"Role not permitted for {kind} transition: {old} -> {new}. Required: {req}"
        )


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
    "validate_transition_with_role",
    "allowed_next_states",
    "required_roles",
    "allowed_transitions",
    "workflow_definition",
    "normalize_role",
]
