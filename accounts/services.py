from __future__ import annotations

import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import (
    AuditLog,
    OTServer,
    PlatformSetting,
    TibiaVacation,
    TibiaVersion,
    User,
)


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


def log_system_audit_event(
    *,
    action: str,
    target: str,
    details: dict[str, object] | None = None,
) -> None:
    AuditLog.objects.create(
        actor=None,
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


def save_otserver_health_check(
    *,
    server: OTServer,
    result: dict[str, object],
    checked_at: datetime | None = None,
) -> None:
    check_time = checked_at or timezone.now()
    database_message = str(result.get("database", {}).get("message", "")).strip()
    api_message = str(result.get("api", {}).get("message", "")).strip()
    combined_message = database_message
    if api_message and api_message != _("API test skipped."):
        combined_message = (
            f"{database_message} | {api_message}" if database_message else api_message
        )

    server.last_health_check_at = check_time
    server.last_health_check_ok = bool(result.get("success"))
    server.last_health_check_message = combined_message[:255]
    server.save(
        update_fields=[
            "last_health_check_at",
            "last_health_check_ok",
            "last_health_check_message",
            "updated_at",
        ]
    )


def run_scheduled_otserver_health_checks(
    *,
    now: datetime | None = None,
    timeout_seconds: int = 5,
) -> list[dict[str, object]]:
    check_time = now or timezone.now()
    monitored_servers = OTServer.objects.filter(
        is_active=True,
        monitor_enabled=True,
    ).order_by("name")
    results: list[dict[str, object]] = []

    for server in monitored_servers:
        interval_minutes = max(int(server.monitor_interval_minutes or 5), 1)
        due_from = check_time - timedelta(minutes=interval_minutes)
        if server.last_health_check_at and server.last_health_check_at > due_from:
            continue

        try:
            result = check_otserver_connections(
                database_engine=server.database_engine,
                db_host=server.db_host,
                db_port=server.db_port,
                db_name=server.db_name,
                db_user=server.db_user,
                db_password=server.get_db_password(),
                db_charset=server.db_charset,
                db_use_ssl=server.db_use_ssl,
                api_base_url=server.api_base_url,
                api_token=server.get_api_token(),
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            result = {
                "success": False,
                "database": {"ok": False, "message": str(exc)[:240]},
                "api": {"ok": None, "message": _("API test skipped.")},
            }
        save_otserver_health_check(server=server, result=result, checked_at=check_time)
        checked_at_local, timezone_name = _format_for_platform_timezone(check_time)
        log_system_audit_event(
            action="otserver.health_check",
            target=server.name,
            details={
                "source": "scheduler",
                "success": result["success"],
                "database_ok": result["database"]["ok"],
                "api_ok": result["api"]["ok"],
                "checked_at": checked_at_local,
                "timezone": timezone_name,
            },
        )
        results.append({"server": server, "result": result})

    return results


def _format_for_platform_timezone(value: datetime) -> tuple[str, str]:
    timezone_name = _get_platform_timezone_name()
    try:
        tzinfo = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tzinfo = timezone.get_default_timezone()
        timezone_name = str(tzinfo)
    localized_value = timezone.localtime(value, tzinfo)
    return localized_value.isoformat(), timezone_name


def _get_platform_timezone_name() -> str:
    try:
        configured_timezone = PlatformSetting.get_solo().default_timezone.strip()
    except Exception:
        configured_timezone = ""
    return configured_timezone or "UTC"


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
    vacation_maps = _build_vacation_maps(servers=filtered_servers)
    for server in filtered_servers:
        try:
            characters = fetch_otserver_characters(server=server, search=search)
            _apply_vocation_translations(
                characters=characters,
                otserver_pk=server.pk,
                tibia_version_code=server.tibia_version_id,
                vacation_maps=vacation_maps,
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


def _build_vacation_maps(*, servers: list[OTServer]) -> dict[str, object]:
    otserver_ids = [server.pk for server in servers]
    version_codes = {
        server.tibia_version_id
        for server in servers
        if getattr(server, "tibia_version_id", "")
    }
    version_codes.add(TibiaVersion.DEFAULT_CODE)
    if not otserver_ids and not version_codes:
        return {"by_otserver": {}, "legacy_by_version": {}}

    by_otserver: dict[int, dict[int, str]] = {}
    legacy_by_version: dict[str, dict[int, str]] = {}
    rows = TibiaVacation.objects.filter(otserver_id__in=otserver_ids).values(
        "otserver_id", "vocation_id", "name"
    )
    for row in rows:
        server_id = int(row["otserver_id"])
        vocation_id = int(row["vocation_id"])
        by_otserver.setdefault(server_id, {})[vocation_id] = str(row["name"]).strip()

    legacy_rows = TibiaVacation.objects.filter(
        otserver__isnull=True,
        tibia_version_id__in=version_codes,
    ).values("tibia_version_id", "vocation_id", "name")
    for row in legacy_rows:
        version_code = str(row["tibia_version_id"])
        vocation_id = int(row["vocation_id"])
        legacy_by_version.setdefault(version_code, {})[vocation_id] = str(
            row["name"]
        ).strip()

    return {"by_otserver": by_otserver, "legacy_by_version": legacy_by_version}


def _apply_vocation_translations(
    *,
    characters: list[dict[str, Any]],
    otserver_pk: int,
    tibia_version_code: str,
    vacation_maps: dict[str, object],
) -> None:
    by_otserver = vacation_maps.get("by_otserver", {})
    legacy_by_version = vacation_maps.get("legacy_by_version", {})
    server_map = (
        by_otserver.get(otserver_pk, {}) if isinstance(by_otserver, dict) else {}
    )
    version_map = (
        legacy_by_version.get(tibia_version_code, {})
        if isinstance(legacy_by_version, dict)
        else {}
    )
    if not version_map and isinstance(legacy_by_version, dict):
        version_map = legacy_by_version.get(TibiaVersion.DEFAULT_CODE, {})
    if not version_map and isinstance(legacy_by_version, dict) and legacy_by_version:
        version_map = next(iter(legacy_by_version.values()))

    for character in characters:
        vocation_id = character.get("vocation_id")
        if not isinstance(vocation_id, int):
            continue

        if vocation_id in server_map:
            character["vocation"] = server_map[vocation_id] or str(vocation_id)
            continue
        if vocation_id in version_map:
            character["vocation"] = version_map[vocation_id] or str(vocation_id)
            continue
        character["vocation"] = str(vocation_id)
