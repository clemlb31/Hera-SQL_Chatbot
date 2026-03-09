import time
from src.cache import QueryCache


def test_set_and_get():
    cache = QueryCache(ttl=10)
    cache.set("SELECT 1", {"rows": [1]})
    assert cache.get("SELECT 1") == {"rows": [1]}


def test_get_miss():
    cache = QueryCache()
    assert cache.get("SELECT 999") is None


def test_key_normalization():
    """Same SQL with different casing/whitespace should hit same cache entry."""
    cache = QueryCache()
    cache.set("  SELECT 1  ", {"rows": [1]})
    assert cache.get("select 1") == {"rows": [1]}


def test_ttl_expiry():
    cache = QueryCache(ttl=0)
    cache.set("SELECT 1", {"rows": [1]})
    time.sleep(0.01)
    assert cache.get("SELECT 1") is None


def test_lru_eviction():
    cache = QueryCache(ttl=60, max_size=2)
    cache.set("SELECT 1", {"a": 1})
    cache.set("SELECT 2", {"a": 2})
    cache.set("SELECT 3", {"a": 3})  # Should evict oldest (SELECT 1)
    assert cache.get("SELECT 1") is None
    assert cache.get("SELECT 2") == {"a": 2}
    assert cache.get("SELECT 3") == {"a": 3}


def test_invalidate_all():
    cache = QueryCache()
    cache.set("SELECT 1", {"a": 1})
    cache.set("SELECT 2", {"a": 2})
    cache.invalidate_all()
    assert cache.get("SELECT 1") is None
    assert cache.get("SELECT 2") is None
