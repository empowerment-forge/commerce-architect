import uuid

from django.core.management.base import BaseCommand

from catalog.portability.importer import apply_catalog_import

from ._catalog_operator import (
    ensure_enabled,
    parse_operation_id,
    receipt_payload,
    read_bounded_input,
    run_command,
    write_json,
)


class Command(BaseCommand):
    help = "Apply a validated Catalog Portability package atomically."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--input", required=True)
        parser.add_argument("--mode", required=True, choices=("merge", "replace-storefront"))
        parser.add_argument("--inventory", choices=("preserve", "restore-snapshot"), default="preserve")
        parser.add_argument("--operation-id", required=True, type=uuid.UUID)
        parser.add_argument("--expected-catalog-digest", required=True)
        parser.add_argument("--confirm-package-sha256", required=True)
        parser.add_argument("--confirm-organization", type=int)

    def handle(self, *args, **options):
        ensure_enabled()
        package = read_bounded_input(options["input"])
        operation_id = parse_operation_id(options["operation_id"])
        receipt = run_command(
            lambda: apply_catalog_import(
                package,
                options["organization"],
                mode=options["mode"],
                inventory_policy=options["inventory"],
                operation_id=operation_id,
                expected_package_sha256=options["confirm_package_sha256"],
                expected_catalog_digest=options["expected_catalog_digest"],
                confirmed_organization_id=options["confirm_organization"],
            )
        )
        write_json(self, {"status": "successful", "receipt": receipt_payload(receipt)})
