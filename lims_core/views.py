# lims_core/views.py
from __future__ import annotations

from typing import Optional

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404, render

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError, NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .mixins import AuditLogMixin
from .models import (
    AuditLog,
    Experiment,
    Institute,
    InventoryItem,
    Laboratory,
    Project,
    Sample,
    StaffMember,
    UserRole,
    WorkflowEvent,
)
from .serializers import (
    AuditLogSerializer,
    ExperimentSerializer,
    InstituteSerializer,
    InventoryItemSerializer,
    LaboratorySerializer,
    ProjectSerializer,
    SampleSerializer,
    StaffMemberSerializer,
    UserRoleSerializer,
)
from .workflows import (
    validate_transition_with_role,
    normalize_role,
)


# ===============================================================
# Utilities
# ===============================================================
def _model_has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _parse_pk(value) -> Optional[str]:
    """
    Parse a primary key passed in query params or headers.

    Supports integer PKs and UUID/string PKs.
    """
    if value is None:
        return None
    v = str(value).strip()
    return v or None


def _apply_default_ordering(qs: QuerySet) -> QuerySet:
    if _model_has_field(qs.model, "created_at"):
        return qs.order_by("-created_at", "-id")
    return qs.order_by("-id")


def _deny_if_payload_has(request, fields: list[str], message: str):
    incoming = getattr(request, "data", {}) or {}
    blocked = [f for f in fields if f in incoming]
    if blocked:
        raise ValidationError({f: message for f in blocked})


def _require_auth(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise NotAuthenticated("Authentication credentials were not provided.")
    return user


# ===============================================================
# Laboratory resolution + Role resolution
# ===============================================================
def resolve_current_laboratory(request) -> Optional[Laboratory]:
    """
    Resolve current laboratory from ?lab=<pk> or X-Laboratory header, and verify
    that the user is permitted to operate in that lab.

    Permission signals supported (in order):
      1) UserRole(user, laboratory) exists (primary / canonical)
      2) StaffMember(user, laboratory) exists (common in LIMS designs)
      3) User is in any Django Group (role encoded via groups in some setups)

    If no lab is provided, and the user has exactly one lab via UserRole,
    return it. Otherwise None.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    lab_id = _parse_pk(request.query_params.get("lab"))
    if lab_id is None:
        lab_id = _parse_pk(request.headers.get("X-Laboratory"))

    if lab_id:
        try:
            lab = Laboratory.objects.select_related("institute").get(
                id=lab_id, is_active=True
            )
        except Laboratory.DoesNotExist:
            return None

        if user.is_superuser:
            return lab

        if UserRole.objects.filter(user=user, laboratory=lab).exists():
            return lab

        # Fallback: StaffMember association
        try:
            if StaffMember.objects.filter(user=user, laboratory=lab).exists():
                return lab
        except Exception:
            pass

        # Fallback: group-based access (role derived later)
        try:
            if user.groups.exists():
                return lab
        except Exception:
            pass

        return None

    labs = list(
        Laboratory.objects.filter(is_active=True, user_roles__user=user).distinct()[:2]
    )
    return labs[0] if len(labs) == 1 else None


def require_laboratory(request) -> Laboratory:
    lab = resolve_current_laboratory(request)
    if not lab:
        raise PermissionDenied(
            "Active laboratory not set or not permitted. Provide ?lab=<id> or X-Laboratory header."
        )
    return lab


def _get_user_role(user, lab: Laboratory) -> str:
    """
    Return a normalized role string for the user in the given lab.

    Role sources (in order):
      1) UserRole(user, laboratory).role (primary)
      2) StaffMember(user, laboratory).role (if such a field exists)
      3) First Django group name (deterministic by name order)

    If none exist, deny.
    """
    if user.is_superuser:
        return "ADMIN"

    # 1) Primary: UserRole
    try:
        role = UserRole.objects.get(user=user, laboratory=lab)
        return normalize_role(role.role)
    except UserRole.DoesNotExist:
        pass

    # 2) StaffMember role field (optional)
    try:
        sm = StaffMember.objects.get(user=user, laboratory=lab)
        if getattr(sm, "role", None):
            return normalize_role(getattr(sm, "role"))
    except Exception:
        pass

    # 3) Group name
    try:
        if user.groups.exists():
            gname = (
                user.groups.order_by("name").values_list("name", flat=True).first()
            )
            if gname:
                return normalize_role(gname)
    except Exception:
        pass

    raise PermissionDenied("User has no role in this laboratory.")


# ===============================================================
# Lab-scoped queryset mixin
# ===============================================================
class LabScopedQuerysetMixin:
    def get_scoped_queryset(self, base_qs: QuerySet) -> QuerySet:
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return base_qs.none()

        if user.is_superuser:
            return base_qs

        if not _model_has_field(base_qs.model, "laboratory"):
            return base_qs

        lab = resolve_current_laboratory(self.request)
        if not lab:
            return base_qs.none()

        return base_qs.filter(laboratory=lab)


# ===============================================================
# Health
# ===============================================================
class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["System"])
    def get(self, request):
        lab = resolve_current_laboratory(request)
        payload = {"status": "ok", "service": "NARO-LIMS"}
        if lab:
            payload["laboratory"] = {
                "id": lab.id,
                "code": lab.code,
                "name": lab.name,
                "institute": lab.institute.code,
            }
        return Response(payload)


# ===============================================================
# Institutes
# ===============================================================
class InstituteViewSet(viewsets.ModelViewSet):
    queryset = Institute.objects.all().order_by("code", "id")
    serializer_class = InstituteSerializer
    permission_classes = [IsAuthenticated]


# ===============================================================
# Laboratories
# ===============================================================
class LaboratoryViewSet(viewsets.ModelViewSet):
    queryset = Laboratory.objects.select_related("institute").all().order_by(
        "institute__code", "code", "id"
    )
    serializer_class = LaboratorySerializer
    permission_classes = [IsAuthenticated]


# ===============================================================
# Staff
# ===============================================================
class StaffMemberViewSet(viewsets.ModelViewSet):
    serializer_class = StaffMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        qs = StaffMember.objects.select_related("institute", "laboratory", "user")

        if not user or not user.is_authenticated:
            return qs.none()

        if user.is_superuser:
            return qs.order_by("full_name", "id")

        user_labs = Laboratory.objects.filter(
            is_active=True, user_roles__user=user
        ).distinct()
        if not user_labs.exists():
            # Fallback: StaffMember based membership
            user_labs = Laboratory.objects.filter(
                is_active=True, staffmember__user=user
            ).distinct()

        if not user_labs.exists():
            return qs.none()

        institutes = user_labs.values_list("institute_id", flat=True)

        return qs.filter(
            Q(laboratory__in=user_labs)
            | Q(laboratory__isnull=True, institute_id__in=institutes)
        ).order_by("full_name", "id")

    def update(self, request, *args, **kwargs):
        if "institute" in (request.data or {}) or "laboratory" in (request.data or {}):
            raise PermissionDenied(
                "Institute or laboratory cannot be changed once created."
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if "institute" in (request.data or {}) or "laboratory" in (request.data or {}):
            raise PermissionDenied(
                "Institute or laboratory cannot be changed once created."
            )
        return super().partial_update(request, *args, **kwargs)


# ===============================================================
# Projects
# ===============================================================
class ProjectViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(self.get_scoped_queryset(super().get_queryset()))

    def perform_create(self, serializer):
        lab = require_laboratory(self.request)
        _deny_if_payload_has(
            self.request,
            ["laboratory", "created_by"],
            "This field is server-controlled.",
        )
        serializer.save(created_by=self.request.user, laboratory=lab)

    def perform_update(self, serializer):
        _deny_if_payload_has(
            self.request, ["laboratory", "created_by"], "This field cannot be modified."
        )
        serializer.save()


# ===============================================================
# Samples (canonical lifecycle enforced)
# ===============================================================
class SampleViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Sample.objects.select_related("project").all()
    serializer_class = SampleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(self.get_scoped_queryset(super().get_queryset()))

    def perform_update(self, serializer):
        incoming = self.request.data or {}

        if "status" in incoming:
            lab = require_laboratory(self.request)
            user = _require_auth(self.request)
            role = _get_user_role(user, lab)

            old = (serializer.instance.status or "").strip().upper()
            new = str(incoming["status"]).strip().upper()

            try:
                validate_transition_with_role("sample", old, new, role)
            except ValueError as e:
                raise ValidationError({"status": str(e)})

            WorkflowEvent.objects.create(
                kind="sample",
                object_id=serializer.instance.id,
                from_status=old,
                to_status=new,
                performed_by=user,
                role=role,
                comment=incoming.get("comment", ""),
                laboratory=lab,
            )

        _deny_if_payload_has(
            self.request, ["laboratory", "project"], "This field cannot be modified."
        )
        serializer.save()


# ===============================================================
# Experiments (canonical lifecycle enforced)
# ===============================================================
class ExperimentViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Experiment.objects.select_related("project").all()
    serializer_class = ExperimentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(self.get_scoped_queryset(super().get_queryset()))

    def perform_update(self, serializer):
        incoming = self.request.data or {}

        if "status" in incoming:
            lab = require_laboratory(self.request)
            user = _require_auth(self.request)
            role = _get_user_role(user, lab)

            old = (serializer.instance.status or "").strip().upper()
            new = str(incoming["status"]).strip().upper()

            try:
                validate_transition_with_role("experiment", old, new, role)
            except ValueError as e:
                raise ValidationError({"status": str(e)})

            WorkflowEvent.objects.create(
                kind="experiment",
                object_id=serializer.instance.id,
                from_status=old,
                to_status=new,
                performed_by=user,
                role=role,
                comment=incoming.get("comment", ""),
                laboratory=lab,
            )

        _deny_if_payload_has(
            self.request, ["laboratory", "project"], "This field cannot be modified."
        )
        serializer.save()


# ===============================================================
# Inventory
# ===============================================================
class InventoryItemViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(self.get_scoped_queryset(super().get_queryset()))

    def perform_update(self, serializer):
        _deny_if_payload_has(
            self.request, ["laboratory"], "Laboratory cannot be changed once created."
        )
        serializer.save()


# ===============================================================
# Roles
# ===============================================================
class UserRoleViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = UserRole.objects.select_related("user", "laboratory").all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(self.get_scoped_queryset(super().get_queryset()))

    def perform_update(self, serializer):
        _deny_if_payload_has(
            self.request, ["laboratory"], "Laboratory cannot be changed once created."
        )
        serializer.save()


# ===============================================================
# Audit logs (READ-ONLY)
# ===============================================================
class AuditLogViewSet(LabScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user", "laboratory").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(self.get_scoped_queryset(super().get_queryset()))


# ===============================================================
# HTML DETAIL VIEWS
# ===============================================================
def sample_detail(request, pk: int):
    sample = get_object_or_404(Sample, pk=pk)
    return render(request, "lims_core/samples/detail.html", {"sample": sample})


def experiment_detail(request, pk: int):
    experiment = get_object_or_404(Experiment, pk=pk)
    return render(
        request, "lims_core/experiments/detail.html", {"experiment": experiment}
    )
