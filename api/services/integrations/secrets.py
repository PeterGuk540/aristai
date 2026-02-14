"""Utilities for encrypting/decrypting integration credentials."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken


def _derive_fernet_key() -> bytes:
    """
    Return a stable Fernet key.

    In production, set INTEGRATIONS_SECRET_KEY to a strong random secret.
    """
    raw = os.getenv("INTEGRATIONS_SECRET_KEY", "").strip()
    if not raw:
        raw = "aristai-integrations-dev-key-change-me"
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_derive_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Could not decrypt integration secret. Check INTEGRATIONS_SECRET_KEY.") from exc
