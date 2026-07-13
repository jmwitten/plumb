"""End-to-end test for the sit-and-reach test box (task SITREACH).

Mirrors the stool e2e probe (compile -> validate -> fabrication records -> fold
invariant -> BOM -> honest verdicts) with this detail's own two guards:

  * the GOVERNING-DIMS GUARD (the protocol contract): reach surface 12in, foot-line
    offset EXACTLY 23cm (9.055in of top-plate overhang), box depth/width 12in are
    PINNED; if detailing ever pressures one, this test goes RED and the question
    returns to the owner (never silent drift). Measured off the COMPILED model.
  * the PROSE-TRUTHFULNESS GUARD (R24 class): the rendered build document must not
    claim what the model does not prove — slide/tip, Support/Stability and
    Structural capacity read UNKNOWN — NOT ANALYZED (ANALYSIS-v1), and the
    reader-facing protocol numbers equal the MODEL's measured geometry.

Plus unit probes for the TWO NEW VOCABULARY WORDS this build added (route-by-class,
vocabulary-gap directive):

  * ``plywood_panel`` — sheet-goods component; fold invariant; honest ripped-strip
    stock disclosure; BOM label carries the width (a panel is not cuttable from a
    length alone).
  * ``butt_screwed`` — the box-corner connection; claims pull_out + shear ONLY
    (edge-grain named), NO downward_load, and emits NO bears_on edge (a butt screw
    holds parts together; it is not a gravity seat).
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

_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "details" / "sit_reach_box.spec.yaml"
_IN = 25.4

#: GOVERNING dimensions — the protocol contract (President's Challenge /
#: FitnessGram). The guard asserts them off the COMPILED MODEL, so a param edit
#: that fails to move the geometry is also caught.
GOV_TOP_SURFACE_IN = 12.0
GOV_FOOT_LINE_CM = 23.0
GOV_BOX_DEPTH_IN = 12.0
GOV_BOX_WIDTH_IN = 12.0

#: Fabricated members and the steps each carries: five panels, each a plain
#: crosscut from its ripped strip (no ease/holes authored — square edges, and the
#: screws drill their own way). Screws and the existing floor carry no record.
_EXPECTED_STEPS = {
    "side panel +X": ["crosscut"],
    "side panel -X": ["crosscut"],
    "front (foot) panel": ["crosscut"],
    "back panel": ["crosscut"],
    "top plate (reach surface)": ["crosscut"],
}


@pytest.fixture(scope="module")
def box():
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def _by_name(detail):
    return {p.name: p for p in detail.assembly.parts}


def _bb(detail, name):
    return _by_name(detail)[name].world_solid().val().BoundingBox()


def test_compiles_and_validates_clean(box):
    """compile -> validate runs the full sweep with an HONEST verdict: no failures
    and no blocking UNKNOWNs. Not a forced CLEAN — the honest verdict is asserted."""
    _detail, report = box
    assert report.failures == [], "\n".join(str(f) for f in report.failures)
    assert report.blocking == [], "\n".join(str(f) for f in report.blocking)
    assert report.ok


def test_every_panel_has_expected_fabrication_record(box):
    """Each panel carries a ProcessRecord of exactly the ops a builder performs;
    the screws and the existing floor carry none (bought / existing)."""
    detail, _report = box
    by_name = _by_name(detail)
    steps_by_name = {}
    for name, part in by_name.items():
        rec = _fabrication_record_of(part.component)
        if rec is not None:
            steps_by_name[name] = [s.kind for s in rec.steps]
    assert steps_by_name == _EXPECTED_STEPS
    for name in ("top screw +X 0", "butt screw -X back 1", "floor"):
        assert _fabrication_record_of(by_name[name].component) is None


def test_fabrication_fold_invariant_holds(box):
    """Every fabricated part's installed solid is byte-identical to fold(stock,
    steps), with no material-removing feature lacking a declared step."""
    detail, _report = box
    verify_assembly_fabrication(detail.assembly)  # raises on any drift


def test_panel_stock_is_disclosed_ripped_strip(box):
    """The honest sheet-goods interim: each panel's stock profile SAYS it is a
    ripped ply strip of the panel's width (there is no rip/sheet vocabulary yet —
    a recorded work order, not a silent claim of purchasable stick stock)."""
    detail, _report = box
    for name in _EXPECTED_STEPS:
        rec = _fabrication_record_of(_by_name(detail)[name].component)
        assert "ply strip" in rec.stock.profile, (name, rec.stock.profile)
        assert rec.stock.form == "linear_stick"


def test_bom_rows_and_cut_lengths(box):
    """BOM derived from the fabrication records: three panel rows (2x sides 12in
    on an 11.25 strip, 2x front/back 10.5in on an 11.25 strip, 1x top 21.06in on a
    12 strip — the label carries the width) and sixteen screws in one length row.
    The floor is EXISTING, never billed as purchased stock."""
    detail, _report = box
    bom = detail.bom_table()

    def in_len(r):
        return round(r["length_mm"] / _IN, 2)

    panel_rows = [r for r in bom if "plywood panel" in r["item"]]
    assert len(panel_rows) == 3
    for r in panel_rows:
        assert "wide" in r["item"], r["item"]  # width rides in the label
    by_len = {in_len(r): r["qty"] for r in panel_rows}
    assert by_len == {12.0: 2, 10.5: 2, 21.06: 1}

    screw_rows = [r for r in bom if "Screw" in r["item"]]
    assert sum(r["qty"] for r in screw_rows) == 16

    assert any("existing" in r["item"].lower() for r in bom)
    floor_ids = {"boulder-0"}
    assert not any(floor_ids & set(r["ids"]) for r in bom
                   if "plywood" in r["item"])


def test_governing_dims_guard(box):
    """THE GUARD (protocol contract). Measured off the compiled model: the reach
    surface is 12in up, the top plate's sitter edge is EXACTLY 23cm forward of the
    foot face (the plane Y=0 the soles press), and the box body is 12x12in. If
    detailing ever pressures one, this goes RED — never silent drift."""
    detail, _report = box
    top = _bb(detail, "top plate (reach surface)")
    front = _bb(detail, "front (foot) panel")

    assert top.zmax / _IN == pytest.approx(GOV_TOP_SURFACE_IN, abs=0.02), (
        f"GOVERNING reach surface drifted to {top.zmax / _IN:.3f}in "
        f"(pinned {GOV_TOP_SURFACE_IN}in) — return to the owner")

    # The foot line: front panel outer face at Y=0; top plate sitter edge at
    # -23cm. Assert BOTH halves so the offset can't drift by either face moving.
    assert front.ymin / 10.0 == pytest.approx(0.0, abs=0.05), (
        f"foot face drifted off Y=0 (ymin {front.ymin:.2f}mm) — return to the owner")
    assert -top.ymin / 10.0 == pytest.approx(GOV_FOOT_LINE_CM, abs=0.05), (
        f"GOVERNING foot-line offset drifted to {-top.ymin / 10.0:.2f}cm "
        f"(pinned {GOV_FOOT_LINE_CM}cm) — return to the owner")

    side = _bb(detail, "side panel +X")
    assert (side.ymax - side.ymin) / _IN == pytest.approx(GOV_BOX_DEPTH_IN, abs=0.02)
    assert (top.xmax - top.xmin) / _IN == pytest.approx(GOV_BOX_WIDTH_IN, abs=0.02)


def test_honest_verdicts_analysis_v1(box):
    """The honest coverage: Physical geometry + Construction completeness PASS;
    Support/Stability, Load-path and Structural capacity are UNKNOWN — NOT
    ANALYZED (slide/tip under test loads is ANALYSIS-v1). No support-obligation
    finding (loose object), and no capacity/adequacy claim anywhere."""
    _detail, report = box
    verdicts = {fc["family"]: fc["verdict"] for fc in report.coverage_payload()}
    assert verdicts["Physical geometry"] == "PASS"
    assert verdicts["Construction completeness"] == "PASS"
    for fam in ("Support/Stability representation", "Structural capacity",
                "Load-path representation"):
        assert verdicts[fam] == "UNKNOWN — NOT ANALYZED", (fam, verdicts[fam])

    assert not any(f.check == "support" for f in report.findings)
    for f in report.findings:
        assert "capacity" not in f.detail.lower() or "not analyzed" in f.detail.lower()


def test_prose_truthfulness_guard(box, tmp_path):
    """R24-class guard: the RENDERED build document must not claim what the model
    does not prove. The reader-facing protocol numbers equal the MODEL's measured
    geometry, and the stability story is honestly UNKNOWN."""
    import json
    detail, _report = box
    detail.render_documentation(tmp_path)
    cov = tmp_path / "coverage_matrix.json"
    assert cov.exists(), "documentation render did not emit coverage_matrix.json"
    verdicts = {fc["family"]: fc["verdict"] for fc in json.loads(cov.read_text())}
    for fam in ("Support/Stability representation", "Structural capacity"):
        assert fam in verdicts and verdicts[fam].startswith("UNKNOWN"), (fam, verdicts.get(fam))

    # The protocol numbers the reader sees equal the model's measured geometry.
    top = _bb(detail, "top plate (reach surface)")
    assert f"{top.zmax / _IN:g}" == "12"
    assert round(-top.ymin / 10.0, 2) == 23.0

    # The build document (the HTML) states the honest limit, not a stability claim.
    sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR
    html = (tmp_path / "doc.html")
    info = SDR.build_document(html, SPEC)
    doc = Path(info["path"]).read_text()
    assert "NOT ANALYZED" in doc
    assert "23cm" in doc or "23 cm" in doc
    low = doc.lower()
    for forbidden in ("proven stable", "stability verified", "capacity verified",
                      "load-tested", "certified safe", "will not tip",
                      "will not slide"):
        assert forbidden not in low, f"doc makes an unproven claim: {forbidden!r}"


# --------------------------------------------------------------------------- #
# New-vocabulary unit probes (the two words this build added).
# --------------------------------------------------------------------------- #

def test_plywood_panel_component_contract():
    """plywood_panel: fold-derived geometry matches params; BOM label carries the
    width; degenerate and un-nestable panels are flagged by check()."""
    from detailgen.components import PlywoodPanel
    from detailgen.core.units import IN

    p = PlywoodPanel(length=21.06 * IN, width=12 * IN, thickness=0.75 * IN)
    bb = p.solid.val().BoundingBox()
    assert (round(bb.xlen / IN, 2), round(bb.ylen / IN, 2),
            round(bb.zlen / IN, 2)) == (21.06, 12.0, 0.75)
    assert p.bom_length_mm() == pytest.approx(21.06 * IN)
    assert "wide" in p.bom_label()
    assert p.check() == []

    assert PlywoodPanel(length=0, width=12 * IN, thickness=0.75 * IN).check()
    too_big = PlywoodPanel(length=100 * IN, width=50 * IN, thickness=0.75 * IN)
    assert any("4x8" in prob for prob in too_big.check())


def test_butt_screwed_claims_and_edges(box):
    """butt_screwed: claims pull_out + shear ONLY (no downward_load — no gravity
    seat smuggled through the fastener), and emits NO bears_on edge; the joint's
    load-path fact is fastened_by. The compiled box exercises four such joints."""
    from detailgen.assemblies.connection import ButtScrewed

    claimed = {(tc.load_class, tc.transfers) for tc in ButtScrewed.transfer_claims}
    assert claimed == {("pull_out", True), ("shear", True)}

    detail, _report = box
    butts = [c for c in detail.connections() if c.kind.label == "butt_screwed"]
    assert len(butts) == 4  # the four box corners
    for c in butts:
        kinds = {e.kind for e in c.kind.edges(c)}
        assert "bears_on" not in kinds
        assert "fastened_by" in kinds and "installed_before" in kinds


def test_full_flow_is_fast():
    """The whole from-scratch flow runs well under a generous 60s budget."""
    t0 = time.perf_counter()
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    verify_assembly_fabrication(detail.assembly)
    detail.bom_table()
    elapsed = time.perf_counter() - t0
    assert report.ok
    assert elapsed < 60.0, f"e2e flow took {elapsed:.1f}s (budget 60s)"
