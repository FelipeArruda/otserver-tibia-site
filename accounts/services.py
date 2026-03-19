from __future__ import annotations

import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.http import HttpRequest
from django.utils import timezone, translation
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


def _localized_runtime_text(*, en: str, pt: str) -> str:
    language = (translation.get_language() or "").lower()
    return pt if language.startswith("pt") else en


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


def inspect_otserver_schema(
    *,
    database_engine: str,
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    db_charset: str,
    db_use_ssl: bool,
    timeout_seconds: int = 5,
) -> dict[str, object]:
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except Exception as exc:
        raise RuntimeError(_("PyMySQL dependency is not installed.")) from exc

    if database_engine not in {"mysql", "mariadb"}:
        raise RuntimeError(_("Unsupported database engine."))

    connect_kwargs: dict[str, Any] = {
        "host": db_host,
        "port": int(db_port),
        "user": db_user,
        "password": db_password,
        "database": db_name,
        "charset": db_charset or "utf8mb4",
        "connect_timeout": timeout_seconds,
        "cursorclass": DictCursor,
    }
    if db_use_ssl:
        connect_kwargs["ssl"] = {}

    connection = pymysql.connect(**connect_kwargs)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            table_rows = cursor.fetchall()
            table_names = sorted(
                {
                    str(next(iter(row.values()))).strip()
                    for row in table_rows
                    if isinstance(row, dict) and row
                },
                key=lambda value: value.casefold(),
            )
            columns_by_table: dict[str, list[str]] = {}
            for table_name in table_names:
                cursor.execute(f"SHOW COLUMNS FROM {_quote_identifier(table_name)}")
                columns = sorted(
                    {
                        str(column.get("Field", "")).strip()
                        for column in cursor.fetchall()
                        if isinstance(column, dict)
                        and str(column.get("Field", "")).strip()
                    },
                    key=lambda value: value.casefold(),
                )
                columns_by_table[table_name] = columns
    finally:
        connection.close()

    return {
        "tables": table_names,
        "columns_by_table": columns_by_table,
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
            schema_mapping = _get_server_schema_mapping(server=server)
            players_table_name = _resolve_players_table_name_from_cursor(
                cursor=cursor,
                configured_table_name=str(
                    schema_mapping.get("players_table", "")
                ).strip(),
            )
            cursor.execute(f"SHOW COLUMNS FROM {_quote_identifier(players_table_name)}")
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
            account_selects, account_join_sql = _resolve_account_source(
                cursor=cursor,
                players_columns=available_columns,
                schema_mapping=schema_mapping,
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
            select_parts.extend(account_selects)
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
                f"FROM {_quote_identifier(players_table_name)} AS players "
                f"{online_join_sql} {account_join_sql}"
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
                "account_id": _as_int_or_none(row.get("account_id")),
                "account_name": _as_text_or_empty(row.get("account_name")),
                "account_email": _as_text_or_empty(row.get("account_email")),
                "account_type": _translate_account_type(row.get("account_type")),
                "account_created_at": _as_datetime_or_none(
                    row.get("account_created_at")
                ),
                "account_last_login": _as_datetime_or_none(
                    row.get("account_last_login")
                ),
                "account_real_name": _as_text_or_empty(row.get("account_real_name")),
                "account_location": _as_text_or_empty(row.get("account_location")),
                "account_country": _as_text_or_empty(row.get("account_country")),
                "account_premium_points": _as_int_or_none(
                    row.get("account_premium_points")
                ),
                "account_premdays": _as_int_or_none(row.get("account_premdays")),
                "account_coins": _as_int_or_none(row.get("account_coins")),
            }
        )
    return characters


def fetch_otserver_character_deaths(
    *,
    server: OTServer,
    character_name: str,
    limit: int = 10,
    timeout_seconds: int = 5,
) -> list[dict[str, Any]]:
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except Exception as exc:
        raise RuntimeError(_("PyMySQL dependency is not installed.")) from exc

    if server.database_engine not in {"mysql", "mariadb"}:
        raise RuntimeError(_("Unsupported database engine."))

    normalized_name = character_name.strip()
    if not normalized_name:
        return []

    query_limit = max(1, min(int(limit), 50))
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

    schema_mapping = _get_server_schema_mapping(server=server)
    connection = pymysql.connect(**connect_kwargs)
    try:
        with connection.cursor() as cursor:
            players_table_name = _resolve_players_table_name_from_cursor(
                cursor=cursor,
                configured_table_name=str(
                    schema_mapping.get("players_table", "")
                ).strip(),
            )
            if not players_table_name:
                return []
            death_table_name = _resolve_death_table_name(
                cursor=cursor,
                configured_table_name=str(
                    schema_mapping.get("deaths_table", "")
                ).strip(),
            )
            if not death_table_name:
                return []

            cursor.execute(f"SHOW COLUMNS FROM {_quote_identifier(players_table_name)}")
            player_columns = {
                str(column.get("Field", "")).lower()
                for column in cursor.fetchall()
                if isinstance(column, dict)
            }
            cursor.execute(f"SHOW COLUMNS FROM {_quote_identifier(death_table_name)}")
            death_columns = {
                str(column.get("Field", "")).lower()
                for column in cursor.fetchall()
                if isinstance(column, dict)
            }

            if "name" not in player_columns:
                return []
            configured_player_id_column = (
                str(schema_mapping.get("player_id_column", "")).strip().lower()
            )
            player_id_column = _first_available_column(
                player_columns,
                (configured_player_id_column,)
                if configured_player_id_column
                else ("id", "player_id", "playerid", "guid"),
            )
            configured_death_player_id_column = (
                str(schema_mapping.get("death_player_id_column", "")).strip().lower()
            )
            death_player_id_column = _first_available_column(
                death_columns,
                (configured_death_player_id_column,)
                if configured_death_player_id_column
                else ("player_id", "playerid", "pid"),
            )
            if not player_id_column or not death_player_id_column:
                return []

            configured_death_time_column = (
                str(schema_mapping.get("death_time_column", "")).strip().lower()
            )
            death_date_column = _first_available_column(
                death_columns,
                (configured_death_time_column,)
                if configured_death_time_column
                else ("date", "time", "created_at", "death_at"),
            )
            configured_death_level_column = (
                str(schema_mapping.get("death_level_column", "")).strip().lower()
            )
            death_level_column = _first_available_column(
                death_columns,
                (configured_death_level_column,)
                if configured_death_level_column
                else ("level",),
            )
            configured_death_killer_column = (
                str(schema_mapping.get("death_killer_column", "")).strip().lower()
            )
            death_killer_column = _first_available_column(
                death_columns,
                (configured_death_killer_column,)
                if configured_death_killer_column
                else ("killed_by", "killer", "mostdamage_by", "by"),
            )
            death_id_column = _first_available_column(
                death_columns, ("id", "death_id", "deathid")
            )
            if not death_date_column and not death_id_column:
                return []

            cursor.execute(
                "SELECT "
                f"{_quote_identifier(player_id_column)} AS player_id "
                f"FROM {_quote_identifier(players_table_name)} WHERE name = %s LIMIT 1",
                (normalized_name,),
            )
            player_row = cursor.fetchone() or {}
            player_id = _as_int_or_none(player_row.get("player_id"))
            if player_id is None:
                return []

            select_parts = []
            if death_date_column:
                select_parts.append(
                    f"death.{_quote_identifier(death_date_column)} AS occurred_at"
                )
            else:
                select_parts.append("NULL AS occurred_at")
            if death_level_column:
                select_parts.append(
                    f"death.{_quote_identifier(death_level_column)} AS death_level"
                )
            else:
                select_parts.append("NULL AS death_level")
            if death_killer_column:
                select_parts.append(
                    f"death.{_quote_identifier(death_killer_column)} AS killed_by"
                )
            else:
                select_parts.append("NULL AS killed_by")
            if death_id_column:
                select_parts.append(f"death.{_quote_identifier(death_id_column)} AS id")
            else:
                select_parts.append("NULL AS id")

            order_by_column = (
                f"death.{_quote_identifier(death_date_column)}"
                if death_date_column
                else f"death.{_quote_identifier(death_id_column)}"
            )
            cursor.execute(
                "SELECT "
                + ", ".join(select_parts)
                + f" FROM {_quote_identifier(death_table_name)} AS death "
                + f"WHERE death.{_quote_identifier(death_player_id_column)} = %s "
                + f"ORDER BY {order_by_column} DESC LIMIT {query_limit}",
                (player_id,),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    deaths: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        deaths.append(
            {
                "occurred_at": _as_datetime_or_none(row.get("occurred_at")),
                "level": _as_int_or_none(row.get("death_level")),
                "killed_by": _as_text_or_empty(row.get("killed_by")),
            }
        )
    return deaths


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
    account_id: str = "",
    account_email: str = "",
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
        account_id=account_id,
        account_email=account_email,
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
    account_id: str = "",
    account_email: str = "",
) -> list[dict[str, Any]]:
    normalized_vocation = vocation.strip().casefold()
    normalized_status = status.strip().lower()
    normalized_account_email = account_email.strip().casefold()
    normalized_account_id = account_id.strip()

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
        if normalized_account_id:
            current_account_id = character.get("account_id")
            if str(current_account_id) != normalized_account_id:
                continue
        if normalized_account_email:
            character_account_email = (
                str(character.get("account_email", "")).strip().casefold()
            )
            if normalized_account_email not in character_account_email:
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


def _translate_account_type(value: object) -> str:
    account_type_code = _as_int_or_none(value)
    if account_type_code is None:
        return _as_text_or_empty(value)
    return {
        0: "None",
        1: "Player",
        2: "Tutor",
        3: "SeniorTutor",
        4: "GameMaster",
        5: "GOD",
    }.get(account_type_code, str(account_type_code))


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


def _resolve_account_source(
    *,
    cursor: Any,
    players_columns: set[str],
    schema_mapping: dict[str, Any] | None = None,
) -> tuple[list[str], str]:
    configured_player_group_column = ""
    if isinstance(schema_mapping, dict):
        configured_player_group_column = str(
            schema_mapping.get("player_group_id_column", "")
        ).strip()
    players_account_key = _first_available_column(
        players_columns,
        ("account_id", "account", "accountid"),
    )
    account_type_key = _first_available_column(
        players_columns,
        (configured_player_group_column.lower(),)
        if configured_player_group_column
        else ("group_id", "groupid", "group"),
    )
    account_id_select = (
        f"players.{_quote_identifier(players_account_key)} AS account_id"
        if players_account_key
        else "NULL AS account_id"
    )
    account_type_select = (
        f"players.{_quote_identifier(account_type_key)} AS account_type"
        if account_type_key
        else "NULL AS account_type"
    )
    select_parts = [
        account_id_select,
        "NULL AS account_name",
        "NULL AS account_email",
        account_type_select,
        "NULL AS account_created_at",
        "NULL AS account_last_login",
        "NULL AS account_real_name",
        "NULL AS account_location",
        "NULL AS account_country",
        "NULL AS account_premium_points",
        "NULL AS account_premdays",
        "NULL AS account_coins",
    ]
    if not players_account_key:
        return select_parts, ""

    account_table_name = _resolve_account_table_name(cursor=cursor)
    if not account_table_name:
        return select_parts, ""

    cursor.execute(f"SHOW COLUMNS FROM {_quote_identifier(account_table_name)}")
    account_columns = {
        str(column.get("Field", "")).lower()
        for column in cursor.fetchall()
        if isinstance(column, dict)
    }
    account_key = _first_available_column(
        account_columns, ("id", "account_id", "accountid")
    )
    if not account_key:
        return select_parts, ""

    account_name_column = _first_available_column(
        account_columns, ("name", "account_name")
    )
    account_email_column = _first_available_column(
        account_columns,
        ("email", "account_email"),
    )
    account_created_column = _first_available_column(
        account_columns,
        ("created_at", "created", "creation"),
    )
    account_last_login_column = _first_available_column(
        account_columns,
        ("last_login", "lastlogin", "web_lastlogin", "lastday"),
    )
    account_real_name_column = _first_available_column(
        account_columns,
        ("rlname", "real_name"),
    )
    account_location_column = _first_available_column(account_columns, ("location",))
    account_country_column = _first_available_column(account_columns, ("country",))
    account_premium_points_column = _first_available_column(
        account_columns,
        ("premium_points",),
    )
    account_premdays_column = _first_available_column(account_columns, ("premdays",))
    account_coins_column = _first_available_column(account_columns, ("coins",))

    select_parts = [
        account_id_select,
        (
            f"account_table.{_quote_identifier(account_name_column)} AS account_name"
            if account_name_column
            else "NULL AS account_name"
        ),
        (
            f"account_table.{_quote_identifier(account_email_column)} AS account_email"
            if account_email_column
            else "NULL AS account_email"
        ),
        (account_type_select),
        (
            f"account_table.{_quote_identifier(account_created_column)} AS account_created_at"
            if account_created_column
            else "NULL AS account_created_at"
        ),
        (
            f"account_table.{_quote_identifier(account_last_login_column)} AS account_last_login"
            if account_last_login_column
            else "NULL AS account_last_login"
        ),
        (
            f"account_table.{_quote_identifier(account_real_name_column)} AS account_real_name"
            if account_real_name_column
            else "NULL AS account_real_name"
        ),
        (
            f"account_table.{_quote_identifier(account_location_column)} AS account_location"
            if account_location_column
            else "NULL AS account_location"
        ),
        (
            f"account_table.{_quote_identifier(account_country_column)} AS account_country"
            if account_country_column
            else "NULL AS account_country"
        ),
        (
            f"account_table.{_quote_identifier(account_premium_points_column)} AS account_premium_points"
            if account_premium_points_column
            else "NULL AS account_premium_points"
        ),
        (
            f"account_table.{_quote_identifier(account_premdays_column)} AS account_premdays"
            if account_premdays_column
            else "NULL AS account_premdays"
        ),
        (
            f"account_table.{_quote_identifier(account_coins_column)} AS account_coins"
            if account_coins_column
            else "NULL AS account_coins"
        ),
    ]
    join_sql = (
        f"INNER JOIN {_quote_identifier(account_table_name)} AS account_table "
        f"ON account_table.{_quote_identifier(account_key)} = "
        f"players.{_quote_identifier(players_account_key)}"
    )
    return select_parts, join_sql


def _resolve_account_table_name(*, cursor: Any) -> str:
    for table_name in ("account", "accounts"):
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        if cursor.fetchone() is not None:
            return table_name
    return ""


def _resolve_death_table_name(*, cursor: Any, configured_table_name: str = "") -> str:
    if configured_table_name:
        cursor.execute("SHOW TABLES LIKE %s", (configured_table_name,))
        if cursor.fetchone() is not None:
            return configured_table_name
        raise RuntimeError(
            _localized_runtime_text(
                en="Configured deaths table '%(table)s' not found.",
                pt="Tabela de mortes configurada '%(table)s' não foi encontrada.",
            )
            % {"table": configured_table_name}
        )
    for table_name in ("players_death", "player_deaths", "player_death"):
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        if cursor.fetchone() is not None:
            return table_name
    return ""


def _resolve_players_table_name_from_cursor(
    *, cursor: Any, configured_table_name: str = ""
) -> str:
    if configured_table_name:
        cursor.execute("SHOW TABLES LIKE %s", (configured_table_name,))
        if cursor.fetchone() is not None:
            return configured_table_name
        raise RuntimeError(
            _localized_runtime_text(
                en="Configured players table '%(table)s' not found.",
                pt="Tabela de players configurada '%(table)s' não foi encontrada.",
            )
            % {"table": configured_table_name}
        )
    for table_name in ("players", "player"):
        cursor.execute("SHOW TABLES LIKE %s", (table_name,))
        if cursor.fetchone() is not None:
            return table_name
    raise RuntimeError(_("Players table not found."))


def _get_server_schema_mapping(*, server: OTServer) -> dict[str, Any]:
    schema_mapping = server.schema_mapping
    if isinstance(schema_mapping, dict):
        return schema_mapping
    return {}


def _first_available_column(
    available_columns: set[str], candidates: tuple[str, ...]
) -> str:
    for candidate in candidates:
        if candidate in available_columns:
            return candidate
    return ""


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
