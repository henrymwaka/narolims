# lims_core/views_metadata_ui.py

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging
import json
import datetime

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

PLACEHOLDER_NO_DATA = "not provided"

FIELD_TEMPLATE_MAP = {
    "text": "lims_core/metadata/field_text.html",
    "number": "lims_core/metadata/field_number.html",
    "date": "lims_core/metadata/field_date.html",
    "boolean": "lims_core/metadata/field_boolean.html",
    "choice": "lims_core/metadata/field_choice.html",
}

FALLBACK_FIELD_TEMPLATE = "lims_core/metadata/field_unknown.html"


def _get_model_for_object_type(object_type: str):
    object_type = (object_type or "").strip().lower()
    if object_type == "sample":
        return Sample
    if object_type == "experiment":
        return Experiment
    raise ValueError(f"Unsupported object type: {object_type}")


def _resolve_laboratory_profile(obj):
    lab = getattr(obj, "laboratory", None)
    return getattr(lab, "profile", None) if lab else None


def _resolve_analysis_context(obj):
    return getattr(obj, "analysis_context", None)


def _safe_get_metadata_value(mv: MetadataValue):
    if mv.value_text not in (None, ""):
        return mv.value_text
    if mv.value_number is not None:
        return mv.value_number
    if mv.value_date is not None:
        return mv.value_date.isoformat()
    if mv.value_boolean is not None:
        return mv.value_boolean
    return PLACEHOLDER_NO_DATA


def _get_existing_values(*, object_type: str, object_id: int) -> Dict[str, Any]:
    values = (
        MetadataValue.objects
        .filter(object_type=object_type, object_id=object_id)
        .select_related("schema_field")
    )

    result: Dict[str, Any] = {}
    for mv in values:
        code = mv.schema_field.code
        if code not in result:
            result[code] = _safe_get_metadata_value(mv)

    return result


def _pick_field_template(field_type: str) -> str:
    return FIELD_TEMPLATE_MAP.get(field_type, FALLBACK_FIELD_TEMPLATE)


def _normalize_choice_options(field) -> List[Dict[str, str]]:
    if hasattr(field, "options") and hasattr(field.options, "all"):
        opts = []
        for o in field.options.all():
            value = str(getattr(o, "value", getattr(o, "code", ""))).strip()
            label = str(getattr(o, "label", getattr(o, "name", value))).strip()
            if value:
                opts.append({"value": value, "label": label or value})
        if opts:
            return opts

    raw = getattr(field, "choices", None)
    if not raw:
        return []

    raw = str(raw).strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [{"value": str(v).strip(), "label": str(v).strip()} for v in data if str(v).strip()]
        if isinstance(data, dict):
            return [
                {"value": str(k).strip(), "label": str(v).strip() or str(k).strip()}
                for k, v in data.items()
                if str(k).strip()
            ]
    except Exception:
        pass

    return [{"value": p, "label": p} for p in raw.split(",") if p.strip()]


def _post_value_for_field(request: HttpRequest, field) -> tuple[Optional[str], Optional[str]]:
    """
    Return (raw_value, matched_key).
    Supports multiple naming conventions so the view does not silently miss inputs.
    """
    candidates = [
        getattr(field, "code", None),
        f"field_{getattr(field, 'code', '')}" if getattr(field, "code", None) else None,
        f"field_{getattr(field, 'id', '')}" if getattr(field, "id", None) else None,
        str(getattr(field, "id", "")) if getattr(field, "id", None) else None,
    ]
    for k in candidates:
        if not k:
            continue
        if k in request.POST:
            return request.POST.get(k), k
    return None, None


def _coerce_payload_value(field, raw: Optional[str]) -> Any:
    if raw in ("", None):
        return None

    if field.field_type == "number":
        try:
            return float(raw)
        except ValueError:
            return raw

    if field.field_type == "boolean":
        return str(raw).lower() in ("1", "true", "yes", "on")

    if field.field_type == "date":
        s = str(raw).strip()
        if not s:
            return None
        try:
            return datetime.date.fromisoformat(s)
        except Exception:
            return s

    return str(raw).strip()


def _persist_metadata_values(
    *,
    schema,
    object_type: str,
    object_id: int,
    payload: Dict[str, Any],
    user,
) -> None:
    for field in schema.fields.all().order_by("order", "id"):
        if field.code not in payload:
            continue

        value = payload.get(field.code)

        # Blank submitted: clear optional fields by deleting the row.
        if value is None:
            if not getattr(field, "required", False):
                MetadataValue.objects.filter(
                    schema_field=field,
                    object_type=object_type,
                    object_id=object_id,
                ).delete()
            continue

        mv, _ = MetadataValue.objects.get_or_create(
            schema_field=field,
            object_type=object_type,
            object_id=object_id,
            defaults={"created_by": user},
        )

        # IMPORTANT: value_text is NOT NULL in your DB, so never set it to None.
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
            mv.value_text = str(value) if value is not None else ""

        mv.created_by = user
        mv.save()


@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def metadata_form(request: HttpRequest, object_type: str, object_id: int) -> HttpResponse:
    model = _get_model_for_object_type(object_type)

    try:
        obj = model.objects.get(pk=object_id)
    except model.DoesNotExist:
        raise Http404("Object not found")

    laboratory_profile = _resolve_laboratory_profile(obj)
    analysis_context = _resolve_analysis_context(obj)

    if laboratory_profile is None:
        raise PermissionDenied("Object is not linked to a laboratory profile")

    accreditation_mode = bool(getattr(laboratory_profile, "accreditation_mode", False))

    try:
        schemas = list(
            resolve_metadata_schema(
                laboratory=laboratory_profile,
                object_type=object_type,
                analysis_context=analysis_context,
            )
        )
    except Exception:
        logger.exception("Schema resolution failed")
        messages.error(request, "Metadata configuration error. Please contact the administrator.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if not schemas:
        messages.info(request, "No metadata schema applies to this object.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    any_schema_unlocked = any(not getattr(schema, "is_locked", False) for schema in schemas)
    disable_submit = accreditation_mode and any_schema_unlocked

    existing_values = _get_existing_values(object_type=object_type, object_id=object_id)
    errors: Dict[str, Dict[str, list]] = {}

    if request.method == "POST":
        logger.info(
            "METADATA_POST: object_type=%s object_id=%s content_type=%s POST_keys=%s",
            object_type,
            object_id,
            request.content_type,
            list(request.POST.keys()),
        )

        if disable_submit:
            messages.error(
                request,
                "Metadata cannot be saved while accreditation mode is active and the schema is not locked.",
            )
            return redirect(request.path)

        payload: Dict[str, Any] = {}
        captured_any_key = False

        for schema in schemas:
            for field in schema.fields.all():
                raw, matched_key = _post_value_for_field(request, field)

                if matched_key is not None:
                    captured_any_key = True

                    # optional blank: store as None so _persist deletes row
                    coerced = _coerce_payload_value(field, raw)
                    if coerced is None and not getattr(field, "required", False):
                        payload[field.code] = None
                    else:
                        payload[field.code] = coerced
                else:
                    # Required but missing entirely from POST: mark missing for validator
                    if getattr(field, "required", False):
                        payload[field.code] = None

        if not captured_any_key:
            logger.warning(
                "No metadata fields captured from POST. object_type=%s object_id=%s schema_ids=%s",
                object_type,
                object_id,
                [getattr(s, "id", None) for s in schemas],
            )
            messages.error(request, "Nothing was saved. No metadata fields were captured from the submitted form.")
            return redirect(request.path)

        for schema in schemas:
            result = validate_metadata_payload(schema=schema, payload=payload)
            if result.get("missing_fields") or result.get("invalid_fields"):
                errors[schema.code] = {
                    "missing": result.get("missing_fields", []),
                    "invalid": result.get("invalid_fields", []),
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

    # Attach renderer template path and options so the template can include correctly.
    for schema in schemas:
        for field in schema.fields.all():
            field.renderer_template = _pick_field_template(field.field_type)
            field.choice_options = _normalize_choice_options(field) if field.field_type == "choice" else []
            field.current_value = existing_values.get(field.code, "")

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
            "placeholder": PLACEHOLDER_NO_DATA,
            "accreditation_mode": accreditation_mode,
            "any_schema_unlocked": any_schema_unlocked,
            "disable_submit": disable_submit,
        },
    )
