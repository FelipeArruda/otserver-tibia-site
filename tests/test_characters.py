from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from accounts.models import OTServer


def _build_character(index: int, *, otserver_name: str = "Atlas") -> dict[str, object]:
    return {
        "name": f"Character-{index:02d}",
        "otserver_pk": 1,
        "otserver_name": otserver_name,
        "vocation": "Knight" if index % 2 == 0 else "Druid",
        "level": index,
        "is_online": index % 3 == 0,
        "updated_at": datetime(2026, 3, 17, 12, 0, tzinfo=UTC),
    }


@pytest.mark.django_db
def test_home_shows_characters_menu_when_user_has_otserver_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="characters-menu@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")
    response = client.get(reverse("accounts:home"))
    content = response.content.decode("utf-8")

    assert response.status_code == 200
    assert "Characters" in content
    assert reverse("accounts:characters") in content


@pytest.mark.django_db
def test_characters_route_requires_view_otserver_permission() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="characters-route@example.com", password="StrongPass123!"
    )

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    denied = client.get(reverse("accounts:characters"))
    assert denied.status_code == 403

    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))
    allowed = client.get(reverse("accounts:characters"))
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_characters_list_supports_filters_sorting_and_pagination_contract() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="characters-filter@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))

    OTServer.objects.create(
        name="Atlas",
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

    mocked_characters = [_build_character(index) for index in range(25)]

    client = Client()
    assert client.login(username=user.email, password="StrongPass123!")

    with patch("accounts.views.list_otserver_characters") as list_mock:
        list_mock.return_value = {
            "characters": mocked_characters,
            "errors": [],
            "available_vocations": ["Druid", "Knight"],
        }
        response = client.get(
            reverse("accounts:characters"),
            {
                "otserver": "1",
                "q": "Character",
                "vocation": "Knight",
                "status": "online",
                "min_level": "10",
                "max_level": "99",
                "order": "level_desc",
                "page": 2,
            },
        )

    assert response.status_code == 200
    assert response.context is not None
    assert response.context["is_paginated"] is True
    assert len(response.context["characters"]) == 5
    assert response.context["filters"]["order"] == "level_desc"
    assert "?page=1&otserver=1" in response.content.decode("utf-8")

    called_kwargs = list_mock.call_args.kwargs
    assert called_kwargs["otserver_pk"] == "1"
    assert called_kwargs["search"] == "Character"
    assert called_kwargs["vocation"] == "Knight"
    assert called_kwargs["status"] == "online"
    assert called_kwargs["min_level"] == 10
    assert called_kwargs["max_level"] == 99
    assert called_kwargs["order"] == "level_desc"


@pytest.mark.django_db
def test_characters_page_is_translated_to_portuguese() -> None:
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email="characters-lang@example.com", password="StrongPass123!"
    )
    user.user_permissions.add(Permission.objects.get(codename="view_otserver"))

    client = Client()
    client.post(reverse("set_language"), {"language": "pt-br", "next": "/"})
    assert client.login(username=user.email, password="StrongPass123!")

    with patch("accounts.views.list_otserver_characters") as list_mock:
        list_mock.return_value = {
            "characters": [],
            "errors": [
                {
                    "otserver_name": "Coolify-dev",
                    "message": "Tabela de jogadores não encontrada.",
                }
            ],
            "available_vocations": [],
        }
        response = client.get(reverse("accounts:characters"))

    content = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "Personagens" in content
    assert "Aplicar filtros" in content
    assert "Todas as vocações" in content
    assert "não puderam ser consultados" in content
