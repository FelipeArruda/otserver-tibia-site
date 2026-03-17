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
- Default timezone (IANA list, e.g. `America/Sao_Paulo`)
- Primary color (hex `#RRGGBB`)
- Logo URL

Behavior:
- Values are persisted in a singleton model (`PlatformSetting`).
- Saving language updates current session/cookie immediately.
- New sessions without user preference use global default language.
- Timezone field is validated against IANA database (`zoneinfo`).
- Platform timezone is activated globally by middleware and applied where date/time rendering is needed (e.g. audit logs).

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

## OTServer management
Routes:
- `/accounts/otservers/`
- `/accounts/otservers/new/`
- `/accounts/otservers/<id>/`
- `/accounts/otservers/<id>/edit/`

Permissions:
- `accounts.view_otserver`
- `accounts.add_otserver`
- `accounts.change_otserver`
- `accounts.delete_otserver`

Supported connections:
- MySQL
- MariaDB

Connection test flow:
- Available on create/edit OTServer form.
- Executes DB connectivity check (`SELECT 1`) and optional API health request.
- Does not persist OTServer data when action is `test_connection`.
- Writes audit event `otserver.connection_test`.

Security for OTServer secrets:
- `db_password` and `api_token` are encrypted at rest.
- Existing plaintext values are migrated and encrypted by migration `0006`.
- UI keeps secrets masked and avoids exposing full values.

Environment variable:
- `OTSERVER_SECRETS_KEY` (optional, strongly recommended in production)
  - If missing, encryption key material falls back to `DJANGO_SECRET_KEY`.

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

Detailed guide:
- See `docs/12-i18n-translation-guide.md`
