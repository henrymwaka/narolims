# lims_core/views.py
from rest_framework import viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Project, Sample, Experiment, InventoryItem, UserRole, AuditLog
from .serializers import (
    ProjectSerializer, SampleSerializer, ExperimentSerializer,
    InventoryItemSerializer, UserRoleSerializer, AuditLogSerializer,
)

# ---- Optional imports (fallbacks keep things working if files aren't present) ----
try:
    from .filters import ProjectFilter, SampleFilter, ExperimentFilter, InventoryItemFilter
    _HAVE_FILTERSETS = True
except Exception:
    ProjectFilter = SampleFilter = ExperimentFilter = InventoryItemFilter = None
    _HAVE_FILTERSETS = False

try:
    from .permissions import IsRoleAllowedOrReadOnly  # RBAC-lite
    BaseWritePermission = IsRoleAllowedOrReadOnly
except Exception:
    BaseWritePermission = IsAuthenticated  # fallback: authenticated users can write

try:
    from .mixins import AuditLogMixin  # logs create/update/delete
except Exception:
    class AuditLogMixin:  # no-op fallback
        pass


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        operation_id="health_check",
        summary="Service health",
        description="Returns a simple status payload to indicate the API is running.",
        responses={200: dict},
        tags=["System"],
    )
    def get(self, request):
        return Response({"status": "ok", "message": "NARO-LIMS is running"})


# ---------------------- Projects ----------------------
@extend_schema_view(
    list=extend_schema(tags=["Projects"]),
    retrieve=extend_schema(tags=["Projects"]),
    create=extend_schema(tags=["Projects"]),
    update=extend_schema(tags=["Projects"]),
    partial_update=extend_schema(tags=["Projects"]),
    destroy=extend_schema(tags=["Projects"]),
)
class ProjectViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [BaseWritePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Prefer dedicated FilterSet if available; else fall back to basic field list
    if _HAVE_FILTERSETS:
        filterset_class = ProjectFilter
    else:
        filterset_fields = ["start_date", "end_date", "created_by"]

    search_fields = ["name", "description", "created_by__username"]
    ordering_fields = ["name", "start_date", "end_date", "id"]
    ordering = ["-id"]

    def perform_create(self, serializer):
        # Set creator automatically
        serializer.save(created_by=self.request.user)


# ---------------------- Samples ----------------------
@extend_schema_view(
    list=extend_schema(tags=["Samples"]),
    retrieve=extend_schema(tags=["Samples"]),
    create=extend_schema(tags=["Samples"]),
    update=extend_schema(tags=["Samples"]),
    partial_update=extend_schema(tags=["Samples"]),
    destroy=extend_schema(tags=["Samples"]),
)
class SampleViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = Sample.objects.select_related("project").all()
    serializer_class = SampleSerializer
    permission_classes = [BaseWritePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    if _HAVE_FILTERSETS:
        filterset_class = SampleFilter
    else:
        filterset_fields = ["project", "sample_type", "collected_on", "storage_location"]

    search_fields = ["sample_id", "collected_by", "storage_location", "project__name", "sample_type"]
    ordering_fields = ["id", "collected_on", "sample_id"]
    ordering = ["-id"]


# ---------------------- Experiments ----------------------
@extend_schema_view(
    list=extend_schema(tags=["Experiments"]),
    retrieve=extend_schema(tags=["Experiments"]),
    create=extend_schema(tags=["Experiments"]),
    update=extend_schema(tags=["Experiments"]),
    partial_update=extend_schema(tags=["Experiments"]),
    destroy=extend_schema(tags=["Experiments"]),
)
class ExperimentViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = Experiment.objects.select_related("project").prefetch_related("samples").all()
    serializer_class = ExperimentSerializer
    permission_classes = [BaseWritePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    if _HAVE_FILTERSETS:
        filterset_class = ExperimentFilter
    else:
        filterset_fields = ["project", "start_date", "end_date"]

    search_fields = ["name", "protocol_reference", "project__name", "samples__sample_id"]
    ordering_fields = ["id", "start_date", "end_date", "name"]
    ordering = ["-id"]


# ---------------------- Inventory ----------------------
@extend_schema_view(
    list=extend_schema(tags=["Inventory"]),
    retrieve=extend_schema(tags=["Inventory"]),
    create=extend_schema(tags=["Inventory"]),
    update=extend_schema(tags=["Inventory"]),
    partial_update=extend_schema(tags=["Inventory"]),
    destroy=extend_schema(tags=["Inventory"]),
)
class InventoryItemViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = InventoryItem.objects.all()
    serializer_class = InventoryItemSerializer
    permission_classes = [BaseWritePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    if _HAVE_FILTERSETS:
        filterset_class = InventoryItemFilter
    else:
        filterset_fields = ["category", "expiry_date", "location", "supplier"]

    search_fields = ["name", "location", "supplier", "category"]
    ordering_fields = ["name", "expiry_date", "quantity", "id"]
    ordering = ["name"]


# ---------------------- User Roles ----------------------
@extend_schema_view(
    list=extend_schema(tags=["Roles"]),
    retrieve=extend_schema(tags=["Roles"]),
    create=extend_schema(tags=["Roles"]),
    update=extend_schema(tags=["Roles"]),
    partial_update=extend_schema(tags=["Roles"]),
    destroy=extend_schema(tags=["Roles"]),
)
class UserRoleViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = UserRole.objects.select_related("user").all()
    serializer_class = UserRoleSerializer
    permission_classes = [BaseWritePermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Keep filters conservative to avoid field-name drift issues
    filterset_fields = ["user", "role"]
    search_fields = ["user__username", "role"]
    ordering_fields = ["user", "role", "id"]
    ordering = ["user", "role"]


# ---------------------- Audit Log (read-only) ----------------------
@extend_schema_view(
    list=extend_schema(tags=["Audit"]),
    retrieve=extend_schema(tags=["Audit"]),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("user").all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # Avoid referencing possibly refactored timestamp field in filters;
    # rely on ID ordering by default. Serializer normalizes timestamp output.
    filterset_fields = ["user", "action"]
    search_fields = ["action", "user__username"]
    ordering_fields = ["id", "action"]
    ordering = ["-id"]
