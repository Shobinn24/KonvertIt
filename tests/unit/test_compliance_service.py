"""
Tests for ComplianceService — VeRO brand matching and restricted keyword detection.
"""

import pytest

from app.core.models import RiskLevel, ScrapedProduct, SourceMarketplace
from app.services.compliance_service import ComplianceService


@pytest.fixture
def service() -> ComplianceService:
    """Create a ComplianceService with the real VeRO brands list."""
    return ComplianceService()


# ─── Brand Loading ────────────────────────────────────────────


class TestBrandLoading:

    def test_loads_vero_brands(self, service):
        assert service.brand_count > 100

    def test_handles_missing_file(self):
        svc = ComplianceService(vero_brands_path="/nonexistent/path.json")
        assert svc.brand_count == 0


# ─── Brand Checking ───────────────────────────────────────────


class TestCheckBrand:

    def test_blocked_brand_nike(self, service):
        result = service.check_brand("Nike")
        assert result.is_compliant is False
        assert result.risk_level == RiskLevel.BLOCKED
        assert len(result.violations) > 0

    def test_blocked_brand_case_insensitive(self, service):
        result = service.check_brand("NIKE")
        assert result.is_compliant is False
        assert result.risk_level == RiskLevel.BLOCKED

    def test_blocked_brand_louis_vuitton(self, service):
        result = service.check_brand("Louis Vuitton")
        assert result.is_compliant is False
        assert result.risk_level == RiskLevel.BLOCKED

    def test_blocked_brand_apple(self, service):
        result = service.check_brand("Apple")
        assert result.is_compliant is False
        assert result.risk_level == RiskLevel.BLOCKED

    def test_clear_brand(self, service):
        result = service.check_brand("Anker")
        assert result.is_compliant is True
        assert result.risk_level == RiskLevel.CLEAR
        assert len(result.violations) == 0

    def test_empty_brand_warning(self, service):
        result = service.check_brand("")
        assert result.risk_level == RiskLevel.WARNING

    def test_whitespace_brand_warning(self, service):
        result = service.check_brand("   ")
        assert result.risk_level == RiskLevel.WARNING

    def test_fuzzy_match_warns(self, service):
        # Slightly misspelled brand name
        result = service.check_brand("Nikee")
        # Should either match exactly or fuzzy match as warning
        assert result.risk_level in (RiskLevel.BLOCKED, RiskLevel.WARNING)


# ─── Product Checking ─────────────────────────────────────────


class TestCheckProduct:

    def test_clean_product_passes(self, service, sample_amazon_product):
        result = service.check_product(sample_amazon_product)
        assert result.is_compliant is True
        assert result.risk_level == RiskLevel.CLEAR

    def test_vero_brand_product_blocked(self, service):
        product = ScrapedProduct(
            title="Nike Air Max 90 Running Shoes",
            price=120.00,
            brand="Nike",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B00TEST123",
            source_product_id="B00TEST123",
        )
        result = service.check_product(product)
        assert result.is_compliant is False
        assert result.risk_level == RiskLevel.BLOCKED

    def test_restricted_keyword_in_title(self, service):
        product = ScrapedProduct(
            title="Replica Designer Handbag - Great Quality",
            price=50.00,
            brand="Generic",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B00TEST456",
            source_product_id="B00TEST456",
        )
        result = service.check_product(product)
        assert result.risk_level == RiskLevel.WARNING
        assert any("replica" in v.lower() for v in result.violations)

    def test_restricted_keyword_in_description(self, service):
        product = ScrapedProduct(
            title="Leather Wallet",
            price=25.00,
            brand="NoBrand",
            description="This is a high quality knockoff of a famous brand",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B00TEST789",
            source_product_id="B00TEST789",
        )
        result = service.check_product(product)
        assert result.risk_level == RiskLevel.WARNING
        assert any("knockoff" in v.lower() for v in result.violations)

    def test_multiple_violations(self, service):
        product = ScrapedProduct(
            title="Fake Nike Replica Shoes",
            price=30.00,
            brand="Nike",
            description="Counterfeit inspired by Nike design",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://www.amazon.com/dp/B00TESTXYZ",
            source_product_id="B00TESTXYZ",
        )
        result = service.check_product(product)
        assert result.is_compliant is False
        assert result.risk_level == RiskLevel.BLOCKED
        # Should have both brand violation and keyword violations
        assert len(result.violations) >= 2


# ─── Quick Check ──────────────────────────────────────────────


class TestIsProtected:

    def test_protected_brand(self, service):
        assert service.is_brand_protected("Nike") is True
        assert service.is_brand_protected("nike") is True

    def test_unprotected_brand(self, service):
        assert service.is_brand_protected("Anker") is False
        assert service.is_brand_protected("SomeRandomBrand") is False
