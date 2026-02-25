"""
SQLAlchemy 2.0 ORM models for KonvertIt.

All models use the modern Mapped/mapped_column syntax.
Multi-tenant isolation is enforced by scoping all queries through user_id
at the repository layer.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Unicode,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(UTC)


def new_uuid() -> uuid.UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


# ─── User & Authentication ────────────────────────────────────


class User(Base):
    """User account — the multi-tenant root entity."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    email: Mapped[str] = mapped_column(Unicode(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    tier: Mapped[str] = mapped_column(
        SAEnum("free", "pro", "enterprise", name="user_tier"),
        default="free",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Stripe Billing
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    tier_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    ebay_credentials: Mapped[list["EbayCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversions: Mapped[list["Conversion"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EbayCredential(Base):
    """Encrypted eBay OAuth credentials for a user's store connection."""

    __tablename__ = "ebay_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    store_name: Mapped[str] = mapped_column(Unicode(200), default="", nullable=False)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted
    token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sandbox_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="ebay_credentials")

    __table_args__ = (
        Index("ix_ebay_credentials_user_id", "user_id"),
    )


# ─── Products & Conversion Pipeline ──────────────────────────


class Product(Base):
    """Scraped product data from a source marketplace."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_marketplace: Mapped[str] = mapped_column(
        SAEnum("amazon", "walmart", name="source_marketplace"),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(Unicode(500), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    brand: Mapped[str] = mapped_column(Unicode(200), default="", nullable=False)
    category: Mapped[str] = mapped_column(Unicode(500), default="", nullable=False)
    image_urls: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="products")
    conversions: Mapped[list["Conversion"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ix_products_user_source_dedup",
            "user_id", "source_marketplace", "source_product_id",
            unique=True,
        ),
    )


class Conversion(Base):
    """Tracks the lifecycle of a scrape → convert → list operation."""

    __tablename__ = "conversions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "completed", "failed", name="conversion_status"),
        default="pending",
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversions")
    product: Mapped["Product"] = relationship(back_populates="conversions")
    listing: Mapped["Listing | None"] = relationship(back_populates="conversion")

    __table_args__ = (
        Index("ix_conversions_user_id", "user_id"),
        Index("ix_conversions_user_status", "user_id", "status"),
        Index("ix_conversions_status", "status"),
        Index("ix_conversions_product_id", "product_id"),
    )


class Listing(Base):
    """An eBay listing created from a conversion."""

    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ebay_item_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(Unicode(80), nullable=False)
    description_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    ebay_category_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "active", "ended", "error", name="listing_status"),
        default="draft",
        nullable=False,
    )
    listed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="listings")
    conversion: Mapped["Conversion | None"] = relationship(back_populates="listing")

    __table_args__ = (
        Index("ix_listings_user_status", "user_id", "status"),
    )


# ─── Price Tracking ──────────────────────────────────────────


class PriceHistory(Base):
    """Append-only price tracking for monitored products."""

    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_product_time", "product_id", "recorded_at"),
    )


# ─── Infrastructure Tracking ─────────────────────────────────


class ProxyUsage(Base):
    """Proxy health and usage tracking (not user-scoped)."""

    __tablename__ = "proxy_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    proxy_address: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    health_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_proxy_usage_health_active", "health_score", "is_active"),
    )
