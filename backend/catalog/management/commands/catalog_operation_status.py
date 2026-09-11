import uuid

from django.core.management.base import BaseCommand

from catalog.models import CatalogOperationReceipt

from ._catalog_operator import (
    ensure_enabled,
    existing_organization,
    parse_operation_id,
    receipt_payload,
    run_command,
    write_json,
)


class Command(BaseCommand):
    help = "Read the durable successful receipt for one catalog operation."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--operation-id", required=True, type=uuid.UUID)

    def handle(self, *args, **options):
        ensure_enabled()
        operation_id = parse_operation_id(options["operation_id"])

        def operation():
            organization = existing_organization(options["organization"])
            receipt = CatalogOperationReceipt.objects.filter(
                operation_id=operation_id,
                organization_id=organization.pk,
            ).first()
            if receipt is None:
                return {
                    "status": "not_recorded",
                    "organization_id": organization.pk,
                    "operation_id": str(operation_id),
                }
            return {"receipt": receipt_payload(receipt)}

        write_json(self, run_command(operation))
