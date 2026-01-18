# lims_core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# =============================================================
# Workflow permission matrix & aggregation (read-only)
# =============================================================
from .views_workflow_permissions import WorkflowPermissionMatrixView
from .views_workflow_permission_aggregate import WorkflowPermissionAggregateView

# =============================================================
# Core API ViewSets (CRUD)
# =============================================================
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

# =============================================================
# Public + UI (HTML)
# =============================================================
from .views_ui import (
    landing,
    features,
    feature_detail,
    updates,
    docs_hub,
    home,
    ui_stats,
    ui_logout,
    workflow_widget_demo,
    sample_list,
    sample_detail,
    experiment_detail,
    batch_list,
    batch_create,
    batch_detail,
    sample_bulk_register,
)

# Entry redirect (wizard-first when there are no projects)
from .views_ui_entry import ui_entry

# =============================================================
# Metadata UI (schema-driven)
# =============================================================
from .views_metadata_ui import metadata_form

# =============================================================
# Workflow definitions (legacy-compatible, static)
# =============================================================
from .views_workflows import (
    WorkflowDefinitionView as LegacyWorkflowDefinitionView,
    WorkflowNextStatesView,
)

# =============================================================
# Workflow runtime execution (ENFORCEMENT POINT)
# =============================================================
from .views_workflow_runtime import (
    WorkflowRuntimeView,
    WorkflowTimelineView,
)

# =============================================================
# Role-aware workflow APIs
# =============================================================
from .views_workflow_api import (
    WorkflowAllowedView,
    WorkflowTransitionView,
)

# =============================================================
# Bulk workflow execution
# =============================================================
from .views_workflow_bulk import WorkflowBulkTransitionView

# =============================================================
# Workflow introspection (canonical, read-only)
# =============================================================
from .views_workflow_introspection import (
    WorkflowDefinitionView as CanonicalWorkflowDefinitionView,
    WorkflowAllowedTransitionsView,
    WorkflowHistoryView,
)

# =============================================================
# Workflow metrics
# =============================================================
from .views_workflow_metrics import WorkflowMetricsView

# =============================================================
# SLA dashboards (aggregation, read-only)
# =============================================================
from .views_sla_dashboard import SLADashboardView

# =============================================================
# Identity
# =============================================================
from .views_identity import WhoAmIView


app_name = "lims_core"

# =============================================================
# DRF Router (CRUD APIs only)
# =============================================================
router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"samples", SampleViewSet, basename="sample")
router.register(r"experiments", ExperimentViewSet, basename="experiment")
router.register(r"inventory", InventoryItemViewSet, basename="inventory")
router.register(r"roles", UserRoleViewSet, basename="role")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"staff", StaffMemberViewSet, basename="staff")


urlpatterns = [
    # =========================================================
    # Public pages (no authentication)
    # =========================================================
    path("", landing, name="landing"),
    path("features/", features, name="features"),
    path("features/<slug:slug>/", feature_detail, name="feature-detail"),
    path("updates/", updates, name="updates"),
    path("docs/", docs_hub, name="docs-hub"),

    # =========================================================
    # Wizard (assisted setup)
    # =========================================================
    path("wizard/", include(("lims_core.wizard.urls", "wizard"), namespace="wizard")),

    # =========================================================
    # UI workspace (authenticated)
    # =========================================================
    # Entry point: if no projects exist in user lab scope, redirect to wizard
    path("ui/", ui_entry, name="ui-home"),

    # Actual workspace view (kept intact, but reachable after ui_entry redirect)
    path("ui/workspace/", home, name="ui-workspace"),

    path("ui/stats/", ui_stats, name="ui-stats"),
    path("ui/logout/", ui_logout, name="ui-logout"),
    path("ui/workflow-demo/", workflow_widget_demo, name="workflow-demo"),

    # ---------------- Samples ----------------
    path("ui/samples/", sample_list, name="sample-list-html"),
    path("ui/samples/<int:pk>/", sample_detail, name="sample-detail-html"),

    # ---------------- Experiments ----------------
    path(
        "ui/experiments/<int:pk>/",
        experiment_detail,
        name="experiment-detail-html",
    ),

    # ---------------- Batches ----------------
    path("ui/batches/", batch_list, name="batch-list"),
    path("ui/batches/create/", batch_create, name="batch-create"),
    path("ui/batches/<int:pk>/", batch_detail, name="batch-detail"),
    path(
        "ui/batches/<int:batch_id>/samples/bulk/",
        sample_bulk_register,
        name="sample-bulk-register",
    ),

    # =========================================================
    # Metadata UI (schema-driven)
    # =========================================================
    path(
        "ui/metadata/<str:object_type>/<int:object_id>/",
        metadata_form,
        name="metadata-form",
    ),

    # =========================================================
    # System
    # =========================================================
    path("health/", HealthCheckView.as_view(), name="health-check"),

    # =========================================================
    # Identity
    # =========================================================
    path("whoami/", WhoAmIView.as_view(), name="whoami"),

    # =========================================================
    # Workflow definitions (legacy)
    # =========================================================
    path(
        "workflows/<str:kind>/",
        LegacyWorkflowDefinitionView.as_view(),
        name="workflow-definition",
    ),
    path(
        "workflows/<str:kind>/next/",
        WorkflowNextStatesView.as_view(),
        name="workflow-next-states",
    ),

    # =========================================================
    # Workflow runtime (metadata-gated)
    # =========================================================
    path(
        "workflows/<str:kind>/<int:pk>/",
        WorkflowRuntimeView.as_view(),
        name="workflow-runtime",
    ),
    path(
        "workflows/<str:kind>/<int:pk>/timeline/",
        WorkflowTimelineView.as_view(),
        name="workflow-timeline",
    ),
    path(
        "workflows/<str:kind>/<int:pk>/allowed/",
        WorkflowAllowedView.as_view(),
        name="workflow-allowed",
    ),
    path(
        "workflows/<str:kind>/<int:pk>/transition/",
        WorkflowTransitionView.as_view(),
        name="workflow-transition",
    ),

    # =========================================================
    # Bulk workflow execution
    # =========================================================
    path(
        "workflows/<str:kind>/bulk/",
        WorkflowBulkTransitionView.as_view(),
        name="workflow-bulk-transition",
    ),

    # =========================================================
    # Workflow introspection (canonical)
    # =========================================================
    path(
        "workflows/definition/<str:kind>/",
        CanonicalWorkflowDefinitionView.as_view(),
        name="workflow-definition-canonical",
    ),
    path(
        "workflows/allowed/<str:kind>/<int:object_id>/",
        WorkflowAllowedTransitionsView.as_view(),
        name="workflow-allowed-transitions",
    ),
    path(
        "workflows/history/<str:kind>/<int:object_id>/",
        WorkflowHistoryView.as_view(),
        name="workflow-history",
    ),

    # =========================================================
    # Workflow permissions
    # =========================================================
    path(
        "workflows/permissions/<str:kind>/",
        WorkflowPermissionMatrixView.as_view(),
        name="workflow-permission-matrix",
    ),
    path(
        "workflows/permissions/<str:kind>/aggregate/",
        WorkflowPermissionAggregateView.as_view(),
        name="workflow-permission-aggregate",
    ),

    # =========================================================
    # Workflow metrics
    # =========================================================
    path(
        "workflows/<str:kind>/<int:pk>/metrics/",
        WorkflowMetricsView.as_view(),
        name="workflow-metrics",
    ),

    # =========================================================
    # SLA dashboards (aggregation, read-only)
    # =========================================================
    path(
        "dashboards/sla/",
        SLADashboardView.as_view(),
        name="sla-dashboard",
    ),

    # =========================================================
    # Core CRUD API (router)
    # =========================================================
    path("", include(router.urls)),
]
