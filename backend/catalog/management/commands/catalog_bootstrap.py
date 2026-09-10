import json

from django.core.management.base import BaseCommand, CommandError

from catalog.bootstrap import (
    BootstrapValidationError,
    apply_mapping,
    load_mapping,
    validate_mapping,
)


class Command(BaseCommand):
    help = "Validate or apply a reviewed Product catalog bootstrap mapping."

    def add_arguments(self, parser):
        parser.add_argument("--mapping", required=True)
        parser.add_argument("--organization", required=True, type=int)
        parser.add_argument("--validate-only", action="store_true")
        parser.add_argument("--fingerprint")

    def handle(self, *args, **options):
        try:
            mapping = load_mapping(options["mapping"])
            plan = validate_mapping(mapping, options["organization"])
        except BootstrapValidationError as exc:
            raise CommandError(str(exc)) from exc

        if options["validate_only"]:
            self.stdout.write(
                json.dumps(
                    {
                        "fingerprint": plan.fingerprint,
                        "organization_id": plan.organization_id,
                        "products": len(plan.assignments),
                    },
                    sort_keys=True,
                )
            )
            return

        if not options["fingerprint"]:
            raise CommandError("--fingerprint is required when applying a mapping")
        try:
            plan = apply_mapping(
                mapping,
                options["organization"],
                options["fingerprint"],
            )
        except BootstrapValidationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Applied reviewed catalog bootstrap {plan.fingerprint} "
                f"to {len(plan.assignments)} Products."
            )
        )
