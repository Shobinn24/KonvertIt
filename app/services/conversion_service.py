"""
Conversion orchestration service.

Orchestrates the full pipeline: scrape → compliance check → convert → price → list.
Supports single URL conversion and bulk conversion with progress tracking.

Supports optional progress callbacks for real-time SSE streaming:
    - on_step: called when the pipeline step changes for an item
    - on_item_complete: called when a single item finishes (success or failure)
    - on_cancel_check: called before each item to check if the job was cancelled
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.converters.ebay_converter import EbayConverter
from app.core.exceptions import (
    ComplianceViolationError,
    ConversionError,
    KonvertItError,
    ListingError,
    ScrapingError,
)
from app.core.models import (
    ComplianceResult,
    ConversionStatus,
    ListingDraft,
    ListingResult,
    ListingStatus,
    ProfitBreakdown,
    RiskLevel,
    ScrapedProduct,
)
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager
from app.scrapers.scraper_factory import ScraperFactory
from app.services.compliance_service import ComplianceService
from app.services.profit_engine import ProfitEngine

logger = logging.getLogger(__name__)

# Callback type aliases for SSE progress streaming
StepCallback = Callable[[str, str], Awaitable[None]]  # (url, step) -> None
ItemCompleteCallback = Callable[
    [int, str, bool, dict | None, str], Awaitable[None]
]  # (index, url, success, result_data, error) -> None
CancelCheck = Callable[[], bool]  # () -> is_cancelled


class ConversionStep(StrEnum):
    """Steps in the conversion pipeline for progress tracking."""
    SCRAPING = "scraping"
    COMPLIANCE = "compliance"
    CONVERTING = "converting"
    PRICING = "pricing"
    LISTING = "listing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ConversionResult:
    """Result of a single URL conversion through the pipeline."""

    url: str
    status: ConversionStatus = ConversionStatus.PENDING
    step: ConversionStep = ConversionStep.SCRAPING
    product: ScrapedProduct | None = None
    compliance: ComplianceResult | None = None
    draft: ListingDraft | None = None
    profit: ProfitBreakdown | None = None
    listing: ListingResult | None = None
    error: str = ""
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    @property
    def is_successful(self) -> bool:
        return self.status == ConversionStatus.COMPLETED

    def to_dict(self) -> dict:
        """Serialize to dict for API responses."""
        return {
            "url": self.url,
            "status": self.status.value,
            "step": self.step.value,
            "product": {
                "title": self.product.title,
                "price": self.product.price,
                "brand": self.product.brand,
                "source_product_id": self.product.source_product_id,
                "image_urls": self.product.images,
                "description": self.product.description,
                "category": self.product.category,
                "source_marketplace": self.product.source_marketplace.value,
            } if self.product else None,
            "compliance": {
                "is_compliant": self.compliance.is_compliant,
                "risk_level": self.compliance.risk_level.value,
                "violations": self.compliance.violations,
            } if self.compliance else None,
            "draft": {
                "title": self.draft.title,
                "price": self.draft.price,
                "sku": self.draft.sku,
            } if self.draft else None,
            "profit": {
                "cost": self.profit.cost,
                "sell_price": self.profit.sell_price,
                "profit": self.profit.profit,
                "margin_pct": self.profit.margin_pct,
                "total_fees": self.profit.total_fees,
            } if self.profit else None,
            "listing": {
                "marketplace_item_id": self.listing.marketplace_item_id,
                "status": self.listing.status.value,
                "url": self.listing.url,
            } if self.listing else None,
            "error": self.error,
        }


@dataclass
class BulkConversionProgress:
    """Progress tracker for bulk conversions."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    results: list[ConversionResult] = field(default_factory=list)

    @property
    def pending(self) -> int:
        return self.total - self.completed - self.failed

    @property
    def progress_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return round(((self.completed + self.failed) / self.total) * 100, 1)

    @property
    def is_done(self) -> bool:
        return self.pending == 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "pending": self.pending,
            "progress_pct": self.progress_pct,
            "results": [r.to_dict() for r in self.results],
        }


def _detect_marketplace(url: str) -> str:
    """Detect source marketplace from URL."""
    url_lower = url.lower()
    if "amazon." in url_lower or "amzn." in url_lower:
        return "amazon"
    elif "walmart." in url_lower:
        return "walmart"
    else:
        raise ConversionError(
            f"Unsupported marketplace URL: {url}",
            details={"url": url, "hint": "Supported: amazon.com, walmart.com"},
        )


class ConversionService:
    """
    Orchestrates the full product conversion pipeline.

    Pipeline steps:
    1. ScraperFactory → scrape product from source URL
    2. ComplianceService → check VeRO compliance
    3. EbayConverter → generate listing draft
    4. ProfitEngine → calculate pricing
    5. EbayLister → publish to eBay (optional, if lister provided)

    Usage:
        service = ConversionService(proxy_manager, browser_manager)
        result = await service.convert_url("https://amazon.com/dp/B09C5RG6KV", user_id)
    """

    def __init__(
        self,
        proxy_manager: ProxyManager,
        browser_manager: BrowserManager,
        compliance_service: ComplianceService | None = None,
        profit_engine: ProfitEngine | None = None,
        ebay_converter: EbayConverter | None = None,
        ebay_lister=None,
        target_margin: float = 0.20,
    ):
        self._proxy_manager = proxy_manager
        self._browser_manager = browser_manager
        self._compliance = compliance_service or ComplianceService()
        self._profit_engine = profit_engine or ProfitEngine()
        self._converter = ebay_converter or EbayConverter()
        self._lister = ebay_lister  # Optional — None means draft-only mode
        self._target_margin = target_margin

    def _get_scraper(self, marketplace: str) -> BaseScraper:
        """Get the appropriate scraper for a marketplace."""
        return ScraperFactory.create(
            marketplace,
            self._proxy_manager,
            self._browser_manager,
        )

    async def convert_url(
        self,
        url: str,
        user_id: str,
        publish: bool = False,
        sell_price: float | None = None,
        on_step: StepCallback | None = None,
    ) -> ConversionResult:
        """
        Convert a product URL through the full pipeline.

        Args:
            url: Source marketplace product URL.
            user_id: The user initiating the conversion.
            publish: If True and lister is configured, publish to eBay.
            sell_price: Override selling price. If None, auto-calculates.
            on_step: Optional async callback invoked on each pipeline step change.
                     Signature: async (url, step_name) -> None

        Returns:
            ConversionResult with pipeline outcome.
        """
        result = ConversionResult(url=url, status=ConversionStatus.PROCESSING)
        logger.info(f"Starting conversion for {url} (user: {user_id})")

        async def _notify_step(step: ConversionStep) -> None:
            """Update result step and fire callback if provided."""
            result.step = step
            if on_step:
                await on_step(url, step.value)

        try:
            # Step 1: Detect marketplace and scrape
            await _notify_step(ConversionStep.SCRAPING)
            marketplace = _detect_marketplace(url)
            scraper = self._get_scraper(marketplace)
            result.product = await scraper.scrape(url)
            logger.info(
                f"Scraped: '{result.product.title[:50]}...' "
                f"(${result.product.price}) from {marketplace}"
            )

            # Step 2: Compliance check
            await _notify_step(ConversionStep.COMPLIANCE)
            result.compliance = self._compliance.check_product(result.product)

            if result.compliance.risk_level == RiskLevel.BLOCKED:
                raise ComplianceViolationError(
                    brand=result.compliance.brand,
                    violations=result.compliance.violations,
                )

            if result.compliance.risk_level == RiskLevel.WARNING:
                logger.warning(
                    f"Compliance warning for '{result.product.brand}': "
                    f"{result.compliance.violations}"
                )

            # Step 3: Convert to eBay listing draft
            await _notify_step(ConversionStep.CONVERTING)
            result.draft = self._converter.convert(result.product)

            # Step 4: Calculate pricing
            await _notify_step(ConversionStep.PRICING)
            cost = result.product.price
            final_price = sell_price or self._profit_engine.suggest_price(
                cost, self._target_margin
            )
            result.draft.price = final_price
            result.profit = self._profit_engine.calculate_profit(
                cost=cost,
                sell_price=final_price,
                category=result.product.category,
            )
            logger.info(
                f"Pricing: cost=${cost:.2f} → sell=${final_price:.2f} "
                f"(profit=${result.profit.profit:.2f}, margin={result.profit.margin_pct:.1f}%)"
            )

            # Step 5: Publish to eBay (optional)
            if publish and self._lister:
                await _notify_step(ConversionStep.LISTING)
                result.listing = await self._lister.create_listing(result.draft)
                logger.info(
                    f"Listed on eBay: {result.listing.marketplace_item_id} "
                    f"({result.listing.status.value})"
                )
            else:
                # Draft mode — listing not published
                result.listing = ListingResult(
                    status=ListingStatus.DRAFT,
                )

            # Success
            await _notify_step(ConversionStep.COMPLETE)
            result.status = ConversionStatus.COMPLETED
            result.completed_at = datetime.now()
            logger.info(f"Conversion complete for {url}")

        except ComplianceViolationError as e:
            result.step = ConversionStep.FAILED
            result.status = ConversionStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            logger.warning(f"Conversion blocked by compliance: {e}")

        except ScrapingError as e:
            result.step = ConversionStep.FAILED
            result.status = ConversionStatus.FAILED
            result.error = f"Scraping failed: {e.message}"
            result.completed_at = datetime.now()
            logger.error(f"Scraping error for {url}: {e}")

        except ListingError as e:
            result.step = ConversionStep.FAILED
            result.status = ConversionStatus.FAILED
            result.error = f"Listing failed: {e.message}"
            result.completed_at = datetime.now()
            logger.error(f"Listing error for {url}: {e}")

        except KonvertItError as e:
            result.step = ConversionStep.FAILED
            result.status = ConversionStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            logger.error(f"Conversion error for {url}: {e}")

        except Exception as e:
            result.step = ConversionStep.FAILED
            result.status = ConversionStatus.FAILED
            result.error = f"Unexpected error: {type(e).__name__}: {e}"
            result.completed_at = datetime.now()
            logger.error(f"Unexpected error converting {url}: {e}", exc_info=True)

        return result

    async def convert_bulk(
        self,
        urls: list[str],
        user_id: str,
        publish: bool = False,
        sell_price: float | None = None,
        on_step: StepCallback | None = None,
        on_item_complete: ItemCompleteCallback | None = None,
        cancel_check: CancelCheck | None = None,
    ) -> BulkConversionProgress:
        """
        Convert multiple product URLs sequentially with progress tracking.

        Args:
            urls: List of source marketplace product URLs.
            user_id: The user initiating the conversions.
            publish: If True, publish each listing to eBay.
            sell_price: Override selling price for all items.
            on_step: Optional async callback for pipeline step changes per item.
            on_item_complete: Optional async callback when each item finishes.
                Signature: async (index, url, success, result_data, error) -> None
            cancel_check: Optional sync function returning True if job is cancelled.
                Checked before each item — allows graceful early termination.

        Returns:
            BulkConversionProgress with all results.
        """
        progress = BulkConversionProgress(total=len(urls))
        logger.info(f"Starting bulk conversion of {len(urls)} URLs (user: {user_id})")

        for i, url in enumerate(urls):
            # Check for cancellation before starting each item
            if cancel_check and cancel_check():
                logger.info(
                    f"Bulk conversion cancelled at item {i + 1}/{len(urls)}"
                )
                break

            logger.info(f"Bulk conversion [{i + 1}/{len(urls)}]: {url}")

            result = await self.convert_url(
                url=url,
                user_id=user_id,
                publish=publish,
                sell_price=sell_price,
                on_step=on_step,
            )

            progress.results.append(result)

            if result.is_successful:
                progress.completed += 1
            else:
                progress.failed += 1

            # Fire item completion callback
            if on_item_complete:
                await on_item_complete(
                    i,
                    url,
                    result.is_successful,
                    result.to_dict() if result.is_successful else None,
                    result.error,
                )

            logger.info(
                f"Bulk progress: {progress.completed} done, "
                f"{progress.failed} failed, {progress.pending} remaining "
                f"({progress.progress_pct}%)"
            )

        logger.info(
            f"Bulk conversion finished: {progress.completed}/{progress.total} successful"
        )
        return progress

    async def preview_conversion(
        self,
        url: str,
        user_id: str,
    ) -> ConversionResult:
        """
        Preview a conversion without publishing — scrape, check, convert, price.

        Same as convert_url with publish=False.
        """
        return await self.convert_url(url=url, user_id=user_id, publish=False)
