"""Tests for the ``install:`` spec surface (task INSTALL v1, schema branch):
loading (strict keys, teaching errors, closed vocabularies), serialization
round-trip (omit-defaults identity), and compilation (value-language lengths
through the Resolver, ``{var}`` interpolation inside ``repeat:`` bodies, the
override map passed INTO the built Connection — never doc-side)."""

import pytest
import yaml

from detailgen.core import IN
from detailgen.assemblies.installation import (
    EntryFace, PROVENANCE_AUTHORED, PROVENANCE_TYPE_DEFAULT)
from detailgen.spec.compiler import SpecCompileError, compile_spec
from detailgen.spec.loader import load_spec_text
from detailgen.spec.schema import InstallSpec, SpecSchemaError
from detailgen.spec.serialize import dump_yaml, spec_to_dict


# -- fixtures -----------------------------------------------------------------


def _screw(cid, name, y):
    return {"id": cid, "type": "structural_screw", "name": name,
            "params": {"diameter": "0.25 in", "length": "$screw_len"},
            "place": {"raw": {"at": ["1 in", f"{y} in", "1 in"]}}}


def _base_doc(install=None):
    """A minimal cleat_screwed spec (two members, two screws), optionally
    carrying an ``install:`` block on its one connection."""
    conn = {"type": "cleat_screwed", "label": "cleat to side",
            "params": {"n_screws": 2},
            "parts": ["cleat", "side"], "hardware": ["s0", "s1"]}
    if install is not None:
        conn["install"] = install
    return {
        "name": "install surface", "units": "in",
        "params": {"screw_len": 1.5},
        "components": [
            {"id": "cleat", "type": "lumber", "name": "cleat",
             "params": {"nominal": "2x4", "length": "4 in"},
             "place": {"raw": {"at": ["0 in", "0 in", "0 in"]}}},
            {"id": "side", "type": "lumber", "name": "side",
             "params": {"nominal": "2x6", "length": "12 in"},
             "place": {"raw": {"at": ["2 in", "0 in", "0 in"]}}},
            _screw("s0", "screw 0", 1), _screw("s1", "screw 1", 2),
        ],
        "connections": [conn],
    }


_FULL_INSTALL = {
    "method": "pocket_screw",
    "entry": {"part": "cleat", "face": "inner_face"},
    "angle": 15,
    "exit": "concealed_exit",
    "exit_faces": [{"part": "side", "face": "outer_face"}],
    "embedment": "= screw_len / 2",
    "head": "recessed_in_pocket",
    "tool": {"length": "6 in", "dia": "1 in"},
    "stage": "own_connection",
}


def _load(doc):
    return load_spec_text(yaml.safe_dump(doc))


def _load_install(install):
    (conn,) = _load(_base_doc(install)).connections
    return conn.install


# -- loading ------------------------------------------------------------------


def test_full_install_block_loads():
    i = _load_install(_FULL_INSTALL)
    assert isinstance(i, InstallSpec)
    assert i.method == "pocket_screw"
    assert (i.entry_part, i.entry_face) == ("cleat", "inner_face")
    assert i.angle == 15
    assert i.exit == "concealed_exit"
    assert i.exit_faces == (("side", "outer_face"),)
    assert i.embedment == "= screw_len / 2"  # RAW — the compiler resolves
    assert i.head == "recessed_in_pocket"
    assert (i.tool_length, i.tool_dia) == ("6 in", "1 in")
    assert i.role == ""


def test_omitted_install_is_none():
    (conn,) = _load(_base_doc()).connections
    assert conn.install is None


def test_unknown_install_key_teaches_with_did_you_mean():
    with pytest.raises(SpecSchemaError, match="embedment"):
        _load_install({"method": "toe_screw", "embedmint": "1 in"})


def test_bad_head_vocabulary_teaches():
    with pytest.raises(SpecSchemaError, match="flush_countersunk"):
        _load_install({"head": "countersunk"})


def test_bad_exit_vocabulary_teaches():
    with pytest.raises(SpecSchemaError, match="through_exit_required"):
        _load_install({"exit": "through"})


def test_exit_faces_without_a_matching_exit_teaches():
    with pytest.raises(SpecSchemaError, match="exit_faces only accompany"):
        _load_install({"exit": "none",
                       "exit_faces": [{"part": "side", "face": "outer_face"}]})


def test_concealed_exit_requires_its_face_set():
    with pytest.raises(SpecSchemaError, match="REQUIRES exit_faces"):
        _load_install({"exit": "concealed_exit"})


def test_angle_out_of_range_teaches():
    with pytest.raises(SpecSchemaError, match=r"\[0, 90\)"):
        _load_install({"angle": 90})
    with pytest.raises(SpecSchemaError, match="degrees"):
        _load_install({"angle": "steep"})


def test_empty_install_block_is_rejected():
    with pytest.raises(SpecSchemaError, match="at least one contract field"):
        _load_install({})
    with pytest.raises(SpecSchemaError, match="at least one contract field"):
        _load_install({"role": "cleat_screws"})


def test_tool_requires_both_length_and_dia():
    with pytest.raises(SpecSchemaError, match="dia"):
        _load_install({"tool": {"length": "6 in"}})


def test_entry_requires_part_and_face():
    with pytest.raises(SpecSchemaError, match="face"):
        _load_install({"entry": {"part": "cleat"}})


# -- round-trip ---------------------------------------------------------------


def test_install_round_trips_identically():
    doc = _load(_base_doc(_FULL_INSTALL))
    dumped = spec_to_dict(doc)
    assert load_spec_text(yaml.safe_dump(dumped)) == doc
    # and only the authored keys are emitted (omit-defaults convention)
    emitted = dumped["connections"][0]["install"]
    assert emitted == _FULL_INSTALL
    # byte-stable re-dump
    text = dump_yaml(doc)
    assert dump_yaml(load_spec_text(text)) == text


def test_partial_install_round_trip_stays_minimal():
    doc = _load(_base_doc({"method": "toe_screw", "role": "cleat_screws"}))
    emitted = spec_to_dict(doc)["connections"][0]["install"]
    assert emitted == {"method": "toe_screw", "role": "cleat_screws"}
    assert load_spec_text(yaml.safe_dump(spec_to_dict(doc))) == doc


# -- compilation --------------------------------------------------------------


def test_compiler_passes_install_into_the_connection():
    det = compile_spec(_load(_base_doc(_FULL_INSTALL)))
    (conn,) = det.connections()
    (fields,) = conn.install.values()
    cleat = det["cleat"]
    side = det["side"]
    assert fields["entry_face"] == EntryFace(cleat.id, "inner_face")
    assert fields["exit"].condition == "concealed_exit"
    assert fields["exit"].faces == (EntryFace(side.id, "outer_face"),)
    # value language resolved to mm through the Resolver
    assert fields["embedment"] == pytest.approx(0.75 * IN)
    assert fields["tool_envelope"].length == pytest.approx(6 * IN)
    assert fields["tool_envelope"].dia == pytest.approx(1 * IN)
    # angle 15 => angled tool axis, display-idealized (no angled solids yet)
    assert fields["tool_axis"].mode == "angled"
    assert fields["tool_axis"].axis_idealized
    # and the resolved contract stamps authored_override on exactly the
    # overridden fields
    checks = conn.generate_checks(det.assembly)
    (r,) = checks.installs
    pm = dict(r.provenance)
    assert pm["method"] == PROVENANCE_AUTHORED
    assert pm["exit"] == PROVENANCE_AUTHORED
    # stage was authored (as its default spelling) — still an authored field
    assert pm["stage"] == PROVENANCE_AUTHORED


def test_angle_zero_compiles_to_shank_axis():
    det = compile_spec(_load(_base_doc({"angle": 0})))
    (conn,) = det.connections()
    (fields,) = conn.install.values()
    assert fields["tool_axis"].mode == "shank"
    assert not fields["tool_axis"].axis_idealized


def test_embedment_through_passes_uninterpreted():
    det = compile_spec(_load(_base_doc({"embedment": "through"})))
    (conn,) = det.connections()
    (fields,) = conn.install.values()
    assert fields["embedment"] == "through"


def test_unknown_entry_part_is_a_compile_error():
    doc = _base_doc({"method": "toe_screw",
                     "entry": {"part": "claet", "face": "inner_face"}})
    with pytest.raises(SpecCompileError, match="claet"):
        compile_spec(_load(doc)).connections()


def test_install_resolves_inside_repeat_bodies():
    """An install: inside a repeat: body resolves per iteration — the {var}
    entry-part template and the value-language embedment both bind to the
    loop, exactly like the connection's parts/label."""
    doc = {
        "name": "repeat install", "units": "in",
        "params": {"screw_len": 1.5},
        "components": [
            {"repeat": {"var": "k", "count": 2}, "body": [
                {"id": "cleat_{k}", "type": "lumber", "name": "cleat {k}",
                 "params": {"nominal": "2x4", "length": "4 in"},
                 "place": {"raw": {"at": ["= k * 10", "0 in", "0 in"]}}},
                {"id": "side_{k}", "type": "lumber", "name": "side {k}",
                 "params": {"nominal": "2x6", "length": "12 in"},
                 "place": {"raw": {"at": ["= k * 10 + 2", "0 in", "0 in"]}}},
                _screw("s_{k}_0", "screw {k}.0", 1),
                _screw("s_{k}_1", "screw {k}.1", 2),
            ]},
        ],
        "connections": [
            {"repeat": {"var": "k", "count": 2}, "body": [
                {"type": "cleat_screwed", "label": "joint {k}",
                 "params": {"n_screws": 2},
                 "parts": ["cleat_{k}", "side_{k}"],
                 "hardware": ["s_{k}_0", "s_{k}_1"],
                 "install": {"method": "pocket_screw",
                             "entry": {"part": "cleat_{k}",
                                       "face": "inner_face"},
                             "embedment": "= screw_len / 2"}},
            ]},
        ],
    }
    det = compile_spec(_load(doc))
    conns = det.connections()
    assert [c.label for c in conns] == ["joint 0", "joint 1"]
    for k, conn in enumerate(conns):
        (fields,) = conn.install.values()
        assert fields["entry_face"] == EntryFace(det[f"cleat {k}"].id,
                                                 "inner_face")
        assert fields["embedment"] == pytest.approx(0.75 * IN)
        checks = conn.generate_checks(det.assembly)
        (r,) = checks.installs
        assert dict(r.provenance)["method"] == PROVENANCE_AUTHORED
        assert dict(r.provenance)["head"] == PROVENANCE_TYPE_DEFAULT
