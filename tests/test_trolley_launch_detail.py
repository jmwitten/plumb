"""Tests for the trolley/launch-edge detail (dacha zipline).

Authored as ``details/trolley_launch.spec.yaml`` and compiled via
``compile_spec_file``; param variants (``TrolleyLaunch(deck_width=36, ...)`` in
the old imperative family) are compiled as family members through ``overrides=``.
"""

import dataclasses
from pathlib import Path

from detailgen.core import IN
from detailgen.core.frame import Frame
from detailgen.spec.compiler import compile_spec_file
from detailgen.validation.checks import check_contact

SPEC = Path(__file__).resolve().parents[1] / "details" / "trolley_launch.spec.yaml"


def _trolley(**overrides):
    return compile_spec_file(SPEC, overrides=overrides or None)


def test_default_build_is_clean():
    detail = _trolley()
    report = detail.validate()
    assert report.ok, str(report)


# (test_grab_bar_height_above_deck_matches_params dropped as redundant: it
# recomputed the same formula extra_checks() already asserts internally at a
# tighter 0.5mm tolerance, using a 25.4mm/1in tolerance 50x looser — fully
# subsumed by, and weaker than, test_default_build_is_clean.)

def test_posts_span_the_configured_deck_width():
    """The two launch legs' INNER (deck-facing) faces should sit exactly
    deck_width apart — the TF-B refit models the posts as the real legs, whose
    inner faces bound the deck at local X=0 and X=deck_width (the wood extends
    OUTWARD from there). A geometry check catching a placement-arithmetic
    regression."""
    detail = _trolley(deck_width=34.0)
    detail.build()
    post1_bb = detail["launch post"].world_solid().val().BoundingBox()
    post2_bb = detail["far post"].world_solid().val().BoundingBox()
    span = post2_bb.xmin - post1_bb.xmax   # inner face to inner face
    assert abs(span - 34.0 * IN) < 0.1 * IN


def test_variant_size_builds_clean():
    detail = _trolley(deck_width=36.0, bar_height_ground=80.0, leg_height=70.0)
    report = detail.validate()
    assert report.ok, str(report)


def test_override_resizes_stub_of_full_run():
    # task-4B-2 stub fix: the launch posts' / deck rim's ``stub_of`` full_dims are
    # DERIVED (leg_full_len = leg_height, rim_full_len = deck_width - 2*post), so a
    # resize override moves them — a leg_height=70 member reports the RESIZED 70.0"
    # run, never the pinned default 63.5". (Was proven cross-path in the retired
    # test_spec_param_family.py; kept here as a spec-only regression guard.)
    detail = _trolley(deck_width=36.0, bar_height_ground=80.0, leg_height=70.0)
    stubs = [r["stub_of"] for r in detail.bom_table() if r["stub_of"] is not None]
    assert any('70.0"' in s["full_dims"] for s in stubs), stubs
    assert not any('63.5"' in s["full_dims"] for s in stubs), stubs


def test_wheel_off_cable_fails_contact_check():
    """Regression for a reviewer-found critical gap: ``expected_overlaps``
    only PERMITS an overlap between the trolley wheel and the cable, it
    can't REQUIRE one — a pair with zero actual overlap still passes the
    interference sweep unconditionally. The ``contact`` check the detail's
    validation declares (``contacts: [{a: trolley_wheel, b: cable}]``) is the
    actual proof the wheel rides the cable.

    The wheel is mated to the cable, so no param/override can lift it off; to
    prove the contact check REQUIRES touch, displace the BUILT ``trolley wheel``
    part 6in off the cable and run the same ``check_contact`` the validation
    runs, directly on the tampered part. As-built it passes; displaced it fails
    — exercising a check on a tampered part, the same in-suite pattern
    ``test_platform_detail.py::test_missing_rail_fastener_screw_fails_hardware_presence``
    uses.
    """
    detail = _trolley()
    detail.build()
    cable = detail["zipline cable"]
    wheel = detail["trolley wheel"]
    touching = check_contact(wheel, cable)
    assert touching.passed, "as-built wheel must ride the cable"
    # 6in off the cable (the imperative ``_wheel_offset`` displacement).
    displaced = dataclasses.replace(
        wheel, world_frame=Frame.translation((6 * IN, 0.0, 0.0)).compose(wheel.world_frame))
    finding = check_contact(displaced, cable)
    assert not finding.passed, "wheel displaced 6in off the cable should NOT bear"
    assert finding.check == "contact"
    assert "trolley wheel" in finding.subject and "cable" in finding.subject


def test_bom_rows_and_existing_vs_fabricated_source():
    detail = _trolley()
    detail.build()
    table = detail.bom_table()
    total_qty = sum(r["qty"] for r in table)
    assert total_qty == 11  # 2 posts + rim + strap + handle + 2 screws + 4 existing-hardware parts
    assert len(table) == 9  # distinct BOM groups

    by_item = {r["item"]: r for r in table}
    for existing_item in ("Zipline cable (existing)", "Trolley wheel (existing)",
                          "Hanger (existing)", "Grab bar (existing)"):
        assert existing_item in by_item, list(by_item)
        assert "existing" in by_item[existing_item]["source"]

    for fabricated_item in ("Strap gate (safety strap + carabiner)",
                            "Grab handle (galvanized)"):
        assert fabricated_item in by_item
        assert by_item[fabricated_item]["source"] == "generated"
