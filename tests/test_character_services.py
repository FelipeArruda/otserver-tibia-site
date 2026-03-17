from datetime import UTC, datetime

from accounts.services import filter_otserver_characters, sort_otserver_characters


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
