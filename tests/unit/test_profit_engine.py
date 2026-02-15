"""
Tests for ProfitEngine — fee calculations, margin math, and edge cases.
"""

import pytest

from app.services.profit_engine import (
    DEFAULT_SHIPPING_COST,
    EBAY_FEE_RATES,
    PAYMENT_PROCESSING_FIXED,
    PAYMENT_PROCESSING_RATE,
    ProfitEngine,
)


@pytest.fixture
def engine() -> ProfitEngine:
    return ProfitEngine()


@pytest.fixture
def engine_free_shipping() -> ProfitEngine:
    return ProfitEngine(default_shipping=0.0)


class TestCalculateProfit:

    def test_basic_profit_calculation(self, engine):
        result = engine.calculate_profit(cost=20.00, sell_price=40.00)

        assert result.cost == 20.00
        assert result.sell_price == 40.00
        assert result.ebay_fee > 0
        assert result.payment_fee > 0
        assert result.shipping_cost == DEFAULT_SHIPPING_COST
        assert result.profit > 0
        assert result.is_profitable is True

    def test_ebay_fee_calculation(self, engine_free_shipping):
        result = engine_free_shipping.calculate_profit(cost=0.0, sell_price=100.00)

        expected_ebay_fee = round(100.00 * EBAY_FEE_RATES["default"], 2)
        assert result.ebay_fee == expected_ebay_fee

    def test_payment_fee_calculation(self, engine_free_shipping):
        result = engine_free_shipping.calculate_profit(cost=0.0, sell_price=100.00)

        expected_payment_fee = round(
            100.00 * PAYMENT_PROCESSING_RATE + PAYMENT_PROCESSING_FIXED, 2
        )
        assert result.payment_fee == expected_payment_fee

    def test_profit_equals_sell_minus_all_costs(self, engine):
        result = engine.calculate_profit(cost=25.00, sell_price=50.00)

        expected = round(
            50.00 - 25.00 - result.ebay_fee - result.payment_fee - result.shipping_cost,
            2,
        )
        assert result.profit == expected

    def test_margin_percentage(self, engine_free_shipping):
        result = engine_free_shipping.calculate_profit(cost=10.00, sell_price=100.00)

        expected_margin = round((result.profit / 100.00) * 100, 2)
        assert result.margin_pct == expected_margin

    def test_zero_sell_price(self, engine):
        result = engine.calculate_profit(cost=20.00, sell_price=0.0)

        assert result.profit == -20.00
        assert result.is_profitable is False

    def test_negative_profit_when_margin_too_thin(self, engine):
        # Selling barely above cost with fees should result in loss
        result = engine.calculate_profit(cost=40.00, sell_price=42.00)
        assert result.is_profitable is False

    def test_category_specific_fee_rate(self, engine_free_shipping):
        # Jewelry has higher fee rate (15.50%)
        result = engine_free_shipping.calculate_profit(
            cost=0.0, sell_price=100.00, category="jewelry"
        )
        expected_fee = round(100.00 * EBAY_FEE_RATES["jewelry"], 2)
        assert result.ebay_fee == expected_fee

    def test_default_category_fee(self, engine_free_shipping):
        result = engine_free_shipping.calculate_profit(
            cost=0.0, sell_price=100.00, category="unknown_category"
        )
        expected_fee = round(100.00 * EBAY_FEE_RATES["default"], 2)
        assert result.ebay_fee == expected_fee

    def test_total_fees_property(self, engine):
        result = engine.calculate_profit(cost=20.00, sell_price=40.00)
        assert result.total_fees == result.ebay_fee + result.payment_fee + result.shipping_cost

    def test_custom_shipping_cost(self):
        engine = ProfitEngine(default_shipping=10.00)
        result = engine.calculate_profit(cost=20.00, sell_price=50.00)
        assert result.shipping_cost == 10.00


class TestSuggestPrice:

    def test_suggested_price_achieves_target_margin(self, engine_free_shipping):
        cost = 20.00
        target_margin = 0.20
        suggested = engine_free_shipping.suggest_price(cost, target_margin)

        # Verify the suggested price actually achieves the target margin
        result = engine_free_shipping.calculate_profit(cost=cost, sell_price=suggested)
        assert abs(result.margin_pct - (target_margin * 100)) < 1.0  # Within 1%

    def test_default_margin_is_20_percent(self, engine_free_shipping):
        suggested = engine_free_shipping.suggest_price(cost=20.00)
        result = engine_free_shipping.calculate_profit(cost=20.00, sell_price=suggested)
        assert abs(result.margin_pct - 20.0) < 1.0

    def test_suggested_price_is_positive(self, engine):
        suggested = engine.suggest_price(cost=5.00)
        assert suggested > 0

    def test_suggested_price_above_cost(self, engine):
        cost = 30.00
        suggested = engine.suggest_price(cost)
        assert suggested > cost

    def test_impossible_margin_falls_back_to_break_even(self, engine):
        # 90% margin is impossible with 13.25% + 2.9% fees
        suggested = engine.suggest_price(cost=10.00, target_margin=0.90)
        break_even = engine.calculate_break_even(10.00)
        assert suggested == break_even


class TestCalculateBreakEven:

    def test_break_even_zero_profit(self, engine):
        cost = 25.00
        break_even = engine.calculate_break_even(cost)
        result = engine.calculate_profit(cost=cost, sell_price=break_even)

        # Profit should be approximately zero (within rounding)
        assert abs(result.profit) <= 0.02

    def test_break_even_above_cost(self, engine):
        break_even = engine.calculate_break_even(cost=20.00)
        assert break_even > 20.00

    def test_break_even_with_free_shipping(self):
        engine = ProfitEngine(default_shipping=0.0)
        break_even = engine.calculate_break_even(cost=20.00)
        # Should be lower than with shipping
        break_even_with_shipping = ProfitEngine().calculate_break_even(cost=20.00)
        assert break_even < break_even_with_shipping

    def test_break_even_zero_cost(self, engine):
        break_even = engine.calculate_break_even(cost=0.0)
        # Should still cover shipping + fixed payment fee
        assert break_even > 0
