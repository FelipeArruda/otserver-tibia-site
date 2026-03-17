from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from accounts.models import AuditLog


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
    with patch("accounts.views.summarize_otserver_characters") as summary_mock:
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
    assert "Webhook queue" in content
