"""Token encryption for secure storage of refresh tokens — S-6 secrets.

Refresh tokens are provider credentials: they can be used to obtain new access
tokens and should be protected like passwords. This module encrypts them at rest
using Fernet (symmetric encryption via cryptography library).

The encryption key is sourced from the environment (LEGALMIND_TOKEN_ENCRYPTION_KEY),
never generated, and its absence is an operator error surfaced clearly.

Fernet provides:
- AES-128 in CBC mode with a random IV per encryption (no two ciphertexts identical)
- HMAC for authentication (tampered ciphertext is rejected)
- Timestamp in every ciphertext (rotation/expiry checking possible)
- Python stdlib dependency (cryptography is already required for TLS)
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from legalmind.security.errors import Unauthenticated


class TokenEncryptionError(Unauthenticated):
    """Token encryption/decryption failure.

    Subclasses Unauthenticated so a forgotten catch still produces a
    fixed 401 rather than a 500.
    """

    def __init__(self, reason: str):
        super().__init__("token encryption error")
        self.reason = reason


def _get_key() -> bytes:
    """Load or derive the Fernet encryption key from environment.

    The key can be provided in two ways:
    1. LEGALMIND_TOKEN_ENCRYPTION_KEY as a base64-encoded Fernet key
    2. LEGALMIND_TOKEN_ENCRYPTION_PASSPHRASE as a password (derives a key)

    If neither is set, raises an error rather than silently storing plaintext.
    """
    raw_key = os.environ.get("LEGALMIND_TOKEN_ENCRYPTION_KEY", "")
    if raw_key:
        try:
            # Validate it's a valid Fernet key by attempting to instantiate
            Fernet(raw_key.encode())
            return raw_key.encode()
        except Exception as e:
            raise TokenEncryptionError(
                f"LEGALMIND_TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {e}")

    passphrase = os.environ.get("LEGALMIND_TOKEN_ENCRYPTION_PASSPHRASE", "")
    if passphrase:
        # Derive a key from the passphrase using PBKDF2HMAC
        salt = b"legalmind_tokens"  # Fixed salt for deterministic key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
        )
        derived = kdf.derive(passphrase.encode())
        return base64.urlsafe_b64encode(derived)

    raise TokenEncryptionError(
        "neither LEGALMIND_TOKEN_ENCRYPTION_KEY nor "
        "LEGALMIND_TOKEN_ENCRYPTION_PASSPHRASE is set in the environment")


def encrypt(token: str) -> str:
    """Encrypt a token (refresh_token) for storage.

    Returns a base64-encoded ciphertext that can be safely stored in the database.
    """
    if not token:
        raise TokenEncryptionError("cannot encrypt an empty token")
    try:
        key = _get_key()
        cipher = Fernet(key)
        ciphertext = cipher.encrypt(token.encode())
        return ciphertext.decode("ascii")
    except TokenEncryptionError:
        raise
    except Exception as e:
        raise TokenEncryptionError(f"encryption failed: {e}")


def decrypt(ciphertext: str) -> str:
    """Decrypt a stored token (refresh_token).

    Returns the plaintext token ready for use.
    """
    if not ciphertext:
        raise TokenEncryptionError("cannot decrypt an empty ciphertext")
    try:
        key = _get_key()
        cipher = Fernet(key)
        plaintext = cipher.decrypt(ciphertext.encode())
        return plaintext.decode("utf-8")
    except InvalidToken as e:
        raise TokenEncryptionError(f"token is invalid or tampered: {e}")
    except TokenEncryptionError:
        raise
    except Exception as e:
        raise TokenEncryptionError(f"decryption failed: {e}")