"""Cache boundary (FR-21): config + safe retrieval responses.

- LocalTTLCache: in-process dict with TTL — the local/demo default.
- RedisCache: skeleton for ElastiCache/Redis in cloud mode; fails closed
  until `redis_url` + the redis client are provided.

Cached values must never cross tenants: callers key by tenant/usecase.
"""

import time
from typing import Any, Protocol


class Cache(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl: int) -> None: ...
    def invalidate(self, prefix: str) -> None: ...


class LocalTTLCache:
    def __init__(self):
        self._items: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.time():
            del self._items[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._items[key] = (time.time() + ttl, value)

    def invalidate(self, prefix: str) -> None:
        for key in [k for k in self._items if k.startswith(prefix)]:
            del self._items[key]


class RedisCache:
    """Skeleton — real wiring needs `redis_url` + redis-py. Raises on use so
    a misconfigured cloud deploy fails loudly instead of silently uncached."""

    def __init__(self, url: str = ""):
        self._url = url

    def _unavailable(self):
        from app.stores.dynamodb import BackendNotConfiguredError

        raise BackendNotConfiguredError(
            "RedisCache: set REGINTEL_REDIS_URL and install redis client"
        )

    def get(self, key: str):
        self._unavailable()

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._unavailable()

    def invalidate(self, prefix: str) -> None:
        self._unavailable()


def get_cache(backend: str = "local", redis_url: str = "") -> Cache:
    if backend == "redis":
        return RedisCache(redis_url)
    return LocalTTLCache()
