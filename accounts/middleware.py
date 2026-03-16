from __future__ import annotations

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.db.utils import OperationalError, ProgrammingError
from django.http import HttpRequest, HttpResponse
from django.utils import timezone, translation

from accounts.models import PlatformSetting


class PlatformDefaultsMiddleware:
    def __init__(self, get_response: SessionMiddleware) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._should_apply_default_language(request):
            self._apply_language_from_platform(request)

        self._apply_timezone_from_platform()
        return self.get_response(request)

    @staticmethod
    def _should_apply_default_language(request: HttpRequest) -> bool:
        has_cookie_language = bool(request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME))
        has_session_language = bool(
            getattr(request, "session", {}).get("django_language")
        )
        return not has_cookie_language and not has_session_language

    @staticmethod
    def _apply_language_from_platform(request: HttpRequest) -> None:
        try:
            preferred_language = PlatformSetting.get_solo().default_language
        except (OperationalError, ProgrammingError, RuntimeError):
            return

        valid_languages = {code for code, _ in settings.LANGUAGES}
        if preferred_language not in valid_languages:
            return

        translation.activate(preferred_language)
        request.LANGUAGE_CODE = preferred_language

    @staticmethod
    def _apply_timezone_from_platform() -> None:
        try:
            timezone.activate(PlatformSetting.get_solo().default_timezone)
        except (OperationalError, ProgrammingError, RuntimeError):
            timezone.activate(settings.TIME_ZONE)
