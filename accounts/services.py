from __future__ import annotations

import urllib.error
import urllib.request
from time import perf_counter

from django.http import HttpRequest
from django.utils.translation import gettext as _

from accounts.models import AuditLog, User


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
