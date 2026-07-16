"""Tests for the zipline PLATFORM detail and its owned components.

The detail is authored as ``details/platform.spec.yaml`` and compiled through
``detailgen.spec.compiler.compile_spec_file`` — the single source now that the
imperative ``details/platform.py`` mirror is retired. Param variants
(``Platform(rail_height=42)`` in the old imperative family) are compiled as
family members via ``overrides=`` (4B-1); the resolved ``params:`` + ``derived:``
dimensions read back through ``detail.params.<field>`` (a read-only ParamsProxy),
which is where the old detail's private ``Params`` fields and derived helpers
(``_n_joists()`` -> ``n_joists``, ``_beam_outer_y`` -> ``outer_y``,
``_rung_length()`` -> ``rung_len``, ``_joist_last_x()`` -> ``joist_last``) now
live. Counts and geometry that the imperative helpers computed on the fly are
read off the compiled namespace or the built assembly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from detailgen.core import IN
from detailgen.spec.compiler import compile_spec_file
from detailgen.components.railing import WireMesh, DeckBoard
from detailgen.components import StructuralScrew
from detailgen.assemblies import Connection, DetailAssembly

SPEC = Path(__file__).resolve().parents[1] / "details" / "platform.spec.yaml"


def _build_accepted_platform_context(build, check):
    detail = build()
    report = detail.validate()
    check(report)
    return detail, report


def test_accepted_platform_context_builds_and_validates_once():
    calls = {"build": 0, "validate": 0, "check": 0}

    class _Detail:
        def validate(self):
            calls["validate"] += 1
            return object()

    def build():
        calls["build"] += 1
        return _Detail()

    def check(_report):
        calls["check"] += 1

    detail, report = _build_accepted_platform_context(build, check)

    assert isinstance(detail, _Detail)
    assert report is not None
    assert calls == {"build": 1, "validate": 1, "check": 1}


def _platform(**overrides):
    """The default platform, or a param-family member when overrides are given
    (the compiled twin of the imperative ``Platform(**overrides)``)."""
    return compile_spec_file(SPEC, overrides=overrides or None)


def _assert_no_fail_only_honest_unknowns(report):
    """The platform has NO FAIL and NO regression. FAB-3 (retire R29) made the
    three foundation-capacity UNKNOWNs blocking by construction (rung 4 —
    uplift/lateral/soil is out of scope, never a number). Task INSTALL v1's
    two toe-screw access UNKNOWNs were resolved ON MERIT by task CPGCORE
    (the authored toe-before-bolts sequence — declared-order clears, the
    wedge-fact why on paper), so the unresolved set is exactly the three
    capacity UNKNOWNs. ``report.ok`` stays False by design. These tests
    assert nothing regressed off that baseline: zero FAILs, and nothing
    unresolved beyond those three."""
    from collections import Counter
    assert report.failures == [], str(report)
    assert Counter(f.check for f in report.unresolved) == Counter(
        {"foundation_capacity": 3}), str(report)


@pytest.fixture(scope="module")
def accepted_platform(tmp_path_factory):
    cache_dir = tmp_path_factory.mktemp("accepted_platform_cache")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("DETAILGEN_CACHE_DIR", str(cache_dir))
        monkeypatch.delenv("DETAILGEN_NO_CACHE", raising=False)
        yield _build_accepted_platform_context(
            _platform, _assert_no_fail_only_honest_unknowns
        )


def _joist_stations(detail):
    """The interior joist centerline X positions (mm), read off the BUILT
    geometry — the spec-path equivalent of the imperative
    ``Platform._joist_stations()``. Read from the placed ``joist i`` parts
    (not reconstructed from ``joist_first`` + ``joist_oc``) so the spacing /
    clearance assertions stay a real geometry check rather than a tautology."""
    n = int(detail.params.n_joists)
    centers = []
    for i in range(n):
        bb = detail[f"joist {i}"].world_solid().val().BoundingBox()
        centers.append((bb.xmin + bb.xmax) / 2)
    return sorted(centers)


# -- owned components build ----------------------------------------------------

def test_wire_mesh_and_deck_board_build():
    for comp in (WireMesh(36 * IN, 32 * IN), DeckBoard(48 * IN)):
        assert comp.solid.val().isValid(), comp
        assert comp.volume() > 0, comp


def test_deck_board_dressed_dimensions():
    b = DeckBoard(48 * IN)
    bb = b.bounding_box()
    assert bb.xlen == pytest.approx(48 * IN)
    assert bb.ylen == pytest.approx(5.5 * IN)      # 5/4x6 dresses to 5.5" wide
    assert bb.zlen == pytest.approx(1.0 * IN)      # ...and a full 1" thick


def test_wire_mesh_flags_oversized_opening():
    # 2" openings satisfy the 4" sphere rule; 5" openings must be flagged.
    assert WireMesh(36 * IN, 32 * IN, opening=2 * IN).check() == []
    assert WireMesh(36 * IN, 32 * IN, opening=5 * IN).check()


# -- default detail validates CLEAN --------------------------------------------

def test_platform_default_validates_clean(accepted_platform):
    _detail, report = accepted_platform
    _assert_no_fail_only_honest_unknowns(report)


# -- geometry relationship: joist layout driven by joist_oc + the trunk --------

def test_joists_sit_at_exactly_joist_oc(accepted_platform):
    detail, _report = accepted_platform
    P = detail.params
    stations = _joist_stations(detail)
    gaps = [(stations[i + 1] - stations[i]) / IN for i in range(len(stations) - 1)]
    # the layout is DRIVEN by joist_oc: every gap equals it (not an even-fit fudge)
    assert all(abs(g - P.joist_oc) < 1e-6 for g in gaps)


def test_first_joist_starts_past_the_trunk(accepted_platform):
    # the ~20" trunk (radius trunk_dia/2, centered at X=0) is the real
    # obstruction: the first joist centerline clears its launch face + bark.
    detail, _report = accepted_platform
    P = detail.params
    first_in = _joist_stations(detail)[0] / IN
    assert first_in >= P.trunk_dia / 2 + P.bark_clear
    # ...and the last joist stays clear of the leg-to-beam bolts.
    assert _joist_stations(detail)[-1] / IN <= P.joist_last + 1e-6


def test_joist_count_is_derived_not_fixed(accepted_platform):
    # count is NOT a fixed param: tighter O.C. fits more joists in the same
    # clear run; a fatter trunk (starting them further out) fits fewer.
    base = int(accepted_platform[0].params.n_joists)
    assert int(_platform(joist_oc=8.0).params.n_joists) > base
    assert int(_platform(trunk_dia=34.0).params.n_joists) < base
    # spacing always equals the requested O.C., whatever the count
    st = _joist_stations(_platform(joist_oc=8.0))
    assert abs((st[1] - st[0]) / IN - 8.0) < 1e-6


def test_deck_board_count_tracks_deck_width():
    narrow = _platform(deck_width=22.0)
    wide = _platform(deck_width=44.0)
    deck_w = narrow.params.deck_w * IN          # dressed 5/4x6 board width (mm)
    assert int(narrow.params.n_deck) == round(22.0 * IN / deck_w)
    assert int(wide.params.n_deck) > int(narrow.params.n_deck)


# -- one variant size builds ---------------------------------------------------

def test_variant_size_builds_and_scales():
    tall = _platform(rail_height=42.0)
    tall.build()
    # the top rail follows the taller guard: rail top = deck + rail_height
    rail_top = tall["rail +Y"].world_solid().val().BoundingBox().zmax
    assert rail_top == pytest.approx((29.0 + 42.0) * IN, abs=1e-3)
    # a longer deck run makes a longer beam (BEAMFIX: the member's total
    # length is beam_len + tree_overhang, not beam_len alone — the beam also
    # continues tree_overhang past the tree face at the other end)
    longer = _platform(beam_len=60.0)
    assert longer["beam +Y"].world_solid().val().BoundingBox().xlen == \
        pytest.approx((60.0 + longer.params.tree_overhang) * IN)


# -- full-width ladder, hung on the legs (architect items 1-2) -----------------

def test_full_width_ladder_hung_on_legs(accepted_platform):
    # architect item 1: rungs span the FULL clear opening between the launch
    # legs' inner faces (the same span the decking uses), not the prior
    # narrow ~7.5" two-post ladder tucked into the -Y half of the gate span.
    detail, _report = accepted_platform
    P = detail.params
    outer_y = P.outer_y * IN                    # imperative _beam_outer_y
    rung_length = P.rung_len * IN               # imperative _rung_length()
    n_steps = int(P.n_steps)
    for s in range(n_steps):
        bb = detail[f"rung {s}"].world_solid().val().BoundingBox()
        assert bb.ylen == pytest.approx(rung_length, abs=1e-3)
        assert bb.ymin == pytest.approx(-outer_y, abs=1e-3)
        assert bb.ymax == pytest.approx(outer_y, abs=1e-3)
    # rungs rise to (but stop below) the deck; count follows n_steps
    tops = [detail[f"rung {s}"].world_solid().val().BoundingBox().zmax
            for s in range(n_steps)]
    assert len(tops) == n_steps
    assert max(tops) < P.deck_height * IN
    # architect item 2: no separate ladder posts — the launch legs
    # themselves are the ladder's rails (a rung is hung directly between
    # them in a face-mount hanger; see test_joist_hangers_declare_fasteners).
    for old_part in ("step post far", "step post near", "step 0", "step 1"):
        with pytest.raises(KeyError):
            detail[old_part]


def test_context_geometry_present_and_not_purchased(accepted_platform):
    # trunk + boulder orient the model and are excluded from the buy list.
    detail, _report = accepted_platform
    trunk_bb = detail["trunk"].world_solid().val().BoundingBox()
    # trunk stands at the tree origin (X=0), from the ground up
    assert abs(trunk_bb.xmin + trunk_bb.xmax) < 1e-6
    assert abs(trunk_bb.zmin) < 1e-6
    # boulder context pad top sits at the raised rock-post base (leg_gap), the
    # tangent bond that grounds the launch posts standalone (TREEFREE: the posts
    # are held leg_gap clear of their foundations); body extends below it.
    boulder_bb = detail["boulder"].world_solid().val().BoundingBox()
    assert boulder_bb.zmax == pytest.approx(detail.params.leg_gap * IN)
    # both are flagged existing (not purchased) in the BOM
    existing = [r for r in detail.bom_table() if "(existing)" in r["item"]]
    labels = {r["item"] for r in existing}
    assert any("trunk" in l.lower() for l in labels), labels
    assert any("boulder" in l.lower() for l in labels), labels


# -- BOM row count / quantities ------------------------------------------------

def test_bom_quantities(accepted_platform):
    detail, _report = accepted_platform
    P = detail.params
    n_j = int(P.n_joists)
    n_steps = int(P.n_steps)
    by_item = {}
    for r in detail.bom_table():
        by_item[r["item"]] = by_item.get(r["item"], 0) + r["qty"]
    # a hanger at each interior-joist end and each ladder-rung end; the
    # end/rim joist is toe-screwed instead (architect item 3 — no hanger
    # fits the ~3.5" gap between the leg's own two bolts).
    assert by_item["Joist Hanger"] == 2 * (n_j + n_steps)
    assert by_item["PT 5/4x6 decking"] == 6
    assert by_item["Welded-wire mesh panel"] == 2
    # STRUCT task #19: 4 BoltedClamp leg joints now — 2 launch legs + 2 tree-end
    # legs — at 2 bolts each = 8 (was 4 with the launch legs alone).
    assert by_item["Hex Bolt"] == 8               # 2 per leg joint x 4 leg joints
    assert by_item["Hex nut"] == 8
    # nut-side + head-side washer per bolt (BoltedClamp): 2 x 8 bolts.
    assert by_item["Flat washer"] == 16
    # every hanger's + the end joist's declared fasteners (architect item 5)
    assert by_item["Structural Screw"] > 0
    # STRUCT task #19: 3 precast pier blocks (under the -Y launch leg + both
    # tree-end legs; the +Y launch leg has the rock anchor instead).
    assert by_item["Precast pier block"] == 3
    # PT 2x6: 2 beams + n_j interior joists + 1 end/rim joist + 2 launch legs
    # + 2 tree-end legs (STRUCT task #19).
    assert by_item["PT 2x6 lumber"] == 2 + n_j + 1 + 2 + 2
    # PT 2x4: 2 tree-end rail posts + 2 top rails + n_steps ladder rungs (no more
    # separate step posts/treads, and no diagonal braces — architect item 6; the
    # tree-end LEGS are 2x6, counted above, not here).
    assert by_item["PT 2x4 lumber"] == 2 + 2 + n_steps


# -- architect review, round 2: items 3-6 --------------------------------------

def test_end_joist_clears_leg_bolts(accepted_platform):
    # architect item 3: the end/rim joist sits in the only clear gap left
    # near the launch end — between the leg's own two thru-bolts — since a
    # standard hanger's flanges don't fit flush at the true beam end.
    detail, report = accepted_platform
    P = detail.params
    _assert_no_fail_only_honest_unknowns(report)
    bb = detail["end joist"].world_solid().val().BoundingBox()
    center = (bb.xmin + bb.xmax) / 2
    assert center == pytest.approx(P.leg_station * IN, abs=1e-3)
    inner_bolt = (P.leg_station - P.bolt_dx) * IN
    outer_bolt = (P.leg_station + P.bolt_dx) * IN
    assert bb.xmin > inner_bolt
    assert bb.xmax < outer_bolt


def test_16in_oc_builds_clean_but_default_stays_12(accepted_platform):
    # architect item 4: 16" O.C. is analyzed (and validates clean) but is
    # NOT adopted as the default — see the platform report's sign-off flag.
    detail = _platform(joist_oc=16.0)
    report = detail.validate()
    _assert_no_fail_only_honest_unknowns(report)
    assert accepted_platform[0].params.joist_oc == 12.0


def test_no_vestigial_diagonal_braces(accepted_platform):
    # architect item 6: the undimensioned, unconnected diagonal braces are
    # removed outright, not rebuilt as sized/fastened knee braces.
    detail, _report = accepted_platform
    detail.build()
    for name in ("brace +Y", "brace -Y"):
        with pytest.raises(KeyError):
            detail[name]


def test_joist_and_rung_hangers_declare_fasteners(accepted_platform):
    # architect item 5: every hanger (joists AND ladder rungs) carries
    # explicit header-side + hung-side screws via a Connection, not just a
    # bare geometric envelope — and the hardware-presence checks prove it.
    detail, report = accepted_platform
    _assert_no_fail_only_honest_unknowns(report)
    hw_findings = [f for f in report.findings if f.check == "connection_hardware"]
    assert hw_findings and all(f.passed for f in hw_findings)
    assert len(detail.derivation_log) > 0
    # spot-check one interior-joist hanger and one ladder-rung hanger
    detail["joist 0+Y header screw 0"]
    detail["rung 0 hanger +Y header screw 0"]


def test_leg_bolts_reauthored_as_bolted_clamp(accepted_platform):
    # W2-6's suggestion: the leg-to-beam bolts now go through the SAME
    # BoltedClamp type the rock anchor uses, with a head washer added so the
    # joint fits the type's 4-piece hardware stack (bolt, head washer, nut
    # washer, nut) — proving the type generalizes past the rock anchor.
    detail, _report = accepted_platform
    detail.build()
    for side in ("+Y", "-Y"):
        for i in range(2):
            detail[f"bolt washer head {side}{i}"]   # raises if missing


# -- rail mirroring (user-spotted render bug: both rails overhung outboard) ----

def test_top_rails_are_mirrored_and_cover_their_posts(accepted_platform):
    # Both top rails must overhang 2" INBOARD, not the same world direction.
    # This is a symmetry property of the whole assembly, not just the rail
    # pair: EVERY +Y/-Y named part's world Y-extent must be the exact mirror
    # of its counterpart (negate and swap min/max) — the class of bug here
    # is a raw placement on one side that forgot to mirror.
    detail, _report = accepted_platform
    detail.build()
    names = {p.name for p in detail.assembly.parts}
    checked_pairs = 0
    for name in names:
        if "+Y" not in name:
            continue
        other = name.replace("+Y", "-Y")
        if other not in names:
            continue
        bb_p = detail[name].world_solid().val().BoundingBox()
        bb_m = detail[other].world_solid().val().BoundingBox()
        assert bb_p.ymax == pytest.approx(-bb_m.ymin, abs=1e-6), (name, other)
        assert bb_p.ymin == pytest.approx(-bb_m.ymax, abs=1e-6), (name, other)
        checked_pairs += 1
    assert checked_pairs > 10   # sanity: the audit actually covered the assembly

    # the specific bug: rail -Y must overhang inboard (toward Y=0) by 2",
    # exactly mirroring rail +Y, and both must fully cover their posts.
    rail_p = detail["rail +Y"].world_solid().val().BoundingBox()
    rail_m = detail["rail -Y"].world_solid().val().BoundingBox()
    post_p = detail["post +Y"].world_solid().val().BoundingBox()
    post_m = detail["post -Y"].world_solid().val().BoundingBox()
    assert rail_p.ymin == pytest.approx(post_p.ymin - 2.0 * IN, abs=1e-6)
    assert rail_p.ymax == pytest.approx(post_p.ymax, abs=1e-6)
    assert rail_m.ymax == pytest.approx(post_m.ymax + 2.0 * IN, abs=1e-6)
    assert rail_m.ymin == pytest.approx(post_m.ymin, abs=1e-6)
    assert rail_m.ymin == pytest.approx(-rail_p.ymax, abs=1e-6)
    assert rail_m.ymax == pytest.approx(-rail_p.ymin, abs=1e-6)


# -- rail-to-post/leg fastening (task RAILFASTEN: rails were previously
# gravity-seated only, with a proven bearing but no declared fastener
# anywhere in the model) -------------------------------------------------

def test_rail_fastening_declares_all_four_joints(accepted_platform):
    # each of the 2 rails crosses a tree-end post AND a launch leg (no
    # mid-span support in this revision) — 4 joints total, each its own
    # RailCapScrewed Connection with N_RAIL_SCREWS vertical screws, all
    # present and passing hardware-presence.
    detail, report = accepted_platform
    n_rail_screws = int(detail.params.n_rail_screws)
    _assert_no_fail_only_honest_unknowns(report)
    rail_hw = [f for f in report.findings
               if f.check == "connection_hardware"
               and "rail cap screwed" in f.subject]
    assert len(rail_hw) == 4 * n_rail_screws
    assert all(f.passed for f in rail_hw)
    joints = {f.subject.split(":", 1)[0] for f in rail_hw}
    assert joints == {
        "rail +Y <-> post +Y (rail cap screwed)",
        "rail +Y <-> leg +Y (rail cap screwed)",
        "rail -Y <-> post -Y (rail cap screwed)",
        "rail -Y <-> leg -Y (rail cap screwed)",
    }
    # spot-check the screws are retrievable by name — proves the geometry is
    # really there, not just the Connection bookkeeping.
    for support in ("post +Y", "leg +Y", "post -Y", "leg -Y"):
        for i in range(n_rail_screws):
            detail[f"{support} rail fastener screw {i}"]


def test_missing_rail_fastener_screw_fails_hardware_presence(accepted_platform):
    # a rail's fastening must be a REAL, present part, not just a Connection
    # declaration: hardware that isn't actually placed in this assembly (the
    # displaced/missing-screw case) must fail hardware-presence, the same
    # non-negotiable proof every other Connection-declared fastener in this
    # file gets (mirrors test_connection.py::test_missing_declared_hardware_
    # fails, scoped to RailCapScrewed).
    detail, _report = accepted_platform
    asm = detail.build()
    real_conn = next(c for c in detail.connections()
                      if c.label == "rail +Y <-> leg +Y (rail cap screwed)")
    other = DetailAssembly("other assembly")
    displaced_screw = other.add(
        StructuralScrew(0.157 * IN, 3.5 * IN, name="displaced screw"))
    tampered = Connection(
        kind=real_conn.kind, parts=real_conn.parts,
        hardware=[displaced_screw, real_conn.hardware[1]],
        label=real_conn.label)
    checks = tampered.generate_checks(asm)
    hw_fails = [f for f in checks.findings
                if f.check == "connection_hardware" and not f.passed]
    assert len(hw_fails) == 1
    assert "displaced screw" in hw_fails[0].subject
    assert "not placed in this assembly" in hw_fails[0].detail
