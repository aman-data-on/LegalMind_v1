"""OIDC provider token storage — refresh token implementation (2026-09-01)

Revision ID: f2c8a1b3d4e5
Revises: e5b8d3f17a2c
Create Date: 2026-09-01

Stores OIDC provider credentials (access_token, refresh_token) to enable
token refresh without re-authentication. This is a hybrid approach that
respects AM-36's stateless JWT decision while adding refresh capability
via the provider's refresh_token grant.

Table structure:
- One row per OIDC identity that has received tokens from the provider
- Refresh tokens are encrypted at rest using Fernet (Python cryptography)
- Access tokens are stored in plaintext (short-lived, ~1h)
- Refresh tokens are long-lived (~6 months for Google)
- Records when each token expires so refresh can be proactive

Security properties (S-6 secrets in environment):
- Token encryption key comes from LEGALMIND_TOKEN_ENCRYPTION_KEY env var
- Tokens are never logged (redacted like credential_hash)
- The table is in the locked schema like other auth data
- Expired refresh tokens are retained for audit trail
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = 'f2c8a1b3d4e5'
down_revision = 'e5b8d3f17a2c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'oidc_provider_tokens',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_identity_id', sa.UUID(), nullable=False),
        # access_token from the authorization code exchange (short-lived, ~1h)
        sa.Column('access_token', sa.Text(), nullable=True),
        # refresh_token for obtaining new access tokens without re-auth
        sa.Column('refresh_token', sa.Text(), nullable=True),
        # The token type, usually "Bearer"
        sa.Column('token_type', sa.String(length=32), nullable=True),
        # When the access_token expires (server time)
        sa.Column('access_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        # When the refresh_token expires (server time)
        sa.Column('refresh_token_expires_at', sa.DateTime(timezone=True), nullable=True),
        # Timestamp of when these tokens were obtained from the provider
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        # Timestamp of the last refresh
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        # Foreign key to user_identities — one-to-one relationship
        sa.ForeignKeyConstraint(['user_identity_id'], ['user_identities.id'],
                                ondelete='CASCADE', name='fk_oidc_tokens_identity'),
        # Primary key
        sa.PrimaryKeyConstraint('id', name='pk_oidc_provider_tokens'),
        # Unique constraint: one token row per identity
        sa.UniqueConstraint('user_identity_id', name='uq_oidc_tokens_identity'),
    )

    # Index for querying by identity
    op.create_index('ix_oidc_tokens_user_identity_id', 'oidc_provider_tokens',
                    ['user_identity_id'])
    # Index for finding expired refresh tokens (audit/cleanup)
    op.create_index('ix_oidc_tokens_refresh_expires', 'oidc_provider_tokens',
                    ['refresh_token_expires_at'])


def downgrade() -> None:
    op.drop_index('ix_oidc_tokens_refresh_expires', table_name='oidc_provider_tokens')
    op.drop_index('ix_oidc_tokens_user_identity_id', table_name='oidc_provider_tokens')
    op.drop_table('oidc_provider_tokens')