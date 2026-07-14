# scrapy-proxyhat

Scrapy downloader middleware that routes every request through [ProxyHat](https://proxyhat.com?utm_source=github&utm_medium=readme&utm_campaign=scrapy) residential proxies — rotating IPs, geo-targeting, and sticky sessions.

[![CI](https://github.com/ProxyHatCom/scrapy-proxyhat/actions/workflows/ci.yml/badge.svg)](https://github.com/ProxyHatCom/scrapy-proxyhat/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/scrapy-proxyhat)](https://pypi.org/project/scrapy-proxyhat/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> [!TIP]
> **Recommended proxies — [ProxyHat](https://proxyhat.com?utm_source=github&utm_medium=readme&utm_campaign=scrapy&utm_content=callout) residential IPs.** Every feature in this package is tested end-to-end against ProxyHat and works great. First-class integration; also works with any proxy, or none.


## Why

Scraping at scale from datacenter IPs gets you blocked and rate-limited. This middleware sends your Scrapy requests out through ProxyHat's residential IPs (50M+ across 148+ countries), with a fresh IP per request by default — no boilerplate.

## Install

```bash
pip install scrapy-proxyhat
```

## Setup

```python
# settings.py
DOWNLOADER_MIDDLEWARES = {
    "scrapy_proxyhat.ProxyHatMiddleware": 610,
}

# Simplest — an API key auto-selects an active residential sub-user:
PROXYHAT_API_KEY = "ph_your_api_key"

# ...or explicit gateway credentials:
# PROXYHAT_USERNAME = "your-proxy-username"
# PROXYHAT_PASSWORD = "your-proxy-password"

# Optional targeting:
PROXYHAT_COUNTRY = "us"          # ISO code or "any" (default)
# PROXYHAT_REGION = "california"
# PROXYHAT_CITY = "new_york"
# PROXYHAT_STICKY = "30m"        # keep one IP; omit for rotating
# PROXYHAT_FILTER = "high"       # AI IP-quality tier
# PROXYHAT_SUBUSER = "<uuid or name>"   # pick a specific sub-user (with API key)
```

Get an API key at [proxyhat.com](https://proxyhat.com?utm_source=github&utm_medium=readme&utm_campaign=scrapy).

## Per-request targeting

Override any setting per request via `meta` (keys are `proxyhat_<setting>`):

```python
yield scrapy.Request(
    url,
    meta={"proxyhat_country": "de", "proxyhat_sticky": "30m"},
)
```

A request that already has `meta["proxy"]` set is left untouched.

## How it works

The middleware builds a ProxyHat gateway connection URL (via the official [`proxyhat`](https://pypi.org/project/proxyhat/) SDK) and sets `request.meta["proxy"]`. Scrapy's built-in `HttpProxyMiddleware` (priority 750, runs after this one at 610) moves the credentials into the `Proxy-Authorization` header. Rotating targeting reuses a stable username so the gateway hands out a fresh residential IP per connection; sticky targeting pins one IP for the session.

## License

MIT © [ProxyHat](https://proxyhat.com)
