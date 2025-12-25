# ⚠️ LEGACY FILE
# Not used by the active workflow engine.
# Kept temporarily for reference only.
# DO NOT MODIFY OR USE.

"""
Authoritative workflow transition rules for Sample objects.

This module MUST mirror WORKFLOW_MATRIX.md exactly.
"""

TERMINAL_STATES = {"ARCHIVED"}

ROLE_TRANSITIONS = {
    "RECEIVED": {
        "LAB_TECH": {"QC_PENDING"},
        "QA": set(),
        "ADMIN": {"QC_PENDING"},
    },
    "QC_PENDING": {
        "LAB_TECH": set(),
        "QA": {"QC_PASSED", "QC_FAILED"},
        "ADMIN": {"QC_PASSED", "QC_FAILED", "ARCHIVED"},
    },
    "QC_PASSED": {
        "LAB_TECH": set(),
        "QA": set(),
        "ADMIN": {"ARCHIVED"},
    },
    "QC_FAILED": {
        "LAB_TECH": set(),
        "QA": set(),
        "ADMIN": {"ARCHIVED"},
    },
    "ARCHIVED": {
        "LAB_TECH": set(),
        "QA": set(),
        "ADMIN": set(),
    },
}


def allowed_transitions(current_state: str, role: str) -> set[str]:
    """
    Returns allowed target states for a given state + role.
    """
    return ROLE_TRANSITIONS.get(current_state, {}).get(role, set())


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def can_transition(current_state: str, target_state: str, role: str) -> bool:
    """
    Definitive transition check.
    """
    if is_terminal(current_state):
        return False
    return target_state in allowed_transitions(current_state, role)
