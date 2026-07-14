from __future__ import annotations

from typing import TYPE_CHECKING, Any

from proxyhat import ProxyHat, build_connection_url
from scrapy.exceptions import NotConfigured

if TYPE_CHECKING:
    from scrapy import Request, Spider
    from scrapy.crawler import Crawler

# Targeting knobs, read from `PROXYHAT_<KEY>` settings or `proxyhat_<key>` request.meta.
_TARGETING_KEYS = ("country", "region", "city", "sticky", "filter")


class ProxyHatMiddleware:
    """Scrapy downloader middleware that routes every request through ProxyHat
    residential proxies.

    Rotating by default (a fresh residential IP per request). Geo/session targeting
    comes from settings and can be overridden per request via ``request.meta``:

    ```python
    # settings.py
    DOWNLOADER_MIDDLEWARES = {"scrapy_proxyhat.ProxyHatMiddleware": 610}
    PROXYHAT_API_KEY = "ph_your_api_key"      # or PROXYHAT_USERNAME + PROXYHAT_PASSWORD
    PROXYHAT_COUNTRY = "us"                    # optional
    ```

    ```python
    # per request
    yield scrapy.Request(url, meta={"proxyhat_country": "de", "proxyhat_sticky": "30m"})
    ```
    """

    def __init__(self, username: str, password: str, targeting: dict[str, Any]) -> None:
        self.username = username
        self.password = password
        self.targeting = targeting
        # When sticky is configured at the settings level, build the connection URL
        # once (minting a single sticky sid) and reuse it for every non-overridden
        # request so the whole crawl pins one exit IP until the TTL expires. The SDK
        # randomizes the sid on each call, so a stable sid means caching the URL.
        self._sticky_url = self._build_url(targeting) if targeting.get("sticky") else None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> ProxyHatMiddleware:
        settings = crawler.settings
        api_key = settings.get("PROXYHAT_API_KEY")
        username = settings.get("PROXYHAT_USERNAME")
        password = settings.get("PROXYHAT_PASSWORD")

        if not ((username and password) or api_key):
            raise NotConfigured(
                "scrapy-proxyhat: set PROXYHAT_API_KEY, or PROXYHAT_USERNAME + PROXYHAT_PASSWORD, in settings."
            )
        if api_key and not (username and password):
            username, password = cls._resolve_sub_user(api_key, settings.get("PROXYHAT_SUBUSER"))

        targeting = {key: settings.get(f"PROXYHAT_{key.upper()}") for key in _TARGETING_KEYS}
        return cls(username, password, targeting)

    @staticmethod
    def _resolve_sub_user(api_key: str, want: str | None) -> tuple[str, str]:
        users = ProxyHat(api_key=api_key).sub_users.list()
        usable = [u for u in users if not u.suspended_at and (u.traffic_limit == 0 or u.used_traffic < u.traffic_limit)]
        if want:
            chosen = next((u for u in users if u.uuid == want or u.name == want), None)
        else:
            chosen = usable[0] if usable else None
        if chosen is None or not chosen.proxy_username or not chosen.proxy_password:
            raise NotConfigured("scrapy-proxyhat: no usable ProxyHat sub-user found (suspended or out of traffic).")
        return chosen.proxy_username, chosen.proxy_password

    def _build_url(self, targeting: dict[str, Any]) -> str:
        kwargs = {key: value for key, value in targeting.items() if value is not None}
        # Credentials live in the URL; Scrapy's HttpProxyMiddleware (priority 750,
        # runs after this one) moves them into the Proxy-Authorization header.
        return build_connection_url(username=self.username, password=self.password, **kwargs)

    def process_request(self, request: Request, spider: Spider) -> None:
        if request.meta.get("proxy"):
            return  # an explicit proxy is already set — don't override it

        targeting = dict(self.targeting)
        overridden = False
        for key in _TARGETING_KEYS:
            override = request.meta.get(f"proxyhat_{key}")
            if override is not None:
                targeting[key] = override
                overridden = True

        # Reuse the cached settings-level sticky URL (stable sid → pinned exit IP)
        # unless this request overrides targeting, in which case build it fresh.
        if self._sticky_url is not None and not overridden:
            request.meta["proxy"] = self._sticky_url
        else:
            request.meta["proxy"] = self._build_url(targeting)
