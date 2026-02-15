"""
VeRO compliance checking service.

Checks products against eBay's Verified Rights Owner (VeRO) program
brand list and restricted keyword patterns to prevent IP violations.
"""

import json
import logging
import os
from difflib import SequenceMatcher

from app.core.interfaces import IComplianceCheckable
from app.core.models import ComplianceResult, RiskLevel, ScrapedProduct

logger = logging.getLogger(__name__)

# Keywords that indicate restricted or high-risk items
RESTRICTED_KEYWORDS = [
    "replica",
    "counterfeit",
    "knockoff",
    "fake",
    "imitation",
    "inspired by",
    "style of",
    "not authentic",
    "unauthorized",
    "bootleg",
]

# Minimum similarity ratio for fuzzy brand matching (0.0 - 1.0)
FUZZY_MATCH_THRESHOLD = 0.85


class ComplianceService(IComplianceCheckable):
    """
    Checks products for VeRO compliance before eBay listing.

    Features:
    - Exact brand name matching against VeRO list
    - Fuzzy brand matching to catch misspellings and variations
    - Restricted keyword scanning in titles and descriptions
    - Risk level assessment (CLEAR / WARNING / BLOCKED)
    """

    def __init__(self, vero_brands_path: str | None = None):
        self._vero_brands: set[str] = set()
        self._vero_brands_lower: set[str] = set()
        self._load_vero_brands(vero_brands_path)

    def _load_vero_brands(self, path: str | None = None) -> None:
        """Load VeRO brand list from JSON file."""
        if path is None:
            path = os.path.join(
                os.path.dirname(__file__), "..", "data", "vero_brands.json"
            )

        try:
            with open(path) as f:
                brands = json.load(f)
            self._vero_brands = set(brands)
            self._vero_brands_lower = {b.lower() for b in brands}
            logger.info(f"Loaded {len(self._vero_brands)} VeRO brands from {path}")
        except FileNotFoundError:
            logger.error(f"VeRO brands file not found: {path}")
            self._vero_brands = set()
            self._vero_brands_lower = set()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in VeRO brands file: {e}")
            self._vero_brands = set()
            self._vero_brands_lower = set()

    @property
    def brand_count(self) -> int:
        """Number of brands in the VeRO list."""
        return len(self._vero_brands)

    def check_brand(self, brand: str) -> ComplianceResult:
        """
        Check if a brand is protected under eBay's VeRO program.

        Performs:
        1. Exact match (case-insensitive)
        2. Fuzzy match for misspellings/variations

        Args:
            brand: The brand name to check.

        Returns:
            ComplianceResult with risk level and violations.
        """
        if not brand or not brand.strip():
            return ComplianceResult(
                is_compliant=True,
                brand=brand,
                risk_level=RiskLevel.WARNING,
                violations=["No brand specified — manual review recommended"],
            )

        brand_clean = brand.strip()
        brand_lower = brand_clean.lower()

        violations = []

        # Exact match
        if brand_lower in self._vero_brands_lower:
            violations.append(
                f"Brand '{brand_clean}' is on the eBay VeRO protected brands list"
            )
            return ComplianceResult(
                is_compliant=False,
                brand=brand_clean,
                risk_level=RiskLevel.BLOCKED,
                violations=violations,
            )

        # Fuzzy match
        fuzzy_match = self._fuzzy_match_brand(brand_lower)
        if fuzzy_match:
            violations.append(
                f"Brand '{brand_clean}' closely matches VeRO brand '{fuzzy_match}' "
                f"— listing may be flagged"
            )
            return ComplianceResult(
                is_compliant=True,
                brand=brand_clean,
                risk_level=RiskLevel.WARNING,
                violations=violations,
            )

        # No match — brand is clear
        return ComplianceResult(
            is_compliant=True,
            brand=brand_clean,
            risk_level=RiskLevel.CLEAR,
            violations=[],
        )

    def check_product(self, product: ScrapedProduct) -> ComplianceResult:
        """
        Run full compliance check on a product.

        Checks:
        1. Brand against VeRO list
        2. Title and description for restricted keywords
        3. Combined risk assessment

        Args:
            product: The scraped product to check.

        Returns:
            ComplianceResult with all detected violations.
        """
        all_violations = []
        highest_risk = RiskLevel.CLEAR

        # Check brand
        brand_result = self.check_brand(product.brand)
        if brand_result.has_violations:
            all_violations.extend(brand_result.violations)
            if brand_result.risk_level == RiskLevel.BLOCKED:
                highest_risk = RiskLevel.BLOCKED
            elif brand_result.risk_level == RiskLevel.WARNING and highest_risk != RiskLevel.BLOCKED:
                highest_risk = RiskLevel.WARNING

        # Check restricted keywords in title and description
        keyword_violations = self._check_restricted_keywords(
            title=product.title,
            description=product.description,
        )
        if keyword_violations:
            all_violations.extend(keyword_violations)
            if highest_risk != RiskLevel.BLOCKED:
                highest_risk = RiskLevel.WARNING

        is_compliant = highest_risk != RiskLevel.BLOCKED

        return ComplianceResult(
            is_compliant=is_compliant,
            brand=product.brand,
            risk_level=highest_risk,
            violations=all_violations,
        )

    def _fuzzy_match_brand(self, brand_lower: str) -> str | None:
        """
        Find the closest matching VeRO brand using sequence matching.

        Returns the matched brand name if similarity >= threshold, else None.
        """
        best_match = None
        best_ratio = 0.0

        for vero_brand in self._vero_brands:
            ratio = SequenceMatcher(None, brand_lower, vero_brand.lower()).ratio()
            if ratio > best_ratio and ratio >= FUZZY_MATCH_THRESHOLD:
                best_ratio = ratio
                best_match = vero_brand

        return best_match

    def _check_restricted_keywords(
        self,
        title: str,
        description: str,
    ) -> list[str]:
        """
        Scan title and description for restricted keywords.

        Returns list of violation messages for any restricted terms found.
        """
        violations = []
        combined_text = f"{title} {description}".lower()

        for keyword in RESTRICTED_KEYWORDS:
            if keyword in combined_text:
                violations.append(
                    f"Restricted keyword '{keyword}' found in product text — "
                    f"may be flagged by eBay"
                )

        return violations

    def is_brand_protected(self, brand: str) -> bool:
        """Quick check — returns True if brand is on VeRO list."""
        return brand.strip().lower() in self._vero_brands_lower
