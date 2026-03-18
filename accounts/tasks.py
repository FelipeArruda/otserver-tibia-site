from __future__ import annotations

from celery import shared_task

from accounts.services import run_scheduled_otserver_health_checks


@shared_task(
    bind=True,
    ignore_result=True,
    name="accounts.tasks.run_otserver_health_check",
)
def run_otserver_health_check(self) -> dict[str, int]:
    del self
    checks = run_scheduled_otserver_health_checks()
    return {"checked_count": len(checks)}
