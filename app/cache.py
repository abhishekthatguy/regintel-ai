"""Cache boundary (FR-21): config + safe retrieval responses.

- LocalTTLCache: in-process dict with TTL — the local/demo default.
- RedisCache: real redis-py client for ElastiCache/Upstash/Render KV in
  cloud mode; enabled by REGINTEL_CACHE_BACKEND=redis + REGINTEL_REDIS_URL.
  Values are JSON-serialized; connection failure degrades to LocalTTLCache
  so a cache outage never breaks the request path.

Cached values must never cross tenants: callers key by tenant/usecase.
"""

import json
import logging
import time
from typing import Any, Protocol

logger = logging.getLogger(__name__)


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
    """Real Redis backend (ElastiCache / Upstash / Render KV). Values are
    JSON-serialized; every operation degrades to the local fallback on
    connection failure so a cache outage never breaks the request path."""

    def __init__(self, url: str = "", client=None):
        self._fallback = LocalTTLCache()
        self._client = client
        if self._client is None and url:
            try:
                import redis

                self._client = redis.Redis.from_url(
                    url, socket_connect_timeout=3, socket_timeout=3
                )
                self._client.ping()
            except Exception as exc:
                logger.warning(
                    "redis unavailable; cache degrades to local",
                    extra={"action": "cache", "outcome": f"fallback:{exc}"},
                )
                self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Any | None:
        if not self._client:
            return self._fallback.get(key)
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return self._fallback.get(key)

    def set(self, key: str, value: Any, ttl: int) -> None:
        if not self._client:
            return self._fallback.set(key, value, ttl)
        try:
            self._client.set(key, json.dumps(value), ex=ttl)
        except Exception:
            self._fallback.set(key, value, ttl)

    def invalidate(self, prefix: str) -> None:
        if not self._client:
            return self._fallback.invalidate(prefix)
        try:
            for batch in self._client.scan_iter(match=f"{prefix}*", count=200):
                self._client.delete(batch)
        except Exception:
            self._fallback.invalidate(prefix)


def get_cache(backend: str = "local", redis_url: str = "") -> Cache:
    if backend == "redis":
        return RedisCache(redis_url)
    return LocalTTLCache()
