"""
Tests for ProxyManager — health scoring, rotation, and fallback chain.
"""

import pytest

from app.scrapers.proxy_manager import DIRECT_PROXY, Proxy, ProxyManager, ProxyType


class TestProxy:
    """Tests for the Proxy dataclass."""

    def test_initial_health_score(self):
        proxy = Proxy(address="http://proxy1:8080")
        assert proxy.health_score == 1.0
        assert proxy.is_active is True

    def test_success_increases_health(self):
        proxy = Proxy(address="http://proxy1:8080", health_score=0.5)
        proxy.record_success()
        assert proxy.health_score == 0.6
        assert proxy.success_count == 1

    def test_failure_decreases_health(self):
        proxy = Proxy(address="http://proxy1:8080", health_score=1.0)
        proxy.record_failure()
        assert proxy.health_score == 0.8
        assert proxy.failure_count == 1

    def test_health_capped_at_one(self):
        proxy = Proxy(address="http://proxy1:8080", health_score=0.95)
        proxy.record_success()
        assert proxy.health_score == 1.0

    def test_health_floored_at_zero(self):
        proxy = Proxy(address="http://proxy1:8080", health_score=0.1)
        proxy.record_failure()
        assert proxy.health_score == 0.0
        assert proxy.is_active is False

    def test_deactivated_on_zero_health(self):
        proxy = Proxy(address="http://proxy1:8080", health_score=0.1)
        proxy.record_failure()
        assert proxy.is_active is False

    def test_success_rate(self):
        proxy = Proxy(address="http://proxy1:8080", success_count=8, failure_count=2)
        assert proxy.success_rate == 0.8

    def test_success_rate_no_requests(self):
        proxy = Proxy(address="http://proxy1:8080")
        assert proxy.success_rate == 1.0


class TestProxyManager:
    """Tests for ProxyManager pool management."""

    @pytest.fixture
    def manager_with_proxies(self) -> ProxyManager:
        """Create a ProxyManager with a mix of proxy types."""
        proxies = [
            Proxy(
                address="http://residential1:8080",
                proxy_type=ProxyType.RESIDENTIAL,
                health_score=0.9,
            ),
            Proxy(
                address="http://residential2:8080",
                proxy_type=ProxyType.RESIDENTIAL,
                health_score=0.7,
            ),
            Proxy(
                address="http://datacenter1:8080",
                proxy_type=ProxyType.DATACENTER,
                health_score=1.0,
            ),
        ]
        return ProxyManager(proxies=proxies)

    def test_pool_size(self, manager_with_proxies):
        assert manager_with_proxies.pool_size == 3

    def test_active_count(self, manager_with_proxies):
        assert manager_with_proxies.active_count == 3

    def test_health_summary(self, manager_with_proxies):
        summary = manager_with_proxies.health_summary
        assert summary["total"] == 3
        assert summary["active"] == 3
        assert 0 < summary["avg_health"] <= 1.0

    @pytest.mark.asyncio
    async def test_get_proxy_returns_residential_first(self, manager_with_proxies):
        proxy = await manager_with_proxies.get_proxy()
        assert proxy.proxy_type == ProxyType.RESIDENTIAL

    @pytest.mark.asyncio
    async def test_get_proxy_rotates(self, manager_with_proxies):
        proxies_returned = set()
        for _ in range(6):
            proxy = await manager_with_proxies.get_proxy()
            proxies_returned.add(proxy.address)
        # Should have used at least 2 different proxies
        assert len(proxies_returned) >= 2

    @pytest.mark.asyncio
    async def test_fallback_to_direct_when_all_exhausted(self):
        proxy = Proxy(
            address="http://dead:8080",
            health_score=0.0,
            is_active=False,
        )
        manager = ProxyManager(proxies=[proxy])
        result = await manager.get_proxy()
        assert result is DIRECT_PROXY

    @pytest.mark.asyncio
    async def test_report_success(self, manager_with_proxies):
        proxy = await manager_with_proxies.get_proxy()
        old_score = proxy.health_score
        await manager_with_proxies.report_success(proxy)
        assert proxy.success_count == 1
        assert proxy.health_score >= old_score

    @pytest.mark.asyncio
    async def test_report_failure(self, manager_with_proxies):
        proxy = await manager_with_proxies.get_proxy()
        old_score = proxy.health_score
        await manager_with_proxies.report_failure(proxy)
        assert proxy.failure_count == 1
        assert proxy.health_score < old_score

    @pytest.mark.asyncio
    async def test_reactivate_all(self):
        proxies = [
            Proxy(address="http://p1:8080", health_score=0.0, is_active=False),
            Proxy(address="http://p2:8080", health_score=0.0, is_active=False),
            Proxy(address="http://p3:8080", health_score=0.5, is_active=True),
        ]
        manager = ProxyManager(proxies=proxies)
        assert manager.active_count == 1

        reactivated = await manager.reactivate_all()
        assert reactivated == 2
        assert manager.active_count == 3

    def test_add_proxy(self, monkeypatch):
        monkeypatch.setattr(
            "app.scrapers.proxy_manager.get_settings",
            lambda: type("S", (), {"proxy_provider": "raw", "scraper_api_key": "", "proxy_list": ""})(),
        )
        manager = ProxyManager(proxies=[])
        manager.add_proxy("http://new:8080", ProxyType.DATACENTER, "manual")
        assert manager.pool_size == 1

    @pytest.mark.asyncio
    async def test_empty_pool_returns_direct(self, monkeypatch):
        monkeypatch.setattr(
            "app.scrapers.proxy_manager.get_settings",
            lambda: type("S", (), {"proxy_provider": "raw", "scraper_api_key": "", "proxy_list": ""})(),
        )
        manager = ProxyManager(proxies=[])
        proxy = await manager.get_proxy()
        assert proxy is DIRECT_PROXY
