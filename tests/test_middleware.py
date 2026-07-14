from types import SimpleNamespace

import pytest
from scrapy.exceptions import NotConfigured
from scrapy.http import Request
from scrapy.settings import Settings

from scrapy_proxyhat import ProxyHatMiddleware


def make_mw(settings):
    # A minimal crawler stub — from_crawler only needs `.settings` (avoids the
    # Twisted reactor requirement of scrapy.utils.test.get_crawler).
    crawler = SimpleNamespace(settings=Settings(settings))
    return ProxyHatMiddleware.from_crawler(crawler)


class TestConfig:
    def test_not_configured_without_credentials(self):
        with pytest.raises(NotConfigured):
            make_mw({})

    def test_username_password_config(self):
        mw = make_mw({"PROXYHAT_USERNAME": "ph-1", "PROXYHAT_PASSWORD": "pw"})
        assert mw.username == "ph-1"
        assert mw.password == "pw"


class TestProcessRequest:
    def test_sets_rotating_proxy_url(self):
        mw = make_mw({"PROXYHAT_USERNAME": "ph-1", "PROXYHAT_PASSWORD": "pw", "PROXYHAT_COUNTRY": "us"})
        req = Request("https://example.com")
        mw.process_request(req, None)
        assert req.meta["proxy"] == "http://ph-1-country-us:pw@gate.proxyhat.com:8080"
        assert "-sid-" not in req.meta["proxy"]  # rotating, not sticky

    def test_per_request_meta_overrides_targeting(self):
        mw = make_mw({"PROXYHAT_USERNAME": "ph-1", "PROXYHAT_PASSWORD": "pw", "PROXYHAT_COUNTRY": "us"})
        req = Request("https://example.com", meta={"proxyhat_country": "de"})
        mw.process_request(req, None)
        assert "ph-1-country-de" in req.meta["proxy"]

    def test_sticky_via_meta_adds_session(self):
        mw = make_mw({"PROXYHAT_USERNAME": "ph-1", "PROXYHAT_PASSWORD": "pw"})
        req = Request("https://example.com", meta={"proxyhat_sticky": "30m"})
        mw.process_request(req, None)
        assert "-ttl-30m" in req.meta["proxy"]

    def test_settings_sticky_pins_same_ip_across_requests(self):
        # Settings-level sticky must pin one exit IP for the whole crawl: two
        # different requests through the same middleware get the identical sid.
        mw = make_mw({"PROXYHAT_USERNAME": "ph-1", "PROXYHAT_PASSWORD": "pw", "PROXYHAT_STICKY": "30m"})
        req1, req2 = Request("https://example.com/a"), Request("https://example.com/b")
        mw.process_request(req1, None)
        mw.process_request(req2, None)
        assert "-sid-" in req1.meta["proxy"] and "-ttl-30m" in req1.meta["proxy"]
        assert req1.meta["proxy"] == req2.meta["proxy"]  # same sid → same IP

    def test_does_not_override_explicit_proxy(self):
        mw = make_mw({"PROXYHAT_USERNAME": "ph-1", "PROXYHAT_PASSWORD": "pw"})
        req = Request("https://example.com", meta={"proxy": "http://other:1"})
        mw.process_request(req, None)
        assert req.meta["proxy"] == "http://other:1"


class TestApiKeyResolution:
    def test_resolves_active_sub_user_via_sdk(self, monkeypatch):
        users = [
            SimpleNamespace(
                uuid="s",
                name=None,
                proxy_username="susp",
                proxy_password="pw",
                traffic_limit=100,
                used_traffic=1,
                suspended_at="2026-01-01",
            ),
            SimpleNamespace(
                uuid="g",
                name=None,
                proxy_username="good",
                proxy_password="pw",
                traffic_limit=0,
                used_traffic=9,
                suspended_at=None,
            ),
        ]
        fake_client = SimpleNamespace(sub_users=SimpleNamespace(list=lambda: users))
        monkeypatch.setattr("scrapy_proxyhat.middleware.ProxyHat", lambda **kw: fake_client)

        mw = make_mw({"PROXYHAT_API_KEY": "ph_key"})
        assert mw.username == "good"
        req = Request("https://example.com")
        mw.process_request(req, None)
        assert "good-country-any" in req.meta["proxy"]

    def test_raises_when_no_usable_sub_user(self, monkeypatch):
        users = [
            SimpleNamespace(
                uuid="x",
                name=None,
                proxy_username="x",
                proxy_password="pw",
                traffic_limit=100,
                used_traffic=100,
                suspended_at=None,
            ),
        ]
        fake_client = SimpleNamespace(sub_users=SimpleNamespace(list=lambda: users))
        monkeypatch.setattr("scrapy_proxyhat.middleware.ProxyHat", lambda **kw: fake_client)
        with pytest.raises(NotConfigured):
            make_mw({"PROXYHAT_API_KEY": "ph_key"})
