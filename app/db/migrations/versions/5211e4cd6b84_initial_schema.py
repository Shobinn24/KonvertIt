"""Initial schema: users, products, conversions, listings, price_history,
ebay_credentials, proxy_usage

Creates the complete KonvertIt database schema with all tables, indices,
foreign keys, and enum types for the multi-marketplace conversion pipeline.

Tables:
    users              — Multi-tenant root entity (accounts, tiers)
    ebay_credentials   — Encrypted eBay OAuth token storage
    products           — Scraped product data from source marketplaces
    conversions        — Pipeline lifecycle tracking (scrape→convert→list)
    listings           — eBay listings created from conversions
    price_history      — Append-only price tracking for monitored products
    proxy_usage        — Proxy health and usage metrics

Revision ID: 5211e4cd6b84
Revises:
Create Date: 2026-02-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5211e4cd6b84"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ─── Custom Enum Types ──────────────────────────────────────

user_tier = sa.Enum("free", "pro", "enterprise", name="user_tier", create_type=False)
source_marketplace = sa.Enum("amazon", "walmart", name="source_marketplace", create_type=False)
conversion_status = sa.Enum(
    "pending", "processing", "completed", "failed", name="conversion_status", create_type=False
)
listing_status = sa.Enum("draft", "active", "ended", "error", name="listing_status", create_type=False)


def upgrade() -> None:
    # Enum types are created automatically by SQLAlchemy's before_create event
    # when create_table references columns with Enum types (via ORM metadata).

    # ─── users ───────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Unicode(320), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("tier", user_tier, nullable=False, server_default="free"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "last_login", sa.DateTime(timezone=True), nullable=True
        ),
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
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ─── ebay_credentials ────────────────────────────────────
    op.create_table(
        "ebay_credentials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "store_name", sa.Unicode(200), nullable=False, server_default=""
        ),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column(
            "token_expiry", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "sandbox_mode",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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

    # ─── products ────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_marketplace", source_marketplace, nullable=False
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_product_id", sa.String(100), nullable=False),
        sa.Column("title", sa.Unicode(500), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column(
            "brand", sa.Unicode(200), nullable=False, server_default=""
        ),
        sa.Column(
            "category", sa.Unicode(500), nullable=False, server_default=""
        ),
        sa.Column(
            "image_urls",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "raw_data",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Unique deduplication index
    op.create_index(
        "ix_products_user_source_dedup",
        "products",
        ["user_id", "source_marketplace", "source_product_id"],
        unique=True,
    )

    # ─── listings ────────────────────────────────────────────
    # Created before conversions since conversions reference listings
    op.create_table(
        "listings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ebay_item_id", sa.String(50), nullable=True),
        sa.Column("title", sa.Unicode(80), nullable=False),
        sa.Column(
            "description_html",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("ebay_category_id", sa.String(20), nullable=True),
        sa.Column(
            "status",
            listing_status,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_synced_at", sa.DateTime(timezone=True), nullable=True
        ),
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
    op.create_index(
        "ix_listings_user_status", "listings", ["user_id", "status"]
    )

    # ─── conversions ─────────────────────────────────────────
    op.create_table(
        "conversions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            conversion_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "converted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ─── price_history ───────────────────────────────────────
    op.create_table(
        "price_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="USD",
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_price_history_product_time",
        "price_history",
        ["product_id", "recorded_at"],
    )

    # ─── proxy_usage ─────────────────────────────────────────
    op.create_table(
        "proxy_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "proxy_address", sa.String(500), nullable=False, unique=True
        ),
        sa.Column(
            "provider", sa.String(50), nullable=False, server_default=""
        ),
        sa.Column(
            "success_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "health_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "last_used_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_proxy_usage_health_active",
        "proxy_usage",
        ["health_score", "is_active"],
    )

    # ─── updated_at trigger function ─────────────────────────
    # Auto-update updated_at on row modification for tables that have it
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )

    # Apply trigger to tables with updated_at column
    for table_name in ("users", "ebay_credentials", "listings"):
        op.execute(
            f"""
            CREATE TRIGGER trigger_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    # Drop triggers first
    for table_name in ("users", "ebay_credentials", "listings"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trigger_{table_name}_updated_at ON {table_name};"
        )
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop indices
    op.drop_index("ix_proxy_usage_health_active", table_name="proxy_usage")
    op.drop_index(
        "ix_price_history_product_time", table_name="price_history"
    )
    op.drop_index("ix_listings_user_status", table_name="listings")
    op.drop_index(
        "ix_products_user_source_dedup", table_name="products"
    )
    op.drop_index("ix_users_email", table_name="users")

    # Drop tables in reverse dependency order
    op.drop_table("proxy_usage")
    op.drop_table("price_history")
    op.drop_table("conversions")
    op.drop_table("listings")
    op.drop_table("products")
    op.drop_table("ebay_credentials")
    op.drop_table("users")

    # Drop enum types
    listing_status.drop(op.get_bind(), checkfirst=True)
    conversion_status.drop(op.get_bind(), checkfirst=True)
    source_marketplace.drop(op.get_bind(), checkfirst=True)
    user_tier.drop(op.get_bind(), checkfirst=True)
