from __future__ import annotations

from app.services.cache import TTLCache


def test_ttl_cache_set_get(monkeypatch):
    times = {"value": 100.0}

    def fake_monotonic():
        return times["value"]

    monkeypatch.setattr("app.services.cache.time.monotonic", fake_monotonic)

    cache = TTLCache[str](ttl_s=10.0, max_size=10)
    cache.set("key", "value")
    assert cache.get("key") == "value"

    times["value"] = 111.0
    assert cache.get("key") is None


def test_ttl_cache_evicts_oldest(monkeypatch):
    times = {"value": 0.0}

    def fake_monotonic():
        return times["value"]

    monkeypatch.setattr("app.services.cache.time.monotonic", fake_monotonic)

    cache = TTLCache[str](ttl_s=100.0, max_size=2)
    cache.set("a", "one")
    times["value"] = 1.0
    cache.set("b", "two")
    times["value"] = 2.0
    cache.set("c", "three")

    assert cache.get("a") is None
    assert cache.get("b") == "two"
    assert cache.get("c") == "three"
