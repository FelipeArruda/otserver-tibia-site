from django.core.management.base import BaseCommand

from accounts.services import run_scheduled_otserver_health_checks


class Command(BaseCommand):
    help = (
        "Run scheduled OTServer health checks based on each server monitoring interval."
    )

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--timeout",
            type=int,
            default=5,
            help="Connection timeout in seconds for each OTServer check.",
        )

    def handle(self, *args: object, **options: object) -> None:
        timeout_seconds = int(options["timeout"])
        checks = run_scheduled_otserver_health_checks(timeout_seconds=timeout_seconds)
        self.stdout.write(
            self.style.SUCCESS(
                f"Executed {len(checks)} OTServer health check(s) with timeout={timeout_seconds}s."
            )
        )
