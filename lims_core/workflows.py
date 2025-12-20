# lims_core/workflows.py
from __future__ import annotations

from typing import Dict, Set


# ===============================================================
# Sample workflow
# ===============================================================
SAMPLE_STATUSES = {
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
    "ARCHIVED": set(),
}


# ===============================================================
# Experiment workflow
# ===============================================================
EXPERIMENT_STATUSES = {
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


# ===============================================================
# Validators
# ===============================================================
def validate_transition(kind: str, old: str, new: str) -> None:
    old = (old or "").strip()
    new = (new or "").strip()

    if kind == "sample":
        transitions = SAMPLE_TRANSITIONS
        universe = SAMPLE_STATUSES
    elif kind == "experiment":
        transitions = EXPERIMENT_TRANSITIONS
        universe = EXPERIMENT_STATUSES
    else:
        raise ValueError("Unknown workflow kind.")

    if old not in universe:
        raise ValueError(f"Unknown {kind} status: {old}")

    if new not in universe:
        raise ValueError(f"Unknown {kind} status: {new}")

    if old == new:
        return

    if new not in transitions.get(old, set()):
        raise ValueError(f"Invalid {kind} status transition: {old} -> {new}")


# ===============================================================
# Introspection helpers (9B)
# ===============================================================
def workflow_definition(kind: str) -> Dict:
    if kind == "sample":
        return {
            "kind": "sample",
            "statuses": sorted(SAMPLE_STATUSES),
            "transitions": {
                k: sorted(v) for k, v in SAMPLE_TRANSITIONS.items()
            },
            "terminal_states": sorted(
                s for s, v in SAMPLE_TRANSITIONS.items() if not v
            ),
        }

    if kind == "experiment":
        return {
            "kind": "experiment",
            "statuses": sorted(EXPERIMENT_STATUSES),
            "transitions": {
                k: sorted(v) for k, v in EXPERIMENT_TRANSITIONS.items()
            },
            "terminal_states": sorted(
                s for s, v in EXPERIMENT_TRANSITIONS.items() if not v
            ),
        }

    raise ValueError("Unknown workflow kind.")


def allowed_next_states(kind: str, current: str) -> list[str]:
    current = (current or "").strip()

    if kind == "sample":
        return sorted(SAMPLE_TRANSITIONS.get(current, set()))

    if kind == "experiment":
        return sorted(EXPERIMENT_TRANSITIONS.get(current, set()))

    raise ValueError("Unknown workflow kind.")


# ===============================================================
# Workflow registry (REQUIRED BY 9C)
# ===============================================================
WORKFLOWS = {
    "sample": {
        "statuses": SAMPLE_STATUSES,
        "transitions": SAMPLE_TRANSITIONS,
        "validate": lambda old, new: validate_transition("sample", old, new),
        "definition": lambda: workflow_definition("sample"),
        "next": lambda current: allowed_next_states("sample", current),
    },
    "experiment": {
        "statuses": EXPERIMENT_STATUSES,
        "transitions": EXPERIMENT_TRANSITIONS,
        "validate": lambda old, new: validate_transition("experiment", old, new),
        "definition": lambda: workflow_definition("experiment"),
        "next": lambda current: allowed_next_states("experiment", current),
    },
}
