"""End-to-end test for the sit-and-reach box, 2x4 FRAME variant (task SITFRAME).

Mirrors the ply-box e2e probe with the frame's own guards:

  * the GOVERNING-DIMS GUARD (the protocol contract — IDENTICAL numbers to the
    ply variant): reach surface 12in, foot line EXACTLY 23cm, body 12x12in,
    measured off the COMPILED model. Plus the frame's own foot-plane facts: BOTH
    front legs' faces AND the rails' front end grain coplanar at Y=0.
  * the PROSE-TRUTHFULNESS GUARD: the rendered doc claims no stability/racking/
    capacity result (all UNKNOWN — NOT ANALYZED) and its protocol numbers equal
    the model's.
  * the ONE-STUD GUARD: the whole frame cuts from a single 8-ft 2x4 — the
    variant's reason to exist. Asserted against the fabrication records (total
    crosscut length + kerf allowance <= 96in), so a detailing change that
    silently outgrows the stud goes RED.

No new vocabulary in this variant: rail_cap_screwed (genuinely end grain here)
and cleat_screwed (long grain both sides: rail face to leg narrow edge) carry
every joint; the top plate is
the ply box's plywood_panel word.
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
SPEC = _REPO / "details" / "sit_reach_frame.spec.yaml"
_IN = 25.4

GOV_TOP_SURFACE_IN = 12.0
GOV_FOOT_LINE_CM = 23.0
GOV_BOX_DEPTH_IN = 12.0
GOV_BOX_WIDTH_IN = 12.0

#: The one-stud contract: 4 legs + 2 rails from one 8-ft 2x4, with a real kerf
#: + end-trim allowance (1/8in kerf x 6 cuts + 1in trim, generous).
STUD_LENGTH_IN = 96.0
KERF_ALLOWANCE_IN = 2.0

_EXPECTED_STEPS = {
    "front leg +X (footplate)": ["crosscut"],
    "front leg -X (footplate)": ["crosscut"],
    "back leg +X": ["crosscut"],
    "back leg -X": ["crosscut"],
    "side rail +X": ["crosscut"],
    "side rail -X": ["crosscut"],
    "top plate (reach surface)": ["crosscut"],
}


@pytest.fixture(scope="module")
def frame():
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    return detail, report


def _by_name(detail):
    return {p.name: p for p in detail.assembly.parts}


def _bb(detail, name):
    return _by_name(detail)[name].world_solid().val().BoundingBox()


def test_compiles_and_validates_with_two_bench_side_frames(frame):
    """The eight symmetric rail corridors clear because each three-member
    side is authored as its own bench frame. The opposite side is absent by
    unit membership, an ordinary declared-order clear rather than the
    caddy's stronger connection-free DECLARED TRUST case."""
    _detail, report = frame
    from collections import Counter
    assert report.failures == [], "\n".join(str(f) for f in report.failures)
    access = [f for f in report.findings
              if f.check == "install_access" and "rail screw" in f.subject]
    assert Counter(f.verdict for f in access) == Counter({"PASS": 8})
    assert all("absent from bench frame" in f.detail
               and "[staging]" in f.detail
               and f.declared_order and not f.declared_trust
               for f in access)
    assert report.blocking == [] and report.ok


def test_every_member_has_expected_fabrication_record(frame):
    detail, _report = frame
    steps_by_name = {}
    for name, part in _by_name(detail).items():
        rec = _fabrication_record_of(part.component)
        if rec is not None:
            steps_by_name[name] = [s.kind for s in rec.steps]
    assert steps_by_name == _EXPECTED_STEPS
    for name in ("cap screw front +X", "rail screw back -X lo", "floor"):
        assert _fabrication_record_of(_by_name(detail)[name].component) is None


def test_build_sequence_benches_both_sides_then_sets_them_before_caps(frame):
    from detailgen.validation.build_sequence import build_sequence_model

    detail, _report = frame
    steps, loose = build_sequence_model(detail)
    titles = [step["title"] for step in steps]
    assert titles[:4] == [
        "bench side +X", "bench side -X",
        "set side +X in place", "set side -X in place"]
    first_cap = min(i for i, title in enumerate(titles)
                    if title.startswith("install top plate ->"))
    assert first_cap > 3
    assert steps[0]["why"].startswith("Lay the +X front leg")
    assert steps[1]["why"].startswith("Lay the -X front leg")
    assert steps[0]["claim"] == steps[1]["claim"] == "staging"
    assert "floor" not in loose


def test_fabrication_fold_invariant_holds(frame):
    detail, _report = frame
    verify_assembly_fabrication(detail.assembly)


def test_one_stud_guard(frame):
    """THE VARIANT'S REASON TO EXIST: every 2x4 stick cuts from ONE 8-ft stud.
    Read the crosscut lengths from the fabrication records (the same records
    the geometry folds from); if detailing ever outgrows the stud, this goes
    RED and the buy story returns to the owner."""
    detail, _report = frame
    stick_in = []
    for name, part in _by_name(detail).items():
        rec = _fabrication_record_of(part.component)
        if rec is not None and "2x4" in rec.stock.profile:
            stick_in.append(rec.crosscut_length() / _IN)
    assert len(stick_in) == 6  # 4 legs + 2 rails
    total = sum(stick_in) + KERF_ALLOWANCE_IN
    assert total <= STUD_LENGTH_IN, (
        f"frame needs {total:.1f}in of 2x4 (with kerf allowance) — "
        f"outgrew the one 8-ft stud contract; return to the owner")


def test_bom_rows_and_cut_lengths(frame):
    """BOM from the fabrication records: one 2x4 row of four 11.25in legs, one
    of two 12in rails, ONE ply panel row (the only plywood — the constraint),
    twelve screws. The floor is EXISTING, never billed."""
    detail, _report = frame
    bom = detail.bom_table()

    def in_len(r):
        return round(r["length_mm"] / _IN, 2)

    stud_rows = [r for r in bom if r["item"] == "2x4 lumber"]
    assert {in_len(r): r["qty"] for r in stud_rows} == {11.25: 4, 12.0: 2}

    panel_rows = [r for r in bom if "plywood panel" in r["item"]]
    assert len(panel_rows) == 1 and panel_rows[0]["qty"] == 1
    assert in_len(panel_rows[0]) == 21.06
    assert "wide" in panel_rows[0]["item"]

    screw_rows = [r for r in bom if "Screw" in r["item"]]
    assert sum(r["qty"] for r in screw_rows) == 12

    assert any("existing" in r["item"].lower() for r in bom)


def test_governing_dims_guard(frame):
    """THE GUARD — identical protocol numbers to the ply variant, plus the
    frame's own foot-plane coplanarity (both footplate legs AND the rail end
    grain land at Y=0)."""
    detail, _report = frame
    top = _bb(detail, "top plate (reach surface)")

    assert top.zmax / _IN == pytest.approx(GOV_TOP_SURFACE_IN, abs=0.02), (
        f"GOVERNING reach surface drifted to {top.zmax / _IN:.3f}in — return to the owner")
    assert -top.ymin / 10.0 == pytest.approx(GOV_FOOT_LINE_CM, abs=0.05), (
        f"GOVERNING foot-line offset drifted to {-top.ymin / 10.0:.2f}cm — return to the owner")
    assert (top.xmax - top.xmin) / _IN == pytest.approx(GOV_BOX_WIDTH_IN, abs=0.02)

    # The foot plane: both footplate faces AND the rail front end grain at Y=0.
    for name in ("front leg +X (footplate)", "front leg -X (footplate)",
                 "side rail +X", "side rail -X"):
        ymin = _bb(detail, name).ymin / 10.0
        assert ymin == pytest.approx(0.0, abs=0.05), (
            f"{name} drifted off the foot plane (ymin {ymin:.2f}cm) — return to the owner")

    back = _bb(detail, "back leg +X")
    assert back.ymax / _IN == pytest.approx(GOV_BOX_DEPTH_IN, abs=0.02)

    # Footplates run full height: no toe-tip gap below the plate underside.
    leg = _bb(detail, "front leg +X (footplate)")
    assert leg.zmax / _IN == pytest.approx(GOV_TOP_SURFACE_IN - 0.75, abs=0.02)
    assert leg.zmin / _IN == pytest.approx(0.0, abs=0.02)


def test_honest_verdicts_analysis_v1(frame):
    _detail, report = frame
    verdicts = {fc["family"]: fc["verdict"] for fc in report.coverage_payload()}
    assert verdicts["Physical geometry"] == "PASS"
    assert verdicts["Construction completeness"] == "PASS"
    for fam in ("Support/Stability representation", "Structural capacity",
                "Load-path representation"):
        assert verdicts[fam] == "UNKNOWN — NOT ANALYZED", (fam, verdicts[fam])
    assert not any(f.check == "support" for f in report.findings)
    for f in report.findings:
        assert "capacity" not in f.detail.lower() or "not analyzed" in f.detail.lower()


def test_frame_joinery_uses_existing_words_honestly(frame):
    """The variant's vocabulary claim: NO new words. Four rail_cap_screwed
    (plate onto leg END grain — the word's true substrate) + four cleat_screwed
    (rail wide face to leg narrow EDGE — long grain both sides), nothing else; no bears_on from the cleats."""
    detail, _report = frame
    conns = detail.connections()
    kinds = sorted(c.kind.label for c in conns)
    assert kinds == ["cleat_screwed"] * 4 + ["rail_cap_screwed"] * 4
    for c in conns:
        edge_kinds = {e.kind for e in c.kind.edges(c)}
        if c.kind.label == "cleat_screwed":
            assert "bears_on" not in edge_kinds
        else:
            assert "bears_on" in edge_kinds  # the cap genuinely seats


def test_cap_screw_heads_are_authored_flush_while_inner_rail_heads_are_seated(frame):
    detail, _report = frame
    installs = detail._connection_checks.installs
    caps = [ri for ri in installs if ri.role == "cap_screws"]
    rails = [ri for ri in installs if ri.role == "cleat_screws"]
    assert len(caps) == 4 and len(rails) == 4
    assert all(ri.contract.head == "flush_countersunk" for ri in caps)
    assert all(ri.provenance_map["head"] == "authored_override" for ri in caps)
    assert all(ri.contract.head == "seated" for ri in rails)


def test_prose_truthfulness_guard(frame, tmp_path):
    import json
    detail, _report = frame
    detail.render_documentation(tmp_path)
    cov = tmp_path / "coverage_matrix.json"
    assert cov.exists()
    verdicts = {fc["family"]: fc["verdict"] for fc in json.loads(cov.read_text())}
    for fam in ("Support/Stability representation", "Structural capacity"):
        assert fam in verdicts and verdicts[fam].startswith("UNKNOWN")

    top = _bb(detail, "top plate (reach surface)")
    assert f"{top.zmax / _IN:g}" == "12"
    assert round(-top.ymin / 10.0, 2) == 23.0

    sys.path.insert(0, str(_REPO / "scripts"))
    import single_detail_report as SDR
    info = SDR.build_document(tmp_path / "doc.html", SPEC)
    doc = Path(info["path"]).read_text()
    assert "NOT ANALYZED" in doc
    assert "23cm" in doc or "23 cm" in doc
    for title in ("bench side +X", "bench side -X",
                  "set side +X in place", "set side -X in place"):
        assert title in doc
    from html import unescape
    visible = unescape(doc).lower()
    assert "rail screw stations" in visible
    assert "0.75in from each rail end" in visible
    assert "0.75in and 2.75in below the rail top" in visible
    assert "cap screw stations" in visible and "1.75in in from each side edge" in visible
    assert "0.75in from the front and back body edges" in visible
    assert "tools:" in visible and "countersink bit" in visible and "clamps" in visible
    assert "required loose accessory" in visible and "adhesive metric rule" in visible
    assert "prototype gate" in visible and "do not use" in visible
    assert "verify the intended test protocol" in visible
    assert "stud and screw stations are free to tune" not in visible
    assert "scores compare to published norms" not in visible
    assert "leveling nuts" not in visible and "natural stone" not in visible
    assert '"type":"existing context"' in visible
    cap_lines = [line for line in visible.split("install contract")
                 if "'cap_screws'" in line]
    assert cap_lines and all("head=flush_countersunk" in line for line in cap_lines)
    assert doc.index("bench side +X") < doc.index("bench side -X") < \
        doc.index("set side +X in place") < doc.index("set side -X in place")
    low = doc.lower()
    for forbidden in ("proven stable", "stability verified", "capacity verified",
                      "load-tested", "certified safe", "will not tip",
                      "will not slide", "will not rack", "rigid enough"):
        assert forbidden not in low, f"doc makes an unproven claim: {forbidden!r}"


def test_full_flow_is_fast():
    t0 = time.perf_counter()
    detail = compile_spec_file(SPEC)
    report = detail.validate()
    verify_assembly_fabrication(detail.assembly)
    detail.bom_table()
    elapsed = time.perf_counter() - t0
    assert report.ok
    assert elapsed < 60.0, f"e2e flow took {elapsed:.1f}s (budget 60s)"
