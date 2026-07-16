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

from pathlib import Path

import pytest

from scope_manifest import (
    ScopeManifestError,
    build_nodes,
    load_scope_manifest,
    module_paths,
    reconcile_scope_manifest,
)


TESTS_DIR = Path(__file__).resolve().parent
SCOPE_MANIFEST = TESTS_DIR / "test_scope_manifest.csv"

REQUIRED_DETAIL_CONTRACTS = frozenset({
    "compile",
    "geometry",
    "validation",
    "connections",
    "fabrication",
    "bom",
    "governance",
    "intent",
    "determinism",
})
ALLOWED_DETAIL_CONTRACTS = REQUIRED_DETAIL_CONTRACTS | {"documents"}


def _is_ordinary_full_collection(
    args,
    *,
    detail_gate=None,
    platform_tier=None,
):
    """Return whether collection should exactly reconcile the full manifest."""
    if detail_gate or platform_tier:
        return False
    if not args:
        return True
    if len(args) != 1:
        return False
    raw = str(args[0]).split("::", 1)[0]
    try:
        return Path(raw).resolve() == TESTS_DIR
    except OSError:
        return False


def _is_detail_gate_candidate(path: str | Path) -> bool:
    """Return whether a test module can declare a semantic detail gate."""
    path = Path(path)
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return False
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return True
    return "pytest.mark.detail_gate" in source


def _detail_gate_selection(items, slug, *, cadence="inner"):
    """Return tests for ``slug`` plus their declared semantic contracts."""
    if cadence not in {"inner", "release"}:
        raise pytest.UsageError(f"unknown detail-gate cadence {cadence!r}")
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
            if "contracts" not in marker.kwargs or not set(marker.kwargs) <= {
                "contracts",
                "cadence",
            }:
                raise pytest.UsageError(
                    f"{item.nodeid}: detail_gate accepts only contracts= "
                    "and cadence="
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
            unknown = set(declared) - ALLOWED_DETAIL_CONTRACTS
            if unknown:
                raise pytest.UsageError(
                    f"{item.nodeid}: unknown detail-gate contracts "
                    f"{sorted(unknown)}"
                )
            marker_cadence = marker.kwargs.get("cadence", "inner")
            if marker_cadence not in {"inner", "release"}:
                raise pytest.UsageError(
                    f"{item.nodeid}: unknown detail-gate cadence "
                    f"{marker_cadence!r}"
                )
            cadence_matches = (
                marker_cadence == "inner" or cadence == "release"
            )
            if marker.args[0] == slug and cadence_matches:
                matched = True
                contracts.update(declared)
        (selected if matched else deselected).append(item)
    return selected, deselected, contracts


def _require_complete_detail_gate(
    slug, selected, contracts, *, cadence="inner"
):
    """Fail closed when a requested gate is unknown or semantically thin."""
    if not selected:
        raise pytest.UsageError(f"unknown detail gate {slug!r}")
    required = set(REQUIRED_DETAIL_CONTRACTS)
    if cadence == "release":
        required.add("documents")
    missing = required - contracts
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
    group.addoption(
        "--detail-cadence",
        action="store",
        choices=("inner", "release"),
        default="inner",
        help="run the fast accepted-model gate or include release documents",
    )


def _scope_records(config):
    records = getattr(config, "_plumb_scope_records", None)
    if records is None:
        records = load_scope_manifest(SCOPE_MANIFEST)
        config._plumb_scope_records = records
    return records


def _requested_build_records(config):
    return build_nodes(
        _scope_records(config),
        config.getoption("detail_gate"),
        include_release=config.getoption("detail_cadence") == "release",
    )


def pytest_ignore_collect(collection_path, config):
    """Avoid importing unrelated test modules during a focused detail gate."""
    if not config.getoption("detail_gate"):
        return None
    path = Path(str(collection_path))
    if path.suffix != ".py" or not path.name.startswith("test_"):
        return None
    try:
        relative = path.resolve().relative_to(Path(str(config.rootpath)).resolve())
    except ValueError:
        return True
    return relative.as_posix() not in set(
        module_paths(_requested_build_records(config))
    )


def pytest_collection_modifyitems(config, items):
    slug = config.getoption("detail_gate")
    cadence = config.getoption("detail_cadence")
    platform_tier = config.getoption("platform_tier", default=None)
    if not slug:
        if _is_ordinary_full_collection(
            config.args,
            detail_gate=slug,
            platform_tier=platform_tier,
        ):
            try:
                reconcile_scope_manifest(
                    load_scope_manifest(SCOPE_MANIFEST),
                    {item.nodeid for item in items},
                )
            except ScopeManifestError as exc:
                raise pytest.UsageError(str(exc)) from exc
        return
    selected_nodeids = {
        record.nodeid for record in _requested_build_records(config)
    }
    selected = [item for item in items if item.nodeid in selected_nodeids]
    deselected = [item for item in items if item.nodeid not in selected_nodeids]
    _marker_selected, _marker_deselected, contracts = _detail_gate_selection(
        items, slug, cadence=cadence
    )
    _require_complete_detail_gate(
        slug, selected, contracts, cadence=cadence
    )
    config.hook.pytest_deselected(items=deselected)
    items[:] = selected


@pytest.fixture(autouse=True)
def _isolated_detailgen_cache_dir(tmp_path_factory, monkeypatch):
    cache_dir = tmp_path_factory.mktemp("detailgen_cache")
    monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(cache_dir))
    monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
