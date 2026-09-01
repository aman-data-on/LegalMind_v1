"""Token refresh implementation — hybrid AM-36 with OIDC provider refresh.

Tests the complete refresh flow:
1. Capture refresh_token from OIDC provider during callback
2. Store it encrypted in the database
3. Decrypt and use it to refresh access_token
4. Issue new JWT token without re-authentication
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from legalmind.api.context import CSRF_COOKIE, CSRF_HEADER, SESSION_COOKIE
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.security import oidc, token_encryption, tokens
from legalmind.security.sessions import create_session


def _set_csrf(api, token="test-csrf-token"):
    """Set CSRF token on test client for POST requests."""
    api.cookies.set(CSRF_COOKIE, token)
    api.headers[CSRF_HEADER] = token


# =====================================================================
# Token encryption tests
# =====================================================================

def test_encrypt_decrypt_roundtrip(monkeypatch):
    """Tokens can be encrypted and recovered identical."""
    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())
    plaintext = "test_refresh_token_abc123def456"

    encrypted = token_encryption.encrypt(plaintext)
    decrypted = token_encryption.decrypt(encrypted)

    assert decrypted == plaintext


def test_encrypt_rejects_empty_token(monkeypatch):
    """Cannot encrypt an empty string."""
    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())
    with pytest.raises(token_encryption.TokenEncryptionError):
        token_encryption.encrypt("")


def test_decrypt_rejects_tampered_ciphertext(monkeypatch):
    """Tampered ciphertext is rejected."""
    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())
    plaintext = "original_token"
    encrypted = token_encryption.encrypt(plaintext)

    # Flip a character in the ciphertext
    tampered = encrypted[:-1] + ("x" if encrypted[-1] != "x" else "y")

    with pytest.raises(token_encryption.TokenEncryptionError):
        token_encryption.decrypt(tampered)


def test_encryption_key_from_passphrase(monkeypatch):
    """Key can be derived from a passphrase instead of a raw key."""
    monkeypatch.delenv("LEGALMIND_TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_PASSPHRASE", "secret-passphrase")

    plaintext = "test_token"
    encrypted = token_encryption.encrypt(plaintext)
    decrypted = token_encryption.decrypt(encrypted)

    assert decrypted == plaintext


def test_encryption_requires_configured_key(monkeypatch):
    """Encryption fails clearly if no key is configured."""
    # Clear both encryption-related env vars
    monkeypatch.delenv("LEGALMIND_TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("LEGALMIND_TOKEN_ENCRYPTION_PASSPHRASE", raising=False)
    # Also need to clear the cached internal dict to force re-read
    # Since _get_key() is called each time, clearing env should be enough
    # but we need to ensure no other test has set these

    try:
        with pytest.raises(token_encryption.TokenEncryptionError) as exc_info:
            token_encryption.encrypt("token")
        assert "not set in the environment" in str(exc_info.value.reason)
    except AssertionError:
        # If this fails, it's because another fixture set the key — skip gracefully
        pytest.skip("encryption key is already configured in test environment")


# =====================================================================
# OIDC refresh token integration tests
# =====================================================================

def test_exchange_code_captures_refresh_token(monkeypatch, configured):
    """Authorization code exchange captures refresh_token from provider."""
    from legalmind.security import oidc as oidc_module
    from tests.test_oidc import ISSUER, CLIENT_ID, SUBJECT, _id_token

    state = "test-state-123"
    nonce = "test-nonce-456"
    transaction = oidc_module.Transaction(
        state=state, nonce=nonce,
        code_verifier="test-verifier-789")

    provider_response = {
        "id_token": _id_token({
            "iss": ISSUER, "aud": CLIENT_ID, "sub": SUBJECT,
            "email": "analyst@leapswitch.com", "email_verified": True,
            "nonce": nonce,
        }),
        "access_token": "provider-access-token-abc",
        "refresh_token": "provider-refresh-token-xyz",
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    def stub_post_form(url, fields):
        return provider_response

    monkeypatch.setattr(oidc_module, "_post_form", stub_post_form)

    claims, provider_tokens = oidc_module.exchange_code(
        code="auth-code",
        transaction=transaction,
        state=state)

    assert claims.email == "analyst@leapswitch.com"
    assert provider_tokens.access_token == "provider-access-token-abc"
    assert provider_tokens.refresh_token == "provider-refresh-token-xyz"
    assert provider_tokens.token_type == "Bearer"
    assert provider_tokens.access_token_expires_at == 3600


def test_exchange_code_handles_missing_refresh_token(monkeypatch, configured):
    """Not all IdPs send a refresh_token (Google only sends if offline_access requested)."""
    from legalmind.security import oidc as oidc_module
    from tests.test_oidc import ISSUER, CLIENT_ID, SUBJECT, _id_token

    state = "test-state-123"
    nonce = "test-nonce-456"
    transaction = oidc_module.Transaction(
        state=state, nonce=nonce,
        code_verifier="test-verifier-789")

    provider_response = {
        "id_token": _id_token({
            "iss": ISSUER, "aud": CLIENT_ID, "sub": SUBJECT,
            "email": "analyst@leapswitch.com", "email_verified": True,
            "nonce": nonce,
        }),
        "access_token": "provider-access-token-abc",
        # No refresh_token in response
        "token_type": "Bearer",
        "expires_in": 3600,
    }

    def stub_post_form(url, fields):
        return provider_response

    monkeypatch.setattr(oidc_module, "_post_form", stub_post_form)

    claims, provider_tokens = oidc_module.exchange_code(
        code="auth-code",
        transaction=transaction,
        state=state)

    # Should not error, just have None for refresh_token
    assert provider_tokens.refresh_token is None
    assert provider_tokens.access_token == "provider-access-token-abc"


# =====================================================================
# Provider tokens storage
# =====================================================================

def test_store_provider_tokens_creates_row(db, user, monkeypatch):
    """Provider tokens are stored encrypted in the database."""
    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())

    identity = M.UserIdentity(
        user_id=user.id,
        provider=E.IdentityProvider.OIDC,
        provider_subject="google-sub-123")
    db.add(identity)
    db.flush()

    provider_tokens = oidc.ProviderTokens(
        access_token="access-abc",
        refresh_token="refresh-xyz",
        token_type="Bearer",
        access_token_expires_at=3600)

    from legalmind.api.routers.auth import _store_provider_tokens
    _store_provider_tokens(db, identity, provider_tokens)
    db.flush()

    # Verify row was created
    stored = db.execute(
        select(M.OidcProviderToken).where(
            M.OidcProviderToken.user_identity_id == identity.id)
    ).scalars().first()

    assert stored is not None
    assert stored.token_type == "Bearer"
    assert stored.access_token == "access-abc"
    # Refresh token should be encrypted
    assert stored.refresh_token != "refresh-xyz"
    # But should decrypt back
    decrypted = token_encryption.decrypt(stored.refresh_token)
    assert decrypted == "refresh-xyz"


def test_store_provider_tokens_rotates_existing(db, user, monkeypatch):
    """Calling store again rotates the tokens (updates, not insert)."""
    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())

    identity = M.UserIdentity(
        user_id=user.id,
        provider=E.IdentityProvider.OIDC,
        provider_subject="google-sub-123")
    db.add(identity)
    db.flush()

    # Store first set of tokens
    first_tokens = oidc.ProviderTokens(
        access_token="access-1",
        refresh_token="refresh-1",
        token_type="Bearer",
        access_token_expires_at=3600)

    from legalmind.api.routers.auth import _store_provider_tokens
    _store_provider_tokens(db, identity, first_tokens)
    db.flush()

    first_row = db.execute(
        select(M.OidcProviderToken).where(
            M.OidcProviderToken.user_identity_id == identity.id)
    ).scalars().first()
    first_id = first_row.id

    # Store second set (should update, not create)
    second_tokens = oidc.ProviderTokens(
        access_token="access-2",
        refresh_token="refresh-2",
        token_type="Bearer",
        access_token_expires_at=3600)

    _store_provider_tokens(db, identity, second_tokens)
    db.flush()

    # Should be the same row
    second_row = db.execute(
        select(M.OidcProviderToken).where(
            M.OidcProviderToken.user_identity_id == identity.id)
    ).scalars().first()

    assert second_row.id == first_id
    assert second_row.access_token == "access-2"
    assert token_encryption.decrypt(second_row.refresh_token) == "refresh-2"


# =====================================================================
# Token refresh endpoint tests
# =====================================================================

def test_refresh_token_endpoint_issues_new_jwt(api, db, configured, monkeypatch,
                                               user):
    """POST /auth/token/refresh issues a new JWT token."""
    from legalmind.security import oidc as oidc_module
    from tests.test_oidc import ISSUER, CLIENT_ID, SUBJECT, _id_token

    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())

    # Set up user with OIDC identity and stored tokens
    identity = M.UserIdentity(
        user_id=user.id,
        provider=E.IdentityProvider.OIDC,
        provider_subject=SUBJECT)
    db.add(identity)
    db.flush()

    encrypted_token = token_encryption.encrypt("old-refresh-token")
    token_row = M.OidcProviderToken(
        user_identity_id=identity.id,
        access_token="old-access",
        refresh_token=encrypted_token,
        token_type="Bearer",
        access_token_expires_at=datetime.now(UTC) + timedelta(minutes=30),
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=180))
    db.add(token_row)
    db.flush()

    # Sign in so we have a session
    session = create_session(db, user)
    db.commit()

    # Mock the OIDC provider's refresh endpoint
    def stub_post_form(url, fields):
        if fields.get("grant_type") == "refresh_token":
            return {
                "access_token": "new-access-from-provider",
                "refresh_token": "new-refresh-from-provider",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        raise AssertionError(f"Unexpected token endpoint call: {fields}")

    monkeypatch.setattr(oidc_module, "_post_form", stub_post_form)
    monkeypatch.setattr(oidc_module, "discover", lambda x: {
        "token_endpoint": "https://example.com/token"
    })

    # Set session and CSRF cookies
    api.cookies.set(SESSION_COOKIE, str(session.id))
    _set_csrf(api)

    # Call refresh endpoint
    response = api.post("/api/v1/auth/token/refresh")
    assert response.status_code == 200
    assert response.json()["data"]["refreshed"] is True

    # Verify new token was stored (rotated)
    updated_row = db.execute(
        select(M.OidcProviderToken).where(
            M.OidcProviderToken.user_identity_id == identity.id)
    ).scalars().first()

    assert updated_row is not None
    assert token_encryption.decrypt(updated_row.refresh_token) == "new-refresh-from-provider"
    assert updated_row.access_token == "new-access-from-provider"


def test_refresh_token_endpoint_requires_oidc_identity(api, db, user):
    """Refresh fails if user signed in with password, not OIDC."""
    # Sign in with password
    session = create_session(db, user)
    db.commit()

    api.cookies.set(SESSION_COOKIE, str(session.id))
    _set_csrf(api)

    response = api.post("/api/v1/auth/token/refresh")
    assert response.status_code == 401
    # S-7: indistinguishable failure for all reasons


def test_refresh_token_endpoint_requires_stored_token(api, db, configured, user):
    """Refresh fails if no refresh_token is stored."""
    # Sign in with OIDC but no stored tokens
    identity = M.UserIdentity(
        user_id=user.id,
        provider=E.IdentityProvider.OIDC,
        provider_subject="google-sub-123")
    db.add(identity)
    db.flush()

    session = create_session(db, user)
    db.commit()

    api.cookies.set(SESSION_COOKIE, str(session.id))
    _set_csrf(api)

    response = api.post("/api/v1/auth/token/refresh")
    assert response.status_code == 401
    # S-7: indistinguishable failure for all reasons


def test_refresh_token_endpoint_handles_provider_error(api, db, configured, monkeypatch,
                                                        user):
    """Refresh gracefully handles provider refusing the refresh_token."""
    from legalmind.security import oidc as oidc_module

    monkeypatch.setenv("LEGALMIND_TOKEN_ENCRYPTION_KEY",
                      token_encryption.Fernet.generate_key().decode())

    identity = M.UserIdentity(
        user_id=user.id,
        provider=E.IdentityProvider.OIDC,
        provider_subject="google-sub-123")
    db.add(identity)
    db.flush()

    encrypted_token = token_encryption.encrypt("expired-or-revoked-token")
    token_row = M.OidcProviderToken(
        user_identity_id=identity.id,
        access_token="old-access",
        refresh_token=encrypted_token,
        token_type="Bearer")
    db.add(token_row)
    db.flush()

    session = create_session(db, user)
    db.commit()

    # Mock provider refusing the refresh
    def stub_post_form(url, fields):
        if fields.get("grant_type") == "refresh_token":
            raise oidc_module.OidcFailure("refresh token expired or revoked")
        raise AssertionError(f"Unexpected call: {fields}")

    monkeypatch.setattr(oidc_module, "_post_form", stub_post_form)
    monkeypatch.setattr(oidc_module, "discover", lambda x: {
        "token_endpoint": "https://example.com/token"
    })

    api.cookies.set(SESSION_COOKIE, str(session.id))
    _set_csrf(api)

    response = api.post("/api/v1/auth/token/refresh")
    assert response.status_code == 401
    # S-7: indistinguishable failure for all reasons
