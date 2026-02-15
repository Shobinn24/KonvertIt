"""
Proxy rotation manager with health scoring.

Manages a pool of proxies (residential and datacenter), tracks success/failure
rates, and automatically rotates to the healthiest available proxy.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import StrEnum

from app.config import ProxyProvider, get_settings

logger = logging.getLogger(__name__)


class ProxyType(StrEnum):
    """Proxy tier for fallback chain ordering."""
    RESIDENTIAL = "residential"
    DATACENTER = "datacenter"
    DIRECT = "direct"


@dataclass
class Proxy:
    """A single proxy with health tracking."""

    address: str
    proxy_type: ProxyType = ProxyType.RESIDENTIAL
    provider: str = ""
    health_score: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    last_used_at: float = 0.0
    is_active: bool = True

    @property
    def total_requests(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests

    def record_success(self) -> None:
        """Record a successful request through this proxy."""
        self.success_count += 1
        self.last_used_at = time.monotonic()
        # Increase health score, capped at 1.0
        self.health_score = min(1.0, self.health_score + 0.1)

    def record_failure(self) -> None:
        """Record a failed request through this proxy."""
        self.failure_count += 1
        self.last_used_at = time.monotonic()
        # Decrease health score, minimum 0.0
        self.health_score = max(0.0, self.health_score - 0.2)
        # Deactivate if health drops to zero
        if self.health_score <= 0.0:
            self.is_active = False
            logger.warning(f"Proxy {self.address} deactivated (health score: 0)")


# Sentinel for direct (no proxy) connection
DIRECT_PROXY = Proxy(
    address="DIRECT",
    proxy_type=ProxyType.DIRECT,
    provider="none",
)


class ProxyManager:
    """
    Manages a pool of rotating proxies with health-based selection.

    Fallback chain: residential → datacenter → direct (no proxy)

    Supports multiple proxy provider formats:
    - ScraperAPI: URL-based proxy (http://api.scraperapi.com?api_key=...)
    - Raw proxy list: Comma-separated addresses (ip:port or user:pass@ip:port)
    - BrightData/SmartProxy: Standard proxy URL format
    """

    def __init__(self, proxies: list[Proxy] | None = None):
        self._proxies: list[Proxy] = proxies or []
        self._lock = asyncio.Lock()
        self._rotation_index = 0

        if not self._proxies:
            self._load_from_config()

    def _load_from_config(self) -> None:
        """Load proxies from application configuration."""
        settings = get_settings()

        if settings.proxy_provider == ProxyProvider.SCRAPERAPI and settings.scraper_api_key:
            # ScraperAPI uses API endpoint mode (not proxy port mode).
            # Playwright doesn't support proxy-port auth, so we wrap target URLs
            # through ScraperAPI's API instead. The "address" stores the API base URL
            # with the key — BaseScraper._navigate() rewrites the navigation URL.
            self._proxies.append(
                Proxy(
                    address=f"https://api.scraperapi.com?api_key={settings.scraper_api_key}",
                    proxy_type=ProxyType.RESIDENTIAL,
                    provider="scraperapi",
                )
            )
            logger.info("Loaded ScraperAPI configuration (API endpoint mode)")

        elif settings.proxy_list:
            # Raw proxy list: comma-separated
            for addr in settings.proxy_list.split(","):
                addr = addr.strip()
                if addr:
                    self._proxies.append(
                        Proxy(
                            address=addr,
                            proxy_type=ProxyType.DATACENTER,
                            provider="raw",
                        )
                    )
            logger.info(f"Loaded {len(self._proxies)} proxies from PROXY_LIST")

        if not self._proxies:
            logger.warning(
                "No proxies configured. Scraping will use direct connections. "
                "Set SCRAPER_API_KEY or PROXY_LIST in .env for proxy rotation."
            )

    @property
    def pool_size(self) -> int:
        """Total number of proxies in the pool."""
        return len(self._proxies)

    @property
    def active_count(self) -> int:
        """Number of healthy, active proxies."""
        return sum(1 for p in self._proxies if p.is_active)

    @property
    def health_summary(self) -> dict:
        """Summary of proxy pool health."""
        return {
            "total": self.pool_size,
            "active": self.active_count,
            "avg_health": (
                sum(p.health_score for p in self._proxies) / max(1, self.pool_size)
            ),
            "total_requests": sum(p.total_requests for p in self._proxies),
        }

    async def get_proxy(self) -> Proxy:
        """
        Get the next best proxy from the pool using health-weighted selection.

        Returns the highest-health active proxy, following the fallback chain:
        residential → datacenter → direct.

        Raises:
            ProxyExhaustedError: If no proxies are available.
        """
        async with self._lock:
            # Sort by proxy type priority, then by health score descending
            type_priority = {
                ProxyType.RESIDENTIAL: 0,
                ProxyType.DATACENTER: 1,
                ProxyType.DIRECT: 2,
            }

            active_proxies = [p for p in self._proxies if p.is_active]

            if not active_proxies:
                # Fallback to direct connection
                logger.warning("All proxies exhausted. Falling back to direct connection.")
                return DIRECT_PROXY

            active_proxies.sort(
                key=lambda p: (type_priority.get(p.proxy_type, 99), -p.health_score)
            )

            # Round-robin among top-health proxies to distribute load
            proxy = active_proxies[self._rotation_index % len(active_proxies)]
            self._rotation_index += 1

            return proxy

    async def report_success(self, proxy: Proxy) -> None:
        """Report a successful request through a proxy."""
        async with self._lock:
            proxy.record_success()

    async def report_failure(self, proxy: Proxy) -> None:
        """Report a failed request through a proxy."""
        async with self._lock:
            proxy.record_failure()

    async def reactivate_all(self) -> int:
        """
        Reactivate all deactivated proxies (health reset to 0.3).
        Useful for periodic recovery attempts.

        Returns the number of reactivated proxies.
        """
        async with self._lock:
            reactivated = 0
            for proxy in self._proxies:
                if not proxy.is_active:
                    proxy.is_active = True
                    proxy.health_score = 0.3
                    reactivated += 1
            if reactivated:
                logger.info(f"Reactivated {reactivated} proxies")
            return reactivated

    def add_proxy(self, address: str, proxy_type: ProxyType = ProxyType.DATACENTER, provider: str = "") -> None:
        """Add a new proxy to the pool."""
        self._proxies.append(
            Proxy(address=address, proxy_type=proxy_type, provider=provider)
        )
