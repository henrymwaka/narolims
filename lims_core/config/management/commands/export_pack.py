import json
from django.core.management.base import BaseCommand, CommandError

from lims_core.config.models import ConfigPack
from lims_core.config.pack_io import pack_to_dict


class Command(BaseCommand):
    help = "Export a ConfigPack to JSON."

    def add_arguments(self, parser):
        parser.add_argument("code", type=str)
        parser.add_argument("--out", type=str, default="")

    def handle(self, *args, **options):
        code = options["code"]
        out = options["out"]

        try:
            pack = ConfigPack.objects.get(code=code)
        except ConfigPack.DoesNotExist as exc:
            raise CommandError(f"Pack not found: {code}") from exc

        payload = pack_to_dict(pack)
        text = json.dumps(payload, indent=2, sort_keys=True)

        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(text + "\n")
            self.stdout.write(self.style.SUCCESS(f"Exported {code} -> {out}"))
        else:
            self.stdout.write(text)
