import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from accounts.models import OTServer, TibiaVersion


def _create_otserver(*, name: str, version: str) -> OTServer:
    tibia_version, _created = TibiaVersion.objects.get_or_create(
        code=version,
        defaults={"sort_order": 1, "is_supported": True},
    )
    return OTServer.objects.create(
        name=name,
        tibia_version=tibia_version,
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


@pytest.mark.django_db
def test_home_shows_tibia_versions_menu_when_user_has_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="versions-menu@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiaversion"),
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Tibia Versions" in content
    assert reverse("accounts:tibia_versions") in content


@pytest.mark.django_db
def test_tibia_versions_route_requires_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="versions-route@example.com", password="StrongPass123!"
    )
    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:tibia_versions"))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    denied_missing_version_perm = client.get(reverse("accounts:tibia_versions"))
    assert denied_missing_version_perm.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_tibiaversion"))
    allowed = client.get(reverse("accounts:tibia_versions"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_tibia_version_create_update_and_delete_flow() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="versions-crud@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiaversion"),
        Permission.objects.get(codename="add_tibiaversion"),
        Permission.objects.get(codename="change_tibiaversion"),
        Permission.objects.get(codename="delete_tibiaversion"),
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    create_response = client.post(
        reverse("accounts:tibia_version_create"),
        {"code": "15.40", "sort_order": 40, "is_supported": "on"},
    )
    assert create_response.status_code == 302
    assert TibiaVersion.objects.filter(code="15.40").exists()

    update_response = client.post(
        reverse("accounts:tibia_version_update", args=["15.40"]),
        {"code": "15.40", "sort_order": 99, "is_supported": ""},
    )
    assert update_response.status_code == 302
    updated = TibiaVersion.objects.get(code="15.40")
    assert updated.sort_order == 99
    assert updated.is_supported is False

    delete_response = client.post(
        reverse("accounts:tibia_version_delete", args=["15.40"])
    )
    assert delete_response.status_code == 302
    assert not TibiaVersion.objects.filter(code="15.40").exists()


@pytest.mark.django_db
def test_tibia_version_delete_is_blocked_when_version_is_in_use() -> None:
    in_use_version, _created = TibiaVersion.objects.update_or_create(
        code="15.20",
        defaults={"sort_order": 20, "is_supported": True},
    )
    _create_otserver(name="Crystal", version=in_use_version.code)

    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="versions-delete-blocked@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiaversion"),
        Permission.objects.get(codename="delete_tibiaversion"),
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.post(
        reverse("accounts:tibia_version_delete", args=[in_use_version.code])
    )
    assert response.status_code == 302
    assert TibiaVersion.objects.filter(code="15.20").exists()

    follow_response = client.get(reverse("accounts:tibia_versions"))
    follow_content = follow_response.content.decode("utf-8")
    assert "Cannot remove this Tibia version" in follow_content


@pytest.mark.django_db
def test_tibia_versions_page_is_translated_and_responsive_in_pt_br() -> None:
    TibiaVersion.objects.update_or_create(
        code="15.30",
        defaults={"sort_order": 30, "is_supported": True},
    )

    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="versions-pt-responsive@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiaversion"),
    )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:tibia_versions"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Tibia" in content
    assert "md:hidden" in content
    assert "md:block" in content
