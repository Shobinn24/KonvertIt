"""Add performance indexes for conversions and ebay_credentials

Adds missing indexes on frequently-queried columns to optimize:
- Conversion lookups by user, status, and product
- eBay credential lookups by user

Revision ID: a3f8b2e19c47
Revises: 5211e4cd6b84
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8b2e19c47"
down_revision: Union[str, None] = "5211e4cd6b84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── conversions indexes ──────────────────────────────────
    op.create_index("ix_conversions_user_id", "conversions", ["user_id"])
    op.create_index(
        "ix_conversions_user_status", "conversions", ["user_id", "status"]
    )
    op.create_index("ix_conversions_status", "conversions", ["status"])
    op.create_index("ix_conversions_product_id", "conversions", ["product_id"])

    # ─── ebay_credentials index ───────────────────────────────
    op.create_index(
        "ix_ebay_credentials_user_id", "ebay_credentials", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_ebay_credentials_user_id", table_name="ebay_credentials")
    op.drop_index("ix_conversions_product_id", table_name="conversions")
    op.drop_index("ix_conversions_status", table_name="conversions")
    op.drop_index("ix_conversions_user_status", table_name="conversions")
    op.drop_index("ix_conversions_user_id", table_name="conversions")
