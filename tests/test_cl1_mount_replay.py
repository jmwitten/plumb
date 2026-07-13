"""CL-1 REPLAY B — the acceptance measurement (cl0-design.md §6, §8.2).

The two tree beams, re-authored as MOUNT relations, LOWER to transforms that
match today's hand-authored spec. The parity harness is the enforced 4B/
frozen-truth discipline: 1e-6. Precisely what holds (measured, not asserted
loosely):

- the BASE hand (beam +Y) is **bit-exact** — identical origin, geometry, and
  ``geometry_hash`` to the raw spec;
- the MIRROR hand (beam -Y) is a DERIVED proper 180° rotation, so its world
  origin carries a principled ~6e-14 mm epsilon (``sin(180°)=1.2e-16`` through an
  offset-origin rotation — snapping it to 0 would be a forbidden heuristic). That
  epsilon is **absorbed by the 6-digit transform digest**, so every production
  hash (``_part_hash``, ``assembly_hash``) is byte-identical raw-vs-mount and the
  1e-6 frozen-truth parity is met. It is NOT bit-equal at the raw-float origin.

Diffed against BOTH the frozen imperative truth
(``tests/baselines/frozen_truth/tree_attachment.json``) and the pre-CL-1
raw-authored spec (frozen as a fixture baseline). The shipping detail's two beams
are now MOUNT relations; no golden is weakened.

REPLAY B counts (the benchmark the retro requires), asserted below on the two
beam placements: raw coordinate arrays 2 -> 0; ``rotate`` clauses 1 -> 0;
``= -…`` mirror-negation twins 1 -> 0. (The beam height is now a ``ground``
standoff relation to the world grade datum — a derived elevation fact, not a raw
Z coordinate.)
"""

from __future__ import annotations

import json
from pathlib import Path

from detailgen.spec.loader import load_spec_file
from detailgen.spec.compiler import compile_spec
from detailgen.spec.schema import MountSpec, RawSpec

ROOT = Path(__file__).resolve().parents[1]
# The shipping detail — its two beams MIGRATED to MOUNT relations (the "after").
REAL = ROOT / "details" / "tree_attachment.spec.yaml"
# The pre-CL-1 raw-authored detail, frozen here as "today's hand-authored spec"
# (the "before") — the baseline the parity harness diffs the lowered IR against.
BASELINE = ROOT / "tests" / "fixtures" / "cl1" / "tree_attachment_raw_baseline.spec.yaml"
FROZEN = ROOT / "tests" / "baselines" / "frozen_truth" / "tree_attachment.json"
TOL = 1e-6
BEAMS = ("beam +Y", "beam -Y")


def _fingerprint(detail):
    out = {}
    for p in detail.assembly.parts:
        wp = p.world_solid()
        solids = wp.vals()
        vol = sum(s.Volume() for s in solids)
        bb = (wp.combine().objects[0].BoundingBox() if len(solids) > 1
              else solids[0].BoundingBox())
        out[p.name] = (list(p.world_frame.origin), vol,
                       [bb.xmin, bb.ymin, bb.zmin, bb.xmax, bb.ymax, bb.zmax])
    return out


def _built(spec_path):
    d = compile_spec(load_spec_file(spec_path))
    d.validate()
    return d


def test_replay_b_mounted_beams_match_frozen_truth_to_1e_6():
    """The mount-authored beams reproduce the frozen imperative transforms +
    geometry to 1e-6 — the enforced parity bar (base hand bit-exact; mirror hand
    within the ~6e-14 sin(180°) epsilon). If MOUNT's lowered rotation or its
    derived mirror hand were off by more than that, this fails."""
    frozen = json.loads(FROZEN.read_text())["geom_fingerprint"]
    fp = _fingerprint(_built(REAL))
    assert set(fp) == set(frozen)
    worst = 0.0
    for name in frozen:
        oi, vi, bi = frozen[name]
        os_, vs, bs = fp[name]
        worst = max(worst, max(abs(a - b) for a, b in zip(oi, os_)))
        worst = max(worst, abs(vi - vs))
        worst = max(worst, max(abs(a - b) for a, b in zip(bi, bs)))
    assert worst <= TOL, f"worst deviation {worst} mm > {TOL}"


def test_replay_b_mounted_matches_raw_baseline_to_1e_6():
    """MOUNT lowers to the same transform (to 1e-6) the pre-CL-1 raw baseline
    produces — 'diff the lowered IR against today's spec' (the parity harness).
    Base hand bit-exact; mirror hand within the sin(180°) epsilon."""
    raw_fp = _fingerprint(_built(BASELINE))
    mount_fp = _fingerprint(_built(REAL))
    for name in BEAMS:
        ro, _, rb = raw_fp[name]
        mo, _, mb = mount_fp[name]
        assert max(abs(a - b) for a, b in zip(ro, mo)) <= TOL, name
        assert max(abs(a - b) for a, b in zip(rb, mb)) <= TOL, name


def test_replay_b_base_hand_bit_exact_mirror_digest_identical():
    """Claim exactly as strong as the mechanism: the BASE hand is bit-exact
    (0.0 origin delta); the MIRROR hand carries the sin(180°) epsilon at the raw
    float but its 6-digit transform DIGEST is byte-identical raw-vs-mount, so the
    production geometry/assembly hashes do not see it."""
    from detailgen.core.buildinfo import build_manifest

    def built(path):
        d = compile_spec(load_spec_file(path))
        d.build()
        return d

    raw, mount = built(BASELINE), built(REAL)
    raw_o = {p.name: p.world_frame.origin for p in raw.assembly.parts}
    mnt_o = {p.name: p.world_frame.origin for p in mount.assembly.parts}
    # base hand: bit-exact origin
    assert max(abs(a - b) for a, b in zip(raw_o["beam +Y"], mnt_o["beam +Y"])) == 0.0
    # mirror hand: within the principled sin(180°) epsilon, not necessarily 0
    dmax = max(abs(a - b) for a, b in zip(raw_o["beam -Y"], mnt_o["beam -Y"]))
    assert 0.0 < dmax < 1e-9

    # both beams' production DIGESTS are byte-identical raw-vs-mount (epsilon
    # absorbed by the 6-digit transform rounding):
    rm = {p["name"]: p["geometry_hash"] for p in build_manifest(raw.assembly)["parts"]}
    mm = {p["name"]: p["geometry_hash"] for p in build_manifest(mount.assembly)["parts"]}
    for name in BEAMS:
        assert rm[name] == mm[name], f"{name} part digest differs raw-vs-mount"
    assert (build_manifest(raw.assembly)["assembly_hash"]
            == build_manifest(mount.assembly)["assembly_hash"])


def test_replay_b_counts_zero_raw_rotate_negation():
    """The migrated placements carry 0 raw coordinate arrays, 0 rotate clauses,
    0 mirror-negation twins — measured on the loaded docs."""
    raw_doc = load_spec_file(BASELINE)
    mount_doc = load_spec_file(REAL)

    def beam_places(doc):
        return {c.id: c.place for c in doc.components if c.id in ("beam_pY", "beam_mY")}

    raw_places = beam_places(raw_doc)
    # Before: both beams are RawSpec; each is 3 raw coordinates; one carries a
    # rotate; one carries the mirror-negation twin (`= -beam_inner_y`, the
    # hand-kept arithmetic negation of the +Y beam's derived inner_y — the R2 twin
    # a sign typo silently breaks).
    assert all(isinstance(p, RawSpec) for p in raw_places.values())
    n_raw_coords_before = sum(len(p.at) for p in raw_places.values())
    n_rotate_before = sum(1 for p in raw_places.values() if p.rotate)
    n_twin_before = sum(
        1 for p in raw_places.values() for v in p.at
        if isinstance(v, str) and v.replace(" ", "").startswith("=-beam_inner_y"))
    assert (n_raw_coords_before, n_rotate_before, n_twin_before) == (6, 1, 1)

    # After: both are MountSpec — no coordinate array, no rotate, no negation.
    mount_places = beam_places(mount_doc)
    assert all(isinstance(p, MountSpec) for p in mount_places.values())
    for p in mount_places.values():
        # a mount carries relation values (clear_by/raise), never a raw at[] / rotate
        assert not hasattr(p, "at")
        assert not hasattr(p, "rotate")
    # mirror is DECLARED once (the opposite hand), never a `= -` negation
    assert sum(1 for p in mount_places.values() if p.mirror) == 1
