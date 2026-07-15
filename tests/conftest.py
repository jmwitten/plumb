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


REQUIRED_DETAIL_CONTRACTS = frozenset({
    "compile",
    "geometry",
    "validation",
    "fabrication",
    "governance",
    "documents",
})


def _detail_gate_selection(items, slug):
    """Return tests for ``slug`` plus their declared semantic contracts."""
    selected = []
    deselected = []
    contracts = set()
    for item in items:
        matched = False
        for marker in item.iter_markers(name="detail_gate"):
            if len(marker.args) != 1 or not isinstance(marker.args[0], str):
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate requires one string slug"
                )
            if set(marker.kwargs) != {"contracts"}:
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate accepts only contracts="
                )
            declared = marker.kwargs["contracts"]
            if not isinstance(declared, (tuple, list)) or not declared:
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate contracts must be non-empty"
                )
            if not all(isinstance(contract, str) for contract in declared):
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate contracts must contain "
                    "only strings"
                )
            unknown = set(declared) - REQUIRED_DETAIL_CONTRACTS
            if unknown:
                raise pytest.UsageError(
                    f"{item.nodeid}: unknown detail-gate contracts "
                    f"{sorted(unknown)}"
                )
            if marker.args[0] == slug:
                matched = True
                contracts.update(declared)
        (selected if matched else deselected).append(item)
    return selected, deselected, contracts


def _require_complete_detail_gate(slug, selected, contracts):
    """Fail closed when a requested gate is unknown or semantically thin."""
    if not selected:
        raise pytest.UsageError(f"unknown detail gate {slug!r}")
    missing = REQUIRED_DETAIL_CONTRACTS - contracts
    if missing:
        raise pytest.UsageError(
            f"detail gate {slug!r} is missing contracts: "
            f"{', '.join(sorted(missing))}"
        )


def pytest_addoption(parser):
    group = parser.getgroup("detail build gates")
    group.addoption(
        "--detail-gate",
        action="store",
        default=None,
        metavar="SLUG",
        help="run the complete semantic build gate for one detail",
    )


def pytest_collection_modifyitems(config, items):
    slug = config.getoption("detail_gate")
    if not slug:
        return
    selected, deselected, contracts = _detail_gate_selection(items, slug)
    _require_complete_detail_gate(slug, selected, contracts)
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected


@pytest.fixture(autouse=True)
def _isolated_detailgen_cache_dir(tmp_path_factory, monkeypatch):
    cache_dir = tmp_path_factory.mktemp("detailgen_cache")
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
