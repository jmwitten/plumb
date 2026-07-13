"""The Support/Stability REPRESENTATION invariant — the adversarial proof suite
(task SUPPORT, directive req 7 + 9).

These cases PROVE the invariant; they are NOT the invariant. Each is a minimal,
ROLE-DRIVEN spec (a walking_surface + supports + a real foundation), never a deck
— the compiler must reject an unsupported occupied region because of what a
``walking_surface`` is, not because it knows what a deck is. The geometry is a
flat occupied surface (deck boards spanning X, tiled in Y) carried by 4x4 support
blocks that bear down onto a footing foundation; the block positions are the only
thing that changes between cases. All lengths are inches.

The verdict ladder these lock (see :mod:`detailgen.validation.support`):

- occupied region within / over its grounded supports        -> PASS  (rung 3)
- an UNDECLARED one-sided overhang (a region with no support) -> FAIL
- an overhang on BOTH sides of an axis (interior support)     -> UNKNOWN (blocks)
- a DECLARED cantilever over the overhang                     -> PASS with note
- DEFERRED support                                            -> FAIL (deferral named)
"""

from __future__ import annotations

import pytest
import yaml

from detailgen.core.ontology import OntologyError
from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text
from detailgen.spec.schema import SpecSchemaError

BOARD_W = 5.5           # deck_board width in Y
BLOCK = 3.5             # 4x4 block plan size + height (board sits at z=BLOCK)


def _in(v):
    return f"{v} in"


def _surface_spec(*, supports, n_boards=6, board_len=60.0, board_x0=0.0,
                  cantilever=(), deferred="", with_foundation=True,
                  declare_supports=True):
    """Build a walking_surface detail: ``n_boards`` deck boards (each ``board_len``
    long in X, tiled in Y) carried by 4x4 ``supports`` blocks (``(x, y)`` plan
    positions) that bear onto a wide footing foundation. Returns the compiled
    SpecDetail (unvalidated)."""
    comps = []
    if with_foundation:
        comps.append({"id": "found", "type": "footing", "name": "found",
                      "params": {"width": _in(200), "length": _in(200),
                                 "thickness": _in(6)},
                      "place": {"raw": {"at": [_in(30), _in(15), _in(0)]}}})
    for j in range(n_boards):
        comps.append({"id": f"board_{j}", "type": "deck_board",
                      "name": f"board {j}",
                      "params": {"length": _in(board_len)},
                      "place": {"raw": {"at": [_in(board_x0), _in(j * BOARD_W),
                                               _in(BLOCK)]}}})
    for i, (bx, by) in enumerate(supports):
        comps.append({"id": f"blk_{i}", "type": "lumber", "name": f"block {i}",
                      "params": {"nominal": "4x4", "length": _in(BLOCK)},
                      "place": {"raw": {"at": [_in(bx), _in(by), _in(0)]}}})

    # Connectivity is declared as BONDS (a "these touch" edge): softer than a
    # bearing (no face-area FAIL if a declared pair doesn't touch), and the same
    # graph the reach-a-foundation BFS and the floating check walk. Each block
    # bonds to the foundation (below) and to the board directly above it; the
    # boards bond in a chain so the whole occupied surface is one connected piece.
    bonds = [{"a": f"board_{j}", "b": f"board_{j + 1}"}
             for j in range(n_boards - 1)]
    for i, (bx, by) in enumerate(supports):
        above = f"board_{min(int(by / BOARD_W), n_boards - 1)}"
        if with_foundation:
            bonds.append({"a": f"blk_{i}", "b": "found"})
        bonds.append({"a": f"blk_{i}", "b": above})

    scheme = {"role": "walking_surface", "label": "deck",
              "members": [f"board_{j}" for j in range(n_boards)]}
    if declare_supports and supports:
        scheme["supports"] = [f"blk_{i}" for i in range(len(supports))]
    if cantilever:
        scheme["declared_cantilever"] = [{"edge": e} for e in cantilever]
    if deferred:
        scheme["deferred_support"] = deferred

    roles = {"board_0": scheme}
    if with_foundation:
        roles["found"] = "ground"

    validation = {"bonds": bonds}
    if with_foundation:
        validation["ground"] = "found"
    doc = {"name": "support_case", "units": "in", "components": comps,
           "validation": validation, "roles": roles}
    return compile_spec(load_spec_text(yaml.safe_dump(doc)))


def _support_finding(detail):
    rep = detail.validate()
    sup = [f for f in rep.findings if f.check == "support"]
    assert len(sup) == 1, f"expected one support finding, got {sup}"
    return rep, sup[0]


# -- the positive control: a supported surface is REPRESENTED (rung 3) --------

def test_supported_surface_passes_rung_3():
    # 4 corner blocks -> their bbox span covers the occupied footprint.
    d = _surface_spec(supports=[(0, 0), (56.5, 0), (0, 29.5), (56.5, 29.5)])
    rep, f = _support_finding(d)
    assert f.passed and f.verdict == "PASS"
    assert "REPRESENTED (rung 3)" in f.detail
    assert "NOT ANALYZED (rung 4)" in f.detail  # never implies adequacy


# -- FAIL: an undeclared one-sided overhang is an unsupported region ----------

def test_front_supports_only_fails():
    """THE regression — the reconstruction of the miss: supports at ONE end, the
    occupied surface cantilevers over the other with nothing under it."""
    d = _surface_spec(supports=[(0, 0), (0, 29.5)])  # only the -X (front) end
    rep, f = _support_finding(d)
    assert not f.passed and f.verdict == "FAIL"
    assert "+X" in f.detail and "no declared cantilever" in f.detail
    assert not rep.ok  # blocks export


def test_removing_support_from_one_end_flips_pass_to_fail():
    both = _surface_spec(supports=[(0, 0), (0, 29.5), (56.5, 0), (56.5, 29.5)])
    _, f_both = _support_finding(both)
    assert f_both.passed  # valid model

    one = _surface_spec(supports=[(0, 0), (0, 29.5)])  # the +X-end pair removed
    _, f_one = _support_finding(one)
    assert not f_one.passed and f_one.verdict == "FAIL"


def test_single_corner_support_fails():
    d = _surface_spec(supports=[(0, 0)])  # one corner only
    rep, f = _support_finding(d)
    assert not f.passed and f.verdict == "FAIL"
    # two adjacent edges overhang with support opposite -> one-sided FAIL
    assert "+X" in f.detail and "+Y" in f.detail
    assert not rep.ok


# -- UNKNOWN (blocking): tiny support under a large surface -------------------

def test_tiny_central_support_is_unknown_not_a_fake_fail():
    """A single small block UNDER THE CENTRE: the occupied surface overhangs it on
    both sides of both axes. v1 cannot tell an intended balanced cantilever from an
    omission, so the honest verdict is UNKNOWN — not a fake FAIL — and it BLOCKS."""
    d = _surface_spec(supports=[(28.25, 14.75)])  # centred block
    rep, f = _support_finding(d)
    assert f.verdict == "UNKNOWN"
    assert not f.passed          # unknown never certifies
    assert "NOT ANALYZED at rung 3" in f.detail
    assert not rep.ok            # UNKNOWN blocks export (req 5)


def test_unknown_support_blocks_require_clean():
    d = _surface_spec(supports=[(28.25, 14.75)])
    with pytest.raises(AssertionError, match="unresolved"):
        d.validate().require_clean()


# -- declared cantilever: the same overhang, now REPRESENTED as intent --------

def test_declared_cantilever_passes_rung_3_with_the_declaration_visible():
    d = _surface_spec(supports=[(0, 0), (0, 29.5)], cantilever=["+X"])
    rep, f = _support_finding(d)
    assert f.passed and f.verdict == "PASS"
    assert "declared cantilever" in f.detail and "+X" in f.detail
    assert rep.ok  # a declared cantilever is a representable, clean scheme


# -- deferred support: FAIL with the deferral named ---------------------------

def test_deferred_support_fails_with_the_deferral_named():
    d = _surface_spec(supports=[], deferred="tree-end legs deferred to STRUCT")
    rep, f = _support_finding(d)
    assert not f.passed and f.verdict == "FAIL"
    assert "DEFERRED" in f.detail and "tree-end legs deferred to STRUCT" in f.detail
    assert not rep.ok


# -- the RCA's canonical counterexample (directive req 9) ---------------------

def test_rca_single_corner_slab_is_rejected():
    """The RCA experiment, committed as the family's canonical counterexample: a
    60in slab on ONE 3.5in block at one end validated CLEAN before this task. Now
    the support check rejects it (undeclared 56in overhang), and require_clean —
    the export gate — refuses it. This is the acceptance proof in miniature."""
    d = _surface_spec(supports=[(0, 0)], n_boards=1, board_len=60.0)
    rep, f = _support_finding(d)
    assert not f.passed and f.verdict == "FAIL"
    assert "not supported" in f.detail
    with pytest.raises(AssertionError):
        rep.require_clean()   # would have EXPORTED before task SUPPORT


# -- a support that reaches no foundation is not represented ------------------

def test_support_not_reaching_a_foundation_fails():
    # No foundation body at all: the block reaches no ground.
    d = _surface_spec(supports=[(0, 0), (56.5, 0)], with_foundation=False)
    rep, f = _support_finding(d)
    assert not f.passed and f.verdict == "FAIL"
    assert "foundation" in f.detail


# -- teaching errors (schema honesty, not a geometry verdict) -----------------

def test_walking_surface_with_no_scheme_is_a_teaching_error():
    """req 1: declaring a walking_surface with no supports / declared_cantilever /
    deferred_support names the missing declaration at load time."""
    with pytest.raises(SpecSchemaError, match="no support scheme"):
        _surface_spec(supports=[(0, 0)], declare_supports=False)


def test_ground_that_is_a_structural_member_is_a_teaching_error():
    """req 2: a validation.ground pointing at a member with a non-ground role is
    the ``ground: leg`` degeneracy — a teaching error, not a silent BFS root."""
    doc = {
        "name": "bad_ground", "units": "in",
        "components": [
            {"id": "blk", "type": "lumber", "name": "block",
             "params": {"nominal": "4x4", "length": _in(BLOCK)},
             "place": {"raw": {"at": [_in(0), _in(0), _in(0)]}}},
        ],
        "roles": {"blk": "support"},
        "validation": {"ground": "blk"},   # a support member as ground
    }
    with pytest.raises(OntologyError, match="must be a FOUNDATION"):
        compile_spec(load_spec_text(yaml.safe_dump(doc))).validate()
