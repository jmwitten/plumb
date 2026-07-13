"""Foundation-role obligation pack — the R29 retirement (task FAB-3).

The mirror image of the SUPPORT check (:mod:`detailgen.validation.support`): where
that check asks "is a walking_surface actually SUPPORTED?", this one asks the
foundation-side question a pier block a leg merely *rests on* left unanswered —
"is a post that BEARS on a foundation actually ATTACHED to it, and is that
foundation founded?". R29 (``retro-index.md:66``): the platform rendered a leg
resting on a pier block, with a bearing pair and a ``ground`` label, and **no
attachment at all**, and still read CLEAN. This pack makes that absence a loud
verdict instead of a silent gap — the same ``check_bearing``-vs-``expected_
overlaps`` lesson the Connection module names: a bearing PERMITS contact but must
never STAND IN for a fastened joint.

Three obligations, generated per foundation body / declared system, each pinned
to a rung of the epistemic ladder (never implying a stronger claim than proven):

- **ATTACHMENT** (``foundation_attachment``, rung 3 — Support/Stability). A post
  that bears on a foundation MUST have a declared post base fastening it down. No
  declared attachment = a loud FAIL naming the post and the block (uplift/lateral
  path undefined). A declared attachment = PASS: the attachment is REPRESENTED,
  never proven adequate.
- **EMBEDMENT / FROST** (``foundation_embedment``, rung 3 — Support/Stability).
  The foundation body's buried depth against frost — the same geometric check
  :class:`~detailgen.components.concrete.ConcretePier` already carries, now
  generated for every declared foundation body. A block set shallower than a
  DECLARED frost depth FAILs; with no frost depth declared the buried depth is
  REPRESENTED (frost adequacy folds into the capacity UNKNOWN below).
- **CAPACITY** (``foundation_capacity``, rung 4 — Structural capacity). Uplift,
  lateral resistance and soil bearing are an HONEST, BLOCKING **UNKNOWN** — never
  a number, never CLEAN (design risk R2: the temptation to compute a capacity
  number is out of scope BY CONSTRUCTION). A declared-but-uncharacterised
  foundation is REPRESENTED, and the build refuses to call it "designed": the
  UNKNOWN verdict blocks a clean export, exactly as the support check's does.

The verdicts are family-tagged via
:data:`detailgen.validation.coverage.KIND_TO_FAMILY`; ``foundation_attachment`` /
``foundation_embedment`` land in Support/Stability (rung 3, the roles-generate-
support-and-stability-obligations family), and ``foundation_capacity`` in
Structural capacity (rung 4) so the two rungs never blur into one verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.units import IN, fmt_in
from .checks import Finding, UNKNOWN_VERDICT


@dataclass(frozen=True)
class ResolvedFoundation:
    """A declared foundation system with its cids resolved to placed parts — the
    shape :func:`check_foundations` consumes for its embedment/capacity
    obligations and the declared-attachment lookup its attachment obligation
    cross-references against the geometry's real post->foundation bearings."""

    label: str
    post: object            # the placed post the system carries
    block: object           # the placed foundation body
    post_base: object = None  # the placed attachment connector, or None (undesigned)
    uplift: str = ""
    bearing_on_grade: str = "field_verify"
    frost_depth: float | None = None  # mm, or None (frost not declared)


def _foundation_bearings(bearings, foundation_ids: set):
    """The ``(post, foundation)`` placed-part pairs where a structural member
    bears on a foundation body — the geometric fact the attachment obligation
    keys on. A bearing with a foundation body on exactly one side names that
    side the foundation and the other side the post; a pair with a foundation on
    both sides or neither is not a post-on-foundation bearing and is skipped."""
    out = []
    seen = set()
    for spec in bearings:
        a, b = spec[0], spec[1]
        a_found = a.id in foundation_ids
        b_found = b.id in foundation_ids
        if a_found == b_found:
            continue  # both foundations or neither — not a post-on-foundation pair
        post, block = (b, a) if a_found else (a, b)
        key = (post.id, block.id)
        if key in seen:
            continue
        seen.add(key)
        out.append((post, block))
    return out


def check_foundations(systems, *, foundation_ids: set, bearings) -> list[Finding]:
    """The foundation-role obligation findings, deterministic in input order.

    ``systems`` are the declared :class:`ResolvedFoundation`\\ s; ``foundation_ids``
    the set of placed-part ids carrying a FOUNDATION (``ground``) role;
    ``bearings`` the resolved ``(a, b, axis, area)`` contact pairs the sweep ran
    on (the SAME list, so the attachment obligation reasons about real geometry,
    not a re-derivation).

    Emits, in order: one ``foundation_attachment`` per post-on-foundation bearing
    (PASS iff a system with a post base joins that exact pair, else a loud FAIL);
    then, per declared system that HAS a post base, EITHER a loud
    ``foundation_attachment`` FAIL when its declared ``(post, block)`` do not
    actually bear (the existence obligation — the mirror of SUPPORT's
    ``missing_supports``, so a foundation whose post does not rest on its block is
    caught, not silently "represented"), OR — when they do bear — one
    ``foundation_embedment`` and one blocking ``foundation_capacity`` UNKNOWN. A
    system without a post base contributes no embedment/capacity finding — its
    attachment FAIL already tells the whole truth."""
    out: list[Finding] = []

    # {(post_id, block_id): system} for systems that declare a post base — the
    # attachments that actually exist. A system with no post base is NOT a
    # satisfied attachment (it is an explicitly-undesigned foundation).
    attached: dict[tuple[str, str], ResolvedFoundation] = {
        (s.post.id, s.block.id): s for s in systems if s.post_base is not None}

    # -- (a) ATTACHMENT — driven by the real post-on-foundation bearings --------
    for post, block in _foundation_bearings(bearings, foundation_ids):
        subject = f"{post.name} -> {block.name}"
        system = attached.get((post.id, block.id))
        if system is not None:
            out.append(Finding(
                "foundation_attachment", subject, True,
                f"post base {system.post_base.name!r} ({system.label}) fastens "
                f"{post.name} DOWN onto {block.name}; attachment REPRESENTED "
                f"(rung 3) — uplift/lateral capacity NOT ANALYZED (rung 4)"))
        else:
            out.append(Finding(
                "foundation_attachment", subject, False,
                f"{post.name} bears on foundation {block.name} with NO declared "
                f"post base — the uplift/lateral attachment is undefined (a "
                f"bearing pair permits contact but cannot stand in for a fastened "
                f"joint). Declare a foundation system with a post_base joining "
                f"them; rung 3: attachment NOT represented"))

    # -- COHERENCE + (b) EMBEDMENT/FROST + (c) CAPACITY — per declared system ----
    # A declared foundation whose post does NOT actually bear on its block is
    # silent nonsense: it would place a disconnected post-base part and emit
    # embedment PASS + capacity UNKNOWN as if the system were real. The existence
    # obligation — the mirror of SUPPORT's ``missing_supports`` — makes that a loud
    # FAIL naming both, and suppresses the embedment/capacity findings that would
    # dress up a physically-absent attachment as "represented".
    all_bearing_keys = {frozenset((spec[0].id, spec[1].id)) for spec in bearings}
    for s in systems:
        if s.post_base is None:
            continue
        if frozenset((s.post.id, s.block.id)) not in all_bearing_keys:
            out.append(Finding(
                "foundation_attachment", f"{s.post.name} -> {s.block.name}", False,
                f"foundation {s.label!r} declares a post base joining {s.post.name} "
                f"to {s.block.name}, but {s.post.name} does NOT bear on "
                f"{s.block.name} (no bearing between them) — a post base for a post "
                f"that does not rest on its block is a disconnected part, not an "
                f"attachment. Declare the bearing, or fix the supports/block "
                f"reference; rung 3: attachment NOT represented"))
            continue
        out.append(_embedment_finding(s))
        out.append(_capacity_finding(s))
    return out


def _buried_depth(block) -> float | None:
    """The foundation body's buried depth below grade, or ``None`` when the block
    type does not model it (embedment then can't be a geometric verdict)."""
    depth = getattr(block.component, "buried_depth", None)
    return None if depth is None else float(depth)


def _embedment_finding(s: ResolvedFoundation) -> Finding:
    subject = f"{s.label}: {s.block.name}"
    buried = _buried_depth(s.block)
    if s.frost_depth is not None:
        if buried is None:
            return Finding(
                "foundation_embedment", subject, True,
                f"frost depth {fmt_in(s.frost_depth)} declared but {s.block.name} "
                f"does not model a buried depth — embedment REPRESENTED, "
                f"field-verify (rung 3)")
        if buried < s.frost_depth:
            return Finding(
                "foundation_embedment", subject, False,
                f"{s.block.name} is {fmt_in(buried)} below grade — shallower than "
                f"the declared frost depth {fmt_in(s.frost_depth)}; a block above "
                f"frost heaves. Deepen the foundation; rung 3: embedment NOT "
                f"represented")
        return Finding(
            "foundation_embedment", subject, True,
            f"{s.block.name} is {fmt_in(buried)} below grade, at/below the "
            f"declared frost depth {fmt_in(s.frost_depth)}; embedment REPRESENTED "
            f"(rung 3)")
    # No frost depth declared: the buried depth is REPRESENTED; frost ADEQUACY is
    # a field-verify question that folds into the capacity UNKNOWN below.
    depth_note = ("" if buried is None
                  else f" (buried {fmt_in(buried)})")
    return Finding(
        "foundation_embedment", subject, True,
        f"{s.block.name} embedment REPRESENTED{depth_note}; no frost depth "
        f"declared — frost adequacy is field-verify (bearing_on_grade: "
        f"{s.bearing_on_grade}), folded into the capacity UNKNOWN (rung 3)")


def _capacity_finding(s: ResolvedFoundation) -> Finding:
    return Finding(
        "foundation_capacity", f"{s.label}: {s.post.name} -> {s.block.name}",
        False,
        f"uplift / lateral / soil-bearing capacity of {s.label} is NOT ANALYZED "
        f"(rung 4, engineer-of-record) — a represented foundation is never proven "
        f"adequate; bearing_on_grade: {s.bearing_on_grade}. This BLOCKS a clean "
        f"'designed': the foundation is REPRESENTED, not verified",
        verdict=UNKNOWN_VERDICT)
