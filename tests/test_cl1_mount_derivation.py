"""CL-1 derivation-table goldens (cl0-design.md §8.7 — executable
documentation), determinism (§8.7 byte-stable), and the CONCEPTUAL acceptance
test §7 Test 2 (mount a part by relation; the transform, contact, evidence and
doc all derive from the one declaration — a raw transform is UNNECESSARY, and a
hand transform silently disagreeing with a hand bearing is UNWRITABLE).
"""

from __future__ import annotations

from pathlib import Path

from detailgen.core.units import IN
from detailgen.components.lumber import Lumber
from detailgen.components.tree import TreeTrunk
from detailgen.spec.lowering import lower_mount
from detailgen.spec.schema import MountSpec
from detailgen.spec.loader import load_spec_file
from detailgen.spec.compiler import compile_spec

ROOT = Path(__file__).resolve().parents[1]
CAT2 = ROOT / "tests" / "fixtures" / "cl1" / "mount_bearing.spec.yaml"
TREE = ROOT / "details" / "tree_attachment.spec.yaml"


def _round(v, n=6):
    return tuple(round(c, n) for c in v)


# -- §8.7 derivation-table golden -------------------------------------------
# The full seven-field derivation table for the tree beam's MOUNT (the mirrored
# -Y hand — the one that derives a rotation), asserted for a fixture declaration.
# This is executable documentation: change what a mount derives and this fails.

def test_derivation_table_golden_mirrored_beam():
    beam = Lumber("2x6", length=24 * IN, treated=True, ease_radius=0.125 * IN,
                  full_length=60 * IN, name="beam -Y")
    trunk = TreeTrunk(diameter=20 * IN, height=96 * IN)
    mount = MountSpec(to="trunk", face="inner", axis="Y", clear_by="$growth_gap",
                      center=("X",), ground="$beam_z", mirror="Y")
    low = lower_mount(
        mount, face_datum=beam.datum("face_near"), base_datum=beam.datum("base"),
        target_frame=trunk.datum("axis"), surface_offset=10 * IN,
        clear_by=5 * IN, offset=None, ground_above=22.5 * IN)

    # field 2 — the derived transform (translation AND rotation):
    assert _round(low.world_frame.origin) == (304.8, -381.0, 571.5)
    assert _round(low.world_frame.x_axis) == (-1.0, 0.0, 0.0)
    assert _round(low.world_frame.y_axis) == (0.0, -1.0, 0.0)
    assert _round(low.world_frame.z_axis) == (0.0, 0.0, 1.0)
    # the base (un-mirrored) hand, for inspection of the mirror derivation:
    assert _round(low.base_frame.origin) == (-304.8, 381.0, 571.5)
    assert low.rotated is True                       # rotation was DERIVED
    assert low.grounded is True                       # base pinned above grade (R3)
    # field 3 — no contact: `clear_by` is a standoff (a gap), not face-area
    # registration, so no bearing/bond is derived (the clearance INVARIANT is a
    # CL-2 feature verb; here the fragment declares none):
    assert low.contact is None
    # field 4 — the dependency edge (who this part registers against):
    assert low.evidence_ref == "trunk"
    # field 5 — the derived placement sentence (incl. the grounding fact):
    assert low.doc_sentence == (
        "opposite-hand inner face a gap clear of trunk (along Y) "
        "— placement + rotation derived; base grounded 571.5mm above grade")
    # field 6 — the affected region an incremental recompile must touch:
    assert low.affected_region == ("trunk",)


# -- §8.7 determinism: the lowering is byte-stable across runs ---------------

def test_lowering_byte_stable_across_runs():
    def beams():
        d = compile_spec(load_spec_file(TREE))
        d.build()
        return {p.name: (_round(p.world_frame.origin, 10),
                         _round(p.world_frame.x_axis, 10),
                         _round(p.world_frame.y_axis, 10),
                         _round(p.world_frame.z_axis, 10))
                for p in d.assembly.parts if p.name in ("beam +Y", "beam -Y")}
    assert beams() == beams()   # identical, not merely within tolerance


# -- §7 Test 2 — mount a part by relation; everything derives ----------------

def test_cat2_mount_by_relation_everything_derives():
    doc = load_spec_file(CAT2)
    # a raw transform is UNNECESSARY: the placed part is authored as a MOUNT.
    cleat_spec = next(c for c in doc.components if c.id == "cleat")
    assert isinstance(cleat_spec.place, MountSpec)
    # the detail authors NO bearing by hand:
    assert not doc.validation.bearings

    d = compile_spec(doc)
    vspec = d.validation_spec()
    # field 2 — transform derived (the cleat is placed off the block face):
    cleat = next(p for p in d.assembly.parts if p.name == "cleat")
    assert cleat.world_frame.origin[1] > 0    # stood off along +Y, derived
    # field 3 — the bearing DERIVES from the same relation that placed the part:
    bearings = vspec.get("bearings", [])
    assert any(a.name == "cleat" and b.name == "block" for (a, b, ax, area) in bearings)
    # and it PASSES — placement and its proof agree by construction (the
    # SM3b class "hand transform disagrees with hand bearing" is unwritable):
    res = d.validate()
    bearing_findings = [f for f in d.report.findings if f.check == "bearing"]
    assert bearing_findings and all(f.passed for f in bearing_findings)
    # field 4 + 5 — the dependency edge and placement sentence are derived facts:
    log = " ".join(f.fact for f in d.derivation_report())
    assert "registers against 'block'" in log
    assert "placed by MOUNT relation" in log
