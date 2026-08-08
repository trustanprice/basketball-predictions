import time

from live_client.cache import DiskCache


def test_set_then_get_roundtrip(tmp_path):
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("EndpointA", {"Season": "2023-24"}, {"data": 1})
    assert cache.get("EndpointA", {"Season": "2023-24"}) == {"data": 1}


def test_get_miss_returns_none(tmp_path):
    cache = DiskCache(cache_dir=tmp_path)
    assert cache.get("EndpointA", {"Season": "2023-24"}) is None


def test_different_params_are_different_cache_entries(tmp_path):
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("EndpointA", {"Season": "2023-24"}, {"data": "a"})
    cache.set("EndpointA", {"Season": "2024-25"}, {"data": "b"})
    assert cache.get("EndpointA", {"Season": "2023-24"}) == {"data": "a"}
    assert cache.get("EndpointA", {"Season": "2024-25"}) == {"data": "b"}


def test_param_key_order_does_not_matter(tmp_path):
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("EndpointA", {"a": 1, "b": 2}, {"data": 1})
    assert cache.get("EndpointA", {"b": 2, "a": 1}) == {"data": 1}


def test_force_refresh_bypasses_cache(tmp_path):
    cache = DiskCache(cache_dir=tmp_path)
    cache.set("EndpointA", {}, {"data": 1})
    assert cache.get("EndpointA", {}, force_refresh=True) is None


def test_ttl_expiry(tmp_path):
    cache = DiskCache(cache_dir=tmp_path, ttl_seconds=0.05)
    cache.set("EndpointA", {}, {"data": 1})
    assert cache.get("EndpointA", {}) == {"data": 1}
    time.sleep(0.1)
    assert cache.get("EndpointA", {}) is None


def test_no_ttl_never_expires(tmp_path):
    cache = DiskCache(cache_dir=tmp_path, ttl_seconds=None)
    cache.set("EndpointA", {}, {"data": 1})
    time.sleep(0.05)
    assert cache.get("EndpointA", {}) == {"data": 1}
