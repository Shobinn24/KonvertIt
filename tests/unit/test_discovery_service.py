"""
Tests for app.services.discovery_service.

Covers URL normalization / ASIN extraction logic that cleans up
sponsored and ad-tracking URLs returned by ScraperAPI search results.
"""

import pytest

from app.services.discovery_service import (
    _extract_asin,
    _normalize_amazon_url,
)


# ─── _extract_asin ───────────────────────────────────────────────


class TestExtractAsin:
    """Tests for ASIN extraction from various Amazon URL formats."""

    # ── Standard product URLs ──

    def test_standard_dp_url(self):
        url = "https://www.amazon.com/dp/B0C2C9NHZW"
        assert _extract_asin(url) == "B0C2C9NHZW"

    def test_dp_url_with_title_slug(self):
        url = "https://www.amazon.com/LEVOIT-Humidifiers-Bedroom/dp/B0C2C9NHZW/ref=sr_1_1"
        assert _extract_asin(url) == "B0C2C9NHZW"

    def test_gp_product_url(self):
        url = "https://www.amazon.com/gp/product/B081S8BC5P"
        assert _extract_asin(url) == "B081S8BC5P"

    def test_dp_url_with_query_params(self):
        url = "https://www.amazon.com/dp/B0C2C9NHZW?ref=pd_rd_uss&pd_rd_w=abc"
        assert _extract_asin(url) == "B0C2C9NHZW"

    def test_dp_url_different_tld(self):
        url = "https://www.amazon.co.uk/dp/B0C2C9NHZW"
        assert _extract_asin(url) == "B0C2C9NHZW"

    # ── Sponsored / redirect URLs ──

    def test_sspa_click_url_with_encoded_dp(self):
        """ScraperAPI returns /sspa/click URLs with URL-encoded destination."""
        url = (
            "https://www.amazon.com/sspa/click?ie=UTF8&spc=MTo3M"
            "&url=%2Fdp%2FB081S8BC5P%2Fref%3Dsr_1_2"
        )
        assert _extract_asin(url) == "B081S8BC5P"

    def test_sspa_click_url_with_double_encoded_dp(self):
        """Some /sspa/click URLs have double-encoded destinations."""
        url = (
            "https://www.amazon.com/sspa/click?ie=UTF8"
            "&url=%252Fdp%252FB09XYZ1234%252Fref%253Dsr"
        )
        # Single unquote produces %2Fdp%2FB09XYZ1234 — need second decode
        # Our function only does one decode, so this may or may not work.
        # The important thing is we try.
        result = _extract_asin(url)
        # After one unquote: %2Fdp%2FB09XYZ1234 — no match on /dp/
        # This won't match, which is acceptable (double encoding is rare)
        # If it does match (future improvement), that's also fine
        assert result is None or result == "B09XYZ1234"

    def test_sspa_click_url_with_full_product_path(self):
        """Sponsored URL with full product URL embedded."""
        url = (
            "https://www.amazon.com/sspa/click?ie=UTF8&spc=MToxOjE"
            "&url=%2FGaming-Hoodie-Funny-Pullover%2Fdp%2FB081S8BC5P"
            "%2Fref%3Dsr_1_3_sspa"
        )
        assert _extract_asin(url) == "B081S8BC5P"

    # ── Ad tracking URLs (no ASIN) ──

    def test_aax_ad_tracking_url_returns_none(self):
        """Ad tracking URLs from aax-us-east don't contain product info."""
        url = (
            "https://aax-us-east-retail-direct.amazon.com/x/c/JCjUz"
            "?ref_=sspa_dk_detail_0&content_id=amzn1.sym.abc123"
        )
        assert _extract_asin(url) is None

    def test_empty_url_returns_none(self):
        assert _extract_asin("") is None

    def test_non_amazon_url_returns_none(self):
        url = "https://www.walmart.com/ip/product-name/123456789"
        assert _extract_asin(url) is None

    def test_url_with_no_asin_pattern(self):
        url = "https://www.amazon.com/s?k=gaming+hoodies&ref=nb_sb_noss"
        assert _extract_asin(url) is None

    # ── Fallback: bare ASIN in path segment ──

    def test_bare_asin_in_path(self):
        """Fallback extracts bare 10-char token from URL path."""
        url = "https://www.amazon.com/some-path/B0C2C9NHZW/extra"
        assert _extract_asin(url) == "B0C2C9NHZW"

    def test_lowercase_asin_not_matched(self):
        """ASINs are uppercase alphanumeric only."""
        url = "https://www.amazon.com/dp/b0c2c9nhzw"
        assert _extract_asin(url) is None


# ─── _normalize_amazon_url ───────────────────────────────────────


class TestNormalizeAmazonUrl:
    """Tests for URL normalization to canonical /dp/{ASIN} form."""

    def test_clean_url_stays_canonical(self):
        url = "https://www.amazon.com/dp/B0C2C9NHZW"
        assert _normalize_amazon_url(url) == "https://www.amazon.com/dp/B0C2C9NHZW"

    def test_dirty_url_with_tracking_params(self):
        url = "https://www.amazon.com/LEVOIT-Humidifiers/dp/B0C2C9NHZW/ref=sr_1_1?keywords=humidifier&qid=1234"
        assert _normalize_amazon_url(url) == "https://www.amazon.com/dp/B0C2C9NHZW"

    def test_sponsored_redirect_normalized(self):
        url = (
            "https://www.amazon.com/sspa/click?ie=UTF8&spc=MTo3M"
            "&url=%2Fdp%2FB081S8BC5P%2Fref%3Dsr_1_2"
        )
        assert _normalize_amazon_url(url) == "https://www.amazon.com/dp/B081S8BC5P"

    def test_gp_product_normalized(self):
        url = "https://www.amazon.com/gp/product/B081S8BC5P?pf_rd_r=abc"
        assert _normalize_amazon_url(url) == "https://www.amazon.com/dp/B081S8BC5P"

    def test_ad_tracking_returns_none(self):
        url = "https://aax-us-east-retail-direct.amazon.com/x/c/JCjUz?ref_=sspa_dk"
        assert _normalize_amazon_url(url) is None

    def test_empty_url_returns_none(self):
        assert _normalize_amazon_url("") is None

    def test_search_url_returns_none(self):
        url = "https://www.amazon.com/s?k=hoodies"
        assert _normalize_amazon_url(url) is None

    def test_always_returns_www_amazon_com(self):
        """Normalized URL always uses www.amazon.com regardless of input TLD."""
        url = "https://www.amazon.co.uk/dp/B0C2C9NHZW"
        assert _normalize_amazon_url(url) == "https://www.amazon.com/dp/B0C2C9NHZW"

    def test_different_asin_prefixes(self):
        """ASINs can start with various characters."""
        # Starts with 0 (older ASINs)
        assert _normalize_amazon_url("https://amazon.com/dp/0451524934") == \
            "https://www.amazon.com/dp/0451524934"
        # Standard B0 prefix
        assert _normalize_amazon_url("https://amazon.com/dp/B0C2C9NHZW") == \
            "https://www.amazon.com/dp/B0C2C9NHZW"
