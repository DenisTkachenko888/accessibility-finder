from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Generic, Optional, Tuple, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    """Simple in-memory TTL cache with max size eviction."""

    def __init__(self, *, ttl_s: float, max_size: int) -> None:
        self.ttl_s = ttl_s
        self.max_size = max_size
        self._store: Dict[str, CacheEntry[T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[T]:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at < now:
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: T) -> None:
        now = time.monotonic()
        with self._lock:
            self._purge_expired(now)
            if len(self._store) >= self.max_size:
                self._evict_oldest()
            self._store[key] = CacheEntry(value=value, expires_at=now + self.ttl_s)

    def _purge_expired(self, now: float) -> None:
        expired_keys = [key for key, entry in self._store.items() if entry.expires_at < now]
        for key in expired_keys:
            self._store.pop(key, None)

    def _evict_oldest(self) -> None:
        if not self._store:
            return
        oldest_key = min(self._store.items(), key=lambda item: item[1].expires_at)[0]
        self._store.pop(oldest_key, None)


def make_cache_key(*parts: object) -> str:
    return "|".join(str(part) for part in parts)
