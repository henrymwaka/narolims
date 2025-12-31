# lims_core/metadata/binder.py

"""
DEPRECATED — DO NOT USE FOR MUTATION

Metadata schema freezing is enforced at the MODEL layer
(Sample / Experiment save()).

This module is retained as a compatibility shim only.
"""

from __future__ import annotations


def bind_schema_if_missing(*, obj, object_type: str) -> None:
    """
    NO-OP by design.

    Schema freezing is enforced centrally in model save().
    This function exists only to avoid breaking older imports.
    """
    return
