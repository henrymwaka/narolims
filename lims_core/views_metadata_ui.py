# lims_core/views_metadata_ui.py

from __future__ import annotations

from typing import Dict, Any, List
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from lims_core.metadata.models import MetadataValue
from lims_core.metadata.resolver import resolve_metadata_schema
from lims_core.metadata.validators import validate_metadata_payload
from lims_core.models import Experiment, Sample

logger = logging.getLogger(__name__)


# ==========================================================
# Helpers
# ==========================================================

def _get_model_for_object_type(object_type: str):
    object_type = (object_type or "").strip().lower()
    if object_type == "sample":
        return Sample
    if object_type == "experiment":
        return Experiment
    raise ValueError("Unsupported object type")


def _resolve_laboratory_profile(obj):
    """
    LaboratoryProfile is attached to Laboratory via:
      related_name="profile"
    """
    lab = getattr(obj, "laboratory", None)
    if lab is None:
        return None
    return getattr(lab, "profile", None)


def _resolve_analysis_context(obj):
    """
    Step 8: Resolve analysis context from the object itself.
    - For analytical labs: set Sample.analysis_context / Experiment.analysis_context
    - For tissue culture / R&D labs: leave it NULL (base schemas still apply)
    """
    return getattr(obj, "analysis_context", None)


def _get_existing_values(*, object_type: str, object_id: int) -> Dict[str, Any]:
    values = (
        MetadataValue.objects.filter(
            object_type=object_type,
            object_id=object_id,
        )
        .select_related("schema_field")
    )
    return {mv.schema_field.code: mv.get_value() for mv in values}


def _persist_metadata_values(
    *,
    schema,
    object_type: str,
    object_id: int,
    payload: Dict[str, Any],
    user,
) -> None:
    for field in schema.fields.all():
        if field.code not in payload:
            continue

        value = payload[field.code]

        mv, created = MetadataValue.objects.get_or_create(
            schema_field=field,
            object_type=object_type,
            object_id=object_id,
            defaults={"created_by": user},
        )

        mv.value_text = ""
        mv.value_number = None
        mv.value_date = None
        mv.value_boolean = None

        if field.field_type == "number":
            mv.value_number = value
        elif field.field_type == "date":
            mv.value_date = value
        elif field.field_type == "boolean":
            mv.value_boolean = value
        else:
            mv.value_text = value or ""

        mv.created_by = user
        mv.save()


def get_metadata_summary(*, object_type: str, object_id: int) -> List[Dict[str, Any]]:
    values = (
        MetadataValue.objects.filter(
            object_type=object_type,
            object_id=object_id,
        )
        .select_related("schema_field", "schema_field__schema")
        .order_by("schema_field__schema__name", "schema_field__order")
    )

    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for mv in values:
        schema = mv.schema_field.schema
        grouped.setdefault(schema, []).append(
            {"label": mv.schema_field.label, "value": mv.get_value()}
        )

    return [{"schema": schema, "values": items} for schema, items in grouped.items()]


# ==========================================================
# View
# ==========================================================

@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def metadata_form(request: HttpRequest, object_type: str, object_id: int) -> HttpResponse:
    """
    Schema-driven metadata entry view.
    - Resolves schemas via LaboratoryProfile (lab.profile)
    - Applies base schemas + optional context schemas
    - Validates payload
    - Persists MetadataValue records
    """

    model = _get_model_for_object_type(object_type)

    try:
        obj = model.objects.get(pk=object_id)
    except model.DoesNotExist:
        raise Http404("Object not found")

    laboratory_profile = _resolve_laboratory_profile(obj)
    analysis_context = _resolve_analysis_context(obj)

    if laboratory_profile is None:
        lab = getattr(obj, "laboratory", None)
        logger.warning(
            "[METADATA] Laboratory %s has no LaboratoryProfile (expected lab.profile)",
            getattr(lab, "code", None),
        )
        raise PermissionDenied("Object is not linked to a laboratory profile")

    logger.debug(
        "[METADATA_FORM] object_type=%s object_id=%s lab=%s profile_id=%s schema=%s:%s ctx=%s",
        object_type,
        object_id,
        getattr(getattr(obj, "laboratory", None), "code", None),
        getattr(laboratory_profile, "id", None),
        getattr(laboratory_profile, "schema_code", None),
        getattr(laboratory_profile, "schema_version", None),
        getattr(getattr(analysis_context, "code", None), None),
    )

    schemas = resolve_metadata_schema(
        laboratory=laboratory_profile,
        object_type=object_type,
        analysis_context=analysis_context,
    )

    if not schemas.exists():
        messages.info(request, "No metadata is required for this object.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    existing_values = _get_existing_values(object_type=object_type, object_id=object_id)
    errors: Dict[str, Dict[str, list]] = {}

    if request.method == "POST":
        payload: Dict[str, Any] = {}

        for schema in schemas:
            for field in schema.fields.all():
                raw = request.POST.get(field.code)

                if raw in ("", None):
                    payload[field.code] = None
                    continue

                if field.field_type == "number":
                    try:
                        payload[field.code] = float(raw)
                    except ValueError:
                        payload[field.code] = raw
                elif field.field_type == "boolean":
                    payload[field.code] = raw.lower() in ("1", "true", "yes", "on")
                else:
                    payload[field.code] = raw.strip()

        for schema in schemas:
            result = validate_metadata_payload(schema=schema, payload=payload)
            if result["missing_fields"] or result["invalid_fields"]:
                errors[schema.code] = {
                    "missing": result["missing_fields"],
                    "invalid": result["invalid_fields"],
                }

        if not errors:
            for schema in schemas:
                _persist_metadata_values(
                    schema=schema,
                    object_type=object_type,
                    object_id=object_id,
                    payload=payload,
                    user=request.user,
                )
            messages.success(request, "Metadata saved successfully.")
            return redirect(request.path)

        messages.error(request, "Please correct the errors below.")

    return render(
        request,
        "lims_core/metadata/form.html",
        {
            "object": obj,
            "object_type": object_type,
            "schemas": schemas,
            "values": existing_values,
            "errors": errors,
            "analysis_context": analysis_context,
        },
    )
