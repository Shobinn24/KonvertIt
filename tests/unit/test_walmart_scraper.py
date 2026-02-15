"""
Unit tests for WalmartScraper.

Tests __NEXT_DATA__ JSON extraction, HTML fallback parsing,
bot detection, product ID extraction, and data transformation.
"""

import json

import pytest

from app.core.exceptions import CaptchaDetectedError
from app.core.models import SourceMarketplace
from app.scrapers.walmart_scraper import WalmartScraper


# ─── Fixtures ──────────────────────────────────────────────


def _build_next_data_page(product: dict) -> str:
    """Build a realistic Walmart page with __NEXT_DATA__ embedded."""
    next_data = {
        "props": {
            "pageProps": {
                "initialData": {
                    "data": {
                        "product": product,
                    }
                }
            }
        }
    }
    return f"""
    <html>
    <head><title>Walmart Product</title></head>
    <body>
        <script id="__NEXT_DATA__" type="application/json">
            {json.dumps(next_data)}
        </script>
        <h1>{product.get("name", "")}</h1>
        <div class="content">Product page content goes here. This is a realistic page
        with enough content to pass the bot detection length check. We need at least
        5000 characters so let's add some more text to make this realistic enough.
        {"x" * 5000}
        </div>
    </body>
    </html>
    """


SAMPLE_NEXT_DATA_PRODUCT = {
    "name": 'onn. 32 Class HD (720P) LED Roku Smart TV (100012589)',
    "brand": "onn.",
    "priceInfo": {
        "currentPrice": {
            "price": 98.00,
            "currencyUnit": "USD",
        }
    },
    "imageInfo": {
        "allImages": [
            {"url": "https://i5.walmartimages.com/seo/onn-32-class-hd-tv.jpg"},
            {"url": "https://i5.walmartimages.com/seo/onn-32-class-hd-tv-2.jpg"},
        ]
    },
    "shortDescription": "The onn. 32\" Class HD Smart TV gives you an outstanding viewing experience.",
    "category": {
        "path": [
            {"name": "Electronics"},
            {"name": "TVs"},
            {"name": "All TVs"},
        ]
    },
    "availabilityStatus": "In Stock",
}


SAMPLE_HTML_PAGE = """
<html>
<head><title>Product Page</title></head>
<body>
    <h1 itemprop="name">Samsung 55" 4K Smart TV</h1>
    <span itemprop="price" content="349.99">$349.99</span>
    <a itemprop="brand">Samsung</a>
    <div data-testid="hero-image">
        <img src="https://i5.walmartimages.com/seo/samsung-tv.jpg" />
    </div>
    <div data-testid="product-description">
        Crystal clear 4K resolution with HDR support.
    </div>
    <div data-testid="breadcrumb">
        <a>Electronics</a>
        <a>TVs</a>
    </div>
""" + "x" * 5000 + """
</body>
</html>
"""


@pytest.fixture
def scraper():
    """Create a WalmartScraper with mocked dependencies."""
    from unittest.mock import MagicMock
    proxy_manager = MagicMock()
    browser_manager = MagicMock()
    return WalmartScraper(
        proxy_manager=proxy_manager,
        browser_manager=browser_manager,
    )


# ─── __NEXT_DATA__ Extraction Tests ───────────────────────


class TestNextDataExtraction:
    """Tests for __NEXT_DATA__ JSON extraction."""

    def test_extract_from_next_data_full_product(self, scraper):
        """Should extract all fields from __NEXT_DATA__."""
        page = _build_next_data_page(SAMPLE_NEXT_DATA_PRODUCT)
        raw = scraper._extract(page)

        assert raw["title"] == 'onn. 32 Class HD (720P) LED Roku Smart TV (100012589)'
        assert raw["price"] == 98.00
        assert raw["brand"] == "onn."
        assert len(raw["images"]) == 2
        assert raw["category"] == "Electronics > TVs > All TVs"
        assert raw["availability"] == "In Stock"
        assert raw["source"] == "next_data"

    def test_extract_price_from_price_info(self, scraper):
        """Should extract price from priceInfo.currentPrice.price."""
        product = {"name": "Test", "priceInfo": {"currentPrice": {"price": 29.99}}}
        price = scraper._extract_price_from_next_data(product)
        assert price == 29.99

    def test_extract_price_from_price_range(self, scraper):
        """Should extract min price from priceInfo.priceRange."""
        product = {
            "name": "Test",
            "priceInfo": {"priceRange": {"minPrice": 15.00, "maxPrice": 25.00}},
        }
        price = scraper._extract_price_from_next_data(product)
        assert price == 15.00

    def test_extract_price_from_direct_field(self, scraper):
        """Should extract price from direct price field."""
        product = {"name": "Test", "price": 42.50}
        price = scraper._extract_price_from_next_data(product)
        assert price == 42.50

    def test_extract_price_from_offer_price(self, scraper):
        """Should extract price from offerPrice field."""
        product = {"name": "Test", "offerPrice": 19.99}
        price = scraper._extract_price_from_next_data(product)
        assert price == 19.99

    def test_extract_price_returns_zero_when_missing(self, scraper):
        """Should return 0.0 when no price found."""
        product = {"name": "Test"}
        price = scraper._extract_price_from_next_data(product)
        assert price == 0.0

    def test_extract_images_from_image_info(self, scraper):
        """Should extract images from imageInfo.allImages."""
        product = {
            "name": "Test",
            "imageInfo": {
                "allImages": [
                    {"url": "https://example.com/img1.jpg"},
                    {"url": "https://example.com/img2.jpg"},
                ]
            },
        }
        images = scraper._extract_images_from_next_data(product)
        assert len(images) == 2

    def test_extract_images_from_images_array(self, scraper):
        """Should extract images from simple images array."""
        product = {
            "name": "Test",
            "images": [
                "https://example.com/img1.jpg",
                "https://example.com/img2.jpg",
            ],
        }
        images = scraper._extract_images_from_next_data(product)
        assert len(images) == 2

    def test_extract_images_from_primary_image(self, scraper):
        """Should fallback to primaryImage."""
        product = {
            "name": "Test",
            "primaryImage": "https://example.com/primary.jpg",
        }
        images = scraper._extract_images_from_next_data(product)
        assert len(images) == 1

    def test_extract_images_max_12(self, scraper):
        """Should limit images to 12 (eBay max)."""
        product = {
            "name": "Test",
            "images": [f"https://example.com/img{i}.jpg" for i in range(20)],
        }
        images = scraper._extract_images_from_next_data(product)
        assert len(images) == 12

    def test_extract_category_from_path(self, scraper):
        """Should build category string from path."""
        product = {
            "name": "Test",
            "category": {
                "path": [
                    {"name": "Electronics"},
                    {"name": "Computers"},
                    {"name": "Laptops"},
                ]
            },
        }
        category = scraper._extract_category_from_next_data(product)
        assert category == "Electronics > Computers > Laptops"

    def test_extract_category_from_breadcrumb(self, scraper):
        """Should build category from breadcrumb."""
        product = {
            "name": "Test",
            "breadcrumb": [
                {"name": "Home"},
                {"name": "Sports"},
            ],
        }
        category = scraper._extract_category_from_next_data(product)
        assert category == "Home > Sports"

    def test_extract_category_from_string(self, scraper):
        """Should use categoryPath string directly."""
        product = {"name": "Test", "categoryPath": "Electronics > Audio"}
        category = scraper._extract_category_from_next_data(product)
        assert category == "Electronics > Audio"

    def test_extract_availability_in_stock(self, scraper):
        """Should extract availability status."""
        product = {"name": "Test", "availabilityStatus": "In Stock"}
        avail = scraper._extract_availability_from_next_data(product)
        assert avail == "In Stock"

    def test_extract_availability_from_bool(self, scraper):
        """Should extract availability from boolean."""
        product = {"name": "Test", "inStock": True}
        assert scraper._extract_availability_from_next_data(product) == "In Stock"

        product = {"name": "Test", "inStock": False}
        assert scraper._extract_availability_from_next_data(product) == "Out of Stock"

    def test_deep_find_product(self, scraper):
        """Should find product deep in nested structure."""
        nested = {
            "level1": {
                "level2": {
                    "product": {
                        "name": "Deep Product",
                        "priceInfo": {"currentPrice": {"price": 9.99}},
                    }
                }
            }
        }
        result = scraper._deep_find_product(nested)
        assert result is not None
        assert result["name"] == "Deep Product"

    def test_deep_find_product_depth_limit(self, scraper):
        """Should respect depth limit."""
        # Build deeply nested structure
        obj = {"name": "Found", "price": 10}
        for _ in range(10):
            obj = {"nested": obj}
        result = scraper._deep_find_product(obj)
        assert result is None


# ─── HTML Fallback Tests ──────────────────────────────────


class TestHtmlFallback:
    """Tests for HTML selector-based extraction."""

    def test_extract_from_html_title(self, scraper):
        """Should extract title from HTML."""
        raw = scraper._extract_from_html(SAMPLE_HTML_PAGE)
        assert raw["title"] == 'Samsung 55" 4K Smart TV'

    def test_extract_from_html_price(self, scraper):
        """Should extract price from HTML."""
        raw = scraper._extract_from_html(SAMPLE_HTML_PAGE)
        assert raw["price"] == 349.99

    def test_extract_from_html_brand(self, scraper):
        """Should extract brand from HTML."""
        raw = scraper._extract_from_html(SAMPLE_HTML_PAGE)
        assert raw["brand"] == "Samsung"

    def test_extract_from_html_images(self, scraper):
        """Should extract images from HTML."""
        raw = scraper._extract_from_html(SAMPLE_HTML_PAGE)
        assert len(raw["images"]) >= 1

    def test_extract_from_html_description(self, scraper):
        """Should extract description from HTML."""
        raw = scraper._extract_from_html(SAMPLE_HTML_PAGE)
        assert "4K" in raw["description"] or "Crystal" in raw["description"]

    def test_extract_from_html_category(self, scraper):
        """Should extract category from breadcrumbs."""
        raw = scraper._extract_from_html(SAMPLE_HTML_PAGE)
        assert "Electronics" in raw["category"]

    def test_fallback_when_no_next_data(self, scraper):
        """Should fallback to HTML when __NEXT_DATA__ is missing."""
        raw = scraper._extract(SAMPLE_HTML_PAGE)
        assert raw["source"] == "html"
        assert raw["title"] == 'Samsung 55" 4K Smart TV'


# ─── Transform Tests ──────────────────────────────────────


class TestTransform:
    """Tests for data transformation."""

    def test_transform_to_scraped_product(self, scraper):
        """Should transform raw data into ScrapedProduct."""
        raw_data = {
            "title": "Test Product",
            "price": 29.99,
            "brand": "TestBrand",
            "images": ["https://example.com/img.jpg"],
            "description": "A test product",
            "category": "Electronics > Gadgets",
            "availability": "In Stock",
        }
        url = "https://www.walmart.com/ip/test-product/123456789"

        product = scraper._transform(raw_data, url)

        assert product.title == "Test Product"
        assert product.price == 29.99
        assert product.brand == "TestBrand"
        assert product.source_marketplace == SourceMarketplace.WALMART
        assert product.source_product_id == "123456789"
        assert product.source_url == url


# ─── Product ID Extraction Tests ──────────────────────────


class TestProductIdExtraction:
    """Tests for Walmart product ID extraction from URLs."""

    def test_extract_id_standard_url(self, scraper):
        """Should extract ID from standard /ip/product-name/ID URL."""
        url = "https://www.walmart.com/ip/onn-32-Class-HD-LED-TV/100012589"
        assert scraper._extract_product_id(url) == "100012589"

    def test_extract_id_short_url(self, scraper):
        """Should extract ID from short /ip/ID URL."""
        url = "https://www.walmart.com/ip/100012589"
        assert scraper._extract_product_id(url) == "100012589"

    def test_extract_id_with_query_params(self, scraper):
        """Should extract ID when URL has query params."""
        url = "https://www.walmart.com/ip/product-name/100012589?selected=true"
        assert scraper._extract_product_id(url) == "100012589"

    def test_extract_id_empty_for_invalid_url(self, scraper):
        """Should return empty for non-Walmart URL."""
        url = "https://www.example.com/product/abc"
        assert scraper._extract_product_id(url) == ""


# ─── Bot Detection Tests ──────────────────────────────────


class TestBotDetection:
    """Tests for Walmart-specific bot detection."""

    def test_detect_captcha(self, scraper):
        """Should raise CaptchaDetectedError for PerimeterX."""
        content = "<html><body>px-captcha verification required</body></html>"
        with pytest.raises(CaptchaDetectedError):
            scraper._detect_bot_block(content)

    def test_detect_press_and_hold(self, scraper):
        """Should raise CaptchaDetectedError for press & hold challenge."""
        content = "<html><body>Press & Hold to confirm</body></html>"
        with pytest.raises(CaptchaDetectedError):
            scraper._detect_bot_block(content)

    def test_detect_access_denied(self, scraper):
        """Should return True for access denied page."""
        content = "<html><body>Access Denied - your request was blocked" + "x" * 5000 + "</body></html>"
        assert scraper._detect_bot_block(content) is True

    def test_detect_short_page(self, scraper):
        """Should flag suspiciously short page."""
        content = "<html><body>Short page</body></html>"
        assert scraper._detect_bot_block(content) is True

    def test_normal_page_passes(self, scraper):
        """Should return False for normal page."""
        content = "<html><body>Normal product page content" + "x" * 5000 + "</body></html>"
        assert scraper._detect_bot_block(content) is False


# ─── Image Processing Tests ───────────────────────────────


class TestImageProcessing:
    """Tests for image URL processing."""

    def test_to_large_image_removes_query_params(self, scraper):
        """Should strip query params from Walmart images."""
        url = "https://i5.walmartimages.com/seo/img.jpg?odnWidth=200"
        result = scraper._to_large_image(url)
        assert "?" not in result

    def test_to_large_image_removes_size_suffix(self, scraper):
        """Should remove size dimensions from URL."""
        url = "https://i5.walmartimages.com/seo/img_200x200.jpg"
        result = scraper._to_large_image(url)
        assert "_200x200" not in result

    def test_to_large_image_passthrough_non_walmart(self, scraper):
        """Should pass through non-Walmart URLs unchanged."""
        url = "https://example.com/image.jpg"
        result = scraper._to_large_image(url)
        assert result == "https://example.com/image.jpg"

    def test_to_large_image_empty_string(self, scraper):
        """Should handle empty string."""
        assert scraper._to_large_image("") == ""

    def test_to_large_image_non_http(self, scraper):
        """Should pass through non-HTTP URLs."""
        assert scraper._to_large_image("data:image/png;base64") == "data:image/png;base64"


# ─── Description Cleaning Tests ───────────────────────────


class TestDescriptionCleaning:
    """Tests for HTML description cleaning."""

    def test_clean_html_description(self, scraper):
        """Should strip HTML tags from description."""
        product = {
            "name": "Test",
            "shortDescription": "<p>This is <b>bold</b> text</p>",
            "priceInfo": {"currentPrice": {"price": 10}},
        }
        data = scraper._parse_next_data({
            "props": {"pageProps": {"initialData": {"data": {"product": product}}}}
        })
        assert "<" not in data["description"]
        assert "bold" in data["description"]

    def test_prefer_short_description(self, scraper):
        """Should prefer shortDescription over detailedDescription."""
        product = {
            "name": "Test",
            "shortDescription": "Short version",
            "detailedDescription": "Detailed long version",
            "priceInfo": {"currentPrice": {"price": 10}},
        }
        data = scraper._parse_next_data({
            "props": {"pageProps": {"initialData": {"data": {"product": product}}}}
        })
        assert data["description"] == "Short version"
