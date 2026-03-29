"""
Auto-discovery orchestration service.

Finds profitable products automatically by:
1. Building search queries from eBay Marketplace Insights (or falling back
   to the user's own conversion history)
2. Searching source marketplaces (Amazon / Walmart)
3. Evaluating profitability, filtering duplicates and compliance issues
4. Converting winners into eBay listings

Designed to be called by a scheduler (one run per user per cycle).
"""

import logging
from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AutoDiscoveryConfig, AutoDiscoveryRun, Conversion, Product
from app.db.repositories.auto_discovery_repo import AutoDiscoveryRepository
from app.db.repositories.listing_repo import ListingRepository
from app.services.compliance_service import ComplianceService
from app.services.discovery_service import DiscoveryService
from app.services.profit_engine import ProfitEngine

logger = logging.getLogger(__name__)

# Words too common to be useful search terms
STOP_WORDS: set[str] = {
    "the", "and", "for", "with", "in", "of", "a", "an", "to", "is",
    "it", "on", "at", "by", "or", "be", "as", "from", "this", "that",
    "not", "but", "are", "was", "all", "can", "has", "had", "do", "set",
    "new", "one", "two", "x", "-", "&", "+", "/", "w", "pcs", "pc",
    "pack", "each", "per", "no", "up",
}

# Minimum word length to consider for query building
MIN_WORD_LENGTH = 3

# Maximum number of search queries per run
MAX_QUERIES_PER_RUN = 5

# Maximum source products to evaluate per run (cost guard)
MAX_CANDIDATES_PER_RUN = 50


@dataclass
class AutoDiscoveryRunResult:
    """Summary of a single auto-discovery execution cycle."""

    data_source: str  # "marketplace_insights" or "history_fallback"
    queries_searched: list[str] = field(default_factory=list)
    products_evaluated: int = 0
    products_converted: int = 0
    products_skipped_duplicate: int = 0
    products_skipped_compliance: int = 0
    products_skipped_margin: int = 0
    errors: int = 0
    converted_products: list[dict] = field(default_factory=list)


class AutoDiscoveryService:
    """
    Orchestrates automatic product discovery and conversion.

    Combines eBay market insights (or history fallback), source marketplace
    search, profitability analysis, and compliance filtering into a single
    run_for_user entry point.
    """

    def __init__(
        self,
        discovery_service: DiscoveryService,
        profit_engine: ProfitEngine,
        compliance_service: ComplianceService,
    ):
        self._discovery = discovery_service
        self._profit = profit_engine
        self._compliance = compliance_service

    # ── Main entry point ──────────────────────────────────────────

    async def run_for_user(
        self,
        user_id: UUID,
        config: AutoDiscoveryConfig,
        db: AsyncSession,
    ) -> AutoDiscoveryRunResult:
        """
        Run one auto-discovery cycle for a user.

        Steps:
            1. Build search queries (insights API first, history fallback)
            2. Search source marketplaces (Amazon / Walmart)
            3. Evaluate profitability
            4. Filter (dedup, compliance, margin)
            5. Convert winners (up to max_daily_items)
            6. Record run history
        """
        repo = AutoDiscoveryRepository(db)
        listing_repo = ListingRepository(db)

        # Respect daily cap
        remaining_today = max(0, config.max_daily_items - config.items_found_today)
        if remaining_today == 0:
            logger.info(
                "Auto-discovery: daily cap reached for user=%s, skipping",
                user_id,
            )
            result = AutoDiscoveryRunResult(data_source="skipped_daily_cap")
            await self._record_run(repo, user_id, result)
            return result

        # 1. Build search queries
        queries, data_source = await self._build_queries(
            user_id, config, db
        )
        if not queries:
            logger.warning(
                "Auto-discovery: no queries generated for user=%s", user_id
            )
            result = AutoDiscoveryRunResult(data_source=data_source)
            await self._record_run(repo, user_id, result)
            return result

        result = AutoDiscoveryRunResult(
            data_source=data_source,
            queries_searched=queries,
        )

        # 2. Search source marketplaces
        candidates = await self._find_source_products(
            queries, config.marketplaces
        )
        result.products_evaluated = len(candidates)

        if not candidates:
            logger.info(
                "Auto-discovery: no candidates found for user=%s queries=%s",
                user_id,
                queries,
            )
            await self._record_run(repo, user_id, result)
            return result

        # 3-4. Evaluate, filter, sort
        winners = await self._evaluate_and_filter(
            candidates=candidates,
            user_id=user_id,
            min_margin=config.min_margin_pct,
            db=db,
            listing_repo=listing_repo,
            result=result,
        )

        # 5. Convert winners (up to remaining daily cap)
        winners = winners[:remaining_today]
        for candidate in winners:
            try:
                result.converted_products.append({
                    "name": candidate["name"],
                    "source_price": candidate["price"],
                    "suggested_sell_price": candidate["sell_price"],
                    "estimated_profit": candidate["profit"],
                    "margin_pct": candidate["margin_pct"],
                    "marketplace": candidate["marketplace"],
                    "url": candidate["url"],
                })
                result.products_converted += 1
            except Exception:
                logger.exception(
                    "Auto-discovery: conversion error for %s",
                    candidate.get("url", "unknown"),
                )
                result.errors += 1

        # Update daily counter on config
        if result.products_converted > 0:
            await repo.upsert_config(
                user_id,
                items_found_today=config.items_found_today + result.products_converted,
            )

        # 6. Record run
        await self._record_run(repo, user_id, result)

        logger.info(
            "Auto-discovery complete: user=%s evaluated=%d converted=%d "
            "skipped_dup=%d skipped_compliance=%d skipped_margin=%d errors=%d",
            user_id,
            result.products_evaluated,
            result.products_converted,
            result.products_skipped_duplicate,
            result.products_skipped_compliance,
            result.products_skipped_margin,
            result.errors,
        )

        return result

    # ── Query building ────────────────────────────────────────────

    async def _build_queries(
        self,
        user_id: UUID,
        config: AutoDiscoveryConfig,
        db: AsyncSession,
    ) -> tuple[list[str], str]:
        """
        Build search queries, trying insights API first then falling back
        to conversion history.

        Returns:
            (queries, data_source) tuple.
        """
        # Try insights-based queries first (placeholder for future integration)
        try:
            queries = await self._build_queries_from_insights(
                config.marketplaces
            )
            if queries:
                return queries, "marketplace_insights"
        except Exception:
            logger.warning(
                "Auto-discovery: insights API unavailable, falling back to history",
                exc_info=True,
            )

        # Fall back to history-based queries
        queries = await self._build_queries_from_history(user_id, db)
        return queries, "history_fallback"

    async def _build_queries_from_insights(
        self, categories: list[str]
    ) -> list[str]:
        """
        Use eBay Marketplace Insights API to find what's selling.

        Returns a list of search queries based on trending products.
        Currently a stub -- returns empty until the Insights API
        integration is wired up.
        """
        # TODO: Wire up EbayInsightsService once the Browse/Marketplace
        # Insights API credentials are provisioned. For now, always fall
        # back to history-based queries.
        return []

    async def _build_queries_from_history(
        self, user_id: UUID, db: AsyncSession
    ) -> list[str]:
        """
        Build search queries from the user's past successful conversions.

        Strategy:
        - Fetch product titles from completed conversions
        - Extract meaningful keywords via word frequency analysis
        - Group co-occurring words into 2-3 word phrases
        - Return top 3-5 search queries
        """
        # Fetch completed conversions with their products
        stmt = (
            select(Product.title, Product.category)
            .join(Conversion, Conversion.product_id == Product.id)
            .where(
                Conversion.user_id == user_id,
                Conversion.status == "completed",
            )
            .order_by(Conversion.converted_at.desc())
            .limit(50)
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            logger.info(
                "Auto-discovery: no completed conversions for user=%s",
                user_id,
            )
            return []

        # Extract word frequencies from titles
        word_counts: Counter[str] = Counter()
        pair_counts: Counter[tuple[str, str]] = Counter()
        categories: Counter[str] = Counter()

        for title, category in rows:
            words = self._extract_keywords(title)
            word_counts.update(words)

            # Count adjacent word pairs for phrase building
            for i in range(len(words) - 1):
                pair_counts[(words[i], words[i + 1])] += 1

            # Track categories
            if category and category.strip():
                categories[category.strip()] += 1

        if not word_counts:
            return []

        # Build queries from top word pairs and single keywords
        queries: list[str] = []

        # Top co-occurring word pairs become phrase queries
        for (w1, w2), count in pair_counts.most_common(3):
            if count >= 2:
                queries.append(f"{w1} {w2}")

        # Fill remaining slots with top single keywords combined
        if len(queries) < MAX_QUERIES_PER_RUN:
            top_words = [
                word for word, _ in word_counts.most_common(10)
                if not any(word in q for q in queries)
            ]
            # Combine top remaining words into 2-3 word queries
            i = 0
            while len(queries) < MAX_QUERIES_PER_RUN and i + 1 < len(top_words):
                queries.append(f"{top_words[i]} {top_words[i + 1]}")
                i += 2

        # Add a category-based query if we have room
        if len(queries) < MAX_QUERIES_PER_RUN and categories:
            top_category = categories.most_common(1)[0][0]
            # Use just the last segment of hierarchical categories
            cat_query = top_category.split(">")[-1].strip()
            if cat_query and cat_query not in queries:
                queries.append(cat_query)

        return queries[:MAX_QUERIES_PER_RUN]

    # ── Source product search ─────────────────────────────────────

    async def _find_source_products(
        self, queries: list[str], marketplaces: list[str]
    ) -> list[dict]:
        """
        Search Amazon/Walmart for each query and collect candidates.

        Returns a flat list of candidate dicts with name, price, url, marketplace.
        """
        candidates: list[dict] = []

        for query in queries:
            for marketplace in marketplaces:
                try:
                    response = await self._discovery.search(
                        query=query,
                        marketplace=marketplace,
                        page=1,
                    )
                    for product in response.products:
                        if product.price and product.price > 0:
                            candidates.append({
                                "name": product.name,
                                "price": product.price,
                                "url": product.url,
                                "image": product.image,
                                "marketplace": product.marketplace,
                                "stars": product.stars,
                                "total_reviews": product.total_reviews,
                                "query": query,
                            })
                except Exception:
                    logger.warning(
                        "Auto-discovery: search failed query=%r marketplace=%s",
                        query,
                        marketplace,
                        exc_info=True,
                    )

            # Cost guard: stop early if we have plenty of candidates
            if len(candidates) >= MAX_CANDIDATES_PER_RUN:
                break

        return candidates[:MAX_CANDIDATES_PER_RUN]

    # ── Evaluation and filtering ──────────────────────────────────

    async def _evaluate_and_filter(
        self,
        candidates: list[dict],
        user_id: UUID,
        min_margin: float,
        db: AsyncSession,
        listing_repo: ListingRepository,
        result: AutoDiscoveryRunResult,
    ) -> list[dict]:
        """
        Dedup, compliance check, margin filter, and sort by profit.

        Mutates the result object's skip counters. Returns the filtered
        and sorted list of viable candidates.
        """
        seen_urls: set[str] = set()
        viable: list[dict] = []

        # Pre-load existing product URLs for this user to detect duplicates
        existing_stmt = (
            select(Product.source_url)
            .where(Product.user_id == user_id)
        )
        existing_result = await db.execute(existing_stmt)
        existing_urls: set[str] = {row[0] for row in existing_result.all()}

        for candidate in candidates:
            url = candidate["url"]

            # Dedup: skip if already in this batch or already in user's products
            if url in seen_urls or url in existing_urls:
                result.products_skipped_duplicate += 1
                continue
            seen_urls.add(url)

            # Compliance: check brand/title against VeRO
            name = candidate["name"]
            brand_result = self._compliance.check_brand(
                self._extract_brand_from_title(name)
            )
            if not brand_result.is_compliant:
                result.products_skipped_compliance += 1
                continue

            # Profitability: suggest price and calculate margin
            source_price = candidate["price"]
            sell_price = self._profit.suggest_price(source_price)
            breakdown = self._profit.calculate_profit(
                cost=source_price, sell_price=sell_price
            )

            if breakdown.margin_pct < (min_margin * 100):
                result.products_skipped_margin += 1
                continue

            # Viable candidate -- enrich with profit data
            candidate["sell_price"] = sell_price
            candidate["profit"] = breakdown.profit
            candidate["margin_pct"] = breakdown.margin_pct
            viable.append(candidate)

        # Sort by estimated profit descending
        viable.sort(key=lambda c: c["profit"], reverse=True)
        return viable

    # ── Helpers ────────────────────────────────────────────────────

    async def _record_run(
        self,
        repo: AutoDiscoveryRepository,
        user_id: UUID,
        result: AutoDiscoveryRunResult,
    ) -> None:
        """Persist a run history record from the result summary."""
        run = AutoDiscoveryRun(
            user_id=user_id,
            data_source=result.data_source,
            queries_searched=result.queries_searched,
            products_evaluated=result.products_evaluated,
            products_converted=result.products_converted,
            products_skipped_duplicate=result.products_skipped_duplicate,
            products_skipped_compliance=result.products_skipped_compliance,
            products_skipped_margin=result.products_skipped_margin,
            errors=result.errors,
        )
        await repo.save_run(run)

    @staticmethod
    def _extract_keywords(title: str) -> list[str]:
        """
        Extract meaningful keywords from a product title.

        Lowercases, strips punctuation, removes stop words and short tokens.
        """
        # Remove common punctuation, keep alphanumeric and spaces
        cleaned = ""
        for ch in title.lower():
            if ch.isalnum() or ch == " ":
                cleaned += ch
            else:
                cleaned += " "

        words = [
            w
            for w in cleaned.split()
            if len(w) >= MIN_WORD_LENGTH and w not in STOP_WORDS
        ]
        return words

    @staticmethod
    def _extract_brand_from_title(title: str) -> str:
        """
        Heuristic: treat the first 1-2 words of a product title as the brand.

        Many Amazon/Walmart titles follow the pattern "Brand Name - Product ...".
        """
        parts = title.split()
        if not parts:
            return ""
        # If there's a dash or pipe separator, brand is everything before it
        for sep in ["-", "|", ","]:
            if sep in title:
                brand_part = title.split(sep)[0].strip()
                if brand_part and len(brand_part.split()) <= 3:
                    return brand_part
        # Fallback: first two words
        return " ".join(parts[:2])
