"""Scoped golden regeneration + diff attribution (INCR-5) — the v1 consumer.

This is the first thing that *uses* the affected region (INCR-4) to retire a real
tax: the hand re-baseline of the golden corpus (retro **R11** — one part-count
change ripples ~10 fixtures by hand today). It is read-only and self-verifying,
exactly the consumer incr-design §4.3 chose for v1: it proves the region is sound
while touching no correctness-critical code, because all it does is *read* the
compiled models and decide which committed goldens a given edit could have changed.

The golden surface it scopes is the per-detail **content-line** taxonomy — the
``F|`` finding / ``D|`` derivation / ``B|`` BOM-row / ``T|`` transform lines that
``tests/baseline_lib.content_lines`` emits and every frozen-truth fingerprint hashes
(``content_fp`` = sha256 of these lines). content_lines lives under ``tests/`` and is
a baseline-surface concern, so it is **injected** (``golden_fn``) rather than
imported up from the validation layer; this module owns only the region-driven
scoping and the attribution of that line taxonomy, which incr-design §4.3 names as
the consumer's job (it "predicts which ``T|`` transforms, which ``F|`` findings,
which ``B|`` BOM rows change").

Three moves, matching the brief:

1. **Scoped regeneration** (:func:`scoped_regen`). Given a *world* — a set of details
   each in a before/after revision pair — a detail whose affected region is EMPTY is
   not regenerated: its golden is REUSED from the base revision untouched. Only a
   detail the edit's region reaches is recomputed. A platform beam-nudge therefore
   never rewrites ``rock_anchor``'s golden (AC4 / the STRUCT lesson, incr-design §5).

2. **Diff attribution** (:func:`_attribute`). Within a regenerated detail, every
   content line that actually changed (base→new) is attributed to the region member
   that explains it — an ``F|`` line to the ``(check, subject)`` finding in the
   region, a ``T|``/``B|``/``D|`` line to the authored id of a region part it names.
   A changed line NO region member explains is a LOUD **anomaly**, never a shrug: it
   means the region missed a line the edit changed (unsound) — the exact failure the
   attribution exists to surface.

3. **The self-verify gate** (:func:`self_verify`) — AC2, the acceptance gate of the
   whole INCR arc, and it is INDEPENDENT by construction. The whole-world comparison
   side (:func:`whole_world_golden`) is the OLD full path: ``golden_fn`` over every
   new revision, with **zero region input** — no diff, no region, no scoping
   (incr-design's non-circularity requirement, review-incrdesign item 2). The gate
   asserts the region-scoped output equals that whole-world output BYTE FOR BYTE, and
   that no regenerated detail carried an attribution anomaly. A byte difference or an
   anomaly means the region or the consumer is wrong — investigate, never widen the
   region to pass.

Read-only end to end: this module compiles and reads models and never writes a
committed baseline. The tooling that *does* write (``scripts/regen_baselines.py
--scoped``) calls :func:`self_verify` first and refuses to write on any mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .affected_region import AffectedRegion, edit_region
from .revision_diff import revision_diff
from ..spec.identity import AuthoredIdentity

#: A per-detail golden: the sorted content lines of one validated revision.
Golden = tuple[str, ...]
#: ``slug -> (base_detail, new_detail)`` — one detail's revision pair. The base and
#: new are already-compiled, already-validated models (the caller owns compilation).
World = dict[str, tuple[object, object]]
#: ``detail -> sorted content lines`` (``tests/baseline_lib.content_lines``), injected
#: so this module does not import a ``tests/`` surface up into the package.
GoldenFn = Callable[[object], list[str]]


def _pos_to_authored(detail) -> dict[str, str | None]:
    """Map every built part's positional ``Placed.id`` (what ``content_lines`` keys
    ``T|`` / ``B|`` / ``D|`` lines on) to its insertion-stable authored id (what the
    region keys parts on). ``None`` for a part no declaration names — such a part is
    not a region member, so a line naming only it is honestly unattributable."""
    ident = AuthoredIdentity(detail)
    return {p.id: ident.try_authored_id_of(p) for p in detail.assembly.parts}


def _normalize_line(line: str, pos2auth: dict) -> str:
    """Rewrite a content line's build-order ``Placed.id``s to their insertion-stable
    authored ids. This is the load-bearing move that makes attribution honest.

    ``content_lines`` keys ``T|`` / ``B|`` / ``D|`` lines on the positional
    ``Placed.id`` (a build-order ordinal — incr-design Finding 1), so inserting a part
    EARLIER in build order renumbers every later part and churns its golden line even
    though nothing about that part changed (``structural_screw-74`` → ``-86``, same
    geometry). The affected region speaks only in authored ids and CORRECTLY excludes
    such a part — it did not semantically change. Attributing over the raw
    positional-keyed diff would therefore read pure ordinal shift as an unexplained
    change; attributing over the AUTHORED-ID-NORMALIZED diff drops exactly that noise
    while preserving every real change (a genuine move alters the non-id content, so
    it survives normalization and, if the region missed it, still surfaces as a loud
    anomaly). A part with no authored id keeps its positional id — an honestly
    unattributable line, not a silent pass. The byte-level self-verify gate compares
    the RAW golden bytes, so this normalization affects attribution only, never the
    bytes a scoped regen would write."""
    kind = line[0]
    f = line.split("|")
    if kind == "T":
        f[1] = pos2auth.get(f[1]) or f[1]
    elif kind in ("B", "D"):
        f[-1] = ";".join(sorted(
            (pos2auth.get(t) or t) for t in f[-1].split(";") if t))
    return "|".join(f)


def _line_member(line: str, region: AffectedRegion) -> str | None:
    """The region member that explains one AUTHORED-ID-NORMALIZED content line, or
    ``None`` if none does (an anomaly).

    The line taxonomy is ``tests/baseline_lib.content_lines``, with positional ids
    already rewritten to authored ids by :func:`_normalize_line`:
      - ``F|check|subject|passed|detail`` — a finding; keyed by ``(check, subject)``
        (the first two fields, before any ``|`` a detail string carries), matched
        against :attr:`AffectedRegion.findings`.
      - ``T|authored_id|origin|x|y|z`` — a part transform; explained iff the id
        (field 1) is in :attr:`AffectedRegion.parts`.
      - ``B|…|ids`` / ``D|…|subjects`` — a BOM row / derivation fact; explained iff any
        trailing ``;``-joined authored id is in the region's parts."""
    kind = line[0]
    fields = line.split("|")
    if kind == "F":
        sig = (fields[1], fields[2])
        return f"finding:{fields[1]}|{fields[2]}" if sig in region.findings else None
    if kind == "T":
        return fields[1] if fields[1] in region.parts else None
    if kind in ("B", "D"):
        for aid in (t for t in fields[-1].split(";") if t):
            if aid in region.parts:
                return aid
        return None
    return None  # an unknown line kind is unexplained by construction — loud.


@dataclass(frozen=True)
class LineAttribution:
    """The attribution of one regenerated detail's changed content lines.

    - ``attributed`` — ``(changed_line, member)`` for every changed line a region
      member explains (which authored id / finding signature accounts for it).
    - ``anomalies`` — changed lines NO region member explains. A non-empty anomaly
      set is the loud soundness signal: the region missed a line the edit changed."""

    attributed: tuple[tuple[str, str], ...]
    anomalies: tuple[str, ...]

    @property
    def is_sound(self) -> bool:
        return not self.anomalies


def _attribute(sem_added, sem_removed, region) -> LineAttribution:
    """Attribute a detail's SEMANTIC (authored-id-normalized) changed lines to region
    members. The caller has already normalized and re-diffed, so a pure positional
    renumber has cancelled out and never reaches here; what remains is the real
    change the region is expected to predict."""
    attributed: list[tuple[str, str]] = []
    anomalies: list[str] = []
    for line in list(sem_added) + list(sem_removed):
        member = _line_member(line, region)
        if member is None:
            anomalies.append(line)
        else:
            attributed.append((line, member))
    return LineAttribution(
        attributed=tuple(sorted(attributed)),
        anomalies=tuple(sorted(anomalies)),
    )


@dataclass(frozen=True)
class DetailRegen:
    """The scoped-regeneration outcome for one detail of the world.

    - ``regenerated`` — did the edit's region reach this detail (non-empty)? If not,
      ``golden`` is the base revision's lines REUSED verbatim (no recompute).
    - ``golden`` — the scoped output lines for this detail (new if regenerated, base
      if reused). This is what a scoped regen would write / leave in place.
    - ``added`` / ``removed`` — the RAW content-line diff base→new (the actual golden
      bytes that change; empty when reused). Includes positional-renumber churn.
    - ``renumbered`` — raw changed lines that are pure positional renumbering (an
      ordinal shift the region correctly does not attribute — reported, not an
      anomaly). ``raw churn − renumbered`` is the semantic diff attribution runs on.
    - ``attribution`` — the diff attribution over the semantic (normalized) diff
      (empty/sound when reused)."""

    slug: str
    regenerated: bool
    region: AffectedRegion
    golden: Golden
    added: tuple[str, ...]
    removed: tuple[str, ...]
    renumbered: int
    attribution: LineAttribution

    @property
    def changed_lines(self) -> int:
        return len(self.added) + len(self.removed)

    @property
    def semantic_changed_lines(self) -> int:
        return self.changed_lines - self.renumbered


@dataclass(frozen=True)
class ScopedRegen:
    """The whole world's scoped-regeneration outcome — one :class:`DetailRegen` per
    detail, plus the churn and anomaly rollups the tooling and the AC2 gate read."""

    details: dict[str, DetailRegen]

    def regenerated_slugs(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, d in self.details.items() if d.regenerated))

    def reused_slugs(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, d in self.details.items() if not d.regenerated))

    def anomalies(self) -> dict[str, tuple[str, ...]]:
        """``slug -> anomalous lines`` for every detail that carried an attribution
        anomaly. Empty on a sound run."""
        return {s: d.attribution.anomalies for s, d in self.details.items()
                if d.attribution.anomalies}

    def churn(self) -> dict:
        """The before/after churn the brief asks for: whole-world regenerates EVERY
        detail; scoped regenerates only the in-region ones. ``changed_lines`` is the
        total attributed diff size across regenerated details."""
        n = len(self.details)
        regen = self.regenerated_slugs()
        return {
            "details": n,
            "whole_world_regenerated": n,          # the old path rewrites all
            "scoped_regenerated": len(regen),      # the region rewrites only these
            "reused": n - len(regen),
            "regenerated_slugs": list(regen),
            "changed_lines": sum(d.changed_lines for d in self.details.values()),
            "semantic_changed_lines": sum(
                d.semantic_changed_lines for d in self.details.values()),
            "renumbered_lines": sum(d.renumbered for d in self.details.values()),
        }


def scoped_regen(base_world: World, new_world: World, golden_fn: GoldenFn) -> ScopedRegen:
    """Scope the golden regeneration of a whole world by affected region.

    ``base_world`` / ``new_world`` map each ``slug`` to its compiled+validated
    (base, new) revision. For each detail: compute the edit's affected region
    (INCR-3 diff → INCR-4 region); if it is EMPTY the golden is the base lines reused
    untouched; if non-empty the golden is recomputed from the new revision and the
    base→new line diff is attributed to region members. Read-only."""
    out: dict[str, DetailRegen] = {}
    for slug, (base, _) in base_world.items():
        new = new_world[slug][1]
        diff = revision_diff(base, new)
        region = edit_region(base, new, diff)
        base_lines = tuple(golden_fn(base))
        if region.is_empty:
            out[slug] = DetailRegen(
                slug=slug, regenerated=False, region=region, golden=base_lines,
                added=(), removed=(), renumbered=0,
                attribution=LineAttribution(attributed=(), anomalies=()))
            continue
        new_lines = tuple(golden_fn(new))
        base_set, new_set = set(base_lines), set(new_lines)
        # RAW diff — the actual golden bytes that change (renumber churn included).
        added = tuple(sorted(new_set - base_set))
        removed = tuple(sorted(base_set - new_set))
        # SEMANTIC diff — normalize positional ids to authored ids and re-diff, so a
        # pure ordinal shift cancels; attribution runs on what genuinely changed.
        base_p2a, new_p2a = _pos_to_authored(base), _pos_to_authored(new)
        nb = {_normalize_line(l, base_p2a) for l in base_lines}
        nn = {_normalize_line(l, new_p2a) for l in new_lines}
        sem_added, sem_removed = nn - nb, nb - nn
        renumbered = (len(added) + len(removed)) - (len(sem_added) + len(sem_removed))
        attribution = _attribute(sem_added, sem_removed, region)
        out[slug] = DetailRegen(
            slug=slug, regenerated=True, region=region, golden=new_lines,
            added=added, removed=removed, renumbered=renumbered,
            attribution=attribution)
    return ScopedRegen(details=out)


def whole_world_golden(new_world: World, golden_fn: GoldenFn) -> dict[str, Golden]:
    """The OLD full path — the whole-world regeneration AC2 compares against. It maps
    ``golden_fn`` over every detail's NEW revision with **zero region input**: no
    diff, no region, no scoping. This independence is the non-circularity the gate
    requires (incr-design's review item 2) — the comparison side must not consult the
    very region it is checking."""
    return {slug: tuple(golden_fn(new)) for slug, (_, new) in new_world.items()}


@dataclass(frozen=True)
class SelfVerify:
    """The AC2 self-verify result. ``passed`` iff the region-scoped golden equals the
    independent whole-world golden byte for byte on every detail AND no regenerated
    detail carried an attribution anomaly."""

    scoped: ScopedRegen
    mismatched_slugs: tuple[str, ...]      # scoped golden != whole-world golden
    anomaly_slugs: tuple[str, ...]         # detail with an unattributable changed line

    @property
    def passed(self) -> bool:
        return not self.mismatched_slugs and not self.anomaly_slugs


def self_verify(base_world: World, new_world: World, golden_fn: GoldenFn) -> SelfVerify:
    """AC2 — region-scoped regeneration == independent whole-world regeneration,
    byte-level, with sound attribution. Computes both sides and compares. A
    ``mismatched`` slug is a scoped golden that differs from the OLD-path golden (a
    detail the region wrongly left out, or wrongly recomputed); an ``anomaly`` slug is
    a regenerated detail with a changed line no region member explained. Either is a
    hard failure — the region or the consumer is wrong."""
    scoped = scoped_regen(base_world, new_world, golden_fn)
    whole = whole_world_golden(new_world, golden_fn)
    mismatched = tuple(sorted(
        slug for slug, dr in scoped.details.items() if dr.golden != whole[slug]))
    anomalies = tuple(sorted(scoped.anomalies()))
    return SelfVerify(scoped=scoped, mismatched_slugs=mismatched,
                      anomaly_slugs=anomalies)
