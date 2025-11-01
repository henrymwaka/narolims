# lims_core/mixins.py
from .models import AuditLog


class AuditLogMixin:
    """
    Mixin to log create/update/delete actions to AuditLog.
    Never raises if logging fails.
    """

    def _log(self, user, action, details=None):
        try:
            AuditLog.objects.create(
                user=user if (user and user.is_authenticated) else None,
                action=action,
                details=details or {},
            )
        except Exception:
            # Never break the request because of logging issues
            pass

    def perform_create(self, serializer):
        instance = serializer.save()
        self._log(self.request.user, f"CREATE {instance.__class__.__name__}", {"id": getattr(instance, "id", None)})

    def perform_update(self, serializer):
        instance = serializer.save()
        self._log(self.request.user, f"UPDATE {instance.__class__.__name__}", {"id": getattr(instance, "id", None)})

    def perform_destroy(self, instance):
        obj_id = getattr(instance, "id", None)
        super().perform_destroy(instance)
        self._log(self.request.user, f"DELETE {instance.__class__.__name__}", {"id": obj_id})
