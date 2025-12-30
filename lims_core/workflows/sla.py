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
- UI and API must consume computed SLA status, not raw rules
"""

# ===============================================================
# SLA DEFINITIONS
# ===============================================================
# Semantics:
# - warn_after   : duration after which SLA enters WARNING
# - breach_after : duration after which SLA is BREACHED
# - severity     : semantic weight used by metrics / alerts
#
# If a state is absent or value is None → no SLA applies
# ===============================================================

SLA_DEFINITIONS: Dict[str, Dict[str, Optional[Dict[str, Any]]]] = {

    # -----------------------------------------------------------
    # SAMPLE WORKFLOW SLA
    # -----------------------------------------------------------
    "sample": {
        "REGISTERED": {
            "warn_after": timedelta(hours=12),
            "breach_after": timedelta(hours=24),
            "severity": "warning",
        },

        "IN_PROCESS": {
            "warn_after": timedelta(days=2),
            "breach_after": timedelta(days=3),
            "severity": "critical",
        },

        # Terminal or non-critical states
        "APPROVED": None,
        "ARCHIVED": None,
        "REJECTED": None,
    },

    # -----------------------------------------------------------
    # EXPERIMENT WORKFLOW SLA
    # -----------------------------------------------------------
    "experiment": {
        "PLANNED": {
            "warn_after": timedelta(days=1),
            "breach_after": timedelta(days=2),
            "severity": "warning",
        },

        "RUNNING": {
            "warn_after": timedelta(days=5),
            "breach_after": timedelta(days=7),
            "severity": "critical",
        },

        "COMPLETED": None,
    },
}

# ===============================================================
# PUBLIC API
# ===============================================================

def get_sla(kind: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Return SLA definition for a workflow kind + state.

    Args:
        kind: workflow kind (case-insensitive)
        state: workflow status (case-insensitive)

    Returns:
        dict with keys:
          - warn_after (timedelta)
          - breach_after (timedelta)
          - severity (str)
        or None if no SLA applies
    """
    if not kind or not state:
        return None

    kind = kind.strip().lower()
    state = state.strip().upper()

    return SLA_DEFINITIONS.get(kind, {}).get(state)
