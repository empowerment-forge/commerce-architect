import uuid

from django.core.management.base import BaseCommand

from catalog.portability.reset import apply_storefront_reset, preview_storefront_reset

from ._catalog_operator import (
    ensure_enabled,
    parse_operation_id,
    receipt_payload,
    run_command,
    write_json,
)


class Command(BaseCommand):
    help = "Preview or apply a non-destructive storefront reset."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--operation-id", type=uuid.UUID)
        parser.add_argument("--expected-catalog-digest")
        parser.add_argument("--confirm-organization", type=int)

    def handle(self, *args, **options):
        ensure_enabled()
        if options["validate_only"]:
            if any(options[name] is not None for name in ("operation_id", "expected_catalog_digest", "confirm_organization")):
                raise self.error("apply-only options cannot be used with --validate-only")
            preview = run_command(lambda: preview_storefront_reset(options["organization"]))
            write_json(self, {"status": "valid", "preview": preview.as_dict()})
            return
        missing = [
            flag
            for flag, key in (
                ("--operation-id", "operation_id"),
                ("--expected-catalog-digest", "expected_catalog_digest"),
                ("--confirm-organization", "confirm_organization"),
            )
            if options[key] is None
        ]
        if missing:
            raise self.error("apply requires " + ", ".join(missing))
        operation_id = parse_operation_id(options["operation_id"])
        receipt = run_command(
            lambda: apply_storefront_reset(
                options["organization"],
                operation_id=operation_id,
                expected_catalog_digest=options["expected_catalog_digest"],
                confirmed_organization_id=options["confirm_organization"],
            )
        )
        write_json(self, {"status": "successful", "receipt": receipt_payload(receipt)})

    def error(self, message):
        from ._catalog_operator import CatalogCommandError

        raise CatalogCommandError(message, returncode=2)
