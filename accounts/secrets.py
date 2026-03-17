from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

ENCRYPTION_PREFIX = "enc::"


def _build_fernet() -> Fernet:
    secret_source = (
        getattr(settings, "OTSERVER_SECRETS_KEY", "") or settings.SECRET_KEY
    ).encode("utf-8")
    digest = hashlib.sha256(secret_source).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def is_encrypted_secret(value: str) -> bool:
    return bool(value and value.startswith(ENCRYPTION_PREFIX))


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    if is_encrypted_secret(value):
        return value
    token = _build_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTION_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if not is_encrypted_secret(value):
        return value

    token = value.removeprefix(ENCRYPTION_PREFIX)
    try:
        return _build_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
