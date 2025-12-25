# lims_core/workflows/sla.py
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Dict, Any

"""
Authoritative SLA definitions and helpers.

This module is PURE LOGIC + DATA.
- No Django imports
- Safe to import at startup
- Must align EXACTLY with workflow rules
"""


# ===============================================================
# SLA DEFINITIONS
# ===============================================================

SLA_DEFINITIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    # -----------------------------------------------------------
    # SAMPLE WORKFLOW SLA
    # -----------------------------------------------------------
    "sample": {
        # Initial registration should not sit idle too long
        "REGISTERED": {
            "max_age": timedelta(hours=24),
            "severity": "warning",
        },

        # Active lab processing is time-critical
        "IN_PROCESS": {
            "max_age": timedelta(days=3),
            "severity": "critical",
        },

        # Optional: QC_PENDING SLA (uncomment if required)
        # "QC_PENDING": {
        #     "max_age": timedelta(days=2),
        #     "severity": "warning",
        # },
    },

    # -----------------------------------------------------------
    # EXPERIMENT WORKFLOW SLA
    # -----------------------------------------------------------
    "experiment": {
        # Planning should not stall indefinitely
        "PLANNED": {
            "max_age": timedelta(days=2),
            "severity": "warning",
        },

        # Running experiments are high priority
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

    Args:
        kind: "sample" | "experiment"
        state: workflow status (case-insensitive)

    Returns:
        dict with keys:
          - max_age (timedelta)
          - severity (str)
        or None if no SLA applies
    """
    if not kind or not state:
        return None

    kind = kind.strip().lower()
    state = state.strip().upper()

    return SLA_DEFINITIONS.get(kind, {}).get(state)
