"""SM2 VIEWS — a detail is a VIEW of the one site model.

Covers: scope-selector semantics (subsystem / id-glob / name-glob) + the
zero-match loud error; the views: loader (strict, teaching errors, round-trip);
the findings-slice honesty rule (a finding spanning two views appears in BOTH;
wording asserted); the SITE-level render gate (dirty site blocks EVERY view;
a synthetic clean two-fragment site renders); the BOM slice (= site BOM minus
out-of-scope, no double count on a partition); the reverse "where else does this
appear?" query; view-local callouts (live value) + camera; coverage NOT
re-derived; and determinism.

The heavy dirty-site model (148 parts) is compiled + validated ONCE per module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.spec.site import compile_site_file
from detailgen.spec.views import (
    Camera,
    Selector,
    View,
    ViewCallout,
    ViewSpec,
    build_views,
    dump_views,
)
from detailgen.spec.schema import SpecSchemaError

REPO = Path(__file__).resolve().parents[1]
SITE_SPEC = REPO / "details" / "site.spec.yaml"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def site():
    s = compile_site_file(SITE_SPEC)
    s.validate()  # one whole-site sweep; views only ever slice this
    return s


def _write_clean_site(tmp_path: Path) -> Path:
    """A synthetic CLEAN two-fragment site: two short 2x4s far apart (no
    interference, no bearings/bonds), composed identity + a big translation, with
    one view. The whole point is a site whose validation is CLEAN so the
    render-gate CLEAN branch can be exercised without the zipline site's pinned
    findings."""
    (tmp_path / "toy_a.spec.yaml").write_text(
        "name: toy a\nunits: in\ncomponents:\n"
        "  - id: bar\n    type: lumber\n    name: bar_a\n"
        "    params: {nominal: \"2x4\", length: 12.0}\n")
    (tmp_path / "toy_b.spec.yaml").write_text(
        "name: toy b\nunits: in\ncomponents:\n"
        "  - id: bar\n    type: lumber\n    name: bar_b\n"
        "    params: {nominal: \"2x6\", length: 12.0}\n")
    site_doc = tmp_path / "toy_site.spec.yaml"
    site_doc.write_text(
        "name: toy clean site\nkind: site\nunits: in\n"
        "subsystems:\n"
        "  - id: a\n    fragment: toy_a.spec.yaml\n    place: identity\n"
        "    confidence: EXACT\n"
        "  - id: b\n    fragment: toy_b.spec.yaml\n"
        "    place: {raw: {at: [0, 300, 0]}}\n    confidence: EXACT\n"
        "views:\n"
        "  - name: a_only\n    include:\n      - subsystem: a\n    camera: iso\n"
        "  - name: b_only\n    include:\n      - subsystem: b\n    camera: top\n")
    return site_doc


# --------------------------------------------------------------------------- #
# Selector semantics + zero-match error
# --------------------------------------------------------------------------- #
def test_subsystem_selector_scopes_a_whole_subsystem(site):
    pf = site.view("platform").part_ids()
    assert pf and all(q.startswith("platform/") for q in pf)
    ra = site.view("rock_anchor").part_ids()
    assert ra and all(q.startswith("rock_anchor/") for q in ra)


def test_id_glob_selector_carves_below_a_subsystem(site):
    v = View(ViewSpec(name="angles",
                      include=(Selector("id", "rock_anchor/angle*"),)), site)
    ids = v.part_ids()
    assert ids and all(q.startswith("rock_anchor/angle") for q in ids)
    # strictly fewer than the whole subsystem
    assert len(ids) < len(site.view("rock_anchor").part_ids())


def test_name_glob_selector_matches_display_names(site):
    v = View(ViewSpec(name="anchor-angles",
                      include=(Selector("name", "rock_anchor/angle*"),)), site)
    parts = v.parts()
    assert parts and all(p.name.startswith("rock_anchor/angle") for p in parts)


def test_zero_match_selector_is_a_loud_error(site):
    v = View(ViewSpec(name="ghost",
                      include=(Selector("subsystem", "no_such_subsystem"),)), site)
    with pytest.raises(SpecSchemaError, match="matches ZERO parts"):
        v.parts()


def test_shared_member_is_one_node_in_two_views(site):
    """The retired rock_anchor/leg resolves — by identity — to platform/leg_pY,
    so the SAME Placed is in both the platform and the rock_anchor view."""
    leg = site._by_id["platform/leg_pY"]
    assert site._by_id["rock_anchor/leg"] is leg
    pf = {id(p) for p in site.view("platform").parts()}
    ra = {id(p) for p in site.view("rock_anchor").parts()}
    assert id(leg) in pf and id(leg) in ra


# --------------------------------------------------------------------------- #
# views: loader — strict, teaching errors, round-trip
# --------------------------------------------------------------------------- #
def test_views_round_trip_serialize(site):
    views = site.doc.views
    assert views  # the authored platform + rock_anchor views
    assert build_views(dump_views(views)) == views


def test_camera_string_and_mapping_forms():
    views = build_views([
        {"name": "v1", "include": [{"subsystem": "a"}], "camera": "top"},
        {"name": "v2", "include": [{"subsystem": "a"}],
         "camera": {"projection": "front", "zoom_to_scope": False}},
    ])
    assert views[0].camera == Camera("top", True)
    assert views[1].camera == Camera("front", False)
    # default camera when omitted
    v = build_views([{"name": "v", "include": [{"subsystem": "a"}]}])[0]
    assert v.camera == Camera("iso", True)


@pytest.mark.parametrize("raw, match", [
    ([{"name": "v", "include": [{"subsytem": "a"}]}], "did you mean 'subsystem'"),
    ([{"name": "v", "include": [{"subsystem": "a"}], "camera": "sideways"}],
     "unknown projection"),
    ([{"name": "v", "include": []}], "at least one scope selector"),
    ([{"name": "v"}], "include"),
    ([{"name": "a", "include": [{"subsystem": "x"}]},
      {"name": "a", "include": [{"subsystem": "y"}]}], "duplicate view name"),
    ([{"name": "v", "include": [{"subsystem": "a"}],
       "callouts": [{"param": "leg_gap"}]}], "qualified site value"),
])
def test_views_loader_teaches(raw, match):
    with pytest.raises(SpecSchemaError, match=match):
        build_views(raw)


def test_unknown_view_name_did_you_mean(site):
    with pytest.raises(KeyError, match="did you mean"):
        site.view("platfrom")


# --------------------------------------------------------------------------- #
# Findings slice — honest framing; a finding spanning two views appears in both
# --------------------------------------------------------------------------- #
def test_finding_spanning_two_views_appears_in_both(site):
    # A finding naming the SHARED +Y launch leg (bound across the platform and
    # rock_anchor subsystems) slices into BOTH views — the slice mechanism is
    # VERDICT-AGNOSTIC. STRUCT: the site is clean now, so these are shared PASSING
    # findings (the old shared-leg registration FAILURE was resolved by design);
    # the point under test is the cross-view slice, not the verdict.
    pf = {str(f) for f in site.view("platform").findings()}
    ra = {str(f) for f in site.view("rock_anchor").findings()}
    shared = pf & ra
    assert shared, "expected shared-leg findings in both views"
    assert any("leg +Y" in s for s in shared)


def test_subject_parser_handles_every_check_shape():
    """The findings-slice parser must recognise EVERY subject shape the checks
    in src/validation/checks.py (+ spatial/loadpath/connection) actually emit —
    not just ' <-> ' and 'label: name'. Audited shapes, one case each."""
    from detailgen.spec.views import _subject_part_ids

    n2i = {"A": "a", "B": "b", "C": "c"}
    cases = {
        "A <-> B": ["a", "b"],                     # interference / contact / bearing
        "A <-> B about YZ": ["a", "b"],            # symmetric_about (trailing clause)
        "A through B": ["a", "b"],                 # through_hole  <-- the rev-sm2 gap
        "A faces toward the trunk (+X)": ["a"],    # faces_toward/away (prose target)
        "A, B, C": ["a", "b", "c"],                # floating (comma-joined names)
        "some connection: B": ["b"],               # connection_hardware (label: name)
        "downward-load: A -> B": ["a", "b"],       # load_path (label: name -> name)
        'leg held 1/2" above rock: A': ["a"],      # dimension (SM4 item 2: prose: part)
        "grab bar height above deck: A <-> B": ["a", "b"],  # cross-part dimension
        'trunk diameter': [],                      # bare prose (no part) still -> []
    }
    for subject, expect in cases.items():
        assert _subject_part_ids(subject, n2i) == expect, subject


def test_through_hole_finding_lands_in_the_scoped_views(site):
    """The two rock-anchor through_hole findings name the shared leg (in BOTH the
    platform and rock_anchor views) and slice into each. TREEFREE drilled the rock
    post for the anchor's cross-bolts, so they now PASS — a passing finding still
    slices to the views that scope its member (the slice mechanism is verdict-
    agnostic)."""
    th = [f for f in site.report.findings if f.check == "through_hole"
          and "rock_anchor/bolt" in f.subject and "platform/leg +Y" in f.subject]
    assert len(th) == 2 and all("through" in f.subject for f in th)
    assert all(f.passed for f in th)   # resolved: the rock post is drilled
    pf = {str(f) for f in site.view("platform").findings()}
    ra = {str(f) for f in site.view("rock_anchor").findings()}
    for f in th:
        assert str(f) in pf and str(f) in ra


def test_every_scoped_failure_lands_in_a_view_slice(site):
    """Slice-completeness (rev-sm2 required assertion): every site FAILURE whose
    subject names an in-scope part appears in at least one view's findings slice.
    After TREEFREE flipped the rock-leg + tree families, the 9 remaining failures
    are TF-B's trolley set — 8 name the shared launch legs / end joist and slice in,
    and the 9th is the floating island whose subject lists trolley-internal parts
    the trolley view scopes; every one lands."""
    from detailgen.spec.views import _name_to_id, _subject_part_ids

    views = site.views()
    n2i = _name_to_id(site.assembly)
    in_scope = set()
    for v in views:
        in_scope |= {p.id for p in v.parts()}
    sliced = set()
    for v in views:
        sliced |= {str(f) for f in v.findings() if not f.passed}

    names_scoped, names_no_part, named_unscoped = [], [], []
    for f in site.report.failures:
        ids = _subject_part_ids(f.subject, n2i)
        if any(i in in_scope for i in ids):
            names_scoped.append(f)
        elif not ids:
            names_no_part.append(f)
        else:
            named_unscoped.append(f)  # names a part, but no CURRENT view scopes it

    # THE invariant: no scoped failure is silently dropped from the slice.
    for f in names_scoped:
        assert str(f) in sliced, f"{f} names a scoped part but is in no view slice"
    # exact accounting on the current site (guards the completeness, not just
    # 'some' finding, so the through-hole omission cannot silently return).
    # Merge reconciliation (controller): the count tracks the SHRINKING TREEFREE
    # finding set. SM4 pinned 29; TF-A's structural families flipped 20 (rock 11 +
    # tree/trunk 9) and TF-B's launch-hardware refit flipped 5, leaving 4: the two
    # leg<->end-joist bearings, the grab-bar-above-joist dimension, and the 4-part
    # floating island (hanging zipline hardware, resolves with the deferred trunk
    # extension). The INVARIANT is unchanged: EVERY remaining failure names an
    # in-scope part and lands in a view slice —
    #   * 4 SCOPED / 0 NO-PART / 0 NAMED-UNSCOPED — now read from the baseline
    #     (tests/baselines/slice_accounting.json; regen + review to change).
    _slice = bl.load_baseline("slice_accounting")
    assert len(names_scoped) == _slice["scoped"]
    assert names_no_part == []
    assert named_unscoped == []
    assert len(names_scoped) == len(site.report.failures) == _slice["total_failures"]


def test_findings_note_is_wording_rule_compliant(site):
    note = site.view("platform").findings_note()
    assert "WHOLE site" in note
    assert "safe" not in note.lower()


def test_view_never_re_derives_coverage(site):
    v = site.view("rock_anchor")
    # coverage is the SITE's own matrix, verbatim
    assert v.site_coverage() == site.coverage_matrix()


# --------------------------------------------------------------------------- #
# SITE-level render gate
# --------------------------------------------------------------------------- #
def test_real_site_views_are_gated_by_foundation_capacity(site, tmp_path):
    # FAB-3 (retire R29): the REAL site is blocked by the three foundation-capacity
    # UNKNOWNs, so the site-level gate is CLOSED — no view of the real site renders
    # (rendering a clean-looking view of a model with an open, blocking finding is
    # exactly the dishonesty the gate exists to prevent). The open-gate render path
    # itself is proven by test_synthetic_clean_site_view_renders below.
    assert not site.report.ok  # blocked by foundation capacity (UNKNOWN, by design)
    with pytest.raises(AssertionError):
        site.require_clean()
    out = tmp_path / "renders"
    with pytest.raises(AssertionError):
        site.view("platform").render(out)


def test_synthetic_clean_site_view_renders(tmp_path):
    doc = _write_clean_site(tmp_path)
    clean = compile_site_file(doc)
    assert clean.validate().ok
    out = tmp_path / "renders"
    png = clean.view("a_only").render(out)
    assert png.exists() and png.stat().st_size > 0
    assert png.name == "a_only_iso.png"  # slug + resolved camera projection


# --------------------------------------------------------------------------- #
# BOM slice — site BOM minus out-of-scope, no double count on a partition
# --------------------------------------------------------------------------- #
def test_bom_slice_partitions_the_site_bom(tmp_path):
    doc = _write_clean_site(tmp_path)
    clean = compile_site_file(doc)
    a = clean.view("a_only").bom_table()
    b = clean.view("b_only").bom_table()
    # a and b are disjoint subsystems with distinct lumber -> the two slices
    # partition the site BOM (sum of qtys == site total; union of items == site)
    site_bom = clean.assembly.bom_table()
    assert sum(r["qty"] for r in a) + sum(r["qty"] for r in b) == \
        sum(r["qty"] for r in site_bom)
    a_items = {r["item"] for r in a}
    b_items = {r["item"] for r in b}
    assert a_items and b_items and not (a_items & b_items)  # out-of-scope excluded
    assert a_items | b_items == {r["item"] for r in site_bom}


def test_bom_slice_matches_site_bom_over_in_scope_parts(site):
    """A view's BOM equals the site BOM recomputed over exactly the in-scope
    parts — 'site BOM minus out-of-scope'."""
    from detailgen.assemblies.assembly import DetailAssembly

    v = site.view("rock_anchor")
    scope_ids = {p.id for p in v.parts()}
    ref = DetailAssembly("ref")
    ref.parts = [p for p in site.assembly.parts if p.id in scope_ids]
    # same rows (item -> qty); list order can differ because a shared member
    # (the leg) sits in a different position in the view's build order than in
    # the site's part list — the CONTENT is the invariant, not the ordering.
    assert {r["item"]: r["qty"] for r in v.bom_table()} == \
        {r["item"]: r["qty"] for r in ref.bom_table()}


# --------------------------------------------------------------------------- #
# Reverse query — "where else does this appear?"
# --------------------------------------------------------------------------- #
def test_where_else_query_finds_the_shared_leg(site):
    # The shared launch leg is one node in THREE views, reached via any of its
    # qualified ids: platform (its owner), rock_anchor (retired rock_anchor/leg ->
    # platform/leg_pY bind) and, since SM4 item 3, trolley (retired
    # trolley/far_post -> platform/leg_pY bind). Single node, three views.
    assert set(site.views_including("platform/leg_pY")) == \
        {"platform", "rock_anchor", "trolley"}
    assert set(site.views_including("rock_anchor/leg")) == \
        {"platform", "rock_anchor", "trolley"}


def test_where_else_query_unshared_part_one_view(site):
    # an anchor-only part (a clamp angle) is in the rock_anchor view only
    got = site.views_including("rock_anchor/angle_0")
    assert got == ["rock_anchor"]


def test_where_else_unknown_part_teaches(site):
    with pytest.raises(KeyError, match="no part"):
        site.views_including("platform/not_a_part")


# --------------------------------------------------------------------------- #
# Callouts (live value) + camera
# --------------------------------------------------------------------------- #
def test_view_callouts_resolve_live_values(site):
    ra = site.view("rock_anchor")
    outs = ra.callouts()
    assert outs == [{"label": '1/2" LEG GAP (off rock)',
                     "p0": [0.0, 0.0, 0.0], "p1": [0.0, 0.0, 12.7]}]


def test_callout_may_reference_any_subsystem_by_qualified_name(site):
    # a rock_anchor-scoped view referencing a PLATFORM param (cross-subsystem)
    v = View(ViewSpec(
        name="x", include=(Selector("subsystem", "rock_anchor"),),
        callouts=(ViewCallout(param="platform.leg_station", label="STA {v}"),)), site)
    (out,) = v.callouts()
    assert out["label"].startswith("STA ")


def test_callout_unknown_param_teaches(site):
    v = View(ViewSpec(name="x", include=(Selector("subsystem", "rock_anchor"),),
                      callouts=(ViewCallout(param="rock_anchor.no_such"),)), site)
    with pytest.raises(SpecSchemaError, match="qualified site value"):
        v.callouts()


def test_camera_resolves(site):
    assert site.view("platform").camera() == {"projection": "iso", "zoom_to_scope": True}
    assert site.view("rock_anchor").camera() == {"projection": "front", "zoom_to_scope": True}


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_views_are_deterministic():
    a = compile_site_file(SITE_SPEC)
    b = compile_site_file(SITE_SPEC)
    a.validate(); b.validate()
    for name in ("platform", "rock_anchor", "tree", "trolley"):
        assert a.view(name).part_ids() == b.view(name).part_ids()
        assert a.view(name).bom_table() == b.view(name).bom_table()
        assert [str(f) for f in a.view(name).findings()] == \
               [str(f) for f in b.view(name).findings()]
