from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from accounts.models import AuditLog, OTServer, PlatformSetting, TibiaVersion
from accounts.services import run_scheduled_otserver_health_checks


def _create_server(
    *,
    name: str,
    interval: int,
    last_check_minutes_ago: int | None,
) -> OTServer:
    TibiaVersion.objects.get_or_create(code=TibiaVersion.DEFAULT_CODE)
    server = OTServer.objects.create(
        name=name,
        tibia_version_id=TibiaVersion.DEFAULT_CODE,
        environment=OTServer.Environment.PRODUCTION,
        database_engine=OTServer.DatabaseEngine.MYSQL,
        db_host="localhost",
        db_port=3306,
        db_name="ot",
        db_user="root",
        db_password="secret",
        db_charset="utf8mb4",
        timezone="UTC",
        monitor_enabled=True,
        monitor_interval_minutes=interval,
    )
    if last_check_minutes_ago is not None:
        OTServer.objects.filter(pk=server.pk).update(
            last_health_check_at=timezone.now()
            - timedelta(minutes=last_check_minutes_ago)
        )
        server.refresh_from_db()
    return server


@pytest.mark.django_db
def test_run_scheduled_checks_respects_interval_and_logs() -> None:
    due = _create_server(name="DueServer", interval=5, last_check_minutes_ago=10)
    _create_server(name="FreshServer", interval=10, last_check_minutes_ago=2)
    now = timezone.now()

    with patch(
        "accounts.services.check_otserver_connections",
        return_value={
            "success": True,
            "database": {"ok": True, "message": "ok"},
            "api": {"ok": None, "message": "API test skipped."},
        },
    ) as checker:
        checks = run_scheduled_otserver_health_checks(now=now)

    assert checker.call_count == 1
    assert len(checks) == 1
    due.refresh_from_db()
    assert due.last_health_check_ok is True
    assert due.last_health_check_at == now
    assert AuditLog.objects.filter(
        action="otserver.health_check",
        target="DueServer",
        details__source="scheduler",
        details__success=True,
    ).exists()


@pytest.mark.django_db
def test_scheduled_checks_log_checked_at_using_platform_timezone() -> None:
    _create_server(name="TimezoneServer", interval=5, last_check_minutes_ago=None)
    platform_settings = PlatformSetting.get_solo()
    platform_settings.default_timezone = "America/Sao_Paulo"
    platform_settings.save(update_fields=["default_timezone"])

    with patch(
        "accounts.services.check_otserver_connections",
        return_value={
            "success": True,
            "database": {"ok": True, "message": "ok"},
            "api": {"ok": None, "message": "API test skipped."},
        },
    ):
        run_scheduled_otserver_health_checks()

    audit = AuditLog.objects.filter(
        action="otserver.health_check", target="TimezoneServer"
    ).first()
    assert audit is not None
    assert audit.details.get("timezone") == "America/Sao_Paulo"
    assert str(audit.details.get("checked_at", "")).endswith("-03:00")


@pytest.mark.django_db
def test_check_otserver_health_command_runs_scheduler() -> None:
    with patch(
        "accounts.management.commands.check_otserver_health.run_scheduled_otserver_health_checks",
        return_value=[{"server": "A"}, {"server": "B"}],
    ) as scheduler:
        call_command("check_otserver_health", "--timeout", "9")

    scheduler.assert_called_once_with(timeout_seconds=9)
