# lims_core/signals.py

from __future__ import annotations

import logging
import threading
from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from lims_core.labs.models import LaboratoryProfile
from lims_core.metadata.models import MetadataSchema, MetadataField

logger = logging.getLogger(__name__)

# Which object types should always have a default schema available
DEFAULT_APPLIES_TO = ("sample", "batch", "experiment")

# Optional configuration:
# In settings.py you can set:
#   NAROLIMS_BASELINE_LAB_CODE = "NARL-GENERAL"
# or any other lab code that you want to serve as the baseline template.
SETTINGS_BASELINE_KEY = "NAROLIMS_BASELINE_LAB_CODE"


# ------------------------------------------------------------
# Request-scoped "current user" storage (used by middleware/audit)
# ------------------------------------------------------------

_thread_locals = threading.local()


def set_current_user(user=None):
    """
    Store the current authenticated user in thread-local storage.
    Used by middleware and any audit hooks that need user context.
    """
    _thread_locals.user = user


def get_current_user(default=None):
    return getattr(_thread_locals, "user", default)


def clear_current_user():
    if hasattr(_thread_locals, "user"):
        delattr(_thread_locals, "user")


# ------------------------------------------------------------
# Baseline selection helpers
# ------------------------------------------------------------

def _configured_baseline_lab_code() -> str | None:
    code = getattr(settings, SETTINGS_BASELINE_KEY, None)
    if not code:
        return None
    code = str(code).strip()
    return code or None


def _pick_source_profile_from_config() -> LaboratoryProfile | None:
    code = _configured_baseline_lab_code()
    if not code:
        return None
    try:
        return LaboratoryProfile.objects.select_related("laboratory").get(
            laboratory__code=code
        )
    except LaboratoryProfile.DoesNotExist:
        logger.warning(
            "Configured baseline lab code not found: %s (setting %s).",
            code,
            SETTINGS_BASELINE_KEY,
        )
        return None


def _profile_has_any_default_schema(lp: LaboratoryProfile) -> bool:
    return MetadataSchema.objects.filter(
        laboratory_profile=lp,
        is_active=True,
        analysis_context__isnull=True,
    ).exists()


def _pick_source_profile_fallback() -> LaboratoryProfile | None:
    """
    Fallback baseline selection when no config is provided.

    Strategy:
    - choose the first lab profile that already has at least one active default schema
    - deterministic ordering by laboratory code
    """
    for lp in LaboratoryProfile.objects.select_related("laboratory").order_by("laboratory__code"):
        if _profile_has_any_default_schema(lp):
            return lp
    return None


def _pick_source_profile() -> LaboratoryProfile | None:
    """
    Source profile resolution order:
    1) settings.NAROLIMS_BASELINE_LAB_CODE, if defined and valid
    2) first profile (by lab code) that has at least one default schema
    """
    lp = _pick_source_profile_from_config()
    if lp:
        return lp
    return _pick_source_profile_fallback()


# ------------------------------------------------------------
# Schema clone helpers
# ------------------------------------------------------------

def _find_source_schema(
    *,
    source_profile: LaboratoryProfile,
    applies_to: str,
    prefer_code: str | None = None,
    prefer_version: str | None = None,
) -> MetadataSchema | None:
    """
    Try to find a schema on the baseline profile.

    Priority:
      1) Match (code, version) if provided
      2) Otherwise, latest active schema for applies_to, default context
    """
    qs = MetadataSchema.objects.filter(
        laboratory_profile=source_profile,
        applies_to=applies_to,
        is_active=True,
        analysis_context__isnull=True,
    )

    if prefer_code and prefer_version:
        exact = qs.filter(code=prefer_code, version=prefer_version).order_by("-created_at", "-id").first()
        if exact:
            return exact

    return qs.order_by("-created_at", "-id").first()


def _target_has_active_default_schema(*, target: LaboratoryProfile, applies_to: str) -> bool:
    return MetadataSchema.objects.filter(
        laboratory_profile=target,
        applies_to=applies_to,
        is_active=True,
        analysis_context__isnull=True,
    ).exists()


def _clone_schema_with_fields(
    *,
    source: MetadataSchema,
    target: LaboratoryProfile,
) -> MetadataSchema:
    """
    Clone schema and its fields into target profile for default context (analysis_context=None).

    IMPORTANT:
    - For accredited labs we must NOT create the schema locked before cloning fields,
      because MetadataField.save() rejects modifications on locked schemas.
    - Therefore:
        create schema unlocked -> clone fields -> optionally lock schema.
    """
    with transaction.atomic():
        should_lock = bool(target.accreditation_mode)

        new = MetadataSchema.objects.create(
            laboratory_profile=target,
            analysis_context=None,
            code=source.code,
            version=source.version,
            name=source.name,
            description=source.description,
            applies_to=source.applies_to,
            is_active=True,
            is_locked=False,  # always start unlocked so we can add fields
            lock_reason="",
        )

        fields = list(MetadataField.objects.filter(schema=source).order_by("order", "id"))
        for f in fields:
            MetadataField.objects.create(
                schema=new,
                order=f.order,
                code=f.code,
                label=f.label,
                field_type=f.field_type,
                required=f.required,
                help_text=f.help_text,
                choices=f.choices,
            )

        if should_lock:
            MetadataSchema.objects.filter(pk=new.pk).update(
                is_locked=True,
                locked_at=timezone.now(),
                lock_reason="Auto-provisioned baseline",
            )
            new.refresh_from_db()

        return new


# ------------------------------------------------------------
# Auto-provisioning hook
# ------------------------------------------------------------

@receiver(post_save, sender=LaboratoryProfile)
def ensure_default_metadata_schemas(sender, instance: LaboratoryProfile, created: bool, **kwargs):
    """
    Auto-provision default schemas so normal users never hit schema resolver failures.

    Behavior:
      - If the profile already has an active default schema for a given applies_to, do nothing.
      - Otherwise, clone from the baseline profile selected by:
          settings.NAROLIMS_BASELINE_LAB_CODE (if set) else fallback auto-pick.
      - For "sample", if LaboratoryProfile.schema_code/schema_version are set, prefer that schema on baseline.
      - For batch and experiment, clone latest baseline schema for that applies_to.
    """
    try:
        target = instance

        source_profile = _pick_source_profile()
        if not source_profile:
            logger.warning(
                "No baseline LaboratoryProfile with schemas exists yet. "
                "Skipping schema auto-provision for lab_profile=%s (lab=%s).",
                target.id,
                getattr(target.laboratory, "code", "?"),
            )
            return

        for applies_to in DEFAULT_APPLIES_TO:
            if _target_has_active_default_schema(target=target, applies_to=applies_to):
                continue

            prefer_code = None
            prefer_version = None

            if applies_to == "sample":
                prefer_code = (target.schema_code or "").strip() or None
                prefer_version = (target.schema_version or "").strip() or None

            source = _find_source_schema(
                source_profile=source_profile,
                applies_to=applies_to,
                prefer_code=prefer_code,
                prefer_version=prefer_version,
            )

            if not source:
                logger.warning(
                    "No baseline schema found to clone (baseline_lab=%s applies_to=%s).",
                    getattr(source_profile.laboratory, "code", "?"),
                    applies_to,
                )
                continue

            new = _clone_schema_with_fields(source=source, target=target)

            logger.info(
                "Auto-provisioned schema for lab_profile=%s lab=%s applies_to=%s schema_id=%s code=%s version=%s locked=%s",
                target.id,
                getattr(target.laboratory, "code", "?"),
                applies_to,
                new.id,
                new.code,
                new.version,
                new.is_locked,
            )

    except Exception as exc:
        # Never block saving a profile due to provisioning
        logger.exception(
            "Schema auto-provision failed for LaboratoryProfile id=%s: %s",
            instance.id,
            exc,
        )
