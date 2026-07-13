"""SUPPORT v1.1 — each declared support must EXIST and BEAR on its own foundation.

The reviewer's probe on the merged family: with the platform's −X cantilever
declared, a tree-end leg that CEASES TO BEAR on its own pier still passed the
support family — v1 only checked plan-bbox SPAN coverage of the declared supports,
and a non-bearing leg borrowed a sibling's path to ground SIDEWAYS through the beam
it clamps. v1.1 makes every declared support a tracked obligation: it must exist in
the model and reach a foundation on its OWN chain (not through a sibling support or
the surface it holds up). Still rung 3 (representation) — no adequacy is claimed.
"""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path

import pytest
import yaml

from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_file, load_spec_text
from detailgen.spec.site import compile_site_file

ROOT = Path(__file__).resolve().parent.parent
PLATFORM = ROOT / "details" / "platform.spec.yaml"


def _support(report):
    sup = [f for f in report.findings if f.check == "support"]
    assert len(sup) == 1, f"expected one support finding, got {sup}"
    return sup[0]


# -- a minimal borrow model: two blocks on a shared beam, over one board -------

def _borrow_spec_text(*, borrow: bool) -> str:
    """blkA bears footing fA; blkB bears footing fB; a shared beam clamps both;
    the board (walking_surface) sits on the beam and declares both blocks. When
    ``borrow`` is set, blkB's OWN foundation bond is dropped, so it can only reach
    ground by routing beam → blkA → fA — the sideways borrow v1.1 rejects."""
    def _in(v):
        return f"{v} in"
    bonds = [{"a": "blkA", "b": "fA"}, {"a": "beam", "b": "blkA"},
             {"a": "beam", "b": "blkB"}, {"a": "board", "b": "beam"}]
    if not borrow:
        bonds.append({"a": "blkB", "b": "fB"})
    doc = {"name": "borrow", "units": "in", "components": [
        {"id": "fA", "type": "footing", "name": "fA",
         "params": {"width": _in(8), "length": _in(8), "thickness": _in(6)},
         "place": {"raw": {"at": [_in(1.75), _in(1.75), _in(0)]}}},
        {"id": "fB", "type": "footing", "name": "fB",
         "params": {"width": _in(8), "length": _in(8), "thickness": _in(6)},
         "place": {"raw": {"at": [_in(38.25), _in(1.75), _in(0)]}}},
        {"id": "blkA", "type": "lumber", "name": "blkA",
         "params": {"nominal": "4x4", "length": _in(3.5)},
         "place": {"raw": {"at": [_in(0), _in(0), _in(0)]}}},
        {"id": "blkB", "type": "lumber", "name": "blkB",
         "params": {"nominal": "4x4", "length": _in(3.5)},
         "place": {"raw": {"at": [_in(36.5), _in(0), _in(0)]}}},
        {"id": "beam", "type": "lumber", "name": "beam",
         "params": {"nominal": "4x4", "length": _in(40)},
         "place": {"raw": {"at": [_in(0), _in(0), _in(3.5)]}}},
        {"id": "board", "type": "lumber", "name": "board",
         "params": {"nominal": "4x4", "length": _in(40)},
         "place": {"raw": {"at": [_in(0), _in(0), _in(7)]}}},
    ],
        "roles": {"fA": "ground", "fB": "ground",
                  "board": {"role": "walking_surface", "label": "deck",
                            "members": ["board"], "supports": ["blkA", "blkB"]}},
        "validation": {"ground": "fA", "bonds": bonds}}
    return yaml.safe_dump(doc)


def test_minimal_healthy_two_supports_pass():
    f = _support(compile_spec(load_spec_text(_borrow_spec_text(borrow=False))).validate())
    assert f.passed and f.verdict == "PASS"


def test_minimal_borrowed_bearing_fails_standalone():
    f = _support(compile_spec(load_spec_text(_borrow_spec_text(borrow=True))).validate())
    assert not f.passed and f.verdict == "FAIL"
    assert "blkB" in f.detail
    assert "on their own" in f.detail  # names the borrow, not a generic float


def test_minimal_borrowed_bearing_fails_in_site(tmp_path):
    """Same borrow, composed into a one-subsystem site — the tightened obligation
    runs on the composed model too (the check is shared by both paths)."""
    (tmp_path / "frag.spec.yaml").write_text(_borrow_spec_text(borrow=True))
    site = tmp_path / "site.spec.yaml"
    site.write_text(
        "name: borrow site\nkind: site\nunits: in\nsubsystems:\n"
        "  - id: f\n    fragment: frag.spec.yaml\n    place: identity\n"
        "    confidence: EXACT\n")
    f = _support(compile_site_file(site).validate())
    assert not f.passed and f.verdict == "FAIL"
    assert "blkB" in f.detail


# -- the reviewer's exact probe, on the real post-STRUCT platform --------------

def _drop_bearing(doc, a, b):
    v = doc.validation
    br = [x for x in v.bearings
          if not (getattr(x, "a", None) == a and getattr(x, "b", None) == b)]
    return dataclasses.replace(doc, validation=dataclasses.replace(v, bearings=br))


def _drop_foundation(doc, block):
    """Remove the FAB-3 foundation system on ``block`` — so its post base no
    longer bonds the leg to the pier. After FAB-3 a leg reaches its pier through
    the post base too (a real attachment bond), so isolating the leg from its own
    foundation now means dropping BOTH the bearing and the post base."""
    fnd = tuple(f for f in doc.foundations if f.block != block)
    return dataclasses.replace(doc, foundations=fnd)


def _add_support(doc, name):
    sch = copy.deepcopy(doc.support_schemes)
    s = sch["deck_0"]
    sch["deck_0"] = dataclasses.replace(s, supports=s.supports + (name,))
    return dataclasses.replace(doc, support_schemes=sch)


def test_platform_as_built_still_passes():
    """The STRUCT-built platform is correct: every declared leg bears its own
    foundation, so the tightened check leaves the acceptance design PASSING."""
    f = _support(compile_spec(load_spec_file(PLATFORM)).validate())
    assert f.passed and f.verdict == "PASS"
    # and the composed site is likewise clean on the support family
    assert _support(compile_site_file(ROOT / "details" / "site.spec.yaml").validate()).passed


def test_tree_end_leg_ceasing_to_bear_now_fails():
    """THE PROBE: leg_tree_mY loses its connection to its own pier (it now only
    clamps the beam). v1 kept PASSING — it borrowed the launch legs' pier through
    the beam. v1.1 FAILs, naming the leg that no longer bears on its own
    foundation. FAB-3 note: the leg reaches its pier through the post base bond
    too, so isolating it now means dropping BOTH its bearing AND its FAB-3
    foundation system — with only the bearing gone the post base is a real,
    remaining path to ground (correctly PASS)."""
    base = load_spec_file(PLATFORM)
    isolated = _drop_foundation(
        _drop_bearing(base, "leg_tree_mY", "pier_tree_mY"), "pier_tree_mY")
    f = _support(compile_spec(isolated).validate())
    assert not f.passed and f.verdict == "FAIL"
    assert "leg tree -Y" in f.detail and "on their own" in f.detail


def test_declared_support_absent_from_the_model_fails():
    """A support named in the scheme but not present in the model (a vanished /
    mistyped leg) FAILs its existence obligation gracefully — not a compile crash."""
    base = load_spec_file(PLATFORM)
    f = _support(compile_spec(_add_support(base, "leg_ghost")).validate())
    assert not f.passed and f.verdict == "FAIL"
    assert "leg_ghost" in f.detail and "not in the model" in f.detail


# -- the span still FAILs when dropping a support genuinely uncovers a region --

# -- the reviewer's DEFEAT: a NON-sibling frame borrow (directional fix) --------

def _frame_spec(components, bonds, supports):
    """A deck on a beam carried by blocks/posts — the shape the reviewer's DEFEAT
    and OVER-BLOCK attacks share. ``components`` is a list of (id, type, params,
    at); the board is the walking_surface, ``supports`` its declared supports."""
    def _in(v):
        return f"{v} in"
    comps = [{"id": cid, "type": typ, "name": cid, "params": p,
              "place": {"raw": {"at": [_in(a[0]), _in(a[1]), _in(a[2])]}}}
             for cid, typ, p, a in components]
    grounds = [cid for cid, typ, p, a in components if typ == "footing"]
    roles = {g: "ground" for g in grounds}
    roles["board"] = {"role": "walking_surface", "label": "deck",
                      "members": ["board"], "supports": supports}
    doc = {"name": "frame", "units": "in", "components": comps, "roles": roles,
           "validation": {"ground": grounds[0], "bonds": bonds}}
    return compile_spec(load_spec_text(yaml.safe_dump(doc)))


def _L(cid, at, length=3.5):
    return (cid, "lumber", {"nominal": "4x4", "length": f"{length} in"}, at)


def _F(cid, at, lx=8):
    return (cid, "footing", {"length": f"{lx} in", "width": "8 in",
                             "thickness": "6 in"}, at)


def test_defeat_nonsibling_frame_borrow_fails():
    """DEFEAT 3: blkB bears NOTHING; a genuine but UNDECLARED post (postC) bears
    fC. blkB reaches ground only by going UP into the beam it clamps and OVER to
    postC's footing. The undirected sibling-only fix passed this CLEAN; the
    surface-side (held-up-frame) block rejects it."""
    d = _frame_spec(
        [_F("fA", (1.75, 1.75, 0)), _F("fC", (19.75, 1.75, 0)),
         _L("blkA", (0, 0, 0)), _L("postC", (18, 0, 0)), _L("blkB", (36.5, 0, 0)),
         _L("beam", (0, 0, 3.5), 40), _L("board", (0, 0, 7), 40)],
        [{"a": "blkA", "b": "fA"}, {"a": "postC", "b": "fC"},
         {"a": "beam", "b": "blkA"}, {"a": "beam", "b": "postC"},
         {"a": "beam", "b": "blkB"}, {"a": "board", "b": "beam"}],
        ["blkA", "blkB"])
    rep = d.validate()
    f = _support(rep)
    assert not f.passed and f.verdict == "FAIL" and "blkB" in f.detail
    assert not rep.ok


def test_defeat_both_phantom_supports_fails():
    """Both declared supports bear nothing; the only real support is an undeclared
    mid-span post. The entire declared scheme is fictional → FAIL (not CLEAN)."""
    d = _frame_spec(
        [_F("fX", (16.25, 1.75, 0)),
         _L("blkA", (0, 0, 0)), _L("postX", (15, 0, 0)), _L("blkB", (36.5, 0, 0)),
         _L("beam", (0, 0, 3.5), 40), _L("board", (0, 0, 7), 40)],
        [{"a": "postX", "b": "fX"}, {"a": "beam", "b": "blkA"},
         {"a": "beam", "b": "postX"}, {"a": "beam", "b": "blkB"},
         {"a": "board", "b": "beam"}],
        ["blkA", "blkB"])
    f = _support(d.validate())
    assert not f.passed and "blkA" in f.detail and "blkB" in f.detail


# -- OVER-BLOCK: legit downward designs must keep PASSING (no false-FAIL) -------

def test_overblock_two_supports_sharing_one_foundation_pass():
    """Two posts genuinely sharing ONE wide pier — each reaches the shared
    foundation directly (downward), so both PASS despite the sibling block."""
    d = _frame_spec(
        [_F("pier", (18, 1.75, 0), lx=54),
         _L("pA", (0, 0, 0)), _L("pB", (36.5, 0, 0)),
         _L("beam", (0, 0, 3.5), 40), _L("board", (0, 0, 7), 40)],
        [{"a": "pA", "b": "pier"}, {"a": "pB", "b": "pier"},
         {"a": "beam", "b": "pA"}, {"a": "beam", "b": "pB"},
         {"a": "board", "b": "beam"}],
        ["pA", "pB"])
    assert _support(d.validate()).passed


def test_overblock_support_through_a_lower_grade_beam_passes():
    """A support bearing DOWN through a non-sibling intermediate (post → grade
    beam → footings, all below the posts) still PASSes — the grade beam is not
    surface-side, so it is not blocked."""
    d = _frame_spec(
        [_F("f1", (1.75, 1.75, 0), lx=10), _F("f2", (38.25, 1.75, 0), lx=10),
         _L("grade", (0, 0, 0), 40),
         _L("pA", (0, 0, 3.5)), _L("pB", (36.5, 0, 3.5)),
         _L("beam", (0, 0, 7), 40), _L("board", (0, 0, 10.5), 40)],
        [{"a": "grade", "b": "f1"}, {"a": "grade", "b": "f2"},
         {"a": "pA", "b": "grade"}, {"a": "pB", "b": "grade"},
         {"a": "beam", "b": "pA"}, {"a": "beam", "b": "pB"},
         {"a": "board", "b": "beam"}],
        ["pA", "pB"])
    assert _support(d.validate()).passed


# -- the DISCLOSED cross-surface residual (task SUPPORT v1.1 Option B) ----------

def test_multi_surface_findings_carry_the_cross_surface_disclosure():
    """v1.1's bearing obligation is a SINGLE-surface guarantee. A model with >1
    walking surface has an unverified cross-surface residual (below), so every
    support finding in such a model carries a VISIBLE rung-3 caveat — never
    silent. (Two independent decks here, both honestly supported.)"""
    def _in(v):
        return f"{v} in"
    comps, bonds, roles = [], [], {}
    for tag, x0 in (("A", 0.0), ("B", 200.0)):
        comps += [
            (f"f1{tag}", "footing", {"length": _in(8), "width": _in(8),
                                     "thickness": _in(6)}, (x0 + 1.75, 1.75, 0)),
            (f"f2{tag}", "footing", {"length": _in(8), "width": _in(8),
                                     "thickness": _in(6)}, (x0 + 38.25, 1.75, 0)),
            (f"b1{tag}", "lumber", {"nominal": "4x4", "length": _in(3.5)}, (x0, 0, 0)),
            (f"b2{tag}", "lumber", {"nominal": "4x4", "length": _in(3.5)}, (x0 + 36.5, 0, 0)),
            (f"beam{tag}", "lumber", {"nominal": "4x4", "length": _in(40)}, (x0, 0, 3.5)),
            (f"deck{tag}", "lumber", {"nominal": "4x4", "length": _in(40)}, (x0, 0, 7)),
        ]
        bonds += [{"a": f"b1{tag}", "b": f"f1{tag}"}, {"a": f"b2{tag}", "b": f"f2{tag}"},
                  {"a": f"beam{tag}", "b": f"b1{tag}"}, {"a": f"beam{tag}", "b": f"b2{tag}"},
                  {"a": f"deck{tag}", "b": f"beam{tag}"}]
        roles[f"f1{tag}"] = "ground"
        roles[f"f2{tag}"] = "ground"
        roles[f"deck{tag}"] = {"role": "walking_surface", "label": f"deck{tag}",
                               "members": [f"deck{tag}"],
                               "supports": [f"b1{tag}", f"b2{tag}"]}
    comps = [{"id": c, "type": t, "name": c, "params": p,
              "place": {"raw": {"at": [_in(a[0]), _in(a[1]), _in(a[2])]}}}
             for c, t, p, a in comps]
    doc = {"name": "two decks", "units": "in", "components": comps, "roles": roles,
           "validation": {"ground": "f1A", "bonds": bonds}}
    rep = compile_spec(load_spec_text(yaml.safe_dump(doc))).validate()
    support = [f for f in rep.findings if f.check == "support"]
    assert len(support) == 2
    for f in support:
        assert f.passed  # both decks are honestly supported
        assert "cross-surface support borrowing is NOT verified" in f.detail
        assert "CL-gated" in f.detail


@pytest.mark.xfail(strict=True, reason=(
    "DOCUMENTED GAP (task SUPPORT v1.1, reviewer addendum): _surface_side is "
    "per-surface, so a phantom in surface A can borrow surface B's foundation "
    "through B's frame. A global frame block cannot tell that phantom borrow from "
    "a legitimate stacked platform (an upper deck's post honestly bearing on a "
    "lower deck's frame) without DECLARED bearing direction — schema/CL territory, "
    "gated on the owner's CL sign-off. Disclosed on the finding surface + here; "
    "flip this xfail to a real test when the directional follow-up lands."))
def test_cross_surface_phantom_borrow_is_rejected():
    """Graph-level proof against the REAL shipped ``_surface_side`` /
    ``_bears_independently``: two surfaces A, B; A declares a ``phantom`` support
    that bears on NOTHING but is braced to B's beam. It reaches ground only via
    ``phantom → beamB → legB → fB`` — a foreign surface's foundation. The DESIRED
    behavior is that this is rejected; today it is not (xfail)."""
    from detailgen.validation.support import _surface_side, _bears_independently

    class _P:
        def __init__(self, i):
            self.id = i

    adj = {
        "deckA": {"beamA"}, "beamA": {"deckA", "legA", "phantom"},
        "legA": {"beamA", "fA"}, "fA": {"legA"},
        "phantom": {"beamA", "beamB"},  # bears nothing of its own; braced to B
        "beamB": {"phantom", "deckB", "legB"}, "deckB": {"beamB"},
        "legB": {"beamB", "fB"}, "fB": {"legB"},
    }
    foundations = {"fA", "fB"}
    frame_a = _surface_side({"deckA"}, {"legA", "phantom"}, adj)
    blocked = (frame_a | {"legA", "phantom"}) - {"phantom"} - foundations
    # DESIRED: the phantom bears on nothing of its own -> must NOT be grounded.
    assert not _bears_independently(_P("phantom"), foundations, adj, blocked)


def test_dropping_a_support_that_uncovers_the_span_still_fails():
    """Sanity that the v1 span check is intact: remove one end's support entirely
    (block + its foundation + the declaration) so the occupied region overhangs
    the remaining support — the undeclared overhang FAILs, as appropriate."""
    doc = yaml.safe_load(_borrow_spec_text(borrow=False))
    # drop blkB, fB, and blkB from the declaration -> board overhangs +X
    doc["components"] = [c for c in doc["components"]
                         if c["id"] not in ("blkB", "fB")]
    doc["validation"]["bonds"] = [
        b for b in doc["validation"]["bonds"]
        if "blkB" not in (b["a"], b["b"]) and "fB" not in (b["a"], b["b"])]
    doc["roles"].pop("fB")
    doc["roles"]["board"]["supports"] = ["blkA"]
    f = _support(compile_spec(load_spec_text(yaml.safe_dump(doc))).validate())
    assert not f.passed  # +X overhang beyond the single remaining support
    assert "+X" in f.detail
