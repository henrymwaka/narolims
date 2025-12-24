# lims_core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# -----------------------------------------------------------
# Core CRUD ViewSets
# -----------------------------------------------------------
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

# -----------------------------------------------------------
# HTML detail pages (workflow embedded)
# -----------------------------------------------------------
from .views_ui import (
    workflow_widget_demo,
    sample_detail,
    experiment_detail,
)

# -----------------------------------------------------------
# Workflow metadata (static definitions)
# -----------------------------------------------------------
from .views_workflows import (
    WorkflowDefinitionView,
    WorkflowNextStatesView,
)

# -----------------------------------------------------------
# Workflow runtime (authoritative executor-backed)
# -----------------------------------------------------------
from .views_workflow_runtime import (
    WorkflowRuntimeView,
    WorkflowTimelineView,
)

# -----------------------------------------------------------
# Phase 7 – Role-aware workflow APIs
# -----------------------------------------------------------
from .views_workflow_api import (
    WorkflowAllowedView,
    WorkflowTransitionView,
)

# -----------------------------------------------------------
# Phase 9 – Bulk workflow execution
# -----------------------------------------------------------
from .views_workflow_bulk import (
    WorkflowBulkTransitionView,
)

# -----------------------------------------------------------
# Phase 11.6 – Workflow metrics (time-in-state, SLA)
# -----------------------------------------------------------
from .views_workflow_metrics import (
    WorkflowMetricsView,
)

# -----------------------------------------------------------
# Identity
# -----------------------------------------------------------
from .views_identity import WhoAmIView


app_name = "lims_core"


# ===============================================================
# Routers (CRUD APIs)
# ===============================================================
router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"samples", SampleViewSet, basename="sample")
router.register(r"experiments", ExperimentViewSet, basename="experiment")
router.register(r"inventory", InventoryItemViewSet, basename="inventory")
router.register(r"roles", UserRoleViewSet, basename="role")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")
router.register(r"staff", StaffMemberViewSet, basename="staff")


# ===============================================================
# URL patterns
# ===============================================================
urlpatterns = [

    # -----------------------------------------------------------
    # UI demos (HTML, browser-facing)
    # -----------------------------------------------------------
    path(
        "ui/workflow-demo/",
        workflow_widget_demo,
        name="workflow-demo",
    ),

    # -----------------------------------------------------------
    # HTML detail pages (workflow widget embedded)
    # -----------------------------------------------------------
    path(
        "samples/<int:pk>/",
        sample_detail,
        name="sample-detail",
    ),
    path(
        "experiments/<int:pk>/",
        experiment_detail,
        name="experiment-detail",
    ),

    # -----------------------------------------------------------
    # Identity / session context
    # -----------------------------------------------------------
    path(
        "whoami/",
        WhoAmIView.as_view(),
        name="whoami",
    ),

    # -----------------------------------------------------------
    # System
    # -----------------------------------------------------------
    path(
        "health/",
        HealthCheckView.as_view(),
        name="health_check",
    ),

    # -----------------------------------------------------------
    # Workflow definitions (static metadata)
    # -----------------------------------------------------------
    path(
        "workflows/<str:kind>/",
        WorkflowDefinitionView.as_view(),
        name="workflow-definition",
    ),
    path(
        "workflows/<str:kind>/next/",
        WorkflowNextStatesView.as_view(),
        name="workflow-next-states",
    ),

    # -----------------------------------------------------------
    # Workflow runtime (single-object state machine)
    # -----------------------------------------------------------
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

    # -----------------------------------------------------------
    # Phase 7 – Role-aware workflow APIs
    # -----------------------------------------------------------
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

    # -----------------------------------------------------------
    # Phase 9 – Bulk workflow transitions
    # -----------------------------------------------------------
    path(
        "workflows/<str:kind>/bulk/",
        WorkflowBulkTransitionView.as_view(),
        name="workflow-bulk-transition",
    ),

    # -----------------------------------------------------------
    # Phase 11.6 – Workflow metrics (time-in-state)
    # -----------------------------------------------------------
    path(
        "workflows/<str:kind>/<int:pk>/metrics/",
        WorkflowMetricsView.as_view(),
        name="workflow-metrics",
    ),

    # -----------------------------------------------------------
    # Core CRUD API
    # -----------------------------------------------------------
    path("", include(router.urls)),
]
