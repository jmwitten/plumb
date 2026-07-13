"""Affected-region computation (INCR-4) — the bounded consequence of an edit.

Given an edit — the set of authored ids INCR-3's :func:`revision_diff` reports as
physically changed (moved / resized / vanished / appeared) — this module computes
the **affected region**: the sub-model a correct recompile must revisit, and only
that. It is the fourth INCR piece and stands on the three merged below it
(incr-design.md §4, §6 item 3, §10.4):

- **INCR-1** (:mod:`detailgen.spec.identity`) — the authored-id bridge. A seed
  arrives as an insertion-stable authored id (``beam_pY``, ``platform/beam_pY`` on
  the composed site) and is resolved to its evidence-graph ``part:`` node through
  the bridge. A ``bind:``-merged site member is ONE node under a canonical id plus
  retired aliases; the seed keys on the canonical id, so an alias's member changing
  is the canonical node's region — no leakage, no missed propagation.
- **INCR-3** (:mod:`detailgen.incremental.revision_diff`) — the seed. The region is
  seeded by :meth:`~detailgen.incremental.revision_diff.RevisionDiff.changed_authored_ids`
  (moved ∪ resized ∪ vanished ∪ appeared). A *persisted* member — including a pure
  rename — seeds nothing: nothing about it changed for the region to invalidate.

The substrate is the **evidence graph** (:mod:`detailgen.validation.evidence`),
already built by the ``validate → evidence_graph`` lifecycle. The region is a
transitive closure over the edges the graph ALREADY indexes — the binding directive
(AD#5 item 5, progress.md:1041-1042) is emphatic that this is built ON the existing
dependency edges, adding **no new edge kind and no new tracker**. This module reads
``edges_from`` / ``edges_into`` in O(degree) and never mutates the graph, so every
frozen baseline stays byte-stable.

Placement (design §10.4 asks the implementer to pick and justify): this lives in
the incremental layer, *beside* :class:`~detailgen.validation.evidence.EvidenceGraph`
rather than as a method *on* it, because the region needs the authored-id bridge
(:mod:`detailgen.spec.identity`) and the diff seed
(:mod:`detailgen.incremental.revision_diff`) — both above the validation layer.
Keeping the region here preserves ``evidence.py`` as a dependency-free substrate (it
imports nothing from ``spec``/``incremental``), which is what keeps its serialized
graph baseline byte-stable.

SOUNDNESS is the invariant (brief; design §9 R2, AC2). Every part, finding, and
derived fact a whole-world recompile would show changed MUST be inside the region;
an under-claim is a defect. Over-claim is tolerated in v1 (Q4 — precision measured,
not gated) and is reported by :meth:`AffectedRegion.metrics`. Two soundness moves
earn the invariant on the real model:

1. **A changed part's one-hop invalidation, closed to its findings.** A finding
   changes only if a part it CHECKS changed; every such finding reaches the changed
   part through a ``concerns`` edge, so seeding the closure from the changed parts
   and following ``concerns`` (into facts and findings) and ``generated`` (fact →
   finding) captures every changed finding. Construction neighbours (``bears_on`` …)
   and bearing-pair partners are added as *revisit context* — they did not
   themselves change, so they do NOT re-seed the closure (a finding never pulls in
   the other part it concerns). That restraint is both what keeps the region a small
   fraction of the model for a local edit (AC3) and what keeps a platform edit from
   leaking across a ``bind:`` boundary into another detail (AC4): were the closure to
   chase an interference finding back to its partner part, one deck board's edit
   would drag in every part it is pair-checked against, some in another subsystem.

2. **The unattributed-findings floor.** A handful of findings carry no ``concerns``
   edge because their subject shape is not one the graph parses into a part link —
   on the platform: 16 ``through_hole`` (``bolt … through …``), plus one each of
   ``floating`` (``all parts grounded`` — a genuinely global check), ``faces_away``
   (``rung … faces away …``), and ``support`` (``walking surface deck: …``). The
   graph cannot attribute these to a part, so a changed part cannot reach them by any
   edge — yet a real edit DOES flip them (measured: extending the deck run flips the
   ``faces_away`` and ``support`` findings). To stay sound the region includes EVERY
   such unattributed finding whenever the seed is non-empty. This is a bounded,
   subject-shape-agnostic over-claim (19 of 10,719 ≈ 0.18% on the platform): a future
   check that emits an unparsed subject simply joins the floor and is never missed,
   rather than silently under-claimed by a brittle per-shape subject parser.

The output (:class:`AffectedRegion`) is a plain, JSON-serializable data object —
parts keyed by authored id, findings by their ``(check, subject)`` signature,
declarations and facts by node id — for the INCR-5 consumer to scope golden
regeneration and attribute the fingerprint diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..spec.identity import AuthoredIdentity, SpecIdentityError
from ..validation.evidence import EvidenceGraph, _CONSTRUCTION_EDGE_KINDS
from .revision_diff import RevisionDiff, revision_diff

#: A finding's id-free identity signature (matches INCR-3's ``FindingSig``).
FindingSig = tuple[str, str]  # (check, subject)


@dataclass(frozen=True)
class AffectedRegion:
    """The bounded consequence of an edit — parts + declarations + facts + findings
    a correct recompile must revisit. All fields are id-keyed and JSON-serializable
    (:meth:`to_dict`):

    - ``seeds`` — the changed authored ids that seeded this region (those present in
      the model it was computed over; a seed that belongs to the other revision of a
      cross-graph edit is resolved there, not here).
    - ``parts`` — authored ids in the region: the seeds plus their construction
      neighbours and bearing-pair partners (the *revisit* set). ``neighbors`` is the
      derived ``parts − seeds``.
    - ``declarations`` / ``facts`` — evidence-graph node ids (``decl:…`` / ``fact:i``)
      for the authored declarations and derived facts implicated.
    - ``findings`` — the ``(check, subject)`` signatures a recompile must revisit;
      ``unattributed_findings`` is the floor subset the graph could not link to a
      part (reported for honesty about the over-claim).
    - ``total_findings`` — findings in the whole model, the denominator for the
      region-size metric (AC3 / AD#6.4)."""

    seeds: frozenset[str]
    parts: frozenset[str]
    declarations: frozenset[str]
    facts: frozenset[str]
    findings: frozenset[FindingSig]
    unattributed_findings: frozenset[FindingSig]
    total_findings: int

    @property
    def neighbors(self) -> frozenset[str]:
        """Region parts that were not themselves seeds — construction neighbours and
        bearing-pair partners pulled in as revisit context."""
        return self.parts - self.seeds

    @property
    def is_empty(self) -> bool:
        """True when nothing seeded the region (an edit that did not reach this
        model — the AC4 cross-detail case: a platform edit leaves ``rock_anchor``'s
        region empty)."""
        return not self.seeds

    def metrics(self) -> dict:
        """The AD#6.4 region-size metrics for one edit: node counts by kind and the
        affected-region size as a fraction of the model's findings (AC3). A local
        single-member edit keeps this fraction small; a report of ``region == whole
        model`` for a local edit would be a soundness bug surfacing as a size."""
        n_find = len(self.findings)
        return {
            "seeds": len(self.seeds),
            "parts": len(self.parts),
            "neighbors": len(self.neighbors),
            "declarations": len(self.declarations),
            "facts": len(self.facts),
            "findings": n_find,
            "unattributed_findings": len(self.unattributed_findings),
            "total_findings": self.total_findings,
            "finding_fraction": (n_find / self.total_findings
                                 if self.total_findings else 0.0),
        }

    def to_dict(self) -> dict:
        return {
            "seeds": sorted(self.seeds),
            "parts": sorted(self.parts),
            "declarations": sorted(self.declarations),
            "facts": sorted(self.facts),
            "findings": [list(s) for s in sorted(self.findings)],
            "unattributed_findings": [list(s) for s in
                                      sorted(self.unattributed_findings)],
            "total_findings": self.total_findings,
            "metrics": self.metrics(),
        }

    def union(self, other: "AffectedRegion") -> "AffectedRegion":
        """Merge two regions computed over the two revisions of one edit (the new
        graph's region for moved/resized/appeared seeds, the old graph's for
        vanished). Stable-id-keyed, so the union is a plain set union; the finding
        denominator is the larger of the two revision totals."""
        return AffectedRegion(
            seeds=self.seeds | other.seeds,
            parts=self.parts | other.parts,
            declarations=self.declarations | other.declarations,
            facts=self.facts | other.facts,
            findings=self.findings | other.findings,
            unattributed_findings=(self.unattributed_findings
                                   | other.unattributed_findings),
            total_findings=max(self.total_findings, other.total_findings),
        )


def _finding_sig(node) -> FindingSig:
    return (node.attrs["check"], node.attrs["subject"])


def _region_node_ids(graph: EvidenceGraph, seed_nids: set) -> tuple[set, set, set, set]:
    """The raw closure over graph node ids. Returns ``(part_nids, decl_nids,
    fact_nids, finding_nids)``. See the module docstring for the soundness argument;
    the layering here is its mechanical form."""
    node = graph.nodes
    part_nids: set = set(seed_nids)   # seeds + revisit context (neighbours/partners)
    decl_nids: set = set()
    fact_nids: set = set()
    finding_nids: set = set()
    invalidated_facts: list = []      # facts concerning a CHANGED part — they propagate

    # Layer 1 — each CHANGED (seed) part's one-hop invalidation + construction
    # neighbours. A changed part invalidates the facts and findings that ``concerns``
    # it (edges INTO the part), names the declarations that ``involves`` it, and is
    # adjacent to its construction neighbours (either edge direction).
    for pid in seed_nids:
        for e in graph.edges_into(pid):
            kind = e.kind
            if kind == "involves":
                decl_nids.add(e.src)
            elif kind in _CONSTRUCTION_EDGE_KINDS:
                part_nids.add(e.src)                       # neighbour (revisit context)
            elif kind == "concerns":
                src_kind = node[e.src].kind
                if src_kind == "derived_fact":
                    if e.src not in fact_nids:
                        fact_nids.add(e.src)
                        invalidated_facts.append(e.src)
                elif src_kind == "finding":
                    finding_nids.add(e.src)
        for e in graph.edges_from(pid):
            if e.kind in _CONSTRUCTION_EDGE_KINDS:
                part_nids.add(e.dst)                        # neighbour (revisit context)

    # Layer 2 — an invalidated derived fact carries to the findings it generated,
    # the declaration it derives from, and its OTHER concerned part (a bearing fact's
    # pair partner — revisit context, never a changed part that re-seeds the closure).
    for fid in invalidated_facts:
        for e in graph.edges_from(fid):
            if e.kind in ("generated", "proven_by"):
                finding_nids.add(e.dst)
            elif e.kind == "derived_from":
                decl_nids.add(e.dst)
            elif e.kind == "concerns":
                part_nids.add(e.dst)

    # Layer 3 — the unattributed-findings floor. A finding with no ``concerns`` edge
    # cannot be reached from any changed part; a sound region always revisits it when
    # the edit is non-empty (module docstring, soundness move 2).
    if seed_nids:
        for n in graph.nodes_of_kind("finding"):
            if not any(e.kind == "concerns" for e in graph.edges_from(n.id)):
                finding_nids.add(n.id)

    # Layer 4 — complete the evidence subgraph: each region finding's generator (the
    # fact or declaration that produced it) is part of the region. A finding never
    # re-seeds a part, so this cannot expand the part set (module docstring: keeping
    # partners out is what preserves cross-detail isolation).
    for fid in finding_nids:
        for e in graph.edges_into(fid):
            if e.kind in ("generated", "proven_by"):
                src_kind = node[e.src].kind
                if src_kind == "derived_fact":
                    fact_nids.add(e.src)
                elif src_kind == "declaration":
                    decl_nids.add(e.src)

    return part_nids, decl_nids, fact_nids, finding_nids


def affected_region(detail, seed_authored_ids) -> AffectedRegion:
    """Compute the affected region of an edit over one compiled model.

    ``detail`` is a compiled detail or composed site (validated if needed — the
    evidence graph reads its lifecycle outputs); ``seed_authored_ids`` are the
    changed authored ids to seed from (typically
    :meth:`RevisionDiff.changed_authored_ids`). A seed id not present in THIS model
    is silently skipped, not an error — for a cross-graph edit the moved/resized/
    appeared ids live in the new model and the vanished ids in the old, so each
    model's region is seeded only by the ids it actually carries (:func:`edit_region`
    unions the two). Read-only; builds no persistence and mutates no baseline."""
    graph = EvidenceGraph.from_detail(detail)
    identity = AuthoredIdentity(detail)

    present_seeds: set = set()
    seed_nids: set = set()
    for aid in seed_authored_ids:
        try:
            nid = identity.graph_nid_of(aid)
        except SpecIdentityError:
            continue  # not a member of this revision's model (the other graph's seed)
        if nid in graph.nodes:
            # Record the CANONICAL authored id, not the id passed in: a seed handed a
            # retired ``bind:`` alias (``tree/beam_mY``) is the canonical node's region
            # (``platform/beam_mY``) — no alias leakage into the reported seed set.
            seed_nids.add(nid)
            present_seeds.add(identity.authored_id_of_graph_nid(nid))

    part_nids, decl_nids, fact_nids, finding_nids = _region_node_ids(graph, seed_nids)

    parts: set = set()
    for pid in part_nids:
        try:
            parts.add(identity.authored_id_of_graph_nid(pid))
        except SpecIdentityError:
            # A built part no declaration names (empty on today's corpus) — report it
            # by its build-order id rather than fabricating an authored one.
            parts.add(pid.removeprefix("part:"))

    findings = {_finding_sig(graph.nodes[fid]) for fid in finding_nids}
    unattributed = {
        _finding_sig(n) for n in graph.nodes_of_kind("finding")
        if not any(e.kind == "concerns" for e in graph.edges_from(n.id))
    } if seed_nids else set()

    return AffectedRegion(
        seeds=frozenset(present_seeds),
        parts=frozenset(parts),
        declarations=frozenset(decl_nids),
        facts=frozenset(fact_nids),
        findings=frozenset(findings),
        unattributed_findings=frozenset(unattributed),
        total_findings=len(graph.nodes_of_kind("finding")),
    )


def edit_region(old_detail, new_detail, diff: RevisionDiff | None = None) -> AffectedRegion:
    """The affected region of a whole edit, from the two compiled revisions. Runs
    (or is handed) the INCR-3 diff, then unions the new model's region for the
    moved/resized/appeared ids with the old model's region for the vanished ids —
    because a vanished member's consequences live in the graph where it still
    existed. Read-only end to end."""
    if diff is None:
        diff = revision_diff(old_detail, new_detail)
    members = diff.members
    new_seeds = frozenset(members.moved) | frozenset(members.resized) \
        | frozenset(members.appeared)
    old_seeds = frozenset(members.vanished)

    new_region = affected_region(new_detail, new_seeds)
    if not old_seeds:
        return new_region
    old_region = affected_region(old_detail, old_seeds)
    return new_region.union(old_region)
