from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from accounts.models import AuditLog, OTServer, TibiaVersion


@pytest.mark.django_db
def test_home_dashboard_renders_classic_layout_sections_with_real_metrics() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="home-classic@example.com", password="StrongPass123!"
    )
    AuditLog.objects.create(
        actor=user,
        action="otserver.connection_test",
        target="Realm A",
        details={"success": False},
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    with (
        patch("accounts.views.run_scheduled_otserver_health_checks"),
        patch("accounts.views.summarize_otserver_characters") as summary_mock,
    ):
        summary_mock.return_value = {
            "total_characters": 60,
            "online_characters": 22,
            "offline_characters": 38,
            "unknown_status_characters": 0,
            "active_sources": 3,
            "healthy_sources": 2,
            "errors": [{"otserver_name": "X", "message": "timeout"}],
        }
        response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert ">22<" in content
    assert ">2<" in content
    assert "2/3 OT sources healthy" in content
    assert "Online players" in content
    assert "Active realms" in content
    assert "Pending tickets" in content
    assert "Next save-server" in content
    assert "Operational feed" in content
    assert "Quick actions" in content
    assert "Operator status" in content
    assert "No monitored OTServers configured." in content


@pytest.mark.django_db
def test_operational_feed_shows_only_otserver_events_with_friendly_labels() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="home-feed@example.com", password="StrongPass123!"
    )
    AuditLog.objects.create(
        actor=user,
        action="otserver.update",
        target="Realm Alpha",
        details={},
    )
    AuditLog.objects.create(
        actor=user,
        action="otserver.connection_test",
        target="Realm Beta",
        details={"success": True},
    )
    AuditLog.objects.create(
        actor=user,
        action="tibia_vacation.create",
        target="15.30:1",
        details={},
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    with patch("accounts.views.run_scheduled_otserver_health_checks"):
        response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "OTServer updated" in content
    assert "Connection test" in content
    assert "Succeeded" in content
    assert "tibia_vacation.create" not in content


@pytest.mark.django_db
def test_operational_feed_limits_to_five_and_translates_to_portuguese() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="home-feed-pt@example.com", password="StrongPass123!"
    )
    for index in range(6):
        AuditLog.objects.create(
            actor=user,
            action="otserver.connection_test",
            target=f"Realm {index}",
            details={"success": True},
        )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=user.email, password="StrongPass123!")
    with patch("accounts.views.run_scheduled_otserver_health_checks"):
        response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert content.count("Teste de conexão") == 5
    assert "Sucesso" in content
    assert "Realm 0" not in content


@pytest.mark.django_db
def test_operator_status_lists_otserver_name_and_connection_state() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="home-status@example.com", password="StrongPass123!"
    )
    TibiaVersion.objects.get_or_create(code=TibiaVersion.DEFAULT_CODE)
    OTServer.objects.create(
        name="Crystal",
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
        last_health_check_ok=True,
    )
    OTServer.objects.create(
        name="Atlas",
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
        last_health_check_ok=False,
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    with patch("accounts.views.run_scheduled_otserver_health_checks"):
        response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Crystal" in content
    assert "Atlas" in content
    assert "Connected" in content
    assert "Disconnected" in content
