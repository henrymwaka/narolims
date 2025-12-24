# lims_core/workflows/sla.py
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Dict, Any


"""
Authoritative SLA definitions and helpers.

This module is PURE LOGIC + DATA.
No Django imports.
Safe to import at startup.
"""


# ===============================================================
# SLA DEFINITIONS
# ===============================================================

SLA_DEFINITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "sample": {
        "RECEIVED": {
            "max_age": timedelta(hours=24),
            "severity": "warning",
        },
        "PROCESSING": {
            "max_age": timedelta(days=3),
            "severity": "critical",
        },
    },
    "experiment": {
        "CREATED": {
            "max_age": timedelta(days=2),
            "severity": "warning",
        },
        "RUNNING": {
            "max_age": timedelta(days=7),
            "severity": "critical",
        },
    },
}


# ===============================================================
# PUBLIC API
# ===============================================================

def get_sla(kind: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Return SLA definition for a workflow kind + state.

    Returns:
        dict with keys (max_age, severity)
        or None if no SLA applies
    """

    if not kind or not state:
        return None

    kind = kind.strip().lower()
    state = state.strip().upper()

    return SLA_DEFINITIONS.get(kind, {}).get(state)
