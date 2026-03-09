import hashlib
import time


class QueryCache:
    """In-memory cache for SQL query results with TTL and LRU eviction."""

    def __init__(self, ttl: int = 300, max_size: int = 100):
        self._cache: dict[str, tuple[dict, float]] = {}
        self.ttl = ttl
        self.max_size = max_size

    def _key(self, sql: str) -> str:
        return hashlib.sha256(sql.strip().lower().encode()).hexdigest()

    def get(self, sql: str) -> dict | None:
        key = self._key(sql)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < self.ttl:
                return result
            del self._cache[key]
        return None

    def set(self, sql: str, result: dict) -> None:
        if len(self._cache) >= self.max_size:
            oldest = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest]
        self._cache[self._key(sql)] = (result, time.time())

    def invalidate_all(self) -> None:
        self._cache.clear()
