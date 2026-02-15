"""
Abstract base converter for marketplace listing conversion.
"""

from abc import abstractmethod

from app.core.interfaces import IConvertable
from app.core.models import ListingDraft, ScrapedProduct


class BaseConverter(IConvertable):
    """
    Base class for marketplace-specific converters.

    Subclasses implement the conversion logic for transforming
    scraped product data into listing drafts for target marketplaces.
    """

    @abstractmethod
    def convert(self, product: ScrapedProduct) -> ListingDraft:
        """Convert scraped product data to a listing draft."""
        ...

    @abstractmethod
    def optimize_title(self, title: str, max_length: int = 80) -> str:
        """Optimize a product title for the target marketplace."""
        ...

    @abstractmethod
    def build_description(self, product: ScrapedProduct) -> str:
        """Build an HTML description for the target marketplace."""
        ...
