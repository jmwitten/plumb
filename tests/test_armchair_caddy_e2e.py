"""End-to-end smoke test for the novel ``armchair_caddy`` detail.

This is the pipeline's GENERALITY probe: a tiny hand-authored spec that is NOT
the zipline, driven through the whole flow fast (compile -> validate -> per-part
fabrication records -> fabrication-fold invariant -> BOM/cut lengths -> honest
support/bearing verdicts). It exists so a reviewer can watch a non-zipline design
exercise the same machinery, and so the progression harness (``scripts/
smoke_progression.py``) has a committed spec to re-run at each FAB milestone.

The design (see ``details/armchair_caddy.spec.yaml``): a three-board saddle that
straddles a sofa arm. One flat top board caps the arm; two side boards drop down
its sides, butt-jointed under the top board and held by hidden interior
registration rails (glued up to the top, screwed into the sides). The caddy
fastens to NOTHING on the sofa — it BEARS on the arm top by gravity. The arm is
an EXISTING context body (self-grounded, like the platform's trunk).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.core.process_graph import (
    verify_assembly_fabrication,
    _fabrication_record_of,
)

_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "details" / "armchair_caddy.spec.yaml"
HARNESS = _REPO / "scripts" / "smoke_progression.py"
VIEW_RENDERER = _REPO / "scripts" / "render_caddy_views.py"

#: The fabricated members and the fabrication steps each must carry. The two 1x6
#: side boards are crosscut to length + eased; the 5/4x6 top board is additionally
#: BORED — the cup hole is a designed recess (CL-2 ``bore`` FEATURE), a DISTINCT
#: step kind from a clearance ``notch`` so the cut note speaks the hole's own name
#: ("cup hole"), never trunk-clearance language. The two full-depth 1x6 registration
#: rails (the D1 hidden-fastener revision, deepened by the D6 stability fix) are
#: plain crosscut blocks — no ease, no bore.
_EXPECTED_STEPS = {
    "side board +X": ["crosscut", "ease"],
    "side board -X": ["crosscut", "ease"],
    "top board": ["crosscut", "ease", "bore"],
    "registration rail +X": ["crosscut"],
    "registration rail -X": ["crosscut"],
}

#: Per-member stock profile (the top board is 5/4x6 decking, the sides plain 1x6,
#: the registration rails full-depth 1x6).
_EXPECTED_STOCK = {
    "side board +X": "1x6",
    "side board -X": "1x6",
    "top board": "5/4x6 PT",
    "registration rail +X": "1x6",
    "registration rail -X": "1x6",
}


@pytest.fixture(scope="module")
def caddy():
    """Compile + validate once; the assertion tests share the built detail."""
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def test_compiles_and_validates_with_declared_bench_staging(caddy):
    """compile_spec_file -> validate runs the full sweep with an HONEST
    verdict. The rail->top joints are hardware-free glued bonds (nothing
    for the installability checks to judge); the side joints author
    joint-geometry embedment minimums. The eight side-screw corridors meet
    the sofa arm in final geometry but clear in the authored whole-detail
    bench frame. Because the arm is connection-free context, every clear
    carries the stronger DECLARED TRUST/P1 ceiling."""
    detail, report = caddy
    from collections import Counter
    assert report.failures == []
    access = [f for f in report.findings if f.check == "install_access"]
    assert Counter(f.verdict for f in access) == Counter({"PASS": 8})
    assert all("sofa arm" in f.detail
               and "[staging]" in f.detail
               and "DECLARED TRUST" in f.detail
               and "insertion travel is not analyzed" in f.detail
               and f.declared_order and f.declared_trust
               for f in access)
    # termination is green on merit: 8 GEOMETRY-PROVEN side bites at the
    # authored minimum. The glued rail->top bonds contribute NO install
    # verdicts at all (no hardware — the type's explicit empty contract),
    # and their connectivity is the derived bonded_to edges.
    terms = [f for f in report.findings if f.check == "install_termination"]
    assert len(terms) == 8 and all(f.passed for f in terms)
    assert sum("declared minimum [authored_override]" in f.detail
               for f in terms) == 8
    bonded = [e for e in detail._connection_checks.edges
              if e.kind == "bonded_to"]
    assert len(bonded) == 2
    assert report.blocking == [] and report.ok


def test_interior_caddy_screw_heads_are_authored_flush_not_proud(caddy):
    detail, _report = caddy
    installs = detail._connection_checks.installs
    assert len(installs) == 2
    assert all(ri.contract.head == "flush_countersunk" for ri in installs)
    assert all(ri.provenance_map["head"] == "authored_override"
               for ri in installs)


def test_every_board_has_expected_fabrication_record(caddy):
    """Each fabricated board carries a ProcessRecord whose steps are exactly the
    operations a builder performs — crosscut + ease on every board, plus the cup
    hole (a ``bore``) through the top board. The purchased parts (the screws, the
    existing arm) carry no record, the honest 'not made, bought'."""
    detail, _report = caddy
    by_name = {p.name: p for p in detail.assembly.parts}

    steps_by_name = {}
    for name, part in by_name.items():
        rec = _fabrication_record_of(part.component)
        if rec is not None:
            steps_by_name[name] = [s.kind for s in rec.steps]

    assert steps_by_name == _EXPECTED_STEPS

    # The screws and the existing arm are purchased-as-is: no fabrication record.
    for name in ("rail-side screw +X upper 0", "rail-side screw -X lower 1", "sofa arm"):
        assert _fabrication_record_of(by_name[name].component) is None

    # Each board's stock is a real linear stick of the expected profile.
    for name, profile in _EXPECTED_STOCK.items():
        rec = _fabrication_record_of(by_name[name].component)
        assert rec.stock.profile == profile
        assert rec.stock.form == "linear_stick"


def test_fabrication_fold_invariant_holds(caddy):
    """The fabrication-fold invariant: every fabricated part's installed solid is
    byte-identical to fold(stock, steps), and no material-removing feature exists
    without a declared step. Raises FabricationFoldError on any drift; a clean
    return is the assertion."""
    detail, _report = caddy
    verify_assembly_fabrication(detail.assembly)  # raises on any drift


def test_bom_rows_and_cut_lengths(caddy):
    """The BOM is derived from the fabrication records, so the cut lengths it
    reports are the crosscut lengths, not an independently-declared number: two
    7in 1x6 side boards, one 9.5in 5/4x6 top board, two 5.5in 1x6 registration
    rails (the D6 fix — same nominal as the sides but a shorter cut, so a separate
    row), and eight rail-side screws (the rail->top joints are glued — no
    hardware, and wood glue is a shop consumable, never a billed row). The
    existing arm is tagged 'existing', never billed as purchased stock."""
    detail, _report = caddy
    bom = detail.bom_table()

    def in_len(r):
        return round(r["length_mm"] / 25.4, 2)

    # Both the sides and the rails are 1x6, but at different cut lengths, so they
    # bill as two distinct rows (bom_group keys on nominal + length). Cut lengths
    # read straight off the crosscut step (retro R28: one source).
    rows_1x6 = [r for r in bom if r["item"] == "1x6 lumber"]
    assert len(rows_1x6) == 2
    side_row = next(r for r in rows_1x6 if in_len(r) == 7.0)   # the two side boards
    rail_row = next(r for r in rows_1x6 if in_len(r) == 5.5)   # the two D6 rails
    assert side_row["qty"] == 2
    assert rail_row["qty"] == 2

    top_row = next(r for r in bom if "5/4x6" in r["item"])
    assert top_row["qty"] == 1
    assert in_len(top_row) == 9.5

    # No 1x2 stock remains — the shallow cleats were deepened into 1x6 rails.
    assert not [r for r in bom if r["item"] == "1x2 lumber"]

    # Eight rail-side screws total (two pairs per rail), one length row — the
    # rail->top joints are glued and bill no hardware.
    screw_rows = [r for r in bom if "Screw" in r["item"]]
    assert len(screw_rows) == 1
    assert sum(r["qty"] for r in screw_rows) == 8

    # The sofa arm is EXISTING context, not purchased lumber — it must not be
    # billed as stock, and its row is honestly marked existing.
    arm_ids = {"boulder-0"}
    assert not any(arm_ids & set(r["ids"]) for r in bom
                   if r["item"] == "1x6 lumber" or "5/4x6" in r["item"])
    arm_row = next(r for r in bom if "existing" in r["item"].lower())
    assert arm_row["qty"] == 1


def test_bearing_on_arm_is_represented_capacity_absent(caddy):
    """The support story, asserted as the HONEST verdict. The top board bears
    flat on the arm top (the gravity saddle) — a PASSing ``bearing`` finding, i.e.
    bearing REPRESENTED. There is NO support-obligation finding (the caddy is a
    loose saddle, not a walking surface) and NO floating check (no constructed
    ground), and crucially NO capacity/adequacy verdict anywhere: rung-4 load
    capacity is honestly absent, never a fake CLEAN capacity claim."""
    _detail, report = caddy

    # The gravity-saddle bearing on the EXISTING arm is represented and passes.
    arm_bearings = [f for f in report.findings
                    if f.check == "bearing" and "sofa arm" in f.subject]
    assert len(arm_bearings) == 1
    assert arm_bearings[0].passed
    assert arm_bearings[0].verdict == "PASS"

    # The side boards do NOT bear on the arm (clearance) — no such bearing exists.
    assert not any(f.check == "bearing" and "side board" in f.subject
                   and "sofa arm" in f.subject for f in report.findings)

    # No support-obligation finding: nothing is declared a walking_surface, so the
    # rung-3 support check never runs — the honest statement that a loose saddle
    # is not an occupied surface with a support obligation.
    assert not any(f.check == "support" for f in report.findings)

    # No capacity/adequacy claim of any kind — rung 4 stays UNKNOWN-by-absence.
    for f in report.findings:
        assert "capacity" not in f.detail.lower() or "not analyzed" in f.detail.lower()


def test_full_flow_is_fast():
    """The whole from-scratch flow (compile -> validate -> fabrication verify ->
    BOM) runs well under a generous 60s budget — a smoke test stays cheap so it
    can run in the normal suite and be re-run repeatedly by the progression
    harness. Timed from a cold compile (the fixture is not reused here)."""
    t0 = time.perf_counter()
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    verify_assembly_fabrication(detail.assembly)
    detail.bom_table()
    elapsed = time.perf_counter() - t0

    assert report.ok
    assert elapsed < 60.0, f"e2e flow took {elapsed:.1f}s (budget 60s)"


def test_raster_builder_captions_avoid_x_coordinate_part_names():
    """Static builder captions use semantic nouns while renderer contracts keep
    their coordinate-bearing machine keys and explicit coordinate axes."""
    source = VIEW_RENDERER.read_text()
    tree = ast.parse(source)
    captions = tuple(
        call.args[3].value
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "draw"
        and len(call.args) >= 4
        and isinstance(call.args[3], ast.Constant)
        and isinstance(call.args[3].value, str)
    )

    assert captions
    assert not [caption for caption in captions
                if "+X" in caption or "-X" in caption]
    assert "END: arm length, side-board 7in drop" in captions
    assert any("ZOOM registration-rail corner" in caption
               for caption in captions)

    for machine_name in (
        "side board +X",
        "side board -X",
        "registration rail +X",
        "registration rail -X",
    ):
        assert f'"{machine_name}":' in source
    assert 'hide=("sofa arm",)' in source
    assert 'ax.set_xlabel("X (across arm)")' in source
    assert 'ax.set_ylabel("Y (along arm)")' in source
    assert 'ax.set_zlabel("Z up")' in source


def _fab2_surface_present() -> bool:
    """Independently probe the tree under test for FAB-2's cut-note surface — the
    SAME report-layer function the harness targets. Era-aware: this flips to True
    on a post-FAB-2 tree without editing the test."""
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    try:
        import consolidated_report
        return callable(getattr(consolidated_report, "_cutlist_fab_note", None))
    except Exception:
        return False


def _section(block: str, key: str) -> str:
    """The lines of one ``--- ... ---`` section of the harness block (up to the
    next section header or the closing bar)."""
    out, capture = [], False
    for ln in block.splitlines():
        if ln.startswith("==="):
            capture = False
            continue
        if ln.startswith("---"):
            capture = key in ln
            continue
        if capture:
            out.append(ln)
    return "\n".join(out)


def test_progression_harness_matches_the_tree_it_runs_on(caddy):
    """Run scripts/smoke_progression.py as the controller would (a fresh
    subprocess against this worktree) and assert the block MATCHES REALITY for
    WHATEVER era it runs on — populated where the capability is built, honest N/A
    where it is not. It probes the checked-out tree's actual FAB-2/FAB-4 surfaces
    rather than hard-coding an era, so fixing the probe and running post-FAB-2
    does not turn this green test red (the era-lock the review flagged)."""
    detail, _report = caddy

    # Ground truth for THIS tree, probed the same way the harness does.
    fab2 = _fab2_surface_present()
    eg = detail.evidence_graph
    fab4 = bool(eg.nodes_of_kind("process_step") or eg.edges_of_kind("produced_by"))

    env = dict(os.environ)
    shim = _REPO / ".shim"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(shim)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    out = subprocess.run(
        [sys.executable, str(HARNESS), "--worktree", str(_REPO)],
        capture_output=True, text=True, env=env, timeout=180)
    assert out.returncode == 0, out.stderr
    block = out.stdout

    # Structure: header + every section present, and the BOM/verdicts flow through.
    assert "armchair-caddy progression probe" in block
    for section in ("validation verdicts", "bill of materials",
                    "process records", "derived cut list", "evidence walkback"):
        assert section in block, section
    # The declared off-sofa bench frame resolves all eight access questions.
    assert "failures: 0" in block and "blocking: 0" in block
    assert "1x6 lumber" in block and '7.00"' in block and '9.50"' in block
    assert '5.50"' in block                              # the D6 1x6 registration rails

    # FAB-1 is present in every era at/after the caddy's base: the process-record
    # section names the real steps, including the top board's cup-hole bore.
    assert "FAB-1=yes" in block
    proc = _section(block, "(FAB-1)")
    assert "crosscut" in proc and "ease" in proc and "bore" in proc

    # FAB-2: the caps flag and the cut-list section must match the tree's reality.
    assert f"FAB-2={'yes' if fab2 else 'no'}" in block
    cut = _section(block, "(FAB-2)")
    if fab2:
        # built -> the top board's cup-hole BORE yields a real cut-note; NEVER 'not built'.
        assert "N/A (not built yet)" not in cut
        assert "bore" in cut
    else:
        assert "N/A (not built yet)" in cut

    # FAB-4: same era-aware check on the evidence-walkback section.
    assert f"FAB-4={'yes' if fab4 else 'no'}" in block
    ev = _section(block, "(FAB-4)")
    if fab4:
        assert "N/A (not built yet)" not in ev
        assert "produced_by edges:" in ev
    else:
        assert "N/A (not built yet)" in ev

    # task-8 fields — present and populated on this tree (post-FAB-3 + VISREV +
    # the committed artifacts), asserted by their real section content.
    doc = _section(block, "doc build")
    # the real reader-facing HTML build document (task 10), reusing site machinery.
    assert "single-detail HTML build document: OK" in doc
    assert "panel(s)" in doc                              # size + panel count reported
    assert "PASS" in doc and "UNKNOWN — NOT ANALYZED" in doc  # honest headline
    vis = _section(block, "VISREV")
    assert "open /" in vis and "resolved" in vis
    # the field must NAME which store it read (auditable, not an anonymous count).
    assert "caddy-findings.yaml" in vis
    vc = _section(block, "view coverage")
    assert "primary" in vc and "zoom" in vc and "why-not" in vc


# ---------------------------------------------------------------------------- #
# task 8: doc render through the real entry path, visual review, view coverage.
# ---------------------------------------------------------------------------- #
def test_certifying_render_accepts_declared_staging(caddy, tmp_path):
    """With no blocking verdict left, both the certifying and documentation
    entry paths render. The trust ceiling remains visible in their reports."""
    detail, _report = caddy
    certified = detail.render(tmp_path / "certified")
    assert certified.exists()
    assert "DECLARED TRUST" in (certified / "validation_report.md").read_text()
    out = detail.render_documentation(tmp_path / "doc")
    assert out.exists()


def test_doc_renders_through_render_documentation(caddy, tmp_path):
    """The FULL pipeline includes the documentation render via the REAL entry
    path — Detail.render_documentation (FAB-3's ungated doc verb), NOT a
    build_html shortcut. It writes the geometry (GLB), the build-doc report, and
    the coverage matrix, and the report LEADS with the honest per-family headline
    (not a bare CLEAN)."""
    detail, _report = caddy
    out = detail.render_documentation(tmp_path)

    glb = out / "detail.glb"
    report_md = out / "validation_report.md"
    assert glb.exists() and glb.stat().st_size > 0          # a real 3D model
    assert (out / "coverage_matrix.json").exists()
    assert report_md.exists()

    text = report_md.read_text()
    assert "# Armchair Coffee Caddy" in text
    # honest headline: the two PASS families named AND the UNKNOWNs surfaced.
    assert "Physical geometry" in text and "Construction completeness" in text
    assert "UNKNOWN — NOT ANALYZED" in text
    # the cup hole and the gravity-saddle story are documented.
    assert "cup hole" in text.lower()
    # the coverage matrix is appended (honesty is a framework property).
    assert "Coverage matrix" in text
    assert "DECLARED TRUST" in text
    assert "**bench whole detail**" in text
    assert "**set whole detail in place**" in text
    assert "authored staging claim" in text


def test_build_sequence_derives_bench_then_set_and_does_not_list_arm_loose(caddy):
    from detailgen.validation.build_sequence import build_sequence_model

    detail, _report = caddy
    steps, loose = build_sequence_model(detail)
    titles = [step["title"] for step in steps]
    assert titles[0] == "bench whole detail"
    assert "set whole detail in place" in titles
    assert titles.index("bench whole detail") < \
        titles.index("set whole detail in place")
    # The staging defense names only the frame/context claim. Glue/cure/screw
    # process order is not representable until +process and must not be smuggled
    # into a reader step as if the CPG had checked it.
    why = steps[0]["why"]
    assert "assembled off the sofa" in why and "DECLARED TRUST" in why
    assert "then drive" not in why and "cure" not in why.lower()
    assert steps[0]["claim"] == "staging"
    assert steps[titles.index("set whole detail in place")]["joins"] == \
        ("whole detail",)
    assert "sofa arm" not in loose


def test_reader_configuration_formats_values_from_the_compiled_namespace():
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR

    value = {"notes": [("Cut", "{top_len:g}in / {station:.2f}in")]}
    assert SDR._format_reader_data(
        value, {"top_len": 9.5, "station": 2.15}) == {
            "notes": [("Cut", "9.5in / 2.15in")]}


def test_visual_review_store_is_valid_and_grounded():
    """The caddy's visual-review findings load through the REAL store loader,
    every finding is grounded in at least one caddy render, resolutions carry
    their required evidence, and the open/resolved split is what the reviewer
    filed (1 open, 3 resolved). This is the visual-review FEEDBACK the directive
    asks for — real suspicions filed through the real machinery."""
    from detailgen.review import load_findings_file

    store = _REPO / "reviews" / "visual" / "caddy-findings.yaml"
    s = load_findings_file(store)  # raises on any schema/vocabulary/evidence error
    assert len(s.findings) == 4
    assert len(s.open_findings()) == 1              # C1 (renderer context-ghosting)
    assert len(s.findings) - len(s.open_findings()) == 3

    for f in s.findings:
        assert f.renders, f.id
        for r in f.renders:
            assert "armchair_caddy" in r.path       # grounded in a caddy render
        # a resolved finding must carry its HOW/evidence note (loader enforces,
        # re-assert to pin the contract).
        if not f.is_open:
            assert f.resolution.note.strip()
    # the stability suspicion resolves to the coverage's honest UNKNOWN, never a
    # forced pass — the directive's canonical resolution.
    c2 = s.by_id()["C2"]
    assert c2.invariant_family == "Support/Stability representation"
    assert c2.resolution.status == "documented-assumption-or-unknown"
    assert "not analyzed" in c2.resolution.note.lower()


def test_view_coverage_table_audited_both_directions():
    """The view-coverage decision table is auditable in BOTH directions per the
    directive: every candidate area is EITHER a ZOOM (with a named view) OR a
    recorded WHY-NOT (with a rationale) — no high-complexity area is silently
    left without a view AND without a reason; and redundant zooms (a mirror joint,
    a plain visible surface) are why-nots, not over-generation."""
    import json

    data = json.loads(
        (_REPO / "reviews" / "visual" / "caddy-view-coverage.json").read_text())
    primary = data["primary_views"]
    areas = data["candidate_areas"]
    assert len(primary) == 4
    zooms = [a for a in areas if a["decision"] == "ZOOM"]
    whynots = [a for a in areas if a["decision"] == "WHY-NOT"]
    assert len(zooms) == 3 and len(whynots) == 4      # audited both directions

    for a in areas:
        assert a["decision"] in ("ZOOM", "WHY-NOT"), a
        # every decision is justified: a ZOOM names its view, a WHY-NOT its reason.
        if a["decision"] == "ZOOM":
            assert a.get("view"), a["area"]
        assert a.get("rationale", "").strip(), a["area"]
    # the deliberately-mirrored -X joint is a recorded why-not, not a second
    # identical zoom (the over-generation guard the directive names).
    mirror = next(a for a in areas if "-X butt joint" in a["area"])
    assert mirror["decision"] == "WHY-NOT" and "mirror" in mirror["rationale"].lower()


def _visible_text(html: str) -> str:
    """The reader-VISIBLE text layer: drop <script>/<style> AND all tags+attrs,
    leaving only text nodes. This is what defeats the F5 false-positive class — a
    token that only appears in the hidden JSON viewer payload or a base64 blob
    (both attributes / script bodies) must NOT satisfy a content assertion."""
    import re
    v = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    v = re.sub(r"<style.*?</style>", " ", v, flags=re.S)
    v = re.sub(r"<[^>]+>", " ", v)          # drop every tag + its attributes
    return re.sub(r"\s+", " ", v)


#: Zipline tokens that must NEVER appear in the caddy's VISIBLE text. The only
#: allowed residual is "trunk"/"tree-face" — the shared cut-note renderer's
#: domain-overfit wording (task #7), which the doc explicitly contextualizes.
_ZIPLINE_TOKENS = [
    "zipline", "strap gate", "strap-gate", "joist", "wire mesh", "welded-wire",
    "grab bar", "grab-handle", "grab handle", "boulder", "launch leg",
    "launch edge", "kids", "pier block", "rock anchor", "trolley", "hang a kid",
    "bounce test", "anchor nut", "tree-end", "beam", "deck run", "mesh infill",
]


def test_single_detail_html_build_document(tmp_path):
    """The caddy smoke flow ends in a reader-facing HTML build document — the same
    kind the zipline site gets — built through the single-detail entry point that
    REUSES the consolidated report's machinery (no parallel implementation). Assert
    the document is well-formed and carries every reused section: the panel with
    embedded stills, the coverage matrix with the honest headline, the BOM + cut
    plan, the visual-review block from the caddy store, and the 3D-viewer GLB."""
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR

    # the single-detail entry point takes a SPEC PATH (caddy = first consumer).
    info = SDR.build_document(
        tmp_path / "caddy_doc.html",
        spec_path=_REPO / "details" / "armchair_caddy.spec.yaml", preview=False)
    html = (tmp_path / "caddy_doc.html").read_text()

    assert info["panels"] == 1                          # one element panel, counted
    # an unregistered detail errors helpfully rather than emitting an empty page.
    with pytest.raises(SystemExit):
        SDR.build_document(tmp_path / "x.html",
                           spec_path=_REPO / "details" / "platform.spec.yaml")

    # well-formed single sheet.
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert html.count('<div class="sheet">') == 1

    # honest headline (not a bare CLEAN) — the SAME per-family verdict the report
    # and the coverage matrix carry.
    assert "Physical geometry" in info["headline"] and "Construction completeness" in info["headline"]
    assert "UNKNOWN — NOT ANALYZED" in info["headline"]
    assert info["headline"] in html

    # reused sections all present.
    assert "Armchair Coffee Caddy" in html            # title block / panel
    assert 'class="panel"' in html                    # render_panel
    assert html.count("data:image/png;base64,") >= 5  # embedded panel stills
    assert "UNKNOWN — NOT ANALYZED" in html            # coverage matrix
    assert "Build sequence (derived)" in html
    assert "bench whole detail" in html
    assert "set whole detail in place" in html
    for cid in ("C1", "C2", "C3", "C4"):               # caddy visual-review block
        assert cid in html
    assert 'id="detail-glb-' in html and "Explore in 3D" in html  # 3D viewer + GLB

    # BOM/labels asserted against the VISIBLE text (F5): every caddy part is in the
    # reader-facing buy list — including BOTH 1x6 side boards (bug F3) — and the arm
    # is the spec's "sofa arm", not the "boulder" primitive it is modeled on (F4).
    vis = _visible_text(html)
    assert "1x6 lumber" in vis and "5/4x6 decking" in vis
    assert "structural screw" in vis.lower()
    assert "sofa arm (existing)" in vis and "Boulder (existing)" not in vis
    low = vis.lower()
    assert "five-piece saddle" in low
    assert "flush with the top-board ends" in low
    assert "inner face sits 1in outside" in low
    assert "top cut formula" in low and "9.5in" in low
    assert "rail layout" in low and "6.5in apart" in low
    assert "screw stations" in low and "2.15in" in low and "3.35in" in low
    assert "0.75in and 4in below" in low
    assert "tools:" in low and "3.5in opening" in low and "hole saw" in low
    assert "drill/driver" in low
    assert "consumables:" in low and "water-resistant finish" in low
    assert "intended cup" in low and "fit template" in low
    assert "drill press" in low and "side handle" in low and "jigsaw" in low
    assert "workpiece clamped" in low
    assert "head=flush_countersunk" in low and "head=proud" not in low
    assert "longitudinal sliding is not analyzed" in low
    # Hidden viewer metadata is reader-visible on hover and must use the
    # domain part, not the rectangular primitive used to approximate it.
    raw = html.lower()
    assert "leveling nuts" not in raw and "natural stone" not in raw
    assert '"type":"existing context"' in raw

    # a real, self-contained document, not a stub.
    assert info["size_bytes"] > 200_000


def test_caddy_doc_carries_no_zipline_content(tmp_path):
    """The class-closer (F5): the reader-facing caddy document must inherit ZERO
    zipline content from the reused builders. Asserted against the VISIBLE text
    layer (not the hidden JSON payload / base64 blobs, which was the false-positive
    that let the contaminated doc pass). Covers F1 (field notes), F2 (footer), F3
    (buy-list intro), F4 (labels). CL-2 closed the task-#7 residual end-to-end: the
    cup hole is now a ``bore`` FEATURE that speaks its OWN name, so NO trunk /
    tree-face wording survives anywhere in the doc (the whitelisted exception is
    gone — see the zero-count assertion below)."""
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR

    SDR.build_document(tmp_path / "d.html",
                       spec_path=_REPO / "details" / "armchair_caddy.spec.yaml")
    vis = _visible_text((tmp_path / "d.html").read_text()).lower()

    # zero zipline tokens in the reader-facing text.
    present = [t for t in _ZIPLINE_TOKENS if t in vis]
    assert not present, f"zipline contamination in caddy doc: {present}"

    # CL-2 closed the task-#7 residual: the cup hole is a `bore` FEATURE that
    # speaks its own name, so NO trunk / tree-face wording survives (the former
    # whitelisted exception of 2 each is now ZERO).
    assert vis.count("trunk") == 0 and vis.count("tree-face") == 0

    # F1: caddy build notes present (from the panel), zipline field-fit absent.
    assert "cup hole" in vis and "gravity" in vis
    assert "bounce test" not in vis and "loaded bar" not in vis
    # F2: footer names the caddy + one model, not the Kids' Zipline / 4 models.
    assert "armchair coffee caddy" in vis and "one parametric model" in vis
    assert "kids" not in vis and "4 parametric models" not in vis


def test_caddy_doc_prose_describes_the_current_rail_joint(tmp_path):
    """Guard against retro R24 (hand-authored consumer prose drifting out of sync
    with the model across design revisions). The reader-facing prose must describe
    the CURRENT top<->side joint — hidden 1x6 registration rails, face-grain
    fastening — and must NOT carry the pre-D1 top-face-screw narrative. Positive +
    targeted-negative, both on the VISIBLE text (low-brittleness: the negatives are
    phrases that ONLY ever described the retired straight-down-into-end-grain joint;
    'end grain' itself is NOT banned — the top's end-grain BEARING is still true)."""
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR

    SDR.build_document(tmp_path / "d.html",
                       spec_path=_REPO / "details" / "armchair_caddy.spec.yaml")
    vis = _visible_text((tmp_path / "d.html").read_text()).lower()

    # POSITIVE: the current joint is described — registration rails, face grain.
    assert "registration rail" in vis
    assert "face grain" in vis
    # NEGATIVE: the retired pre-D1 joint narrative is gone. These phrases described
    # ONLY the top board screwed straight down into the side's end grain on the show
    # face — impossible for the hidden-rail joint, so their presence = stale prose.
    for stale in ("screwed straight down", "top-face screw stations",
                  "screws per joint"):
        assert stale not in vis, f"stale pre-D1 joint prose in caddy doc: {stale!r}"


# ---------------------------------------------------------------------------- #
# task 12: design review — ruling applied honestly + disclosed in the doc.
# ---------------------------------------------------------------------------- #
def test_design_findings_store_statuses_per_ruling():
    """The design-review store (D1-D6) loads through the REAL loader with the
    statuses set by the 2026-07-08 rulings and the revisions that followed: D1
    fixed-by-revision (the hidden-cleat revision), D6 fixed-by-revision (those
    cleats deepened into 1x6 registration rails — the stability fix), D2
    accepted-with-rationale (hardwood; species vocabulary = CL v2), D3/D4/D5 open.
    The fix + rationale live in each finding, never lost."""
    from detailgen.review import load_findings_file

    store = _REPO / "reviews" / "visual" / "caddy-design-findings.yaml"
    s = load_findings_file(store)                       # raises on any schema error
    by = s.by_id()
    assert set(by) == {"D1", "D2", "D3", "D4", "D5", "D6"}
    assert len(s.open_findings()) == 3                  # D1/D2/D6 resolved; D3/D4/D5 open

    # D1: FIXED by the revision — resolved under the first-class fixed-by-revision
    # state (a real defect removed by a spec revision), its note recording the
    # cleat_screwed type + the deleted show-face screws.
    assert not by["D1"].is_open
    assert by["D1"].resolution.status == "fixed-by-revision"
    d1note = by["D1"].resolution.note.lower()
    assert "fixed" in d1note and "cleat_screwed" in d1note
    assert "deleted" in d1note and "face grain" in d1note
    # D6: FIXED by the rail revision — the cleats deepened into 1x6 rails, note
    # citing the rail fix + the restored registration depth.
    assert not by["D6"].is_open
    assert by["D6"].resolution.status == "fixed-by-revision"
    d6note = by["D6"].resolution.note.lower()
    assert "fixed" in d6note and "rail" in d6note and "5.5" in d6note
    # D2: accepted-with-rationale, deferred to species vocabulary (CL v2).
    assert not by["D2"].is_open
    assert by["D2"].resolution.status == "documented-assumption-or-unknown"
    assert "species" in by["D2"].resolution.note.lower()


def test_design_review_block_disclosed_in_caddy_doc(tmp_path):
    """The document itself discloses the design review (the directive's force): a
    'Design review' block, rendered by the SAME review renderer from the sibling
    store, sits alongside the visual-review block. Asserted on the VISIBLE text."""
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR

    SDR.build_document(tmp_path / "d.html",
                       spec_path=_REPO / "details" / "armchair_caddy.spec.yaml")
    vis = _visible_text((tmp_path / "d.html").read_text())

    # both honesty surfaces present and distinct.
    assert "Design review" in vis and "intent register" in vis
    assert "Visual review" in vis                       # the C1-C4 block still there
    for did in ("D1", "D2", "D3", "D4", "D5"):
        assert did in vis
    # D1 reads as FIXED via the first-class design-change state (not an assumption).
    assert "fixed-by-revision" in vis
    # the design block still gates nothing — no zipline contamination introduced.
    assert not [t for t in _ZIPLINE_TOKENS if t in vis.lower()]


def test_rail_revision_hides_fasteners_and_registers_deep():
    """The D6 revision (2026-07-08), joints as shipped today: two full-depth 1x6
    registration rails (dropping 5.5in down the arm side), each GLUED up to the
    top board's underside and screwed into its side board with an upper + lower
    side-screw pair. No fastener lands on the top show face; the deep rail
    restores lateral registration (rock ~2.6deg vs the shallow cleat's 9.5deg);
    and the top<->side end-grain bearing is unchanged (a rail registers, it is
    not the gravity seat)."""
    from detailgen.core.units import IN

    detail = compile_spec_file(SPEC)
    detail.build()
    parts = detail.assembly.parts
    by = {p.name: p for p in parts}
    names = list(by)

    # Two interior registration rails; no top-face 'joint screw' parts, no 1x2 cleat.
    rails = [p for p in parts if p.name.startswith("registration rail")]
    assert len(rails) == 2
    assert not any("joint screw" in n for n in names)

    # Each rail registers DEEP: its inner face is 0.25in off the arm (reveal
    # preserved) and it drops ~5.5in below the arm-top pivot (Z=0), vs the 1x2
    # cleat's 1.5in — the D6 stability restoration.
    for rail in rails:
        bb = rail.world_solid().val().BoundingBox()
        assert round((0 - bb.zmin) / IN, 2) == 5.5      # registration depth below pivot
    # arm reveal: rail inner face 0.25in off the arm side at X=3.0in (=arm_w/2).
    rp = by["registration rail +X"].world_solid().val().BoundingBox()
    assert round((rp.xmin / IN) - 3.0, 2) == 0.25

    # Eight rail-side screws (two pairs per rail; the rail->top joints are glued,
    # no hardware), NONE on the show face: every screw's top stays below the top
    # board's show face.
    screws = [p for p in parts if "screw" in p.name]
    assert len(screws) == 8
    show_face_z = 1.0 * IN                              # top board top face (deck_thk)
    for s in screws:
        zmax = s.world_solid().val().BoundingBox().zmax
        assert zmax < show_face_z - 1e-3, f"{s.name} breaches the top show face"

    # The top-on-side end-grain gravity seat stays a declared, passing bearing pair
    # (the rails register/hold parts together; they are NOT the seat).
    report = detail.validate()
    side_bearings = [f for f in report.findings if f.check == "bearing"
                     and "top board" in f.subject and "side board" in f.subject]
    assert len(side_bearings) == 2 and all(f.passed for f in side_bearings)
