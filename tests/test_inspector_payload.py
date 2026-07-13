"""Task INSPECTOR — the inspector payload IR (the compiler-emits side).

These tests bind the DATA CONTRACT the Inspector HTML consumes, not pixels: the
panel is prototype-grade, but the payload it renders must be complete, pure
JSON, and HONEST. The honesty tests have teeth — they assert not just that the
happy path holds on the real rock anchor but that the invariants that keep an
UNKNOWN family from silently reading as adequacy actually fire.

The rock anchor is the fixture because it is the mission's honesty exemplar: two
families PASS with real findings, FOUR are UNKNOWN (structural capacity, code
compliance, spatial intent, functional use) — exactly the case where a naive
per-part verdict view would mislead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import hashlib

from detailgen.rendering.inspector import (
    InspectorPayloadError,
    SCHEMA,
    Verification,
    build_inspector_payload,
    emit_inspector_html,
    render_inspector_document,
)
from detailgen.spec.compiler import compile_spec_file

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"


# Factory keeping the ``RockAnchor()`` call syntax; compiles the detail's
# spec.yaml (the imperative mirror is retired).
def RockAnchor():
    return compile_spec_file(DETAILS / "rock_anchor.spec.yaml")


@pytest.fixture(scope="module")
def payload():
    detail = RockAnchor()
    detail.validate()
    return build_inspector_payload(detail)


@pytest.fixture(scope="module")
def detail():
    d = RockAnchor()
    d.validate()
    return d


# -- completeness: every part has a full four-section record -----------------


def test_every_part_has_a_complete_descriptor(payload, detail):
    names = {p.name for p in detail.assembly.parts}
    assert set(payload["parts"]) == names
    assert payload["part_order"] and set(payload["part_order"]) == names
    for name, rec in payload["parts"].items():
        assert rec["name"] == name
        assert rec["part_id"]
        for section in ("descriptor", "provenance", "verification", "dependencies"):
            assert rec[section], f"{name} has empty {section}"
        d = rec["descriptor"]
        # a real WHAT-IS answer: identity, material and a dimension line
        assert d["component_type"] and d["material"] and d["descriptor"]
        # every section-3 record carries the full assembly coverage matrix
        assert rec["verification"]["coverage"], f"{name} lost its coverage matrix"


def test_id_to_name_covers_every_part(payload, detail):
    assert len(payload["id_to_name"]) == len(detail.assembly.parts)
    for pid, name in payload["id_to_name"].items():
        assert pid.startswith("part:")
        assert name in payload["parts"]


# -- purity: the payload is JSON, all the way down ---------------------------


def test_payload_is_pure_json(payload):
    dumped = json.dumps(payload)          # raises TypeError if any non-native leaks in
    assert json.loads(dumped) == payload  # round-trips structurally equal
    assert payload["schema"] == SCHEMA


def test_rendered_document_is_self_contained(payload):
    import re

    html = render_inspector_document(payload, glb_b64="QUJD")  # dummy b64
    assert "<!DOCTYPE html>" in html
    assert "inspector-data-" + payload["slug"] in html
    assert "inspector-glb-" + payload["slug"] in html
    # NO off-host resource may be LOADED — no src/href/url() to an external host
    # (benign namespace-URI string literals inside vendored three.js don't count;
    # the property is "nothing is fetched", i.e. no resource-loading attribute).
    assert not re.search(r'(?:src|href)\s*=\s*["\']https?://', html)
    assert not re.search(r'url\(\s*["\']?https?://', html)
    # the payload JSON cannot close the <script> early
    assert "</script>" not in json.dumps(payload).replace("</", "<\\/")


# -- honesty: the wording rule binds the emitted strings ---------------------


def test_unknown_families_are_labelled_not_analysed(payload):
    """A part with UNKNOWN families renders them AS UNKNOWN — never a bare PASS
    and never silence. The rock anchor has five un-analysed families (Fastener
    installability left the UNKNOWN set when the INSTALL v1 axis checks ran —
    its 8 checks PASS); every part must carry them, flagged
    ``analysed=False`` with a self-describing note."""
    fams = payload["coverage"]["families"]
    unknown = [f for f in fams if not f["analysed"]]
    assert len(unknown) == 5, "rock anchor should have 5 UNKNOWN families"
    assert "Fastener installability" not in {f["family"] for f in unknown}, \
        "installability is ANALYSED on the rock anchor since INSTALL v1"
    for f in unknown:
        assert "UNKNOWN" in f["verdict"] and "NOT ANALYZED" in f["verdict"]
        assert f["checks_run"] == 0
        assert f["note"], "an UNKNOWN family must explain itself"
    # and every single part carries the same five UNKNOWN families in section 3
    for name, rec in payload["parts"].items():
        cov = rec["verification"]["coverage"]
        part_unknown = [c for c in cov if not c["analysed"]]
        assert len(part_unknown) == 5, f"{name} hides UNKNOWN families"
        for c in part_unknown:
            assert "NOT ANALYZED" in c["verdict"]


def test_no_finding_is_a_bare_verdict(payload):
    """Section 3's cardinal rule: never a bare PASS. Every finding the payload
    carries is pre-EXPLAINED — the explanation names the check, the subject, and
    the fact or intrinsic law that generated it."""
    seen = 0
    for rec in payload["parts"].values():
        for fd in rec["verification"]["findings"]:
            seen += 1
            expl = fd["explanation"]
            assert expl not in ("PASS", "FAIL", ""), "bare verdict leaked"
            verdict = "PASS" if fd["passed"] else "FAIL"
            assert expl.startswith(verdict) and fd["check"] in expl
            assert "—" in expl, "an explanation must give a reason (the em-dash clause)"
    assert seen > 0


def test_part_can_only_claim_analysed_families(payload):
    """The honesty merge: a part's own family verdicts may only name families the
    assembly actually analysed. A PASS in an un-analysed family would be a lie."""
    analysed = {f["family"] for f in payload["coverage"]["families"] if f["analysed"]}
    for name, rec in payload["parts"].items():
        for pf in rec["verification"]["part_families"]:
            assert pf["family"] in analysed, f"{name} claims un-analysed {pf['family']}"


def test_standing_note_present_everywhere(payload):
    assert "NOT ANALYZED" in payload["coverage"]["standing_note"]
    for rec in payload["parts"].values():
        assert rec["verification"]["standing_note"] == payload["coverage"]["standing_note"]


# -- the honesty merge fires when the two views disagree ---------------------


class _Row:
    def __init__(self, family, verdict, checks_run):
        self.family = family
        self.verdict = verdict
        self.checks_run = checks_run
        self.failures = 0
        self.note = "synthetic"


def test_verification_rejects_a_verdict_in_an_unanalysed_family():
    """If ``how_verified`` ever returned a part-family verdict for a family the
    coverage matrix says NOTHING ran in, the payload must refuse to build rather
    than emit a part that looks verified where it was not."""
    how_verified = {
        "findings": [], "evidence_chain": [], "load_paths": [],
        "standing_note": "x",
        "family_verdicts": [
            {"family": "Structural capacity", "verdict": "PASS",
             "checks_run": 3, "failures": 0, "note": "n"}
        ],
    }
    coverage_rows = [_Row("Structural capacity", "UNKNOWN — NOT ANALYZED", 0)]
    with pytest.raises(InspectorPayloadError, match="un-analysed families"):
        Verification.build(how_verified, coverage_rows)


# -- section 4: the load path is represented, and navigable ------------------


def test_leg_surfaces_its_represented_load_path(payload):
    leg = payload["parts"]["leg"]
    lps = leg["dependencies"]["load_paths"]
    assert lps, "the leg must surface its represented downward-load path"
    chain = lps[0]["chain"]
    # every named node on the chain is itself a selectable part (navigation works)
    for node_name in chain:
        assert node_name in payload["parts"], f"load-path node {node_name} not selectable"
    assert lps[0]["represented"] is True
    assert chain[0] == "leg" and lps[0]["reached_ground"] == "boulder"


def test_neighbors_name_selectable_parts(payload):
    """Section 4 navigation: every construction neighbour names a part that is a
    key in the payload, so clicking it becomes the next selection."""
    for name, rec in payload["parts"].items():
        for nb in rec["dependencies"]["neighbors"]:
            assert nb["other_name"] in payload["parts"], (
                f"{name} neighbour {nb['other_name']!r} is not a selectable part")


# -- determinism: two builds are byte-identical (FOLLOW-UP) ------------------
# The Evidence-Graph determinism fix (sdd/cleanup) makes the emitted artifact
# reproducible. These lock that so the committed HTML can be regenerated by
# anyone and match, and a future nondeterminism regression fails loudly here.


def test_payload_is_deterministic_across_builds(payload):
    """Building the payload from two independent validations yields byte-identical
    JSON — the whole IR (descriptors, provenance chains, findings, coverage) is a
    pure function of the detail, with no set/dict-ordering or float-formatting
    wobble leaking in."""
    d2 = RockAnchor()
    d2.validate()
    again = build_inspector_payload(d2)
    assert again == payload
    canon = lambda p: json.dumps(p, separators=(",", ":"), sort_keys=False)
    assert canon(again) == canon(payload)


def test_emitted_html_is_byte_reproducible(tmp_path, monkeypatch):
    """The full self-contained HTML — payload JSON AND the gzipped-base64 GLB —
    is byte-for-byte reproducible across two independent emits. This is the
    property that lets the committed rock_anchor_inspector.html be regenerated on
    demand instead of trusted as an opaque blob.

    The wall clock is advanced between the two emits, because the real bug this
    guards is a wall-clock timestamp leaking into the artifact (gzip stamps the
    current time into its header unless told not to). With the same clock on both
    emits the bug hides; moving time between them makes it fail loudly."""
    out1 = emit_inspector_html(RockAnchor(), tmp_path / "a.html",
                               glb_work_dir=tmp_path / "g1")
    monkeypatch.setattr("time.time", lambda: 2_000_000_000.0)  # far-future clock
    out2 = emit_inspector_html(RockAnchor(), tmp_path / "b.html",
                               glb_work_dir=tmp_path / "g2")
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    assert h1 == h2, "emitted Inspector HTML is not byte-reproducible (time leak?)"
