"""S3c — the generic persistent DiskCache mechanism: put/get round trip,
atomic-write/corrupt-entry safety, and the kill switch. Solid-cache and
verdict-cache integration (the two clients built on this) are covered in
``tests/test_persistent_caches.py``.
"""

import os

import pytest

from detailgen.core.diskcache import DiskCache, cache_disabled, cache_root


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
    return DiskCache("unit_test")


def test_get_on_empty_cache_is_a_clean_miss(cache):
    assert cache.get("some-key") is None
    assert cache.misses == 1
    assert cache.hits == 0


def test_put_then_get_round_trips_bytes(cache):
    cache.put("k1", b"hello world")
    assert cache.get("k1") == b"hello world"
    assert cache.hits == 1


def test_distinct_keys_do_not_collide(cache):
    cache.put("k1", b"aaa")
    cache.put("k2", b"bbb")
    assert cache.get("k1") == b"aaa"
    assert cache.get("k2") == b"bbb"


def test_write_is_atomic_no_tmp_files_left_behind(cache):
    cache.put("k1", b"payload")
    root = cache_root()
    leftover_tmp = list(root.rglob(".tmp-*"))
    assert leftover_tmp == []


def test_corrupt_entry_is_a_miss_not_a_crash(cache):
    """A DiskCache entry is raw bytes -- corruption at that layer just means
    the bytes changed, which get() can't detect (that's the deserializing
    caller's job, exercised in test_persistent_caches.py). What DiskCache
    itself must never do is raise on a missing/garbage path -- e.g. the
    parent directory disappearing between mkdir and read."""
    cache.put("k1", b"payload")
    # Simulate the cache root vanishing (e.g. a concurrent cache-clear).
    import shutil

    shutil.rmtree(cache_root(), ignore_errors=True)
    assert cache.get("k1") is None
    assert cache.misses == 1


def test_kill_switch_forces_miss_and_skips_write(cache, monkeypatch):
    cache.put("k1", b"payload")
    assert cache.get("k1") == b"payload"

    monkeypatch.setenv("DETAILGEN_NO_CACHE", "1")
    assert cache_disabled() is True
    assert cache.get("k1") is None  # kill switch: never reads, even though present
    cache.put("k2", b"should not persist")

    monkeypatch.delenv("DETAILGEN_NO_CACHE")
    assert cache.get("k2") is None  # confirms the put above was skipped


def test_cache_root_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(tmp_path / "custom"))
    assert cache_root() == tmp_path / "custom"


def test_two_disk_cache_instances_share_persisted_state(cache, tmp_path):
    """A fresh DiskCache('unit_test') pointed at the same root sees what an
    earlier instance wrote -- the mechanism a fresh PROCESS relies on."""
    cache.put("k1", b"payload")
    fresh = DiskCache("unit_test")
    assert fresh.get("k1") == b"payload"


def test_different_subdirs_are_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(tmp_path))
    a = DiskCache("solids")
    b = DiskCache("verdicts")
    a.put("k", b"solid-bytes")
    assert b.get("k") is None  # same key, different subdir -> isolated
