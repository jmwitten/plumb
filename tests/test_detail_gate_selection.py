from __future__ import annotations

from dataclasses import dataclass

import pytest

from conftest import (
    REQUIRED_DETAIL_CONTRACTS,
    _detail_gate_selection,
    _is_detail_gate_candidate,
    _load_runtime_scope_records,
    _require_complete_detail_gate,
)
from scope_manifest import build_nodes, module_paths


@dataclass(frozen=True)
class _Item:
    name: str
    markers: tuple[pytest.Mark, ...]

    @property
    def nodeid(self) -> str:
        return f"tests/test_example.py::test_{self.name}"

    def iter_markers(self, name: str | None = None):
        return tuple(
            marker for marker in self.markers
            if name is None or marker.name == name
        )


def _marker(*args, **kwargs) -> pytest.Mark:
    return pytest.mark.detail_gate(*args, **kwargs).mark


def _item(
    slug: str | None,
    *,
    contracts: tuple[str, ...] = (),
    cadence: str | None = None,
) -> _Item:
    kwargs = {"contracts": contracts}
    if cadence is not None:
        kwargs["cadence"] = cadence
    markers = () if slug is None else (_marker(slug, **kwargs),)
    return _Item(name=slug or "unmarked", markers=markers)


def test_collection_candidate_filter_skips_files_without_gate_markers(tmp_path):
    gate = tmp_path / "test_gate.py"
    gate.write_text('pytestmark = pytest.mark.detail_gate("probe", contracts=("compile",))')
    unrelated = tmp_path / "test_unrelated.py"
    unrelated.write_text("def test_unrelated(): pass")

    assert _is_detail_gate_candidate(gate) is True
    assert _is_detail_gate_candidate(unrelated) is False


def test_runtime_scope_discovers_generic_contract_without_manifest_row(
    tmp_path,
):
    manifest = tmp_path / "test_scope_manifest.csv"
    manifest.write_text("nodeid,category,owner,cadence,rationale\n")
    details = tmp_path / "details"
    details.mkdir()
    (details / "garden_shelf.spec.yaml").write_text("name: garden shelf\n")
    (details / "garden_shelf.cert.yaml").write_text(
        "schema_version: 1\n"
        "subject:\n"
        "  kind: standalone_detail\n"
        "  source: garden_shelf.spec.yaml\n"
    )

    records = _load_runtime_scope_records(manifest, details, tmp_path)

    selected = build_nodes(records, "garden_shelf")
    assert [row.nodeid for row in selected] == [
        "tests/test_certified_builds.py::test_certified_build[garden_shelf]"
    ]
    assert module_paths(selected) == ("tests/test_certified_builds.py",)


def test_selection_keeps_only_requested_slug():
    selected, deselected, contracts = _detail_gate_selection(
        [
            _item("armchair_caddy", contracts=("compile", "geometry")),
            _item("platform", contracts=("compile",)),
            _item(None),
        ],
        "armchair_caddy",
    )

    assert [row.name for row in selected] == ["armchair_caddy"]
    assert len(deselected) == 2
    assert contracts == {"compile", "geometry"}


def test_inner_gate_excludes_release_documents():
    inner = _item(
        "family_birdhouse", contracts=("compile",), cadence="inner"
    )
    release = _item(
        "family_birdhouse", contracts=("documents",), cadence="release"
    )

    selected, deselected, contracts = _detail_gate_selection(
        [inner, release], "family_birdhouse", cadence="inner"
    )

    assert selected == [inner]
    assert deselected == [release]
    assert contracts == {"compile"}


def test_release_gate_includes_inner_and_requires_documents():
    inner = _item(
        "family_birdhouse",
        contracts=tuple(REQUIRED_DETAIL_CONTRACTS),
        cadence="inner",
    )
    documents = _item(
        "family_birdhouse", contracts=("documents",), cadence="release"
    )

    selected, deselected, contracts = _detail_gate_selection(
        [inner, documents], "family_birdhouse", cadence="release"
    )
    _require_complete_detail_gate(
        "family_birdhouse",
        selected,
        contracts,
        cadence="release",
    )

    assert selected == [inner, documents]
    assert deselected == []
    assert "documents" in contracts


def test_release_gate_missing_documents_fails_closed():
    inner = _item(
        "family_birdhouse",
        contracts=tuple(REQUIRED_DETAIL_CONTRACTS),
        cadence="inner",
    )

    with pytest.raises(pytest.UsageError, match="missing contracts: documents"):
        _require_complete_detail_gate(
            "family_birdhouse",
            [inner],
            set(REQUIRED_DETAIL_CONTRACTS),
            cadence="release",
        )


def test_unknown_slug_fails_collection():
    with pytest.raises(pytest.UsageError, match="unknown detail gate"):
        _require_complete_detail_gate("missing", [], set())


def test_missing_contract_fails_collection():
    selected = [_item("armchair_caddy", contracts=("compile",))]

    with pytest.raises(
        pytest.UsageError,
        match=r"missing contracts:.*determinism",
    ):
        _require_complete_detail_gate(
            "armchair_caddy", selected, {"compile"}
        )


def test_complete_contract_is_accepted():
    selected = [_item(
        "armchair_caddy",
        contracts=tuple(REQUIRED_DETAIL_CONTRACTS),
    )]

    _require_complete_detail_gate(
        "armchair_caddy",
        selected,
        set(REQUIRED_DETAIL_CONTRACTS),
    )


def test_optional_documents_contract_is_allowed_but_not_required():
    selected, _deselected, contracts = _detail_gate_selection(
        [_item("armchair_caddy", contracts=("documents",))],
        "armchair_caddy",
    )

    assert len(selected) == 1
    assert contracts == {"documents"}
    with pytest.raises(pytest.UsageError, match="missing contracts"):
        _require_complete_detail_gate(
            "armchair_caddy", selected, contracts
        )


@pytest.mark.parametrize(
    ("marker", "message"),
    (
        (_marker(), "requires one string slug"),
        (
            _marker("armchair_caddy", contracts=("compile",), extra=True),
            "accepts only contracts= and cadence=",
        ),
        (
            _marker("armchair_caddy", contracts=()),
            "contracts must be non-empty",
        ),
        (
            _marker("armchair_caddy", contracts=("compile", 7)),
            "contracts must contain only strings",
        ),
        (
            _marker("armchair_caddy", contracts=("compile", "magic")),
            "unknown detail-gate contracts.*magic",
        ),
        (
            _marker(
                "armchair_caddy",
                contracts=("compile",),
                cadence="nightly",
            ),
            "unknown detail-gate cadence.*nightly",
        ),
    ),
)
def test_malformed_marker_fails_with_item_identity(marker, message):
    item = _Item(name="malformed", markers=(marker,))

    with pytest.raises(
        pytest.UsageError,
        match=rf"{item.nodeid}.*{message}",
    ):
        _detail_gate_selection([item], "armchair_caddy")
