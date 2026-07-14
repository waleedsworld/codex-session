"""Unit tests for ``utils.crypto`` — Fernet encryption of credentials at rest.

A fixed key is injected via ``ENCRYPTION_KEY`` so the tests never touch the
on-disk ``.storage_key`` file and stay fully deterministic.
"""
import pytest
from cryptography.fernet import Fernet

import utils.crypto as crypto


@pytest.fixture(autouse=True)
def _fixed_key(monkeypatch):
    """Force a known key and clear the module-level cache before each test."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    monkeypatch.setattr(crypto, "_fernet", None)
    yield
    monkeypatch.setattr(crypto, "_fernet", None)


def test_round_trip():
    secret = "super-secret-password-123"
    token = crypto.encrypt(secret)
    assert token != secret
    assert crypto.decrypt(token) == secret


def test_empty_string_passthrough():
    assert crypto.encrypt("") == ""
    assert crypto.decrypt("") == ""


def test_is_encrypted_true_for_ciphertext():
    token = crypto.encrypt("value")
    assert crypto.is_encrypted(token) is True


def test_is_encrypted_false_for_plaintext():
    assert crypto.is_encrypted("value") is False
    assert crypto.is_encrypted("") is False


def test_unicode_round_trip():
    secret = "pä$$wörd — 秘密 🔐"
    assert crypto.decrypt(crypto.encrypt(secret)) == secret


def test_ciphertext_is_non_deterministic():
    # Fernet embeds a random IV/timestamp, so encrypting twice differs
    # while both still decrypt to the same plaintext.
    a = crypto.encrypt("same")
    b = crypto.encrypt("same")
    assert a != b
    assert crypto.decrypt(a) == crypto.decrypt(b) == "same"
