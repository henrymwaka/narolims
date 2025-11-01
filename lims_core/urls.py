from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HealthCheckView,
    ProjectViewSet, SampleViewSet, ExperimentViewSet,
    InventoryItemViewSet, UserRoleViewSet, AuditLogViewSet,
)

app_name = "lims_core"

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"samples", SampleViewSet, basename="sample")
router.register(r"experiments", ExperimentViewSet, basename="experiment")
router.register(r"inventory", InventoryItemViewSet, basename="inventory")
router.register(r"roles", UserRoleViewSet, basename="role")
router.register(r"audit-logs", AuditLogViewSet, basename="auditlog")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health_check"),
    path("", include(router.urls)),
]
