"""Physical invariants that v1 generic certification cannot yet express.

The generic contract owns compilation, validation, part/BOM counts,
fabrication, connections, governance, and determinism. These tests remain
because closed-miter fit, diagonal key axes/stations, bore placement, and two
real geometry/joint mutations require richer spatial evidence than the v1
selector model exposes.
"""

import math
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry",),
)

from detailgen.components import HardwoodPanel, WoodDowel
from detailgen.core.units import IN
from detailgen.design_review import (
    load_design_review_file,
    selection_fingerprint,
)
from detailgen.spec import compile_spec, compile_spec_file, load_spec_text


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "armchair_caddy.spec.yaml"
REVIEW = ROOT / "details" / "armchair_caddy.design-review.yaml"
IMPLEMENTED_SELECTION = (
    "52e7b80496016b14ef09797dae2b783b29b03bbd0cb115eae1e2ecd5571ba40b"
)


@pytest.fixture(scope="module")
def caddy():
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def _mutated_caddy(mutate):
    raw = yaml.safe_load(SPEC.read_text())
    raw.pop("design_review", None)
    mutate(raw)
    return compile_spec(load_spec_text(yaml.safe_dump(raw, sort_keys=False)))


def test_caddy_uses_three_hardwood_panels_and_four_keys_only(caddy):
    detail, _report = caddy
    parts = detail.assembly.parts
    panels = [part for part in parts if isinstance(part.component, HardwoodPanel)]
    dowels = [part for part in parts if isinstance(part.component, WoodDowel)]

    assert len(panels) == 3
    assert len(dowels) == 4
    assert {part.name for part in panels} == {
        "top panel",
        "side panel +X",
        "side panel -X",
    }
    assert not [part for part in parts if "rail" in part.name.lower()]
    assert not [part for part in parts if "screw" in part.name.lower()]
    assert {type(conn.kind).__name__ for conn in detail.connections()} == {
        "DowelReinforcedMiter"
    }
    assert len(detail.connections()) == 2


def test_three_panel_shell_has_uniform_stock_fit_and_closed_miter_geometry(caddy):
    detail, _report = caddy
    by = detail._by_id
    top = by["top"]
    positive = by["side_pos"]
    negative = by["side_neg"]

    assert top.component.thickness == pytest.approx(0.75 * IN)
    assert positive.component.thickness == pytest.approx(0.75 * IN)
    assert negative.component.thickness == pytest.approx(0.75 * IN)
    assert top.component.length == pytest.approx(8 * IN)
    assert positive.component.length == pytest.approx(7.75 * IN)
    assert negative.component.length == pytest.approx(7.75 * IN)

    top_bb = top.world_solid().val().BoundingBox()
    pos_bb = positive.world_solid().val().BoundingBox()
    neg_bb = negative.world_solid().val().BoundingBox()
    assert top_bb.xlen == pytest.approx(8 * IN)
    assert top_bb.zmin == pytest.approx(0.0)
    assert top_bb.zmax == pytest.approx(0.75 * IN)
    assert pos_bb.xmin == pytest.approx(3.25 * IN)
    assert neg_bb.xmax == pytest.approx(-3.25 * IN)
    assert pos_bb.zmin == pytest.approx(-7 * IN)
    assert neg_bb.zmin == pytest.approx(-7 * IN)
    assert pos_bb.zmax == pytest.approx(0.75 * IN)
    assert neg_bb.zmax == pytest.approx(0.75 * IN)
    assert pos_bb.xmin - neg_bb.xmax == pytest.approx(6.5 * IN)


def test_four_dowels_match_precedent_size_stations_and_diagonal_axes(caddy):
    detail, _report = caddy
    dowels = sorted(
        (part for part in detail.assembly.parts
         if isinstance(part.component, WoodDowel)),
        key=lambda part: part.name,
    )

    assert all(part.component.diameter == pytest.approx(0.375 * IN)
               for part in dowels)
    assert all(part.component.length == pytest.approx(math.sqrt(2) * 0.75 * IN)
               for part in dowels)
    assert all(part.component.end_trim == "miter_flush" for part in dowels)
    stations = sorted(round(part.world_frame.origin[1] / IN, 6) for part in dowels)
    assert stations == [-1.5625, -1.5625, 1.5625, 1.5625]
    axes = {tuple(round(value, 6) for value in part.world_frame.x_axis)
            for part in dowels}
    diagonal = round(1 / math.sqrt(2), 6)
    assert axes == {(diagonal, 0.0, -diagonal),
                    (-diagonal, 0.0, -diagonal)}

    top = detail._by_id["top"].world_solid()
    for part in dowels:
        side = detail._by_id[
            "side_pos" if "+X" in part.name else "side_neg"
        ].world_solid()
        outside_panels = part.world_solid().cut(top.union(side)).val().Volume()
        assert outside_panels == pytest.approx(0.0, abs=1e-5)


def test_top_retains_centered_three_and_half_inch_cup_bore(caddy):
    detail, _report = caddy
    record = detail._by_id["top"].component.fabrication_record("top")
    (bore,) = [step for step in record.steps if step.kind == "bore"]

    assert bore.param("feature") == "cup hole"
    assert 2 * bore.param("radius") == pytest.approx(3.5 * IN)
    assert bore.param("cx") == pytest.approx(4 * IN)
    assert bore.param("cy") == pytest.approx(2.75 * IN)


def test_bom_contains_three_panels_four_dowels_and_no_legacy_hardware(caddy):
    detail, _report = caddy
    rows = detail.assembly.bom_table()

    assert sum(row["qty"] for row in rows if row["item"] == "3/4 in hardwood panel") == 3
    assert sum(row["qty"] for row in rows if row["item"] == "3/8 in hardwood dowel") == 4
    visible = " ".join(row["item"].lower() for row in rows)
    assert "rail" not in visible
    assert "screw" not in visible
    assert "5/4" not in visible


def test_implemented_selection_and_model_are_owner_confirmed(caddy):
    detail, _report = caddy
    review = load_design_review_file(REVIEW)

    assert review.decision.application == "implemented"
    assert selection_fingerprint(review) == IMPLEMENTED_SELECTION
    assert review.modeling_approval is not None
    assert review.modeling_approval.approved_by == "Joel Witten"
    assert review.modeling_approval.selection_fingerprint == IMPLEMENTED_SELECTION
    assert review.delivery_confirmation is not None
    assert review.delivery_confirmation.approved_by == "Joel Witten"
    assert review.delivery_confirmation.selection_fingerprint == IMPLEMENTED_SELECTION
    assert (
        review.delivery_confirmation.model_fingerprint
        == detail.design_governance.model_digest
    )
    assert detail.require_modeling_approval() is detail
    assert detail.require_delivery_ready().ok


def test_caddy_keyed_miter_rejects_extra_hardware():
    """The selected joint cannot be silently padded with a third key."""
    def add_third_key(raw):
        raw["connections"][0]["hardware"].append("dowel_neg_near")

    with pytest.raises(ValueError, match=r"expected 2 hardware item\(s\).+got 3"):
        _mutated_caddy(add_third_key).validate()


def test_caddy_synthetic_oversized_corner_keys_fail_interference():
    """An implausibly large key must collide with the sofa-arm context."""
    detail = _mutated_caddy(
        lambda raw: raw["params"].update(dowel_dia=2.0)
    )

    report = detail.validate()

    failures = [
        finding
        for finding in report.failures
        if finding.check == "interference" and "corner key" in finding.subject
    ]
    assert len(failures) == 4
    assert all("sofa arm" in finding.subject for finding in failures)
    assert all("unexpected overlap" in finding.detail for finding in failures)
