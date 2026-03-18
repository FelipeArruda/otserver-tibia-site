from __future__ import annotations

import urllib.error
import urllib.request
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from django.http import HttpRequest
from django.utils.translation import gettext as _

from accounts.models import AuditLog, OTServer, TibiaVacation, TibiaVersion, User


def log_audit_event(
    *,
    request: HttpRequest,
    action: str,
    target: str,
    details: dict[str, object] | None = None,
) -> None:
    actor = request.user if isinstance(request.user, User) else None
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target=target,
        details=details or {},
    )


def check_otserver_connections(
    *,
    database_engine: str,
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    db_charset: str,
    db_use_ssl: bool,
    api_base_url: str = "",
    api_token: str = "",
    timeout_seconds: int = 5,
) -> dict[str, object]:
    db_result: dict[str, object] = {
        "ok": False,
        "latency_ms": None,
        "message": _("Database connection failed."),
    }
    api_result: dict[str, object] = {
        "ok": None,
        "latency_ms": None,
        "message": _("API test skipped."),
    }

    try:
        import pymysql
    except Exception:
        db_result["message"] = _("PyMySQL dependency is not installed.")
    else:
        if database_engine not in {"mysql", "mariadb"}:
            db_result["message"] = _("Unsupported database engine.")
        else:
            connect_kwargs = {
                "host": db_host,
                "port": int(db_port),
                "user": db_user,
                "password": db_password,
                "database": db_name,
                "charset": db_charset or "utf8mb4",
                "connect_timeout": timeout_seconds,
            }
            if db_use_ssl:
                connect_kwargs["ssl"] = {}

            try:
                db_start = perf_counter()
                connection = pymysql.connect(**connect_kwargs)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                connection.close()
                db_latency = int((perf_counter() - db_start) * 1000)
                db_result = {
                    "ok": True,
                    "latency_ms": db_latency,
                    "message": _("Database connection succeeded."),
                }
            except Exception as exc:
                db_result["message"] = str(exc)[:240]

    if api_base_url:
        headers: dict[str, str] = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        request = urllib.request.Request(api_base_url, headers=headers, method="GET")
        try:
            api_start = perf_counter()
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                status_code = response.getcode()
            api_latency = int((perf_counter() - api_start) * 1000)
            api_result = {
                "ok": 200 <= status_code < 400,
                "latency_ms": api_latency,
                "message": f"API status {status_code}.",
            }
        except urllib.error.URLError as exc:
            api_result = {
                "ok": False,
                "latency_ms": None,
                "message": str(exc.reason)[:240],
            }
        except Exception as exc:
            api_result = {
                "ok": False,
                "latency_ms": None,
                "message": str(exc)[:240],
            }

    overall_success = bool(db_result["ok"]) and (
        api_result["ok"] is True or api_result["ok"] is None
    )
    return {
        "success": overall_success,
        "database": db_result,
        "api": api_result,
    }


def fetch_otserver_characters(
    *,
    server: OTServer,
    search: str = "",
    timeout_seconds: int = 5,
) -> list[dict[str, Any]]:
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except Exception as exc:
        raise RuntimeError(_("PyMySQL dependency is not installed.")) from exc

    if server.database_engine not in {"mysql", "mariadb"}:
        raise RuntimeError(_("Unsupported database engine."))

    connect_kwargs: dict[str, Any] = {
        "host": server.db_host,
        "port": int(server.db_port),
        "user": server.db_user,
        "password": server.get_db_password(),
        "database": server.db_name,
        "charset": server.db_charset or "utf8mb4",
        "connect_timeout": timeout_seconds,
        "cursorclass": DictCursor,
    }
    if server.db_use_ssl:
        connect_kwargs["ssl"] = {}

    connection = pymysql.connect(**connect_kwargs)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE %s", ("players",))
            if cursor.fetchone() is None:
                raise RuntimeError(_("Players table not found."))

            cursor.execute("SHOW COLUMNS FROM players")
            available_columns = {
                str(column.get("Field", "")).lower()
                for column in cursor.fetchall()
                if isinstance(column, dict)
            }
            if "name" not in available_columns:
                raise RuntimeError(_("Column 'name' not found in players table."))
            online_join_sql, online_presence_expr = _resolve_online_source(
                cursor=cursor, players_columns=available_columns
            )

            select_parts = [
                "players.name AS name",
                (
                    "players.level AS level"
                    if "level" in available_columns
                    else "NULL AS level"
                ),
                (
                    "players.vocation AS vocation"
                    if "vocation" in available_columns
                    else "NULL AS vocation"
                ),
                (
                    "players.lastlogin AS lastlogin"
                    if "lastlogin" in available_columns
                    else "NULL AS lastlogin"
                ),
            ]
            if online_presence_expr:
                select_parts.append(
                    f"CASE WHEN {online_presence_expr} THEN 1 ELSE 0 END AS online"
                )
            elif "online" in available_columns:
                select_parts.append("players.online AS online")
            else:
                select_parts.append("NULL AS online")

            query = (
                f"SELECT {', '.join(select_parts)} "
                f"FROM players AS players {online_join_sql}"
            )
            params: list[str] = []
            if search:
                query += " WHERE players.name LIKE %s"
                params.append(f"%{search}%")
            query += " ORDER BY players.name ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
    finally:
        connection.close()

    characters: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        name = str(row.get("name", "")).strip()
        if not name:
            continue

        characters.append(
            {
                "name": name,
                "otserver_pk": server.pk,
                "otserver_name": server.name,
                "vocation_id": _as_int_or_none(row.get("vocation")),
                "vocation": _as_text_or_empty(row.get("vocation")),
                "level": _as_int_or_none(row.get("level")),
                "is_online": _as_bool_or_none(row.get("online")),
                "updated_at": _as_datetime_or_none(row.get("lastlogin")),
            }
        )
    return characters


def fetch_otserver_character_summary(
    *,
    server: OTServer,
    timeout_seconds: int = 5,
) -> dict[str, int]:
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except Exception as exc:
        raise RuntimeError(_("PyMySQL dependency is not installed.")) from exc

    if server.database_engine not in {"mysql", "mariadb"}:
        raise RuntimeError(_("Unsupported database engine."))

    connect_kwargs: dict[str, Any] = {
        "host": server.db_host,
        "port": int(server.db_port),
        "user": server.db_user,
        "password": server.get_db_password(),
        "database": server.db_name,
        "charset": server.db_charset or "utf8mb4",
        "connect_timeout": timeout_seconds,
        "cursorclass": DictCursor,
    }
    if server.db_use_ssl:
        connect_kwargs["ssl"] = {}

    connection = pymysql.connect(**connect_kwargs)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE %s", ("players",))
            if cursor.fetchone() is None:
                raise RuntimeError(_("Players table not found."))

            cursor.execute("SHOW COLUMNS FROM players")
            available_columns = {
                str(column.get("Field", "")).lower()
                for column in cursor.fetchall()
                if isinstance(column, dict)
            }
            if "name" not in available_columns:
                raise RuntimeError(_("Column 'name' not found in players table."))
            online_join_sql, online_presence_expr = _resolve_online_source(
                cursor=cursor, players_columns=available_columns
            )

            if online_presence_expr:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS total_characters,
                        SUM(
                            CASE WHEN {online_presence_expr} THEN 1 ELSE 0 END
                        ) AS online_characters
                    FROM players AS players
                    {online_join_sql}
                    """.format(
                        online_presence_expr=online_presence_expr,
                        online_join_sql=online_join_sql,
                    )
                )
                row = cursor.fetchone() or {}
                total = _as_int_or_none(row.get("total_characters")) or 0
                online = _as_int_or_none(row.get("online_characters")) or 0
                offline = max(total - online, 0)
                return {
                    "total_characters": total,
                    "online_characters": online,
                    "offline_characters": offline,
                    "unknown_status_characters": 0,
                }

            if "online" in available_columns:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS total_characters,
                        SUM(CASE WHEN players.online = 1 THEN 1 ELSE 0 END) AS online_characters
                    FROM players AS players
                    """
                )
                row = cursor.fetchone() or {}
                total = _as_int_or_none(row.get("total_characters")) or 0
                online = _as_int_or_none(row.get("online_characters")) or 0
                offline = max(total - online, 0)
                return {
                    "total_characters": total,
                    "online_characters": online,
                    "offline_characters": offline,
                    "unknown_status_characters": 0,
                }

            cursor.execute("SELECT COUNT(*) AS total_characters FROM players")
            row = cursor.fetchone() or {}
            total = _as_int_or_none(row.get("total_characters")) or 0
            return {
                "total_characters": total,
                "online_characters": 0,
                "offline_characters": 0,
                "unknown_status_characters": total,
            }
    finally:
        connection.close()


def summarize_otserver_characters(
    *, servers: list[OTServer], timeout_seconds: int = 5
) -> dict[str, Any]:
    active_servers = [server for server in servers if server.is_active]
    summary = {
        "total_characters": 0,
        "online_characters": 0,
        "offline_characters": 0,
        "unknown_status_characters": 0,
        "active_sources": len(active_servers),
        "healthy_sources": 0,
        "errors": [],
    }

    for server in active_servers:
        try:
            server_summary = fetch_otserver_character_summary(
                server=server, timeout_seconds=timeout_seconds
            )
        except Exception as exc:
            summary["errors"].append(
                {"otserver_name": server.name, "message": str(exc)}
            )
            continue

        summary["healthy_sources"] += 1
        summary["total_characters"] += server_summary["total_characters"]
        summary["online_characters"] += server_summary["online_characters"]
        summary["offline_characters"] += server_summary["offline_characters"]
        summary["unknown_status_characters"] += server_summary[
            "unknown_status_characters"
        ]

    return summary


def list_otserver_characters(
    *,
    servers: list[OTServer],
    search: str = "",
    otserver_pk: str = "",
    vocation: str = "",
    min_level: int | None = None,
    max_level: int | None = None,
    status: str = "",
    order: str = "name_asc",
) -> dict[str, Any]:
    filtered_servers = [server for server in servers if server.is_active]
    if otserver_pk.isdigit():
        filtered_servers = [
            server for server in filtered_servers if str(server.pk) == otserver_pk
        ]

    all_characters: list[dict[str, Any]] = []
    source_errors: list[dict[str, str]] = []
    vacation_map_by_version = _build_vacation_map_by_version(servers=filtered_servers)
    for server in filtered_servers:
        try:
            characters = fetch_otserver_characters(server=server, search=search)
            _apply_vocation_translations(
                characters=characters,
                tibia_version_code=server.tibia_version_id,
                vacation_map_by_version=vacation_map_by_version,
            )
            all_characters.extend(characters)
        except Exception as exc:
            source_errors.append({"otserver_name": server.name, "message": str(exc)})

    filtered_characters = filter_otserver_characters(
        all_characters,
        vocation=vocation,
        min_level=min_level,
        max_level=max_level,
        status=status,
    )
    sorted_characters = sort_otserver_characters(filtered_characters, order=order)
    available_vocations = sorted(
        {
            str(character.get("vocation", "")).strip()
            for character in all_characters
            if str(character.get("vocation", "")).strip()
        },
        key=lambda vocation_name: vocation_name.casefold(),
    )

    return {
        "characters": sorted_characters,
        "errors": source_errors,
        "available_vocations": available_vocations,
    }


def filter_otserver_characters(
    characters: list[dict[str, Any]],
    *,
    vocation: str = "",
    min_level: int | None = None,
    max_level: int | None = None,
    status: str = "",
) -> list[dict[str, Any]]:
    normalized_vocation = vocation.strip().casefold()
    normalized_status = status.strip().lower()

    filtered: list[dict[str, Any]] = []
    for character in characters:
        character_vocation = str(character.get("vocation", "")).strip().casefold()
        character_level = character.get("level")
        character_online = character.get("is_online")

        if normalized_vocation and character_vocation != normalized_vocation:
            continue
        if min_level is not None and not (
            isinstance(character_level, int) and character_level >= min_level
        ):
            continue
        if max_level is not None and not (
            isinstance(character_level, int) and character_level <= max_level
        ):
            continue
        if normalized_status == "online" and character_online is not True:
            continue
        if normalized_status == "offline" and character_online is not False:
            continue

        filtered.append(character)

    return filtered


def sort_otserver_characters(
    characters: list[dict[str, Any]], *, order: str = "name_asc"
) -> list[dict[str, Any]]:
    normalized_order = order.strip().lower()
    if normalized_order == "name_desc":
        return sorted(
            characters,
            key=lambda character: str(character.get("name", "")).casefold(),
            reverse=True,
        )
    if normalized_order == "level_desc":
        return sorted(
            characters,
            key=lambda character: (
                character.get("level") is None,
                -_to_level_value(character.get("level")),
                str(character.get("name", "")).casefold(),
            ),
        )
    if normalized_order == "level_asc":
        return sorted(
            characters,
            key=lambda character: (
                character.get("level") is None,
                _to_level_value(character.get("level")),
                str(character.get("name", "")).casefold(),
            ),
        )
    if normalized_order == "updated_desc":
        return sorted(
            characters,
            key=lambda character: (
                character.get("updated_at") is None,
                -_to_timestamp(character.get("updated_at")),
                str(character.get("name", "")).casefold(),
            ),
        )
    if normalized_order == "updated_asc":
        return sorted(
            characters,
            key=lambda character: (
                character.get("updated_at") is None,
                _to_timestamp(character.get("updated_at")),
                str(character.get("name", "")).casefold(),
            ),
        )
    return sorted(
        characters, key=lambda character: str(character.get("name", "")).casefold()
    )


def _as_text_or_empty(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _as_bool_or_none(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    try:
        return bool(int(str(value).strip()))
    except (TypeError, ValueError):
        normalized = str(value).strip().lower()
        if normalized in {"true", "yes", "online"}:
            return True
        if normalized in {"false", "no", "offline"}:
            return False
        return None


def _as_datetime_or_none(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return datetime.fromtimestamp(float(value), tz=UTC)

    try:
        numeric_value = int(str(value).strip())
    except (TypeError, ValueError):
        return None

    if numeric_value <= 0:
        return None
    return datetime.fromtimestamp(numeric_value, tz=UTC)


def _to_timestamp(value: object) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return -1.0


def _to_level_value(value: object) -> int:
    if isinstance(value, int):
        return value
    return -1


def _resolve_online_source(
    *, cursor: Any, players_columns: set[str]
) -> tuple[str, str]:
    cursor.execute("SHOW TABLES LIKE %s", ("players_online",))
    if cursor.fetchone() is None:
        return "", ""

    cursor.execute("SHOW COLUMNS FROM players_online")
    online_columns = {
        str(column.get("Field", "")).lower()
        for column in cursor.fetchall()
        if isinstance(column, dict)
    }

    candidate_pairs = [
        ("id", "player_id"),
        ("id", "playerid"),
        ("name", "player_name"),
        ("name", "playername"),
        ("name", "name"),
    ]
    for players_column, online_column in candidate_pairs:
        if players_column not in players_columns or online_column not in online_columns:
            continue
        quoted_players_column = _quote_identifier(players_column)
        quoted_online_column = _quote_identifier(online_column)
        join_sql = (
            "LEFT JOIN ("
            f"SELECT DISTINCT {quoted_online_column} AS online_key "
            "FROM players_online"
            ") AS online_players "
            f"ON online_players.online_key = players.{quoted_players_column}"
        )
        return join_sql, "online_players.online_key IS NOT NULL"

    return "", ""


def _quote_identifier(identifier: str) -> str:
    escaped = identifier.replace("`", "``")
    return f"`{escaped}`"


def _build_vacation_map_by_version(
    *, servers: list[OTServer]
) -> dict[str, dict[int, dict[str, str]]]:
    version_codes = {
        server.tibia_version_id
        for server in servers
        if getattr(server, "tibia_version_id", "")
    }
    version_codes.add(TibiaVersion.DEFAULT_CODE)
    if not version_codes:
        return {}

    rows = TibiaVacation.objects.filter(tibia_version_id__in=version_codes).values(
        "tibia_version_id",
        "vocation_id",
        "name",
        "name_pt_br",
    )
    mapping: dict[str, dict[int, dict[str, str]]] = {}
    for row in rows:
        version_code = str(row["tibia_version_id"])
        vocation_id = int(row["vocation_id"])
        mapping.setdefault(version_code, {})[vocation_id] = {
            "name": str(row.get("name", "")).strip(),
            "name_pt_br": str(row.get("name_pt_br", "")).strip(),
        }
    return mapping


def _apply_vocation_translations(
    *,
    characters: list[dict[str, Any]],
    tibia_version_code: str,
    vacation_map_by_version: dict[str, dict[int, dict[str, str]]],
) -> None:
    version_map = vacation_map_by_version.get(tibia_version_code, {})
    if not version_map:
        version_map = vacation_map_by_version.get(TibiaVersion.DEFAULT_CODE, {})
    if not version_map and vacation_map_by_version:
        # Last-resort fallback when the server's Tibia version has no mapped vocations.
        version_map = next(iter(vacation_map_by_version.values()))

    for character in characters:
        vocation_id = character.get("vocation_id")
        if not isinstance(vocation_id, int):
            continue

        vacation = version_map.get(vocation_id)
        if not vacation:
            character["vocation"] = str(vocation_id)
            continue

        name = vacation.get("name", "")
        character["vocation"] = name or str(vocation_id)
