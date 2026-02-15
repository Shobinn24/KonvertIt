"""
Tests for AmazonScraper — extraction logic using HTML fixtures.

All tests use saved HTML fixtures (no network calls).
"""

import os

import pytest

from app.core.exceptions import CaptchaDetectedError, DogPageError
from app.core.models import SourceMarketplace
from app.scrapers.amazon_scraper import ASIN_PATTERN, AmazonScraper
from app.scrapers.browser_manager import BrowserManager
from app.scrapers.proxy_manager import ProxyManager

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "amazon")


@pytest.fixture
def scraper():
    """Create an AmazonScraper with mock dependencies."""
    proxy_mgr = ProxyManager(proxies=[])
    browser_mgr = BrowserManager.__new__(BrowserManager)
    browser_mgr._pool_size = 1
    browser_mgr._headless = True
    browser_mgr._min_delay = 0
    browser_mgr._max_delay = 0
    return AmazonScraper(proxy_manager=proxy_mgr, browser_manager=browser_mgr)


@pytest.fixture
def product_html():
    """Load the Amazon product page fixture."""
    path = os.path.join(FIXTURES_DIR, "product_page.html")
    with open(path) as f:
        return f.read()


@pytest.fixture
def dog_page_html():
    """Load the Amazon dog page fixture."""
    path = os.path.join(FIXTURES_DIR, "dog_page.html")
    with open(path) as f:
        return f.read()


@pytest.fixture
def captcha_html():
    """Load the Amazon CAPTCHA page fixture."""
    path = os.path.join(FIXTURES_DIR, "captcha_page.html")
    with open(path) as f:
        return f.read()


# ─── Title Extraction ─────────────────────────────────────────


class TestTitleExtraction:

    def test_extracts_title(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert "Anker USB C Charger 40W" in data["title"]
        assert "521 Charger" in data["title"]

    def test_title_is_stripped(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert not data["title"].startswith(" ")
        assert not data["title"].endswith(" ")


# ─── Price Extraction ─────────────────────────────────────────


class TestPriceExtraction:

    def test_extracts_price(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert data["price"] == 25.99

    def test_price_is_float(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert isinstance(data["price"], float)

    def test_price_greater_than_zero(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert data["price"] > 0


# ─── Brand Extraction ─────────────────────────────────────────


class TestBrandExtraction:

    def test_extracts_brand(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert data["brand"] == "Anker"

    def test_strips_visit_the_prefix(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert not data["brand"].startswith("Visit the")

    def test_strips_store_suffix(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert not data["brand"].endswith("Store")


# ─── Image Extraction ─────────────────────────────────────────


class TestImageExtraction:

    def test_extracts_images(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert len(data["images"]) >= 1

    def test_images_are_high_res(self, scraper, product_html):
        data = scraper._extract(product_html)
        for url in data["images"]:
            assert "SL1500" in url or "_SL" in url or "media-amazon.com" in url

    def test_max_12_images(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert len(data["images"]) <= 12

    def test_images_are_urls(self, scraper, product_html):
        data = scraper._extract(product_html)
        for url in data["images"]:
            assert url.startswith("http")


# ─── Description Extraction ───────────────────────────────────


class TestDescriptionExtraction:

    def test_extracts_description(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert len(data["description"]) > 10

    def test_description_contains_feature_text(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert "Ultra-Compact" in data["description"] or "charger" in data["description"].lower()


# ─── Category Extraction ──────────────────────────────────────


class TestCategoryExtraction:

    def test_extracts_category(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert "Electronics" in data["category"]

    def test_category_is_breadcrumb_format(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert " > " in data["category"]


# ─── Availability Extraction ──────────────────────────────────


class TestAvailabilityExtraction:

    def test_extracts_availability(self, scraper, product_html):
        data = scraper._extract(product_html)
        assert "In Stock" in data["availability"]


# ─── Transform ────────────────────────────────────────────────


class TestTransform:

    def test_transforms_to_scraped_product(self, scraper, product_html):
        raw_data = scraper._extract(product_html)
        product = scraper._transform(raw_data, "https://www.amazon.com/dp/B09C5RG6KV")

        assert product.title != ""
        assert product.price == 25.99
        assert product.brand == "Anker"
        assert product.source_marketplace == SourceMarketplace.AMAZON
        assert product.source_product_id == "B09C5RG6KV"
        assert product.source_url == "https://www.amazon.com/dp/B09C5RG6KV"
        assert product.is_complete is True

    def test_extracts_asin_from_url(self, scraper):
        assert scraper._extract_asin("https://www.amazon.com/dp/B09C5RG6KV") == "B09C5RG6KV"
        assert scraper._extract_asin("https://amazon.com/gp/product/B09C5RG6KV") == "B09C5RG6KV"
        assert scraper._extract_asin("https://amazon.com/Some-Product/dp/B09C5RG6KV/ref=sr") == "B09C5RG6KV"


# ─── Bot Detection ────────────────────────────────────────────


class TestBotDetection:

    def test_detects_dog_page(self, scraper, dog_page_html):
        with pytest.raises(DogPageError):
            scraper._detect_bot_block(dog_page_html)

    def test_detects_captcha(self, scraper, captcha_html):
        with pytest.raises(CaptchaDetectedError):
            scraper._detect_bot_block(captcha_html)

    def test_normal_page_not_blocked(self, scraper, product_html):
        # Should return False (not blocked) for a normal product page
        result = scraper._detect_bot_block(product_html)
        assert result is False

    def test_short_page_detected(self, scraper):
        short_content = "<html><body>Short page</body></html>"
        result = scraper._detect_bot_block(short_content)
        assert result is True


# ─── ASIN Pattern ─────────────────────────────────────────────


class TestAsinPattern:

    def test_standard_dp_url(self):
        match = ASIN_PATTERN.search("https://www.amazon.com/dp/B09C5RG6KV")
        assert match is not None
        assert match.group(1) == "B09C5RG6KV"

    def test_gp_product_url(self):
        match = ASIN_PATTERN.search("https://www.amazon.com/gp/product/B09C5RG6KV")
        assert match is not None
        assert match.group(1) == "B09C5RG6KV"

    def test_url_with_ref(self):
        match = ASIN_PATTERN.search(
            "https://www.amazon.com/Anker-Charger/dp/B09C5RG6KV/ref=sr_1_1"
        )
        assert match is not None
        assert match.group(1) == "B09C5RG6KV"

    def test_invalid_url(self):
        match = ASIN_PATTERN.search("https://www.amazon.com/some-page")
        assert match is None
