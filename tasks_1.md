# Tasks 1 - Authentication Backend (CBV + i18n-ready)

## Objective
Implement an authentication backend using Django CBVs with:
- email + password authentication
- forgot-password and reset-password flow
- internationalization readiness based on translation files
- reuse of Django built-in auth components whenever possible

## Task Checklist
- [x] Create `accounts` app and register it in project settings.
- [x] Implement custom `User` model using `email` as unique identifier.
- [x] Configure `AUTH_USER_MODEL` and create initial migration for accounts.
- [x] Build authentication forms reusing Django auth forms (`AuthenticationForm`, `UserCreationForm`).
- [x] Implement CBVs for:
  - [x] login
  - [x] logout
  - [x] signup
  - [x] forgot password (`PasswordResetView`)
  - [x] password reset done/confirm/complete views
- [x] Expose auth routes under `/accounts/`.
- [x] Add root redirect to login page.
- [x] Add i18n infrastructure in settings:
  - [x] `LocaleMiddleware`
  - [x] `LANGUAGES`
  - [x] `LOCALE_PATHS`
  - [x] `set_language` route
- [x] Add file-based translation catalog: `locale/pt_BR/LC_MESSAGES/django.po`.
- [x] Add authentication templates with translatable strings under `templates/registration/`.
- [x] Configure development email backend for password reset flow.
- [x] Add automated tests for signup, email login, forgot password, and language endpoint.
- [x] Run quality checks:
  - [x] `ruff check .`
  - [x] `pytest -q`

## Acceptance Criteria
- [x] User can sign up with email and password.
- [x] User can log in using email + password.
- [x] User can request password reset via forgot-password flow.
- [x] Password reset email is generated correctly.
- [x] Project is prepared for multilingual UI via translation files.
- [x] Authentication logic is implemented with CBVs.
- [x] Test suite passes.
