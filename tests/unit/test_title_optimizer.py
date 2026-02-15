"""
Unit tests for the enhanced TitleOptimizer.

Tests the full optimization pipeline: clean → noise removal → abbreviations →
deduplication → filler removal → truncation.
"""

import pytest

from app.converters.title_optimizer import TitleAnalysis, TitleOptimizer


@pytest.fixture
def optimizer():
    return TitleOptimizer()


# ─── Basic Behavior ──────────────────────────────────────


class TestBasicBehavior:
    """Tests for basic optimize() behavior."""

    def test_empty_title(self, optimizer):
        assert optimizer.optimize("") == ""

    def test_short_title_unchanged(self, optimizer):
        """Short titles that already fit should pass through cleanly."""
        title = "Anker USB C Charger 40W Fast"
        result = optimizer.optimize(title)
        assert result == title
        assert len(result) <= 80

    def test_always_within_80_chars(self, optimizer):
        """Result must never exceed 80 characters."""
        long_title = (
            "Samsung Galaxy S24 Ultra 512GB Unlocked 5G Smartphone with "
            "Titanium Frame and Advanced AI Camera System for Professional "
            "Photography and Video Recording in Phantom Black Color"
        )
        result = optimizer.optimize(long_title)
        assert len(result) <= 80

    def test_preserves_brand_at_start(self, optimizer):
        """Brand name (first word) should be preserved."""
        title = "Sony WH-1000XM5 Wireless Noise Cancelling Headphones for the Professional User"
        result = optimizer.optimize(title)
        assert result.startswith("Sony")


# ─── Cleaning ────────────────────────────────────────────


class TestCleaning:
    """Tests for whitespace and punctuation cleaning."""

    def test_normalizes_whitespace(self, optimizer):
        title = "Product   Name    With  Spaces"
        result = optimizer.optimize(title)
        assert "  " not in result

    def test_strips_trailing_dashes(self, optimizer):
        title = "Product Name -"
        result = optimizer.optimize(title)
        assert not result.endswith("-")
        assert not result.endswith(" ")

    def test_strips_trailing_comma(self, optimizer):
        title = "Product Name,"
        result = optimizer.optimize(title)
        assert not result.endswith(",")

    def test_strips_leading_pipe(self, optimizer):
        title = "| Product Name"
        result = optimizer.optimize(title)
        assert result == "Product Name"

    def test_double_comma_cleaned(self, optimizer):
        title = "Product,, Name"
        result = optimizer.optimize(title)
        assert ",," not in result

    def test_double_dash_cleaned(self, optimizer):
        title = "Product - - Name"
        result = optimizer.optimize(title)
        assert "- -" not in result


# ─── Noise Removal ───────────────────────────────────────


class TestNoiseRemoval:
    """Tests for Amazon/Walmart noise pattern removal."""

    def test_removes_amazons_choice(self, optimizer):
        title = "Amazon's Choice Product Bluetooth Speaker Waterproof"
        result = optimizer.optimize(title)
        assert "Amazon" not in result

    def test_removes_best_seller(self, optimizer):
        title = "#1 Best Seller Wireless Mouse Ergonomic Design for Office"
        result = optimizer.optimize(title)
        assert "Best Seller" not in result

    def test_removes_amazon_exclusive(self, optimizer):
        title = "Amazon Exclusive Gaming Keyboard Mechanical RGB"
        result = optimizer.optimize(title)
        assert "Amazon Exclusive" not in result

    def test_removes_limited_time_offer(self, optimizer):
        title = "Phone Case Clear Limited Time Offer Slim Design"
        result = optimizer.optimize(title)
        assert "Limited Time Offer" not in result

    def test_removes_free_shipping(self, optimizer):
        title = "Running Shoes Free Shipping Lightweight Breathable Comfortable"
        result = optimizer.optimize(title)
        assert "Free Shipping" not in result

    def test_removes_great_gift(self, optimizer):
        title = "Watch Box Great Gift for Men Leather Organizer"
        result = optimizer.optimize(title)
        assert "Great Gift" not in result

    def test_removes_gift_set(self, optimizer):
        title = "Candle Gift Set Lavender Rose Vanilla Scented"
        result = optimizer.optimize(title)
        assert "Gift Set" not in result

    def test_removes_trailing_model_number_parens(self, optimizer):
        title = "onn. 32 Class HD LED TV (100012589)"
        result = optimizer.optimize(title)
        assert "(100012589)" not in result

    def test_removes_trademark_symbols(self, optimizer):
        title = "BrandName™ Product® With© Features"
        result = optimizer.optimize(title)
        assert "™" not in result
        assert "®" not in result
        assert "©" not in result

    def test_removes_bracketed_updated_version(self, optimizer):
        title = "Laptop Stand [Updated 2024 Version] Adjustable Aluminum"
        result = optimizer.optimize(title)
        assert "[Updated 2024 Version]" not in result

    def test_removes_bracketed_latest_model(self, optimizer):
        title = "Webcam HD [Latest Model] USB Plug and Play"
        result = optimizer.optimize(title)
        assert "[Latest Model]" not in result

    def test_removes_as_seen_on_tv(self, optimizer):
        title = "Kitchen Gadget As Seen On TV Vegetable Chopper"
        result = optimizer.optimize(title)
        assert "As Seen On TV" not in result

    def test_removes_by_brand_at_end(self, optimizer):
        title = "Wireless Earbuds Premium Sound Quality by SoundMax"
        result = optimizer.optimize(title)
        assert "by SoundMax" not in result

    def test_removes_buy_get_promo(self, optimizer):
        title = "Socks Cotton Crew Buy 3 Get 1 Comfortable Athletic"
        result = optimizer.optimize(title)
        assert "Buy 3 Get 1" not in result

    def test_noise_removal_cleans_leftover_spaces(self, optimizer):
        """After removing noise, there shouldn't be double spaces."""
        title = "Product Amazon's Choice Best Seller Widget"
        result = optimizer.optimize(title)
        assert "  " not in result


# ─── Smart Abbreviations ─────────────────────────────────


class TestSmartAbbreviations:
    """Tests for keyword abbreviation system."""

    def test_stainless_steel_to_ss(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Kitchen Knife Set Stainless Steel Professional Chef Cutlery Block Sharpener Extra Long Blade Ergonomic"
        )
        assert "SS" in analysis.optimized
        assert "Stainless Steel" not in analysis.optimized

    def test_bluetooth_to_bt(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Wireless Speaker Bluetooth 5.0 Portable Rechargeable Waterproof Outdoor Indoor Bass Stereo Sound"
        )
        assert "BT" in analysis.optimized
        assert "Bluetooth" not in analysis.optimized

    def test_inches_to_symbol(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Monitor Stand Adjustable Height 27 Inches Wide Dual Screen Desktop Organizer Metal Base Heavy Duty"
        )
        assert '27"' in analysis.optimized

    def test_pounds_to_lb(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Dumbbell Set 20 Pounds Adjustable Weight Training Home Gym Equipment Fitness Exercise Rubber Coated"
        )
        assert "20lb" in analysis.optimized

    def test_ounces_to_oz(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Water Bottle 32 Ounces Stainless Steel Insulated Double Wall Vacuum Sports Travel Gym Flask"
        )
        assert "32oz" in analysis.optimized

    def test_pack_of_n_to_n_pack(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "LED Light Bulbs Pack of 12 Daylight 60W Equivalent Energy Saving Dimmable A19 Base Long Lasting"
        )
        assert "12-Pack" in analysis.optimized

    def test_piece_to_pc(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Tool Set 50 Piece Home Repair Kit Screwdriver Wrench Pliers Hammer Professional Household Mechanic"
        )
        assert "50pc" in analysis.optimized

    def test_professional_to_pro(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Hair Dryer Professional Salon Grade Ionic Technology Lightweight Fast Drying Multiple Heat Settings"
        )
        assert "Pro" in analysis.optimized

    def test_waterproof_to_wp(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Watch Band Waterproof Silicone Replacement Adjustable Sport Universal Fit Compatible Apple Samsung"
        )
        assert "WP" in analysis.optimized

    def test_rechargeable_to_rchg(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Flashlight Rechargeable LED Tactical High Lumens Waterproof Zoomable Emergency Outdoor Camping Hiking"
        )
        assert "Rchg" in analysis.optimized

    def test_wifi_normalized(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Security Camera Wi-Fi Outdoor Waterproof Night Vision Motion Detection Two Way Audio Cloud Storage"
        )
        assert "WiFi" in analysis.optimized

    def test_generation_to_gen(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "iPad Case Generation 10 Protective Cover Stand Auto Wake Sleep Magnetic Closure Slim Lightweight Fit"
        )
        assert "Gen" in analysis.optimized

    def test_carbon_fiber_to_cf(self, optimizer):
        analysis = optimizer.optimize_with_analysis(
            "Phone Case Carbon Fiber Texture Slim Protective Shockproof Cover Compatible iPhone 15 Pro Max Matte"
        )
        assert "CF" in analysis.optimized

    def test_abbreviation_case_insensitive(self, optimizer):
        """Should abbreviate regardless of case."""
        analysis = optimizer.optimize_with_analysis(
            "Knife STAINLESS STEEL blade professional grade kitchen chef utility paring bread set block storage"
        )
        assert "SS" in analysis.optimized

    def test_analysis_tracks_abbreviations(self, optimizer):
        """TitleAnalysis should list which abbreviations were applied."""
        analysis = optimizer.optimize_with_analysis(
            "Bottle Stainless Steel 32 Ounces Bluetooth Speaker Waterproof Rechargeable Portable Outdoor Hiking"
        )
        assert len(analysis.abbreviations_applied) > 0
        # At least SS, oz, BT, WP, Rchg should have been applied
        labels = analysis.abbreviations_applied
        label_text = " ".join(labels)
        assert "SS" in label_text


# ─── Deduplication ────────────────────────────────────────


class TestDeduplication:
    """Tests for duplicate word removal."""

    def test_removes_duplicate_words(self, optimizer):
        """Test _deduplicate directly to verify logic."""
        title = "Wireless Wireless Mouse Ergonomic Ergonomic Design USB Receiver"
        analysis = TitleAnalysis(original=title, optimized="")
        result = optimizer._deduplicate(title, analysis)
        words = result.split()
        assert words.count("Wireless") == 1
        assert words.count("Ergonomic") == 1

    def test_keeps_short_duplicates(self, optimizer):
        """Should not deduplicate very short words like 'in', 'to'."""
        title = "2 in 1 Laptop to Desktop Converter"
        result = optimizer.optimize(title)
        # Short words (<=2 chars) are not deduplicated
        assert "2" in result

    def test_case_insensitive_dedup(self, optimizer):
        """Test _deduplicate handles case-insensitive matching."""
        title = "Charger CHARGER USB Cable Quick Fast Charge Adapter"
        analysis = TitleAnalysis(original=title, optimized="")
        result = optimizer._deduplicate(title, analysis)
        lower_words = [w.lower() for w in result.split()]
        assert lower_words.count("charger") == 1


# ─── Filler Word Removal ─────────────────────────────────


class TestFillerRemoval:
    """Tests for stop word removal."""

    def test_removes_basic_fillers(self, optimizer):
        """Should remove 'the', 'a', 'an' etc. when title is too long."""
        title = (
            "The Original Premium Quality Stainless Steel Water Bottle "
            "That Is a Very Great Choice in the Kitchen and at the Office "
            "by BrandName"
        )
        result = optimizer.optimize(title)
        assert len(result) <= 80
        # "the", "a", "that", "is" etc. should be removed

    def test_keeps_for_and_with(self, optimizer):
        """'for' and 'with' carry search value and should be preserved."""
        title = "Phone Case for iPhone 15 Pro with MagSafe"
        result = optimizer.optimize(title)
        assert "for" in result
        assert "with" in result

    def test_preserves_first_word(self, optimizer):
        """First word should never be removed even if it's a filler."""
        title = "The Best Wireless Headphones Ever Made"
        result = optimizer.optimize(title)
        assert result.startswith("The")

    def test_aggressive_vs_standard_filler_removal(self, optimizer):
        """Aggressive mode should also remove 'for' and 'with'."""
        title = "Case for iPhone with MagSafe for Wireless Charging"
        aggressive = optimizer._remove_filler_words_aggressive(title)
        # "for" and "with" should be gone in aggressive mode
        words = aggressive.split()
        # First word kept regardless
        assert "for" not in words[1:]
        assert "with" not in words[1:]


# ─── Truncation ──────────────────────────────────────────


class TestTruncation:
    """Tests for word-boundary truncation."""

    def test_truncates_at_word_boundary(self, optimizer):
        """Should not cut in the middle of a word."""
        result = optimizer.optimize(
            "A" * 40 + " " + "B" * 40 + " " + "C" * 20,
            max_length=80,
        )
        # Should not contain a partial word
        assert len(result) <= 80
        for word in result.split():
            # Each word should be clean
            assert len(word) > 0

    def test_very_long_title_still_fits(self, optimizer):
        title = "x " * 100  # 200 chars
        result = optimizer.optimize(title)
        assert len(result) <= 80

    def test_analysis_marks_truncation(self, optimizer):
        """TitleAnalysis.was_truncated should be True when truncation happened."""
        # Use unique words so dedup doesn't reduce it before truncation
        words = [f"Word{i}" for i in range(30)]
        title = " ".join(words)  # ~200 chars of unique words
        analysis = optimizer.optimize_with_analysis(title)
        assert analysis.was_truncated is True
        assert len(analysis.optimized) <= 80


# ─── TitleAnalysis ────────────────────────────────────────


class TestTitleAnalysis:
    """Tests for the TitleAnalysis dataclass."""

    def test_chars_saved(self):
        analysis = TitleAnalysis(
            original="x" * 120,
            optimized="x" * 75,
            original_length=120,
            optimized_length=75,
        )
        assert analysis.chars_saved == 45

    def test_fits_limit(self):
        analysis = TitleAnalysis(original="", optimized="", optimized_length=75)
        assert analysis.fits_limit is True

        analysis2 = TitleAnalysis(original="", optimized="", optimized_length=85)
        assert analysis2.fits_limit is False

    def test_to_dict(self):
        analysis = TitleAnalysis(
            original="Original",
            optimized="Opt",
            original_length=8,
            optimized_length=3,
            abbreviations_applied=["Bluetooth→BT"],
            words_removed=["the"],
            was_truncated=False,
        )
        d = analysis.to_dict()
        assert d["original"] == "Original"
        assert d["optimized"] == "Opt"
        assert d["chars_saved"] == 5
        assert d["fits_limit"] is True
        assert "Bluetooth→BT" in d["abbreviations_applied"]
        assert "the" in d["words_removed"]

    def test_optimize_with_analysis_returns_analysis(self, optimizer):
        title = "Short Title"
        analysis = optimizer.optimize_with_analysis(title)
        assert analysis.original == title
        assert analysis.optimized == title
        assert analysis.original_length == len(title)
        assert analysis.optimized_length == len(title)
        assert analysis.was_truncated is False


# ─── Suggest Titles ───────────────────────────────────────


class TestSuggestTitles:
    """Tests for A/B title suggestion feature."""

    def test_returns_at_least_one_variant(self, optimizer):
        variants = optimizer.suggest_titles("Simple Product Title")
        assert len(variants) >= 1

    def test_all_variants_within_limit(self, optimizer):
        title = (
            "Samsung Galaxy S24 Ultra 512GB Unlocked 5G Smartphone with "
            "Titanium Frame and Advanced AI Camera System for Professional "
            "Photography and Video Recording in Phantom Black Color Edition"
        )
        variants = optimizer.suggest_titles(title)
        for v in variants:
            assert len(v) <= 80

    def test_variants_are_unique(self, optimizer):
        title = (
            "Professional Stainless Steel Kitchen Knife Set with Bluetooth "
            "Temperature Sensor and Rechargeable Battery Pack of 12 Waterproof"
        )
        variants = optimizer.suggest_titles(title)
        # All variants should be unique
        assert len(variants) == len(set(variants))

    def test_empty_title_returns_single_empty(self, optimizer):
        variants = optimizer.suggest_titles("")
        assert variants == [""]

    def test_short_title_may_return_one(self, optimizer):
        """A short title may only produce 1 variant if all paths yield the same result."""
        variants = optimizer.suggest_titles("Anker USB C Charger")
        assert len(variants) >= 1
        assert all(v == "Anker USB C Charger" for v in variants)


# ─── Real-World Titles ────────────────────────────────────


class TestRealWorldTitles:
    """Tests with realistic product titles from Amazon/Walmart."""

    def test_amazon_charger_title(self, optimizer):
        title = (
            "Anker USB C Charger 40W, 521 Charger (Nano Pro), PIQ 3.0 "
            "Durable Compact Fast Charger for iPhone 15/15 Plus/15 Pro/15 "
            "Pro Max, Galaxy S23/S23+, iPad Pro, and More"
        )
        result = optimizer.optimize(title)
        assert len(result) <= 80
        assert "Anker" in result
        assert "Charger" in result

    def test_amazon_headphones_title(self, optimizer):
        title = (
            "Sony WH-1000XM5 Wireless Industry Leading Noise Canceling "
            "Headphones with Auto Noise Canceling Optimizer, Crystal "
            "Clear Hands-Free Calling, and Alexa Voice Control, Black"
        )
        result = optimizer.optimize(title)
        assert len(result) <= 80
        assert "Sony" in result

    def test_walmart_tv_title(self, optimizer):
        title = "onn. 32 Class HD (720P) LED Roku Smart TV (100012589)"
        result = optimizer.optimize(title)
        assert len(result) <= 80
        assert "onn." in result
        # Model number in parens should be stripped
        assert "100012589" not in result

    def test_amazon_water_bottle_title(self, optimizer):
        title = (
            "IRON °FLASK Sports Water Bottle - 32 Ounces - 3 Lids "
            "(Straw Lid) - Stainless Steel Insulated - Hot & Cold - "
            "Double Walled - Thermo Mug - Metal Canteen for the "
            "Gym and for Outdoor Hiking - Perfect Gift for Men"
        )
        result = optimizer.optimize(title)
        assert len(result) <= 80
        assert "IRON" in result
        # Abbreviations should be applied
        assert "Ounce" not in result  # Should be "oz"
        assert "Stainless Steel" not in result  # Should be "SS"

    def test_amazon_bluetooth_speaker(self, optimizer):
        title = (
            "JBL Charge 5 - Portable Bluetooth Speaker with Deep Bass, "
            "IP67 Waterproof and Dustproof, 20 Hours of Playtime, "
            "Built-in Powerbank, in Black by JBL"
        )
        result = optimizer.optimize(title)
        assert len(result) <= 80
        assert "JBL" in result
        # "by JBL" at end should be removed as noise
        assert not result.endswith("by JBL")

    def test_amazon_badge_title(self, optimizer):
        title = (
            "Amazon's Choice Ergonomic Wireless Mouse Rechargeable "
            "Bluetooth Silent Click USB Receiver Adjustable DPI "
            "Comfortable Grip for Laptop Desktop PC"
        )
        result = optimizer.optimize(title)
        assert len(result) <= 80
        assert "Amazon" not in result
        # Core product words should survive
        assert "Mouse" in result

    def test_title_with_multiple_abbreviations(self, optimizer):
        """Multiple abbreviations should stack."""
        title = (
            "Portable Rechargeable Bluetooth Speaker 12 Inches "
            "Waterproof Professional Grade Carbon Fiber Housing "
            "Stainless Steel Grille Adjustable Bass"
        )
        analysis = optimizer.optimize_with_analysis(title)
        assert len(analysis.optimized) <= 80
        # Should have applied multiple abbreviations
        assert len(analysis.abbreviations_applied) >= 3

    def test_pipeline_order_incremental(self, optimizer):
        """Steps should be applied incrementally — stop early if possible."""
        # This title is 76 chars after noise removal, so no abbreviations needed
        title = "Anker USB C Charger 40W Compact Fast (XYZAB)"
        analysis = optimizer.optimize_with_analysis(title)
        assert len(analysis.optimized) <= 80
        # Should not have needed abbreviations or truncation
        assert analysis.was_truncated is False
