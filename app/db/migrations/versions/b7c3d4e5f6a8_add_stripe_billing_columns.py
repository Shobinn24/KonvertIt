"""Add Stripe billing columns to users table.

Revision ID: b7c3d4e5f6a8
Revises: a3f8b2e19c47
Create Date: 2026-02-24 12:00:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b7c3d4e5f6a8"
down_revision = "a3f8b2e19c47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("stripe_subscription_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("tier_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_users_stripe_customer_id", "users", ["stripe_customer_id"], unique=True
    )
    op.create_index(
        "ix_users_stripe_subscription_id", "users", ["stripe_subscription_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_stripe_subscription_id", table_name="users")
    op.drop_index("ix_users_stripe_customer_id", table_name="users")
    op.drop_column("users", "tier_updated_at")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
