# lims_core/views.py
from __future__ import annotations

from typing import Optional

from django.db.models import QuerySet, Q
from django.core.exceptions import FieldDoesNotExist

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError

from drf_spectacular.utils import extend_schema

from .models import (
    Institute,
    Laboratory,
    StaffMember,
    Project,
    Sample,
    Experiment,
    InventoryItem,
    UserRole,
    AuditLog,
)

from .serializers import (
    InstituteSerializer,
    LaboratorySerializer,
    StaffMemberSerializer,
    ProjectSerializer,
    SampleSerializer,
    ExperimentSerializer,
    InventoryItemSerializer,
    UserRoleSerializer,
    AuditLogSerializer,
)

from .workflows import validate_transition

# Permissions
try:
    from .permissions import IsRoleAllowedOrReadOnly
    BaseWritePermission = IsRoleAllowedOrReadOnly
except Exception:
    BaseWritePermission = IsAuthenticated

from .mixins import AuditLogMixin


# ===============================================================
# Utilities
# ===============================================================
def _model_has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except FieldDoesNotExist:
        return False


def _parse_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _apply_default_ordering(qs: QuerySet) -> QuerySet:
    if _model_has_field(qs.model, "created_at"):
        return qs.order_by("-created_at", "-id")
    return qs.order_by("-id")


def _deny_if_payload_has(request, fields: list[str], message: str):
    incoming = getattr(request, "data", {}) or {}
    present = [f for f in fields if f in incoming]
    if present:
        raise ValidationError({f: message for f in present})


# ===============================================================
# Laboratory resolution
# ===============================================================
def resolve_current_laboratory(request) -> Optional[Laboratory]:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    lab_id = _parse_int(request.query_params.get("lab"))
    if lab_id is None:
        lab_id = _parse_int(request.headers.get("X-Laboratory"))

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

        return None

    labs = list(
        Laboratory.objects.filter(
            is_active=True,
            user_roles__user=user,
        ).distinct()[:2]
    )

    if len(labs) == 1:
        return labs[0]

    return None


def require_laboratory(request) -> Laboratory:
    lab = resolve_current_laboratory(request)
    if not lab:
        raise PermissionDenied(
            "Active laboratory not set or not permitted. "
            "Provide ?lab=<id> or X-Laboratory header."
        )
    return lab


# ===============================================================
# Lab-scoped queryset mixin (READ ONLY)
# ===============================================================
class LabScopedQuerysetMixin:
    def get_scoped_queryset(self, base_qs: QuerySet) -> QuerySet:
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return base_qs.none()

        model = base_qs.model
        if not _model_has_field(model, "laboratory"):
            return base_qs

        if user.is_superuser:
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
    permission_classes = [BaseWritePermission]


# ===============================================================
# Laboratories
# ===============================================================
class LaboratoryViewSet(viewsets.ModelViewSet):
    queryset = Laboratory.objects.select_related("institute").all().order_by(
        "institute__code", "code", "id"
    )
    serializer_class = LaboratorySerializer
    permission_classes = [BaseWritePermission]


# ===============================================================
# Staff
# ===============================================================
class StaffMemberViewSet(viewsets.ModelViewSet):
    serializer_class = StaffMemberSerializer
    permission_classes = [BaseWritePermission]

    def get_queryset(self):
        user = self.request.user
        qs = StaffMember.objects.select_related("institute", "laboratory", "user")

        if not user or not user.is_authenticated:
            return qs.none()

        if user.is_superuser:
            return qs.order_by("full_name", "id")

        user_labs = Laboratory.objects.filter(
            is_active=True,
            user_roles__user=user,
        ).distinct()

        if not user_labs.exists():
            return qs.none()

        institutes = user_labs.values_list("institute_id", flat=True)

        return qs.filter(
            Q(laboratory__in=user_labs)
            | Q(laboratory__isnull=True, institute_id__in=institutes)
        ).order_by("full_name", "id")

    def perform_update(self, serializer):
        incoming = getattr(self.request, "data", {}) or {}
        if "institute" in incoming or "laboratory" in incoming:
            raise PermissionDenied(
                "Institute or laboratory cannot be changed once created."
            )
        serializer.save()


# ===============================================================
# Projects
# ===============================================================
class ProjectViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [BaseWritePermission]

    def get_queryset(self):
        return _apply_default_ordering(
            self.get_scoped_queryset(super().get_queryset())
        )

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
            self.request,
            ["laboratory", "created_by"],
            "This field cannot be modified.",
        )
        serializer.save()


# ===============================================================
# Samples
# ===============================================================
class SampleViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Sample.objects.select_related("project").all()
    serializer_class = SampleSerializer
    permission_classes = [BaseWritePermission]

    def get_queryset(self):
        return _apply_default_ordering(
            self.get_scoped_queryset(super().get_queryset())
        )

    def perform_update(self, serializer):
        incoming = getattr(self.request, "data", {}) or {}

        # Enforce workflow transitions for status updates (12A)
        if "status" in incoming:
            current = (serializer.instance.status or "").strip().upper()
            target = str(incoming["status"]).strip().upper()
            try:
                validate_transition("sample", current, target)
            except ValueError as e:
                raise ValidationError({"status": str(e)})

        _deny_if_payload_has(
            self.request,
            ["laboratory", "project"],
            "This field cannot be modified.",
        )
        serializer.save()


# ===============================================================
# Experiments
# ===============================================================
class ExperimentViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Experiment.objects.select_related("project").all()
    serializer_class = ExperimentSerializer
    permission_classes = [BaseWritePermission]

    def get_queryset(self):
        return _apply_default_ordering(
            self.get_scoped_queryset(super().get_queryset())
        )

    def perform_update(self, serializer):
        incoming = getattr(self.request, "data", {}) or {}

        # Enforce workflow transitions for status updates (12A)
        if "status" in incoming:
            current = (serializer.instance.status or "").strip().upper()
            target = str(incoming["status"]).strip().upper()
            try:
                validate_transition("experiment", current, target)
            except ValueError as e:
                raise ValidationError({"status": str(e)})

        _deny_if_payload_has(
            self.request,
            ["laboratory", "project"],
            "This field cannot be modified.",
        )
        serializer.save()


# ===============================================================
# Inventory
# ===============================================================
class InventoryItemViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [BaseWritePermission]

    def get_queryset(self):
        return _apply_default_ordering(
            self.get_scoped_queryset(super().get_queryset())
        )

    def perform_update(self, serializer):
        _deny_if_payload_has(
            self.request,
            ["laboratory"],
            "Laboratory cannot be changed once created.",
        )
        serializer.save()


# ===============================================================
# Roles
# ===============================================================
class UserRoleViewSet(LabScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = UserRole.objects.select_related("user", "laboratory").all()
    serializer_class = UserRoleSerializer
    permission_classes = [BaseWritePermission]

    def get_queryset(self):
        return _apply_default_ordering(
            self.get_scoped_queryset(super().get_queryset())
        )

    def perform_update(self, serializer):
        _deny_if_payload_has(
            self.request,
            ["laboratory"],
            "Laboratory cannot be changed once created.",
        )
        serializer.save()


# ===============================================================
# Audit logs
# ===============================================================
class AuditLogViewSet(LabScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user", "laboratory").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return _apply_default_ordering(
            self.get_scoped_queryset(super().get_queryset())
        )
