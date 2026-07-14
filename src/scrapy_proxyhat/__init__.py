"""scrapy-proxyhat — route Scrapy requests through ProxyHat residential proxies."""

from scrapy_proxyhat.middleware import ProxyHatMiddleware

__all__ = ["ProxyHatMiddleware"]
__version__ = "0.1.1"
