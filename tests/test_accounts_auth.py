import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@pytest.mark.django_db
def test_signup_creates_user_with_email_as_identifier() -> None:
    client = Client()
    response = client.post(
        reverse("accounts:signup"),
        {
            "email": "user@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        },
    )

    assert response.status_code == 302
    user = get_user_model().objects.get(email="user@example.com")
    assert user.email == "user@example.com"
    assert user.pk == "user@example.com"


@pytest.mark.django_db
def test_login_accepts_email_and_password() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(email="login@example.com", password="StrongPass123!")

    client = Client()
    response = client.post(
        reverse("accounts:login"),
        {"username": "login@example.com", "password": "StrongPass123!"},
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:home")


@pytest.mark.django_db
def test_auth_routes_are_accessible_and_functional() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="routes@example.com",
        password="StrongPass123!",
    )
    client = Client()

    assert client.get(reverse("accounts:login")).status_code == 200
    assert client.get(reverse("accounts:signup")).status_code == 200
    assert client.get(reverse("accounts:password_reset")).status_code == 200

    # Home must require authentication.
    home_anonymous = client.get(reverse("accounts:home"))
    assert home_anonymous.status_code == 302
    assert reverse("accounts:login") in home_anonymous.url

    assert client.login(username="routes@example.com", password="StrongPass123!")
    assert client.get(reverse("accounts:home")).status_code == 200
    logout_response = client.get(reverse("accounts:logout"))
    assert logout_response.status_code == 302
    assert logout_response.url == reverse("accounts:login")

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_confirm = client.get(
        reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": uid, "token": token},
        )
    )
    assert reset_confirm.status_code == 200


def test_set_language_endpoint_is_available() -> None:
    client = Client()
    response = client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert response.status_code == 302
    assert response.cookies["django_language"].value == "pt-br"


def test_login_page_is_translated_after_language_switch() -> None:
    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    response = client.get(reverse("accounts:login"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Bem-vindo de volta" in content
    assert "Acessar" in content


def test_forgot_password_page_is_translated_with_accents() -> None:
    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    response = client.get(reverse("accounts:password_reset"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Esqueci minha senha" in content
    assert "instruções de redefinição" in content


@pytest.mark.django_db
def test_home_shows_admin_menus_when_user_has_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="adminmenu@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_user"),
        Permission.objects.get(codename="view_group"),
    )

    client = Client()
    assert client.login(username="adminmenu@example.com", password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "User Management" in content
    assert "Roles &amp; Groups" in content


@pytest.mark.django_db
def test_home_hides_admin_menus_without_permissions() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(
        email="simplemenu@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username="simplemenu@example.com", password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "User Management" not in content
    assert "Roles &amp; Groups" not in content


@pytest.mark.django_db
def test_home_shows_audit_menu_only_for_staff_users() -> None:
    user_model = get_user_model()
    regular = user_model.objects.create_user(
        email="regular@example.com", password="StrongPass123!"
    )
    staff = user_model.objects.create_user(
        email="staff@example.com", password="StrongPass123!", is_staff=True
    )

    client = Client()
    assert client.login(username=regular.email, password="StrongPass123!")
    regular_response = client.get(reverse("accounts:home"))
    assert "Audit Logs" not in regular_response.content.decode("utf-8")
    client.get(reverse("accounts:logout"))

    assert client.login(username=staff.email, password="StrongPass123!")
    staff_response = client.get(reverse("accounts:home"))
    assert "Audit Logs" in staff_response.content.decode("utf-8")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
@pytest.mark.django_db
def test_forgot_password_sends_reset_email() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(
        email="recover@example.com", password="StrongPass123!"
    )

    client = Client()
    response = client.post(
        reverse("accounts:password_reset"),
        {"email": "recover@example.com"},
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 1
    assert "reset" in mail.outbox[0].subject.lower()
