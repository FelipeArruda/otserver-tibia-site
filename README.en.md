# OTServ Control Panel

Language: English | [Português (Brasil)](README.md)

Django web panel for managing OTServ/Tibia servers.

## Project status

This system is under active development. Features and layout can change frequently.

## Quick access (frontend and backend)

With the project running at `http://127.0.0.1:8000`:

- Public interface (home): `http://127.0.0.1:8000/`
- Main panel (login): `http://127.0.0.1:8000/accounts/login/`
- Django Admin backend: `http://127.0.0.1:8000/admin/`

## Default development credentials

The `python manage.py seed_test_user` command creates/updates the default user:

- Email/Login: `admin@admin.com`
- Password: `admin`

Notes:

- In Docker, this command already runs at startup (`entrypoint.sh` and `entrypoint.ps1`).
- In local execution without Docker, run manually:
  - `python manage.py migrate`
  - `python manage.py seed_test_user`

## Goal

Build a web platform that supports:

- user authentication;
- registration and management of multiple OTServ servers;
- server status checks (online/offline);
- online player count display;
- reading entities from the OTServ database;
- server version selection;
- integrated shop;
- theme system with upload and activation;
- local and container-based execution.

## Main stack

- Backend: Django
- Frontend: Django Templates + Tailwind CSS
- Application database: PostgreSQL (default), with MariaDB option
- Infrastructure: Docker + Docker Compose

## Build and Deploy (Docker)

### Prerequisites

- Docker
- Docker Compose

### Local build (Linux image)

```bash
docker compose build
```

### Run locally

```bash
docker compose up -d
```

The same `docker-compose.yml` works for both local and Coolify.

- Local: keep `WEB_PUBLISHED_PORT=8000`.
- Coolify: set `WEB_PUBLISHED_PORT=0` to avoid host port conflicts.

The container runs migrations automatically at startup (`python manage.py migrate --noinput`) before starting the server.

Local app: `http://localhost:8000`

With the current stack, `docker compose` also starts:

- `redis` (broker/result backend);
- `celery_worker` (asynchronous task execution);
- `celery_beat` (periodic scheduler).

The OTServer health check routine runs automatically via Celery Beat, respecting each OTServer monitoring interval.

### Manual build by Dockerfile

Linux:

```bash
docker build -f Dockerfile.linux -t otserver-tibia-site:linux .
```

Windows:

```powershell
docker build -f Dockerfile.windows -t otserver-tibia-site:windows .
```

Note: Dockerfiles run `python -m pip install --upgrade pip` before installing packages.

## CI/CD (GitHub Actions + Docker Hub)

Workflows:

- `.github/workflows/docker-linux.yml`
- `.github/workflows/docker-windows.yml`
- `.github/workflows/quality.yml`
- `.github/workflows/release.yml`

Triggers:

- `push` to `main`
- `pull_request` to validate Linux and Windows builds without publishing images
- manual `workflow_dispatch`

Required GitHub repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Published tags:

- Linux: `linux-<sha>` and `latest-linux`
- Windows: `windows-<sha>` and `latest-windows`

Behavior by event:

- `pull_request`: builds Linux and Windows only for validation, without Docker Hub login and without push
- `push` to `main` and `workflow_dispatch`: builds and publishes the images

Automated release:

- generates tags in the `vYYYY.MM.DD.N` format (for example, `v2026.03.16.1`)
- if another release runs on the same day, `N` is incremented (`v2026.03.16.2`, `v20260316.3`, ...)
- publishes Docker Hub images using the release version:
  - `${DOCKERHUB_USERNAME}/otserver-tibia-site:vYYYY.MM.DD.N-linux`
  - `${DOCKERHUB_USERNAME}/otserver-tibia-site:vYYYY.MM.DD.N-windows`

Note about local Windows Dockerfile builds:

- on a Linux Docker host, `Dockerfile.windows` cannot be executed end-to-end because the base image is Windows-only
- the real validation for that Dockerfile runs on the GitHub Actions `windows-2022` runner

## Quality and Tests

Dev dependencies:

```bash
pip install -r requirements-dev.txt
```

Local checks:

```bash
ruff check .
ruff format --check .
python manage.py makemigrations --check --dry-run
pytest -q
```

The `quality.yml` workflow runs these checks automatically on push/PR to keep the project healthy.

## Dependency Updates

Dependabot is enabled in `.github/dependabot.yml` to monitor `pip` dependencies (including `requirements.txt`) and open weekly update PRs.

## Current structure

```text
.
|-- core/
|-- docs/
|-- .github/
|-- Dockerfile.linux
|-- Dockerfile.windows
|-- docker-compose.yml
|-- entrypoint.sh
|-- entrypoint.ps1
|-- manage.py
|-- requirements.txt
|-- requirements-dev.txt
|-- pyproject.toml
|-- pytest.ini
|-- tests/
|-- README.en.md
`-- README.md
```

## Languages (i18n)

The language switcher uses `/i18n/setlang/` and the `django_language` cookie.

Whenever you change translations (`locale/*/LC_MESSAGES/django.po`) or `{% trans %}` strings, compile message catalogs:

```bash
python scripts/compile_messages.py
```

Without this step, the language cookie may change but rendered HTML can remain untranslated.


