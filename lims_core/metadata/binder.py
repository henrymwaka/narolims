# lims_core/metadata/binder.py

from __future__ import annotations

from typing import Optional

from lims_core.metadata.models import MetadataSchema
from lims_core.metadata.resolver import resolve_metadata_schema


def pick_schema_for_object(
    *,
    laboratory,
    object_type: str,
    analysis_context=None,
) -> Optional[MetadataSchema]:
    """
    Returns the best schema to bind (freeze) for the given object context.

    Strategy:
      - resolver returns base + (optional) context-specific schemas
      - choose latest by (version desc, id desc)
    """
    qs = resolve_metadata_schema(
        laboratory=laboratory,
        object_type=object_type,
        analysis_context=analysis_context,
    )
    return qs.order_by("-version", "-id").first()


def bind_schema_if_missing(
    *,
    obj,
    object_type: str,
) -> None:
    """
    Freeze metadata_schema if it is currently NULL.
    Designed for use during creation only.
    """
    if getattr(obj, "metadata_schema_id", None):
        return

    schema = pick_schema_for_object(
        laboratory=getattr(obj, "laboratory", None),
        object_type=object_type,
        analysis_context=getattr(obj, "analysis_context", None),
    )
    obj.metadata_schema = schema
