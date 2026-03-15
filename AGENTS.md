# Repository Guidelines

## Project Structure & Module Organization

The Django project lives in [`core/`](/C:/dev/otserver-tibia-site/core), which contains settings, URL routing, and ASGI/WSGI entry points. Tests live in [`tests/`](/C:/dev/otserver-tibia-site/tests); follow the existing flat test layout unless a new app justifies a local `tests.py` or `tests/` package. Product, architecture, database, and roadmap notes are documented in [`docs/`](/C:/dev/otserver-tibia-site/docs). Container and startup files are in the repository root: `Dockerfile.linux`, `Dockerfile.windows`, `docker-compose.yml`, `entrypoint.sh`, and `entrypoint.ps1`.

## Build, Test, and Development Commands

- `pip install -r requirements.txt -r requirements-dev.txt`: install runtime and dev dependencies.
- `python manage.py runserver`: run the app locally.
- `python manage.py migrate`: apply database migrations.
- `docker compose build`: build the local Linux image.
- `docker compose up -d`: start the app in Docker on `http://localhost:8000`.
- `ruff check .`: run lint checks.
- `ruff format --check .`: verify formatting.
- `python manage.py makemigrations --check --dry-run`: ensure model changes are reflected in migrations.
- `pytest -q`: run the test suite used by CI.

## Coding Style & Naming Conventions

Use Python 3.13 and 4-space indentation. Ruff is the formatter and linter; the project uses a line length of 88 and lint rules `E`, `F`, and `I` from [`pyproject.toml`](/C:/dev/otserver-tibia-site/pyproject.toml). Prefer descriptive `snake_case` for Python modules, functions, and variables. Keep Django settings, URLs, and view logic explicit rather than overly abstract.

## Testing Guidelines

Pytest with `pytest-django` is configured in [`pytest.ini`](/C:/dev/otserver-tibia-site/pytest.ini). Valid test file patterns are `tests.py`, `test_*.py`, and `*_tests.py`. Add tests for any behavioral change, especially routing, settings, migrations, and request/response behavior. Run `pytest -q` locally before opening a PR.

## Commit & Pull Request Guidelines

Follow the existing lightweight commit style seen in history: concise, imperative summaries such as `feat: add specialist skill agents`, `Fix Docker CI validation for pull requests`, or `chore(deps-dev): bump ruff...`. Keep commits focused. PRs should include a short description of the change, note any migration or config impact, and link the relevant issue if one exists. For UI or workflow changes, include screenshots or exact reproduction steps.

## Security & Configuration Tips

Do not commit `.env` files, secrets, or local database artifacts. The default app database target is PostgreSQL, with MariaDB mentioned as an option in project docs. Validate Docker and CI changes on both Linux and Windows paths when touching container or workflow files.
