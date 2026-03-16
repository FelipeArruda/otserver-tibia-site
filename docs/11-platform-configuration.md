# 11 - Platform Configuration Guide

## Scope
This guide describes how to operate platform configuration features delivered in `accounts/`:
- Global settings (branding, default language, timezone)
- Per-user language preference
- Audit logs for critical administrative actions

## Global settings
Route: `/accounts/settings/`  
Permission: `accounts.change_platformsetting`

Supported fields:
- Platform name
- Default language (`en`, `pt-br`)
- Default timezone
- Primary color (hex `#RRGGBB`)
- Logo URL

Behavior:
- Values are persisted in a singleton model (`PlatformSetting`).
- Saving language updates current session/cookie immediately.
- New sessions without user preference use global default language.

## User language preference
Route: `POST /accounts/language/`  
Auth required: yes

Behavior:
- Stores selected language in:
  - `User.preferred_language`
  - session (`django_language`)
  - language cookie
- User preference overrides platform default when no explicit session/cookie exists.

## Language precedence
1. Explicit user session/cookie language
2. Authenticated user `preferred_language`
3. Global `PlatformSetting.default_language`

## Audit logs
Route: `/accounts/audit/`  
Permission: `accounts.view_auditlog`

Tracked actions:
- `platform.settings.update`
- `user.create`
- `user.update`
- `user.toggle_active`

Stored data:
- Actor (user)
- Action
- Target
- JSON details
- Timestamp

## i18n maintenance
Update translations:
1. Edit `locale/pt_BR/LC_MESSAGES/django.po`
2. Compile messages:

```bash
python scripts/compile_messages.py
```

3. Validate:

```bash
python manage.py check
pytest -q
```
