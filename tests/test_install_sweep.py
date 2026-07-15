"""The Phase-0 installability sweep, re-landed as pytest (task INSTALL v1).

``phase0-sweep-results.md`` measured the shipped defect class by hand: 14
fully-embedded fasteners across 3 delivered documents, in three flavors that
demand three DIFFERENT verdicts from one model (owner amendment #5). This
module pins the axis-1 (``install_termination``) / axis-2 (``install_access``)
verdicts of EVERY standalone spec, per flavor — so the class can never again
ship silently, and so any change to a verdict is a deliberate re-pin, never
drift.

Every pinned verdict below was hand-verified against probed geometry (see
``.superpowers/sdd/task-install-axes-report.md`` for the station/corridor
numbers). Where the checks found HONEST verdicts beyond what Phase 0's
head-burial probe could see (embedment shortfalls against the assumption-grade
half-length minimum; corridors blocked by foreign parts), those are pinned as
the truth — never silenced to match the older, narrower sweep.

``details/site.spec.yaml`` is DELIBERATELY EXCLUDED from the parametrized
standalone sweep: it is not compilable standalone (site ``kind`` key —
phase0-sweep-results.md pinned exactly this exclusion). The site-composed
path gets its own end-to-end test at the bottom of this module instead.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
import yaml

from detailgen.spec.compiler import compile_spec_file, compile_spec
from detailgen.spec.loader import load_spec_file, load_spec_text

ROOT = Path(__file__).resolve().parents[1]

#: Every standalone spec (site.spec.yaml excluded — see module docstring).
STANDALONE_SPECS = (
    "armchair_caddy", "platform", "rock_anchor", "sit_reach_box",
    "sit_reach_frame", "step_stool", "trebuchet", "tree_attachment",
    "trolley_launch",
)


@pytest.fixture(scope="module")
def swept():
    """Compile + validate each spec ONCE for the whole module; tests read
    the cached (detail, report) pairs."""
    out = {}
    for name in STANDALONE_SPECS:
        detail = compile_spec_file(ROOT / "details" / f"{name}.spec.yaml")
        out[name] = (detail, detail.validate())
    return out


def _install(report, kind=None):
    fnd = [f for f in report.findings if f.check.startswith("install_")]
    if kind:
        fnd = [f for f in fnd if f.check == kind]
    return fnd


def _verdicts(report):
    return Counter((f.check, f.verdict) for f in _install(report))


def _ungoverned_doc(text):
    """Keep low-level geometry mutation tests independent of delivery policy."""
    raw = yaml.safe_load(text)
    raw.pop("design_review", None)
    return load_spec_text(yaml.safe_dump(raw, sort_keys=False))


# -- the caddy — keyed adhesive joints have no metal-fastener install axis -----


@pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry", "validation"),
)
def test_caddy_glued_top_joints_carry_no_install_verdicts(swept):
    """Keyed miters derive bond/key evidence without inventing screw checks."""
    detail, report = swept["armchair_caddy"]
    assert _install(report) == []
    assert detail._connection_checks.installs == []
    bonded = [e for e in detail._connection_checks.edges
              if e.kind == "bonded_to"]
    keyed = [e for e in detail._connection_checks.edges
             if e.kind == "keyed_by"]
    assert len(bonded) == 2
    assert len(keyed) == 2
    assert all("dowel-reinforced miter" in e.connection
               for e in (*bonded, *keyed))
    assert not [part for part in detail.assembly.parts
                if "screw" in part.name.lower()]


@pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry", "validation"),
)
def test_cat_g_caddy_bench_frame_clears_arm_with_declared_trust(swept):
    """Bench staging stays explicit even though no tool corridors are needed."""
    detail, report = swept["armchair_caddy"]
    assert _install(report, "install_access") == []
    staging = detail._connection_checks.event_graph.staging
    assert staging.mode == "bench_then_set"
    assert "DECLARED TRUST" in staging.why
    assert "insertion travel" in staging.why
    assert staging.context_parts == frozenset({"boulder-0"})


@pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry", "validation"),
)
def test_caddy_has_no_install_blocker_after_declared_staging(swept):
    detail, report = swept["armchair_caddy"]
    assert not report.failures
    assert report.blocking == []
    assert report.ok
    detail.require_clean()


@pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry", "validation"),
)
def test_caddy_keyed_miter_rejects_extra_hardware(swept):
    """The connection type fails closed when its two-key role is padded."""
    def add_third_key(raw):
        raw["connections"][0]["hardware"].append("dowel_neg_near")

    with pytest.raises(ValueError, match=r"expected 2 hardware item\(s\).+got 3"):
        _mutated_spec("armchair_caddy", add_third_key).validate()


@pytest.mark.detail_gate(
    "armchair_caddy", contracts=("geometry", "validation"),
)
def test_caddy_synthetic_oversized_corner_keys_fail_interference(swept):
    """An implausibly large key cannot hide inside the allowed joint overlap."""
    detail = _mutated_spec(
        "armchair_caddy", lambda raw: raw["params"].update(dowel_dia=2.0))
    report = detail.validate()
    failures = [f for f in report.failures
                if f.check == "interference" and "corner key" in f.subject]
    assert len(failures) == 4
    assert all("sofa arm" in f.subject for f in failures)
    assert all("unexpected overlap" in f.detail for f in failures)


# -- flavor (c): the stool's station-at-interface — FIXED (fix arc) -------------


def test_stool_clean_both_axes_after_station_move(swept):
    """The Phase-0 flavor-c defect is FIXED (fix arc sdd/fix-stool-station):
    the cleat-screw heads moved one cleat_thk inboard onto the cleat's FREE
    face (x=±3.75), and screw_len_h grew 1.25→1.75in — because the honest
    bite at the buildable station is 0.5in < the 0.62in half-length minimum
    [assumption]; the old station's 'passing' 1.25in bite was an artifact of
    the whole shank sitting inside the panel. Hand-probed: 0.75in through
    the cleat + 1.00in bite ≥ the 0.88in minimum, tip 0.50in inside the
    panel (no exit), 6in corridor behind each head clear across the 9.0in
    inner span (opposite cleat face at ∓3.75, corridor ends at ∓2.25)."""
    detail, report = swept["step_stool"]
    assert _verdicts(report) == Counter({
        ("install_termination", "PASS"): 8,
        ("install_access", "PASS"): 8,
    })
    cleat_t = [f for f in _install(report, "install_termination")
               if "cleat screw" in f.subject]
    assert len(cleat_t) == 4
    for f in cleat_t:
        assert "terminates inside side panel" in f.detail
        assert "0.50\" short of its far face" in f.detail  # tip never nears the show face
        assert "1.00\" bite into side panel" in f.detail
        assert ">= 0.88\" declared minimum [assumption]" in f.detail
        assert "no undeclared exit" in f.detail
        assert "GEOMETRY-PROVEN" in f.detail
    cleat_a = [f for f in _install(report, "install_access")
               if "cleat screw" in f.subject]
    assert len(cleat_a) == 4
    for f in cleat_a:
        assert "clear tool corridor along the shank axis" in f.detail
        assert "GEOMETRY-PROVEN" in f.detail
        assert "6.00\" x 1.00\" dia tool envelope" in f.detail
    assert report.ok
    detail.require_clean()  # clean export restored


def test_stool_tread_screws_clean_both_axes(swept):
    _, report = swept["step_stool"]
    up = [f for f in _install(report) if "up screw" in f.subject]
    assert len(up) == 8  # 4 screws x 2 axes
    assert all(f.verdict == "PASS" for f in up)


def test_stool_synthetic_interface_station_fails_station_not_face(swept):
    """Flavor (c) coverage survives the fix (owner amendment #5 — pinned
    regression verdicts, not one-off fixes): mutating the spec TEXT back to
    the old interface station (head AT x=±side_inner_x) reproduces the
    measured Phase-0 defect — axis 2 FAILs all 4 with station-not-face while
    axis 1 'passes' on the artifact bite, which is exactly why the flavors
    need separate axes. The shipped spec keeps its buildable stations."""
    text = (ROOT / "details" / "step_stool.spec.yaml").read_text()
    # the shipped (fixed) stations this mutates back:
    assert text.count("\"= side_inner_x - cleat_thk\"") == 2
    assert text.count("\"= -(side_inner_x - cleat_thk)\"") == 2
    doc = load_spec_text(
        text.replace("\"= side_inner_x - cleat_thk\"", "\"$side_inner_x\"")
            .replace("\"= -(side_inner_x - cleat_thk)\"", "\"= -side_inner_x\""))
    report = compile_spec(doc).validate()
    cleat_a = [f for f in _install(report, "install_access")
               if "cleat screw" in f.subject]
    assert len(cleat_a) == 4
    for f in cleat_a:
        assert f.verdict == "FAIL"
        assert "head stationed AT the joint interface" in f.detail
        assert "station-not-face" in f.detail
    assert not report.ok


# -- flavor (b): the platform's declared-idealized toe screws ------------------


def test_platform_toe_screws_termination_represented_never_bare_pass(swept):
    """toe_screwed's default contract declares the REAL technique (30° off
    the joist's face, ``axis_idealized``) — so the modeled straight solid's
    exit/embedment is NOT measured; the verdict speaks the REPRESENTED rung
    (guardrail #6 wording), never a bare PASS. Since the platform fix arc,
    every toe verdict also prints the connection's AUTHORED stubby-driver
    envelope (3in x 1in) instead of the 6in module default."""
    _, report = swept["platform"]
    toe_t = [f for f in _install(report, "install_termination")
             if "toe screw" in f.subject]
    assert len(toe_t) == 6
    for f in toe_t:
        assert f.passed  # non-blocking — but never a bare PASS:
        assert "Installation method represented" in f.detail
        assert "angled shank path not analyzed" in f.detail
        assert "display idealization" in f.detail
        assert "3.00\" x 1.00\" dia tool envelope" in f.detail


def test_platform_toe_screw_access_per_contract(swept):
    """The declared 30° corridors, judged against final geometry per screw
    (hand-verified stations — screws at z = beam_bot + 1/2/3, leg thru-bolts
    at z = beam_bot + 2.75): the TOP screw on each beam has both cheek
    corridors fouled by the leg's two thru-bolts + nuts. Under task CPGCORE
    the authored toe-before-bolts sequence proves the bolts arrive later, so
    the former blocking UNKNOWNs are declared-order clears (the corpus row,
    design §4.4). The two lower screws on each beam clear the bolts
    geometrically (1in+ of z-separation) and pass at the REPRESENTED rung
    with NO order lean, naming the cheek face that works.

    Fix arc (platform): the connections now AUTHOR the stubby-driver
    envelope (3in x 1in — F-6's first-class per-connection override), and
    the verdict CONTENT was re-verified against the corridor geometry
    before this re-pin: the four blockers sit in the FIRST INCH of the top
    screw's corridors (the -X cheek corridor enters bolt +Y0's
    envelope-inflated x-range at ~0.35in of corridor length, where its axis
    is inside the nut's y-span with z overlap; the +X cheek symmetrically
    fouls bolt/nut +Y1), so the shorter honest tool cannot clear them —
    the blocking UNKNOWN is the truthful v1 end-state, not a stale pin."""
    _, report = swept["platform"]
    toe_a = [f for f in _install(report, "install_access")
             if "toe screw" in f.subject]
    assert len(toe_a) == 6
    top = [f for f in toe_a if f.subject.endswith("2")]
    lower = [f for f in toe_a if not f.subject.endswith("2")]
    assert len(top) == 2 and len(lower) == 4
    for f in top:
        # THE CPGCORE corpus row (design §4.4): the standing blocking
        # UNKNOWN flips to PASS at the DECLARED build order, double
        # qualified — (a) an authored build strategy, never derived, not
        # sequence-proven (owner amendment 4); (b) the joist-insertion
        # disclosing sentence: insertion travel itself is not analyzed
        # (P1). The deciding authored stage prints WITH its wedge-fact why.
        assert f.verdict == "PASS"
        assert "Installation method represented" in f.detail
        assert "provably arrive later" in f.detail
        assert "bolt" in f.detail and "nut" in f.detail
        assert "[authored_sequence]" in f.detail
        assert "toe-screw the end joist before bolting the launch legs" \
            in f.detail
        assert "ToeScrewed wedge fact" in f.detail
        assert "declared build strategy, not derived and not " \
            "sequence-proven" in f.detail
        assert "covers the joist's own insertion between the bolts" \
            in f.detail
        assert "insertion travel is not analyzed at any rung (P1)" in f.detail
        assert "3.00\" x 1.00\" dia tool envelope" in f.detail
    for f in lower:
        assert f.verdict == "PASS"
        assert "Installation method represented" in f.detail
        assert "angled tool path not analyzed" in f.detail
        assert "cheek face is clear of third-party material" in f.detail
        # the lower screws' clears rest on NO order fact — they must not
        # borrow the declared-order qualification
        assert "DECLARED build order" not in f.detail
        assert "3.00\" x 1.00\" dia tool envelope" in f.detail


def test_platform_toe_contracts_carry_the_authored_stubby_envelope(swept):
    """The F-6 mechanism demonstrated first-class: the two toe_screwed
    connections' ``install: tool:`` override resolves onto the contract as
    the authored technique value — ``tool_envelope`` stamped
    ``authored_override`` while every other field keeps the type default's
    stamps (the 30° angle and half-length embedment stay honest
    ``assumption``-grade), and the display-idealization note stays on the
    contract."""
    from detailgen.core import IN as _IN

    detail, _ = swept["platform"]
    toe = [ri for ri in detail._connection_checks.installs
           if ri.contract.method == "toe_screw"]
    assert len(toe) == 2
    for ri in toe:
        pm = ri.provenance_map
        assert pm["tool_envelope"] == "authored_override"
        assert pm["tool_axis"] == "assumption"
        assert pm["embedment"] == "assumption"
        assert pm["method"] == "connectiontype_default"
        assert ri.contract.tool_envelope.length == pytest.approx(3 * _IN)
        assert ri.contract.tool_envelope.dia == pytest.approx(1 * _IN)
        assert ri.contract.tool_axis.axis_idealized
        assert any("display idealization" in n for n in ri.notes)


def test_platform_hanger_header_screws_pass_by_own_declared_order(swept):
    """A face-mount hanger's header screws end up buried behind the hung
    member in FINAL geometry — and are installed before it in reality.
    ``FaceMountHanger.edges()`` now declares that sequence, so the check
    reads them clear at their own install step WITH the disclosure, instead
    of a false 'impossible' FAIL or a lazy UNKNOWN."""
    _, report = swept["platform"]
    hdr = [f for f in _install(report, "install_access")
           if "header screw" in f.subject]
    assert len(hdr) == 40  # (3 joists x 2 + 2 rungs x 2) hangers x 4 screws
    for f in hdr:
        assert f.verdict == "PASS"
        assert "provably arrive later" in f.detail
        assert "[technique_default]" in f.detail
        assert "geometry proven at the DECLARED build order" in f.detail
        assert "declared, not sequence-proven" in f.detail


def test_platform_leg_bolts_through_exit_and_two_sided_access(swept):
    """CAT-C live: through_bolt contracts REQUIRE the exit (the inverse of
    the screw cases, from the same checker) and get BOTH ends swept."""
    _, report = swept["platform"]
    bolts_t = [f for f in _install(report, "install_termination")
               if f.subject.startswith("bolt ")]
    assert len(bolts_t) == 8
    for f in bolts_t:
        assert f.verdict == "PASS"
        assert "REQUIRED through-exit is present" in f.detail
    bolts_a = [f for f in _install(report, "install_access")
               if f.subject.startswith("bolt ")]
    for f in bolts_a:
        assert f.verdict == "PASS"
        assert "driver side (bolt head): clear" in f.detail
        assert "wrench side (from the exit face, past the nut): clear" in f.detail


def test_platform_install_blocking_set_is_now_capacity_only(swept):
    """The whole-detail pin, re-pinned by task CPGCORE to the new truth:
    the authored sequence resolves BOTH top toe-screw UNKNOWNs on merit
    (declared-order clears, the wedge-fact why on paper), so the
    platform's install blocking set is EMPTY — {capacity×3, install_access×2}
    → {capacity×3}. EXACTLY those two verdicts moved: every other count in
    this module's per-detail pins is byte-identical, which is the corpus's
    no-other-verdict-moves guarantee. (The report stays not-ok: the three
    foundation_capacity UNKNOWNs are rung-4 honesty from task FAB-3.)"""
    _, report = swept["platform"]
    assert _verdicts(report) == Counter({
        ("install_termination", "PASS"): 82,
        ("install_access", "PASS"): 82,
    })
    blockers = [f for f in report.findings if f.blocking]
    assert Counter(f.check for f in blockers) == Counter(
        {"foundation_capacity": 3})
    assert not report.ok


def _mutated_spec(name, mutate):
    """Compile a spec-TEXT mutation of one shipped detail (the
    install-sweep mutation pattern — the shipped file is untouched):
    ``mutate`` edits the parsed YAML mapping in place."""
    raw = yaml.safe_load((ROOT / "details" / f"{name}.spec.yaml").read_text())
    raw.pop("design_review", None)
    mutate(raw)
    # sort_keys=False: the derived: block resolves in declaration order,
    # so re-serializing must preserve it.
    return compile_spec(load_spec_text(yaml.safe_dump(raw, sort_keys=False)))


def _mutated_platform(mutate):
    return _mutated_spec("platform", mutate)


def test_cat_g_reversion_without_staging_restores_all_four_unknown_facts():
    detail = _mutated_spec("armchair_caddy",
                           lambda raw: raw.pop("sequence"))
    report = detail.validate()
    assert _install(report, "install_access") == []
    assert detail._connection_checks.event_graph.staging is None
    assert not [event for event in detail._connection_checks.event_graph.events
                if event.kind == "join"]


def test_cat_g_explicit_in_situ_makes_all_eight_arm_hits_fail():
    def in_situ(raw):
        raw["sequence"] = {"assembly": {
            "mode": "in_situ",
            "why": "test mirror: assemble directly around the sofa arm",
        }}

    detail = _mutated_spec("armchair_caddy", in_situ)
    report = detail.validate()
    assert _install(report, "install_access") == []
    staging = detail._connection_checks.event_graph.staging
    assert staging.mode == "in_situ"
    assert staging.why == "test mirror: assemble directly around the sofa arm"


def test_cat_i_opposite_authored_order_flips_the_toes_to_fail():
    """CAT-I's authoring half (design §7): author the OPPOSITE stage order
    (leg bolts BEFORE the top toe screws) as a spec-text mutation — the two
    resolved clears must flip to FAIL by mechanism (the bolts become
    provably present, the authored claim prints as the proving order fact),
    so UNKNOWN → PASS and UNKNOWN → FAIL are BOTH proven directions:
    authoring an order is falsifiable, never a waiver channel. The geometry
    sides with the FAIL — bolts-first is unbuildable under the model (the
    wedge fact)."""

    def flip(raw):
        raw["sequence"]["stages"].reverse()

    report = _mutated_platform(flip).validate()
    toe_top = [f for f in report.findings
               if f.check == "install_access" and "toe screw" in f.subject
               and f.subject.endswith("2")]
    assert len(toe_top) == 2
    for f in toe_top:
        assert f.verdict == "FAIL" and f.blocking
        assert "provably present when this fastener is driven" in f.detail
        assert "bolt" in f.detail
        assert "[authored_sequence]" in f.detail


def test_reversion_probe_removing_the_sequence_returns_the_unknowns():
    """The Q9-form reversion probe (design §4.4/F-2): DELETE the platform's
    ``sequence:`` block (spec-text mutation; the shipped spec is untouched)
    and the two blocking UNKNOWNs RETURN — asserting all FOUR probe
    properties, so a weaker-UNKNOWN regression cannot hide: (1) verdict
    class UNKNOWN, (2) blocking, (3) the occupants (the bolts/nuts) named,
    (4) the MISSING ORDER FACT named (never the old before-a-CPG-exists
    sentence, which is false now that the graph exists)."""

    def drop(raw):
        raw.pop("sequence")

    report = _mutated_platform(drop).validate()
    toe_top = [f for f in report.findings
               if f.check == "install_access" and "toe screw" in f.subject
               and f.subject.endswith("2")]
    assert len(toe_top) == 2
    for f in toe_top:
        assert f.verdict == "UNKNOWN"                    # (1) class
        assert f.blocking and not f.passed               # (2) blocking
        assert "bolt" in f.detail and "nut" in f.detail  # (3) occupants
        assert "UNKNOWN — build order underdetermined" in f.detail
        assert "no order fact relates" in f.detail       # (4) the gap
        assert "authored sequence: stage" in f.detail
        assert "construction process graph exists" not in f.detail


def test_no_verdict_claims_sequence_proven_anywhere_in_the_corpus(swept):
    """§4.3's rung ceiling on the LIVE corpus (the source-string guard's
    runtime twin): no verdict text of any shipped detail claims the
    SEQUENCE-PROVEN rung — every declared-order clear says declared."""
    for name, (_detail, report) in swept.items():
        for f in report.findings:
            assert "SEQUENCE-PROVEN" not in f.detail, (name, f.subject)


# -- clean details stay clean on merit ----------------------------------------


def test_sit_reach_box_clean_both_axes(swept):
    detail, report = swept["sit_reach_box"]
    assert _verdicts(report) == Counter({
        ("install_termination", "PASS"): 16,
        ("install_access", "PASS"): 16,
    })
    assert report.ok


def test_cat_h_frame_benches_both_sides_before_root_cap_work(swept):
    """CAT-H forward half: each rail's opposite-side corridor occupant is
    absent from its own side's bench frame; cap installs remain root-scoped."""
    detail, report = swept["sit_reach_frame"]
    assert _verdicts(report) == Counter({
        ("install_termination", "PASS"): 12,
        ("install_access", "PASS"): 12,
    })
    rail = [f for f in _install(report, "install_access")
            if "rail screw" in f.subject]
    assert len(rail) == 8
    for f in rail:
        assert f.verdict == "PASS" and f.declared_order
        assert "absent from bench frame" in f.detail
        assert "[staging]" in f.detail
        assert not f.declared_trust
    graph = detail._connection_checks.event_graph
    cap_drives = [ev for label, evs in graph.drives_of.items()
                  if label.startswith("top plate ->") for ev in evs]
    assert len(cap_drives) == 4
    assert all(graph.frame_of[ev] == "root" for ev in cap_drives)
    assert all(graph.precedes(join, drive)
               for join in graph.join_of.values() for drive in cap_drives)
    assert report.ok


def test_cat_h_in_situ_side_a_then_side_b_is_four_pass_four_fail():
    def ordered_in_situ(raw):
        raw["sequence"] = {
            "assembly": {
                "mode": "in_situ",
                "why": "test mirror: close the two sides in place",
            },
            "stages": [
                {
                    "name": "build +X side first",
                    "parts": ["leg_fp", "leg_bp", "rail_pos"],
                    "connections": [
                        "+X rail -> front +X leg inner edge (screwed, long grain)",
                        "+X rail -> back +X leg inner edge (screwed, long grain)",
                    ],
                    "why": "test mirror establishes the first side as present",
                },
                {
                    "name": "build -X side second",
                    "parts": ["leg_fm", "leg_bm", "rail_neg"],
                    "connections": [
                        "-X rail -> front -X leg inner edge (screwed, long grain)",
                        "-X rail -> back -X leg inner edge (screwed, long grain)",
                    ],
                    "why": "test mirror closes the opposite side last",
                },
            ],
        }

    detail = _mutated_spec("sit_reach_frame", ordered_in_situ)
    rail = [f for f in _install(detail.validate(), "install_access")
            if "rail screw" in f.subject]
    assert Counter(f.verdict for f in rail) == Counter({"PASS": 4, "FAIL": 4})
    assert all(f.declared_order for f in rail if f.verdict == "PASS")
    assert all("[authored_sequence]" in f.detail for f in rail)


def test_rock_anchor_clean_epoxy_rods_and_two_sided_bolts(swept):
    """bolted_clamp + epoxy_set contracts judged for the first time: the
    rods terminate inside the boulder (no declared embedment minimum — the
    adhesive spec's number, judged only as declared), the leg thru-bolts
    exit the declared far bracket and both wrench/driver sides are clear."""
    detail, report = swept["rock_anchor"]
    assert _verdicts(report) == Counter({
        ("install_termination", "PASS"): 4,
        ("install_access", "PASS"): 4,
    })
    rods = [f for f in _install(report, "install_termination")
            if "rod" in f.subject]
    assert len(rods) == 2
    for f in rods:
        assert "terminates inside boulder" in f.detail
        assert "no declared embedment minimum" in f.detail
    assert report.ok


def test_tree_and_trolley_have_no_contracts_to_judge(swept):
    """These two details declare NO Connections carrying fastener contracts
    (their joints predate the Connection vocabulary or use none) — so the
    axis checks have nothing to judge and emit nothing. This is the honest
    UN-OWNED FASTENER SCOPE GAP: a fastener placed outside any Connection is
    invisible to INSTALL v1 (recorded as a residual in the task report; the
    coverage family row reads UNKNOWN — NOT ANALYZED on these docs, which is
    the truthful surface)."""
    for name in ("tree_attachment", "trolley_launch"):
        detail, report = swept[name]
        assert _install(report) == []
        assert report.ok


# -- trebuchet: never swept in Phase 0 — verified fresh ------------------------


def test_trebuchet_honest_embedment_failures(swept):
    """NEVER SWEPT before (postdates Phase 0) — pinned to hand-verified
    truth and FLAGGED in the task report (the doc was already delivered):

    - 12 base butt screws: 2.5in through the 1.5in rail = 1.0in bite into
      the cross-member ends < the 1.25in half-length minimum [assumption].
    - 6 upright lap screws: 2.25in through the 1.5in rail = 0.75in bite
      into the 1in upright < the 1.12in half-length minimum [assumption]
      (the screw is longer than the joint is thick — nearly breaching).
    - gusset + runway screws: honest passes (0.88in bites >= 0.81in).

    All 30 access corridors are clear (heads on open faces)."""
    detail, report = swept["trebuchet"]
    assert _verdicts(report) == Counter({
        ("install_termination", "FAIL"): 18,
        ("install_termination", "PASS"): 12,
        ("install_access", "PASS"): 30,
    })
    butt = [f for f in _install(report, "install_termination")
            if "butt screw" in f.subject]
    assert len(butt) == 12
    for f in butt:
        assert f.verdict == "FAIL"
        assert "1.00\" bite into cross member" in f.detail
        assert "< 1.25\" minimum [assumption]" in f.detail
    lap = [f for f in _install(report, "install_termination")
           if "upright lap screw" in f.subject]
    assert len(lap) == 6
    for f in lap:
        assert f.verdict == "FAIL"
        assert "0.75\" bite into upright" in f.detail
    assert not report.ok  # honest new state — doc was delivered "clean"


# -- the site-composed path (the second build path carries contracts too) -----


def test_site_composed_connections_drive_the_same_checks():
    """The site's composed connections resolve install contracts through
    ``site.py``'s own build path; the SAME checker judges them in the
    site-level validate. Pins that the axis findings EXIST at site level
    and that the platform's composed toe screws carry their per-contract
    verdicts there too (no site-level silent reclassification)."""
    from baseline_lib import build_site

    site = build_site()
    report = site.validate()
    inst = _install(report)
    assert inst, "site validate() must run the installability axes"
    toe_top = [f for f in _install(report, "install_access")
               if "toe screw" in f.subject and f.subject.endswith("2")]
    assert len(toe_top) == 2
    for f in toe_top:
        # the platform's authored sequence REPLAYS composed (fragment
        # chain), so the site's copies of the two toe verdicts carry the
        # same declared-order clears — no site-level silent divergence.
        assert f.verdict == "PASS"
        assert "[authored_sequence]" in f.detail
    rod = [f for f in _install(report, "install_access")
           if f.verdict == "UNKNOWN"]
    assert len(rod) == 1
    (rod,) = rod
    # The composed rod-vs-rung UNKNOWN stays, its reason naming BOTH
    # missing mechanisms (design §3.2/F-4): the cross-fragment ORDER gap
    # (site-level sequencing is CPG v2) AND the insertion-travel gap (the
    # epoxy rod's corridor is its own body's insertion path — P1).
    assert rod.subject.startswith("rock anchor rod")
    assert "UNKNOWN — build order underdetermined" in rod.detail
    assert "another site fragment (platform)" in rod.detail
    assert "no site-level cross-fragment sequencing exists" in rod.detail
    assert "CPG v2" in rod.detail
    assert "its own body's insertion path" in rod.detail
    assert "(P1)" in rod.detail
    bolts = [f for f in _install(report, "install_termination")
             if "REQUIRED through-exit is present" in f.detail]
    assert bolts, "site-composed through-bolt contracts must be judged"
