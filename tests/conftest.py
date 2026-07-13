"""Shared test fixtures.

S3c (persistent solid + verdict caches, ``core.diskcache``) made
``Component.solid``/``validation.checks`` read and write a real on-disk
cache by default. Without isolation here, that cache would default to the
repo's real ``outputs/cache/`` for every test, which two things then
break:

1. **Cross-test leakage.** Tests run in one process/session; a component
   built in an earlier test file (e.g. ``test_platform_detail.py``
   building a full Platform, whose hardware happens to share a
   ``cache_key()`` with something a later test in
   ``test_reproducible_builds.py`` builds fresh) would silently reuse that
   entry, breaking any test that resets the IN-RUN caches
   (``_reset_solid_cache``/``_reset_local_digest_cache``) to assert a
   "genuinely fresh build" and, pre-S3c, could assume that reset was
   equivalent to "never built before" — no longer true with a persistent
   tier unless each test also gets a private cache root.
2. **State bleeding into the real repo directory** from a test run at all
   (``outputs/`` is gitignored and meant to hold only regenerated
   artifacts, not test scratch).

This autouse fixture gives every test its own empty ``DETAILGEN_CACHE_DIR``
— a fresh directory from ``tmp_path_factory``, deliberately NOT a
subdirectory of that test's own ``tmp_path`` (a test may use ``tmp_path``
itself as a render/export target and assert on its exact contents — see
``test_detail_base.py::test_no_public_export_verb_bypasses_the_gate``,
which asserts zero files were written there; nesting the cache under
``tmp_path`` would make every such test see a stray ``detailgen_cache/``
entry it never wrote). The persistent tier is exercised for real (real
disk I/O, real BREP round trips) WITHIN a test, since a single test's own
reset-then-rebuild sequence still sees genuine hits, but never carries
anything across tests or into the real cache. A test that wants a
DIFFERENT cache root (e.g. to assert two ``DiskCache``/``Component``
instances share a directory across a simulated "fresh process") overrides
this by setting ``DETAILGEN_CACHE_DIR`` itself, same as any other
``monkeypatch.setenv`` — this fixture just supplies the default.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolated_detailgen_cache_dir(tmp_path_factory, monkeypatch):
    cache_dir = tmp_path_factory.mktemp("detailgen_cache")
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
