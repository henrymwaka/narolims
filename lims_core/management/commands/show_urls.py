from django.core.management.base import BaseCommand
from django.urls import get_resolver


class Command(BaseCommand):
    help = "Print URL patterns. Optional: --contains <text>"

    def add_arguments(self, parser):
        parser.add_argument("--contains", default="", help="Filter URLs containing this text")

    def handle(self, *args, **options):
        needle = (options["contains"] or "").strip()

        def walk(patterns, prefix=""):
            for p in patterns:
                if hasattr(p, "url_patterns"):
                    walk(p.url_patterns, prefix + str(p.pattern))
                else:
                    full = prefix + str(p.pattern)
                    if not needle or needle in full:
                        self.stdout.write(f"{full}\tname={p.name}")

        walk(get_resolver().url_patterns)
