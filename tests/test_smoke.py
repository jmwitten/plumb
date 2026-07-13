"""Smoke tests: components build, validation catches real problems,
and the example detail validates clean."""

import sys
from pathlib import Path

import pytest

from detailgen.core import IN, FT
from detailgen.components import (
    Lumber, ConcretePier, LagScrew, Washer, JoistHanger, PostBase,
    AngleBracket, HexBolt, HexNut, ThreadedRod, Boulder, Epoxy, PierBlock,
)
from detailgen.assemblies import DetailAssembly
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation import validate_assembly

DETAILS = Path(__file__).resolve().parents[1] / "details"
# ``deck_ledger_example`` is a demo detail that stays on the imperative path
# (it is not one of the four spec-mirrored details); import it by adding the
# details dir to the path, as test_example_detail_is_clean does below.
sys.path.insert(0, str(DETAILS))


def test_lumber_dimensions():
    joist = Lumber("2x8", length=8 * FT)
    bb = joist.bounding_box()
    assert bb.xlen == pytest.approx(8 * FT)
    assert bb.ylen == pytest.approx(1.5 * IN)
    assert bb.zlen == pytest.approx(7.25 * IN)
    assert joist.check() == []


def test_lumber_check_flags_over_stock():
    assert Lumber("2x8", length=24 * FT).check()


def test_components_build():
    pier = ConcretePier(10 * IN, 54 * IN)
    lag = LagScrew(0.5 * IN, 4 * IN)
    washer = Washer(9 / 16 * IN)
    hanger = JoistHanger(1.5 * IN, 7.25 * IN)
    base = PostBase(5.5 * IN)

    for comp in (pier, lag, washer, hanger, base):
        assert comp.volume() > 0, comp

    # exact dimensions from the real solid, not just "nonzero volume" — a
    # shrunk extrusion (e.g. ConcretePier's depth) still has positive volume
    # but fails these.
    pier_bb = pier.bounding_box()
    assert pier_bb.zlen == pytest.approx(54 * IN)
    assert pier_bb.xlen == pytest.approx(10 * IN)
    assert pier_bb.ylen == pytest.approx(10 * IN)

    washer_bb = washer.bounding_box()
    assert washer_bb.zlen == pytest.approx(washer.thickness)
    assert washer_bb.xlen == pytest.approx(washer.outer_diameter)

    lag_bb = lag.bounding_box()
    assert lag_bb.zlen == pytest.approx(lag.length + lag.head_height)


def test_validation_catches_overlap():
    detail = DetailAssembly("clash")
    detail.add(Lumber("2x4", length=1 * FT, name="a"))
    detail.add(Lumber("2x4", length=1 * FT, name="b"), at=(0, 0.5 * IN, 0))
    report = validate_assembly(detail)
    assert not report.ok
    with pytest.raises(AssertionError):
        report.require_clean()


def test_example_detail_is_clean():
    import deck_ledger_example

    detail = deck_ledger_example.build()
    report = validate_assembly(
        detail,
        expected_overlaps={
            ("lag 1", "ledger"), ("lag 1", "house rim"),
            ("lag 2", "ledger"), ("lag 2", "house rim"),
        },
        contacts=[
            ("ledger", "house rim"),
            ("joist hanger", "ledger"),
            ("joist", "joist hanger"),
        ],
    )
    assert report.ok, str(report)


def test_detail_grade_components_build():
    """The engineering-grade parts all produce valid solids, with the
    declared features (holes, dimensions) actually present in the real
    geometry — not just "some positive volume"."""
    bracket_with_hole = AngleBracket(3 * IN, 3 * IN, 0.25 * IN, 3.5 * IN,
                                      holes_base=[(0, 2.25 * IN, 0.6875 * IN)])
    bracket_no_hole = AngleBracket(3 * IN, 3 * IN, 0.25 * IN, 3.5 * IN)
    lumber = Lumber("2x6", 14 * IN, treated=True, ease_radius=0.125 * IN)
    parts = [
        bracket_with_hole,
        HexBolt(0.375 * IN, 2.5 * IN),
        HexNut(0.5 * IN),
        ThreadedRod(0.5 * IN, 10.75 * IN, thread_zones=[(7 * IN, 10.75 * IN)]),
        Boulder(9 * IN, 12 * IN, 11 * IN,
                holes=[(0, 2.25 * IN, 0.625 * IN, 8 * IN)]),
        Epoxy(0.625 * IN, 0.5 * IN, 8 * IN),
        lumber,
    ]
    for c in parts:
        assert c.solid.val().isValid(), c
        assert c.volume() > 0, c

    # the punched hole must actually remove material — the exact mutation
    # this test is named to catch (holes silently skipped, e.g. iterating
    # an empty list) still leaves a positive, valid volume, so this compares
    # against an identical bracket with no hole instead of a bare volume>0.
    assert bracket_with_hole.volume() < bracket_no_hole.volume()

    # nominal 2x6 actual dimensions (1.5 x 5.5"), from the real solid —
    # catches a shrunk extrusion the same way ConcretePier's was missed.
    lumber_bb = lumber.bounding_box()
    assert lumber_bb.xlen == pytest.approx(14 * IN)
    assert lumber_bb.ylen == pytest.approx(1.5 * IN, abs=0.2 * IN)  # eased edge shaves a hair
    assert lumber_bb.zlen == pytest.approx(5.5 * IN, abs=0.2 * IN)


def test_pier_block_builds_with_top_pad_datum_at_origin():
    """PierBlock (task #19): a precast concrete foundation box whose top pad is
    the datum at Z=0, body extending into -Z (the ``Footing`` convention) — the
    post's base bears directly on the pad. The registry resolves it, the solid
    is valid, and the ``top``/``bottom`` datums bracket the modeled height."""
    from detailgen.core.registry import components

    assert components.get("pier_block") is PierBlock
    pb = PierBlock(10.5 * IN, 10.5 * IN, 8 * IN, name="pier test")
    assert pb.solid.val().isValid()
    assert pb.volume() > 0
    bb = pb.bounding_box()
    # top pad at Z=0, body into -Z: zmax=0, zmin=-height.
    assert bb.zmax == pytest.approx(0.0)
    assert bb.zmin == pytest.approx(-8 * IN)
    assert bb.xlen == pytest.approx(10.5 * IN)
    assert bb.ylen == pytest.approx(10.5 * IN)
    datums = pb._datums()
    assert datums["top"].origin[2] == pytest.approx(0.0)
    assert datums["bottom"].origin[2] == pytest.approx(-8 * IN)
    assert pb.bom_label() == "Precast pier block"


def test_bearing_check_catches_gap():
    """check_bearing must fail when parts that should touch don't."""
    from detailgen.validation import check_bearing
    detail = DetailAssembly("gap")
    a = detail.add(Lumber("2x4", 6 * IN, name="a"))
    b = detail.add(Lumber("2x4", 6 * IN, name="b"), at=(0, 2 * IN, 0))  # 0.5" gap in Y
    assert not check_bearing(a, b, "Y", min_area=100).passed


def test_rock_anchor_detail_is_clean():
    detail = compile_spec_file(DETAILS / "rock_anchor.spec.yaml")
    report = detail.validate()
    assert report.ok, str(report)
    # BOM aggregates to the expected line items
    labels = {r["item"]: r["qty"] for r in detail.bom_table()}
    assert labels["Steel angle"] == 2
    assert labels["Anchor rod (all-thread)"] == 2
    assert labels["Fender washer"] == 4
