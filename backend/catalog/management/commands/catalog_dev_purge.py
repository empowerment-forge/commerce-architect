import uuid

from django.core.management.base import BaseCommand

from catalog.portability.dev_reset import (
    apply_catalog_dev_purge,
    preview_catalog_dev_purge,
)

from ._catalog_operator import (
    CatalogCommandError,
    ensure_enabled,
    parse_operation_id,
    receipt_payload,
    run_command,
    write_json,
)


class Command(BaseCommand):
    help = "Preview or apply the development-only catalog purge."

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--operation-id", type=uuid.UUID)
        parser.add_argument("--expected-catalog-digest")
        parser.add_argument("--confirm-purge")

    def handle(self, *args, **options):
        ensure_enabled()
        organization_id = options["organization"]
        apply_values = (options["operation_id"], options["expected_catalog_digest"], options["confirm_purge"])
        if options["validate_only"]:
            if any(value is not None for value in apply_values):
                raise CatalogCommandError(
                    "apply-only options cannot be used with --validate-only",
                    returncode=2,
                )
            preview = run_command(lambda: preview_catalog_dev_purge(organization_id))
            payload = {"status": "valid" if preview.valid else "invalid", "preview": preview.as_dict()}
            write_json(self, payload)
            if not preview.valid:
                raise CatalogCommandError("purge preview has blockers", returncode=3)
            return
        missing = [
            flag
            for flag, value in (
                ("--operation-id", options["operation_id"]),
                ("--expected-catalog-digest", options["expected_catalog_digest"]),
                ("--confirm-purge", options["confirm_purge"]),
            )
            if value is None
        ]
        if missing:
            raise CatalogCommandError("apply requires " + ", ".join(missing), returncode=2)
        receipt = run_command(
            lambda: apply_catalog_dev_purge(
                organization_id,
                operation_id=parse_operation_id(options["operation_id"]),
                expected_catalog_digest=options["expected_catalog_digest"],
                confirm_purge=options["confirm_purge"],
            )
        )
        write_json(self, {"status": "successful", "receipt": receipt_payload(receipt)})
