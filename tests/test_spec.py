"""Tests for DetailSpec (Task W2-7): the declarative language, its strict
loader/diagnostics, and the compiler that turns a spec into a working Detail.

The centrepiece is the oracle proof: the rock anchor authored as
``details/rock_anchor.spec.yaml`` reproduces its FROZEN IMPERATIVE TRUTH — a
byte-identical assembly (all placed-part world transforms within 1e-6), a clean
validation, and an identical BOM. The reference side is
``tests/baselines/frozen_truth/rock_anchor.json`` (the last testimony of the
retired ``details/rock_anchor.py``, captured by ``scripts/capture_frozen_truth.py``
while both paths still existed), so the oracle keeps its teeth after the
imperative detail is gone.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.spec import (
    DetailSpecDoc,
    SpecCompileError,
    SpecSchemaError,
    SpecValueError,
    compile_spec,
    dump_json,
    dump_yaml,
    load_spec_file,
    load_spec_text,
)
from detailgen.spec.values import Resolver
from detailgen.core import IN

_REPO = Path(__file__).resolve().parents[1]
_SPEC = _REPO / "details" / "rock_anchor.spec.yaml"
_FROZEN = _REPO / "tests" / "baselines" / "frozen_truth" / "rock_anchor.json"


# -- the value language ------------------------------------------------------


def _resolver(**ns):
    return Resolver(namespace=ns, unit_factor=IN)


def test_directives_resolve_to_millimetres_lengths():
    r = _resolver(rod_embed=8.0, rod_stick=2.75)
    assert r.resolve("$rod_embed") == pytest.approx(8.0 * IN)
    assert r.resolve("= rod_embed + rod_stick") == pytest.approx(10.75 * IN)
    assert r.resolve("8 in") == pytest.approx(203.2)
    assert r.resolve("120 mm") == pytest.approx(120.0)


def test_plain_scalars_pass_through_unchanged():
    r = _resolver()
    assert r.resolve("2x6") == "2x6"
    assert r.resolve("leveling nut") == "leveling nut"
    assert r.resolve(True) is True
    assert r.resolve(1800) == 1800          # a bearing area in mm², not a length
    assert r.resolve([-90, "Y"]) == [-90, "Y"]


def test_unknown_dimension_name_suggests_did_you_mean():
    r = _resolver(rod_embed=8.0)
    with pytest.raises(SpecValueError) as e:
        r.resolve("$rod_ember")
    assert "rod_embed" in str(e.value) and "did you mean" in str(e.value)


def test_expression_rejects_arbitrary_python():
    r = _resolver(x=1.0)
    with pytest.raises(SpecValueError):
        r.resolve("= __import__('os').system('true')")
    with pytest.raises(SpecValueError):
        r.resolve("= x.bit_length()")


def test_expression_division_by_zero_is_a_diagnostic():
    r = _resolver(x=1.0)
    with pytest.raises(SpecValueError) as e:
        r.resolve("= x / 0")
    assert "zero" in str(e.value)


# -- loader diagnostics (strict) ---------------------------------------------


def _minimal(components="- {id: a, type: lumber, name: a, params: {nominal: \"2x6\", length: \"6 in\"}}"):
    return f"name: t\ncomponents:\n  {components}\n"


def test_unknown_top_level_key_suggests_did_you_mean():
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text("name: t\ncomponent: []\n")  # 'component' vs 'components'
    msg = str(e.value)
    assert "unknown key 'component'" in msg and "components" in msg


def test_missing_required_field_names_the_field():
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text("type: detail\n")  # no 'name', no 'components'
    assert "missing required key" in str(e.value)


def test_unknown_component_place_key_is_rejected_with_suggestion():
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text(
            "name: t\ncomponents:\n"
            "  - {id: a, type: lumber, name: a, place: {datum: base, too: b}}\n"
        )
    assert "too" in str(e.value) and "'to'" in str(e.value)


def test_component_needs_exactly_one_of_type_or_imperative():
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text("name: t\ncomponents:\n  - {id: a, name: a}\n")
    assert "exactly one of 'type'" in str(e.value)
    with pytest.raises(SpecSchemaError):
        load_spec_text("name: t\ncomponents:\n  - {id: a, type: lumber, imperative: x.y}\n")


def test_raw_and_mate_keys_cannot_mix():
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text(
            "name: t\ncomponents:\n"
            "  - {id: a, type: lumber, name: a, place: {raw: {at: [0,0,0]}, to: b}}\n"
        )
    assert "raw" in str(e.value)


# -- raw-placement flagging + imperative-hook logging ------------------------


def test_raw_placement_is_flagged_in_the_derivation_log():
    doc = load_spec_text(
        'name: t\nunits: in\ncomponents:\n'
        '  - id: a\n    type: lumber\n    name: a\n'
        '    params: {nominal: "2x6", length: "6 in"}\n'
        '    place: {raw: {at: ["0 in", "0 in", "3 in"], rotate: [["Y", 90]]}}\n'
    )
    detail = compile_spec(doc)
    detail.build()
    raw_facts = [f for f in detail._spec_log if f.rule == "spec.placement.raw"]
    assert len(raw_facts) == 1
    assert raw_facts[0].confidence == "placeholder"       # loud escape hatch
    assert "escape hatch" in raw_facts[0].fact


def test_imperative_hook_builds_and_is_logged_loudly():
    # The P3 escape hatch: a dotted path to any callable f(name=..., **params)
    # -> Component. A real component factory stands in for "geometry the DSL
    # cannot express" so the test needs no bespoke module on the path.
    doc = load_spec_text(
        'name: t\nunits: in\ncomponents:\n'
        '  - id: w\n    imperative: detailgen.components.Lumber\n    name: widget\n'
        '    params: {nominal: "2x6", length: "6 in"}\n'
    )
    detail = compile_spec(doc)
    detail.build()
    assert detail["widget"].component.length == pytest.approx(6 * IN)
    hooks = [f for f in detail._spec_log if f.rule == "spec.component.imperative_hook"]
    assert len(hooks) == 1 and hooks[0].confidence == "placeholder"
    assert "IMPERATIVE hook" in hooks[0].fact


def test_imperative_hook_bad_path_is_a_clear_error():
    doc = load_spec_text(
        "name: t\ncomponents:\n  - {id: w, imperative: nope.does.not.exist, name: w}\n"
    )
    with pytest.raises(SpecCompileError) as e:
        compile_spec(doc).build()
    assert "imperative hook" in str(e.value)


def test_bad_datum_name_is_a_teaching_diagnostic_with_suggestions():
    # Datum names are per-component and the easiest vocabulary to mistype; a
    # typo must list the component's real datums + did-you-mean, not leak a raw
    # KeyError from deep in the mate API.
    part_typo = load_spec_text(
        'name: t\nunits: in\ncomponents:\n'
        '  - {id: n, type: hex_nut, name: n, params: {diameter: "0.5 in"}}\n'
        '  - {id: w, type: washer, name: w, params: {inner_diameter: "0.5 in"}, '
        'place: {datum: bass, to: n, to_datum: top}}\n'
    )
    with pytest.raises(SpecCompileError) as e:
        compile_spec(part_typo).build()
    msg = str(e.value)
    assert "no datum 'bass'" in msg and "available datums" in msg
    assert "did you mean" in msg and "base" in msg

    target_typo = load_spec_text(
        'name: t\nunits: in\ncomponents:\n'
        '  - {id: n, type: hex_nut, name: n, params: {diameter: "0.5 in"}}\n'
        '  - {id: w, type: washer, name: w, params: {inner_diameter: "0.5 in"}, '
        'place: {datum: base, to: n, to_datum: topp}}\n'
    )
    with pytest.raises(SpecCompileError) as e:
        compile_spec(target_typo).build()
    assert "no datum 'topp'" in str(e.value) and "'top'" in str(e.value)


def test_yaml_on_key_footgun_gets_a_special_cased_message():
    # `on: n` is parsed by YAML 1.1 as the boolean key True; the diagnostic must
    # point at the fix (write `to:`), not emit "unknown key True".
    with pytest.raises(SpecSchemaError) as e:
        load_spec_text(
            'name: t\ncomponents:\n'
            '  - {id: w, type: washer, name: w, params: {inner_diameter: "0.5 in"}, '
            'place: {datum: base, on: n, to_datum: top}}\n'
        )
    msg = str(e.value)
    assert "boolean" in msg and "'to:'" in msg


def test_defaulted_units_is_recorded_in_the_derivation_log():
    # Omitting `units:` silently assumes inches — an author intending mm would
    # get every length 25.4x off, so P1 requires the default be logged.
    defaulted = compile_spec(load_spec_text(
        'name: t\ncomponents:\n'
        '  - {id: a, type: lumber, name: a, params: {nominal: "2x6", length: "6 in"}}\n'
    ))
    facts = [f for f in defaulted._spec_log if f.rule == "spec.units.default"]
    assert len(facts) == 1 and facts[0].confidence == "inferred"
    assert "defaulted to 'in'" in facts[0].fact

    declared = compile_spec(load_spec_text(
        'name: t\nunits: mm\ncomponents:\n'
        '  - {id: a, type: lumber, name: a, params: {nominal: "2x6", length: 152.4}}\n'
    ))
    assert not [f for f in declared._spec_log if f.rule == "spec.units.default"]
    assert [f for f in declared._spec_log if f.rule == "spec.units"][0].confidence == "official"


def test_forward_referenced_mate_target_is_a_clear_error():
    doc = load_spec_text(
        'name: t\nunits: in\ncomponents:\n'
        '  - {id: a, type: washer, name: a, params: {inner_diameter: "0.5 in"}, '
        'place: {datum: base, to: b, to_datum: top}}\n'
        '  - {id: b, type: hex_nut, name: b, params: {diameter: "0.5 in"}}\n'
    )
    with pytest.raises(SpecCompileError) as e:
        compile_spec(doc).build()
    assert "unknown component id 'b'" in str(e.value) and "declared earlier" in str(e.value)


# -- round-trip identity -----------------------------------------------------


def test_round_trip_yaml_and_json_identity():
    doc = load_spec_file(_SPEC)
    assert load_spec_text(dump_yaml(doc), fmt="yaml") == doc
    assert load_spec_text(dump_json(doc), fmt="json") == doc
    # And re-serializing the reloaded doc is byte-stable.
    assert dump_yaml(load_spec_text(dump_yaml(doc))) == dump_yaml(doc)


# -- the oracle proof: spec == frozen imperative rock anchor -----------------


def _frozen():
    return json.loads(_FROZEN.read_text())


def _fingerprint(detail):
    """Per placed part, by name: world origin + volume + bbox — API-agnostic and
    (via bbox) orientation-sensitive, so it proves the full transform, not just
    the translation. Matches the shape frozen in the corpus."""
    out = {}
    for p in detail.assembly.parts:
        wp = p.world_solid()
        solids = wp.vals()
        vol = sum(s.Volume() for s in solids)
        bb = (wp.combine().objects[0].BoundingBox() if len(solids) > 1
              else solids[0].BoundingBox())
        out[p.name] = (
            list(p.world_frame.origin),
            vol,
            [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax],
        )
    return out


def test_rock_anchor_spec_compiles_and_validates_clean():
    detail = compile_spec(load_spec_file(_SPEC))
    report = detail.validate()
    assert report.ok, str(report)
    assert len(detail.assembly.parts) == bl.load_baseline("detail_counts")["rock_anchor"]["parts"]


def test_rock_anchor_spec_matches_frozen_transforms_to_1e_6():
    spec = compile_spec(load_spec_file(_SPEC))
    spec.build()
    fs = _fingerprint(spec)
    ff = _frozen()["geom_fingerprint"]
    assert set(ff) == set(fs), (
        f"part-name mismatch: only frozen={sorted(set(ff)-set(fs))[:5]}, "
        f"only spec={sorted(set(fs)-set(ff))[:5]}")
    worst = 0.0
    for name in ff:
        oi, vi, bi = ff[name]
        os_, vs, bs = fs[name]
        for a, b in zip(oi, os_):
            worst = max(worst, abs(a - b))
        worst = max(worst, abs(vi - vs))
        for a, b in zip(bi, bs):
            worst = max(worst, abs(a - b))
    assert worst <= 1e-6, f"worst transform/geometry deviation {worst} mm > 1e-6"


def test_rock_anchor_spec_bom_equivalent_to_frozen():
    spec = compile_spec(load_spec_file(_SPEC))
    bs = spec.bom_table()
    bf = _frozen()["bom"]
    assert len(bs) == len(bf)
    for rs, rf in zip(bs, bf):
        for k in rf:
            if k == "length_mm" and rf[k] is not None and rs[k] is not None:
                # a real length: identical to the SAME 1e-6 geometric bar the
                # transforms use (raw floats differ by <=2e-13 mm from inch->mm
                # conversion ordering — GEOMETRY, still tolerance-equal).
                assert abs(rs[k] - rf[k]) <= 1e-6
            else:
                assert rs[k] == rf[k], f"BOM field {k!r}: {rs[k]!r} != {rf[k]!r}"


def test_rock_anchor_spec_generates_connection_checks():
    # The bearings/overlaps/bonds are GENERATED from the declared connections
    # via the standard Detail.validate path — the derivation log must carry
    # the Connection-rule facts, not just the spec-level placement facts.
    detail = compile_spec(load_spec_file(_SPEC))
    detail.validate()
    rules = {f.rule for f in detail.derivation_report()}
    assert "ThreadedRodEpoxyAnchor.bearing_pairs" in rules
    assert "BoltedClamp.edges" in rules
    assert "spec.placement.mate" in rules


# -- negative: a detached declared connection FAILS through the compiled path -


def test_detached_connection_bearing_fails_validation():
    # Open a 3 mm standoff under an angle's upper fender washer so it no longer
    # bears on the parts the ThreadedRodEpoxyAnchor connection REQUIRES it to
    # touch. A Connection-generated bearing proves contact, so this must FAIL —
    # the trolley-review non-negotiable, now flowing through the spec compiler.
    doc = load_spec_file(_SPEC)
    components = []
    for c in doc.components:
        if c.id == "fender_washer_up_0":
            c = replace(c, place=replace(c.place, offset=("0 in", "0 in", "3 mm")))
        components.append(c)
    detached = replace(doc, components=components)

    report = compile_spec(detached).validate()
    assert not report.ok
    bearing_fails = [f for f in report.failures if f.check == "bearing"]
    assert bearing_fails, "expected a REQUIRED-bearing failure from the detached washer"
