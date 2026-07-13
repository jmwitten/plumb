"""Tests for the ``sequence:`` spec surface (task SEQSCHEMA, loader/schema
plumbing slice of stepdoc-cpg-design.md §3.1 family 3, ``authored_sequence``):
loading (strict keys, teaching errors, declaration order) and the one
semantic (whole-doc) check — connection/part existence — that the loader
cannot make on its own.

No spec ships a ``sequence:`` block yet (that is the NEXT task's job); every
fixture here is test-local, mirroring ``test_install_spec_surface.py``."""

from __future__ import annotations

import pytest
import yaml

from detailgen.spec.compiler import compile_spec
from detailgen.spec.loader import load_spec_text
from detailgen.spec.schema import AuthoredStage, SequenceSpec, SpecSchemaError
from detailgen.spec.semantics import SemanticError


# -- fixtures -----------------------------------------------------------------


def _base_doc(sequence=None):
    """A minimal three-member, two-connection spec: legs A/B each screwed to
    a shared rail. No geometry is ever built by these tests (only
    ``load_spec_text``/``compile_spec`` run), so component/connection
    ``type`` strings need not resolve through a real registry."""
    doc = {
        "name": "sequence schema test",
        "components": [
            {"id": "leg_a", "type": "lumber"},
            {"id": "leg_b", "type": "lumber"},
            {"id": "rail", "type": "lumber"},
        ],
        "connections": [
            {"type": "cleat_screwed", "label": "leg a to rail",
             "parts": ["leg_a", "rail"]},
            {"type": "cleat_screwed", "label": "leg b to rail",
             "parts": ["leg_b", "rail"]},
        ],
    }
    if sequence is not None:
        doc["sequence"] = sequence
    return doc


def _load(doc):
    return load_spec_text(yaml.safe_dump(doc))


_HAPPY_SEQUENCE = {
    "stages": [
        {"name": "bench_leg_a", "connections": ["leg a to rail"],
         "why": "leg a is screwed to the rail flat on the bench, before "
                "the frame is stood up"},
        {"name": "bench_leg_b", "parts": ["leg_b"],
         "why": "leg b is set aside loose until its own screws are driven"},
        {"name": "stand_up", "connections": ["leg b to rail"], "parts": ["rail"],
         "why": "the frame is stood up and leg b's screws are driven last, "
                "clear of leg a's corridor"},
    ],
}


# -- happy path: parsed structure, declaration order, why carried ------------


def test_sequence_loads_into_typed_stages_in_declaration_order():
    doc = _load(_base_doc(_HAPPY_SEQUENCE))
    assert isinstance(doc.sequence, SequenceSpec)
    assert len(doc.sequence.stages) == 3
    assert all(isinstance(s, AuthoredStage) for s in doc.sequence.stages)
    # rule 6: stages are totally ordered by DECLARATION order — the dataclass
    # preserves it (no separate index field to drift from position).
    assert [s.name for s in doc.sequence.stages] == [
        "bench_leg_a", "bench_leg_b", "stand_up"]


def test_sequence_stage_carries_its_connections_parts_and_why():
    doc = _load(_base_doc(_HAPPY_SEQUENCE))
    first, second, third = doc.sequence.stages
    assert first.connections == ("leg a to rail",)
    assert first.parts == ()
    assert first.why == (
        "leg a is screwed to the rail flat on the bench, before the frame "
        "is stood up")
    assert second.connections == ()
    assert second.parts == ("leg_b",)
    assert third.connections == ("leg b to rail",)
    assert third.parts == ("rail",)


def test_sequence_free_spec_round_trips_to_the_empty_default():
    """A detail declaring no ``sequence:`` block loads to the empty default —
    no shipped spec authors one yet, and this must not perturb it."""
    doc = _load(_base_doc())
    assert doc.sequence == SequenceSpec()
    assert doc.sequence.stages == ()


def test_sequence_resolves_against_the_real_connections_and_parts():
    """The stage's spec-local names are exactly the doc's own connection
    'label's and component 'id's — no separate namespace, no re-typing."""
    doc = _load(_base_doc(_HAPPY_SEQUENCE))
    conn_labels = {c.label for c in doc.connections}
    part_ids = {c.id for c in doc.components}
    for stage in doc.sequence.stages:
        assert set(stage.connections) <= conn_labels
        assert set(stage.parts) <= part_ids


def test_sequence_free_detail_compiles_clean():
    """compile_spec (which runs analyze_sequence in __init__) must not choke
    on a doc with no sequence: block at all."""
    compile_spec(_load(_base_doc()))  # no error


def test_valid_sequence_compiles_clean():
    compile_spec(_load(_base_doc(_HAPPY_SEQUENCE)))  # no error


# -- rule 1: why is REQUIRED per stage ----------------------------------------


def test_stage_missing_why_key_is_a_loud_load_error():
    seq = {"stages": [{"name": "s0", "connections": ["leg a to rail"]}]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    msg = str(e.value)
    assert "why" in msg and "missing required key" in msg


def test_stage_empty_why_is_a_loud_load_error_naming_the_stage():
    seq = {"stages": [{"name": "s0", "connections": ["leg a to rail"],
                       "why": "   "}]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    msg = str(e.value)
    assert "'s0'" in msg
    assert "required" in msg and "defense" in msg  # the house rule, named


# -- rule 2: connections/parts must name something that exists ---------------


def test_stage_naming_an_unknown_connection_is_a_semantic_error():
    seq = {"stages": [{"name": "s0", "connections": ["leg a to raill"],
                       "why": "typo'd label"}]}
    with pytest.raises(SemanticError) as e:
        compile_spec(_load(_base_doc(seq)))
    msg = str(e.value)
    assert "leg a to raill" in msg and "no declared connection" in msg
    assert "leg a to rail" in msg  # did-you-mean names the real label


def test_stage_naming_an_unknown_part_is_a_semantic_error():
    seq = {"stages": [{"name": "s0", "parts": ["leg_z"],
                       "why": "typo'd id"}]}
    with pytest.raises(SemanticError) as e:
        compile_spec(_load(_base_doc(seq)))
    msg = str(e.value)
    assert "leg_z" in msg and "no declared component" in msg


def test_unknown_reference_diagnostic_fires_before_geometry_builds():
    """Like retire's, this is a declaration-time (§3.5) SemanticError, raised
    in compile __init__, before any assembly is built."""
    seq = {"stages": [{"name": "s0", "connections": ["nope"], "why": "x"}]}
    doc = _load(_base_doc(seq))
    with pytest.raises(SemanticError):
        compile_spec(doc)


# -- rule 3: stage names unique; a connection/part in >1 stage is a conflict -


def test_duplicate_stage_names_are_a_loud_load_error():
    seq = {"stages": [
        {"name": "s0", "connections": ["leg a to rail"], "why": "first"},
        {"name": "s0", "connections": ["leg b to rail"], "why": "second"},
    ]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    msg = str(e.value)
    assert "'s0'" in msg and "unique" in msg


def test_connection_claimed_by_two_stages_is_a_loud_load_error():
    seq = {"stages": [
        {"name": "s0", "connections": ["leg a to rail"], "why": "first claim"},
        {"name": "s1", "connections": ["leg a to rail"], "why": "second claim"},
    ]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    msg = str(e.value)
    assert "leg a to rail" in msg and "s0" in msg and "s1" in msg
    assert "contradictory order" in msg


def test_part_claimed_by_two_stages_is_a_loud_load_error():
    seq = {"stages": [
        {"name": "s0", "parts": ["leg_a"], "why": "first claim"},
        {"name": "s1", "parts": ["leg_a"], "why": "second claim"},
    ]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    msg = str(e.value)
    assert "leg_a" in msg and "contradictory order" in msg


def test_same_name_as_both_a_connection_and_a_part_is_not_a_conflict():
    """Connections and parts are separate namespaces (a connection 'label'
    and a component 'id' are unrelated fields elsewhere in the schema too) —
    the SAME string in one stage's connections and another's parts is not a
    double-claim over one thing."""
    seq = {"stages": [
        {"name": "s0", "connections": ["leg a to rail"], "why": "conn claim"},
        {"name": "s1", "parts": ["leg a to rail"], "why": "unrelated part id"},
    ]}
    # loads clean structurally; fails later only because "leg a to rail" is
    # not a real component id (rule 2) — proving the two lists don't collide.
    with pytest.raises(SemanticError) as e:
        compile_spec(_load(_base_doc(seq)))
    assert "no declared component" in str(e.value)


# -- rule 4: a stage listing nothing is a loud load error ---------------------


def test_stage_with_neither_connections_nor_parts_is_a_loud_load_error():
    seq = {"stages": [{"name": "s0", "why": "no target named"}]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    msg = str(e.value)
    assert "'s0'" in msg and "at least one" in msg


def test_stage_with_empty_connections_and_parts_lists_is_a_loud_load_error():
    seq = {"stages": [{"name": "s0", "connections": [], "parts": [],
                       "why": "no target named"}]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    assert "at least one" in str(e.value)


def test_sequence_block_with_zero_stages_is_a_loud_load_error():
    """A sequence: block declaring no stages claims no order over anything —
    the loader teaches the author to omit the block instead of shipping a
    silent no-op."""
    seq = {"stages": []}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    assert "empty" in str(e.value)


# -- rule 5: unknown keys are loud, and NOT special-cased ---------------------


def test_unknown_key_in_sequence_block_is_a_loud_load_error():
    seq = {"stages": [{"name": "s0", "connections": ["leg a to rail"],
                       "why": "x"}], "notes": "extra"}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    assert "unknown key 'notes'" in str(e.value)


def test_unknown_key_in_a_stage_entry_is_a_loud_load_error():
    seq = {"stages": [{"name": "s0", "connections": ["leg a to rail"],
                       "why": "x", "note": "typo of why"}]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    assert "unknown key 'note'" in str(e.value)


@pytest.mark.parametrize("key,value", [
    ("after", ["cure(leg a to rail)"]),
    ("subassemblies", [{"name": "side", "parts": ["leg_a"]}]),
    ("assembly", "bench_then_set"),
])
def test_future_staging_keys_are_not_special_cased(key, value):
    """'after:' (point constraints), 'subassemblies:'/'assembly:' (§3.4
    staging) are FUTURE keys of the sequence: language, deliberately not
    implemented in this v1-core plumbing task. They must hit the ordinary
    unknown-key error like any other typo — never a distinct "not yet
    supported" message, and never a silent no-op."""
    seq = {"stages": [{"name": "s0", "connections": ["leg a to rail"],
                       "why": "x"}], key: value}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    assert f"unknown key {key!r}" in str(e.value)


def test_after_key_on_a_stage_entry_is_also_not_special_cased():
    seq = {"stages": [{"name": "s0", "connections": ["leg a to rail"],
                       "why": "x", "after": ["cure(leg a to rail)"]}]}
    with pytest.raises(SpecSchemaError) as e:
        _load(_base_doc(seq))
    assert "unknown key 'after'" in str(e.value)


# -- landing surface: reaches the compiled surface axis-3 will consume -------


def test_specdetail_sequence_hook_returns_the_loaded_stages():
    """SpecDetail.sequence() (the Detail-base hook, task SEQSCHEMA) exposes
    the loaded+validated stages directly — the doc-level analog of
    connections()/install:, so a consumer never needs to reach back into
    doc.sequence by hand."""
    detail = compile_spec(_load(_base_doc(_HAPPY_SEQUENCE)))
    assert detail.sequence() == detail.doc.sequence.stages
    assert len(detail.sequence()) == 3


def test_sequence_free_specdetail_sequence_hook_is_empty():
    detail = compile_spec(_load(_base_doc()))
    assert detail.sequence() == ()


def test_compile_connections_lands_sequence_on_connectionchecks():
    """Mirrors how install:/edges reach ConnectionChecks.installs: a
    caller-supplied sequence must land on the SAME compiled surface
    (ConnectionChecks.sequence) the axis-3 task will read installs off of —
    unit-tested directly against compile_connections, independent of any
    buildable geometry."""
    from detailgen.assemblies.assembly import DetailAssembly
    from detailgen.assemblies.connection import compile_connections
    from detailgen.components import Lumber
    from detailgen.core import IN

    a = DetailAssembly("landing")
    part = a.add(Lumber("2x4", 4 * IN, name="a part"))
    stages = (AuthoredStage(name="s0", why="x", parts=(part.id,)),)
    checks = compile_connections(a, [], sequence=stages)
    assert checks.sequence == stages
    # CPGCORE: the landed sequence also builds onto the ONE event graph
    assert checks.event_graph is not None
    assert part.id in checks.event_graph.event_of


def test_compile_connections_stage_naming_nothing_built_is_loud():
    """Re-pinned by task CPGCORE (deliberate, to the new truth): the
    compiled surface now RESOLVES the sequence into the event graph, so a
    stage naming a part that was never built is a loud load-time teaching
    error at compile_connections — the unknown-name registry discipline,
    one level down from the spec loader's own existence check."""
    from detailgen.assemblies.assembly import DetailAssembly
    from detailgen.assemblies.connection import compile_connections

    stages = (AuthoredStage(name="s0", why="x", parts=("p",)),)
    with pytest.raises(ValueError, match="names no built part"):
        compile_connections(DetailAssembly("empty"), [], sequence=stages)


def test_compile_connections_default_sequence_is_empty():
    from detailgen.assemblies.assembly import DetailAssembly
    from detailgen.assemblies.connection import compile_connections

    checks = compile_connections(DetailAssembly("empty"), [])
    assert checks.sequence == ()
