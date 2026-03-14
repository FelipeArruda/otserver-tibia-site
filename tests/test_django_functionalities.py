from django.core.management import call_command
from django.test import Client
from django.urls import reverse


def test_admin_url_redirects_for_anonymous_user() -> None:
    client = Client()
    response = client.get("/admin/")
    assert response.status_code == 302


def test_admin_login_page_is_available() -> None:
    client = Client()
    response = client.get(reverse("admin:login"))
    assert response.status_code == 200


def test_django_system_check_passes() -> None:
    call_command("check")
