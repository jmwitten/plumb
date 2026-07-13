"""SM1 SITECORE: the site model — one compiled Detail composed from spec
fragments, with namespaced single-node identity.

The centerpiece (req 3): a member two subsystems share is ONE node, so a
cross-subsystem disagreement the per-detail structure hid is either made
inexpressible (identity ``is``) or surfaced as an honest FAIL. Here the rock
anchor's leg stub binds to the platform's real launch leg, and the anchor —
independently authored — does NOT register against that real leg: the site
model catches the misregistration the site-overview placement table could only
CAVEAT. That dirty verdict is the mechanism working; these tests pin the exact
finding set and assert ``require_clean`` raises, so master stays green while the
model honestly says FAIL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from collections import Counter

import baseline_lib as bl
from detailgen.assemblies.assembly import SpecReferenceError
from detailgen.core.buildinfo import build_manifest
from detailgen.spec.compiler import SpecCompileError, compile_spec
from detailgen.spec.loader import load_spec_file
from detailgen.spec.schema import SpecSchemaError
from detailgen.spec.semantics import SemanticError
from detailgen.spec import site as site_module
from detailgen.spec.site import (
    SiteDetail,
    compile_site_file,
    load_site_text,
)

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"
SITE = DETAILS / "site.spec.yaml"


def _site_from_text(body: str) -> SiteDetail:
    """A SiteDetail from inline text, resolving fragments against the real
    ``details/`` directory (so a test can vary one field of the document)."""
    return SiteDetail(load_site_text(body), base_dir=DETAILS)


_TWO = """
name: t
kind: site
units: in
subsystems:
  - {id: platform, fragment: platform.spec.yaml, place: identity}
  - id: rock_anchor
    fragment: rock_anchor.spec.yaml
    place: {raw: {at: ["= platform.leg_station", "= platform.outer_y", 0]}}
    bind: {leg: platform/leg_pY}
dedup:
  - {drop: platform/boulder, keep: rock_anchor/boulder}
validation: {ground: rock_anchor/boulder}
"""


def test_site_owned_process_capability_fails_before_fragment_compilation(
        monkeypatch):
    body = _TWO + """
connections:
  - type: cleat_screwed
    label: unsupported site cure
    parts: [platform/leg_pY, platform/beam_pY]
    process:
      cure:
        instructions: [Wait for the selected adhesive label.]
        completion: selected_label_full_cure
        why: This is an adversarial unsupported-capability probe.
"""

    def _fragment_compile_must_not_run(_doc):
        pytest.fail("site capability validation ran after fragment compilation")

    monkeypatch.setattr(site_module, "compile_spec", _fragment_compile_must_not_run)
    with pytest.raises(
            SemanticError,
            match="unsupported site cure.*cleat_screwed.*does not support.*cure"):
        _site_from_text(body)


# -- one compiled model ------------------------------------------------------ #
def test_site_compiles_to_one_assembly():
    site = compile_site_file(SITE)
    asm = site.assembly
    # The composed site is 180 parts in ONE DetailAssembly (baseline-pinned):
    # the platform's own members + rock_anchor/tree/trolley (less bound stubs and
    # deduped context bodies) + FAB-3's 3 pier post bases (one per pier foundation).
    assert len(asm.parts) == bl.load_baseline("detail_counts")["site"]["parts"]
    assert site.name == "zipline site"


def test_namespacing_rule_every_part_prefixed():
    site = compile_site_file(SITE)
    for p in site.assembly.parts:
        assert "/" in p.name, f"{p.name!r} is not namespaced <subsystem>/<name>"
        assert p.name.split("/", 1)[0] in (
            "platform", "rock_anchor", "tree", "trolley")


# -- single node: a shared member is ONE Placed object ----------------------- #
def test_bound_stub_is_the_real_member_identity():
    site = compile_site_file(SITE)
    site.build()
    # Every bound stub resolves — by IDENTITY — to the real member: the anchor's
    # leg -> the platform leg; the tree's beam stubs -> the platform's continuous
    # beams; the trolley's post/rim context stubs -> the platform legs + end joist.
    assert site._by_id["rock_anchor/leg"] is site._by_id["platform/leg_pY"]
    assert site._by_id["tree/beam_pY"] is site._by_id["platform/beam_pY"]
    assert site._by_id["tree/beam_mY"] is site._by_id["platform/beam_mY"]
    assert site._by_id["trolley/launch_post"] is site._by_id["platform/leg_mY"]
    assert site._by_id["trolley/far_post"] is site._by_id["platform/leg_pY"]
    assert site._by_id["trolley/deck_rim"] is site._by_id["platform/end_joist"]


def test_single_node_beam_is_one_object_cross_detail():
    """The BEAMFIX cross-detail invariant, now an in-model property: the tree's
    beam and the platform's beam are literally ONE node, so the X-coverage the old
    pair-load cross-detail test asserted (the stub within the beam envelope) is not
    a comparison of two models but an identity — there is no second beam to
    diverge in X."""
    site = compile_site_file(SITE)
    site.build()
    for side in ("pY", "mY"):
        assert site._by_id[f"tree/beam_{side}"] is site._by_id[f"platform/beam_{side}"]


def test_deduped_context_body_is_the_real_member_identity():
    site = compile_site_file(SITE)
    site.build()
    assert site._by_id["platform/boulder"] is site._by_id["rock_anchor/boulder"]
    assert site._by_id["platform/trunk"] is site._by_id["tree/trunk"]


def test_bound_stub_not_instantiated_and_bom_is_stub_free():
    site = compile_site_file(SITE)
    site.build()
    # No retired part appears as its own node in the assembly...
    assert not any(p.component.stub_of() is not None for p in site.assembly.parts)
    # ...so the BOM carries no stub row for a bound member (the double-count
    # guard the combined BOM needed is unnecessary here — gone by construction).
    assert all(row.get("stub_of") is None for row in site.bom_table())


# -- THE core outcome: honest FAIL findings for the shared-member registration #
def _failures(site):
    rep = site.validate()
    return rep, {(f.check, f.subject) for f in rep.failures}


def test_site_blocks_on_honest_unknowns():
    # FAB-3 (retire R29 / CAT-2): STRUCT #19 had earned a CLEAN site, but the
    # pier blocks the legs rest on were shown-not-designed — a bearing + a
    # `ground` label, no attachment, yet CLEAN. FAB-3 declares the three
    # foundation SYSTEMS: attachment + embedment are now REPRESENTED (no FAIL),
    # but uplift/lateral/soil CAPACITY is an honest BLOCKING UNKNOWN by
    # construction. Task INSTALL v1 added honest install UNKNOWNs; task
    # CPGCORE resolved the platform's two top toe screws on merit (the
    # authored toe-before-bolts sequence replays composed), leaving ONE
    # install UNKNOWN, a truth only visible COMPOSED — rock-anchor rod 1's
    # insertion corridor is obstructed by the platform's lowest ladder rung
    # + hanger hardware (hand-verified: rung 0 spans z 6.2-9.7in directly
    # over the rod top at 2.75in). The rod goes in before the rung in
    # reality; that is CROSS-FRAGMENT order (CPG v2) and insertion travel
    # (P1) — the verdict names both missing mechanisms.
    site = compile_site_file(SITE)
    rep = site.validate()
    assert not rep.ok
    assert [f.check for f in rep.failures] == []  # no FAIL — only honest UNKNOWNs
    assert Counter(f.check for f in rep.blocking) == Counter(
        {"foundation_capacity": 3, "install_access": 1})
    rod = [f for f in rep.blocking if "rod 1" in f.subject]
    assert len(rod) == 1 and "rung 0" in rod[0].detail
    assert "cross-fragment" in rod[0].detail and "(P1)" in rod[0].detail
    with pytest.raises(AssertionError):
        site.require_clean()  # the gate is CLOSED


# -- THE pinned divergence set: three independently-authored subsystems, each
#    bound to the platform's real members, each surfacing a registration the
#    per-detail structure hid. SM1's leg set, extended by SM3b's tree + trolley.
#
# TREEFREE (task TF-A) RESOLVED the entire SM1 rock-leg family (11 findings) BY
# DESIGN — the anchor was re-seated onto the platform's REAL leg, not the check
# loosened — so `_LEG_DIVERGENCE` is now EMPTY. Each removed finding and the one
# design change that killed it:
#   * `interference` leg <-> angle 0 / bolt 0-1 / bolt washer nut 0-1 / bolt nut
#     0-1 (7) AND `bearing` angle 1 <-> leg (1): the anchor's site placement moved
#     +0.75" in Y (details/site.spec.yaml: outer_y -> outer_y + t2x/2) so its rod
#     line + clamp angles now CENTER on the real leg's centerline instead of
#     clamping 0.75" inboard of it — the angles bear and the nuts clear.
#   * `through_hole` bolt 0-1 through leg (2): the rock post (leg +Y) is now
#     drilled for the anchor's two cross-bolts (platform.spec.yaml anchor_bolt_up
#     /anchor_bolt_dx holes), so each bolt passes a clear annulus.
#   * `dimension` leg held 1/2" above rock (1): the leg's base now DERIVES to
#     leg_gap above the boulder (platform leg_gap standoff convention + leg_len =
#     leg_top - leg_gap) — end grain out of water, the anchor's design intent.
# (The SM1 leg family is fully RESOLVED — its divergence set is empty.)
#
# THE tree beam-Y + trunk/deck divergence — RESOLVED BY DESIGN by TREEFREE (task
# TF-A). Each removed finding and its design fix:
#   * `bearing` tree/washer <-> platform/beam (4): the lag connection is RETIRED
#     (free-standing platform). The washers + lags are gone from the tree fragment
#     (now trunk + two plain beam stubs), so there is no washer to miss-bear.
#   * `dimension` beam inner face tangent at trunk radius (1): the beams no longer
#     sit TANGENT to the trunk — they CLEAR it. The tangent-equality check is gone;
#     in its place the platform declares a Y-GROWTH-CLEARANCE invariant (beam inner
#     face clears the trunk by >= growth_gap), which PASSES against the real beam.
#   * `interference` platform/deck 1-4 <-> tree/trunk (4): the deck is now NOTCHED
#     around the trunk (DeckBoard trunk_cut) — a real modeled cutout fitted to the
#     trunk — so the tree growing PAST the deck no longer collides with the boards.
#
# TF-B RESOLVED the 5 launch-HARDWARE registration findings BY DESIGN (the trolley
# posts are exact stubs of the real legs). ARCH0 moved the pinned set out of Python
# literals and into the reviewable tests/baselines/site_divergence.json — each
# finding CARRIES its justification note there, and
# `test_site_divergence_finding_set_is_pinned` asserts the exact set against that
# baseline.
#
# STRUCT (task #19) RESOLVED the LAST findings BY DESIGN, so the pinned set is now
# EMPTY (site_divergence.json.findings == []). Each removed finding and its design
# change:
#   * two `bearing` leg <-> end-joist findings — REMOVED (e74f109): the launch
#     posts never bore on the rim; the legs bear on the beams and the end joist
#     toe-screws to them, so the claim was unintended (not a loosened check).
#   * one `dimension` grab-bar-height finding — RESOLVED (e74f109): the trolley
#     grab bar re-derives against the real end-joist top and now reads its honest
#     height with no drawn-vs-derived gap.
#   * one `floating` island — RESOLVED (e74f109, per A3): the pre-existing zipline
#     hardware grounds through the tree (trunk extended to the cable anchor, cable
#     bonded to it) as DEMONSTRATION geometry — no engineered anchor, single ground
#     terminal kept.
#   * one `support` finding (task SUPPORT acceptance proof) — RESOLVED (STRUCT):
#     two tree-end legs on pier blocks support the deck tree end, and the residual
#     tree apron (the living trunk bars any foundation under X<~11) is a DECLARED
#     cantilever, so the rung-3 support check PASSES. See platform.spec.yaml roles.


def test_site_divergence_finding_set_is_pinned():
    site = compile_site_file(SITE)
    rep, got = _failures(site)
    # The pinned set (+ each finding's justification) lives in
    # tests/baselines/site_divergence.json — asserted exactly, never hand-edited;
    # a change is a deliberate `scripts/regen_baselines.py` + reviewed git diff.
    expected = {(f["check"], f["subject"])
                for f in bl.load_baseline("site_divergence")["findings"]}
    assert got == expected, (got - expected, expected - got)


def test_every_failure_concerns_a_bound_or_deduped_member():
    """Every divergence in the site concerns a member two subsystems SHARE — a
    bound stub (leg / beam / post / rim) or a deduped context body (trunk). No
    OTHER contradiction is representable: the rest of each subsystem's internal
    geometry is clean. STRUCT task #19 resolved the last divergences by design, so
    the failure set is now EMPTY and this holds vacuously — it remains as a guard
    that any FUTURE regression can only be a shared-member disagreement."""
    site = compile_site_file(SITE)
    _, got = _failures(site)
    shared = ("platform/leg +Y", "platform/leg -Y", "platform/beam +Y",
              "platform/beam -Y", "platform/end joist", "tree/trunk")
    for check, subject in got:
        # The floating island (SM4 item 1) is the ONE failure whose subject names
        # only trolley-internal parts: it is the CONSEQUENCE of a shared-member
        # divergence (the trolley posts/handle don't reach the real legs, so the
        # hanging hardware is grounded through nothing), so it is admitted here as
        # the connectivity restatement of the trolley registration divergence.
        # The `support` failure (task SUPPORT) is a DIFFERENT class: the deck's
        # rung-3 walking_surface obligation, unsupported at the tree end — not a
        # shared-member registration divergence but the acceptance proof (the
        # previous design the compiler rejects), pinned in the baseline as
        # resolved-by-STRUCT. Every OTHER failure names a shared member directly —
        # including the three dimension checks, which since SM4 item 2 carry the
        # real member they measure (leg / beam / end joist) in their subject.
        assert (check in ("floating", "support")
                or any(m in subject for m in shared)), (check, subject)


def test_no_divergences_remain_all_resolved_by_design():
    """Every cross-subsystem divergence the site once pinned is now RESOLVED by
    design, so the failure set is EMPTY: the SM1 rock-leg (0.750"/0.5") and the
    tree beam-Y (~3.4" / 15-vs-10) families by TREEFREE (anchor re-seated, lag
    retired); the trolley leg<->end-joist bearings, grab-bar height, and floating
    zipline island by TF-B/e74f109; and the SUPPORT tree-end proof by STRUCT's
    tree-end legs + declared tree-apron cantilever. The site_divergence baseline
    is correspondingly empty (asserted by test_site_divergence_finding_set_is_
    pinned)."""
    site = compile_site_file(SITE)
    rep = site.validate()
    assert rep.failures == [], [(f.check, f.subject) for f in rep.failures]


# -- qualified value references ---------------------------------------------- #
def test_qualified_placement_ref_resolves_in_owning_fragment_numbers():
    site = compile_site_file(SITE)
    # = platform.leg_station (45"), = platform.outer_y + platform.t2x/2 (16.5 +
    # 0.75 = 17.25", the REAL leg centerline the TREEFREE re-seat targets) -> mm.
    origin = site._transforms["rock_anchor"].origin
    assert origin[0] == pytest.approx(45.0 * 25.4)
    assert origin[1] == pytest.approx(17.25 * 25.4)
    assert origin[2] == pytest.approx(0.0)


def test_qualified_ref_unknown_subsystem_is_teaching_error():
    body = _TWO.replace('"= platform.leg_station"', '"= platfrm.leg_station"')
    with pytest.raises(SpecCompileError) as e:
        _site_from_text(body)
    assert "platfrm.leg_station" in str(e.value)


# -- teaching errors: bind / dedup / schema strictness ----------------------- #
def test_unbound_stub_is_a_teaching_error():
    body = _TWO.replace("    bind: {leg: platform/leg_pY}\n", "")
    with pytest.raises(SpecCompileError) as e:
        _site_from_text(body).build()
    msg = str(e.value)
    assert "rock_anchor/leg" in msg and "bind" in msg


def test_binding_a_non_stub_is_a_teaching_error():
    body = _TWO.replace("bind: {leg: platform/leg_pY}",
                        "bind: {boulder: platform/leg_pY, leg: platform/leg_pY}")
    with pytest.raises(SpecCompileError) as e:
        _site_from_text(body).build()
    assert "not a partial-member stub" in str(e.value)


def test_bind_to_missing_qualified_id_is_spec_reference_error():
    body = _TWO.replace("platform/leg_pY", "platform/leg_pZ")
    with pytest.raises(SpecReferenceError) as e:
        _site_from_text(body).build()
    msg = str(e.value)
    assert "platform/leg_pZ" in msg and "did you mean" in msg


def test_unknown_top_level_key_is_teaching_error():
    with pytest.raises(SpecSchemaError) as e:
        load_site_text("name: t\nkind: site\nnope: 1\n"
                       "subsystems:\n  - {id: p, fragment: platform.spec.yaml}\n")
    assert "unknown key 'nope'" in str(e.value)


def test_confidence_enum_is_enforced():
    with pytest.raises(SpecSchemaError):
        load_site_text("name: t\nkind: site\nsubsystems:\n"
                       "  - {id: p, fragment: platform.spec.yaml, confidence: MAYBE}\n")


def test_subsystem_place_rejects_a_datum_mate():
    with pytest.raises(SpecSchemaError):
        load_site_text("name: t\nkind: site\nsubsystems:\n"
                       "  - {id: p, fragment: platform.spec.yaml, "
                       "place: {datum: base, to: x}}\n")


def test_dedup_dropping_a_structural_member_is_a_teaching_error():
    """rev-sm1 attack A, verbatim: a `dedup: drop` of a real structural part
    (source=generated, not a context body) would silently delete a genuine
    finding — waiver machinery the design forbids. It must be a loud error;
    only an existing/context body may be deduped."""
    body = _TWO.replace(
        "  - {drop: platform/boulder, keep: rock_anchor/boulder}\n",
        "  - {drop: platform/boulder, keep: rock_anchor/boulder}\n"
        "  - {drop: rock_anchor/bolt_1, keep: rock_anchor/bolt_0, "
        "basis: NOT the same thing}\n")
    with pytest.raises(SpecCompileError) as e:
        _site_from_text(body).build()
    msg = str(e.value)
    assert "rock_anchor/bolt_1" in msg
    assert "structural" in msg or "source=generated" in msg


def test_dedup_of_the_context_boulder_still_passes():
    """The legit dedup (a context boulder another subsystem models for real) is
    unaffected by the restriction — the site still composes with the boulder as
    one node."""
    site = compile_site_file(SITE)
    site.build()
    assert len(site.assembly.parts) == bl.load_baseline("detail_counts")["site"]["parts"]
    assert site._by_id["platform/boulder"] is site._by_id["rock_anchor/boulder"]


def test_right_angle_z_rotation_compiles_and_remaps():
    """SM3b lands the rotated-subsystem generalization SM1 deferred: a RIGHT-ANGLE
    rotation about Z maps each fragment axis exactly onto a world axis, so a
    fragment declaring through-holes / absolute-coordinate dimension checks (like
    rock_anchor) now COMPILES under a 90 deg Z spin (the axis letters + dimension
    measures remap) rather than raising the SM1 deferral error."""
    body = _TWO.replace(
        'place: {raw: {at: ["= platform.leg_station", "= platform.outer_y", 0]}}',
        'place: {raw: {at: ["= platform.leg_station", "= platform.outer_y", 0], '
        'rotate: [["Z", 90]]}}')
    site = _site_from_text(body)          # no raise
    site.validate()                       # runs the remapped checks


def test_non_right_angle_or_off_z_rotation_is_a_loud_error():
    """The generalization is SCOPED to right-angle rotations about Z; a non-90
    angle or a tilt about X/Y does NOT map axes onto axes (a face would straddle
    two world axes), so every frame-dependent check would be silently wrong. Those
    stay a loud teaching error — general-rotation remapping is queued."""
    for rot in ('rotate: [["Z", 45]]', 'rotate: [["X", 90]]'):
        body = _TWO.replace(
            'place: {raw: {at: ["= platform.leg_station", "= platform.outer_y", 0]}}',
            'place: {raw: {at: ["= platform.leg_station", "= platform.outer_y", 0], '
            f'{rot}}}}}')
        with pytest.raises(SpecCompileError) as e:
            _site_from_text(body)
        assert "right-angle" in str(e.value).lower()


def test_trolley_bearing_axis_remap_is_load_bearing():
    """The trolley is placed with a REAL 90 deg Z rotation; its launch_post<->
    grab_handle bearing (fragment axis X) must remap to world Y in-site. The
    launch_post is bound to the platform's real leg -Y, so this exercises the
    remap on a live shared-member bearing: checked along the remapped world Y it
    reads flush and PASSES (the trolley hardware is an exact stub of the real leg,
    per TF-B). Were the axis left at the fragment 'X', the check would push along
    the wrong world axis. (The pure axis-letter remap is unit-guarded by
    test_right_angle_z_rotation_compiles_and_remaps.)

    STRUCT/TF-B note: the earlier leg<->end-joist bearing this test used to assert
    a FAIL against was REMOVED BY DESIGN (e74f109) — the launch posts never bore
    on the rim; the legs bear on the beams and the end joist toe-screws to them.
    So the remapped trolley bearing now registers CLEANLY rather than flagging a
    1.5" gap."""
    site = compile_site_file(SITE)
    rep = site.validate()
    by_subject = {f.subject: f for f in rep.findings}
    f = by_subject["platform/leg -Y <-> trolley/grab handle"]
    assert f.passed and "flush" in f.detail
    # the removed-by-design registration FAIL is genuinely gone, not merely hidden
    assert "platform/leg +Y <-> platform/end joist" not in by_subject


def test_reserved_spatial_name_teaches_at_site_level():
    body = _TWO + "spatial:\n  parallel: []\n"
    with pytest.raises(SpecSchemaError) as e:
        load_site_text(body)
    assert "reserved" in str(e.value)


# -- determinism -------------------------------------------------------------- #
def test_two_independent_builds_have_equal_fingerprints():
    a = build_manifest(compile_site_file(SITE).assembly)
    b = build_manifest(compile_site_file(SITE).assembly)
    assert a["assembly_hash"] == b["assembly_hash"]


# -- standalone fragment equivalence is UNTOUCHED ---------------------------- #
def test_fragments_still_compile_standalone_and_unprefixed():
    """A fragment IS a DetailSpecDoc: it still compiles standalone with its own
    (un-namespaced) identity, unaffected by any in-site re-hosting. The
    byte-identical golden equivalence is enforced by the existing
    test_platform_spec / test_platform_promote_equiv suites, which this task
    leaves untouched; this guards that the site's namespacing does not leak into
    a standalone compile in the same process."""
    # Build the site first (it renames its OWN fragment component instances)...
    compile_site_file(SITE).build()
    # ...a fresh standalone compile is unaffected: 124 parts, names unprefixed.
    plat = compile_spec(load_spec_file(DETAILS / "platform.spec.yaml"))
    plat.build()
    assert len(plat.assembly.parts) == bl.load_baseline("detail_counts")["platform"]["parts"]
    assert plat["beam +Y"].name == "beam +Y"
    # STRUCT task #19 resolved every FAIL. FAB-3 (retire R29) then declared the
    # three pier foundation systems: attachment + embedment REPRESENTED (no FAIL),
    # but uplift/lateral/soil CAPACITY is an honest BLOCKING UNKNOWN (rung 4), so
    # the platform now has three unresolved foundation-capacity findings and is no
    # longer clean — a foundation shown is never silently called "designed".
    plat_rep = plat.validate()
    assert plat_rep.failures == []
    # 3 capacity UNKNOWNs (FAB-3); the two INSTALL v1 toe-screw UNKNOWNs
    # were resolved on merit by the authored sequence (task CPGCORE).
    assert Counter(f.check for f in plat_rep.unresolved) == Counter(
        {"foundation_capacity": 3})

    ra = compile_spec(load_spec_file(DETAILS / "rock_anchor.spec.yaml"))
    assert ra.validate().ok  # rock anchor is clean in isolation (no walking surface)
