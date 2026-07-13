"""Support / Stability REPRESENTATION check — rung 3 (task SUPPORT).

The honest, capacity-free question this check answers, for every
``walking_surface`` (an occupied region that a Role generates a support
obligation for): **is the occupied region actually SUPPORTED?** — i.e. does it
have a declared support scheme that (a) reaches a real FOUNDATION and (b) sits
UNDER the occupied footprint (or is an explicitly declared cantilever). This is
strictly stronger than rung 1 (``floating``: connected to *a* ground node, which
may be a structural member) and rung 2 (``load_path``: a support→ground chain is
REPRESENTED) — both of which the platform's unsupported tree end passed while
being obviously unstable (see ``investigation-stability-miss.md``). It is
strictly weaker than rung 4 (force/moment/capacity), which stays UNKNOWN: a
represented support is never claimed adequate.

Three verdicts, per surface:

- **PASS** — the occupied footprint sits over grounded supports (or a declared
  cantilever accounts for the overhang). Support is REPRESENTED (rung 3).
- **FAIL** — a region of the occupied surface overhangs its grounded supports on
  a side with no declared cantilever (that region is unsupported), OR support is
  ``deferred``, OR no declared support reaches a foundation. An honest,
  representation-level failure — never a capacity claim.
- **UNKNOWN (blocking)** — the surface overhangs its support on *both* sides of
  an axis (interior support, no cantilever declared): whether the represented
  support holds the whole surface is not determinable at rung 3. Honest "cannot
  tell", and it BLOCKS a clean export (the directive: never CLEAN when support is
  unanswerable) — it is not a fake FAIL.

The graph reuse: "reaches a foundation" is the same BFS the load-path check uses
(:func:`detailgen.validation.loadpath._bfs_path`), fed the physical-contact graph
(the bearings + bonds that actually touch, exactly as ``check_no_floaters``
builds it) and terminated at FOUNDATION bodies (parts with the ``ground`` role) —
never at a structural member. The coverage itself is a plan-view (X/Y) footprint
comparison: no forces, no areas, no capacity.

The check kind is ``support``; it is family-tagged to "Support/Stability
representation" in :data:`detailgen.validation.coverage.KIND_TO_FAMILY`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from collections import deque

from ..core import IN
from ..core.ontology import GROUND_ROLE, is_foundation_role
from .checks import Finding, UNKNOWN_VERDICT, _cached_linked

#: Plan overhang below which an occupied edge counts as flush with its support
#: (board-registration slop, not a cantilever). Absolute, deterministic; an
#: overhang beyond this on an undeclared edge is an unsupported region.
SUPPORT_OVERHANG_TOL = 0.5 * IN

#: The plan edges and their opposites (X/Y only — gravity is -Z, so support
#: coverage is a horizontal-footprint question).
_OPPOSITE = {"+X": "-X", "-X": "+X", "+Y": "-Y", "-Y": "+Y"}


@dataclass(frozen=True)
class ResolvedSurface:
    """A walking_surface scheme with its cids resolved to placed parts — the
    shape both the standalone and the site path hand to :func:`check_support`."""

    label: str
    members: tuple            # placed parts whose union AABB is the footprint
    supports: tuple           # placed parts declared to carry it down
    cantilever_edges: dict = field(default_factory=dict)  # edge -> note
    deferred_support: str = ""
    #: names of members declared in ``supports:`` that DO NOT resolve to a part in
    #: the model (a vanished / mistyped support) — a tracked existence obligation
    #: (task SUPPORT v1.1). Empty when every declared support is present.
    missing_supports: tuple = ()


class _Box:
    __slots__ = ("xmin", "xmax", "ymin", "ymax")

    def __init__(self, xmin, xmax, ymin, ymax):
        self.xmin, self.xmax, self.ymin, self.ymax = xmin, xmax, ymin, ymax


def foundation_ids(roles_by_part: dict) -> set:
    """Part IDs that carry a FOUNDATION role (the terminals a support scheme may
    reach). ``roles_by_part`` maps a placed part to its role string; only
    ``ground``-role bodies qualify (:func:`is_foundation_role`) — a structural
    member is never a foundation."""
    return {p.id for p, role in roles_by_part.items()
            if is_foundation_role(role)}


def _plan_box(parts) -> _Box:
    """Union axis-aligned X/Y footprint of ``parts`` (world frame)."""
    xs0, xs1, ys0, ys1 = [], [], [], []
    for p in parts:
        bb = p.world_solid().val().BoundingBox()
        xs0.append(bb.xmin); xs1.append(bb.xmax)
        ys0.append(bb.ymin); ys1.append(bb.ymax)
    return _Box(min(xs0), max(xs1), min(ys0), max(ys1))


def _surface_side(member_ids: set, support_ids: set, adj: dict) -> set:
    """The set of parts the walking surface REACHES without passing through a
    declared support — i.e. the HELD-UP FRAME the supports carry (the beams,
    joists, the members themselves), plus anything the frame connects to that is
    not gated behind a support (task SUPPORT v1.1, directional).

    This is the tolerance-free discriminator the sibling-only fix lacked: a
    support's FOUNDATION-side hardware (its pier, or the leveling angle brackets
    the launch legs stand on) sits BELOW the support and is reachable only THROUGH
    it, so it is NOT surface-side; the frame the support HOLDS UP is reachable
    from the surface without it, so it IS. Blocking the surface-side set forces a
    support to reach ground through its own foundation, never by borrowing a
    non-sibling foundation UP through the frame it clamps (reviewer's DEFEAT 3 /
    both-phantom) — while a genuine downward chain (post → grade beam → footing,
    launch leg → angle → boulder) is preserved because those intermediates are
    below the supports, not surface-side.

    SCOPE (v1.1): ``support_ids`` is THIS surface's supports only, so the frame
    blocked is this surface's frame. In a MULTI-surface model, another surface's
    frame is not blocked here, so a phantom can borrow a foreign surface's
    foundation through it — the disclosed cross-surface residual (a global block
    can't tell that phantom borrow from a legit stacked platform without directional
    bearing semantics, which is CL-gated)."""
    seen = set(member_ids)
    q = deque(member_ids)
    while q:
        for m in adj.get(q.popleft(), ()):
            if m in seen or m in support_ids:
                continue
            seen.add(m)
            q.append(m)
    return seen


def _contact_adjacency(bearings, bonds, tol) -> dict:
    """Undirected part-id adjacency over the bearings + bonds that ACTUALLY
    touch (min-distance ≤ near-miss), the same physical-contact graph
    ``check_no_floaters`` walks — a declared-but-gapped bearing contributes no
    edge, so a support that does not really reach its foundation cannot fake a
    path."""
    adj: dict = {}

    def link(a, b):
        adj.setdefault(a.id, set()).add(b.id)
        adj.setdefault(b.id, set()).add(a.id)

    for spec in bearings:
        a, b = spec[0], spec[1]
        if _cached_linked(a, b, tol):
            link(a, b)
    for (a, b) in bonds:
        if _cached_linked(a, b, tol):
            link(a, b)
    return adj


def _overhangs(surface: _Box, support: _Box) -> dict:
    """Per plan edge, how far the occupied ``surface`` extends beyond the
    ``support`` span (0 when the surface is within the support on that edge)."""
    return {
        "-X": max(0.0, support.xmin - surface.xmin),
        "+X": max(0.0, surface.xmax - support.xmax),
        "-Y": max(0.0, support.ymin - surface.ymin),
        "+Y": max(0.0, surface.ymax - support.ymax),
    }


def _fmt_in(mm: float) -> str:
    return f"{mm / IN:.1f}in"


def check_support(surfaces, *, foundations: set, bearings, bonds,
                  tol, overhang_tol: float = SUPPORT_OVERHANG_TOL) -> list[Finding]:
    """One ``support`` :class:`Finding` per walking surface, deterministic in
    input order. ``foundations`` is the set of part IDs carrying a FOUNDATION
    (``ground``) role; ``bearings``/``bonds`` are the resolved contact pairs the
    reach-a-foundation BFS walks; ``tol`` is the geometry :class:`Tolerances`
    (its ``near_miss`` gates physical contact).

    v1.1 SCOPE (single surface): the bearing obligation is verified WITHIN each
    surface's own support graph. When a model composes MORE THAN ONE walking
    surface, cross-surface support borrowing is NOT verified (see
    :func:`_surface_side`) — a support could bear on a neighbouring surface's frame
    instead of a foundation and still pass. That residual is DISCLOSED on every
    finding in a multi-surface model (never silent) and pinned as a documented gap;
    closing it needs directional bearing semantics (CL-gated)."""
    adj = _contact_adjacency(bearings, bonds, tol)
    multi_surface = len(surfaces) > 1
    out: list[Finding] = []
    for s in surfaces:
        f = _check_one(s, foundations, adj, overhang_tol)
        if multi_surface:
            # DISCLOSE the cross-surface residual on the finding itself — visible
            # on the family's report surface, never silent (task SUPPORT v1.1 B).
            f = Finding(f.check, f.subject, f.passed,
                        f.detail + MULTI_SURFACE_CAVEAT, verdict=f.verdict)
        out.append(f)
    return out


#: Appended to every support finding when a model has >1 walking surface — the
#: honest, VISIBLE disclosure of the cross-surface residual (task SUPPORT v1.1
#: Option B). Rung-3 language; names the follow-up. No shipped detail has >1
#: surface, so this never touches the platform/site findings.
MULTI_SURFACE_CAVEAT = (
    " [rung-3 limit: with multiple walking surfaces, cross-surface support "
    "borrowing is NOT verified here — a support bearing on another surface's "
    "frame rather than a foundation can pass; closing it needs directional "
    "bearing semantics (CL-gated)]")


def _bears_independently(support, foundations: set, adj: dict,
                         blocked: set) -> bool:
    """Does ``support`` reach a FOUNDATION without routing through ``blocked``?
    (task SUPPORT v1.1.) ``blocked`` is THIS surface's held-up frame
    (:func:`_surface_side`) plus its sibling declared supports — so within a
    single surface a support can no longer reach ground by borrowing a foundation
    UP through the frame it clamps or SIDEWAYS through a sibling; it must descend
    through its own foundation-side chain. NB the frame set is PER-SURFACE, so a
    phantom in one surface can still borrow ANOTHER surface's foundation through
    that surface's frame — the disclosed multi-surface residual."""
    seen = {support.id}
    q = deque([support.id])
    while q:
        for m in adj.get(q.popleft(), ()):
            if m in seen or m in blocked:
                continue
            if m in foundations:
                return True
            seen.add(m)
            q.append(m)
    return False


def _check_one(s: ResolvedSurface, foundations, adj, overhang_tol) -> Finding:
    # Subject shape ``<label>: <member parts>`` (the connection_hardware/load_path
    # pattern): the member part names after ": " let the finding slice into every
    # view that scopes the occupied surface, so a viewer of that subsystem sees
    # the support verdict — never a silently-dropped finding.
    subject = (f"walking surface {s.label}: "
               + ", ".join(p.name for p in s.members))

    if s.deferred_support:
        return Finding(
            "support", subject, False,
            f"support is DEFERRED ({s.deferred_support}) — an intentionally "
            f"incomplete structure reports FAIL until the support is designed; "
            f"rung 3: support NOT represented")

    # EXISTENCE obligation (task SUPPORT v1.1): a support named in the scheme that
    # is not a part in the model (removed / mistyped) fails by declaration —
    # naming exactly what was declared vs what reality shows.
    if s.missing_supports:
        names = ", ".join(sorted(s.missing_supports))
        return Finding(
            "support", subject, False,
            f"declared support(s) {names} are not in the model — a declared "
            f"support must exist and bear; rung 3: support NOT represented")

    if not foundations:
        return Finding(
            "support", subject, False,
            f"no foundation is declared (a part with role {GROUND_ROLE!r}); the "
            f"occupied surface's support cannot reach ground; rung 3: support "
            f"NOT represented")

    # BEARING obligation (task SUPPORT v1.1): each declared support must reach a
    # foundation through its OWN foundation-side chain — never by borrowing a
    # foundation UP through the held-up frame or SIDEWAYS through a sibling. The
    # frame is the surface-side set (reachable from the members without a
    # support); blocking it + the siblings forces an honest descent.
    support_ids = {p.id for p in s.supports}
    member_ids = {p.id for p in s.members}
    frame = _surface_side(member_ids, support_ids, adj)
    grounded, ungrounded = [], []
    for sup in s.supports:
        blocked = (frame | support_ids) - {sup.id} - foundations
        (grounded if _bears_independently(sup, foundations, adj, blocked)
         else ungrounded).append(sup)

    if ungrounded:
        names = ", ".join(p.name for p in ungrounded)
        return Finding(
            "support", subject, False,
            f"declared support(s) {names} do not bear down to a foundation "
            f"(role {GROUND_ROLE!r}) on their own — a support that reaches ground "
            f"only through a sibling support or the surface it holds up is not "
            f"bearing; rung 3: support NOT represented")
    if not grounded:
        return Finding(
            "support", subject, False,
            f"no declared support reaches a foundation; rung 3: support NOT "
            f"represented")

    W = _plan_box(s.members)
    S = _plan_box(grounded)
    over = _overhangs(W, S)
    unsupported = {e for e, d in over.items()
                   if d > overhang_tol and e not in s.cantilever_edges}
    sup_names = ", ".join(p.name for p in grounded)
    cant = ""
    if s.cantilever_edges:
        cant = ("; declared cantilever(s): "
                + ", ".join(sorted(s.cantilever_edges)))

    if not unsupported:
        return Finding(
            "support", subject, True,
            f"occupied region sits over grounded supports [{sup_names}]{cant}; "
            f"support REPRESENTED (rung 3) — structural adequacy NOT ANALYZED "
            f"(rung 4)")

    one_sided = sorted(e for e in unsupported if _OPPOSITE[e] not in unsupported)
    if one_sided:
        detail = "; ".join(
            f"{e} by {_fmt_in(over[e])}" for e in one_sided)
        return Finding(
            "support", subject, False,
            f"occupied region overhangs its grounded supports [{sup_names}] with "
            f"no declared cantilever ({detail}) — that region is not supported; "
            f"rung 3: support NOT represented")

    # All unsupported edges are balanced across their axis: interior support,
    # ambiguous intent — honest UNKNOWN, not a fake FAIL.
    axes = sorted({e[1] for e in unsupported})
    detail = ", ".join(f"{e} by {_fmt_in(over[e])}" for e in sorted(unsupported))
    return Finding(
        "support", subject, False,
        f"occupied region overhangs its support [{sup_names}] on both sides of "
        f"{'/'.join(axes)} ({detail}); whether the represented support holds the "
        f"whole surface is NOT ANALYZED at rung 3 — declare a cantilever to "
        f"represent intent, or add supports",
        verdict=UNKNOWN_VERDICT)
