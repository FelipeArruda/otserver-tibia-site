# 12 - i18n Translation Guide

## Goal
Keep the interface fully translated (`en` and `pt-br`) across templates, forms, messages and dynamic labels.

## Where translations live
- Source catalog: `locale/pt_BR/LC_MESSAGES/django.po`
- Compiled catalog: `locale/pt_BR/LC_MESSAGES/django.mo`

## How to translate new UI text
1. Mark text in code:
   - Templates: `{% trans "Your text" %}`
   - Python (views/forms/models): `_("Your text")`
2. Add/update `msgid` + `msgstr` in `locale/pt_BR/LC_MESSAGES/django.po`.
3. Compile catalogs:

```bash
python scripts/compile_messages.py
```

4. Validate:

```bash
ruff check .
pytest -q
```

## CI and Docker behavior
- Docker image builds (`Dockerfile.linux` and `Dockerfile.windows`) run `python scripts/compile_messages.py`.
- CI (`quality.yml` and `release.yml`) recompiles catalogs and fails if `locale` changes are detected (`git diff --exit-code -- locale`).
- Keep `django.po` and `django.mo` committed together to avoid pipeline failures.

## Dynamic permission labels
Role screens render permission labels from codename pattern (`add/change/delete/view`) and model verbose name.

Required translation keys in `django.po`:
- `Can add %(model)s`
- `Can change %(model)s`
- `Can delete %(model)s`
- `Can view %(model)s`

## Recommended review checklist
- Switch language via sidebar (`EN` / `BR`) and validate page refresh.
- Check success/error flash messages after save/create/update/delete actions.
- Confirm filters, buttons, section titles and empty states are translated.
- Verify new strings in `users`, `roles`, `role_form`, and `role_detail`.
