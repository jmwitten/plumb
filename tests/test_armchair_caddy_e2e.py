"""End-to-end smoke test for the novel ``armchair_caddy`` detail.

This is the pipeline's GENERALITY probe: a tiny hand-authored spec that is NOT
the zipline, driven through the whole flow fast (compile -> validate -> per-part
fabrication records -> fabrication-fold invariant -> BOM/cut lengths -> honest
support/bearing verdicts). It exists so a reviewer can watch a non-zipline design
exercise the same machinery, and so the progression harness (``scripts/
smoke_progression.py``) has a committed spec to re-run at each FAB milestone.

The design (see ``details/armchair_caddy.spec.yaml``): a three-panel hardwood
sleeve that straddles a sofa arm. One flat top panel caps the arm; two matching
side panels turn down through glued 45-degree miters, each reinforced by two
diagonal hardwood corner keys. The caddy
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
import yaml

from detailgen.spec.compiler import compile_spec_file
from detailgen.core.process_graph import (
    verify_assembly_fabrication,
    _fabrication_record_of,
)

_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "details" / "armchair_caddy.spec.yaml"
HARNESS = _REPO / "scripts" / "smoke_progression.py"
VIEW_RENDERER = _REPO / "scripts" / "render_caddy_views.py"

_EXPECTED_STEPS = {
    "side panel +X": ["crosscut", "ease", "miter_crosscut"],
    "side panel -X": ["crosscut", "ease", "miter_crosscut"],
    "top panel": ["crosscut", "ease", "miter_crosscut", "miter_crosscut", "bore"],
}

_EXPECTED_STOCK = {
    "side panel +X": "3/4 in hardwood panel, 5 1/2 in wide",
    "side panel -X": "3/4 in hardwood panel, 5 1/2 in wide",
    "top panel": "3/4 in hardwood panel, 5 1/2 in wide",
}


@pytest.fixture(scope="module")
def caddy():
    """Compile + validate once; the assertion tests share the built detail."""
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def test_compiles_and_validates_with_declared_bench_staging(caddy):
    """The hardware-free keyed miters validate without invented screw checks."""
    detail, report = caddy
    assert report.failures == []
    access = [f for f in report.findings if f.check == "install_access"]
    assert access == []
    terms = [f for f in report.findings if f.check == "install_termination"]
    assert terms == []
    bonded = [e for e in detail._connection_checks.edges
              if e.kind == "bonded_to"]
    assert len(bonded) == 2
    keyed = [e for e in detail._connection_checks.edges if e.kind == "keyed_by"]
    assert len(keyed) == 2
    assert report.blocking == [] and report.ok


def test_reinforced_miters_have_no_metal_install_contract(caddy):
    detail, _report = caddy
    assert detail._connection_checks.installs == []
    assert not [part for part in detail.assembly.parts
                if "screw" in part.name.lower() or "bracket" in part.name.lower()]


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

    # The dowels and existing arm are purchased-as-is: no fabrication record.
    for name in ("corner key +X front", "corner key -X back", "sofa arm"):
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
    """The BOM derives the two panel lengths and four flush dowel keys."""
    detail, _report = caddy
    bom = detail.bom_table()

    def in_len(r):
        return round(r["length_mm"] / 25.4, 2)

    panels = [r for r in bom if r["item"] == "3/4 in hardwood panel"]
    assert len(panels) == 2
    side_row = next(r for r in panels if in_len(r) == 7.75)
    top_row = next(r for r in panels if in_len(r) == 8.0)
    assert side_row["qty"] == 2
    assert top_row["qty"] == 1
    dowel_row = next(r for r in bom if r["item"] == "3/8 in hardwood dowel")
    assert dowel_row["qty"] == 4 and in_len(dowel_row) == 1.06
    assert not [r for r in bom if "screw" in r["item"].lower()
                or "rail" in r["item"].lower()]

    # The sofa arm is EXISTING context, not purchased lumber — it must not be
    # billed as stock, and its row is honestly marked existing.
    arm_ids = {"boulder-0"}
    assert not any(arm_ids & set(r["ids"]) for r in bom
                   if r["item"] == "3/4 in hardwood panel")
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

    # The side panels do NOT bear on the arm (clearance) — no such bearing exists.
    assert not any(f.check == "bearing" and "side panel" in f.subject
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
    assert "END: arm length and removable waterfall sleeve" in captions
    assert any("ZOOM reinforced miter" in caption
               for caption in captions)

    for machine_name in (
        "side panel +X",
        "side panel -X",
        "corner key +X front",
        "corner key -X back",
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
    # The keyed glue joints need no metal-fastener access corridors.
    assert "failures: 0" in block and "blocking: 0" in block
    assert "3/4 in hardwood panel" in block
    assert '7.75"' in block and '8.00"' in block
    assert "3/8 in hardwood dowel" in block

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
def test_certifying_render_accepts_declared_staging(tmp_path):
    """Legacy ungoverned details retain both historical render entry paths."""
    raw = yaml.safe_load(SPEC.read_text())
    raw.pop("design_review")
    legacy_spec = tmp_path / SPEC.name
    legacy_spec.write_text(yaml.safe_dump(raw, sort_keys=False))
    detail = compile_spec_file(legacy_spec)
    detail.validate()

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
    # +process provenance is not hidden behind the per-connection sample cap.
    assert "DowelReinforcedMiter.process_events" in text
    assert "[inferred] event order" in text
    assert "event order drive(top -> side" in text
    assert "top -> side +X (dowel-reinforced miter)" in text
    assert "keyed_by" in text


def test_build_sequence_derives_each_miter_cure_before_final_join(caddy):
    from detailgen.assemblies.event_graph import Event
    from detailgen.validation.build_sequence import (
        build_sequence_model, render_build_sequence_md)

    detail, _report = caddy
    steps, loose = build_sequence_model(detail)
    titles = [step["title"] for step in steps]
    assert titles[0] == "bench whole detail"
    assert "set whole detail in place" in titles
    assert titles.index("bench whole detail") < \
        titles.index("set whole detail in place")
    why = steps[0]["why"]
    assert "finished off the sofa" in why and "DECLARED TRUST" in why
    assert steps[0]["claim"] == "staging"
    assert steps[titles.index("set whole detail in place")]["joins"] == \
        ("whole detail",)
    assert "sofa arm" not in loose

    graph = detail._connection_checks.event_graph
    joints = (
        "top -> side +X (dowel-reinforced miter)",
        "top -> side -X (dowel-reinforced miter)",
    )
    process_steps = [step for step in steps if step["process"] is not None]
    assert len(process_steps) == 2
    assert all(step["process"]["fact"].provenance ==
               "authored_process_fact" for step in process_steps)
    join = graph.join_of["whole detail"]
    for joint in joints:
        bond = Event("drive", joint, "")
        cure = Event("process", joint, "cure")
        assert graph.precedes(bond, cure)
        assert graph.precedes(cure, join)
        cure_step = next(step for step in process_steps
                         if step["process"]["event"] == cure)
        assert cure_step["order_claims"] == ()

    first = render_build_sequence_md(detail)
    assert first == render_build_sequence_md(detail)
    assert detail.resolved_after() == ()
    assert first.count("Insert both corner keys") == 2
    assert "No generic duration is represented" in first


def test_miter_process_order_has_one_authoritative_owner(caddy):
    from detailgen.assemblies.event_graph import FAMILY_NECESSITY

    detail, _report = caddy
    graph = detail._connection_checks.event_graph
    process_edges = [edge for edge in graph.edges
                     if edge.family == FAMILY_NECESSITY
                     and edge.b.kind == "process"]
    assert len(process_edges) == 2
    assert all(edge.a.kind == "drive" and edge.b.group == "cure"
               for edge in process_edges)
    facts = [fact for fact in detail._connection_checks.derived
             if fact.rule == "DowelReinforcedMiter.process_events"]
    assert len(facts) == 2
    assert not [fact for fact in detail._connection_checks.derived
                if fact.rule == "sequence.after"]


def test_cat_k_sequence_prose_exists_only_in_typed_authoring_surfaces():
    """The §6.5 grep/AST closer: report scripts and free spec prose cannot
    author a glue/cure/screw sequence beside the graph-derived one."""
    import re

    from detailgen.spec.loader import load_spec_file
    from detailgen.spec.schema import ProseSection

    script = (_REPO / "scripts" / "single_detail_report.py").read_text()
    constants = [
        node.value for node in ast.walk(ast.parse(script))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    sequence_pattern = re.compile(
        r"(?:glue|cure).{0,180}(?:before|then).{0,180}screw",
        flags=re.I | re.S)
    assert not [value for value in constants if sequence_pattern.search(value)]
    assert "Hidden rail joints — glue, then screws" not in script

    # Reusable modeling types cannot become a second owner of a consumer's
    # cross-connection sequence.  Scan the actual class docstring so this
    # closer fails if the caddy recipe drifts back into Glued's source docs.
    model_source = (_REPO / "src" / "assemblies" / "connection.py").read_text()
    model_tree = ast.parse(model_source)
    glued_class = next(
        node for node in model_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Glued")
    glued_doc = ast.get_docstring(glued_class) or ""
    assert not sequence_pattern.search(glued_doc)

    spec = load_spec_file(SPEC)
    free_text = [assumption for conn in spec.connections
                 for assumption in conn.assumptions]
    free_text.extend(section.text for section in spec.doc.sections
                     if isinstance(section, ProseSection))
    assert not [value for value in free_text if sequence_pattern.search(value)]


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
    mirror = next(a for a in areas if "-X reinforced miter" in a["area"])
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

    # BOM/labels asserted against visible text: panels, keys, and context all read
    # as the builder-facing objects rather than their implementation primitives.
    vis = _visible_text(html)
    assert "3/4 in hardwood panel" in vis
    assert "3/8 in hardwood dowel" in vis
    assert "Sofa arm (existing)" in vis and "Boulder (existing)" not in vis
    low = vis.lower()
    assert "three-panel hardwood sleeve" in low
    assert "reinforced-miter waterfall" in low
    assert "panel cuts" in low and "8in long point" in low and "7.75in long point" in low
    assert "corner-key layout" in low and "1.1875in" in low
    assert "doweling jig" in low and "clamp square" in low
    assert "water-resistant finish" in low
    assert "intended cup" in low and "fit templates" in low
    assert "no rail or metal fastener remains" in low
    assert "sliding resistance" in low
    assert "authored_process_fact" in low
    assert "selected adhesive label's full-cure/full-strength condition" in low
    assert "actual shop conditions" in low
    assert "no generic duration is represented" in low
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


def test_caddy_doc_prose_describes_the_current_reinforced_miter(tmp_path):
    """Guard against retro R24 (hand-authored consumer prose drifting out of sync
    with the model across revisions). The visible prose must describe the current
    keyed miters and omit every retired rail, bracket, and screw architecture."""
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR

    SDR.build_document(tmp_path / "d.html",
                       spec_path=_REPO / "details" / "armchair_caddy.spec.yaml")
    vis = _visible_text((tmp_path / "d.html").read_text()).lower()

    assert "45-degree glued miters" in vis
    assert "hardwood corner keys" in vis
    assert "two 3/8in hardwood keys" in vis
    for stale in ("registration rail", "structural screw", "cleat_screwed",
                  "screws per joint"):
        assert stale not in vis, f"stale retired-joint prose in caddy doc: {stale!r}"


# ---------------------------------------------------------------------------- #
# task 12: design review — ruling applied honestly + disclosed in the doc.
# ---------------------------------------------------------------------------- #
def test_design_findings_store_statuses_per_ruling():
    """The design-review store (D1-D6) loads through the REAL loader with the
    current reinforced-miter resolutions while D3/D4/D5 remain honest follow-ups."""
    from detailgen.review import load_findings_file

    store = _REPO / "reviews" / "visual" / "caddy-design-findings.yaml"
    s = load_findings_file(store)                       # raises on any schema error
    by = s.by_id()
    assert set(by) == {"D1", "D2", "D3", "D4", "D5", "D6"}
    assert len(s.open_findings()) == 3                  # D1/D2/D6 resolved; D3/D4/D5 open

    assert not by["D1"].is_open
    assert by["D1"].resolution.status == "fixed-by-revision"
    d1note = by["D1"].resolution.note.lower()
    assert "fixed" in d1note and "reinforced-miter" in d1note
    assert "deleted" in d1note and "hardwood dowels" in d1note
    assert not by["D6"].is_open
    assert by["D6"].resolution.status == "fixed-by-revision"
    d6note = by["D6"].resolution.note.lower()
    assert "fixed" in d6note and "eliminated" in d6note
    assert not by["D2"].is_open
    assert by["D2"].resolution.status == "fixed-by-revision"
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


def test_reinforced_miter_revision_uses_three_panels_and_four_keys():
    """The selected architecture has no hidden catch-up parts or metal hardware."""
    from detailgen.core.units import IN

    detail = compile_spec_file(SPEC)
    detail.build()
    parts = detail.assembly.parts
    by = {p.name: p for p in parts}
    names = list(by)

    panels = [p for p in parts if p.reader_name in ("Top panel", "Side panel")]
    keys = [p for p in parts if p.reader_name == "Corner key"]
    assert len(panels) == 3 and len(keys) == 4
    assert not any("rail" in n or "screw" in n or "bracket" in n for n in names)

    top = by["top panel"].world_solid().val().BoundingBox()
    sides = [by["side panel +X"].world_solid().val().BoundingBox(),
             by["side panel -X"].world_solid().val().BoundingBox()]
    assert round((top.xmax - top.xmin) / IN, 2) == 8.0
    assert round((sides[0].xmin - sides[1].xmax) / IN, 2) == 6.5
    assert all(round(p.component.diameter / IN, 3) == 0.375 for p in keys)

    report = detail.validate()
    bearings = [f for f in report.findings if f.check == "bearing"]
    assert len(bearings) == 1 and bearings[0].passed
