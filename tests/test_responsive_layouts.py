import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("route_name", "page_marker"),
    [
        ("accounts:otservers", "OTServers"),
        ("accounts:tibia_vacations", "Vocations"),
        ("accounts:users", "User Management"),
        ("accounts:roles", "Roles & Groups"),
        ("accounts:audit_logs", "Audit Logs"),
    ],
)
def test_list_pages_render_mobile_and_desktop_layout(
    route_name: str, page_marker: str
) -> None:
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        email="responsive-layouts@example.com",
        password="StrongPass123!",
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    response = client.get(reverse(route_name))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert page_marker in content
    assert "md:hidden" in content
    assert "md:block" in content
