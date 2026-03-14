# OTServ Control Panel

Language: English | [Português (Brasil)](README.md)

Django web panel for managing OTServ/Tibia servers.

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

The container runs migrations automatically at startup (`python manage.py migrate --noinput`) before starting the server.

Local app: `http://localhost:8000`

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

Triggers:

- `push` to `main`
- manual `workflow_dispatch`

Required GitHub repository secrets:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Published tags:

- Linux: `linux-<sha>` and `latest-linux`
- Windows: `windows-<sha>` and `latest-windows`

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
