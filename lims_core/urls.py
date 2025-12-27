# lims_core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# -------------------------------------------------
# Permission matrix & aggregation (read-only, lab-scoped)
# -------------------------------------------------
from .views_workflow_permissions import WorkflowPermissionMatrixView
from .views_workflow_permission_aggregate import WorkflowPermissionAggregateView

# -------------------------------------------------
# Core API ViewSets
# -------------------------------------------------
from .views import (
    HealthCheckView,
    ProjectViewSet,
    SampleViewSet,
    ExperimentViewSet,
    InventoryItemViewSet,
    UserRoleViewSet,
    AuditLogViewSet,
    StaffMemberViewSet,
)

# -------------------------------------------------
# UI / HTML Views
# -------------------------------------------------
from .views_ui import (
    landing,
    home,
    ui_stats,
    ui_logout,
    workflow_widget_demo,
    sample_list,
    sample_detail,
    experiment_detail,
)

# -------------------------------------------------
# Workflow definitions (static metadata)
# -------------------------------------------------
from .views_workflows import (
    WorkflowDefinitionView,
    WorkflowNextStatesView,
)

# -------------------------------------------------
# Workflow runtime (single-object execution)
# -------------------------------------------------
from .views_workflow_runtime import (
    WorkflowRuntimeView,
    WorkflowTimelineView,
)

# -------------------------------------------------
# Role-aware workflow APIs
# -------------------------------------------------
from .views_workflow_api import (
    WorkflowAllowedView,
    WorkflowTransitionView,
)

# -------------------------------------------------
# Bulk workflow execution
# -------------------------------------------------
from .views_workflow_bulk import (
    WorkflowBulkTransitionView,
)

# -------------------------------------------------
# Workflow introspection (canonical, read-only)
# -------------------------------------------------
from .views_workflow_introspection import (
    WorkflowDefinitionView as CanonicalWorkflowDefinitionView,
    WorkflowAllowedTransitionsView,
    WorkflowHistoryView,
)

# -------------------------------------------------
# Workflow metrics
# -------------------------------------------------
from .views_workflow_metrics import (
    WorkflowMetricsView,
)

# -------------------------------------------------
# Identity
# -------------------------------------------------
from .views_identity import WhoAmIView


app_name = "lims_core"

# -------------------------------------------------
# Router (CRUD APIs)
# -------------------------------------------------
router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"samples", SampleViewSet, basename="sample")
router.register(r"experiments", ExperimentViewSet, basename="experiment")
router.register(r"inventory", InventoryItemViewSet, basename="inventory")
router.register(r"roles", UserRoleViewSet, basename="role")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"staff", StaffMemberViewSet, basename="staff")


urlpatterns = [
    # ============================================================
    # Public landing (replaces DRF api-root at /lims/)
    # ============================================================
    path("", landing, name="landing"),

    # ============================================================
    # Core CRUD API
    # ============================================================
    path("", include(router.urls)),

    # ============================================================
    # System
    # ============================================================
    path("health/", HealthCheckView.as_view(), name="health_check"),

    # ============================================================
    # Identity
    # ============================================================
    path("whoami/", WhoAmIView.as_view(), name="whoami"),

    # ============================================================
    # Workflow definitions (legacy-compatible)
    # ============================================================
    path("workflows/<str:kind>/", WorkflowDefinitionView.as_view(), name="workflow-definition"),
    path("workflows/<str:kind>/next/", WorkflowNextStatesView.as_view(), name="workflow-next-states"),

    # ============================================================
    # Workflow runtime (single-object)
    # ============================================================
    path("workflows/<str:kind>/<int:pk>/", WorkflowRuntimeView.as_view(), name="workflow-runtime"),
    path("workflows/<str:kind>/<int:pk>/timeline/", WorkflowTimelineView.as_view(), name="workflow-timeline"),

    # ============================================================
    # Role-aware workflow APIs
    # ============================================================
    path("workflows/<str:kind>/<int:pk>/allowed/", WorkflowAllowedView.as_view(), name="workflow-allowed"),
    path("workflows/<str:kind>/<int:pk>/transition/", WorkflowTransitionView.as_view(), name="workflow-transition"),

    # ============================================================
    # Bulk workflow transitions
    # ============================================================
    path("workflows/<str:kind>/bulk/", WorkflowBulkTransitionView.as_view(), name="workflow-bulk-transition"),

    # ============================================================
    # Workflow introspection (canonical, read-only)
    # ============================================================
    path("workflows/definition/<str:kind>/", CanonicalWorkflowDefinitionView.as_view(), name="workflow-definition-canonical"),
    path("workflows/allowed/<str:kind>/<int:object_id>/", WorkflowAllowedTransitionsView.as_view(), name="workflow-allowed-transitions"),
    path("workflows/history/<str:kind>/<int:object_id>/", WorkflowHistoryView.as_view(), name="workflow-history"),

    # ============================================================
    # Workflow permission matrix (per-object)
    # ============================================================
    path("workflows/permissions/<str:kind>/", WorkflowPermissionMatrixView.as_view(), name="workflow-permission-matrix"),

    # ============================================================
    # Workflow permission aggregation (multi-object)
    # ============================================================
    path("workflows/permissions/<str:kind>/aggregate/", WorkflowPermissionAggregateView.as_view(), name="workflow-permission-aggregate"),

    # ============================================================
    # Workflow metrics
    # ============================================================
    path("workflows/<str:kind>/<int:pk>/metrics/", WorkflowMetricsView.as_view(), name="workflow-metrics"),

    # ============================================================
    # UI / HTML pages (authenticated workspace)
    # ============================================================
    path("ui/", home, name="ui-home"),
    path("ui/stats/", ui_stats, name="ui-stats"),
    path("ui/logout/", ui_logout, name="ui-logout"),
    path("ui/workflow-demo/", workflow_widget_demo, name="workflow-demo"),
    path("ui/samples/", sample_list, name="sample-list-html"),
    path("ui/samples/<int:pk>/", sample_detail, name="sample-detail-html"),
    path("ui/experiments/<int:pk>/", experiment_detail, name="experiment-detail-html"),
]
