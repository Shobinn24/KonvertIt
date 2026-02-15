"""
Abstract base classes defining the core contracts for KonvertIt.

All scrapers, converters, listers, and services implement these interfaces,
enabling polymorphism and loose coupling throughout the application.
"""

from abc import ABC, abstractmethod

from app.core.models import (
    ComplianceResult,
    ListingDraft,
    ListingResult,
    ProfitBreakdown,
    ScrapedProduct,
)


class IScrapeable(ABC):
    """Interface for marketplace scrapers."""

    @abstractmethod
    async def scrape(self, url: str) -> ScrapedProduct:
        """
        Scrape a product page and return structured product data.

        Args:
            url: The product page URL to scrape.

        Returns:
            ScrapedProduct with extracted data.

        Raises:
            ScrapingError: If scraping fails after retries.
            ProductNotFoundError: If the product page doesn't exist.
            CaptchaDetectedError: If a CAPTCHA challenge is encountered.
        """
        ...

    @abstractmethod
    def validate(self, product: ScrapedProduct) -> bool:
        """
        Validate that scraped product data meets minimum quality requirements.

        Args:
            product: The scraped product to validate.

        Returns:
            True if the product data is valid and complete enough for conversion.
        """
        ...


class IConvertable(ABC):
    """Interface for marketplace-specific listing converters."""

    @abstractmethod
    def convert(self, product: ScrapedProduct) -> ListingDraft:
        """
        Convert scraped product data into a listing draft for the target marketplace.

        Args:
            product: Source product data from scraping.

        Returns:
            ListingDraft ready for publishing to the target marketplace.

        Raises:
            ConversionError: If the product cannot be converted.
        """
        ...


class IListable(ABC):
    """Interface for marketplace listing operations."""

    @abstractmethod
    async def create_listing(self, draft: ListingDraft) -> ListingResult:
        """
        Create a new listing on the target marketplace.

        Args:
            draft: The listing draft to publish.

        Returns:
            ListingResult with the created listing details.

        Raises:
            ListingError: If listing creation fails.
            EbayAuthError: If authentication is invalid or expired.
        """
        ...

    @abstractmethod
    async def update_listing(self, listing_id: str, draft: ListingDraft) -> ListingResult:
        """
        Update an existing listing on the target marketplace.

        Args:
            listing_id: The marketplace listing ID to update.
            draft: The updated listing data.

        Returns:
            ListingResult with the updated listing details.
        """
        ...

    @abstractmethod
    async def end_listing(self, listing_id: str, reason: str = "") -> bool:
        """
        End/deactivate a listing on the target marketplace.

        Args:
            listing_id: The marketplace listing ID to end.
            reason: Optional reason for ending the listing.

        Returns:
            True if the listing was successfully ended.
        """
        ...


class IPriceable(ABC):
    """Interface for pricing and profit calculation."""

    @abstractmethod
    def calculate_profit(
        self,
        cost: float,
        sell_price: float,
        category: str | None = None,
    ) -> ProfitBreakdown:
        """
        Calculate detailed profit breakdown for a product.

        Args:
            cost: The product acquisition cost.
            sell_price: The intended selling price.
            category: Optional marketplace category for category-specific fees.

        Returns:
            ProfitBreakdown with itemized fees and profit.
        """
        ...

    @abstractmethod
    def suggest_price(self, cost: float, target_margin: float = 0.20) -> float:
        """
        Calculate a suggested selling price to achieve the target profit margin.

        Args:
            cost: The product acquisition cost.
            target_margin: Desired profit margin as a decimal (default 20%).

        Returns:
            Recommended selling price.
        """
        ...

    @abstractmethod
    def calculate_break_even(self, cost: float) -> float:
        """
        Calculate the minimum selling price to break even (zero profit).

        Args:
            cost: The product acquisition cost.

        Returns:
            Minimum selling price.
        """
        ...


class IComplianceCheckable(ABC):
    """Interface for compliance and brand protection checking."""

    @abstractmethod
    def check_brand(self, brand: str) -> ComplianceResult:
        """
        Check if a brand is protected under VeRO or other IP programs.

        Args:
            brand: The brand name to check.

        Returns:
            ComplianceResult indicating compliance status and risk level.
        """
        ...

    @abstractmethod
    def check_product(self, product: ScrapedProduct) -> ComplianceResult:
        """
        Run full compliance check on a product including brand, keywords, and category.

        Args:
            product: The scraped product to check.

        Returns:
            ComplianceResult with all detected violations.
        """
        ...
