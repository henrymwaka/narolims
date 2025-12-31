# lims_core/management/commands/check_metadata_renderers.py

from django.core.management.base import BaseCommand, CommandError
from django.template.loader import get_template

from lims_core.metadata.models import MetadataField
from lims_core.metadata.renderers import get_field_renderer
from lims_core.metadata.renderer_contract import validate_renderer_contract


class Command(BaseCommand):
    help = "Validate metadata field renderers and their declared contracts"

    def handle(self, *args, **options):
        self.stdout.write("Checking metadata renderer coverage and contracts…\n")

        field_types = (
            MetadataField.objects
            .values_list("field_type", flat=True)
            .distinct()
        )

        errors_found = False

        for field_type in sorted(field_types):
            renderer = get_field_renderer(field_type)

            # Step 1: template existence
            try:
                get_template(renderer)
            except Exception as exc:
                self.stderr.write(
                    f"[ERROR] field_type='{field_type}' → renderer='{renderer}' not loadable\n"
                    f"        {exc}"
                )
                errors_found = True
                continue

            # Step 2: contract validation
            contract_errors = validate_renderer_contract(renderer)
            if contract_errors:
                self.stderr.write(
                    f"[ERROR] field_type='{field_type}' → renderer='{renderer}'"
                )
                for err in contract_errors:
                    self.stderr.write(f"        {err}")
                errors_found = True
            else:
                self.stdout.write(
                    f"[OK] field_type='{field_type}' → {renderer}"
                )

        if errors_found:
            self.stderr.write("\nRenderer validation FAILED.")
            raise CommandError("One or more metadata renderers are invalid.")

        self.stdout.write("\nAll metadata renderers validated successfully.")
