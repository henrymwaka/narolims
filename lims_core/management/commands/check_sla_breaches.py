from django.core.management.base import BaseCommand
from lims_core.models import WorkflowTransition
from lims_core.workflows.sla_monitor import check_sla_breach


class Command(BaseCommand):
    help = "Check SLA breaches for active workflow states"

    def handle(self, *args, **options):
        seen = set()

        for t in WorkflowTransition.objects.order_by("kind", "object_id", "-created_at"):
            key = (t.kind, t.object_id)
            if key in seen:
                continue
            seen.add(key)
            check_sla_breach(t.kind, t.object_id)
