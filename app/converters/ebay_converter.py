"""
eBay listing converter — transforms scraped products into eBay listing drafts.

Phase 2 will add full title optimization, description templating,
and category mapping.
"""

import logging

from app.converters.base_converter import BaseConverter
from app.converters.description_builder import DescriptionBuilder
from app.converters.title_optimizer import TitleOptimizer
from app.core.models import ListingDraft, ScrapedProduct, TargetMarketplace

logger = logging.getLogger(__name__)


class EbayConverter(BaseConverter):
    """
    Converts scraped product data into eBay-ready listing drafts.

    Handles:
    - Title optimization (80 char max for eBay)
    - HTML description generation
    - Image selection (max 12 for eBay)
    - SKU generation from source product ID
    """

    def __init__(self):
        self._title_optimizer = TitleOptimizer()
        self._description_builder = DescriptionBuilder()

    def convert(self, product: ScrapedProduct) -> ListingDraft:
        """Convert a scraped product to an eBay listing draft."""
        title = self.optimize_title(product.title)
        description = self.build_description(product)
        sku = f"KI-{product.source_product_id}"

        return ListingDraft(
            title=title,
            description_html=description,
            price=product.price,  # Will be overridden by profit engine
            images=product.images[:12],
            condition="New",
            sku=sku,
            target_marketplace=TargetMarketplace.EBAY,
            source_product_id=product.source_product_id,
            source_marketplace=product.source_marketplace,
        )

    def optimize_title(self, title: str, max_length: int = 80) -> str:
        """Optimize title for eBay's 80-character limit."""
        return self._title_optimizer.optimize(title, max_length)

    def build_description(self, product: ScrapedProduct) -> str:
        """Build an HTML description for eBay."""
        return self._description_builder.build(product)
