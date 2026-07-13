"""Tests for the parameterizable ``Detail`` base class (Task 3).

These exercise the framework contract itself — lifecycle enforcement, the
base-owned handle registry, param-derived dimension callouts, and BOM
single-sourcing — against a deliberately cheap two-block detail so the suite
stays fast. The real rock anchor is covered end-to-end in ``test_smoke`` and by
the oracle fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from detailgen.core import DEFAULT, IN, Tolerances
from detailgen.components import Lumber
from detailgen.assemblies import DetailAssembly, Placed
from detailgen.details import Detail, Callout
from detailgen.details.base import fmt_frac_in


@dataclass(frozen=True)
class _StackParams:
    gap: float = 4.0     # inches between the two blocks along Z
    size: float = 2.0    # block length (inches)


class _Stack(Detail):
    """Two 2x4 blocks, the upper one lifted ``gap`` inches. gap>=depth (3.5")
    separates them (clean); gap=0 makes them coincide (interference failure)."""

    name = "stack"
    Params = _StackParams

    def assemble(self, d: DetailAssembly) -> None:
        P = self.params
        d.add(Lumber("2x4", P.size * IN, name="a"))
        d.add(Lumber("2x4", P.size * IN, name="b"), at=(0, 0, P.gap * IN))

    def callouts(self):
        return [Callout("gap", "{v} GAP", p0=(0, 0, 0),
                        p1=lambda p: (0, 0, p.gap * IN))]


@dataclass(frozen=True)
class _ContactParams:
    tol: Tolerances = DEFAULT


class _ContactStack(Detail):
    """Two 2x4 blocks with a fixed 0.6mm bbox gap in Y, checked via
    ``contacts`` rather than interference. Exists only to prove
    ``validation_spec()["tol"]`` actually reaches ``validate_assembly`` through
    the ``Detail`` lifecycle (mirrors the tolerance-override pattern in
    ``test_config.py``, one seam higher)."""

    name = "contact-stack"
    Params = _ContactParams

    def assemble(self, d: DetailAssembly) -> None:
        d.add(Lumber("2x4", 6 * IN, name="a"))
        d.add(Lumber("2x4", 6 * IN, name="b"), at=(0, 1.5 * IN + 0.6, 0))

    def validation_spec(self) -> dict:
        return {"contacts": [(self["a"], self["b"])], "tol": self.params.tol}


class _SelfRefStack(_Stack):
    """Reads an already-placed part via ``self[...]`` *during* ``assemble`` —
    exercises the mid-assembly registry (must not recurse into build)."""

    def assemble(self, d: DetailAssembly) -> None:
        P = self.params
        d.add(Lumber("2x4", P.size * IN, name="a"))
        assert self["a"].name == "a"          # mid-assembly lookup, no recursion
        d.add(Lumber("2x4", P.size * IN, name="b"), at=(0, 0, P.gap * IN))


# -- fractional-inch formatter ------------------------------------------------

@pytest.mark.parametrize("value,text", [
    (8.0, '8"'), (4.5, '4-1/2"'), (0.5, '1/2"'), (2.75, '2-3/4"'),
    (0.0, '0"'),
    # Float-imprecision carry: a hair BELOW a whole inch (the side an
    # mm->in round-trip actually lands on, e.g. math.nextafter(48.0, -inf))
    # must round UP and carry, not split-before-round into "N-1/1". Values
    # a hair ABOVE the whole number don't exercise this: round-then-split
    # already lands on the whole part with no carry needed either way.
    (47.99999999999999, '48"'), (11.999999999999998, '12"'),
    (2.9999999999999996, '3"'), (-47.99999999999999, '-48"'),
])
def test_fmt_frac_in(value, text):
    assert fmt_frac_in(value) == text


# -- handle registry (base-owned; kills the (detail, handles) tuple) ----------

def test_handle_registry_retrieves_placed_by_name():
    s = _Stack()
    a = s["a"]
    assert isinstance(a, Placed)
    assert a.name == "a"
    assert s["b"].name == "b"


def test_handle_registry_raises_on_unknown_key():
    s = _Stack()
    with pytest.raises(KeyError):
        s["nope"]


def test_build_returns_same_assembly_each_call():
    s = _Stack()
    assert s.build() is s.build()
    assert s.assembly is s.build()


def test_self_reference_during_assemble_does_not_recurse():
    # build() registers the assembly before assemble() runs, so a subclass may
    # read an already-placed part via self["a"] mid-assembly without recursing.
    s = _SelfRefStack(gap=4.0)
    assert s["b"].name == "b"        # builds cleanly (no RecursionError)
    assert s.validate().ok


# -- lifecycle enforcement: no export without a clean validation --------------

def test_dirty_detail_cannot_render(tmp_path):
    s = _Stack(gap=0.0)                 # blocks coincide -> interference
    assert s.validate().ok is False
    with pytest.raises(AssertionError):
        s.render(tmp_path / "dirty")


def test_render_without_prior_validate_auto_validates_and_gates(tmp_path):
    # A fresh detail has no report; render() must validate before it will
    # write anything, and a dirty one must still raise.
    s = _Stack(gap=0.0)
    assert s.report is None
    with pytest.raises(AssertionError):
        s.render(tmp_path / "auto")
    assert not (tmp_path / "auto").exists()          # nothing created at all


def test_no_public_export_verb_bypasses_the_gate(tmp_path):
    # Structural enforcement: render() is the ONLY public export path, and it is
    # gated. The file-writing hooks are non-public so a dirty detail cannot be
    # exported through any public verb.
    assert not hasattr(Detail, "export")             # renamed to _export
    assert not hasattr(Detail, "document")           # renamed to _document
    assert hasattr(Detail, "_export") and hasattr(Detail, "_document")

    s = _Stack(gap=0.0)                               # dirty
    export_verbs = [name for name in vars(Detail)
                    if not name.startswith("_") and name in {"export", "document", "render"}]
    assert export_verbs == ["render"]                # nothing else public writes
    with pytest.raises(AssertionError):
        s.render(tmp_path / "d")
    assert not list(tmp_path.iterdir())              # zero files written


def test_clean_detail_renders(tmp_path):
    s = _Stack(gap=4.0)                 # separated -> clean
    assert s.report is None
    out = s.render(tmp_path / "clean")
    assert s.report is not None and s.report.ok
    assert (out / "stack.step").exists()


# -- one class, many sizes ----------------------------------------------------

def test_same_class_two_sizes_scales_geometry():
    small = _Stack(size=2.0).assembly
    big = _Stack(size=6.0).assembly
    sx = small._resolve("a").world_solid().val().BoundingBox().xlen
    bx = big._resolve("a").world_solid().val().BoundingBox().xlen
    assert bx > sx
    assert round(bx - sx, 6) == round(4.0 * IN, 6)


# -- callouts auto-derive their text from the live param value ----------------

def test_callout_text_tracks_param_value():
    assert _Stack(gap=4.0).rendered_callouts()[0]["label"] == '4" GAP'
    assert _Stack(gap=2.5).rendered_callouts()[0]["label"] == '2-1/2" GAP'


def test_callout_placement_tracks_param_value():
    c = _Stack(gap=3.0).rendered_callouts()[0]
    assert c["p1"] == [0.0, 0.0, 3.0 * IN]


# -- tolerances flow through validation_spec() --------------------------------

def test_tolerances_flow_from_validation_spec_through_validate():
    """A 0.6mm bbox gap fails DEFAULT's contact_bbox_tolerance (0.5mm) but
    passes a detail-supplied Tolerances that widens it to 1.0mm — proving the
    whole Detail -> validate() -> validate_assembly() chain honors
    validation_spec()["tol"], not just validate_assembly itself."""
    tight = _ContactStack()
    assert tight.validate().ok is False

    loose = _ContactStack(tol=replace(DEFAULT, contact_bbox_tolerance=1.0))
    assert loose.validate().ok is True


# -- BOM single source of truth -----------------------------------------------

def test_bom_paths_agree_on_shared_fields():
    s = _Stack()
    detail_bom = {row["id"]: row for row in s.bom()}
    table = s.bom_table()
    # every id in the table's groups is a real part, and its material matches
    # the per-part BOM row for that same part (both derive from one row source)
    seen_ids = set()
    for group in table:
        for pid in group["ids"]:
            assert pid in detail_bom
            assert detail_bom[pid]["material"] == group["material"]
            seen_ids.add(pid)
    assert seen_ids == set(detail_bom)          # nothing dropped or invented
    assert sum(g["qty"] for g in table) == len(detail_bom)
