"""CL-1 declaration-time semantic analysis (cl0-design.md §3.5, §8.5) + the
CONCEPTUAL acceptance test §7 Test 5.

Each seeded error is a mount mistake that, before CL-1, was discoverable only
after a full ~3-minute build+validate loop (retro R4/R6). Now each is an instant
teaching :class:`SemanticError` at COMPILE time — the class of wrongness "a
spatial/reference error found only after building geometry" is gone. The tests
assert both that the error fires and that it fires BEFORE any geometry is built.
"""

from __future__ import annotations

import pytest

from detailgen.spec.loader import load_spec_text
from detailgen.spec.compiler import compile_spec
from detailgen.spec.semantics import SemanticError

# A minimal, well-formed base: a trunk context body + one mounted beam. Each
# test mutates ONE knob to seed exactly one class of wrongness.
_HEAD = """
name: t
type: tree_attachment
units: in
params: {trunk_dia: 20.0, trunk_h: 96.0, growth_gap: 5.0, beam_len: 24.0, beam_z: 22.5}
components:
  - {id: trunk, type: tree_trunk, name: trunk, params: {diameter: "$trunk_dia", height: "$trunk_h"}}
"""


def _beam(mount_yaml, cid="beam", name="beam"):
    return (f'  - id: {cid}\n    type: lumber\n    name: "{name}"\n'
            f'    params: {{nominal: "2x6", length: "$beam_len", treated: true}}\n'
            f'    place: {{mount: {mount_yaml}}}\n')


def _compile(spec_text):
    return compile_spec(load_spec_text(spec_text))


def test_well_formed_mount_compiles():
    """The positive control: a fully-pinned mount compiles without a semantic
    error (the pass is not a blanket reject)."""
    spec = _HEAD + _beam('{to: trunk, face: inner, axis: Y, clear_by: "$growth_gap", center: [X], ground: {above: "$beam_z"}}')
    _compile(spec)  # no raise


def test_dangling_reference():
    spec = _HEAD + _beam('{to: truck, face: inner, axis: Y, clear_by: "$growth_gap", center: [X], ground: {above: "$beam_z"}}')
    with pytest.raises(SemanticError, match=r"truck.*not a declared component.*did you mean.*trunk"):
        _compile(spec)


def test_under_constrained_missing_inplane():
    # in-plane axis X pinned by nothing (no center, no raise for X).
    spec = _HEAD + _beam('{to: trunk, face: inner, axis: Y, clear_by: "$growth_gap", ground: {above: "$beam_z"}}')
    with pytest.raises(SemanticError, match=r"under-constrained.*\['X'\]"):
        _compile(spec)


def test_over_constrained_z_centered_and_raised():
    spec = _HEAD + _beam('{to: trunk, face: inner, axis: Y, clear_by: "$growth_gap", center: [X, Z], ground: {above: "$beam_z"}}')
    with pytest.raises(SemanticError, match=r"Z is both centered and grounded"):
        _compile(spec)


def test_over_constrained_ground_on_standoff_axis():
    spec = _HEAD + _beam('{to: trunk, face: base, axis: Z, flush: true, center: [X, Y], ground: {above: "$beam_z"}}')
    with pytest.raises(SemanticError, match=r"'ground' registers the base along Z.*standoff axis"):
        _compile(spec)


def test_unrealisable_mirror():
    # DOF is satisfied (X centered, Z raised), but mirror across X leaves TWO
    # candidate rotation axes {Y, Z} — not a single rigid opposite hand.
    spec = _HEAD + _beam('{to: trunk, face: inner, axis: Y, clear_by: "$growth_gap", center: [X], ground: {above: "$beam_z"}, mirror: X}')
    with pytest.raises(SemanticError, match=r"mirror 'X' cannot be realised as a single rigid rotation"):
        _compile(spec)


def test_mount_cycle():
    two = (_beam('{to: b, face: inner, axis: Y, clear_by: "$growth_gap", center: [X], ground: {above: "$beam_z"}}', cid="a", name="a")
           + _beam('{to: a, face: inner, axis: Y, clear_by: "$growth_gap", center: [X], ground: {above: "$beam_z"}}', cid="b", name="b"))
    spec = _HEAD + two
    with pytest.raises(SemanticError, match=r"cycle.*(a -> b -> a|b -> a -> b)"):
        _compile(spec)


def test_cat5_novel_overconstraint_fails_before_geometry(monkeypatch):
    """CONCEPTUAL acceptance §7 Test 5: a NOVEL spec the compiler has never seen
    — an over-constrained mount — fails at semantic-analysis time with a teaching
    error, BEFORE any geometry builds. We prove the 'before geometry' clause by
    making the geometry kernel raise if it is ever touched; the SemanticError
    must arrive first."""
    import detailgen.assemblies.assembly as asm

    def _boom(*a, **k):
        raise AssertionError("geometry was built — the semantic error did not "
                             "fire before the kernel ran")

    monkeypatch.setattr(asm.DetailAssembly, "add", _boom)
    monkeypatch.setattr(asm.DetailAssembly, "_append", _boom)
    spec = _HEAD + _beam('{to: trunk, face: inner, axis: Y, clear_by: "$growth_gap", center: [X, Z], ground: {above: "$beam_z"}}')
    with pytest.raises(SemanticError):
        _compile(spec)
