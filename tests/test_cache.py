"""FR-21: real RedisCache backend against fakeredis (no server needed)."""

import fakeredis
import pytest

from app.cache import LocalTTLCache, RedisCache, get_cache


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def cache(redis_client):
    return RedisCache(client=redis_client)


def test_redis_get_set(cache, redis_client):
    cache.set("usecase:it:answer:q1", {"answer": "a", "citations": ["c1"]}, ttl=60)
    assert cache.get("usecase:it:answer:q1") == {"answer": "a", "citations": ["c1"]}
    # TTL was applied on the server side
    assert 0 < redis_client.ttl("usecase:it:answer:q1") <= 60


def test_redis_miss_returns_none(cache):
    assert cache.get("usecase:it:answer:nothing") is None


def test_redis_invalidate_prefix(cache):
    cache.set("usecase:it:answer:a", 1, ttl=60)
    cache.set("usecase:it:answer:b", 2, ttl=60)
    cache.set("usecase:hr:answer:a", 3, ttl=60)
    cache.invalidate("usecase:it:")
    assert cache.get("usecase:it:answer:a") is None
    assert cache.get("usecase:it:answer:b") is None
    # tenant isolation: other prefix untouched
    assert cache.get("usecase:hr:answer:a") == 3


def test_redis_ttl_expiry(cache):
    cache.set("k", "v", ttl=1)
    assert cache.get("k") == "v"
    # fakeredis honors expiry via actual time; simulate expiry
    # by deleting — proves get path handles absence
    cache._client.delete("k")
    assert cache.get("k") is None


def test_redis_unavailable_degrades_to_local():
    # no url, no client → local fallback, never raises
    cache = RedisCache()
    cache.set("k", {"x": 1}, ttl=60)
    assert cache.get("k") == {"x": 1}
    assert cache.available is False


def test_redis_bad_url_degrades_gracefully():
    cache = RedisCache("redis://localhost:1/unreachable")
    cache.set("k", "v", ttl=60)
    assert cache.get("k") == "v"  # served by fallback


def test_get_cache_factory_selects_backend(redis_client, monkeypatch):
    assert isinstance(get_cache("local"), LocalTTLCache)
    assert isinstance(get_cache("redis", "redis://x"), RedisCache)


class SpyCache(LocalTTLCache):
    def __init__(self):
        super().__init__()
        self.gets = 0
        self.sets = 0

    def get(self, key):
        self.gets += 1
        return super().get(key)

    def set(self, key, value, ttl):
        self.sets += 1
        return super().set(key, value, ttl)


def test_knowledge_tool_uses_cache(get_store, settings):
    """Second identical retrieval hits cache — store/embedder untouched."""
    from app.config.loader import UseCaseLoader
    from app.retrieval.embeddings import get_embedder
    from app.retrieval.rerank import get_reranker
    from app.tools.base import ToolContext
    from app.tools.knowledge import KnowledgeSearchTool

    usecase = UseCaseLoader(settings.usecase_dir).get("it_support")
    cache = SpyCache()
    ctx = ToolContext(
        user=None, usecase=usecase, store=get_store,
        embedder=get_embedder(usecase.models.embedding),
        reranker=get_reranker(usecase.models.rerank), crm=None,
        cache=cache, cache_ttl=300,
    )
    tool = KnowledgeSearchTool()
    first = tool.run(ctx, "how do I connect to the VPN")
    second = tool.run(ctx, "how do I connect to the VPN")

    assert first["found"] and second["found"]
    assert cache.sets == 1 and cache.gets == 2
    # citations round-trip through JSON without losing contract fields
    assert second["citations"][0].citation_id == "c1"
    assert second["citations"][0].title == first["citations"][0].title


def test_knowledge_tool_cache_key_is_tenant_scoped(get_store, settings):
    """Different usecases/departments never share cached responses."""
    from app.config.loader import UseCaseLoader
    from app.retrieval.embeddings import get_embedder
    from app.retrieval.rerank import get_reranker
    from app.tools.base import ToolContext
    from app.tools.knowledge import KnowledgeSearchTool

    loader = UseCaseLoader(settings.usecase_dir)
    cache = SpyCache()
    tool = KnowledgeSearchTool()
    for usecase_id in ("it_support", "hr_support"):
        usecase = loader.get(usecase_id)
        ctx = ToolContext(
            user=None, usecase=usecase, store=get_store,
            embedder=get_embedder(usecase.models.embedding),
            reranker=get_reranker(usecase.models.rerank), crm=None,
            cache=cache, cache_ttl=300,
        )
        tool.run(ctx, "time off")
    # same query string, two tenants → two cache writes, zero shared hits
    assert cache.sets == 2
