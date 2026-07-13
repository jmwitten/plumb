"""End-to-end test for the 3-foot backyard trebuchet (task TREB).

Mirrors the stool/sitreach e2e probes (compile -> validate -> fabrication
records -> fold invariant -> BOM -> honest verdicts) with this detail's own
guards:

  * the GOVERNING-DIMS GUARD (the owner contract): axle centerline 32in, arm
    48in at EXACTLY 4:1 (38.4in throw / 9.6in counterweight), and the 14in
    counterweight lane are PINNED; if detailing ever pressures one, this test
    goes RED and the question returns to the owner. Measured off the COMPILED
    model with LITERAL expecteds (sitreach MINOR-1 lesson).
  * the HANGING-POSE GUARD: the modeled pose claims the arm HANGS on the rod —
    centerline exactly one radial bore clearance (1/16in) below the axle line.
    A concentric-faked arm goes RED here (the render cannot resolve the offset;
    the model must).
  * the PROSE-TRUTHFULNESS GUARD (R24 class): the rendered build document must
    not claim what the model does not prove — kinematics, stability, capacity
    and firing dynamics read UNKNOWN / NOT ANALYZED, and the rigging section is
    present (DS1: the unmodeled half ships as first-class prose).

This detail adds NO new vocabulary; its first-class residual is the PIVOT
(no pivot/journal ConnectionType — declared through bonds/contacts/
expected_overlaps/through-hole, the trolley-launch precedent), so the pivot's
declarations are probed here as the honest shape they claim to be.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec_file
from detailgen.core.process_graph import (
    verify_assembly_fabrication,
    _fabrication_record_of,
)

_REPO = Path(__file__).resolve().parents[1]
SPEC = _REPO / "details" / "trebuchet.spec.yaml"
_IN = 25.4

#: GOVERNING dimensions — the owner contract (~3ft scale, one-day, dual
#: payload). LITERAL here, never read back from the spec's params.
GOV_AXLE_H_IN = 32.0
GOV_ARM_LEN_IN = 48.0
GOV_ARM_RATIO = 4.0
GOV_CLEAR_W_IN = 14.0
#: The declared hanging pose: bore 3/4 over rod 5/8 -> the arm centerline sits
#: one radial clearance below the axle line.
HANG_DROP_IN = (0.75 - 0.625) / 2

#: Fabricated members and the steps each carries. The three deck boards each
#: carry their ONE designed bore (the single-feature-per-board vocabulary
#: limit this build discloses); everything else is a plain crosscut. Screws,
#: rod, nuts, washers and the existing ground carry no record (bought).
_EXPECTED_STEPS = {
    "base rail +X": ["crosscut"],
    "base rail -X": ["crosscut"],
    "cross member front": ["crosscut"],
    "cross member mid": ["crosscut"],
    "cross member rear": ["crosscut"],
    "upright +X": ["crosscut", "ease", "bore"],
    "upright -X": ["crosscut", "ease", "bore"],
    "gusset knee +X": ["crosscut"],
    "gusset knee -X": ["crosscut"],
    "runway plate": ["crosscut"],
    "throwing arm": ["crosscut", "ease", "bore"],
}


@pytest.fixture(scope="module")
def treb():
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def _by_name(detail):
    return {p.name: p for p in detail.assembly.parts}


def _bb(detail, name):
    return _by_name(detail)[name].world_solid().val().BoundingBox()


def test_compiles_and_validates_with_honest_embedment_failures(treb):
    """HONEST NEW STATE since task INSTALL v1 (the trebuchet postdates the
    Phase-0 sweep and was never swept until the axis checks ran): 18 screws
    bite less than their contracts' assumption-grade half-length embedment
    minimum — the 12 base butt screws (2.5in through the 1.5in rail = 1.0in
    into the cross ends < 1.25in) and the 6 upright lap screws (2.25in
    through the 1.5in rail = 0.75in into the 1in upright < 1.12in). Access
    is clean on all 30 corridors (heads on open faces). The doc was
    delivered before these checks existed; the FAILs are pinned as the truth
    (no silent reclassification) and flagged in the INSTALL-AXES task
    report — the fix arc (longer screws or an authored embedment override
    with a WHY) is downstream."""
    _detail, report = treb
    from collections import Counter
    assert Counter(f.check for f in report.failures) == Counter(
        {"install_termination": 18})
    for f in report.failures:
        assert "embedment below the declared minimum" in f.detail
        assert "[assumption]" in f.detail
    assert report.blocking == report.failures  # no UNKNOWNs
    assert not report.ok


def test_every_member_has_expected_fabrication_record(treb):
    """Each wood member carries a ProcessRecord of exactly the ops a builder
    performs — the three deck boards each carry their ONE bore; the hardware
    and the existing ground carry none."""
    detail, _report = treb
    by_name = _by_name(detail)
    steps_by_name = {}
    for name, part in by_name.items():
        rec = _fabrication_record_of(part.component)
        if rec is not None:
            steps_by_name[name] = [s.kind for s in rec.steps]
    assert steps_by_name == _EXPECTED_STEPS
    for name in ("axle rod", "axle nut +X outer", "arm washer -X",
                 "butt screw +X front 0", "ground"):
        assert _fabrication_record_of(by_name[name].component) is None


def test_fabrication_fold_invariant_holds(treb):
    """Every fabricated part's installed solid is byte-identical to fold(stock,
    steps), with no material-removing feature lacking a declared step — the
    three axle bores are declared FEATURE cuts, not silent geometry."""
    detail, _report = treb
    verify_assembly_fabrication(detail.assembly)  # raises on any drift


def test_bom_rows(treb):
    """BOM derived from the fabrication records: 2x4 rows (2x 48in rails, 3x
    16in crosses), 5/4x6 rows (2x 35in uprights, 1x 48in arm), ply rows nesting
    on ONE 12in-wide strip story (2x 24in knees, 1x 44.5in runway), the rod,
    8 nuts, 6 washers, and 30 screws across three length rows. The ground is
    EXISTING, never billed."""
    detail, _report = treb
    bom = detail.bom_table()

    def in_len(r):
        return round(r["length_mm"] / _IN, 2) if r["length_mm"] else None

    lum = {(in_len(r)): r["qty"] for r in bom if "2x4" in r["item"]}
    assert lum == {48.0: 2, 16.0: 3}

    deck = {(in_len(r)): r["qty"] for r in bom if "5/4x6" in r["item"]}
    assert deck == {35.0: 2, 48.0: 1}

    ply_rows = [r for r in bom if "plywood panel" in r["item"]]
    assert len(ply_rows) == 2
    for r in ply_rows:
        assert '12.00" wide' in r["item"], r["item"]  # one-strip nesting story
    assert {in_len(r): r["qty"] for r in ply_rows} == {24.0: 2, 44.5: 1}

    assert sum(r["qty"] for r in bom if "Hex nut" in r["item"]) == 8
    assert sum(r["qty"] for r in bom if "Fender washer" in r["item"]) == 6
    assert sum(r["qty"] for r in bom if "rod" in r["item"].lower()) == 1
    assert sum(r["qty"] for r in bom if "Screw" in r["item"]) == 30

    assert any("existing" in r["item"].lower() for r in bom)


def test_governing_dims_guard(treb):
    """THE GUARD (owner contract). Measured off the compiled model with literal
    expecteds: axle at 32in, the arm split exactly 4:1 on a 48in stick, the
    counterweight lane exactly 14in clear. Drift goes RED — never silent."""
    detail, _report = treb
    rod = _bb(detail, "axle rod")
    arm = _bb(detail, "throwing arm")
    up_p = _bb(detail, "upright +X")
    up_m = _bb(detail, "upright -X")

    assert (rod.zmin + rod.zmax) / 2 / _IN == pytest.approx(GOV_AXLE_H_IN, abs=0.02), (
        f"GOVERNING axle height drifted to {(rod.zmin + rod.zmax) / 2 / _IN:.3f}in "
        f"(pinned {GOV_AXLE_H_IN}in) — return to the owner")

    short = GOV_ARM_LEN_IN / (GOV_ARM_RATIO + 1)          # 9.6
    assert arm.ymax / _IN == pytest.approx(short, abs=0.02), (
        f"GOVERNING counterweight arm drifted to {arm.ymax / _IN:.3f}in "
        f"(pinned {short}in) — return to the owner")
    assert -arm.ymin / _IN == pytest.approx(GOV_ARM_LEN_IN - short, abs=0.02), (
        f"GOVERNING throw arm drifted to {-arm.ymin / _IN:.3f}in "
        f"(pinned {GOV_ARM_LEN_IN - short}in) — return to the owner")

    assert up_p.xmin / _IN == pytest.approx(GOV_CLEAR_W_IN / 2, abs=0.02)
    assert up_m.xmax / _IN == pytest.approx(-GOV_CLEAR_W_IN / 2, abs=0.02), (
        "GOVERNING counterweight lane drifted — return to the owner")


def test_hanging_pose_guard(treb):
    """The declared pose is REAL in the geometry: the arm's centerline sits
    exactly one radial clearance below the axle line (bore tangent on the
    rod's top), not concentric-faked."""
    detail, _report = treb
    rod = _bb(detail, "axle rod")
    arm = _bb(detail, "throwing arm")
    rod_ctr = (rod.zmin + rod.zmax) / 2 / _IN
    arm_ctr = (arm.zmin + arm.zmax) / 2 / _IN
    assert rod_ctr - arm_ctr == pytest.approx(HANG_DROP_IN, abs=0.005), (
        f"hanging pose drifted: arm centerline {arm_ctr:.4f}in vs axle "
        f"{rod_ctr:.4f}in (declared drop {HANG_DROP_IN}in)")


def test_pivot_declarations_are_the_honest_shape(treb):
    """The pivot is NOT a Connection (no pivot/journal word — disclosed work
    order): no declared connection touches the arm or the rod; the arm's
    relations ride the escape hatches (bond arm<->rod + contact + through-hole),
    exactly the trolley-launch precedent."""
    detail, _report = treb
    doc = detail.doc
    for conn in doc.connections:
        for pid in conn.parts:
            assert pid not in ("arm", "axle_rod"), (
                f"a Connection claims the pivot ({conn.label}) — the pivot has "
                "no honest ConnectionType; it must stay in the escape hatches")
    bonds = {(b.a, b.b) for b in doc.validation.bonds}
    assert ("arm", "axle_rod") in bonds
    contacts = {(c.a, c.b) for c in doc.validation.contacts}
    assert ("arm", "axle_rod") in contacts
    th = doc.validation.through_holes
    assert len(th) == 1 and th[0].part == "axle_rod"
    assert set(th[0].passes_through) == {"upright_pos", "arm", "upright_neg"}


def test_honest_verdicts_analysis_v1(treb):
    """The honest coverage: Physical geometry + Construction completeness PASS;
    Support/Stability, Load-path and Structural capacity are UNKNOWN — NOT
    ANALYZED (firing dynamics are ANALYSIS-v1's first MECHANISM). No
    support-obligation finding (loose object), no capacity claim anywhere."""
    _detail, report = treb
    verdicts = {fc["family"]: fc["verdict"] for fc in report.coverage_payload()}
    assert verdicts["Physical geometry"] == "PASS"
    assert verdicts["Construction completeness"] == "PASS"
    for fam in ("Support/Stability representation", "Structural capacity",
                "Load-path representation"):
        assert verdicts[fam] == "UNKNOWN — NOT ANALYZED", (fam, verdicts[fam])

    assert not any(f.check == "support" for f in report.findings)
    for f in report.findings:
        assert "capacity" not in f.detail.lower() or "not analyzed" in f.detail.lower()


def test_prose_truthfulness_guard(treb, tmp_path):
    """R24-class guard: the RENDERED build document must not claim what the
    model does not prove, and MUST carry the rigging section (DS1 — the
    unmodeled half ships as first-class prose) and the safety block."""
    import json
    detail, _report = treb
    detail.render_documentation(tmp_path)
    cov = tmp_path / "coverage_matrix.json"
    assert cov.exists(), "documentation render did not emit coverage_matrix.json"
    verdicts = {fc["family"]: fc["verdict"] for fc in json.loads(cov.read_text())}
    for fam in ("Support/Stability representation", "Structural capacity"):
        assert fam in verdicts and verdicts[fam].startswith("UNKNOWN"), (fam, verdicts.get(fam))

    sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR
    html = tmp_path / "doc.html"
    info = SDR.build_document(html, SPEC)
    doc = Path(info["path"]).read_text()
    assert "NOT ANALYZED" in doc
    assert "Rigging" in doc, "the rigging section (DS1) is missing"
    assert "safety" in doc.lower(), "the operating-safety block is missing"
    low = doc.lower()
    for forbidden in ("proven stable", "stability verified", "capacity verified",
                      "load-tested", "certified safe", "will not tip",
                      "will not slide", "kinematics verified", "range verified",
                      "guaranteed range"):
        assert forbidden not in low, f"doc makes an unproven claim: {forbidden!r}"

    # DRAWDIM guard (naive-builder review V5): the numbers a builder tapes
    # must ship ON PAPER — the cut plan carries the bore STATIONS (the
    # station-less arm bore was the review's top wrong-build risk), and the
    # three derived sheets (dimensioned elevation, pivot stack, operating
    # diagram) are in the panel.
    assert "from one end" in doc, "cut plan lost its bore stations (V5)"
    assert 'center 38.4&quot; from one end' in doc or \
        'center 38.4" from one end' in doc, "arm-bore station missing (V5)"
    for sheet in ("the build sheet", "operating diagram", "pivot stack"):
        assert sheet in low, f"derived sheet missing from the doc: {sheet}"


def test_install_disclosures_reach_the_per_detail_reader_surfaces(treb, tmp_path):
    """Owner guardrail #7's doc half (honesty review F2): a reader of THIS
    blocked doc must see, on paper, WHY it is blocked — the resolved install
    contracts with per-field provenance and the full text of every open
    axis verdict (measured bites, the [assumption] minimum, the tool
    envelope). Both per-detail surfaces carry it: the lifecycle
    validation_report.md and the single-detail HTML."""
    detail, _report = treb
    out = detail.render_documentation(tmp_path / "doc")
    md = (out / "validation_report.md").read_text()
    assert "## Fastener installation — contracts and axis verdicts" in md
    assert "method=driven_straight [connectiontype_default]" in md
    assert "embedment=1.25\" min bite [assumption]" in md
    assert ("assumption: embedment default = half the fastener's under-head "
            "length" in md)
    assert "### Open installability verdicts (blocking)" in md
    assert md.count("embedment below the declared minimum") == 18
    assert "1.00\" bite into cross member front < 1.25\" minimum [assumption]" in md
    assert "6.00\" x 1.00\" dia tool envelope" in md
    # task CPGCORE: the epistemic-contract table (owner amendment 2) sits
    # near the top of the disclosure section, and the derived Build
    # Sequence section reaches the same lifecycle surface — one reader
    # step per connection install unit (no stages authored here), nothing
    # hand-typed, and no SEQUENCE-PROVEN claim anywhere.
    assert "### Epistemic contract — where each order fact comes from" in md
    assert "none authored by this detail" in md
    assert "## Build sequence (derived)" in md
    assert "no step title, order, or sentence here is hand-typed" in md
    assert md.count("**install ") == 13   # the trebuchet's 13 install units
    assert "SEQUENCE-PROVEN" not in md.replace(
        "SEQUENCE-PROVEN — a rung RESERVED", "")
    # Idempotence (review-cpgcore F-4): re-documenting into the same
    # out_dir must not stack a second Build Sequence section.
    detail._write_build_sequence(out)
    detail._write_build_sequence(out)
    md2 = (out / "validation_report.md").read_text()
    assert md2.count("## Build sequence (derived)") == 1
    assert md2.count("**install ") == 13

    import sys
    from pathlib import Path as _P
    if str(_REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR
    html_path = tmp_path / "doc.html"
    SDR.build_document(html_path, SPEC)
    doc = _P(html_path).read_text()
    assert "Fastener installation &mdash; contracts and axis verdicts" in doc
    assert "install-disclosure" in doc
    assert "[assumption]" in doc
    assert doc.count("embedment below the declared minimum") == 18
    # task CPGCORE: the SAME epistemic table + Build Sequence content model
    # reaches the HTML build document (two views, one derivation).
    assert "Epistemic contract" in doc
    assert "Build sequence (derived)" in doc
    assert "build-sequence" in doc
