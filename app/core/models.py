"""
Pydantic domain models for KonvertIt.

These models represent the data flowing through the conversion pipeline:
ScrapedProduct → ListingDraft → ListingResult
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceMarketplace(StrEnum):
    """Supported source marketplaces for scraping."""
    AMAZON = "amazon"
    WALMART = "walmart"


class TargetMarketplace(StrEnum):
    """Supported target marketplaces for listing."""
    EBAY = "ebay"


class RiskLevel(StrEnum):
    """Compliance risk levels for VeRO/IP checking."""
    CLEAR = "clear"
    WARNING = "warning"
    BLOCKED = "blocked"


class ConversionStatus(StrEnum):
    """Status of a conversion operation."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ListingStatus(StrEnum):
    """Status of a marketplace listing."""
    DRAFT = "draft"
    ACTIVE = "active"
    ENDED = "ended"
    ERROR = "error"


class UserTier(StrEnum):
    """User subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ─── Pipeline Models ──────────────────────────────────────────


class ScrapedProduct(BaseModel):
    """Product data extracted from a source marketplace."""

    title: str = Field(..., min_length=1, max_length=500)
    price: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    brand: str = Field(default="", max_length=200)
    images: list[str] = Field(default_factory=list)
    description: str = Field(default="")
    category: str = Field(default="")
    availability: str = Field(default="")
    source_marketplace: SourceMarketplace
    source_url: str
    source_product_id: str = Field(..., min_length=1)
    raw_data: dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now())

    @property
    def has_images(self) -> bool:
        return len(self.images) > 0

    @property
    def is_complete(self) -> bool:
        """Check if the product has all critical fields populated."""
        return bool(self.title and self.price > 0 and self.source_product_id)


class ListingDraft(BaseModel):
    """A prepared listing ready to be published to a target marketplace."""

    title: str = Field(..., min_length=1, max_length=80)
    description_html: str = Field(default="")
    price: float = Field(..., gt=0)
    currency: str = Field(default="USD", max_length=3)
    images: list[str] = Field(default_factory=list, max_length=12)
    category_id: str = Field(default="")
    condition: str = Field(default="New")
    sku: str = Field(default="")
    quantity: int = Field(default=1, ge=1)
    target_marketplace: TargetMarketplace = TargetMarketplace.EBAY
    source_product_id: str = Field(default="")
    source_marketplace: SourceMarketplace | None = None


class ListingResult(BaseModel):
    """Result of a listing creation or update operation."""

    marketplace_item_id: str = Field(default="")
    status: ListingStatus = ListingStatus.DRAFT
    url: str = Field(default="")
    fees_estimate: float = Field(default=0.0)
    error_message: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now())


# ─── Business Logic Models ────────────────────────────────────


class ProfitBreakdown(BaseModel):
    """Detailed profit calculation for a product conversion."""

    cost: float = Field(..., ge=0, description="Product acquisition cost")
    sell_price: float = Field(..., ge=0, description="Intended selling price")
    ebay_fee: float = Field(default=0.0, ge=0, description="eBay final value fee")
    payment_fee: float = Field(default=0.0, ge=0, description="Payment processing fee")
    shipping_cost: float = Field(default=0.0, ge=0, description="Estimated shipping cost")
    profit: float = Field(default=0.0, description="Net profit (can be negative)")
    margin_pct: float = Field(default=0.0, description="Profit margin as percentage")

    @property
    def is_profitable(self) -> bool:
        return self.profit > 0

    @property
    def total_fees(self) -> float:
        return self.ebay_fee + self.payment_fee + self.shipping_cost


class ComplianceResult(BaseModel):
    """Result of a VeRO/IP compliance check."""

    is_compliant: bool = Field(default=True, description="Whether the product passes compliance")
    violations: list[str] = Field(default_factory=list, description="List of violation reasons")
    brand: str = Field(default="", description="The brand that was checked")
    risk_level: RiskLevel = Field(default=RiskLevel.CLEAR, description="Overall risk assessment")
    checked_at: datetime = Field(default_factory=lambda: datetime.now())

    @property
    def has_violations(self) -> bool:
        return len(self.violations) > 0
