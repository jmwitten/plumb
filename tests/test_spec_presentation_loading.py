"""Task 4B-2: STRICT loading + teaching errors + round-trip for the five new
presentation blocks (callouts / explode / doc / cross_check / export), matching
the rest of the spec loader's culture — an unknown key is a hard did-you-mean
diagnostic, a missing required key names the field, and ``load(dump(doc))``
round-trips every block."""

from __future__ import annotations

import pytest

from detailgen.spec.loader import load_spec_text
from detailgen.spec.schema import SpecSchemaError
from detailgen.spec.serialize import dump_json, dump_yaml

_BASE = """
name: t
units: in
params: {a: 2.0}
components:
  - {id: p, type: boulder, name: p, params: {width: 1, length: 1, depth: 1}}
"""


def _doc(extra: str):
    return load_spec_text(_BASE + extra)


# -- round-trip every block ---------------------------------------------------


def test_all_presentation_blocks_round_trip():
    doc = _doc("""
callouts:
  - {param: a, label: "{v} X", p0: ["= a", 0, 0], p1: ["= a", 0, "= a"]}
explode:
  - {id: p, vector: [0, "= a", 0]}
cross_check: {ref: detailgen.spec.crosschecks.rock_anchor_solver}
export: {glb_tolerance: 0.08, glb_angular_tolerance: 0.12, inject_explode: true, explode_authoring_units: true}
doc:
  sections:
    - prose: |
        # Title
        - a is {a:.1f}
    - findings: {header: "## F", check: bearing}
    - derivation_log: {header: "## D", preamble: "pre", mode: per_connection, cap: 3}
    - hardware_presence: {header: "## H", cap: 2}
    - bom_table: {header: "## B"}
""")
    assert load_spec_text(dump_yaml(doc)) == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc


# -- strict keys + did-you-mean ----------------------------------------------


def test_callout_unknown_key_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("callouts:\n  - {param: a, p0: [0,0,0], p1: [0,0,0], labl: x}\n")
    assert "unknown key 'labl'" in str(e.value) and "label" in str(e.value)


def test_callout_missing_endpoint_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("callouts:\n  - {param: a, p0: [0,0,0]}\n")
    assert "missing required key 'p1'" in str(e.value)


def test_callout_bad_point_shape_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("callouts:\n  - {param: a, p0: [0,0], p1: [0,0,0]}\n")
    assert "3-element" in str(e.value)


def test_explode_missing_vector_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("explode:\n  - {id: p}\n")
    assert "missing required key 'vector'" in str(e.value)


def test_cross_check_requires_ref():
    with pytest.raises(SpecSchemaError) as e:
        _doc("cross_check: {reff: x}\n")
    assert "unknown key 'reff'" in str(e.value)


def test_export_missing_required_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("export: {glb_tolerance: 0.1}\n")
    assert "missing required key 'glb_angular_tolerance'" in str(e.value)


def test_doc_unknown_section_kind_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("doc:\n  sections:\n    - findings_: {header: h, check: bearing}\n")
    msg = str(e.value)
    assert "unknown section kind 'findings_'" in msg and "findings" in msg


def test_doc_section_not_single_key_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("doc:\n  sections:\n    - {prose: a, bom_table: {header: h}}\n")
    assert "single-key mapping" in str(e.value)


def test_derivation_log_bad_mode_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("doc:\n  sections:\n    - derivation_log: {header: h, mode: firstn}\n")
    assert "'first_n' or 'per_connection'" in str(e.value)


def test_findings_section_missing_check_teaches():
    with pytest.raises(SpecSchemaError) as e:
        _doc("doc:\n  sections:\n    - findings: {header: h}\n")
    assert "missing required key 'check'" in str(e.value)


def test_findings_section_unknown_check_kind_teaches():
    # an unknown check name would silently render an empty section — reject it
    # with a did-you-mean over the known kinds (a typo for 'bearing').
    with pytest.raises(SpecSchemaError) as e:
        _doc("doc:\n  sections:\n    - findings: {header: h, check: bearng}\n")
    msg = str(e.value)
    assert "unknown check kind 'bearng'" in msg and "'bearing'" in msg


def test_findings_section_known_check_kinds_accepted():
    # every renderable kind loads without error (guards against the list drifting
    # out of sync with what a real detail's report renders).
    for kind in ("bearing", "through_hole", "floating", "contact", "dimension",
                 "connection_hardware"):
        _doc(f"doc:\n  sections:\n    - findings: {{header: h, check: {kind}}}\n")
