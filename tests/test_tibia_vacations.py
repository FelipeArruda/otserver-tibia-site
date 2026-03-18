import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from accounts.models import OTServer, TibiaVacation, TibiaVersion


def _create_otserver(name: str, *, version: str = "15.30") -> OTServer:
    TibiaVersion.objects.get_or_create(code=version, defaults={"sort_order": 1})
    return OTServer.objects.create(
        name=name,
        tibia_version_id=version,
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
def test_home_shows_vocations_menu_when_user_has_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="vocations-menu@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiavacation"),
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Vocations" in content
    assert reverse("accounts:tibia_vacations") in content


@pytest.mark.django_db
def test_tibia_vacations_route_requires_permissions() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="vocations-route@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:tibia_vacations"))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    denied_missing_vocation_perm = client.get(reverse("accounts:tibia_vacations"))
    assert denied_missing_vocation_perm.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_tibiavacation"))
    allowed = client.get(reverse("accounts:tibia_vacations"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_tibia_vacation_create_flow() -> None:
    server = _create_otserver("Vocation Create Server")
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="vocations-create@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiavacation"),
        Permission.objects.get(codename="add_tibiavacation"),
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:tibia_vacation_create"),
        {
            "otserver": str(server.pk),
            "vocation_id": 11,
            "name": "Templar",
            "description": "a templar",
            "name_pt_br": "Templário",
            "description_pt_br": "um templário",
            "base_id": 11,
            "from_voc": 11,
            "client_id": 16,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("accounts:tibia_vacations")
    assert TibiaVacation.objects.filter(
        otserver=server,
        tibia_version_id="15.30",
        vocation_id=11,
        name="Templar",
        name_pt_br="Templário",
    ).exists()


@pytest.mark.django_db
def test_tibia_vacation_edit_labels_are_portuguese_in_pt_br() -> None:
    server = _create_otserver("Vocation Edit Server")
    vacation = TibiaVacation.objects.create(
        otserver=server,
        tibia_version_id="15.30",
        vocation_id=99,
        name="Tester",
        description="a tester",
    )

    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="vocations-pt-labels@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="change_tibiavacation"),
    )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=user.email, password="StrongPass123!")

    response = client.get(reverse("accounts:tibia_vacation_update", args=[vacation.pk]))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "OTServer" in content
    assert "ID da vocação" in content
    assert "Descrição" in content
    assert "Vocação de origem" in content


@pytest.mark.django_db
def test_tibia_vacation_create_success_message_is_translated_in_pt_br() -> None:
    server = _create_otserver("Vocation Success Server")
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="vocations-success-msg@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="view_tibiavacation"),
        Permission.objects.get(codename="add_tibiavacation"),
    )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=user.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:tibia_vacation_create"),
        {
            "otserver": str(server.pk),
            "vocation_id": 77,
            "name": "Sentinel",
            "description": "a sentinel",
            "name_pt_br": "Sentinela",
            "description_pt_br": "um sentinela",
            "base_id": 77,
            "from_voc": 77,
            "client_id": 77,
        },
        follow=True,
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Vocação criada com sucesso." in content


@pytest.mark.django_db
def test_tibia_vacation_duplicate_error_message_is_translated_in_pt_br() -> None:
    server = _create_otserver("Vocation Duplicate Server")
    TibiaVacation.objects.create(
        otserver=server,
        tibia_version_id="15.30",
        vocation_id=88,
        name="Guardian",
        description="a guardian",
    )
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="vocations-error-msg@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(
        Permission.objects.get(codename="view_otserver"),
        Permission.objects.get(codename="add_tibiavacation"),
    )

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=user.email, password="StrongPass123!")

    response = client.post(
        reverse("accounts:tibia_vacation_create"),
        {
            "otserver": str(server.pk),
            "vocation_id": 88,
            "name": "Guardian",
            "description": "a guardian",
            "name_pt_br": "Guardião",
            "description_pt_br": "um guardião",
            "base_id": 88,
            "from_voc": 88,
            "client_id": 88,
        },
        follow=True,
    )
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Corrija os campos destacados." in content
    assert "Já existe uma vocação com este ID para o OTServer selecionado." in content
