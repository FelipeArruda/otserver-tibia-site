from __future__ import annotations

from django.db.utils import OperationalError, ProgrammingError

from accounts.models import PlatformSetting


def platform_settings(request: object) -> dict[str, PlatformSetting | None]:
    try:
        return {"platform_settings": PlatformSetting.get_solo()}
    except (OperationalError, ProgrammingError, RuntimeError):
        return {"platform_settings": None}
