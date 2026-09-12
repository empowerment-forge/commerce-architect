from django.core.management.base import BaseCommand

from catalog.portability.exporter import export_catalog
from catalog.services import get_active_organization

from ._catalog_operator import ensure_enabled, run_command, write_json


class Command(BaseCommand):
    help = "Export one Organization's Catalog Portability package."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        ensure_enabled()

        def operation():
            organization = get_active_organization(options["organization"])
            output = export_catalog(organization.pk, options["output"])
            return {"status": "successful", "organization_id": organization.pk, "output": str(output)}

        write_json(self, run_command(operation))
