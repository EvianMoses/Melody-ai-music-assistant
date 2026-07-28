"""Tests for OAuth token encryption at rest (AUTH-006, ADR-007).

Pure-unit: no database, no network, no Google credentials.
"""

from __future__ import annotations

import pytest

from contracts import token_crypto


@pytest.fixture
def key_a() -> str:
    return token_crypto.generate_key()


@pytest.fixture
def key_b() -> str:
    return token_crypto.generate_key()


def test_round_trip(monkeypatch, key_a):
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    ciphertext, key_id = token_crypto.encrypt("ya29.super-secret-access-token")
    assert token_crypto.decrypt(ciphertext) == "ya29.super-secret-access-token"
    assert key_id


def test_ciphertext_does_not_contain_the_plaintext(monkeypatch, key_a):
    """The headline property: the stored column must not reveal the token."""
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    secret = "ya29.super-secret-access-token"
    ciphertext, _ = token_crypto.encrypt(secret)
    assert secret not in ciphertext


def test_key_id_does_not_leak_key_material(monkeypatch, key_a):
    """key_id is persisted in a column and appears in logs -- it must be a
    non-reversible identifier, never the key itself."""
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    _, key_id = token_crypto.encrypt("x")
    assert key_id not in key_a
    assert key_a not in key_id
    assert len(key_id) == 16


def test_missing_key_raises_rather_than_storing_plaintext(monkeypatch):
    """A silent plaintext fallback would defeat the whole control."""
    monkeypatch.delenv(token_crypto.ENV_VAR, raising=False)
    with pytest.raises(token_crypto.TokenCryptoError) as exc_info:
        token_crypto.encrypt("secret")
    assert token_crypto.ENV_VAR in str(exc_info.value)


def test_blank_key_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv(token_crypto.ENV_VAR, "   ")
    with pytest.raises(token_crypto.TokenCryptoError):
        token_crypto.encrypt("secret")


def test_malformed_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv(token_crypto.ENV_VAR, "not-a-valid-fernet-key")
    with pytest.raises(token_crypto.TokenCryptoError) as exc_info:
        token_crypto.encrypt("secret")
    assert "malformed" in str(exc_info.value).lower()


def test_wrong_key_cannot_decrypt(monkeypatch, key_a, key_b):
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    ciphertext, _ = token_crypto.encrypt("secret")

    monkeypatch.setenv(token_crypto.ENV_VAR, key_b)
    with pytest.raises(token_crypto.TokenCryptoError):
        token_crypto.decrypt(ciphertext)


def test_rotation_new_key_encrypts_old_key_still_decrypts(monkeypatch, key_a, key_b):
    """The rotation contract from ADR-007: prepend the new key, keep the old."""
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    old_ciphertext, old_key_id = token_crypto.encrypt("legacy-token")

    # Rotate: new key first, old key retained.
    monkeypatch.setenv(token_crypto.ENV_VAR, f"{key_b},{key_a}")
    assert token_crypto.decrypt(old_ciphertext) == "legacy-token"

    new_ciphertext, new_key_id = token_crypto.encrypt("fresh-token")
    assert new_key_id != old_key_id  # sealed by the new primary key
    assert token_crypto.decrypt(new_ciphertext) == "fresh-token"


def test_decrypt_error_message_does_not_echo_ciphertext(monkeypatch, key_a, key_b):
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    ciphertext, _ = token_crypto.encrypt("secret")
    monkeypatch.setenv(token_crypto.ENV_VAR, key_b)
    with pytest.raises(token_crypto.TokenCryptoError) as exc_info:
        token_crypto.decrypt(ciphertext)
    assert ciphertext not in str(exc_info.value)


def test_encrypt_optional_passes_none_through(monkeypatch, key_a):
    """Google omits the refresh token on re-consent -- that must not crash."""
    monkeypatch.setenv(token_crypto.ENV_VAR, key_a)
    assert token_crypto.encrypt_optional(None) == (None, None)
    ciphertext, key_id = token_crypto.encrypt_optional("refresh-me")
    assert token_crypto.decrypt(ciphertext) == "refresh-me"
    assert key_id
