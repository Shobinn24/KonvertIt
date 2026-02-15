"""
SEO-optimized title generation for eBay listings.

Transforms verbose Amazon/Walmart product titles into concise, keyword-rich
eBay titles within the 80-character limit.

Optimization pipeline:
    1. Clean — normalize whitespace, strip trailing punctuation
    2. Remove noise — strip source-marketplace junk (Amazon badges, model suffixes, promos)
    3. Abbreviate — replace common terms with space-saving abbreviations
    4. Deduplicate — remove repeated words/phrases
    5. Remove fillers — drop low-value stop words
    6. Truncate — cut at word boundary within 80 chars
"""

import re
from dataclasses import dataclass, field


@dataclass
class TitleAnalysis:
    """Analysis result from the optimizer for debugging/logging."""

    original: str
    optimized: str
    original_length: int = 0
    optimized_length: int = 0
    abbreviations_applied: list[str] = field(default_factory=list)
    words_removed: list[str] = field(default_factory=list)
    was_truncated: bool = False

    @property
    def chars_saved(self) -> int:
        return self.original_length - self.optimized_length

    @property
    def fits_limit(self) -> bool:
        return self.optimized_length <= 80

    def to_dict(self) -> dict:
        return {
            "original": self.original,
            "optimized": self.optimized,
            "original_length": self.original_length,
            "optimized_length": self.optimized_length,
            "chars_saved": self.chars_saved,
            "fits_limit": self.fits_limit,
            "abbreviations_applied": self.abbreviations_applied,
            "words_removed": self.words_removed,
            "was_truncated": self.was_truncated,
        }


class TitleOptimizer:
    """
    Optimizes product titles for eBay's 80-character limit with
    keyword-density-aware abbreviations and smart reordering.

    The optimizer applies transformations incrementally — each step
    checks if the title is already within the limit before proceeding
    to more aggressive optimizations.

    Usage:
        optimizer = TitleOptimizer()
        title = optimizer.optimize("Very Long Amazon Product Title ...")
        # or with analysis:
        analysis = optimizer.optimize_with_analysis("Very Long Title ...")
    """

    # ─── Smart Abbreviations ──────────────────────────────────
    # Ordered from most-savings to least. Each tuple: (pattern, replacement, label)
    # Patterns are case-insensitive and match whole words.

    ABBREVIATIONS: list[tuple[str, str, str]] = [
        # Materials & Finishes
        (r"\bStainless\s+Steel\b", "SS", "Stainless Steel→SS"),
        (r"\bCarbon\s+Fiber\b", "CF", "Carbon Fiber→CF"),
        (r"\bAluminum\s+Alloy\b", "Aluminum", "Aluminum Alloy→Aluminum"),
        # Connectivity
        (r"\bBluetooth\b", "BT", "Bluetooth→BT"),
        (r"\bWi-?Fi\b", "WiFi", "Wi-Fi→WiFi"),
        # Colors (only abbreviate long compound colors)
        (r"\bMulti-?colou?r(?:ed)?\b", "Multi", "Multicolor→Multi"),
        # Sizing & Quantities
        (r"\bPack\s+of\s+(\d+)\b", r"\1-Pack", "Pack of N→N-Pack"),
        (r"\b(\d+)\s*(?:Piece|Pcs|pcs)\b", r"\1pc", "N Piece→Npc"),
        (r"\b(\d+)\s*(?:Count|Ct)\b", r"\1ct", "N Count→Nct"),
        # Units
        (r"\b(\d+)\s*Inch(?:es)?\b", r'\1"', 'Inches→"'),
        (r"\b(\d+(?:\.\d+)?)\s*Ounce(?:s)?\b", r"\1oz", "Ounces→oz"),
        (r"\b(\d+(?:\.\d+)?)\s*Pound(?:s)?\b", r"\1lb", "Pounds→lb"),
        (r"\b(\d+(?:\.\d+)?)\s*Gallon(?:s)?\b", r"\1gal", "Gallons→gal"),
        (r"\b(\d+(?:\.\d+)?)\s*Millimeter(?:s)?\b", r"\1mm", "Millimeters→mm"),
        (r"\b(\d+(?:\.\d+)?)\s*Centimeter(?:s)?\b", r"\1cm", "Centimeters→cm"),
        (r"\b(\d+(?:\.\d+)?)\s*Milliliter(?:s)?\b", r"\1ml", "Milliliters→ml"),
        (r"\b(\d+(?:\.\d+)?)\s*Liter(?:s)?\b", r"\1L", "Liters→L"),
        # Tech specs
        (r"\bGeneration\b", "Gen", "Generation→Gen"),
        (r"\bVersion\b", "Ver", "Version→Ver"),
        (r"\bEdition\b", "Ed", "Edition→Ed"),
        (r"\bCompatible\b", "Compat", "Compatible→Compat"),
        (r"\bReplacement\b", "Repl", "Replacement→Repl"),
        (r"\bAdjustable\b", "Adj", "Adjustable→Adj"),
        (r"\bProfessional\b", "Pro", "Professional→Pro"),
        (r"\bAutomatic\b", "Auto", "Automatic→Auto"),
        (r"\bPortable\b", "Port", "Portable→Port"),
        (r"\bRechargeable\b", "Rchg", "Rechargeable→Rchg"),
        (r"\bWaterproof\b", "WP", "Waterproof→WP"),
        (r"\bTemperature\b", "Temp", "Temperature→Temp"),
        (r"\bAccessories\b", "Accs", "Accessories→Accs"),
        (r"\bAccessory\b", "Acc", "Accessory→Acc"),
        (r"\bUniversal\b", "Univ", "Universal→Univ"),
        (r"\bOrganizer\b", "Org", "Organizer→Org"),
        (r"\bProtector\b", "Prot", "Protector→Prot"),
        (r"\bProtection\b", "Prot", "Protection→Prot"),
    ]

    # ─── Noise Patterns ───────────────────────────────────────
    # Common Amazon/Walmart title junk to remove

    NOISE_PATTERNS: list[re.Pattern] = [
        # Amazon badges and promotional text
        re.compile(r"\b(?:Amazon'?s?\s+Choice|Best\s+Seller|#1\s+Best\s+Seller)\b", re.IGNORECASE),
        re.compile(r"\bAmazon\s+Exclusive\b", re.IGNORECASE),
        # Promotional phrases
        re.compile(r"\b(?:Limited\s+Time\s+(?:Offer|Deal)|Free\s+Shipping)\b", re.IGNORECASE),
        re.compile(r"\b(?:Buy\s+\d+\s+Get\s+\d+|Save\s+\d+%)\b", re.IGNORECASE),
        re.compile(r"\bAs\s+Seen\s+On\s+TV\b", re.IGNORECASE),
        # Gift/occasion junk
        re.compile(r"\b(?:Great|Perfect|Ideal)\s+(?:Gift|Present)\s*(?:for\s+\w+)?\b", re.IGNORECASE),
        re.compile(r"\bGift\s+(?:Box|Set|Idea|Package)\b", re.IGNORECASE),
        # Trailing model numbers in parentheses (only at end)
        re.compile(r"\s*\([A-Z0-9]{5,}\)\s*$"),
        # Redundant "by BrandName" at end
        re.compile(r"\bby\s+\w+\s*$", re.IGNORECASE),
        # Excessive trademark/registration symbols
        re.compile(r"[™®©]+"),
        # Bracketed noise like [Updated 2024], [Latest Model], [Gift Ready]
        re.compile(r"\[(?:Updated|Latest|New)\s*\d*\s*(?:Version|Model|Edition)?\]", re.IGNORECASE),
        re.compile(r"\[(?:Gift\s+Ready|Holiday\s+Special|Limited\s+Edition)\]", re.IGNORECASE),
    ]

    # ─── Filler Words ─────────────────────────────────────────

    FILLER_WORDS = {
        "the", "a", "an", "and", "or", "for", "with", "in", "on", "at",
        "to", "of", "by", "from", "that", "this", "these", "those",
        "is", "are", "was", "were", "be", "been", "being",
        "it", "its", "your", "our", "very", "most", "more",
        "also", "just", "only", "even", "into", "onto", "than",
    }

    # Words that look like fillers but carry search value on eBay
    FILLER_EXCEPTIONS = {
        "for",   # "case for iPhone" — important for search
        "with",  # "laptop with charger" — important for buyers
    }

    # ─── Public API ───────────────────────────────────────────

    def optimize(self, title: str, max_length: int = 80) -> str:
        """
        Optimize a title for eBay listing.

        Applies transformations incrementally until the title fits
        within the character limit. Less aggressive steps are tried first.

        Args:
            title: Original product title from source marketplace.
            max_length: Maximum character length (eBay max is 80).

        Returns:
            Optimized title within the character limit.
        """
        return self.optimize_with_analysis(title, max_length).optimized

    def optimize_with_analysis(self, title: str, max_length: int = 80) -> TitleAnalysis:
        """
        Optimize a title and return detailed analysis.

        Args:
            title: Original product title from source marketplace.
            max_length: Maximum character length (eBay max is 80).

        Returns:
            TitleAnalysis with the optimized title and metadata.
        """
        analysis = TitleAnalysis(
            original=title,
            optimized="",
            original_length=len(title),
        )

        if not title:
            return analysis

        # Step 1: Clean whitespace and punctuation
        result = self._clean(title)

        # Step 2: Remove marketplace noise (always applied — improves quality)
        result = self._remove_noise(result, analysis)

        # Check if we're done
        if len(result) <= max_length:
            analysis.optimized = result
            analysis.optimized_length = len(result)
            return analysis

        # Step 3: Apply smart abbreviations
        result = self._apply_abbreviations(result, analysis)

        if len(result) <= max_length:
            analysis.optimized = result
            analysis.optimized_length = len(result)
            return analysis

        # Step 4: Remove duplicate/redundant words
        result = self._deduplicate(result, analysis)

        if len(result) <= max_length:
            analysis.optimized = result
            analysis.optimized_length = len(result)
            return analysis

        # Step 5: Remove filler words (more aggressive)
        result = self._remove_filler_words(result, analysis)

        if len(result) <= max_length:
            analysis.optimized = result
            analysis.optimized_length = len(result)
            return analysis

        # Step 6: Truncate at word boundary (last resort)
        result = self._truncate(result, max_length)
        analysis.was_truncated = True

        analysis.optimized = result
        analysis.optimized_length = len(result)
        return analysis

    def suggest_titles(self, title: str, max_length: int = 80) -> list[str]:
        """
        Generate multiple title variations for A/B testing.

        Returns up to 3 variations:
        1. Standard optimized title (abbreviations + filler removal)
        2. Keyword-dense variant (aggressive abbreviation, more keywords)
        3. Clean variant (minimal abbreviation, natural reading)

        Args:
            title: Original product title.
            max_length: Max character length.

        Returns:
            List of 1-3 optimized title variants.
        """
        if not title:
            return [""]

        variants: list[str] = []

        # Variant 1: Standard optimization
        standard = self.optimize(title, max_length)
        variants.append(standard)

        # Variant 2: Aggressive abbreviation (try harder to keep all keywords)
        aggressive = self._clean(title)
        aggressive = self._remove_noise(aggressive, TitleAnalysis(original=title, optimized=""))
        aggressive = self._apply_abbreviations(aggressive, TitleAnalysis(original=title, optimized=""))
        aggressive = self._deduplicate(aggressive, TitleAnalysis(original=title, optimized=""))
        aggressive = self._remove_filler_words_aggressive(aggressive)
        if len(aggressive) > max_length:
            aggressive = self._truncate(aggressive, max_length)
        if aggressive != standard:
            variants.append(aggressive)

        # Variant 3: Minimal abbreviation (more natural reading)
        clean = self._clean(title)
        clean = self._remove_noise(clean, TitleAnalysis(original=title, optimized=""))
        clean = self._deduplicate(clean, TitleAnalysis(original=title, optimized=""))
        if len(clean) > max_length:
            clean = self._remove_filler_words(
                clean, TitleAnalysis(original=title, optimized="")
            )
        if len(clean) > max_length:
            clean = self._truncate(clean, max_length)
        if clean not in variants:
            variants.append(clean)

        return variants

    # ─── Internal Pipeline Steps ──────────────────────────────

    def _clean(self, title: str) -> str:
        """Normalize whitespace, strip trailing punctuation and junk chars."""
        # Remove trailing commas, dashes, pipes
        title = re.sub(r"[,\-–—|]+\s*$", "", title)
        # Remove leading/trailing pipes and dashes used as separators
        title = re.sub(r"^\s*[|\-–—]\s*", "", title)
        # Normalize multiple spaces
        title = re.sub(r"\s+", " ", title).strip()
        # Remove double commas, double dashes
        title = re.sub(r",\s*,", ",", title)
        title = re.sub(r"-\s*-", "-", title)
        return title.strip()

    def _remove_noise(self, title: str, analysis: TitleAnalysis) -> str:
        """Remove Amazon/Walmart-specific noise patterns."""
        result = title
        for pattern in self.NOISE_PATTERNS:
            cleaned = pattern.sub("", result)
            if cleaned != result:
                removed = pattern.findall(result)
                for r in removed:
                    if isinstance(r, str) and r.strip():
                        analysis.words_removed.append(r.strip())
                result = cleaned

        # Clean up resulting double-spaces
        result = re.sub(r"\s+", " ", result).strip()
        # Clean trailing punctuation left over
        result = re.sub(r"[,\-–—\s]+$", "", result).strip()
        return result

    def _apply_abbreviations(self, title: str, analysis: TitleAnalysis) -> str:
        """Apply smart abbreviations, most-savings first."""
        result = title
        for pattern, replacement, label in self.ABBREVIATIONS:
            new_result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            if new_result != result:
                analysis.abbreviations_applied.append(label)
                result = new_result

        # Clean up any double spaces from replacements
        return re.sub(r"\s+", " ", result).strip()

    def _deduplicate(self, title: str, analysis: TitleAnalysis) -> str:
        """Remove duplicate words (case-insensitive), keeping first occurrence."""
        words = title.split()
        seen: set[str] = set()
        result = []

        for word in words:
            lower = word.lower().strip(",.;:-")
            if lower in seen and len(lower) > 2:
                # Skip duplicates (only for words longer than 2 chars)
                analysis.words_removed.append(word)
                continue
            seen.add(lower)
            result.append(word)

        return " ".join(result)

    def _remove_filler_words(self, title: str, analysis: TitleAnalysis) -> str:
        """Remove common filler words that don't help eBay search ranking."""
        words = title.split()
        if not words:
            return ""

        # Always keep the first word (usually the brand)
        result = [words[0]]
        for word in words[1:]:
            lower = word.lower()
            if lower in self.FILLER_WORDS and lower not in self.FILLER_EXCEPTIONS:
                analysis.words_removed.append(word)
            else:
                result.append(word)

        return " ".join(result)

    def _remove_filler_words_aggressive(self, title: str) -> str:
        """Aggressively remove all filler words including exceptions."""
        words = title.split()
        if not words:
            return ""

        result = [words[0]]
        for word in words[1:]:
            if word.lower() not in self.FILLER_WORDS:
                result.append(word)

        return " ".join(result)

    def _truncate(self, title: str, max_length: int) -> str:
        """Truncate at the last complete word within the limit."""
        if len(title) <= max_length:
            return title

        truncated = title[:max_length]
        # Find last space to avoid cutting mid-word
        last_space = truncated.rfind(" ")
        if last_space > max_length // 2:
            return truncated[:last_space].rstrip(" ,.-")
        return truncated.rstrip(" ,.-")
