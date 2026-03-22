"""Add user profile fields: name, email verification, and location.

Revision ID: c9d1e2f3a4b5
Revises: b7c3d4e5f6a8
Create Date: 2026-03-22 12:00:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9d1e2f3a4b5"
down_revision = "b7c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Name fields
    op.add_column("users", sa.Column("first_name", sa.Unicode(100), nullable=False, server_default=""))
    op.add_column("users", sa.Column("last_name", sa.Unicode(100), nullable=False, server_default=""))

    # Email verification
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("email_verification_token", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email_verification_sent_at", sa.DateTime(timezone=True), nullable=True))

    # Location fields
    op.add_column("users", sa.Column("city", sa.Unicode(100), nullable=False, server_default=""))
    op.add_column("users", sa.Column("state", sa.Unicode(100), nullable=False, server_default=""))
    op.add_column("users", sa.Column("country", sa.String(2), nullable=False, server_default="US"))
    op.add_column("users", sa.Column("postal_code", sa.String(20), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("users", "postal_code")
    op.drop_column("users", "country")
    op.drop_column("users", "state")
    op.drop_column("users", "city")
    op.drop_column("users", "email_verification_sent_at")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
