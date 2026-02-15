"""
Profit calculation engine for eBay listings.

Calculates eBay fees, payment processing fees, shipping costs,
and profit margins to help sellers price products profitably.
"""

import logging

from app.core.interfaces import IPriceable
from app.core.models import ProfitBreakdown

logger = logging.getLogger(__name__)


# eBay fee rates by category (final value fee percentages)
# Source: https://www.ebay.com/help/selling/fees-credits-invoices/selling-fees
EBAY_FEE_RATES = {
    "default": 0.1325,                    # 13.25% for most categories
    "books": 0.1455,                       # 14.55% for books & magazines
    "clothing": 0.1325,                    # 13.25% for clothing & accessories
    "electronics": 0.1325,                 # 13.25% for consumer electronics
    "collectibles": 0.1325,               # 13.25% for collectibles
    "home_garden": 0.1325,                # 13.25% for home & garden
    "sporting_goods": 0.1325,             # 13.25% for sporting goods
    "toys": 0.1325,                        # 13.25% for toys & hobbies
    "jewelry": 0.1550,                     # 15.50% for jewelry & watches
    "musical_instruments": 0.0635,         # 6.35% for guitars & basses (special rate)
    "business_industrial": 0.0525,         # 5.25% for heavy equipment
}

# Payment processing fee (eBay Managed Payments)
PAYMENT_PROCESSING_RATE = 0.029  # 2.9%
PAYMENT_PROCESSING_FIXED = 0.30  # $0.30 per transaction

# Default shipping cost if not specified
DEFAULT_SHIPPING_COST = 5.00


class ProfitEngine(IPriceable):
    """
    Calculates profit breakdown and suggests pricing for eBay listings.

    Accounts for:
    - eBay final value fee (category-specific)
    - Payment processing fee (2.9% + $0.30)
    - Shipping cost estimate
    - Configurable markup percentage
    """

    def __init__(self, default_shipping: float = DEFAULT_SHIPPING_COST):
        self._default_shipping = default_shipping

    def _get_ebay_fee_rate(self, category: str | None = None) -> float:
        """Get the eBay final value fee rate for a category."""
        if category:
            category_lower = category.lower().replace(" ", "_").replace("&", "")
            for key, rate in EBAY_FEE_RATES.items():
                if key in category_lower:
                    return rate
        return EBAY_FEE_RATES["default"]

    def calculate_profit(
        self,
        cost: float,
        sell_price: float,
        category: str | None = None,
    ) -> ProfitBreakdown:
        """
        Calculate detailed profit breakdown.

        Args:
            cost: Product acquisition cost (what you pay for the item).
            sell_price: The price you'll list it at on eBay.
            category: Optional eBay category for fee rate lookup.

        Returns:
            ProfitBreakdown with itemized fees and net profit.
        """
        if sell_price <= 0:
            return ProfitBreakdown(
                cost=cost,
                sell_price=sell_price,
                profit=-cost,
                margin_pct=-100.0 if cost > 0 else 0.0,
            )

        fee_rate = self._get_ebay_fee_rate(category)

        ebay_fee = round(sell_price * fee_rate, 2)
        payment_fee = round(sell_price * PAYMENT_PROCESSING_RATE + PAYMENT_PROCESSING_FIXED, 2)
        shipping_cost = self._default_shipping

        total_costs = cost + ebay_fee + payment_fee + shipping_cost
        profit = round(sell_price - total_costs, 2)
        margin_pct = round((profit / sell_price) * 100, 2) if sell_price > 0 else 0.0

        return ProfitBreakdown(
            cost=cost,
            sell_price=sell_price,
            ebay_fee=ebay_fee,
            payment_fee=payment_fee,
            shipping_cost=shipping_cost,
            profit=profit,
            margin_pct=margin_pct,
        )

    def suggest_price(self, cost: float, target_margin: float = 0.20) -> float:
        """
        Calculate a suggested selling price to achieve the target margin.

        Uses the formula:
            sell_price = (cost + shipping + fixed_fee) / (1 - ebay_rate - payment_rate - target_margin)

        Args:
            cost: Product acquisition cost.
            target_margin: Desired profit margin as decimal (0.20 = 20%).

        Returns:
            Recommended selling price, rounded to 2 decimal places.
        """
        fee_rate = EBAY_FEE_RATES["default"]
        denominator = 1.0 - fee_rate - PAYMENT_PROCESSING_RATE - target_margin

        if denominator <= 0:
            logger.warning(
                f"Target margin {target_margin:.0%} is too high — combined fees exceed 100%. "
                "Returning break-even price instead."
            )
            return self.calculate_break_even(cost)

        numerator = cost + self._default_shipping + PAYMENT_PROCESSING_FIXED
        price = numerator / denominator

        return round(price, 2)

    def calculate_break_even(self, cost: float) -> float:
        """
        Calculate the minimum selling price to break even (zero profit).

        Args:
            cost: Product acquisition cost.

        Returns:
            Minimum selling price where profit = $0.00.
        """
        fee_rate = EBAY_FEE_RATES["default"]
        denominator = 1.0 - fee_rate - PAYMENT_PROCESSING_RATE

        if denominator <= 0:
            # Should never happen with real fee rates, but safety check
            return cost * 2

        numerator = cost + self._default_shipping + PAYMENT_PROCESSING_FIXED
        return round(numerator / denominator, 2)
