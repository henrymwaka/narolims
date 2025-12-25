from django.core.exceptions import PermissionDenied
from django.db import models


class WorkflowWriteGuardMixin(models.Model):
    """
    Prevents direct modification of workflow-controlled fields
    outside the workflow engine.

    Models inheriting this mixin must be transitioned via
    execute_transition(), never via save() or serializer writes.
    """

    WORKFLOW_FIELD = "status"

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None and self.WORKFLOW_FIELD:
            old = (
                self.__class__.objects.filter(pk=self.pk)
                .values_list(self.WORKFLOW_FIELD, flat=True)
                .first()
            )
            new = getattr(self, self.WORKFLOW_FIELD, None)

            if old != new:
                raise PermissionDenied(
                    f"Direct modification of '{self.WORKFLOW_FIELD}' is forbidden. "
                    "Use workflow transition APIs."
                )

        return super().save(*args, **kwargs)
