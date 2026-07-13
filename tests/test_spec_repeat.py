"""DetailSpec REPEAT construct + the validation-block / measure additions the
platform benchmark forced. Positive behavior + a teaching diagnostic per gap
(the SPECPLAT contract: every new inference/concept gets positive + negative
tests)."""

from __future__ import annotations

import pytest

from detailgen.spec.compiler import SpecCompileError, compile_spec
from detailgen.spec.loader import load_spec_text
from detailgen.spec.serialize import dump_json, dump_yaml
from detailgen.spec.metrics import compute_metrics, format_metrics


def _build(text):
    detail = compile_spec(load_spec_text(text))
    detail.build()
    return detail


# -- repeat: expansion + derived count ---------------------------------------

_DECK = """
name: t
units: in
params: {board_w: 5.5, deck_width: 33.0}
derived: {n_deck: '= deck_width / board_w'}
components:
  - repeat: {var: j, count: '= n_deck'}
    body:
      - id: 'deck_{j}'
        type: deck_board
        name: 'deck {j}'
        params: {length: "48 in"}
        place: {raw: {at: [0, '= -deck_width/2 + j*board_w', "28 in"]}}
"""


def test_repeat_expands_over_a_derived_count():
    detail = _build(_DECK)
    parts = [p.name for p in detail.assembly.parts]
    assert parts == [f"deck {j}" for j in range(6)]           # count DERIVED = 6
    ys = [round(p.world_frame.origin[1], 2) for p in detail.assembly.parts]
    assert ys == [-419.1, -279.4, -139.7, 0.0, 139.7, 279.4]  # -deck_width/2 + j*board_w


def test_repeat_index_binds_into_ids_names_and_expressions():
    detail = _build(_DECK)
    # a metric split that proves the AUTHORED blocks (1 template) differ from
    # the BUILT parts (6) — the compression the construct buys.
    m = compute_metrics(load_spec_text(_DECK), detail)
    assert m["components"] == 1 and m["built_parts"] == 6 and m["repeat_blocks"] == 1


def test_headline_compression_excludes_escape_hatch_and_bookkeeping_facts():
    """The HEADLINE ratio counts only genuine inference. `_DECK` builds 6 deck
    boards via a repeat, each RAW-placed, so it has BOTH non-inference kinds:
    6 escape-hatch facts (`spec.placement.raw`, placeholder — restate geometry,
    rev-specplat rec 2) AND 6 bookkeeping facts (`spec.repeat.instance` — one
    per part echoing its loop index, restating structure, rev-cleanup ruling).
    Neither may count toward the honest numerator; both inflate raw-inclusive."""
    detail = _build(_DECK)
    m = compute_metrics(load_spec_text(_DECK), detail)
    assert m["escape_hatch_facts"] == 6             # one per raw placement
    assert m["bookkeeping_facts"] == 6             # one per repeated part
    assert (m["genuine_derived_facts"]
            == m["derived_facts"] - 6 - 6)
    # a bookkeeping fact scales with part count but must NOT lift the headline:
    # the honest ratio is strictly below the raw-inclusive one.
    assert m["compression"] < m["compression_raw_inclusive"]
    text = format_metrics(m)
    assert "genuine derived" in text and "raw escape-hatch" in text
    assert "bookkeeping facts" in text and "raw-inclusive" in text


def test_repeat_instance_facts_are_never_in_the_genuine_numerator():
    """rev-cleanup: the per-part `spec.repeat.instance` facts scale with part
    count, so as the loop grows they must not lift the genuine-derived count —
    they land in the bookkeeping bucket, one per built part, always."""
    detail = _build(_NEST)                          # 2 x 3 = 6 built parts
    m = compute_metrics(load_spec_text(_NEST), detail)
    assert m["bookkeeping_facts"] == 6
    inst = [f for f in detail._spec_log if f.rule == "spec.repeat.instance"]
    assert len(inst) == m["bookkeeping_facts"]
    # every one of them is excluded from the genuine numerator
    assert all(f.confidence == "inferred" for f in inst)  # not mislabelled uncertain


def test_repeat_nests():
    text = """
name: t
units: in
components:
  - repeat: {var: k, count: 2}
    body:
      - repeat: {var: i, count: 3}
        body:
          - id: 's_{k}_{i}'
            type: structural_screw
            name: 'screw {k} {i}'
            params: {diameter: "0.157 in", length: "1.5 in"}
            place: {raw: {at: ['= k*10', '= i*2', 0]}}
"""
    detail = _build(text)
    assert len(detail.assembly.parts) == 6
    got = {p.name: [round(c, 3) for c in p.world_frame.origin] for p in detail.assembly.parts}
    assert got["screw 1 2"][0] == round(10 * 25.4, 3)   # k=1 -> x=10in
    assert got["screw 1 2"][1] == round(4 * 25.4, 3)    # i=2 -> y=4in


# -- repeat: per-instance provenance back-link (rev-specplat rec 1, P1) -------

_NEST = """
name: t
units: in
components:
  - repeat: {var: k, count: 2}
    body:
      - repeat: {var: i, count: 3}
        body:
          - id: 's_{k}_{i}'
            type: structural_screw
            name: 'screw {k} {i}'
            params: {diameter: "0.157 in", length: "1.5 in"}
            place: {raw: {at: ['= k*10', '= i*2', 0]}}
"""


def test_repeat_instance_backlinks_each_part_to_its_index():
    """The single ``spec.repeat.expand`` fact says a repeat ran N times but not
    which built part is which iteration; ``spec.repeat.instance`` threads
    ``{var}={index}`` into every repeated part's provenance so a specific
    instance is as traceable as a hand placement."""
    detail = _build(_DECK)
    inst = [f for f in detail._spec_log if f.rule == "spec.repeat.instance"]
    facts = {f.fact for f in inst}
    assert len(inst) == 6                                   # one per built part
    assert "component 'deck_0' is repeat instance {j}=0" in facts
    assert "component 'deck_5' is repeat instance {j}=5" in facts
    # each fact concerns exactly its own part, by real Placed.id — so the
    # back-link is usable (not a dangling string): the subjects cover every part
    subjects = {f.subjects[0] for f in inst}
    assert all(len(f.subjects) == 1 for f in inst)
    assert subjects == {p.id for p in detail.assembly.parts}


def test_repeat_instance_threads_full_nested_coordinate():
    """A part inside nested repeats traces to BOTH loop indices, outer→inner,
    so it pins to a single cell of the loop nest (not just 'some k, some i')."""
    detail = _build(_NEST)
    inst = {f.fact for f in detail._spec_log if f.rule == "spec.repeat.instance"}
    assert "component 's_1_2' is repeat instance {k}=1, {i}=2" in inst
    assert sum(1 for _ in inst) == 6                        # 2 x 3 cells


# -- repeat: teaching diagnostics --------------------------------------------

def _err(text):
    with pytest.raises(SpecCompileError) as e:
        _build(text)
    return str(e.value)


def test_repeat_non_integer_count_is_a_diagnostic():
    msg = _err("""
name: t
units: in
params: {w: 10.0}
components:
  - repeat: {var: j, count: '= w / 3'}
    body: [{id: 'd_{j}', type: deck_board, params: {length: "48 in"}}]
""")
    assert "non-negative whole number" in msg and "floor" in msg


def test_repeat_negative_count_is_a_diagnostic():
    msg = _err("""
name: t
units: in
components:
  - repeat: {var: j, count: -2}
    body: [{id: 'd_{j}', type: deck_board, params: {length: "48 in"}}]
""")
    assert "non-negative" in msg


def test_repeat_var_shadowing_a_dimension_is_a_diagnostic():
    msg = _err("""
name: t
units: in
params: {k: 5.0}
components:
  - repeat: {var: k, count: 2}
    body: [{id: 'd_{k}', type: deck_board, params: {length: "48 in"}}]
""")
    assert "shadows" in msg and "k" in msg


def test_unknown_template_var_is_a_diagnostic():
    msg = _err("""
name: t
units: in
components:
  - repeat: {var: k, count: 2}
    body: [{id: 'd_{j}', type: deck_board, params: {length: "48 in"}}]
""")
    assert "{j}" in msg and "no loop variable" in msg


def test_repeat_body_without_var_token_collides_on_every_iteration():
    msg = _err("""
name: t
units: in
components:
  - repeat: {var: k, count: 2}
    body: [{id: fixed, type: deck_board, params: {length: "48 in"}}]
""")
    assert "duplicate component id" in msg


# -- validation: authored bearings / bonds + new measures --------------------

def test_authored_bearing_and_bond_compile_and_validate():
    text = """
name: t
units: in
params: {}
components:
  - id: a
    type: lumber
    name: a
    params: {nominal: "2x6", length: "24 in"}
    place: {raw: {at: [0, 0, 0]}}
  - id: b
    type: lumber
    name: b
    params: {nominal: "2x6", length: "24 in"}
    place: {raw: {at: [0, "1.5 in", 0]}}
validation:
  bearings:
    - {a: a, b: b, axis: Y, area: 100}
  bonds:
    - {a: a, b: b}
"""
    detail = compile_spec(load_spec_text(text))
    spec = detail.validation_spec()
    assert "bearings" in spec and "bonds" in spec
    assert spec["bearings"][0][2] == "Y" and spec["bearings"][0][3] == 100
    assert len(spec["bonds"]) == 1


def test_bearing_unknown_part_is_a_teaching_diagnostic():
    detail = compile_spec(load_spec_text("""
name: t
units: in
components:
  - id: a
    type: lumber
    name: a
    params: {nominal: "2x6", length: "24 in"}
    place: {raw: {at: [0, 0, 0]}}
validation:
  bearings:
    - {a: a, b: nope, axis: Y, area: 100}
"""))
    with pytest.raises(SpecCompileError) as e:
        detail.validation_spec()   # bearings resolve here, not at build
    assert "unknown component id 'nope'" in str(e.value)


def test_span_and_mid_measures_resolve():
    from detailgen.spec.compiler import _BBOX_MEASURES
    assert set(_BBOX_MEASURES) >= {"xlen", "ylen", "zlen", "xmid", "ymid", "zmid"}


# -- round-trip identity with repeat + bearings/bonds ------------------------

def test_repeat_and_validation_round_trip():
    doc = load_spec_text(_DECK)
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc
