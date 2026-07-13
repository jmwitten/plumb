"""Whole-site overview: compose all four zipline details into ONE shared
frame for the consolidated build document's "Site overview" section.

Motivation (user-caught, 2026-07-06 late): each detail renders alone, so a
shared-member drift (the platform/tree_attachment beam Y positions
disagreeing by ~5") was invisible until pointed out by eye. A single
composed view makes that kind of drift human-visible without requiring any
new geometric validation.

Scope discipline (binding, see the module's callers)
-----------------------------------------------------
This module only COMPOSES already-validated per-detail geometry into one
frame for a picture. It never re-validates the composed scene: the overlap
semantics between two details' context copies of the same physical feature
(e.g. the trunk modeled once in the platform detail and again, differently, in
the tree_attachment detail) are not defined yet (that is Wave 3 / SiteContext
territory). Callers must keep stating this explicitly, verbatim, per the
project's wording rule: composition is REPRESENTED for orientation;
cross-detail validation NOT ANALYZED.

Site frame
----------
The shared site frame IS the platform detail's own world frame (tree face at
X=0, ground/anchor plane at Z=0, beam run along +X to the launch end). Every
other detail's placement below is derived from the world-frame conventions
each detail's own module docstring already states — see
:func:`compute_site_transforms` for the basis of each one, and each one's
confidence is carried into :class:`PlacementInfo` for the document.

De-duplication
---------------
Every detail deliberately re-models a piece of ANOTHER detail's canonical
member for context (a beam-end stub, a leg stub, a second copy of the trunk
or the boulder). Composing all four verbatim would draw those twice.
:func:`build_site_overview` drops the duplicate copy using only metadata
already on the component — never a hand list of part names — so a future
fifth detail inherits the same behavior automatically:

1. The platform detail is always canonical; nothing of its is ever dropped.
2. ``component.stub_of() is not None`` — a component explicitly tagged as a
   partial-member stub (the tree beam-end, the rock-anchor leg) whose full
   run is modeled elsewhere. Dropped.
3. An "existing" context body (:func:`is_existing`'s predicate — the exact
   one the combined BOM already applies) of a TYPE the platform ALSO models
   (the tree trunk, the boulder) is a duplicate of platform's copy. Dropped.
   An existing body of a type platform does NOT model (the zipline cable,
   trolley wheel, hanger, grab bar — trolley_launch's alone) has nothing to
   dedupe against and is KEPT.
4. Structural lumber outside the platform detail (:func:`is_context_stub_lumber`
   — the exact guard the combined BOM already applies to avoid double-buying
   it) is a duplicate of a platform member (trolley_launch's launch posts /
   deck-edge rim, which predate the formal ``stub_of()`` metadata). Dropped.

``is_existing``/``is_context_stub_lumber`` live here (not in
``consolidated_report.py``) so both the BOM path and this composition path
share one definition — moved from ``consolidated_report.py`` as part of this
task rather than duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from detailgen.assemblies import DetailAssembly, Placed
from detailgen.core import IN
from detailgen.core.frame import Frame

# --------------------------------------------------------------------------- #
# Dedup predicates — shared by the combined BOM (consolidated_report.py) and
# the site-overview composition below. One definition, two call sites.
# --------------------------------------------------------------------------- #
def is_existing(row: dict) -> bool:
    """A BOM row is 'existing — not purchased' if the component's source says
    so, OR its label marks it existing (the boulder is a natural feature whose
    source metadata reads 'generated' but which is not a purchase)."""
    return row["source"] != "generated" or "(existing)" in row["item"]


def is_context_stub_lumber(name: str, row: dict) -> bool:
    """Double-count guard. The PLATFORM detail is canonical for every piece of
    structural lumber in the build (beams, legs, joists, decking, rails, 2x4
    braces). The other three details each model a short *context stub* of a
    platform member so the connection reads — and the reconciliation report
    labels every one of them 'stub (context)':

      * trolley_launch: 2 launch posts (2x6x68") + deck-edge rim (2x6x22")
        = the platform's 2 launch legs (63.5") + deck edge  (reconciliation #7)
      * tree_attachment: 2 beam stubs (2x6x24") = the platform's 2 beams (60",
        BEAMFIX: 48" deck run + 12" continuing past the tree centerline)
      * rock_anchor: 1 leg stub (2x6x14") = the base of a platform launch leg

    Counting these would have the builder buy lumber that doesn't exist as a
    separate piece. So structural-lumber rows from the three connection details
    are dropped; only their genuinely new hardware is kept. The platform's own
    lumber is always kept. (No real lumber purchase lives only in a connection
    detail — verified: their only lumber lines are these stubs.)
    """
    return name != "platform" and "lumber" in row["item"].lower()


def _component_is_existing(component) -> bool:
    """:func:`is_existing`, applied directly to a placed part's component
    (not a BOM row) — same two fields, read straight off the component."""
    return is_existing({
        "source": getattr(component, "source", "generated"),
        "item": component.bom_label(),
    })


def _component_is_stub_lumber(detail_name: str, component) -> bool:
    """:func:`is_context_stub_lumber`, applied directly to a placed part's
    component."""
    return is_context_stub_lumber(detail_name, {"item": component.bom_label()})


# --------------------------------------------------------------------------- #
# Placement: site frame == platform's own world frame.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PlacementInfo:
    detail: str
    basis: str
    confidence: str  # "EXACT" or "ASSUMED"
    note: str = ""


def compute_site_transforms(details: dict) -> dict[str, Frame]:
    """Return ``{detail_name: Frame}`` mapping each detail's OWN world frame
    into the shared site frame (== the platform detail's world frame).

    - ``platform``: identity — it IS the site frame.
    - ``tree_attachment``: identity. Both modules' docstrings state the SAME
      convention independent of this task (trunk centered at X=0/Y=0, ground
      at Z=0, beam run along +X) and ``beam_z`` is a param deliberately set
      to match the platform's real beam-underside formula — no transform
      needed or invented here.
    - ``rock_anchor``: translation only. Its own docstring's world frame
      already matches the platform's axis convention (beam/launch direction
      +X, leg wide faces along Y) — only an offset is needed. Its local
      origin (0,0,0) is the boulder-pad top-face center (the boulder is
      added with no offset — see the rock_anchor detail's ``assemble``), so
      translating that origin to the platform's launch-leg station places
      the whole anchor assembly under that leg. Only ONE of the platform's
      two symmetric launch legs is represented (the +Y one) — the -Y twin
      is a mirror image, not separately composed, to avoid drawing the same
      hardware twice for no new information.
    - ``trolley_launch``: rotation + translation. Its own local frame runs
      X across the deck width (posts at X=0/deck_width) and Y along the
      beam-run axis (launch edge at Y=0, deck interior at +Y) — a
      DIFFERENT axis convention from the platform's (X along the beam run,
      Y across the deck width), so composing it needs a 90 degree spin
      about Z as well as a translation. The deck_width param is an already
      -reconciled EXACT match to the platform's own beam-to-beam span
      (asserted below, not just assumed); the AXIS MAPPING itself (which
      local axis becomes which world axis, and its sign) was derived by
      reading both modules' stated frame conventions side by side, not
      independently field-verified — logged as ASSUMED in the placement
      table for that reason.
    """
    platform = details["platform"]
    pf = platform.params
    tl = details["trolley_launch"].params

    # Reused, not re-derived: the platform's own already-reconciled half-span
    # across the two launch legs (joist_span/2 + beam thickness), read from the
    # compiled detail's public derived dimension ``outer_y`` (authoring inches) —
    # the spec-path equivalent of the .py detail's ``_beam_outer_y`` property, the
    # single source of truth. Recomputing it independently here would risk
    # drifting from the real geometry.
    beam_outer_y_in = platform.params.outer_y
    beam_outer_y_mm = beam_outer_y_in * IN

    if abs(2 * beam_outer_y_in - tl.deck_width) > 1e-6:
        raise ValueError(
            "site overview: platform's beam-to-beam span "
            f"(2x{beam_outer_y_in:.3f}\"={2 * beam_outer_y_in:.3f}\") no "
            f"longer matches trolley_launch.deck_width ({tl.deck_width}\") — "
            "the cross-detail Y reconciliation the trolley_launch site "
            "transform depends on has drifted; re-derive that transform "
            "before composing the overview"
        )

    return {
        "platform": Frame.identity(),
        "tree_attachment": Frame.identity(),
        "rock_anchor": Frame.translation(
            (pf.leg_station * IN, beam_outer_y_mm, 0.0)
        ),
        "trolley_launch": Frame.translation(
            (pf.beam_len * IN, -tl.deck_width / 2 * IN, 0.0)
        ).compose(Frame.rotation(90.0, axis=(0.0, 0.0, 1.0))),
    }


def _placement_table(details: dict) -> list[PlacementInfo]:
    pf = details["platform"].params
    beam_outer_y_in = pf.outer_y  # spec-path equivalent of .py ``_beam_outer_y / IN``
    return [
        PlacementInfo(
            "platform",
            "Canonical site frame (identity). Every other detail's "
            "placement below is expressed relative to this one.",
            "EXACT",
        ),
        PlacementInfo(
            "tree_attachment",
            "Identity — shares the platform's world-frame convention "
            "verbatim (trunk centered at X=0/Y=0, ground at Z=0; beam_z "
            "is a param set to match the platform's real beam-underside "
            "height).",
            "EXACT",
        ),
        PlacementInfo(
            "rock_anchor",
            f'Translated only, to the launch-leg station (X={pf.leg_station:.1f}", '
            f'Y=+{beam_outer_y_in:.2f}") at the shared Z=0 anchor plane. Its own '
            "local origin is the boulder-pad center, so this seats that boulder "
            "under one of the platform's two symmetric launch legs; the -Y twin "
            "is a mirror image, not separately composed.",
            "ASSUMED",
            "No verified sub-inch registration between rock_anchor's "
            "independently-authored leg stub and the platform's actual leg "
            "member — field-verify before relying on this view for fit.",
        ),
        PlacementInfo(
            "trolley_launch",
            f'Rotated 90&deg; about Z, then translated so its launch-edge line '
            f'(local Y=0) lands at the platform\'s launch edge (X={pf.beam_len:.1f}") '
            f'and its deck-width axis (local X, 0..{details["trolley_launch"].params.deck_width:.0f}") '
            f'lands on the platform\'s Y span (&plusmn;{beam_outer_y_in:.2f}").',
            "ASSUMED",
            "The deck_width equality is an exact, already-reconciled match "
            "(checked in code) — but the AXIS MAPPING itself (which local "
            "axis becomes which world axis, and its sign) was derived by "
            "reading both modules' stated frame conventions, not "
            "independently field-verified.",
        ),
    ]


# --------------------------------------------------------------------------- #
# Composition
# --------------------------------------------------------------------------- #
REASON_STUB = "stub_of metadata: partial member, full run is the platform's canonical member"
REASON_EXISTING_DUP = "existing/context feature already shown once via the platform detail"
REASON_LUMBER_DUP = "structural lumber duplicate of a platform member (bought once)"

#: Build order the four details are composed in (platform first so its
#: "existing" context types are known before the others are scanned).
DETAIL_ORDER = ("platform", "tree_attachment", "rock_anchor", "trolley_launch")


@dataclass
class SiteOverviewResult:
    assembly: DetailAssembly
    placements: list[PlacementInfo]
    dropped: list[dict] = field(default_factory=list)
    kept_counts: dict[str, int] = field(default_factory=dict)
    dropped_counts: dict[str, int] = field(default_factory=dict)


def _drop_reason(detail_name: str, component, platform_existing_types: set[str]) -> str | None:
    if detail_name == "platform":
        return None
    if component.stub_of() is not None:
        return REASON_STUB
    if _component_is_existing(component) and type(component).__name__ in platform_existing_types:
        return REASON_EXISTING_DUP
    if _component_is_stub_lumber(detail_name, component):
        return REASON_LUMBER_DUP
    return None


def build_site_overview(details: dict) -> SiteOverviewResult:
    """Compose all four details' assemblies into one shared-frame
    ``DetailAssembly`` ("Site Overview"), applying the dedup rule above.

    Reuses each detail's OWN already-built component objects (never copies
    or re-tessellates them) — the composed assembly's parts differ from the
    originals only in ``world_frame``, so its content-hash
    (``core.buildinfo.build_manifest``) changes automatically if ANY of the
    four details' geometry changes, with no separate invalidation logic to
    maintain."""
    transforms = compute_site_transforms(details)
    platform_existing_types = {
        type(p.component).__name__
        for p in details["platform"].assembly.parts
        if _component_is_existing(p.component)
    }

    site = DetailAssembly("Site Overview")
    dropped: list[dict] = []
    kept_counts = {name: 0 for name in DETAIL_ORDER}
    dropped_counts = {name: 0 for name in DETAIL_ORDER}

    for name in DETAIL_ORDER:
        transform = transforms[name]
        for p in details[name].assembly.parts:
            reason = _drop_reason(name, p.component, platform_existing_types)
            if reason is not None:
                dropped.append({"detail": name, "name": p.name, "reason": reason})
                dropped_counts[name] += 1
                continue
            new_frame = transform.compose(p.world_frame)
            site.parts.append(Placed(
                p.component, new_frame, at=new_frame.origin, rotate=[],
                id=f"{name}-{p.id}",
            ))
            kept_counts[name] += 1

    return SiteOverviewResult(
        assembly=site,
        placements=_placement_table(details),
        dropped=dropped,
        kept_counts=kept_counts,
        dropped_counts=dropped_counts,
    )


def tree_vs_platform_beam_y(details: dict) -> dict:
    """DEPRECATED (SM4 item 4). This hand-written Y-divergence callout is SUBSUMED
    by the compiled site model: SM3b composes the tree fragment against the real
    beams, so the divergence is now a SYSTEM finding (the beam-tangent dimension
    ``beam inner face tangent at trunk radius: platform/beam +Y`` reads 15" vs the
    tree's 10", plus the washer↔beam bearing FAILs). The site-model section of the
    consolidated report no longer calls this. It is retained only for the LEGACY
    ``render_site_overview`` panel (not wired into ``main`` any more) and its
    ``tests/test_site_overview.py`` coverage; prefer the site model's findings.

    The KNOWN Y-DIVERGENCE (open design decision, user-caught, NOT
    resolved by this task): the platform's real beams sit at
    Y=+/-beam_outer_y (the 33" deck width's structural span) while the tree
    connection's OWN beam-stub geometry is drawn trunk-tangent, at
    Y=+/-trunk_radius..+thickness — a different Y band. The dedup rule above
    hides the tree detail's stub (it is ``stub_of``-tagged, full run is the
    platform's beam), so the composed view shows only the platform's real
    beam position. That is the correct rendering choice, but it would
    silently paper over the divergence if the document didn't say so
    explicitly — this returns the numbers so the document can."""
    from detailgen.components.lumber import NOMINAL_SIZES

    platform = details["platform"]
    tree_p = details["tree_attachment"].params
    thickness_in = NOMINAL_SIZES["2x6"][0] / IN

    return {
        "platform_outer_y_in": platform.params.outer_y,  # spec-path ``_beam_outer_y / IN``
        "tree_inner_y_in": tree_p.trunk_dia / 2,
        "tree_outer_y_in": tree_p.trunk_dia / 2 + thickness_in,
    }
