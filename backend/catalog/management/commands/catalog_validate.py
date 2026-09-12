from django.core.management.base import BaseCommand

from catalog.portability.planner import plan_catalog_import

from ._catalog_operator import (
    bounded_plan_payload,
    ensure_enabled,
    read_bounded_input,
    run_command,
    write_json,
    CatalogCommandError,
)


class Command(BaseCommand):
    help = "Validate a Catalog Portability package without mutating the database."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--input", required=True)
        parser.add_argument("--mode", required=True, choices=("merge", "replace-storefront"))
        parser.add_argument("--inventory", choices=("preserve", "restore-snapshot"), default="preserve")

    def handle(self, *args, **options):
        ensure_enabled()
        package = read_bounded_input(options["input"])
        plan = run_command(
            lambda: plan_catalog_import(
                package,
                options["organization"],
                mode=options["mode"],
                inventory_policy=options["inventory"],
            )
        )
        payload = {"status": "valid" if plan.valid else "invalid", "plan": bounded_plan_payload(plan)}
        write_json(self, payload)
        if not plan.valid:
            raise CatalogCommandError("catalog validation failed", returncode=2)
