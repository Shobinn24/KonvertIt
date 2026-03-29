"""Add auto-discovery tables, listing product_id FK, and dedup index

Creates:
- auto_discovery_configs table (per-user auto-discovery settings)
- auto_discovery_runs table (run history tracking)
- product_id FK on listings table (for duplicate detection)
- Partial unique index on listings(user_id, product_id) WHERE status IN ('draft','active')

Revision ID: d4e5f6a7b8c9
Revises: c9d1e2f3a4b5
Create Date: 2026-03-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c9d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Listing: add product_id FK + dedup index ─────────────
    op.add_column(
        "listings",
        sa.Column("product_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_listings_product_id",
        "listings",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Backfill product_id on existing listings via the conversion relationship
    # (Conversion already links product_id and listing_id)
    op.execute(
        """
        UPDATE listings
        SET product_id = c.product_id
        FROM conversions c
        WHERE c.listing_id = listings.id
          AND listings.product_id IS NULL
        """
    )

    # If backfill created conflicts (same user+product with multiple active
    # listings), keep the newest and end the older ones so the unique index
    # can be created safely.
    op.execute(
        """
        UPDATE listings
        SET status = 'ended'
        WHERE id IN (
            SELECT l.id
            FROM listings l
            INNER JOIN (
                SELECT user_id, product_id, MAX(created_at) AS newest
                FROM listings
                WHERE status IN ('draft', 'active')
                  AND product_id IS NOT NULL
                GROUP BY user_id, product_id
                HAVING COUNT(*) > 1
            ) dups ON l.user_id = dups.user_id
                  AND l.product_id = dups.product_id
                  AND l.created_at < dups.newest
            WHERE l.status IN ('draft', 'active')
        )
        """
    )

    # Partial unique index: only one draft/active listing per product per user
    op.execute(
        """
        CREATE UNIQUE INDEX ix_listings_user_product_active_dedup
        ON listings (user_id, product_id)
        WHERE status IN ('draft', 'active')
        """
    )

    # ─── Auto-Discovery Config ────────────────────────────────
    op.create_table(
        "auto_discovery_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("auto_publish", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("min_margin_pct", sa.Float, nullable=False, server_default="0.20"),
        sa.Column("max_daily_items", sa.Integer, nullable=False, server_default="10"),
        sa.Column("marketplaces", JSON, nullable=False, server_default='["amazon"]'),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_found_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ─── Auto-Discovery Runs ─────────────────────────────────
    op.create_table(
        "auto_discovery_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "data_source",
            sa.String(50),
            nullable=False,
            server_default="history_fallback",
        ),
        sa.Column("queries_searched", JSON, nullable=False, server_default="[]"),
        sa.Column("products_evaluated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("products_converted", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "products_skipped_duplicate", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "products_skipped_compliance",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "products_skipped_margin", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("errors", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_auto_discovery_runs_user_id", "auto_discovery_runs", ["user_id"]
    )
    op.create_index(
        "ix_auto_discovery_runs_run_at", "auto_discovery_runs", ["run_at"]
    )


def downgrade() -> None:
    # ─── Drop auto-discovery tables ───────────────────────────
    op.drop_index("ix_auto_discovery_runs_run_at", "auto_discovery_runs")
    op.drop_index("ix_auto_discovery_runs_user_id", "auto_discovery_runs")
    op.drop_table("auto_discovery_runs")
    op.drop_table("auto_discovery_configs")

    # ─── Drop listing dedup index + product_id column ─────────
    op.drop_index("ix_listings_user_product_active_dedup", "listings")
    op.drop_constraint("fk_listings_product_id", "listings", type_="foreignkey")
    op.drop_column("listings", "product_id")
