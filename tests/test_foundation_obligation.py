"""Foundation-role obligation pack — the R29 retirement (task FAB-3).

CAT-2 (the acceptance bar, a caught-past-failure): a pier block a leg merely
RESTS on — a bearing pair + a ``ground`` label, no attachment — read CLEAN
before (``retro-index.md:66``). After FAB-3 that exact shape FAILs the attachment
obligation loudly; with a post base declared the attachment is REPRESENTED and
CAPACITY is a blocking UNKNOWN, so the model can no longer call an undesigned
foundation CLEAN. AC3: all three platform legs carry declared post bases + hardware
lines + generated attachment obligations, and the embedment check fires for a
too-shallow block. Ladder honesty: the capacity verdict is UNKNOWN by construction
— no code path emits PASS/CLEAN for it, ever.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.validation.checks import (
    FAIL_VERDICT, PASS_VERDICT, UNKNOWN_VERDICT)
from detailgen.validation.foundation import (
    ResolvedFoundation, _capacity_finding, check_foundations)

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "details" / "platform.spec.yaml"


def _fkind(report, kind):
    return [f for f in report.findings if f.check == kind]


# -- CAT-2: the R29 shape, before and after ---------------------------------- #


@pytest.fixture(scope="module")
def platform_doc():
    return load_spec_file(PLATFORM)


def test_cat2_undesigned_foundation_fails_attachment_loudly(platform_doc):
    """The exact R29 shape that read CLEAN before: the three legs BEAR on their
    pier blocks (a ``ground`` bearing pair) with NO foundation system declared.
    Stripping the ``foundations:`` block reproduces it — and the attachment
    obligation now FAILs loudly, naming each post and its block, instead of
    passing silently."""
    doc = replace(platform_doc, foundations=())
    report = compile_spec(doc).validate()
    att = _fkind(report, "foundation_attachment")
    assert len(att) == 3 and all(not f.passed for f in att), \
        "an undesigned foundation must FAIL the attachment obligation"
    subjects = {f.subject for f in att}
    assert subjects == {"leg -Y -> pier -Y",
                        "leg tree +Y -> pier tree +Y",
                        "leg tree -Y -> pier tree -Y"}
    for f in att:
        assert f.verdict == FAIL_VERDICT
        assert "NO declared post base" in f.detail
    # No system declared -> no embedment/capacity findings (the FAIL is the whole
    # story); and the failure is a real FAIL, not a blocking UNKNOWN here.
    assert not _fkind(report, "foundation_capacity")
    assert not _fkind(report, "foundation_embedment")


def test_cat2_declared_foundation_represents_attachment_blocks_on_capacity(platform_doc):
    """With the post bases declared (the shipped platform), each attachment is
    REPRESENTED (rung 3) — but capacity is a BLOCKING UNKNOWN (rung 4), so the
    model still refuses to call the foundation CLEAN. That is the R29 retirement:
    a foundation shown is never a foundation silently designed."""
    report = compile_spec(platform_doc).validate()
    att = _fkind(report, "foundation_attachment")
    assert len(att) == 3 and all(f.passed for f in att)
    for f in att:
        assert f.verdict == PASS_VERDICT and "REPRESENTED (rung 3)" in f.detail

    cap = _fkind(report, "foundation_capacity")
    assert len(cap) == 3
    for f in cap:
        assert f.verdict == UNKNOWN_VERDICT and f.blocking and not f.passed

    # The model is NOT clean, and it is blocked only by honest UNKNOWNs — not
    # by any FAIL (attachment/embedment are PASS). The INSTALL v1 toe-screw
    # UNKNOWNs were resolved on merit by task CPGCORE's authored sequence,
    # so the capacity UNKNOWNs are the whole blocking set.
    # require_clean must raise.
    assert not report.ok
    assert [f.check for f in report.failures] == []
    assert Counter(f.check for f in report.blocking) == Counter(
        {"foundation_capacity": 3})
    with pytest.raises(AssertionError):
        report.require_clean()


def test_cat2_site_can_no_longer_call_undesigned_foundation_clean():
    """The site-level statement of CAT-2: the composed zipline site — which read
    CLEAN before FAB-3 — is now blocked, because the platform's foundation
    capacity is an honest UNKNOWN. (Faster to assert on the platform fragment
    directly; the site path is exercised by test_site_model.)"""
    report = compile_spec(load_spec_file(PLATFORM)).validate()
    assert not report.ok and report.blocking


# -- AC3: three legs designed + embedment fires on a too-shallow block -------- #


def test_ac3_three_legs_have_post_bases_and_hardware_lines(platform_doc):
    detail = compile_spec(platform_doc)
    detail.validate()
    # Three post bases exist as real placed parts, each a purchased BOM line.
    post_bases = [p for p in detail.assembly.parts
                  if type(p.component).__name__ == "PostBase"]
    assert len(post_bases) == 3
    bom = detail.bom_table()
    pb_rows = [r for r in bom if r["item"] == "Adjustable standoff post base"]
    assert len(pb_rows) == 1 and pb_rows[0]["qty"] == 3  # 3 identical -> one group
    # Each is the hardware of a generated post->block Connection.
    pb_conns = [c for c in detail.connections()
                if type(c.kind).__name__ == "StandoffPostBase"]
    assert len(pb_conns) == 3
    for c in pb_conns:
        assert len(c.hardware) == 1
        assert type(c.hardware[0].component).__name__ == "PostBase"


_SHALLOW = """
name: shallow pier fixture
units: in
components:
  - id: post
    type: lumber
    params: {nominal: "2x6", length: "20 in", treated: true}
    place: {raw: {at: [0, 0, 2], rotate: [["Y", -90]]}}
  - id: pier
    type: pier_block
    params: {width: "10.5 in", length: "10.5 in", height: "2 in"}   # only 2" below grade
    place: {raw: {at: [0, 0, 2]}}
roles:
  pier: ground
foundations:
  - label: "shallow"
    supports: post
    block: pier
    post_base: {type: standoff_post_base, params: {width: "3.5 in", length: "3.5 in", height: "2 in"}}
    frost_depth: "48 in"
validation:
  ground: pier
  bearings:
    - {a: post, b: pier, axis: Z, area: 100}   # the post really rests on its block
"""


def test_ac3_embedment_fires_on_too_shallow_block():
    """An adversarial fixture: a foundation that DECLARES a 48" frost depth over a
    block set only 2" below grade. The embedment obligation fires — a FAIL naming
    the block and the shortfall, the same rung-below-capacity geometric check a
    ConcretePier already carries."""
    report = compile_spec(load_spec_text(_SHALLOW)).validate()
    emb = _fkind(report, "foundation_embedment")
    assert len(emb) == 1
    f = emb[0]
    assert not f.passed and f.verdict == FAIL_VERDICT
    assert "shallower than the declared frost depth" in f.detail


def test_embedment_passes_when_block_reaches_declared_frost():
    """The same fixture with the frost depth reduced below the block's 2" buried
    depth passes embedment (rung 3 represented) — the check is a real geometric
    comparison, not a rubber stamp."""
    doc = load_spec_text(_SHALLOW.replace('frost_depth: "48 in"', 'frost_depth: "1.5 in"'))
    report = compile_spec(doc).validate()
    emb = _fkind(report, "foundation_embedment")
    assert len(emb) == 1 and emb[0].passed and emb[0].verdict == PASS_VERDICT


# -- Coherence: a foundation whose post does not bear on its block ----------- #

_NONBEARING = _SHALLOW.replace(
    "at: [0, 0, 2], rotate", "at: [500, 0, 2], rotate"   # post placed 500" away
).replace(
    '    frost_depth: "48 in"\n', ""                          # isolate the coherence FAIL
).replace(
    "  bearings:\n    - {a: post, b: pier, axis: Z, area: 100}"
    "   # the post really rests on its block\n", ""      # ...and it does NOT bear
)


def test_foundation_declared_for_nonbearing_post_fails_loudly():
    """The silent-nonsense case the review caught: a foundation declares a post
    base joining a post to a block, but the post does NOT actually bear on that
    block (moved 500" away / a mistyped ref). Before the fix this placed a
    disconnected post-base part and emitted embedment PASS + capacity UNKNOWN as
    if real. Now the existence obligation (the mirror of SUPPORT's
    missing_supports) FAILs loudly naming both, and suppresses the embedment /
    capacity findings that would dress up a physically-absent attachment."""
    report = compile_spec(load_spec_text(_NONBEARING)).validate()
    att = _fkind(report, "foundation_attachment")
    assert len(att) == 1 and not att[0].passed and att[0].verdict == FAIL_VERDICT
    assert "does NOT bear on" in att[0].detail
    assert att[0].subject == "post -> pier"
    # the incoherent system emits NO embedment / capacity — the FAIL is the whole
    # story, never a "represented" verdict over a disconnected part.
    assert not _fkind(report, "foundation_embedment")
    assert not _fkind(report, "foundation_capacity")


# -- Ladder honesty: capacity is UNKNOWN by construction --------------------- #


def test_foundation_capacity_is_unknown_never_pass_or_fail():
    """The capacity verdict is UNKNOWN for EVERY input — declared or not, any frost
    depth: v1 computes no capacity number by construction (design risk R2). No
    code path can emit PASS/CLEAN (or even FAIL) for foundation_capacity."""
    class _P:  # a stand-in placed part with the attrs the pack reads
        def __init__(self, pid, name):
            self.id, self.name = pid, name

    post, block, pb = _P("post-0", "post"), _P("pier-0", "pier"), _P("pb-0", "pb")
    for frost in (None, 48 * 25.4, 0.0):
        sys = ResolvedFoundation(
            label="f", post=post, block=block, post_base=pb,
            uplift="declared", bearing_on_grade="field_verify", frost_depth=frost)
        cap = _capacity_finding(sys)
        assert cap.verdict == UNKNOWN_VERDICT
        assert cap.passed is False and cap.blocking
        assert "NOT ANALYZED" in cap.detail and "rung 4" in cap.detail


def test_no_capacity_finding_source_emits_pass():
    """Structural guard: the ONLY place a ``foundation_capacity`` Finding is built
    is ``_capacity_finding``, and it hard-codes UNKNOWN — so no future edit can
    silently certify a foundation's capacity. (A source scan, not a behavior test:
    it catches a second, PASS-emitting construction site being added.)"""
    src = (ROOT / "src" / "validation" / "foundation.py").read_text()
    # every literal use of the kind string sits in the one UNKNOWN-verdict builder
    assert src.count('"foundation_capacity"') == 1
    assert "verdict=UNKNOWN_VERDICT" in src
    assert 'PASS' not in src.split('"foundation_capacity"')[1][:400]
