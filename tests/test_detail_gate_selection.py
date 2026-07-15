from __future__ import annotations

from dataclasses import dataclass

import pytest

from conftest import (
    REQUIRED_DETAIL_CONTRACTS,
    _detail_gate_selection,
    _require_complete_detail_gate,
)


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
) -> _Item:
    markers = () if slug is None else (
        _marker(slug, contracts=contracts),
    )
    return _Item(name=slug or "unmarked", markers=markers)


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


def test_unknown_slug_fails_collection():
    with pytest.raises(pytest.UsageError, match="unknown detail gate"):
        _require_complete_detail_gate("missing", [], set())


def test_missing_contract_fails_collection():
    selected = [_item("armchair_caddy", contracts=("compile",))]

    with pytest.raises(
        pytest.UsageError,
        match=r"missing contracts:.*documents",
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


@pytest.mark.parametrize(
    ("marker", "message"),
    (
        (_marker(), "requires one string slug"),
        (
            _marker("armchair_caddy", contracts=("compile",), extra=True),
            "accepts only contracts=",
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
    ),
)
def test_malformed_marker_fails_with_item_identity(marker, message):
    item = _Item(name="malformed", markers=(marker,))

    with pytest.raises(
        pytest.UsageError,
        match=rf"{item.nodeid}.*{message}",
    ):
        _detail_gate_selection([item], "armchair_caddy")
