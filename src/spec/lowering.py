"""The MOUNT **lowering pass** — a pure, deterministic, byte-stable expansion of
a :class:`~detailgen.spec.schema.MountSpec` relation into the FROZEN spec IR
(the resolved world :class:`~detailgen.core.frame.Frame` a raw/mate placement
also produces), plus the facts the relation *derives* (CL-1, retro R2/R3).

Why this exists (cl0-design.md §2, §3.1). A raw placement hands the machine
three hand-computed coordinates and a hand-picked ``rotate`` clause; the intent
— *"the inner face stands a growth gap clear of the trunk, turned to face it"* —
lives in a YAML comment. Four hand-synchronised encodings of one intent (the
coordinates, the mirror-negation twin, the contact check, the doc prose) are
four surfaces an edit must chase and an agent can get wrong (the SM3b
frame-composition class). MOUNT collapses them to one relation: the compiler
DERIVES the full rigid transform (translation **and** rotation), the opposite
hand (``mirror``), the contact the relation implies, the dependency edge, and
the placement sentence — all from the single declaration, kept in sync by
construction.

Purity + determinism (cl0-design.md §6). ``lower_mount`` is a pure function of
its inputs: the resolved relation values, the target's world frame + surface
half-extent, and the part's face datum. Same inputs → the same world frame and
the same derived facts on every run — no inference, no heuristic. Where the
relation cannot pin all six degrees of freedom, that is NOT guessed here: the
semantic-analysis pass (:mod:`detailgen.spec.semantics`) has already rejected it
with a teaching error naming the missing constraint. This pass only expands a
relation already proven well-formed.

The rotation is COMPUTED FROM THE FACE PAIR, never authored: the part's named
face is turned so its outward normal points at the target, and its in-plane axis
falls on the target's canonical in-plane axis (this pins all three rotational
DOF — CL-2 dropped the ``spin`` re-aim, which derived nothing). The
``mirror`` instance is the opposite hand, realised as the proper 180° rotation
about the one axis the part is symmetric across (the axis it is centered on) —
so the ``= -…`` mirror-negation twin and the hand ``["Z",180]`` both vanish.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.frame import Frame
from .schema import MOUNT_AXES, MOUNT_FACE_ALIASES, FeatureSpec, MountSpec


_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}


@dataclass(frozen=True)
class MountLowering:
    """The result of lowering ONE :class:`MountSpec` — the frozen-IR transform
    plus every fact the relation derives (the §3.1 seven-field table, as data a
    determinism golden asserts).

    ``world_frame`` is the EFFECTIVE placement of this part: the base hand, or —
    when the relation carries ``mirror`` — the opposite hand, realised as a
    proper 180° rotation (never a reflection, never a hand-authored ``rotate``).
    ``base_frame`` is the un-mirrored hand, kept for the derivation golden so the
    mirror derivation is inspectable. ``rotated`` records whether the derived
    orientation differs from identity (the hand-rotation the author no longer
    writes). ``contact`` / ``evidence_ref`` / ``doc_sentence`` /
    ``affected_region`` are the derived validation / ownership / presentation /
    incremental facts (§3.1 fields 3–6)."""

    world_frame: Frame
    base_frame: Frame
    rotated: bool
    #: whether a ground (R3) relation pinned the base height above grade
    grounded: bool
    #: (kind, a_id, b_id, axis) for a derived contact, or None (positioning only)
    contact: object
    #: the reference part id this placed part registers against (evidence edge)
    evidence_ref: str
    #: derived placement sentence (value language already resolved), for the doc
    doc_sentence: str
    #: the ids/facts an incremental recompile must touch if the reference moves
    affected_region: tuple


class MountLoweringError(ValueError):
    """A mount that cannot be lowered — raised only for a condition the semantic
    pass is supposed to have caught first (a belt-and-braces guard, in the
    teaching style). A well-formed, semantic-checked mount never reaches this."""


def _axis_dir(frame: Frame, axis: str):
    return {"X": frame.x_axis, "Y": frame.y_axis, "Z": frame.z_axis}[axis]


def _mirror_axis_c(mount: MountSpec) -> str:
    """The single target axis the ``mirror`` 180° rotation turns about: the axis
    that is NEITHER the mirror plane-normal NOR a centered axis. The opposite
    hand is a proper rotation about this axis, absorbed by the part's centering
    so it flips only the mirror axis (the hand) — never a reflection, never a
    hand-authored spin. Requires exactly one such axis (the semantic pass
    enforces it)."""
    remaining = [a for a in MOUNT_AXES if a != mount.mirror and a not in mount.center]
    if len(remaining) != 1:
        raise MountLoweringError(
            f"mirror {mount.mirror!r} needs the part centered on every non-mirror "
            f"axis but one (so the opposite hand is a rigid rotation); centered on "
            f"{list(mount.center)} leaves ambiguous axes {remaining}")
    return remaining[0]


def lower_mount(
    mount: MountSpec,
    *,
    face_datum: Frame,
    base_datum: Frame,
    target_frame: Frame,
    surface_offset: float,
    clear_by: float | None,
    offset: float | None,
    ground_above: float | None,
) -> MountLowering:
    """Expand ``mount`` into a world :class:`Frame` (+ the derived facts).

    Geometry inputs (all resolved by the caller — this stays pure):

    - ``face_datum`` — the part's registering face datum in the part's LOCAL
      frame (origin on the face plane, outward-normal +Z, in-plane +X). Its
      origin is the part's registering point; its length-axis coordinate is the
      centering anchor.
    - ``base_datum`` — the part's seating (``base``) datum, local; its origin's
      height is what ``ground`` pins (against the world grade datum).
    - ``target_frame`` — the target's reference frame in WORLD (its ``axis`` /
      ``base`` datum). The standoff / center / mirror axes are named in it.
    - ``surface_offset`` — the target's half-extent along the standoff axis (its
      surface distance from ``target_frame`` origin); ``clear_by`` / ``offset``
      are measured from that surface.
    - ``clear_by`` / ``offset`` — resolved standoff lengths (``flush`` => both
      ``None``: the face meets the surface).
    - ``ground_above`` — resolved height of the ``base`` datum ABOVE the world
      grade datum (Z=0), the R3 grounding standoff, or ``None`` when the standoff
      and center pin every axis.
    """
    axis = mount.axis
    a_dir = _axis_dir(target_frame, axis)

    # -- rotation: turn the face so its outward normal points AT the target -----
    # The base instance sits on the +axis side; its face normal points -axis
    # (back toward the target). The face's in-plane +X falls on the target's
    # canonical in-plane axis (first of X/Y/Z that is not the standoff axis).
    inplane_axis = next(a for a in MOUNT_AXES if a != axis)
    inplane_dir = _axis_dir(target_frame, inplane_axis)
    normal_world = tuple(-c for c in a_dir)           # face normal -> -axis
    face_world_rot = Frame.from_origin_axes((0.0, 0.0, 0.0), inplane_dir, normal_world)
    face_local_rot = Frame.from_origin_axes(
        (0.0, 0.0, 0.0), face_datum.x_axis, face_datum.z_axis)
    part_rot = face_world_rot.compose(face_local_rot.inverse())

    # -- translation: pin one world axis per constraint (closed form) -----------
    # Everything is reasoned in the TARGET frame, then mapped back to world.
    if clear_by is not None:
        gap = surface_offset + float(clear_by)
    elif offset is not None:
        gap = surface_offset + float(offset)
    else:                                              # flush: face meets surface
        gap = surface_offset
    base = _place(part_rot, face_datum, base_datum, target_frame,
                  axis, gap, mount.center, ground_above)

    world = base
    if mount.mirror:
        c_dir = _axis_dir(target_frame, _mirror_axis_c(mount))
        world = Frame.rotation(
            180.0, c_dir, origin=target_frame.origin).compose(base)

    rotated = not world.approx_equal(
        Frame.translation(world.origin), tol=1e-9)

    # -- derived contact (§3.1 field 3): DERIVED from the relation KIND ---------
    # A `flush` mount is face-area registration — the relation IMPLIES a bearing,
    # so one is derived automatically from the same declaration that places the
    # part (the SM3b class — a hand transform disagreeing with a hand bearing — is
    # unwritable). A `clear_by` / `offset` is a STANDOFF: the faces do not meet, so
    # no contact is derived (a clearance INVARIANT is a CL-2 feature verb, not a
    # placement contact — cl0-design §3.1 REPLAY A). Nothing is authored.
    contact = ("bearing", mount.to, axis) if mount.flush else None

    side = "opposite-hand " if mount.mirror else ""
    rel = ("flush against" if mount.flush
           else "a gap clear of" if clear_by is not None
           else "offset from")
    doc = (f"{side}{mount.face} face {rel} {mount.to} "
           f"(along {axis}) — placement + rotation derived")
    if ground_above is not None:
        doc += f"; base grounded {round(ground_above, 3)}mm above grade"

    return MountLowering(
        world_frame=world, base_frame=base, rotated=rotated,
        contact=contact, evidence_ref=mount.to,
        doc_sentence=doc, affected_region=(mount.to,),
        grounded=ground_above is not None,
    )


def _place(part_rot, face_datum, base_datum, target_frame,
           axis, gap, center, ground_above):
    """Solve the translation: in the TARGET frame the face datum origin sits at
    ``gap`` along the standoff axis and at 0 on each ``center`` axis; then, if a
    ``ground_above`` relation is given, the base datum origin is pinned that
    height above the WORLD grade datum (Z=0) by a world-Z shift (grade is a fixed
    world datum, not a target-relative one). One coordinate per constraint — a
    closed form, no search, byte-stable."""
    Ti = _AXIS_INDEX
    tinv = target_frame.inverse()
    # face datum origin, in target-frame coords, with the part rotated at world 0:
    face_tf = tinv.transform_point(part_rot.transform_point(face_datum.origin))
    desired = list(face_tf)
    desired[Ti[axis]] = gap
    for c in center:
        desired[Ti[c]] = 0.0
    delta_tf = tuple(desired[i] - face_tf[i] for i in range(3))
    world = target_frame.compose(Frame.translation(delta_tf)).compose(
        tinv).compose(part_rot)
    if ground_above is not None:
        base_world_z = world.transform_point(base_datum.origin)[Ti["Z"]]
        dz = ground_above - base_world_z
        world = Frame.translation((0.0, 0.0, dz)).compose(world)
    return world


# --------------------------------------------------------------------------- #
# FEATURE lowering (CL-2, retro R9/R14) — pure `declaration + placed positions
# -> board-local cut` expansion. See FeatureSpec for the grammar.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FeatureLowering:
    """The result of lowering ONE :class:`FeatureSpec` — the board-local cut plus
    every fact the feature derives (cl0-design.md §3.2 seven-field table).

    ``cut`` is ``(cx, cy, radius)`` in the featured part's LOCAL frame — the exact
    tuple a hand-authored ``trunk_cut`` produced, so the folded geometry is
    unchanged. ``noun`` is the display name the cut note renders (the member's
    name for a clearance_cut, the feature's own name for a bore); ``step_kind`` is
    the fabrication :class:`~detailgen.core.process_graph.ProcessStep` kind
    (``notch`` for a clearance_cut, ``bore`` for a designed recess) and
    ``provenance`` is the feature's identity (authored id, else content key) that
    the step keys on. ``clears`` names the member a clearance_cut fits around (the
    evidence edge + the affected region); a bore clears nothing. ``clearance`` is
    ``(member_id, gap_mm)`` for the derived ge clearance invariant, or ``None``
    (a bore mandates none). ``callout`` is ``(label, radius_mm)`` for the derived
    dimension callout anchor."""

    kind: str
    cut: tuple                 # (cx, cy, radius) board-local, mm
    noun: str
    step_kind: str             # "notch" | "bore"
    provenance: str
    clears: str                # member id, or "" for a bore
    clearance: object          # (member_id, gap_mm) or None
    callout: tuple             # (label, radius_mm)
    affected_region: tuple


def feature_identity(feat: FeatureSpec) -> str:
    """The feature's stable identity FAB/INCR/the cut note key on (Q3, fab-design
    §9): the AUTHORED ``id`` when given, else a CONTENT key derived from the
    declaration — ``clearance_cut:<around>`` / ``bore:<name-or-'anon'>``. The
    content key is the honest substitute for an unnamed interim surface (the
    residual fab-design §9 disclosed); authoring an ``id`` closes it."""
    if feat.id:
        return feat.id
    if feat.kind == "clearance_cut":
        return f"clearance_cut:{feat.around}"
    tag = feat.name.strip().replace(" ", "_") if feat.name else "anon"
    return f"bore:{tag}"


def feature_noun(feat: FeatureSpec, *, member_name: str = "") -> str:
    """The display noun the cut note renders. A clearance_cut speaks the member's
    own name (``trunk``); a bore speaks the feature's authored ``name`` (``cup
    hole``). Falls back to the authored ``name`` where a member name is absent."""
    if feat.kind == "clearance_cut":
        return feat.name or member_name or feat.around
    return feat.name or "recess"


def lower_feature(
    feat: FeatureSpec,
    *,
    part_frame: Frame,
    part_center_local: tuple,
    member_axis_world: tuple | None,
    member_radius: float | None,
    member_name: str = "",
    gap: float | None = None,
    dia: float | None = None,
    at_local: tuple | None = None,
    unit_factor: float = 1.0,
) -> FeatureLowering:
    """Expand ``feat`` into a board-local cut ``(cx, cy, radius)`` + derived facts.

    Geometry inputs (all resolved by the caller — this stays pure):

    - ``part_frame`` — the featured part's placed WORLD frame.
    - ``part_center_local`` — the part's own local center ``(x, y)`` (its ``base``
      datum origin), the default bore center.
    - ``member_axis_world`` — the clearance_cut member's world axis point (its
      ``axis``/``base`` datum origin); ``None`` for a bore.
    - ``member_radius`` — the member's cross-sectional radius (half its
      world-bbox extent perpendicular to the cut), so ``radius = member_radius +
      gap`` reproduces the hand ``= trunk_dia/2 + gap`` exactly; ``None`` for a bore.
    - ``gap`` — resolved radial clearance (clearance_cut, mm); ``dia`` — resolved
      bore diameter (mm); ``at_local`` — resolved authored bore center, or
      ``None`` => the part center; ``unit_factor`` — the authoring unit's mm
      factor, used so the derived radius reproduces the value language's own
      float path (evaluate the sum in authoring units, scale ONCE).
    """
    ident = feature_identity(feat)
    if feat.kind == "clearance_cut":
        # The board-local cut center IS the member's world axis re-expressed in
        # the part's local frame — the world->local negation the author does by
        # hand (the `= -…` twin, R9). For an axis-aligned board with the member at
        # the world origin this is a pure per-axis subtraction (bit-exact).
        local = part_frame.inverse().transform_point(member_axis_world)
        # radius = member radius + gap, computed the way the value language would
        # have (`= trunk_dia/2 + gap`): sum in AUTHORING units, scale by the unit
        # factor ONCE. Summing the two already-scaled mm terms instead would drift
        # by a float-associativity epsilon (~6e-14mm) that OCCT volume integration
        # amplifies at the tangential notch edge — so this single-scale path keeps
        # the migrated notch byte-identical to the retired hand expression.
        radius = (float(member_radius) / unit_factor
                  + float(gap) / unit_factor) * unit_factor
        cut = (local[0], local[1], radius)
        noun = feature_noun(feat, member_name=member_name)
        return FeatureLowering(
            kind=feat.kind, cut=cut, noun=noun, step_kind="notch",
            provenance=ident, clears=feat.around,
            clearance=(feat.around, float(gap)),
            callout=(f"{noun} clearance", radius),
            affected_region=(feat.around,),
        )
    # bore — a DESIGNED recess: center is authored (`at`) or the part center; it
    # references no member, so it derives NO clearance invariant and NO evidence
    # edge to a member (it is a hole the design wants, not a fit around anything).
    cx, cy = (at_local if at_local is not None else part_center_local)
    radius = float(dia) / 2.0
    noun = feature_noun(feat)
    return FeatureLowering(
        kind=feat.kind, cut=(float(cx), float(cy), radius), noun=noun,
        step_kind="bore", provenance=ident, clears="",
        clearance=None, callout=(noun, radius), affected_region=(),
    )
