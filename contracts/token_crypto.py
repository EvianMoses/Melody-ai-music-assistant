"""Symmetric encryption for stored OAuth token material (ADR-007, AUTH-006).

Section 2.3's data-model rule is absolute: *"OAuth token values are encrypted or
stored in an approved secret store; never plaintext columns."* Everything
written to ``oauth_accounts.encrypted_*_token`` goes through here first.

**Why this lives in ``contracts/`` rather than ``shared_lib/``.** It encrypts a
column defined next door in ``contracts/db_models.py``, so it travels with the
schema it protects, and every service that needs it already does
``COPY contracts /app/contracts``. ``shared_lib`` was the first choice but is
the wrong home here: it is a pip-installed package whose ``__init__`` pulls in
FastAPI, and the Flask app -- the only component that writes this table today --
has no FastAPI dependency and imports from the repo root, where ``shared_lib``
resolves as an empty namespace package. Importing ``contracts.token_crypto``
costs nothing extra to anyone: ``contracts/__init__.py`` is a bare docstring, so
``cryptography`` is only imported by code that actually asks for this module.

Fernet (AES-128-CBC + HMAC-SHA256) is used rather than raw AES-GCM because it is
misuse-resistant: it is authenticated by construction and generates its own IV
per message, so there is no way to accidentally reuse a nonce -- a failure mode
that is silent and catastrophic.

Key rotation: ``OAUTH_TOKEN_ENCRYPTION_KEY`` accepts a comma-separated list.
``MultiFernet`` encrypts with the **first** key and decrypts with **any** of
them, so rotating means prepending a new key and leaving the old one in place
until existing rows are re-encrypted. ``encrypt()`` returns the id of the key it
used, which callers persist alongside the ciphertext
(``oauth_accounts.encryption_key_id``) so it is always knowable which key sealed
a given row.

There is deliberately **no plaintext fallback**. A missing key raises, because
silently storing an unencrypted token would defeat the entire control while
looking like it worked.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

ENV_VAR = "OAUTH_TOKEN_ENCRYPTION_KEY"


class TokenCryptoError(RuntimeError):
    """Configuration or decryption failure. Never carries key or token material."""


def generate_key() -> str:
    """A fresh urlsafe-base64 Fernet key, for setup docs and tests."""
    return Fernet.generate_key().decode()


def _key_id(key: str) -> str:
    """Short, stable, non-reversible identifier for a key.

    A hash prefix rather than the key itself -- this value is persisted in a
    database column and appears in logs, so it must not leak key material while
    still letting an operator tell which key sealed a row.
    """
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _load_keys() -> list[str]:
    raw = os.getenv(ENV_VAR) or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise TokenCryptoError(
            f"{ENV_VAR} is not set. OAuth tokens cannot be stored without it -- "
            "storing them unencrypted is not a supported fallback. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return keys


def _fernet(keys: list[str]) -> MultiFernet:
    try:
        return MultiFernet([Fernet(k.encode()) for k in keys])
    except (ValueError, TypeError) as exc:
        raise TokenCryptoError(
            f"{ENV_VAR} contains a malformed Fernet key "
            "(expected urlsafe base64-encoded 32 bytes)."
        ) from exc


def encrypt(plaintext: str) -> tuple[str, str]:
    """Encrypt with the primary key. Returns (ciphertext, key_id)."""
    keys = _load_keys()
    token = _fernet(keys).encrypt(plaintext.encode())
    return token.decode(), _key_id(keys[0])


def decrypt(ciphertext: str) -> str:
    """Decrypt with any configured key (supports rotation)."""
    keys = _load_keys()
    try:
        return _fernet(keys).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        # Deliberately vague: never echo ciphertext or key material.
        raise TokenCryptoError(
            "Stored token could not be decrypted with any configured key. "
            f"If {ENV_VAR} was rotated or lost, affected users must reconnect."
        ) from exc


def encrypt_optional(plaintext: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """``encrypt`` that tolerates None -- Google omits the refresh token on
    re-consent when one was already issued, so that column is nullable."""
    if plaintext is None:
        return None, None
    return encrypt(plaintext)
