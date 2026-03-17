import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from accounts.models import AuditLog, OTServer


@pytest.mark.django_db
def test_home_dashboard_uses_project_data_metrics_and_recent_events() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="home-metrics@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_auditlog"),
    )

    OTServer.objects.create(
        name="Realm Alpha",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="root",
        db_password="secret",
        timezone="UTC",
        is_active=True,
    )
    OTServer.objects.create(
        name="Realm Beta",
        environment="staging",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv_beta",
        db_user="root",
        db_password="secret",
        timezone="UTC",
        is_active=False,
    )

    AuditLog.objects.create(
        actor=user,
        action="otserver.connection_test",
        target="Realm Alpha",
        details={"success": True},
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "1/2" in content
    assert "otserver.connection_test" in content
    assert "Realm Alpha" in content
    assert reverse("accounts:otservers") in content
    assert reverse("accounts:audit_logs") in content
