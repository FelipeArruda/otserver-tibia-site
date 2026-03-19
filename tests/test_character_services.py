from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from django.utils import translation

from accounts import services
from accounts.models import OTServer, TibiaVacation, TibiaVersion
from accounts.services import (
    _resolve_account_source,
    _resolve_online_source,
    filter_otserver_characters,
    list_otserver_characters,
    sort_otserver_characters,
    summarize_otserver_characters,
)


def test_filter_otserver_characters_filters_by_status_vocation_and_level() -> None:
    characters = [
        {
            "name": "Alpha",
            "vocation": "Knight",
            "level": 100,
            "is_online": True,
            "updated_at": datetime(2026, 3, 17, 10, 0, tzinfo=UTC),
        },
        {
            "name": "Beta",
            "vocation": "Druid",
            "level": 80,
            "is_online": False,
            "updated_at": datetime(2026, 3, 17, 9, 0, tzinfo=UTC),
        },
        {
            "name": "Gamma",
            "vocation": "Knight",
            "level": 20,
            "is_online": False,
            "updated_at": None,
        },
    ]

    filtered = filter_otserver_characters(
        characters,
        vocation="Knight",
        min_level=50,
        max_level=120,
        status="online",
    )

    assert len(filtered) == 1
    assert filtered[0]["name"] == "Alpha"


def test_filter_otserver_characters_supports_account_filters() -> None:
    characters = [
        {"name": "Alpha", "account_id": 101, "account_email": "alpha@ot.dev"},
        {"name": "Beta", "account_id": 202, "account_email": "beta@ot.dev"},
    ]

    filtered = filter_otserver_characters(
        characters,
        account_id="202",
        account_email="beta@",
    )

    assert len(filtered) == 1
    assert filtered[0]["name"] == "Beta"


def test_sort_otserver_characters_supports_level_and_updated_sorting() -> None:
    characters = [
        {
            "name": "KnightA",
            "level": 200,
            "updated_at": datetime(2026, 3, 17, 10, 0, tzinfo=UTC),
        },
        {
            "name": "KnightB",
            "level": 350,
            "updated_at": datetime(2026, 3, 17, 12, 0, tzinfo=UTC),
        },
        {
            "name": "KnightC",
            "level": 150,
            "updated_at": None,
        },
    ]

    by_level = sort_otserver_characters(characters, order="level_desc")
    assert [row["name"] for row in by_level] == ["KnightB", "KnightA", "KnightC"]

    by_updated = sort_otserver_characters(characters, order="updated_desc")
    assert [row["name"] for row in by_updated] == ["KnightB", "KnightA", "KnightC"]


def test_summarize_otserver_characters_aggregates_and_handles_errors(
    monkeypatch,
) -> None:
    servers = [
        SimpleNamespace(name="Alpha", is_active=True),
        SimpleNamespace(name="Beta", is_active=True),
        SimpleNamespace(name="Gamma", is_active=False),
    ]

    def fake_summary(*, server, timeout_seconds=5):
        if server.name == "Beta":
            raise RuntimeError("unreachable")
        return {
            "total_characters": 10,
            "online_characters": 4,
            "offline_characters": 5,
            "unknown_status_characters": 1,
        }

    monkeypatch.setattr(services, "fetch_otserver_character_summary", fake_summary)

    result = summarize_otserver_characters(servers=servers)

    assert result["active_sources"] == 2
    assert result["healthy_sources"] == 1
    assert result["total_characters"] == 10
    assert result["online_characters"] == 4
    assert result["offline_characters"] == 5
    assert result["unknown_status_characters"] == 1
    assert result["errors"] == [{"otserver_name": "Beta", "message": "unreachable"}]


@pytest.mark.django_db
def test_list_otserver_characters_translates_vocation_by_tibia_version(
    monkeypatch,
) -> None:
    TibiaVersion.objects.get_or_create(code="15.30", defaults={"sort_order": 1})
    server = OTServer.objects.create(
        name="Crystal",
        tibia_version_id="15.30",
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
    TibiaVacation.objects.update_or_create(
        otserver=server,
        tibia_version_id="15.30",
        vocation_id=4,
        defaults={
            "name": "Knight",
            "name_pt_br": "Cavaleiro",
            "description": "a knight",
            "description_pt_br": "um cavaleiro",
            "base_id": 4,
            "from_voc": 4,
            "client_id": 1,
        },
    )

    def fake_fetch(*, server, search="", timeout_seconds=5):
        del search, timeout_seconds
        return [
            {
                "name": "Knight Sample",
                "otserver_pk": server.pk,
                "otserver_name": server.name,
                "vocation_id": 4,
                "vocation": "4",
                "level": 8,
                "is_online": False,
                "updated_at": None,
            }
        ]

    monkeypatch.setattr(services, "fetch_otserver_characters", fake_fetch)

    with translation.override("pt-br"):
        result = list_otserver_characters(servers=[server])
    assert result["characters"][0]["vocation"] == "Knight"
    assert "Knight" in result["available_vocations"]

    with translation.override("en"):
        result = list_otserver_characters(servers=[server])
    assert result["characters"][0]["vocation"] == "Knight"


@pytest.mark.django_db
def test_list_otserver_characters_falls_back_to_default_version_vocations(
    monkeypatch,
) -> None:
    TibiaVersion.objects.get_or_create(code="15.20", defaults={"sort_order": 1})
    TibiaVersion.objects.get_or_create(code="15.30", defaults={"sort_order": 2})
    server = OTServer.objects.create(
        name="FallbackServer",
        tibia_version_id="15.20",
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
    TibiaVacation.objects.update_or_create(
        otserver=None,
        tibia_version_id="15.30",
        vocation_id=2,
        defaults={
            "name": "Druid",
            "name_pt_br": "Druida",
            "description": "a druid",
            "description_pt_br": "um druida",
            "base_id": 2,
            "from_voc": 2,
            "client_id": 4,
        },
    )

    def fake_fetch(*, server, search="", timeout_seconds=5):
        del search, timeout_seconds
        return [
            {
                "name": "Druid Sample",
                "otserver_pk": server.pk,
                "otserver_name": server.name,
                "vocation_id": 2,
                "vocation": "2",
                "level": 8,
                "is_online": False,
                "updated_at": None,
            }
        ]

    monkeypatch.setattr(services, "fetch_otserver_characters", fake_fetch)

    with translation.override("pt-br"):
        result = list_otserver_characters(servers=[server])

    assert result["characters"][0]["vocation"] == "Druid"


def test_resolve_online_source_prefers_players_online_join_by_player_id() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self._last_query = ""

        def execute(self, query, params=None):  # noqa: ANN001
            del params
            self._last_query = str(query)

        def fetchone(self):  # noqa: ANN201
            if "SHOW TABLES LIKE" in self._last_query:
                return {"Tables_in_db": "players_online"}
            return None

        def fetchall(self):  # noqa: ANN201
            if "SHOW COLUMNS FROM players_online" in self._last_query:
                return [{"Field": "player_id"}]
            return []

    join_sql, presence_expr = _resolve_online_source(
        cursor=FakeCursor(),
        players_columns={"id", "name"},
    )

    assert "players_online" in join_sql
    assert "player_id" in join_sql
    assert "players.`id`" in join_sql
    assert presence_expr == "online_players.online_key IS NOT NULL"


def test_resolve_account_source_builds_safe_join_and_fallback_fields() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self._last_query = ""

        def execute(self, query, params=None):  # noqa: ANN001
            del params
            self._last_query = str(query)

        def fetchone(self):  # noqa: ANN201
            if "SHOW TABLES LIKE" in self._last_query:
                return {"Tables_in_db": "account"}
            return None

        def fetchall(self):  # noqa: ANN201
            if "SHOW COLUMNS FROM `account`" in self._last_query:
                return [
                    {"Field": "id"},
                    {"Field": "email"},
                    {"Field": "created"},
                    {"Field": "lastday"},
                ]
            return []

    select_parts, join_sql = _resolve_account_source(
        cursor=FakeCursor(),
        players_columns={"id", "name", "account_id"},
    )

    assert "INNER JOIN `account` AS account_table" in join_sql
    assert "players.`account_id`" in join_sql
    assert "account_table.`id`" in join_sql
    assert "AS account_id" in select_parts[0]
    assert "AS account_email" in select_parts[2]
    assert "AS account_created_at" in select_parts[4]
    assert "AS account_last_login" in select_parts[5]


def test_resolve_account_source_supports_accounts_table_name() -> None:
    class FakeCursor:
        def __init__(self) -> None:
            self._last_query = ""

        def execute(self, query, params=None):  # noqa: ANN001
            self._last_query = str(query)
            self._params = params

        def fetchone(self):  # noqa: ANN201
            if "SHOW TABLES LIKE" in self._last_query:
                if self._params == ("account",):
                    return None
                if self._params == ("accounts",):
                    return {"Tables_in_db": "accounts"}
            return None

        def fetchall(self):  # noqa: ANN201
            if "SHOW COLUMNS FROM `accounts`" in self._last_query:
                return [
                    {"Field": "id"},
                    {"Field": "name"},
                    {"Field": "email"},
                    {"Field": "type"},
                    {"Field": "created"},
                    {"Field": "web_lastlogin"},
                ]
            return []

    select_parts, join_sql = _resolve_account_source(
        cursor=FakeCursor(),
        players_columns={"id", "name", "account_id"},
    )

    assert "INNER JOIN `accounts` AS account_table" in join_sql
    assert "AS account_name" in select_parts[1]
    assert "AS account_email" in select_parts[2]
    assert "AS account_type" in select_parts[3]
    assert "AS account_created_at" in select_parts[4]
    assert "AS account_last_login" in select_parts[5]
