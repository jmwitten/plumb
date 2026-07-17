from __future__ import annotations

import csv
from pathlib import Path

import pytest

from conftest import (
    _is_ordinary_full_collection,
    _require_platform_tier,
    _validate_scope_options,
)
from scope_manifest import (
    ScopeManifestError,
    ScopeRecord,
    augment_certification_nodes,
    build_nodes,
    load_scope_manifest,
    module_paths,
    platform_nodes,
    reconcile_scope_manifest,
)


FIELDNAMES = ("nodeid", "category", "owner", "cadence", "rationale")


def _write_manifest(tmp_path: Path, rows: list[tuple[str, ...]]) -> Path:
    path = tmp_path / "scope.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(FIELDNAMES)
        writer.writerows(rows)
    return path


def test_every_record_has_one_closed_category(tmp_path):
    path = _write_manifest(
        tmp_path,
        [
            (
                "tests/test_x.py::test_x",
                "mystery",
                "plumb-platform",
                "unit",
                "pure shared rule",
            )
        ],
    )

    with pytest.raises(ScopeManifestError, match="unknown category 'mystery'"):
        load_scope_manifest(path)


def test_reconciliation_fails_for_unclassified_and_retired_nodes():
    records = (
        ScopeRecord(
            nodeid="tests/test_x.py::test_old",
            category="platform",
            owner="plumb-platform",
            cadence="unit",
            rationale="pure shared rule",
        ),
    )

    with pytest.raises(
        ScopeManifestError,
        match=r"unclassified=.*test_new.*retired=.*test_old",
    ):
        reconcile_scope_manifest(records, {"tests/test_x.py::test_new"})


def test_duplicate_nodeids_fail_closed(tmp_path):
    row = (
        "tests/test_x.py::test_x",
        "platform",
        "plumb-platform",
        "unit",
        "pure shared rule",
    )
    path = _write_manifest(tmp_path, [row, row])

    with pytest.raises(ScopeManifestError, match="duplicate nodeid"):
        load_scope_manifest(path)


def test_generic_parameterized_node_can_belong_to_one_build(tmp_path):
    path = _write_manifest(
        tmp_path,
        [
            (
                "tests/test_certified_builds.py::test_certified_build[family_birdhouse]",
                "document_build_accuracy",
                "family_birdhouse",
                "inner",
                "normal accepted-model certification",
            ),
            (
                "tests/test_bbox_prefilter.py::test_platform_prefilter_agrees_with_unfiltered",
                "platform",
                "plumb-platform",
                "audit",
                "exhaustive shared-algorithm oracle",
            ),
        ],
    )

    rows = load_scope_manifest(path)

    assert [row.nodeid for row in build_nodes(rows, "family_birdhouse")] == [
        "tests/test_certified_builds.py::test_certified_build[family_birdhouse]"
    ]


def test_certification_contracts_fill_only_missing_generic_scope_records():
    explicit = ScopeRecord(
        nodeid="tests/test_certified_builds.py::test_certified_build[existing]",
        category="document_build_accuracy",
        owner="existing",
        cadence="inner",
        rationale="explicit rationale",
    )

    records = augment_certification_nodes(
        (explicit,), ("future_build", "existing", "future_build")
    )

    assert records[0] is explicit
    assert records[1] == ScopeRecord(
        nodeid=(
            "tests/test_certified_builds.py::"
            "test_certified_build[future_build]"
        ),
        category="document_build_accuracy",
        owner="future_build",
        cadence="inner",
        rationale=(
            "Generic certification node discovered from "
            "details/future_build.cert.yaml."
        ),
    )
    reconcile_scope_manifest(records, {row.nodeid for row in records})


@pytest.mark.parametrize(
    ("category", "owner", "cadence", "message"),
    (
        ("platform", "family_birdhouse", "unit", "platform owner"),
        (
            "document_build_accuracy",
            "plumb-platform",
            "inner",
            "build owner",
        ),
        ("platform", "plumb-platform", "inner", "platform cadence"),
        (
            "document_build_accuracy",
            "family_birdhouse",
            "audit",
            "build cadence",
        ),
    ),
)
def test_category_owner_and_cadence_must_agree(
    tmp_path, category, owner, cadence, message
):
    path = _write_manifest(
        tmp_path,
        [
            (
                "tests/test_x.py::test_x",
                category,
                owner,
                cadence,
                "classification rationale",
            )
        ],
    )

    with pytest.raises(ScopeManifestError, match=message):
        load_scope_manifest(path)


def test_release_nodes_are_opt_in_for_a_build(tmp_path):
    path = _write_manifest(
        tmp_path,
        [
            (
                "tests/test_build.py::test_model",
                "document_build_accuracy",
                "family_birdhouse",
                "inner",
                "accepted model",
            ),
            (
                "tests/test_build.py::test_documents",
                "document_build_accuracy",
                "family_birdhouse",
                "release",
                "accepted package",
            ),
        ],
    )
    rows = load_scope_manifest(path)

    assert [row.nodeid for row in build_nodes(rows, "family_birdhouse")] == [
        "tests/test_build.py::test_model"
    ]
    assert [
        row.nodeid
        for row in build_nodes(rows, "family_birdhouse", include_release=True)
    ] == [
        "tests/test_build.py::test_model",
        "tests/test_build.py::test_documents",
    ]


def test_platform_tier_selection_is_exact(tmp_path):
    path = _write_manifest(
        tmp_path,
        [
            (
                "tests/test_a.py::test_unit",
                "platform",
                "plumb-platform",
                "unit",
                "pure rule",
            ),
            (
                "tests/test_b.py::test_integration",
                "platform",
                "plumb-platform",
                "integration",
                "live subsystem",
            ),
            (
                "tests/test_c.py::test_audit",
                "platform",
                "plumb-platform",
                "audit",
                "exhaustive oracle",
            ),
        ],
    )

    assert [row.nodeid for row in platform_nodes(load_scope_manifest(path), "audit")] == [
        "tests/test_c.py::test_audit"
    ]

    with pytest.raises(ScopeManifestError, match="unknown platform tier"):
        platform_nodes(load_scope_manifest(path), "nightly")


def test_module_paths_are_derived_from_selected_nodeids(tmp_path):
    path = _write_manifest(
        tmp_path,
        [
            (
                "tests/test_b.py::test_second",
                "platform",
                "plumb-platform",
                "audit",
                "oracle",
            ),
            (
                "tests/test_a.py::TestGroup::test_first[param]",
                "platform",
                "plumb-platform",
                "audit",
                "oracle",
            ),
            (
                "tests/test_b.py::test_third",
                "platform",
                "plumb-platform",
                "audit",
                "oracle",
            ),
        ],
    )

    assert module_paths(load_scope_manifest(path)) == (
        "tests/test_a.py",
        "tests/test_b.py",
    )


def test_only_an_unfiltered_full_collection_reconciles_every_manifest_node():
    assert _is_ordinary_full_collection(["tests"]) is True
    assert _is_ordinary_full_collection([]) is True
    assert _is_ordinary_full_collection(["tests/test_scope_manifest.py"]) is False
    assert _is_ordinary_full_collection(
        ["tests"], detail_gate="family_birdhouse"
    ) is False
    assert _is_ordinary_full_collection(["tests"], platform_tier="audit") is False


def test_build_and_platform_selectors_are_mutually_exclusive():
    with pytest.raises(
        pytest.UsageError,
        match="cannot combine --detail-gate with --platform-tier",
    ):
        _validate_scope_options("family_birdhouse", "audit")

    _validate_scope_options("family_birdhouse", None)
    _validate_scope_options(None, "integration")


def test_platform_tier_with_zero_selected_nodes_fails_closed():
    with pytest.raises(pytest.UsageError, match="platform tier 'audit'.*no tests"):
        _require_platform_tier("audit", [])
