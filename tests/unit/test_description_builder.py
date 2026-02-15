"""
Comprehensive tests for the enhanced DescriptionBuilder.

Tests cover:
- All three templates (modern, classic, minimal)
- Feature bullet extraction from various formats
- Image gallery rendering
- Specs table generation
- HTML escaping / XSS prevention
- Edge cases (empty fields, no images, long descriptions)
- build_all_templates() A/B variant generation
- Backward compatibility (default template via build(product))
"""

import pytest

from app.converters.description_builder import (
    DescriptionBuilder,
    DescriptionTemplate,
    _COLORS,
)
from app.core.models import ScrapedProduct, SourceMarketplace


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def builder() -> DescriptionBuilder:
    return DescriptionBuilder()


@pytest.fixture
def full_product() -> ScrapedProduct:
    """A product with all fields populated and multiple images."""
    return ScrapedProduct(
        title="Anker USB C Charger 40W Fast Charging",
        price=25.99,
        currency="USD",
        brand="Anker",
        images=[
            "https://example.com/img1.jpg",
            "https://example.com/img2.jpg",
            "https://example.com/img3.jpg",
            "https://example.com/img4.jpg",
            "https://example.com/img5.jpg",
            "https://example.com/img6.jpg",
        ],
        description="Ultra-Compact fast charger by Anker. Supports USB-C Power Delivery.",
        category="Cell Phone Accessories > Chargers",
        availability="In Stock",
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/B09C5RG6KV",
        source_product_id="B09C5RG6KV",
    )


@pytest.fixture
def minimal_product() -> ScrapedProduct:
    """A product with only required fields."""
    return ScrapedProduct(
        title="Simple Widget",
        price=9.99,
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/X000001",
        source_product_id="X000001",
    )


@pytest.fixture
def bullet_product() -> ScrapedProduct:
    """A product with bullet-point description."""
    return ScrapedProduct(
        title="Wireless Mouse with Ergonomic Design",
        price=19.99,
        brand="Logitech",
        images=["https://example.com/mouse.jpg"],
        description=(
            "• 2.4GHz wireless connectivity\n"
            "• Ergonomic contoured shape\n"
            "• 12-month battery life\n"
            "• Plug and play USB receiver"
        ),
        category="Computer Peripherals > Mice",
        availability="In Stock",
        source_marketplace=SourceMarketplace.AMAZON,
        source_url="https://www.amazon.com/dp/M000001",
        source_product_id="M000001",
    )


@pytest.fixture
def multi_sentence_product() -> ScrapedProduct:
    """A product with a multi-sentence description (3+ sentences)."""
    return ScrapedProduct(
        title="Premium Kitchen Knife Set",
        price=49.99,
        brand="Cuisinart",
        images=["https://example.com/knife.jpg"],
        description=(
            "Professional-grade stainless steel blades. "
            "Ergonomic handles for comfort and control. "
            "Includes chef knife, bread knife, and utility knife."
        ),
        category="Kitchen > Knives",
        source_marketplace=SourceMarketplace.WALMART,
        source_url="https://www.walmart.com/ip/123456",
        source_product_id="123456",
    )


# ─── TestDescriptionTemplate ────────────────────────────────


class TestDescriptionTemplate:
    """Tests for the DescriptionTemplate enum."""

    def test_has_three_templates(self):
        assert len(DescriptionTemplate) == 3

    def test_template_values(self):
        assert DescriptionTemplate.MODERN == "modern"
        assert DescriptionTemplate.CLASSIC == "classic"
        assert DescriptionTemplate.MINIMAL == "minimal"


# ─── TestBuildDefaultTemplate ────────────────────────────────


class TestBuildDefaultTemplate:
    """Tests for backward compatibility — build() defaults to MODERN."""

    def test_default_is_modern(self, builder, full_product):
        default_html = builder.build(full_product)
        modern_html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert default_html == modern_html

    def test_returns_string(self, builder, full_product):
        result = builder.build(full_product)
        assert isinstance(result, str)

    def test_contains_title(self, builder, full_product):
        result = builder.build(full_product)
        assert "Anker USB C Charger 40W Fast Charging" in result

    def test_contains_wrapper_div(self, builder, full_product):
        result = builder.build(full_product)
        assert result.startswith("<div")
        assert result.endswith("</div>")


# ─── TestModernTemplate ──────────────────────────────────────


class TestModernTemplate:
    """Tests for the MODERN template layout."""

    def test_has_header_banner(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert _COLORS["primary"] in html
        assert "<h2" in html

    def test_has_hero_image(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "img1.jpg" in html
        assert 'max-width:280px' in html

    def test_has_specs_table(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "Product Details" in html
        assert "Anker" in html
        assert "Cell Phone Accessories" in html

    def test_has_image_gallery(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "More Images" in html
        # Gallery shows images[1:5], so img2 through img5
        assert "img2.jpg" in html
        assert "img3.jpg" in html
        assert "img4.jpg" in html
        assert "img5.jpg" in html
        # img6 should NOT be in gallery (limited to 4 extra)
        # img1 is hero, not in gallery
        # img6 is the 6th image, gallery is images[1:5] = img2-img5

    def test_gallery_limited_to_4_extra(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        # Count gallery images by looking for 'alt="Product image"'
        gallery_count = html.count('alt="Product image"')
        assert gallery_count == 4

    def test_has_footer(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "Listed with KonvertIt" in html

    def test_has_description(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "Ultra-Compact fast charger" in html

    def test_inline_css_no_style_tag(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "<style" not in html
        assert "style=" in html

    def test_border_radius_on_wrapper(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "border-radius:8px" in html

    def test_source_marketplace_in_specs(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MODERN)
        assert "Source" in html
        assert "Amazon" in html


# ─── TestClassicTemplate ─────────────────────────────────────


class TestClassicTemplate:
    """Tests for the CLASSIC template layout."""

    def test_has_title_with_border(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "border-bottom:2px solid" in html
        assert full_product.title in html

    def test_has_hero_image_larger(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "max-width:400px" in html

    def test_has_description_header(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "Description" in html

    def test_has_hr_separators(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "<hr" in html

    def test_has_specs_table(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "Product Details" in html
        assert "<table" in html

    def test_has_gallery_section(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "Additional Images" in html
        assert "img2.jpg" in html

    def test_gallery_image_size(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "width:140px" in html

    def test_has_footer(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "Listed with KonvertIt" in html

    def test_has_padding(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.CLASSIC)
        assert "padding:24px" in html


# ─── TestMinimalTemplate ─────────────────────────────────────


class TestMinimalTemplate:
    """Tests for the MINIMAL template layout."""

    def test_has_smaller_title(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "font-size:18px" in html

    def test_narrower_max_width(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "max-width:600px" in html

    def test_no_gallery(self, builder, full_product):
        """Minimal template shows only one image, no gallery."""
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "More Images" not in html
        assert "Additional Images" not in html

    def test_single_image_only(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "img1.jpg" in html
        # Only the hero image + its alt text should reference the product
        assert "max-width:300px" in html

    def test_inline_specs_no_table(self, builder, full_product):
        """Minimal template uses inline specs with bullets, not a table."""
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "&bull;" in html
        assert "Anker" in html
        # No table tag in minimal
        assert "<table" not in html

    def test_no_footer(self, builder, full_product):
        """Minimal template has no footer branding."""
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "Listed with KonvertIt" not in html

    def test_has_description(self, builder, full_product):
        html = builder.build(full_product, DescriptionTemplate.MINIMAL)
        assert "Ultra-Compact" in html


# ─── TestFeatureExtraction ───────────────────────────────────


class TestFeatureExtraction:
    """Tests for _extract_features() bullet extraction."""

    def test_bullet_points_with_dot(self, builder):
        desc = "• Feature one\n• Feature two\n• Feature three"
        features = builder._extract_features(desc)
        assert features == ["Feature one", "Feature two", "Feature three"]

    def test_bullet_points_with_dash(self, builder):
        desc = "- Fast charging\n- Compact design\n- USB-C compatible"
        features = builder._extract_features(desc)
        assert len(features) == 3
        assert "Fast charging" in features

    def test_bullet_points_with_asterisk(self, builder):
        desc = "* Waterproof\n* Dustproof\n* Shockproof"
        features = builder._extract_features(desc)
        assert len(features) == 3

    def test_bullet_points_with_checkmark(self, builder):
        desc = "✓ High quality\n✓ Durable\n✓ Lightweight"
        features = builder._extract_features(desc)
        assert len(features) == 3
        assert "High quality" in features

    def test_numbered_list(self, builder):
        desc = "1. First feature\n2. Second feature\n3. Third feature"
        features = builder._extract_features(desc)
        assert len(features) == 3
        assert "First feature" in features

    def test_numbered_list_with_parens(self, builder):
        desc = "1) Fast\n2) Reliable\n3) Affordable"
        features = builder._extract_features(desc)
        assert len(features) == 3

    def test_sentence_splitting_three_plus(self, builder):
        desc = "This is great. It works well. Very durable product."
        features = builder._extract_features(desc)
        assert len(features) == 3

    def test_no_splitting_for_two_sentences(self, builder):
        desc = "This is great. It works well."
        features = builder._extract_features(desc)
        assert features == []

    def test_single_sentence_returns_empty(self, builder):
        desc = "A simple product description with no structure"
        features = builder._extract_features(desc)
        assert features == []

    def test_empty_string_returns_empty(self, builder):
        features = builder._extract_features("")
        assert features == []

    def test_caps_at_8_bullets(self, builder):
        sentences = ". ".join(f"Sentence {i}" for i in range(15)) + "."
        features = builder._extract_features(sentences)
        assert len(features) <= 8

    def test_strips_whitespace(self, builder):
        desc = "•   Lots of space   \n•  Also spacey  "
        features = builder._extract_features(desc)
        assert features[0] == "Lots of space"
        assert features[1] == "Also spacey"

    def test_filters_empty_bullets(self, builder):
        desc = "• Good feature\n•\n• Another feature"
        features = builder._extract_features(desc)
        # Empty bullet should be filtered out
        assert all(f.strip() for f in features)


# ─── TestBuildSpecs ──────────────────────────────────────────


class TestBuildSpecs:
    """Tests for _build_specs() spec pair generation."""

    def test_full_product_specs(self, builder, full_product):
        specs = builder._build_specs(full_product)
        labels = [s[0] for s in specs]
        assert "Brand" in labels
        assert "Category" in labels
        assert "Availability" in labels
        assert "Source" in labels

    def test_brand_value(self, builder, full_product):
        specs = builder._build_specs(full_product)
        brand_spec = next(s for s in specs if s[0] == "Brand")
        assert brand_spec[1] == "Anker"

    def test_source_marketplace_display(self, builder, full_product):
        specs = builder._build_specs(full_product)
        source_spec = next(s for s in specs if s[0] == "Source")
        assert source_spec[1] == "Amazon"

    def test_walmart_source_display(self, builder, multi_sentence_product):
        specs = builder._build_specs(multi_sentence_product)
        source_spec = next(s for s in specs if s[0] == "Source")
        assert source_spec[1] == "Walmart"

    def test_minimal_product_specs(self, builder, minimal_product):
        specs = builder._build_specs(minimal_product)
        labels = [s[0] for s in specs]
        # No brand, category, or availability — only source
        assert "Brand" not in labels
        assert "Category" not in labels
        assert "Source" in labels


# ─── TestImageHandling ───────────────────────────────────────


class TestImageHandling:
    """Tests for image gallery rendering across templates."""

    def test_no_images_modern(self, builder, minimal_product):
        html = builder.build(minimal_product, DescriptionTemplate.MODERN)
        assert "<img" not in html
        assert "More Images" not in html

    def test_no_images_classic(self, builder, minimal_product):
        html = builder.build(minimal_product, DescriptionTemplate.CLASSIC)
        assert "<img" not in html
        assert "Additional Images" not in html

    def test_no_images_minimal(self, builder, minimal_product):
        html = builder.build(minimal_product, DescriptionTemplate.MINIMAL)
        assert "<img" not in html

    def test_single_image_no_gallery(self, builder, bullet_product):
        """Product with one image should show hero but no gallery."""
        html = builder.build(bullet_product, DescriptionTemplate.MODERN)
        assert "mouse.jpg" in html
        assert "More Images" not in html

    def test_two_images_shows_gallery(self, builder):
        product = ScrapedProduct(
            title="Test Product",
            price=10.0,
            images=["https://example.com/a.jpg", "https://example.com/b.jpg"],
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="T001",
        )
        html = builder.build(product, DescriptionTemplate.MODERN)
        assert "More Images" in html
        assert "b.jpg" in html


# ─── TestHtmlEscaping ────────────────────────────────────────


class TestHtmlEscaping:
    """Tests for HTML escaping / XSS prevention."""

    def test_escapes_angle_brackets(self, builder):
        assert builder._escape("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert('xss')&lt;/script&gt;"
        )

    def test_escapes_ampersand(self, builder):
        assert builder._escape("A & B") == "A &amp; B"

    def test_escapes_quotes(self, builder):
        assert builder._escape('He said "hello"') == "He said &quot;hello&quot;"

    def test_escapes_in_title(self, builder):
        product = ScrapedProduct(
            title='<script>alert("XSS")</script> Product',
            price=10.0,
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="XSS001",
        )
        html = builder.build(product)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_escapes_in_description(self, builder):
        product = ScrapedProduct(
            title="Safe Title",
            price=10.0,
            description='<img onerror="alert(1)" src=x>',
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="XSS002",
        )
        html = builder.build(product)
        assert 'onerror="alert(1)"' not in html
        assert "&lt;img" in html


# ─── TestBuildAllTemplates ───────────────────────────────────


class TestBuildAllTemplates:
    """Tests for build_all_templates() A/B variant generation."""

    def test_returns_three_variants(self, builder, full_product):
        variants = builder.build_all_templates(full_product)
        assert len(variants) == 3

    def test_keys_match_template_names(self, builder, full_product):
        variants = builder.build_all_templates(full_product)
        assert set(variants.keys()) == {"modern", "classic", "minimal"}

    def test_variants_are_different(self, builder, full_product):
        variants = builder.build_all_templates(full_product)
        assert variants["modern"] != variants["classic"]
        assert variants["modern"] != variants["minimal"]
        assert variants["classic"] != variants["minimal"]

    def test_all_contain_title(self, builder, full_product):
        variants = builder.build_all_templates(full_product)
        for name, html in variants.items():
            assert full_product.title in html, f"{name} template missing title"

    def test_all_are_valid_html(self, builder, full_product):
        variants = builder.build_all_templates(full_product)
        for name, html in variants.items():
            assert html.startswith("<div"), f"{name} doesn't start with <div"
            assert html.endswith("</div>"), f"{name} doesn't end with </div>"


# ─── TestEdgeCases ───────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and unusual inputs."""

    def test_empty_description(self, builder, minimal_product):
        html = builder.build(minimal_product)
        # Should still render without error
        assert minimal_product.title in html

    def test_empty_brand(self, builder, minimal_product):
        html = builder.build(minimal_product)
        # Brand row should not appear
        assert "Brand" not in html or "&bull;" in html  # minimal has inline

    def test_very_long_description(self, builder):
        product = ScrapedProduct(
            title="Test",
            price=5.0,
            description="A" * 5000,
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="LONG001",
        )
        html = builder.build(product)
        assert "A" * 100 in html  # Description should be included

    def test_unicode_in_title(self, builder):
        product = ScrapedProduct(
            title="日本語テスト Product — Special™",
            price=10.0,
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="UNI001",
        )
        html = builder.build(product)
        assert "日本語テスト" in html

    def test_special_chars_in_brand(self, builder):
        product = ScrapedProduct(
            title="Test",
            price=10.0,
            brand='O\'Brien & Sons "Premium"',
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="SPEC001",
        )
        html = builder.build(product)
        # Brand should be escaped
        assert "O'Brien &amp; Sons &quot;Premium&quot;" in html


# ─── TestBulletRendering ─────────────────────────────────────


class TestBulletRendering:
    """Tests that extracted bullets render as <li> items."""

    def test_modern_renders_bullets(self, builder, bullet_product):
        html = builder.build(bullet_product, DescriptionTemplate.MODERN)
        assert "<ul" in html
        assert "<li" in html
        assert "2.4GHz wireless connectivity" in html

    def test_classic_renders_bullets(self, builder, bullet_product):
        html = builder.build(bullet_product, DescriptionTemplate.CLASSIC)
        assert "<ul" in html
        assert "<li" in html
        assert "Ergonomic contoured shape" in html

    def test_minimal_renders_bullets(self, builder, bullet_product):
        html = builder.build(bullet_product, DescriptionTemplate.MINIMAL)
        assert "<ul" in html
        assert "<li" in html

    def test_sentence_split_renders_bullets(self, builder, multi_sentence_product):
        html = builder.build(multi_sentence_product, DescriptionTemplate.MODERN)
        assert "<li" in html
        assert "Professional-grade" in html

    def test_plain_paragraph_when_no_bullets(self, builder):
        product = ScrapedProduct(
            title="Test",
            price=10.0,
            description="Just a simple one-line description",
            source_marketplace=SourceMarketplace.AMAZON,
            source_url="https://example.com",
            source_product_id="PLAIN001",
        )
        html = builder.build(product, DescriptionTemplate.MODERN)
        assert "<p" in html
        assert "<li" not in html
        assert "Just a simple one-line description" in html


# ─── TestEbayConverterIntegration ────────────────────────────


class TestEbayConverterIntegration:
    """Tests that EbayConverter works with the enhanced DescriptionBuilder."""

    def test_converter_uses_builder(self, full_product):
        from app.converters.ebay_converter import EbayConverter

        converter = EbayConverter()
        draft = converter.convert(full_product)
        # Description should be valid HTML from modern template
        assert draft.description_html.startswith("<div")
        assert "Anker" in draft.description_html

    def test_converter_description_has_footer(self, full_product):
        from app.converters.ebay_converter import EbayConverter

        converter = EbayConverter()
        draft = converter.convert(full_product)
        assert "KonvertIt" in draft.description_html
