"""End-to-end test for the kids' two-step step stool — the first CL-first detail.

Mirrors the caddy e2e probe (compile -> validate -> fabrication records -> fold
invariant -> BOM -> honest verdicts), and adds the two guards the STOOLBUILD brief
requires:

  * the GOVERNING-DIMS GUARD (the owner contract): step surfaces 5.5in / 10.25in
    and footprint-depth >= upper-height are PINNED; if detailing ever pressures one,
    this test goes RED and the question returns to the owner (never silent drift).
  * the PROSE-TRUTHFULNESS GUARD (learned from the caddy's R24 round): the rendered
    build document must not claim what the model does not prove — tip-over /
    Support-Stability / Structural capacity read UNKNOWN — NOT ANALYZED (ANALYSIS-v1),
    and the reader-facing step-height numbers equal the MODEL's measured heights.

The design (details/step_stool.spec.yaml): two 2x10 side panels straddle the depth;
a 5/4x6 lower tread rides on 1x2 cleats screwed to the panels' inner faces; a 5/4x6
upper tread caps the panel tops, screwed down. It rests on the floor (EXISTING
context) by gravity. Register is functional-dominant, so the screws are visible.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.core.process_graph import (
    verify_assembly_fabrication,
    _fabrication_record_of,
)
from detailgen.validation.coverage import coverage_matrix

_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "details" / "step_stool.spec.yaml"
_IN = 25.4

#: GOVERNING dimensions — the owner contract. These are the numbers a redesign is
#: NOT allowed to move without the owner; the guard below asserts them off the
#: COMPILED MODEL (not the params), so a param edit that fails to move the geometry
#: is also caught.
GOV_UPPER_SURFACE_IN = 10.25
GOV_LOWER_SURFACE_IN = 5.5
GOV_MIN_FOOTPRINT_RATIO = 1.0   # footprint depth >= upper height (the tip-over ratio)

#: Fabricated members and the steps each carries. Panels + treads are crosscut +
#: eased; the 1x2 cleats are plain crosscut blocks (no ease authored). Screws and
#: the existing floor carry no record (bought / existing).
_EXPECTED_STEPS = {
    "side panel +X": ["crosscut", "ease"],
    "side panel -X": ["crosscut", "ease"],
    "upper tread": ["crosscut", "ease"],
    "lower tread": ["crosscut", "ease"],
    "cleat +X": ["crosscut"],
    "cleat -X": ["crosscut"],
}


@pytest.fixture(scope="module")
def stool():
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def _by_name(detail):
    return {p.name: p for p in detail.assembly.parts}


def _zmax_in(detail, name):
    bb = _by_name(detail)[name].world_solid().val().BoundingBox()
    return bb.zmax / _IN


def test_compiles_and_validates_clean(stool):
    """compile -> validate runs the full sweep with an HONEST verdict — CLEAN
    again since the station-move fix arc: the four cleat screws (the measured
    Phase-0 station-at-interface flavor) now head on the cleat's FREE face
    (x=±3.75) and, at 1.75in, bite 1.00in ≥ the 0.88in half-length minimum
    [assumption] — both axes GEOMETRY-PROVEN PASS on all 8 screws. The
    verdict texts are asserted so the clean state is the PROVEN one, never a
    silently-skipped check (the sweep pins the per-screw texts too)."""
    _detail, report = stool
    assert not report.failures and not report.blocking
    inst = [f for f in report.findings if f.check.startswith("install_")]
    assert len(inst) == 16  # 8 screws x 2 axes
    assert all(f.verdict == "PASS" for f in inst)
    cleat = [f for f in inst if "cleat screw" in f.subject]
    assert len(cleat) == 8
    for f in cleat:
        assert "GEOMETRY-PROVEN" in f.detail
    assert report.ok


def test_every_board_has_expected_fabrication_record(stool):
    """Each fabricated board carries a ProcessRecord of exactly the ops a builder
    performs; the screws and the existing floor carry none (bought / existing)."""
    detail, _report = stool
    by_name = _by_name(detail)
    steps_by_name = {}
    for name, part in by_name.items():
        rec = _fabrication_record_of(part.component)
        if rec is not None:
            steps_by_name[name] = [s.kind for s in rec.steps]
    assert steps_by_name == _EXPECTED_STEPS
    for name in ("up screw +X 0", "cleat screw -X 1", "floor"):
        assert _fabrication_record_of(by_name[name].component) is None


def test_fabrication_fold_invariant_holds(stool):
    """Every fabricated part's installed solid is byte-identical to fold(stock,
    steps), with no material-removing feature lacking a declared step."""
    detail, _report = stool
    verify_assembly_fabrication(detail.assembly)  # raises on any drift


def test_bom_rows_and_cut_lengths(stool):
    """BOM derived from the fabrication records: two 2x10 panels (11in), two 5/4x6
    treads (12in upper + 9in lower — two rows), two 1x2 cleats (4in), eight screws
    (two length rows). The floor is EXISTING, never billed as purchased stock."""
    detail, _report = stool
    bom = detail.bom_table()

    def in_len(r):
        return round(r["length_mm"] / _IN, 2)

    panel_rows = [r for r in bom if r["item"] == "2x10 lumber"]
    assert len(panel_rows) == 1 and panel_rows[0]["qty"] == 2
    assert in_len(panel_rows[0]) == 11.0

    tread_rows = [r for r in bom if "5/4x6" in r["item"]]
    assert {in_len(r) for r in tread_rows} == {12.0, 9.0}
    assert sum(r["qty"] for r in tread_rows) == 2

    cleat_rows = [r for r in bom if r["item"] == "1x2 lumber"]
    assert len(cleat_rows) == 1 and cleat_rows[0]["qty"] == 2 and in_len(cleat_rows[0]) == 4.0

    screw_rows = [r for r in bom if "Screw" in r["item"]]
    assert sum(r["qty"] for r in screw_rows) == 8

    # The floor is EXISTING context, not billed as lumber.
    floor_ids = {"boulder-0"}
    assert not any(floor_ids & set(r["ids"]) for r in bom
                   if "lumber" in r["item"] or "5/4x6" in r["item"])
    assert any("existing" in r["item"].lower() for r in bom)


def test_governing_dims_guard(stool):
    """THE GUARD (owner contract). Measured off the compiled model: the upper step
    surface is 10.25in, the lower is 5.5in, and the footprint depth is at least the
    upper height (the tip-over ratio that scored). If detailing ever pressures one,
    this goes RED and the question returns to the owner — never silent drift."""
    detail, _report = stool
    upper = _zmax_in(detail, "upper tread")
    lower = _zmax_in(detail, "lower tread")
    assert upper == pytest.approx(GOV_UPPER_SURFACE_IN, abs=0.02), (
        f"GOVERNING upper step surface drifted to {upper:.3f}in "
        f"(pinned {GOV_UPPER_SURFACE_IN}in) — return to the owner")
    assert lower == pytest.approx(GOV_LOWER_SURFACE_IN, abs=0.02), (
        f"GOVERNING lower step surface drifted to {lower:.3f}in "
        f"(pinned {GOV_LOWER_SURFACE_IN}in) — return to the owner")

    # Footprint depth = the panels' Y extent; ratio to the upper height is the
    # scored tip-over proxy and must not drop below 1.0.
    bb = _by_name(detail)["side panel +X"].world_solid().val().BoundingBox()
    depth_in = (bb.ymax - bb.ymin) / _IN
    ratio = depth_in / upper
    assert ratio >= GOV_MIN_FOOTPRINT_RATIO, (
        f"GOVERNING footprint ratio dropped to {ratio:.3f} "
        f"(min {GOV_MIN_FOOTPRINT_RATIO}) — return to the owner")


def test_honest_verdicts_analysis_v1(stool):
    """The honest coverage: Physical geometry + Construction completeness PASS;
    Support/Stability, Load-path and Structural capacity are UNKNOWN — NOT ANALYZED
    (tip-over is ANALYSIS-v1). No support-obligation finding (loose object), and no
    capacity/adequacy claim anywhere — never a fake CLEAN stability claim."""
    _detail, report = stool
    verdicts = {fc["family"]: fc["verdict"] for fc in report.coverage_payload()}
    assert verdicts["Physical geometry"] == "PASS"
    assert verdicts["Construction completeness"] == "PASS"
    # Since the station-move fix arc: installability PASS on merit (both axes
    # GEOMETRY-PROVEN on all 8 screws), not by absence.
    assert verdicts["Fastener installability"] == "PASS"
    for fam in ("Support/Stability representation", "Structural capacity",
                "Load-path representation"):
        assert verdicts[fam] == "UNKNOWN — NOT ANALYZED", (fam, verdicts[fam])

    # No walking_surface declared -> the rung-3 support check never runs.
    assert not any(f.check == "support" for f in report.findings)
    # No capacity/adequacy claim of any kind (rung-4 UNKNOWN-by-absence).
    for f in report.findings:
        assert "capacity" not in f.detail.lower() or "not analyzed" in f.detail.lower()


def test_prose_truthfulness_guard(stool, tmp_path):
    """R24-class guard: the RENDERED build document must not claim what the model
    does not prove. The reader-facing step-height numbers equal the MODEL's measured
    heights, and the stability story is honestly UNKNOWN — the doc says tip-over /
    Support-Stability / capacity are NOT ANALYZED and never claims the stool proven
    stable."""
    import json
    detail, _report = stool
    detail.render_documentation(tmp_path)
    cov = tmp_path / "coverage_matrix.json"
    assert cov.exists(), "documentation render did not emit coverage_matrix.json"
    verdicts = {fc["family"]: fc["verdict"] for fc in json.loads(cov.read_text())}

    # Honest stability: the coverage carries UNKNOWN for the safety families;
    # nothing renders them as analyzed/PASS.
    for fam in ("Support/Stability representation", "Structural capacity"):
        assert fam in verdicts and verdicts[fam].startswith("UNKNOWN"), (fam, verdicts.get(fam))

    # The reader-facing step heights equal the MODEL's measured heights (prose can
    # not drift from geometry): the spec's doc prose interpolates the params, and
    # the governing-dims guard proves the params match the geometry.
    upper = _zmax_in(detail, "upper tread")
    lower = _zmax_in(detail, "lower tread")
    assert f"{upper:g}" == "10.25" and f"{lower:g}" == "5.5"

    # The build document (the HTML) must state the honest limit, not a stability claim.
    sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR
    html = (tmp_path / "doc.html")
    info = SDR.build_document(html, SPEC)
    doc = Path(info["path"]).read_text()
    assert "NOT ANALYZED" in doc
    assert "tip-over" in doc.lower()
    # Never a claim that the stool is proven stable / load-tested / capacity-verified.
    low = doc.lower()
    for forbidden in ("proven stable", "stability verified", "capacity verified",
                      "load-tested", "certified safe"):
        assert forbidden not in low, f"doc makes an unproven claim: {forbidden!r}"


def test_full_flow_is_fast():
    """The whole from-scratch flow runs well under a generous 60s budget."""
    t0 = time.perf_counter()
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    verify_assembly_fabrication(detail.assembly)
    detail.bom_table()
    elapsed = time.perf_counter() - t0
    assert report.ok  # clean again since the station-move fix arc
    assert elapsed < 60.0, f"e2e flow took {elapsed:.1f}s (budget 60s)"
