from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.forms import PlatformSettingForm
from accounts.models import AuditLog, OTServer, PlatformSetting
from accounts.services import check_otserver_connections


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
    assert 'data-testid="settings-group"' in content
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
    assert 'data-testid="settings-group"' not in content
    assert "User Management" not in content
    assert "Roles &amp; Groups" not in content
    assert reverse("accounts:users") not in content
    assert reverse("accounts:roles") not in content


@pytest.mark.django_db
def test_home_shows_settings_group_when_one_settings_item_is_allowed() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="settings-group@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_user"))

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'data-testid="settings-group"' in content
    assert "User Management" in content
    assert "Roles &amp; Groups" not in content


@pytest.mark.django_db
def test_home_shows_otservers_in_main_menu() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="otservers-menu@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'data-testid="otservers_group"' in content
    assert "OTServers" in content
    assert reverse("accounts:otservers") in content
    assert reverse("accounts:characters") in content
    assert 'data-testid="settings-group"' not in content


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
def test_roles_list_filters_by_name_and_members() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="roles-filter@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_group"))

    with_members = Group.objects.create(name="Alpha Team")
    without_members = Group.objects.create(name="Zulu Team")
    with_members.user_set.add(manager)
    del without_members

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    search_response = client.get(reverse("accounts:roles"), {"q": "Alpha"})
    search_content = search_response.content.decode("utf-8")
    assert "Alpha Team" in search_content
    assert "Zulu Team" not in search_content

    members_response = client.get(reverse("accounts:roles"), {"members": "with"})
    members_content = members_response.content.decode("utf-8")
    assert "Alpha Team" in members_content
    assert "Zulu Team" not in members_content

    without_members_response = client.get(
        reverse("accounts:roles"), {"members": "without"}
    )
    without_members_content = without_members_response.content.decode("utf-8")
    assert "Alpha Team" not in without_members_content
    assert "Zulu Team" in without_members_content


@pytest.mark.django_db
def test_roles_list_orders_by_permissions_desc() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="roles-order@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_group"))

    low_role = Group.objects.create(name="Low Perm")
    high_role = Group.objects.create(name="High Perm")
    high_role.permissions.add(
        Permission.objects.get(codename="view_user"),
        Permission.objects.get(codename="change_user"),
    )
    low_role.permissions.add(Permission.objects.get(codename="view_user"))

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:roles"), {"order": "permissions_desc"})
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert content.find("High Perm") < content.find("Low Perm")


@pytest.mark.django_db
def test_roles_list_orders_by_members_and_falls_back_on_invalid_order() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="roles-order-members@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_group"))

    Group.objects.create(name="A Role")
    role_b = Group.objects.create(name="B Role")
    Group.objects.create(name="C Role")
    role_b.user_set.add(manager)

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    members_order_response = client.get(
        reverse("accounts:roles"), {"order": "members_desc"}
    )
    members_content = members_order_response.content.decode("utf-8")
    assert members_order_response.status_code == 200
    assert members_content.find("B Role") < members_content.find("A Role")

    name_desc_response = client.get(reverse("accounts:roles"), {"order": "name_desc"})
    name_desc_content = name_desc_response.content.decode("utf-8")
    assert name_desc_response.status_code == 200
    assert name_desc_content.find("C Role") < name_desc_content.find("A Role")

    invalid_order_response = client.get(reverse("accounts:roles"), {"order": "invalid"})
    invalid_order_content = invalid_order_response.content.decode("utf-8")
    assert invalid_order_response.status_code == 200
    assert invalid_order_content.find("A Role") < invalid_order_content.find("C Role")


@pytest.mark.django_db
def test_roles_list_is_paginated_and_keeps_filters_in_links() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="roles-pagination@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_group"))

    for index in range(15):
        Group.objects.create(name=f"PaginatedRole{index:02d}")

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:roles"), {"q": "PaginatedRole"})

    assert response.status_code == 200
    assert response.context["is_paginated"] is True
    assert response.context["paginator"].per_page == 10
    assert len(response.context["roles"]) == 10
    assert "?page=2&q=PaginatedRole" in response.content.decode("utf-8")

    second_page = client.get(
        reverse("accounts:roles"), {"q": "PaginatedRole", "page": 2}
    )
    assert second_page.status_code == 200
    assert len(second_page.context["roles"]) == 5


@pytest.mark.django_db
def test_role_create_requires_add_group_permission() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-creator-denied@example.com",
        password="StrongPass123!",
    )
    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    denied = client.post(
        reverse("accounts:role_create"),
        {
            "role-name": "Content Team",
            "role-permissions": [Permission.objects.get(codename="view_user").pk],
        },
    )
    assert denied.status_code == 403

    manager.user_permissions.add(
        Permission.objects.get(codename="add_group"),
        Permission.objects.get(codename="view_group"),
    )
    allowed = client.post(
        reverse("accounts:role_create"),
        {
            "role-name": "Content Team",
            "role-permissions": [Permission.objects.get(codename="view_user").pk],
        },
    )
    assert allowed.status_code == 302
    assert Group.objects.filter(name="Content Team").exists()
    assert AuditLog.objects.filter(action="role.create", target="Content Team").exists()


@pytest.mark.django_db
def test_role_create_get_requires_permissions() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-create-get@example.com",
        password="StrongPass123!",
    )
    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:role_create"))
    assert denied.status_code == 403

    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="add_group"),
    )
    allowed = client.get(reverse("accounts:role_create"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_role_create_page_is_translated_in_portuguese() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-create-lang@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="add_group"),
    )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:role_create"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Criar papel" in content
    assert "Voltar para papéis" in content
    assert "Pode visualizar" in content


@pytest.mark.django_db
def test_role_create_shows_inline_error_for_duplicate_name() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-creator-duplicate@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="add_group"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:role_create"),
        {
            "role-name": "owner",
            "role-permissions": [Permission.objects.get(codename="view_user").pk],
        },
    )

    assert response.status_code == 400
    assert "A role with this name already exists." in response.content.decode("utf-8")


@pytest.mark.django_db
def test_role_create_shows_inline_error_for_invalid_permission() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-creator-invalid-perm@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="add_group"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:role_create"),
        {
            "role-name": "Role Invalid Perm",
            "role-permissions": ["999999"],
        },
    )

    assert response.status_code == 400
    assert "Select a valid choice." in response.content.decode("utf-8")


@pytest.mark.django_db
def test_role_update_updates_permissions_and_members() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-editor@example.com",
        password="StrongPass123!",
    )
    member = user_model.objects.create_user(
        email="member@example.com",
        password="StrongPass123!",
    )
    role = Group.objects.create(name="Ops")
    role.permissions.add(Permission.objects.get(codename="view_group"))

    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="change_group"),
        Permission.objects.get(codename="change_user"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:role_update", kwargs={"pk": role.pk}),
        {
            "role-name": "Operations",
            "role-permissions": [Permission.objects.get(codename="view_user").pk],
            "role-members": [member.pk],
        },
    )

    assert response.status_code == 302
    role.refresh_from_db()
    assert role.name == "Operations"
    assert role.permissions.filter(codename="view_user").exists()
    assert role.user_set.filter(email=member.email).exists()
    assert AuditLog.objects.filter(action="role.update", target="Operations").exists()


@pytest.mark.django_db
def test_role_update_without_change_user_does_not_change_members() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-editor-limited@example.com",
        password="StrongPass123!",
    )
    current_member = user_model.objects.create_user(
        email="current-member@example.com",
        password="StrongPass123!",
    )
    other_member = user_model.objects.create_user(
        email="other-member@example.com",
        password="StrongPass123!",
    )
    role = Group.objects.create(name="Viewer Ops")
    role.user_set.add(current_member)

    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="change_group"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:role_update", kwargs={"pk": role.pk}),
        {
            "role-name": "Viewer Ops",
            "role-permissions": [],
            "role-members": [other_member.pk],
        },
    )

    assert response.status_code == 302
    role.refresh_from_db()
    assert role.user_set.filter(email=current_member.email).exists()
    assert not role.user_set.filter(email=other_member.email).exists()


@pytest.mark.django_db
def test_role_update_get_requires_permissions() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-update-get@example.com",
        password="StrongPass123!",
    )
    role = Group.objects.create(name="Role Update Get")

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:role_update", kwargs={"pk": role.pk}))
    assert denied.status_code == 403

    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="change_group"),
    )
    allowed = client.get(reverse("accounts:role_update", kwargs={"pk": role.pk}))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_role_update_page_is_translated_in_portuguese() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="role-update-i18n@example.com",
        password="StrongPass123!",
    )
    role = Group.objects.create(name="Role i18n")
    manager.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="change_group"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    response = client.get(reverse("accounts:role_update", kwargs={"pk": role.pk}))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Editar papel" in content
    assert "Voltar para papéis" in content
    assert "Permissões" in content
    assert "Salvar alterações do papel" in content
    assert "Contas" in content


@pytest.mark.django_db
def test_role_detail_requires_view_group_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="role-detail@example.com",
        password="StrongPass123!",
    )
    role = Group.objects.create(name="Role Detail")

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:role_detail", kwargs={"pk": role.pk}))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_group"))
    allowed = client.get(reverse("accounts:role_detail", kwargs={"pk": role.pk}))
    assert allowed.status_code == 200
    assert "Role Detail" in allowed.content.decode("utf-8")


@pytest.mark.django_db
def test_otservers_route_requires_view_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="otservers-view@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    denied = client.get(reverse("accounts:otservers"))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    allowed = client.get(reverse("accounts:otservers"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_otserver_crud_flow_with_permissions() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-crud@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_otserver"),
        Permission.objects.get(codename="change_otserver"),
        Permission.objects.get(codename="delete_otserver"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    create_response = client.post(
        reverse("accounts:otserver_create"),
        {
            "name": "Crystal Server",
            "tibia_version": "13.40",
            "environment": "production",
            "database_engine": "mysql",
            "db_host": "localhost",
            "db_port": 3306,
            "db_name": "otserv",
            "db_user": "otserv_user",
            "db_password": "Secret123!",
            "db_charset": "utf8mb4",
            "db_collation": "utf8mb4_unicode_ci",
            "db_use_ssl": "on",
            "api_base_url": "https://example.com/api",
            "api_token": "token-1",
            "timezone": "UTC",
            "monitor_enabled": "on",
            "is_active": "on",
            "players_table": "players",
            "deaths_table": "player_deaths",
            "player_id_column": "id",
            "player_group_id_column": "group_id",
            "death_player_id_column": "player_id",
            "death_time_column": "time",
            "death_level_column": "level",
            "death_killer_column": "killed_by",
        },
    )
    assert create_response.status_code == 302
    server = OTServer.objects.get(name="Crystal Server")
    assert server.tibia_version_id == "13.40"
    create_log = AuditLog.objects.get(
        action="otserver.create", target="Crystal Server", actor=manager
    )
    assert create_log.details["db_password_changed"] is True
    assert create_log.details["api_token_changed"] is True
    assert create_log.details["monitor_interval_minutes"] == 5
    assert "db_password" not in create_log.details
    assert create_log.details["db_host"] == "localhost"
    assert create_log.details["db_port"] == 3306
    assert create_log.details["db_name"] == "otserv"
    assert create_log.details["db_user"] == "otserv_user"
    assert create_log.details["db_charset"] == "utf8mb4"
    assert create_log.details["db_collation"] == "utf8mb4_unicode_ci"
    assert create_log.details["db_use_ssl"] is True
    assert create_log.details["api_base_url"] == "https://example.com/api"
    assert create_log.details["api_token_configured"] is True
    assert create_log.details["timezone"] == "UTC"
    assert create_log.details["monitor_enabled"] is True
    assert create_log.details["is_active"] is True
    assert create_log.details["schema_players_table"] == "players"
    assert create_log.details["schema_deaths_table"] == "player_deaths"
    assert create_log.details["schema_player_id_column"] == "id"
    assert create_log.details["schema_player_group_id_column"] == "group_id"
    assert create_log.details["schema_death_player_id_column"] == "player_id"
    assert create_log.details["schema_death_time_column"] == "time"
    assert create_log.details["schema_death_level_column"] == "level"
    assert create_log.details["schema_death_killer_column"] == "killed_by"

    detail_response = client.get(reverse("accounts:otserver_detail", args=[server.pk]))
    assert detail_response.status_code == 200
    assert "Crystal Server" in detail_response.content.decode("utf-8")

    update_response = client.post(
        reverse("accounts:otserver_update", args=[server.pk]),
        {
            "name": "Crystal Server",
            "tibia_version": "12.70",
            "environment": "staging",
            "database_engine": "mariadb",
            "db_host": "127.0.0.1",
            "db_port": 3307,
            "db_name": "otserv_staging",
            "db_user": "otserv_user2",
            "db_password": "",
            "db_charset": "utf8mb4",
            "db_collation": "",
            "db_use_ssl": "",
            "api_base_url": "",
            "api_token": "",
            "timezone": "America/Sao_Paulo",
            "monitor_enabled": "on",
            "is_active": "on",
            "players_table": "players_custom",
            "deaths_table": "player_deaths_custom",
            "player_id_column": "guid",
            "player_group_id_column": "groupid_custom",
            "death_player_id_column": "pid",
            "death_time_column": "created_at",
            "death_level_column": "lvl",
            "death_killer_column": "killer_name",
        },
    )
    assert update_response.status_code == 302
    server.refresh_from_db()
    assert server.tibia_version_id == "12.70"
    assert server.environment == "staging"
    assert server.database_engine == "mariadb"
    assert server.db_password.startswith("enc::")
    assert server.get_db_password() == "Secret123!"
    update_log = AuditLog.objects.get(
        action="otserver.update", target="Crystal Server", actor=manager
    )
    assert update_log.details["db_password_changed"] is False
    assert update_log.details["api_token_changed"] is False
    assert "db_password" not in update_log.details
    assert update_log.details["db_host"] == "127.0.0.1"
    assert update_log.details["db_port"] == 3307
    assert update_log.details["db_name"] == "otserv_staging"
    assert update_log.details["db_user"] == "otserv_user2"
    assert update_log.details["db_collation"] == ""
    assert update_log.details["db_use_ssl"] is False
    assert update_log.details["api_base_url"] == ""
    assert update_log.details["timezone"] == "America/Sao_Paulo"
    assert update_log.details["schema_players_table"] == "players_custom"
    assert update_log.details["schema_deaths_table"] == "player_deaths_custom"
    assert update_log.details["schema_player_id_column"] == "guid"
    assert update_log.details["schema_player_group_id_column"] == "groupid_custom"
    assert update_log.details["schema_death_player_id_column"] == "pid"
    assert update_log.details["schema_death_time_column"] == "created_at"
    assert update_log.details["schema_death_level_column"] == "lvl"
    assert update_log.details["schema_death_killer_column"] == "killer_name"
    schema_update_log = AuditLog.objects.get(
        action="otserver.schema_mapping.update",
        target="Crystal Server",
        actor=manager,
    )
    assert schema_update_log.details["before"]["players_table"] == "players"
    assert schema_update_log.details["after"]["players_table"] == "players_custom"
    assert schema_update_log.details["before"]["player_group_id_column"] == "group_id"
    assert (
        schema_update_log.details["after"]["player_group_id_column"] == "groupid_custom"
    )

    delete_response = client.post(reverse("accounts:otserver_delete", args=[server.pk]))
    assert delete_response.status_code == 302
    assert AuditLog.objects.filter(
        action="otserver.delete", target="Crystal Server", actor=manager
    ).exists()
    assert not OTServer.objects.filter(pk=server.pk).exists()


@pytest.mark.django_db
def test_otserver_create_requires_view_and_add_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="otserver-create-perm@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="add_otserver"))

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    denied = client.get(reverse("accounts:otserver_create"))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    allowed = client.get(reverse("accounts:otserver_create"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_otserver_form_is_translated_in_portuguese() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-lang@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_otserver"),
    )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:otserver_create"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Nome" in content
    assert "Testar conexão" in content


@pytest.mark.django_db
def test_otserver_update_logs_db_password_change_without_exposing_secret() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-password-audit@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="change_otserver"),
    )
    server = OTServer.objects.create(
        name="PasswordAudit",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="root",
        db_password="old-secret",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:otserver_update", args=[server.pk]),
        {
            "name": "PasswordAudit",
            "tibia_version": server.tibia_version_id,
            "environment": "production",
            "database_engine": "mysql",
            "db_host": "localhost",
            "db_port": 3306,
            "db_name": "otserv",
            "db_user": "root",
            "db_password": "new-secret",
            "db_charset": "utf8mb4",
            "db_collation": "",
            "db_use_ssl": "",
            "api_base_url": "",
            "api_token": "",
            "timezone": "UTC",
            "monitor_enabled": "on",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    log_entry = AuditLog.objects.get(
        action="otserver.update", target="PasswordAudit", actor=manager
    )
    assert log_entry.details["db_password_changed"] is True
    assert "db_password" not in log_entry.details


@pytest.mark.django_db
def test_otserver_form_shows_loading_state_markup_for_connection_test() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-loading@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_otserver"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:otserver_create"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "data-test-connection-button" in content
    assert "data-test-connection-spinner" in content
    assert "data-test-connection-loading-label" in content
    assert "Testing connection..." in content


@pytest.mark.django_db
def test_otserver_form_lists_tibia_versions_and_uses_default() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-version-form@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_otserver"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:otserver_create"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'name="tibia_version"' in content
    assert '<option value="7.40"' in content
    assert '<option value="15.30"' in content

    create_without_explicit_version = client.post(
        reverse("accounts:otserver_create"),
        {
            "name": "VersionDefaultServer",
            "environment": "production",
            "database_engine": "mysql",
            "db_host": "localhost",
            "db_port": 3306,
            "db_name": "otserv",
            "db_user": "otserv_user",
            "db_password": "Secret123!",
            "db_charset": "utf8mb4",
            "db_collation": "",
            "db_use_ssl": "",
            "api_base_url": "",
            "api_token": "",
            "timezone": "UTC",
            "monitor_enabled": "on",
            "is_active": "on",
        },
    )

    assert create_without_explicit_version.status_code == 302
    created_server = OTServer.objects.get(name="VersionDefaultServer")
    assert created_server.tibia_version_id == "15.30"


@pytest.mark.django_db
def test_otserver_update_delete_require_view_with_mutation_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="otserver-mutate-perm@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="change_otserver"),
        Permission.objects.get(codename="delete_otserver"),
    )
    server = OTServer.objects.create(
        name="NoViewPermission",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password="secret",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied_update = client.get(reverse("accounts:otserver_update", args=[server.pk]))
    denied_delete = client.post(reverse("accounts:otserver_delete", args=[server.pk]))
    assert denied_update.status_code == 403
    assert denied_delete.status_code == 403


@pytest.mark.django_db
def test_otserver_create_requires_db_password() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-password-required@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_otserver"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:otserver_create"),
        {
            "name": "NoPasswordServer",
            "environment": "production",
            "database_engine": "mysql",
            "db_host": "localhost",
            "db_port": 3306,
            "db_name": "otserv",
            "db_user": "otserv_user",
            "db_password": "",
            "db_charset": "utf8mb4",
            "db_collation": "",
            "db_use_ssl": "",
            "api_base_url": "",
            "api_token": "",
            "timezone": "UTC",
            "monitor_enabled": "on",
            "is_active": "on",
        },
    )
    assert response.status_code == 200
    assert "db_password" in response.context["form"].errors
    assert not OTServer.objects.filter(name="NoPasswordServer").exists()


@pytest.mark.django_db
def test_otserver_list_filters_and_pagination() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-filter@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_otserver"))

    for index in range(12):
        OTServer.objects.create(
            name=f"Server-{index}",
            environment="production" if index % 2 == 0 else "staging",
            database_engine="mysql" if index % 2 == 0 else "mariadb",
            db_host="localhost",
            db_port=3306,
            db_name=f"db_{index}",
            db_user="root",
            db_password="secret",
            timezone="UTC",
            is_active=index % 3 != 0,
        )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(
        reverse("accounts:otservers"),
        {"environment": "production", "database_engine": "mysql"},
    )

    assert response.status_code == 200
    assert response.context["is_paginated"] is False
    assert all(
        server.environment == "production" for server in response.context["servers"]
    )
    assert all(
        server.database_engine == "mysql" for server in response.context["servers"]
    )

    paginated_response = client.get(reverse("accounts:otservers"), {"page": 2})
    assert paginated_response.status_code == 200
    assert paginated_response.context["is_paginated"] is True
    assert paginated_response.context["paginator"].per_page == 10

    pagination_with_filters = client.get(
        reverse("accounts:otservers"),
        {"environment": "production", "database_engine": "mysql", "page": 1},
    )
    assert (
        "environment=production" in pagination_with_filters.context["pagination_query"]
    )
    assert (
        "database_engine=mysql" in pagination_with_filters.context["pagination_query"]
    )


@pytest.mark.django_db
def test_otserver_test_connection_from_create_does_not_persist_and_logs() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-test-create@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_otserver"),
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    from unittest.mock import patch

    with patch("accounts.views.check_otserver_connections") as test_mock:
        test_mock.return_value = {
            "success": True,
            "database": {"ok": True, "latency_ms": 11, "message": "db ok"},
            "api": {"ok": None, "latency_ms": None, "message": "API test skipped."},
        }
        response = client.post(
            reverse("accounts:otserver_create"),
            {
                "name": "ConnOnly",
                "environment": "production",
                "database_engine": "mysql",
                "db_host": "localhost",
                "db_port": 3306,
                "db_name": "otserv",
                "db_user": "otserv_user",
                "db_password": "Secret123!",
                "db_charset": "utf8mb4",
                "db_collation": "",
                "db_use_ssl": "",
                "api_base_url": "",
                "api_token": "",
                "timezone": "UTC",
                "monitor_enabled": "on",
                "is_active": "on",
                "action": "test_connection",
            },
        )

    assert response.status_code == 200
    assert test_mock.called
    assert not OTServer.objects.filter(name="ConnOnly").exists()
    audit_entry = AuditLog.objects.get(
        action="otserver.connection_test", target="ConnOnly", actor=manager
    )
    assert audit_entry.details["success"] is True
    assert audit_entry.details["database_ok"] is True
    assert audit_entry.details["api_ok"] is None


@pytest.mark.django_db
def test_otserver_test_connection_update_uses_saved_secrets_and_logs() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-test-update@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="change_otserver"),
    )
    server = OTServer.objects.create(
        name="ConnUpdate",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password="saved-pass",
        api_token="saved-token",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    from unittest.mock import patch

    with patch("accounts.views.check_otserver_connections") as test_mock:
        test_mock.return_value = {
            "success": False,
            "database": {"ok": False, "latency_ms": None, "message": "failed"},
            "api": {"ok": False, "latency_ms": None, "message": "failed"},
        }
        response = client.post(
            reverse("accounts:otserver_update", args=[server.pk]),
            {
                "name": "ConnUpdate",
                "environment": "production",
                "database_engine": "mysql",
                "db_host": "localhost",
                "db_port": 3306,
                "db_name": "otserv",
                "db_user": "user",
                "db_password": "",
                "db_charset": "utf8mb4",
                "db_collation": "",
                "db_use_ssl": "",
                "api_base_url": "https://example.com/api",
                "api_token": "",
                "timezone": "UTC",
                "monitor_enabled": "on",
                "is_active": "on",
                "action": "test_connection",
            },
        )

    assert response.status_code == 200
    assert test_mock.called
    called_kwargs = test_mock.call_args.kwargs
    assert called_kwargs["db_password"] == "saved-pass"
    assert called_kwargs["api_token"] == "saved-token"
    audit_entry = AuditLog.objects.get(
        action="otserver.connection_test", target="ConnUpdate", actor=manager
    )
    assert audit_entry.details["success"] is False
    assert audit_entry.details["database_ok"] is False
    assert audit_entry.details["api_ok"] is False


@pytest.mark.django_db
def test_otserver_update_does_not_prefill_secret_fields_on_get() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-empty-secrets@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="change_otserver"),
    )
    server = OTServer.objects.create(
        name="NoPrefillSecrets",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password="stored-db-password",
        api_token="stored-api-token",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:otserver_update", args=[server.pk]))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert 'name="db_password"' in content
    assert 'name="api_token"' in content
    assert "stored-db-password" not in content
    assert "stored-api-token" not in content


@pytest.mark.django_db
def test_otserver_test_connection_keeps_used_secret_values_in_form() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-keep-secret@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="change_otserver"),
    )
    server = OTServer.objects.create(
        name="KeepSecretAfterTest",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password="stored-db-password",
        api_token="stored-api-token",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    from unittest.mock import patch

    with patch("accounts.views.check_otserver_connections") as test_mock:
        test_mock.return_value = {
            "success": True,
            "database": {"ok": True, "latency_ms": 12, "message": "db ok"},
            "api": {"ok": True, "latency_ms": 19, "message": "api ok"},
        }
        response = client.post(
            reverse("accounts:otserver_update", args=[server.pk]),
            {
                "name": "KeepSecretAfterTest",
                "environment": "production",
                "database_engine": "mysql",
                "db_host": "localhost",
                "db_port": 3306,
                "db_name": "otserv",
                "db_user": "user",
                "db_password": "",
                "db_charset": "utf8mb4",
                "db_collation": "",
                "db_use_ssl": "",
                "api_base_url": "https://example.com/api",
                "api_token": "",
                "timezone": "UTC",
                "monitor_enabled": "on",
                "is_active": "on",
                "action": "test_connection",
            },
        )

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert 'name="db_password"' in content
    assert 'name="api_token"' in content
    assert 'value="stored-db-password"' in content
    assert 'value="stored-api-token"' in content


@pytest.mark.django_db
def test_otserver_secrets_are_encrypted_and_masked_on_detail() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-secret-mask@example.com",
        password="StrongPass123!",
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    server = OTServer.objects.create(
        name="SecureOTServer",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password="my-db-secret",
        api_token="my-api-token",
        timezone="UTC",
    )

    server.refresh_from_db()
    assert server.db_password.startswith("enc::")
    assert server.api_token.startswith("enc::")
    assert server.get_db_password() == "my-db-secret"
    assert server.get_api_token() == "my-api-token"

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:otserver_detail", args=[server.pk]))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "********" in content
    assert "my-db-secret" not in content
    assert "my-api-token" not in content


@pytest.mark.django_db
def test_otserver_encrypted_secret_supports_long_values() -> None:
    long_secret = "s" * 400
    server = OTServer.objects.create(
        name="LongSecretServer",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password=long_secret,
        api_token=long_secret,
        timezone="UTC",
    )
    server.refresh_from_db()

    assert server.db_password.startswith("enc::")
    assert server.api_token.startswith("enc::")
    assert server.get_db_password() == long_secret
    assert server.get_api_token() == long_secret


@pytest.mark.django_db
def test_otserver_test_connection_requires_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="otserver-test-perm@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="add_otserver"))
    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied = client.post(
        reverse("accounts:otserver_create"),
        {
            "name": "DeniedConnection",
            "environment": "production",
            "database_engine": "mysql",
            "db_host": "localhost",
            "db_port": 3306,
            "db_name": "otserv",
            "db_user": "otserv_user",
            "db_password": "Secret123!",
            "db_charset": "utf8mb4",
            "db_collation": "",
            "db_use_ssl": "",
            "api_base_url": "",
            "api_token": "",
            "timezone": "UTC",
            "monitor_enabled": "on",
            "is_active": "on",
            "action": "test_connection",
        },
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_otserver_list_test_connection_requires_change_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="otserver-list-test-denied@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    server = OTServer.objects.create(
        name="ListDenied",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="otserv_user",
        db_password="Secret123!",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    denied = client.post(
        reverse("accounts:otserver_test_connection", args=[server.pk]),
        {"next": reverse("accounts:otservers")},
    )
    assert denied.status_code == 403


@pytest.mark.django_db
def test_otserver_list_test_connection_logs_and_redirects_to_filtered_list() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="otserver-list-test@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="change_otserver"),
    )
    server = OTServer.objects.create(
        name="ListConnectionTest",
        environment="production",
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="otserv_user",
        db_password="Secret123!",
        api_token="api-token",
        timezone="UTC",
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")

    from unittest.mock import patch

    with patch("accounts.views.check_otserver_connections") as test_mock:
        test_mock.return_value = {
            "success": True,
            "database": {"ok": True, "latency_ms": 8, "message": "db ok"},
            "api": {"ok": True, "latency_ms": 13, "message": "api ok"},
        }
        response = client.post(
            reverse("accounts:otserver_test_connection", args=[server.pk]),
            {"next": f"{reverse('accounts:otservers')}?q=ListConnectionTest"},
        )

    assert response.status_code == 302
    assert response.url == f"{reverse('accounts:otservers')}?q=ListConnectionTest"
    called_kwargs = test_mock.call_args.kwargs
    assert called_kwargs["db_password"] == "Secret123!"
    assert called_kwargs["api_token"] == "api-token"
    audit_entry = AuditLog.objects.get(
        action="otserver.connection_test",
        target="ListConnectionTest",
        actor=manager,
    )
    assert audit_entry.details["source"] == "list"
    assert audit_entry.details["success"] is True


def test_otserver_connection_service_handles_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    import types

    class DummyCursor:
        def execute(self, _query: str) -> None:
            return None

        def fetchone(self) -> tuple[int]:
            return (1,)

        def __enter__(self) -> "DummyCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

    class DummyConnection:
        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def close(self) -> None:
            return None

    class DummyHttpResponse:
        def __enter__(self) -> "DummyHttpResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

        def getcode(self) -> int:
            return 200

    monkeypatch.setitem(
        sys.modules,
        "pymysql",
        types.SimpleNamespace(connect=lambda **_kwargs: DummyConnection()),
    )
    monkeypatch.setattr(
        "accounts.services.urllib.request.urlopen",
        lambda _request, timeout: DummyHttpResponse(),
    )

    result = check_otserver_connections(
        database_engine="mysql",
        db_host="localhost",
        db_port=3306,
        db_name="otserv",
        db_user="user",
        db_password="secret",
        db_charset="utf8mb4",
        db_use_ssl=False,
        api_base_url="https://example.com/health",
        api_token="token",
    )

    assert result["success"] is True
    assert result["database"]["ok"] is True
    assert result["api"]["ok"] is True


@pytest.mark.django_db
def test_role_delete_requires_delete_group_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="role-delete@example.com",
        password="StrongPass123!",
    )
    role = Group.objects.create(name="Role Delete")

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied = client.post(reverse("accounts:role_delete", kwargs={"pk": role.pk}))
    assert denied.status_code == 403
    assert Group.objects.filter(pk=role.pk).exists()

    user.user_permissions.add(
        Permission.objects.get(codename="view_group"),
        Permission.objects.get(codename="delete_group"),
    )
    allowed = client.post(reverse("accounts:role_delete", kwargs={"pk": role.pk}))
    assert allowed.status_code == 302
    assert not Group.objects.filter(pk=role.pk).exists()
    assert AuditLog.objects.filter(action="role.delete", target="Role Delete").exists()


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
def test_users_list_is_paginated_and_keeps_filters_in_links() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="users-pagination@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(Permission.objects.get(codename="view_user"))

    for index in range(15):
        user_model.objects.create_user(
            email=f"pag-user-{index:02d}@example.com",
            password="StrongPass123!",
        )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.get(reverse("accounts:users"), {"q": "pag-user"})

    assert response.status_code == 200
    assert response.context["is_paginated"] is True
    assert response.context["paginator"].per_page == 10
    assert len(response.context["users"]) == 10
    assert "?page=2&q=pag-user" in response.content.decode("utf-8")

    second_page = client.get(reverse("accounts:users"), {"q": "pag-user", "page": 2})
    assert second_page.status_code == 200
    assert len(second_page.context["users"]) == 5


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
def test_platform_settings_form_lists_timezones() -> None:
    form = PlatformSettingForm(instance=PlatformSetting.get_solo())
    choices = {value for value, _label in form.fields["default_timezone"].choices}
    rendered = str(form["default_timezone"])

    assert "America/Sao_Paulo" in choices
    assert "UTC" in choices
    assert rendered.count("<option") > 10


@pytest.mark.django_db
def test_platform_settings_form_falls_back_when_timezone_database_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("accounts.forms.available_timezones", lambda: set())
    form = PlatformSettingForm(instance=PlatformSetting.get_solo())
    choices = {value for value, _label in form.fields["default_timezone"].choices}

    assert "UTC" in choices
    assert "America/Sao_Paulo" in choices


@pytest.mark.django_db
def test_platform_settings_form_uses_utc_when_stored_timezone_is_blank() -> None:
    platform_settings = PlatformSetting.get_solo()
    platform_settings.default_timezone = ""
    platform_settings.save(update_fields=["default_timezone"])

    form = PlatformSettingForm(instance=platform_settings)
    choices = {value for value, _label in form.fields["default_timezone"].choices}

    assert form.initial["default_timezone"] == "UTC"
    assert "UTC" in choices


@pytest.mark.django_db
def test_platform_settings_rejects_invalid_timezone() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="platform-invalid-timezone@example.com",
        password="StrongPass123!",
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
            "default_timezone": "Invalid/Timezone",
            "primary_color": "#0ea5e9",
            "logo_url": "https://example.com/logo.png",
        },
    )

    assert response.status_code == 200
    assert response.context is not None
    assert "default_timezone" in response.context["form"].errors


@pytest.mark.django_db
def test_platform_default_timezone_is_applied_globally() -> None:
    user_model = get_user_model()
    user_model.objects.create_user(
        email="timezone-user@example.com", password="StrongPass123!"
    )

    platform_settings = PlatformSetting.get_solo()
    platform_settings.default_timezone = "America/Sao_Paulo"
    platform_settings.save(update_fields=["default_timezone"])

    client = Client()
    response = client.get(reverse("accounts:login"))

    assert response.status_code == 200
    assert timezone.get_current_timezone_name() == "America/Sao_Paulo"


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
def test_language_preference_updates_user_and_session() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="langpref@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:language"),
        {"language": "en", "next": reverse("accounts:home")},
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:home")
    user.refresh_from_db()
    assert user.preferred_language == "en"
    assert client.session.get("django_language") == "en"
    assert response.cookies["django_language"].value == "en"


@pytest.mark.django_db
def test_middleware_uses_user_language_preference_without_cookie() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="prefonly@example.com",
        password="StrongPass123!",
        preferred_language="en",
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))

    assert response.status_code == 200
    assert response.wsgi_request.LANGUAGE_CODE == "en"


@pytest.mark.django_db
def test_audit_route_requires_view_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="auditor-denied@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    denied = client.get(reverse("accounts:audit_logs"))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_auditlog"))
    allowed = client.get(reverse("accounts:audit_logs"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_audit_logs_are_paginated_and_keep_filter_links() -> None:
    user_model = get_user_model()
    auditor = user_model.objects.create_user(
        email="auditor-pagination@example.com", password="StrongPass123!"
    )
    auditor.user_permissions.add(Permission.objects.get(codename="view_auditlog"))

    for index in range(13):
        AuditLog.objects.create(
            actor=auditor,
            action="audit.page",
            target=f"paginated-target-{index}",
            details={},
        )
    for index in range(3):
        AuditLog.objects.create(
            actor=auditor,
            action="audit.other",
            target=f"other-target-{index}",
            details={},
        )

    client = Client()
    assert client.login(username=auditor.email, password="StrongPass123!")
    response = client.get(reverse("accounts:audit_logs"), {"action": "audit.page"})

    assert response.status_code == 200
    assert response.context["is_paginated"] is True
    assert response.context["paginator"].per_page == 10
    assert response.context["show_secondary_content"] is False
    assert len(response.context["logs"]) == 10
    assert all(entry.action == "audit.page" for entry in response.context["logs"])
    content = response.content.decode("utf-8")
    assert "?page=2&action=audit.page" in content
    assert f'href="{reverse("accounts:audit_logs")}"' in content
    assert ">Clear<" in content
    assert "xl:grid-cols-1" in content

    second_page = client.get(
        reverse("accounts:audit_logs"), {"action": "audit.page", "page": 2}
    )
    assert second_page.status_code == 200
    assert len(second_page.context["logs"]) == 3
    assert all(entry.action == "audit.page" for entry in second_page.context["logs"])


@pytest.mark.django_db
def test_audit_logs_filter_by_date_range() -> None:
    user_model = get_user_model()
    auditor = user_model.objects.create_user(
        email="auditor-date-range@example.com", password="StrongPass123!"
    )
    auditor.user_permissions.add(Permission.objects.get(codename="view_auditlog"))

    old_log = AuditLog.objects.create(
        actor=auditor,
        action="audit.range",
        target="old-target",
        details={},
    )
    mid_log = AuditLog.objects.create(
        actor=auditor,
        action="audit.range",
        target="mid-target",
        details={},
    )
    new_log = AuditLog.objects.create(
        actor=auditor,
        action="audit.range",
        target="new-target",
        details={},
    )

    now = datetime.now(dt_timezone.utc)
    AuditLog.objects.filter(pk=old_log.pk).update(created_at=now - timedelta(days=5))
    AuditLog.objects.filter(pk=mid_log.pk).update(created_at=now - timedelta(days=2))
    AuditLog.objects.filter(pk=new_log.pk).update(created_at=now)

    start_date = (now - timedelta(days=3)).date().isoformat()
    end_date = (now - timedelta(days=1)).date().isoformat()

    client = Client()
    assert client.login(username=auditor.email, password="StrongPass123!")
    response = client.get(
        reverse("accounts:audit_logs"),
        {"action": "audit.range", "start_date": start_date, "end_date": end_date},
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "mid-target" in content
    assert "old-target" not in content
    assert "new-target" not in content


@pytest.mark.django_db
def test_audit_logs_invalid_date_range_returns_empty_and_message() -> None:
    user_model = get_user_model()
    auditor = user_model.objects.create_user(
        email="auditor-invalid-range@example.com", password="StrongPass123!"
    )
    auditor.user_permissions.add(Permission.objects.get(codename="view_auditlog"))
    AuditLog.objects.create(
        actor=auditor,
        action="audit.invalid-range",
        target="target",
        details={},
    )

    client = Client()
    assert client.login(username=auditor.email, password="StrongPass123!")
    response = client.get(
        reverse("accounts:audit_logs"),
        {"start_date": "2026-03-10", "end_date": "2026-03-01"},
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Start date cannot be after end date." in content
    assert "No audit records found." in content
    assert len(response.context["logs"]) == 0


@pytest.mark.django_db
def test_platform_settings_update_creates_audit_log() -> None:
    user_model = get_user_model()
    manager = user_model.objects.create_user(
        email="audit-platform@example.com", password="StrongPass123!"
    )
    manager.user_permissions.add(
        Permission.objects.get(codename="change_platformsetting")
    )

    client = Client()
    assert client.login(username=manager.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:platform_settings"),
        {
            "platform_name": "Audit Platform",
            "default_language": "pt-br",
            "default_timezone": "America/Sao_Paulo",
            "primary_color": "#0ea5e9",
            "logo_url": "https://example.com/logo.png",
        },
    )
    assert response.status_code == 302
    assert AuditLog.objects.filter(
        action="platform.settings.update",
        target="platform",
        actor=manager,
    ).exists()


@pytest.mark.django_db
def test_home_shows_audit_menu_only_with_permission() -> None:
    user_model = get_user_model()
    regular = user_model.objects.create_user(
        email="regular@example.com", password="StrongPass123!"
    )
    auditor = user_model.objects.create_user(
        email="auditor@example.com", password="StrongPass123!"
    )
    auditor.user_permissions.add(Permission.objects.get(codename="view_auditlog"))

    client = Client()
    assert client.login(username=regular.email, password="StrongPass123!")
    regular_response = client.get(reverse("accounts:home"))
    assert "Audit Logs" not in regular_response.content.decode("utf-8")
    client.get(reverse("accounts:logout"))

    assert client.login(username=auditor.email, password="StrongPass123!")
    auditor_response = client.get(reverse("accounts:home"))
    assert "Audit Logs" in auditor_response.content.decode("utf-8")


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
