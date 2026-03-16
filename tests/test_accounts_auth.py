import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import PlatformSetting


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
def test_login_accepts_email_case_insensitively() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(email="Admin@Admin.com", password="StrongPass123!")

    client = Client()
    response = client.post(
        reverse("accounts:login"),
        {"username": "admin@admin.com", "password": "StrongPass123!"},
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
    assert reverse("accounts:users") in content
    assert reverse("accounts:roles") in content


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
    assert reverse("accounts:users") not in content
    assert reverse("accounts:roles") not in content


@pytest.mark.django_db
def test_users_route_requires_view_user_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="rbac1@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username="rbac1@example.com", password="StrongPass123!")
    denied_response = client.get(reverse("accounts:users"))
    assert denied_response.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_user"))
    allowed_response = client.get(reverse("accounts:users"))
    assert allowed_response.status_code == 200


@pytest.mark.django_db
def test_roles_route_requires_view_group_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="rbac2@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username="rbac2@example.com", password="StrongPass123!")
    denied_response = client.get(reverse("accounts:roles"))
    assert denied_response.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_group"))
    allowed_response = client.get(reverse("accounts:roles"))
    assert allowed_response.status_code == 200


@pytest.mark.django_db
def test_default_roles_are_seeded() -> None:
    role_names = set(Group.objects.values_list("name", flat=True))
    assert {"Owner", "Game Master", "Support", "Viewer"}.issubset(role_names)


@pytest.mark.django_db
def test_user_create_route_requires_add_user_permission() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="manager@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:user_create"))
    assert denied.status_code == 403

    manager.user_permissions.add(Permission.objects.get(codename="add_user"))
    allowed = client.get(reverse("accounts:user_create"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_user_create_flow_works_with_required_permission() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="creator@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(Permission.objects.get(codename="add_user"))

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:user_create"),
        {
            "email": "new.user@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:users")
    assert user_model.objects.filter(email="new.user@example.com").exists()


@pytest.mark.django_db
def test_user_update_and_toggle_require_change_user_permission() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="changer@example.com", password="StrongPass123!"
    )
    target = user_model.objects.create_user(
        email="target@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    denied_edit = client.get(reverse("accounts:user_update", kwargs={"pk": target.pk}))
    denied_toggle = client.post(
        reverse("accounts:user_toggle_active", kwargs={"pk": target.pk})
    )
    assert denied_edit.status_code == 403
    assert denied_toggle.status_code == 403

    manager.user_permissions.add(Permission.objects.get(codename="change_user"))

    allowed_edit = client.post(
        reverse("accounts:user_update", kwargs={"pk": target.pk}),
        {
            "email": target.email,
            "is_active": "on",
            "is_staff": "on",
        },
    )
    assert allowed_edit.status_code == 302

    target.refresh_from_db()
    assert target.is_staff is True

    toggle_response = client.post(
        reverse("accounts:user_toggle_active", kwargs={"pk": target.pk})
    )
    assert toggle_response.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False


@pytest.mark.django_db
def test_user_filters_by_status_and_search() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="viewer@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_user"))

    user_model.objects.create_user(email="alpha@example.com", password="StrongPass123!")
    user_model.objects.create_user(
        email="beta@example.com", password="StrongPass123!", is_active=False
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    active_response = client.get(reverse("accounts:users"), {"status": "active"})
    active_content = active_response.content.decode("utf-8")
    assert "alpha@example.com" in active_content
    assert "beta@example.com" not in active_content

    search_response = client.get(reverse("accounts:users"), {"q": "beta@"})
    search_content = search_response.content.decode("utf-8")
    assert "beta@example.com" in search_content
    assert "alpha@example.com" not in search_content


@pytest.mark.django_db
def test_platform_settings_route_requires_change_permission() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="platform@example.com", password="StrongPass123!"
    )
    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    denied_response = client.get(reverse("accounts:platform_settings"))
    assert denied_response.status_code == 403

    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )
    allowed_response = client.get(reverse("accounts:platform_settings"))
    assert allowed_response.status_code == 200


@pytest.mark.django_db
def test_platform_settings_can_be_updated() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="platform-editor@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:platform_settings"),
        {
            "platform_name": "Painel OTServ BR",
            "default_language": "pt-br",
            "default_timezone": "America/Sao_Paulo",
            "primary_color": "#0ea5e9",
            "logo_url": "https://example.com/logo.png",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:platform_settings")

    platform_settings = PlatformSetting.get_solo()
    assert platform_settings.platform_name == "Painel OTServ BR"
    assert platform_settings.default_language == "pt-br"
    assert platform_settings.default_timezone == "America/Sao_Paulo"
    assert platform_settings.primary_color == "#0ea5e9"
    assert client.session.get("django_language") == "pt-br"
    assert response.cookies["django_language"].value == "pt-br"


@pytest.mark.django_db
def test_platform_default_language_applies_without_user_selection() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(email="lang@example.com", password="StrongPass123!")

    platform_settings = PlatformSetting.get_solo()
    platform_settings.default_language = "pt-br"
    platform_settings.save(update_fields=["default_language"])

    client = Client()
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200
    assert response.wsgi_request.LANGUAGE_CODE == "pt-br"

    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    response_with_cookie = client.get(reverse("accounts:login"))
    assert response_with_cookie.wsgi_request.LANGUAGE_CODE == "en"


@pytest.mark.django_db
def test_home_shows_platform_settings_menu_with_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="menu-platform@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="change_platformsetting"))

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Platform Settings" in content
    assert reverse("accounts:platform_settings") in content


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
