"""The Evidence Graph (task EVIDENCE, P4) — validation as PROOF GENERATION.

The derivation log (``DerivedFact``) answers "what did the platform infer?".
This module answers the harder question every engineering conclusion must
survive: **"WHY do we believe this?"** It assembles one queryable graph whose
nodes span the full chain the mission ledger names —

    authored declarations  →  derived facts  →  generated checks / findings
                                                        →  family verdicts

— so any conclusion can be walked back to the authored intent that caused it,
the rule that derived it, the assumptions it rests on, and the checks that
substantiate it. Nothing here re-derives or re-validates: the graph is
assembled entirely from outputs the existing ``Detail`` lifecycle already
produces (``connections()`` + ``compile_connections`` + the
``ValidationReport`` + the coverage matrix), so building it CANNOT change a
single validation outcome (proven byte-identical on rock_anchor and platform
by ``tests/test_evidence_equiv.py``).

Why a graph, and why now
------------------------
This is the data layer the Inspector (the compiler's future primary
interface — an engineering IDE, not a PDF) consumes: its four questions are
methods here (:meth:`~EvidenceGraph.what_is` / :meth:`~EvidenceGraph.why_here`
/ :meth:`~EvidenceGraph.how_verified` / :meth:`~EvidenceGraph.what_depends_on`),
each returning plain JSON-serializable data the HTML renders directly.

Two design commitments make the graph trustworthy rather than decorative:

1. **Completeness invariants (the honesty core), enforced at build time.**
   An orphan derived fact — one that traces to no authored declaration — is a
   HARD diagnostic (:class:`EvidenceGraphError`), never silently kept or
   dropped. Every finding traces to the fact or declaration that generated it.
   Every family verdict's substantiating findings match the coverage matrix's
   provenance exactly. The guards have teeth: see the mutation-style tests.

2. **The knowledge-source dimension (KNOWLEDGE STRATEGY), ORTHOGONAL to
   confidence.** Every fact and declaration node carries ``source_type``:

   - ``authoritative`` — ground truth the compiler must honor, not the output
     of inferential construction knowledge: an author's direct declaration
     (a ``Connection``'s declared parts/hardware, an imperative validation
     declaration), a verbatim restatement of one (the base
     ``required_hardware`` pass-through; a ``merge_into_spec`` dedup record),
     or an intrinsic physical/geometric law the framework checks
     unconditionally (non-interference, no-floaters, through-hole clearance,
     dimension-equals-intent).
   - ``verified_heuristic`` — a reviewed, promoted ``ConnectionType`` rule
     derived the fact (``bearing_pairs`` / ``allowed_intersections`` /
     ``bonded_pairs`` / ``edges``). Reusable construction knowledge: the
     KNOWLEDGE STRATEGY's middle tier.
   - ``llm_hypothesis`` — a candidate rule, NEVER build-blocking. NONE exist
     in the codebase today; the guarantee is enforced by construction
     (:func:`assert_llm_nonblocking`, run on every built graph): an
     ``llm_hypothesis`` node may only ANNOTATE, never ``generated``/
     ``proven_by`` a check that could fail.

   ``source_type`` is computed from the producing SOURCE (which hook/rule/
   declaration made the node), not from the existing ``confidence`` tag —
   the two axes are recorded independently (they happen to correlate today
   but neither is a function of the other's value).

Performance (honest characterization)
-------------------------------------
Building the graph is NOT free and is not "sub-second" on the platform: the
full ``validate() → build`` is ~3.6s, dominated by the assembly validation the
graph reads from (the graph assembly itself — node/edge construction — is the
small part). It is lazy and cached on the ``Detail`` (``evidence_graph``),
rebuilt only after the next ``validate()``, so the cost is paid once. Queries
are O(degree): :meth:`edges_from` / :meth:`edges_into` read the adjacency index
maintained in :meth:`add_edge`, so an Inspector fanning out over a part's edges
does not rescan all ~34k platform edges per call.

Open by construction (ONTOLOGY seam)
------------------------------------
Node and edge ``kind`` are open strings, never closed enums — the next task
(ONTOLOGY: Role/LoadClass/TransferCapability) ADDS node/edge kinds to this
graph without touching this module. The kinds this task populates are the
constants below; a reader can enumerate them but the graph does not reject
new ones.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field

from .coverage import PROVENANCE_ONLY_KINDS, family_of

#: The knowledge-source dimension (KNOWLEDGE STRATEGY). Open in spirit — a
#: fourth tier could be added — but these three are the mission's vocabulary.
SOURCE_TYPES: frozenset[str] = frozenset(
    {"authoritative", "verified_heuristic", "llm_hypothesis"}
)

#: Node kinds THIS task populates (open discriminator — ONTOLOGY adds more).
#: The ONTOLOGY additions (``role`` / ``transfer_claim`` / ``load_path``) are
#: listed in :data:`ONTOLOGY_NODE_KINDS` and folded in below — the graph never
#: rejects a new kind, so this is documentation, not a gate.
NODE_KINDS: frozenset[str] = frozenset(
    {"part", "declaration", "derived_fact", "finding", "family_verdict",
     "assumption"}
)

#: Edge kinds THIS task populates (open discriminator). Construction-graph
#: edges (``bears_on`` / ``fastened_by`` / ``transfers_load_to`` /
#: ``bonded_to`` / ``installed_before``) come straight from ``Connection``
#: edges and keep their kind strings verbatim.
EDGE_KINDS: frozenset[str] = frozenset(
    {"involves", "derived_from", "concerns", "generated", "proven_by",
     "assumes", "substantiates",
     "bears_on", "fastened_by", "transfers_load_to", "bonded_to",
     "installed_before"}
)

# -- ONTOLOGY (task ONTOLOGY) additive kinds ---------------------------------
# The construction ontology layer adds three node kinds and their edges to the
# graph WITHOUT touching any existing node/edge semantics: a ``role`` node per
# roled part (``has_role``), a ``transfer_claim`` node per TransferCapability
# claim (``declares_transfer`` from the connection declaration), and a
# ``load_path`` node per represented support→ground path (``on_load_path`` to
# each part on the chain, ``represents`` to the load_path finding it explains).
#: ONTOLOGY node kinds (folded into the documented enumeration additively).
ONTOLOGY_NODE_KINDS: frozenset[str] = frozenset(
    {"role", "transfer_claim", "load_path"})
#: ONTOLOGY edge kinds.
ONTOLOGY_EDGE_KINDS: frozenset[str] = frozenset(
    {"has_role", "declares_transfer", "on_load_path", "represents"})
NODE_KINDS = NODE_KINDS | ONTOLOGY_NODE_KINDS
EDGE_KINDS = EDGE_KINDS | ONTOLOGY_EDGE_KINDS

# -- FAB-4 (Construction Process Graph projection) additive kinds ------------
# The fabrication half of the Construction Process Graph is a GENERATIVE record
# (fab-design.md §4): per Placed part, a ``ProcessRecord`` of ``stock -> ordered
# steps -> installed geometry`` whose steps ARE the source of truth the cut list /
# BOM / geometry derive from. It cannot live inside the Evidence graph, whose
# invariant is that it generates nothing. So the Evidence graph gains a read-only
# PROJECTION of it — exactly as it already re-hosts Construction edges verbatim:
# one ``process_step`` node per authored fabrication step, and a ``produced_by``
# edge from the installed part to each step that made it, carrying the step's
# authored design intent as edge provenance so a changed op is walkable back to
# the declaration that generated it (the INCR affected-region seam,
# incr-design.md:78-81). Purchased-as-is parts (no ``fabrication_record`` or an
# empty step list) project NO step nodes: the ABSENCE of ``produced_by`` edges is
# the honest "bought, not made" fact. Additive by construction — projecting the
# record moves no existing node/edge, so every existing-kind count is unchanged.
#: FAB node kinds (folded into the documented enumeration additively).
FAB_NODE_KINDS: frozenset[str] = frozenset({"process_step"})
#: FAB edge kinds.
FAB_EDGE_KINDS: frozenset[str] = frozenset({"produced_by"})
NODE_KINDS = NODE_KINDS | FAB_NODE_KINDS
EDGE_KINDS = EDGE_KINDS | FAB_EDGE_KINDS

_CONSTRUCTION_EDGE_KINDS = frozenset(
    {"bears_on", "fastened_by", "transfers_load_to", "bonded_to",
     "installed_before"}
)


class EvidenceGraphError(Exception):
    """A completeness invariant of the Evidence Graph was violated — an orphan
    fact, an untraceable finding, or an ``llm_hypothesis`` wired to a check.
    Raised loudly (never a silent drop) — the graph's honesty is the whole
    point, so a graph that cannot be built HONESTLY must not be built."""


@dataclass
class Node:
    """One graph node. ``attrs`` holds only JSON-native values (str/int/float/
    bool/list/dict/None) so the graph round-trips through JSON with no custom
    codec and node equality is structural."""

    id: str
    kind: str
    label: str
    attrs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label,
                "attrs": self.attrs}

    @classmethod
    def from_dict(cls, d: dict) -> "Node":
        return cls(id=d["id"], kind=d["kind"], label=d["label"],
                   attrs=dict(d.get("attrs", {})))


@dataclass
class GraphEdge:
    src: str
    dst: str
    kind: str
    provenance: str = ""  # source declaration/connection label, when known

    def to_dict(self) -> dict:
        return {"src": self.src, "dst": self.dst, "kind": self.kind,
                "provenance": self.provenance}

    @classmethod
    def from_dict(cls, d: dict) -> "GraphEdge":
        return cls(src=d["src"], dst=d["dst"], kind=d["kind"],
                   provenance=d.get("provenance", ""))

    def _key(self):
        return (self.src, self.dst, self.kind, self.provenance)


class EvidenceGraph:
    """A queryable evidence graph. Build one with :meth:`build` (or
    :meth:`from_detail`); query it with the four Inspector methods; serialize
    with :meth:`to_dict` / :meth:`from_dict`."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[GraphEdge] = []
        self._edge_keys: set = set()
        # Adjacency index (rev-evidence advisory): src->edges and dst->edges,
        # maintained incrementally in add_edge so the Inspector query methods —
        # which fan out over edges_from/edges_into per part — are O(degree)
        # instead of O(E) list scans over all ~34k platform edges. Insertion
        # order within each bucket matches ``self.edges``, so results (and their
        # order) are byte-identical to the old full-scan filter.
        self._out: dict[str, list[GraphEdge]] = {}
        self._in: dict[str, list[GraphEdge]] = {}

    # -- construction primitives --------------------------------------------

    def add_node(self, kind: str, node_id: str, label: str, **attrs) -> Node:
        """Add (idempotently, by id) a node. Re-adding the same id returns the
        existing node — a part/assumption referenced from many places is one
        node, not many."""
        existing = self.nodes.get(node_id)
        if existing is not None:
            return existing
        node = Node(id=node_id, kind=kind, label=label, attrs=dict(attrs))
        self.nodes[node_id] = node
        return node

    def add_edge(self, src: str, dst: str, kind: str, provenance: str = "") -> None:
        """Add (deduplicated) a typed edge. Endpoints need not exist yet;
        :meth:`_verify` confirms every endpoint resolves once the graph is
        assembled."""
        edge = GraphEdge(src=src, dst=dst, kind=kind, provenance=provenance)
        key = edge._key()
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(edge)
        self._out.setdefault(src, []).append(edge)
        self._in.setdefault(dst, []).append(edge)

    # -- adjacency queries ---------------------------------------------------

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def nodes_of_kind(self, kind: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind == kind]

    def edges_of_kind(self, kind: str) -> list[GraphEdge]:
        return [e for e in self.edges if e.kind == kind]

    def edges_from(self, node_id: str) -> list[GraphEdge]:
        return list(self._out.get(node_id, ()))

    def edges_into(self, node_id: str) -> list[GraphEdge]:
        return list(self._in.get(node_id, ()))

    # -- serialization (req 5d: round-trips) --------------------------------

    def to_dict(self) -> dict:
        return {
            "nodes": [self.nodes[k].to_dict() for k in sorted(self.nodes)],
            "edges": [e.to_dict() for e in sorted(
                self.edges, key=lambda e: e._key())],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceGraph":
        g = cls()
        for nd in d["nodes"]:
            node = Node.from_dict(nd)
            g.nodes[node.id] = node
        for ed in d["edges"]:
            g.add_edge(ed["src"], ed["dst"], ed["kind"], ed.get("provenance", ""))
        return g

    def __eq__(self, other) -> bool:
        if not isinstance(other, EvidenceGraph):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def copy(self) -> "EvidenceGraph":
        return EvidenceGraph.from_dict(self.to_dict())

    def __repr__(self) -> str:
        return (f"<EvidenceGraph {len(self.nodes)} nodes / "
                f"{len(self.edges)} edges>")

    # ======================================================================
    # Building
    # ======================================================================

    @classmethod
    def from_detail(cls, detail) -> "EvidenceGraph":
        """Build the graph for a ``Detail``, validating it first if needed.
        Reads only lifecycle outputs the detail already holds."""
        if detail.report is None:
            detail.validate()
        return cls.build(
            assembly=detail.assembly,
            connections=detail.connections(),
            connection_checks=getattr(detail, "_connection_checks", None),
            report=detail.report,
            roles=_detail_roles(detail),  # ONTOLOGY: {} when detail declares none
        )

    @classmethod
    def build(cls, *, assembly, connections, connection_checks, report,
              roles=None) -> "EvidenceGraph":
        """Assemble the graph from already-computed lifecycle outputs:

        - ``assembly`` — the built :class:`DetailAssembly` (its ``parts`` become
          ``part`` nodes; part names resolve finding subjects back to ids).
        - ``connections`` — the declared :class:`Connection`\\ s (``declaration``
          nodes + ``involves`` edges to their parts).
        - ``connection_checks`` — the ``ConnectionChecks`` from
          ``compile_connections`` (``derived`` facts + construction ``edges``);
          ``None`` for a detail with no connections.
        - ``report`` — the finalized :class:`ValidationReport` (``finding``
          nodes + the coverage matrix's ``family_verdict`` nodes).
        """
        g = cls()
        name_to_id = _name_to_id(assembly)

        g._add_parts(assembly)
        g._add_process_steps(assembly)                                 # FAB-4
        conn_labels = g._add_connection_declarations(connections)
        g._add_derived_facts(connection_checks, conn_labels)          # req 5a
        g._add_construction_edges(connection_checks)
        g._add_findings(report, name_to_id, connection_checks, conn_labels)  # req 5b
        g._add_family_verdicts(report)                                 # req 5c

        # ONTOLOGY (task ONTOLOGY): additive role / transfer-claim / load-path
        # layer, gated on the author having DECLARED roles — declaring roles is
        # how a detail opts into the load-system view. A detail with no roles
        # (the platform tonight — SPATIAL owns it) gets NONE of these nodes, so
        # its graph stays byte-identical to master: the transfer claims that
        # would decorate it are type knowledge with no load path to feed yet.
        if roles:
            g._add_roles(roles)
            g._add_transfer_claims(connections)
            g._add_load_paths(roles, connections, connection_checks, name_to_id)

        g._verify()
        assert_llm_nonblocking(g)                                      # req 2
        return g

    # -- part nodes ----------------------------------------------------------

    def _add_parts(self, assembly) -> None:
        for p in assembly.parts:
            comp = p.component
            try:
                material = comp.material.key
            except Exception:
                material = getattr(comp, "material_key", "")
            self.add_node(
                "part", _part_nid(p.id), p.name,
                name=p.name,
                component_type=type(comp).__name__,
                material=material,
                descriptor=_safe(comp.describe),
                bom_label=_safe(comp.bom_label),
                assumptions=_safe(comp.assumptions),
                params=_json_params(comp),
                datums=sorted(comp.datums),
                source_type="authoritative",  # a placed part is authored fact
            )

    # -- fabrication projection (FAB-4) --------------------------------------

    def _add_process_steps(self, assembly) -> None:
        """Project each Placed part's ``ProcessRecord`` read-only into the graph:
        one ``process_step`` node per authored fabrication step and a
        ``produced_by`` edge from the installed part to each step that made it
        (``part -> its steps``). This is a PROJECTION of the generative
        Construction Process Graph, never a re-derivation — it reads only
        ``fabrication_record()`` (StockRef + ordered steps built from the part's
        already-authored params), builds no geometry, and adds no node/edge of any
        existing kind, so it moves no validation outcome and no existing count.

        Each step node carries its authored design intent (``provenance`` — the
        FEATURE / ``holes`` entry / implicit crosscut that generated it) and the
        stock it is cut from, so ``stock -> ordered steps -> installed geometry``
        is a walkable chain (CAT-3). The ``produced_by`` edge additionally carries
        that intent as its provenance: the seam INCR walks to pull a changed op
        into the affected region (incr-design.md:78-81) — sound here, not yet used.

        A purchased-as-is part projects NOTHING: a part with no
        ``fabrication_record`` (the base ``Component`` — a pier block, a bolt) or
        an empty step list is bought, not made, and the ABSENCE of ``process_step``
        nodes / ``produced_by`` edges on its part node IS that fact. Node ids key
        on the part id + the step's CONTENT identity (never a positional ordinal —
        the ordinal trap INCR rejects), so inserting a step leaves the others'
        node ids untouched; the ordered position is recorded as an ``order`` attr."""
        for p in assembly.parts:
            record = _fabrication_record_of(p.component)
            if record is None or not record.steps:
                continue  # purchased-as-is: no steps -> no nodes (honest absence)
            part_nid = _part_nid(p.id)
            stock = record.stock
            stock_attrs = {
                "stock_profile": stock.profile,
                "stock_form": stock.form,
                "stock_section": [float(stock.section[0]), float(stock.section[1])],
                "stock_material": stock.material_key,
            }
            for order, step in enumerate(record.steps):
                sid = _step_nid(p.id, step)
                self.add_node(
                    "process_step", sid, _step_label(step),
                    step_kind=step.kind,
                    order=order,
                    params=_json_step_params(step),
                    provenance=step.provenance,
                    part=part_nid,
                    source_type="authoritative",  # a verbatim restatement of the
                    # part's authored geometry params (length/ease/holes/trunk_cut)
                    **stock_attrs,
                )
                self.add_edge(part_nid, sid, "produced_by", step.provenance)

    # -- declaration nodes ---------------------------------------------------

    def _add_connection_declarations(self, connections) -> set:
        """One ``declaration`` node per declared Connection + ``involves``
        edges to every part and hardware item it names. Connection
        declarations are ``authoritative`` — a Connection is the author's
        direct statement of a joint's intent."""
        labels = set()
        for conn in connections or []:
            nid = _conn_decl_nid(conn.label)
            labels.add(conn.label)
            self.add_node(
                "declaration", nid, conn.label,
                subtype="connection",
                connection_type=type(conn.kind).__name__,
                source_type="authoritative",
                assumptions=list(conn.assumptions),
                n_parts=len(conn.parts),
                n_hardware=len(conn.hardware),
            )
            for part in conn.parts:
                self.add_edge(nid, _part_nid(part.id), "involves", conn.label)
            for hw in conn.hardware:
                self.add_edge(nid, _part_nid(hw.id), "involves", conn.label)
            for a in conn.assumptions:
                self._attach_assumption(nid, a)
        return labels

    def _imperative_decl(self, aspect: str, label: str) -> str:
        """An intrinsic/imperative validation declaration (interference sweep,
        through-hole probes, no-floaters, a dimension check). ``authoritative``:
        an intrinsic physical law or a directly authored check."""
        nid = _imp_decl_nid(aspect)
        self.add_node("declaration", nid, label, subtype="imperative",
                      aspect=aspect, source_type="authoritative")
        return nid

    # -- derived-fact nodes (req 5a: no orphans) -----------------------------

    def _add_derived_facts(self, connection_checks, conn_labels: set) -> None:
        facts = list(connection_checks.derived) if connection_checks else []
        # Determinism: the compiled ``derived`` list arrives in a process-
        # varying order (its upstream connection hooks iterate sets), so the
        # index-based ``fact:i`` ids — and every edge that references them —
        # would differ across processes, making the serialized graph non-
        # reproducible. Assign ids in a canonical content order instead. Facts
        # with an identical sort key are byte-identical nodes producing the
        # same (deduplicated) edges, so ties need no further tiebreak. This is
        # emit-time canonicalization only: it moves no validation outcome (the
        # report findings and their fingerprint are already order-stable).
        facts.sort(key=_fact_sort_key)
        for i, fact in enumerate(facts):
            nid = _fact_nid(i)
            self.add_node(
                "derived_fact", nid, fact.fact,
                fact=fact.fact,
                connection=fact.connection,
                rule=fact.rule,
                confidence=fact.confidence,
                source_type=fact.source_type,
                assumptions=list(fact.assumptions),
                subjects=list(fact.subjects),
            )
            # req 5a: every derived fact must reach an authored declaration.
            # A fact whose connection resolves to no declared Connection is an
            # ORPHAN — a hard diagnostic, never silently kept.
            if fact.connection not in conn_labels:
                raise EvidenceGraphError(
                    f"orphan derived fact {nid}: {fact.fact!r} names connection "
                    f"{fact.connection!r}, which is not a declared Connection "
                    f"({sorted(conn_labels)}). Every derived fact must trace to "
                    f"an authored declaration — see EvidenceGraph completeness "
                    f"invariants."
                )
            self.add_edge(nid, _conn_decl_nid(fact.connection), "derived_from",
                          fact.connection)
            for sid in fact.subjects:
                self.add_edge(nid, _part_nid(sid), "concerns", fact.connection)
            for a in fact.assumptions:
                self._attach_assumption(nid, a)

    def _fact_index(self) -> dict:
        """Index derived-fact nodes so a finding can be linked to the fact that
        generated it: by ``(connection, part_id)`` for hardware-presence facts
        and by the frozenset of subject ids for pairwise (bearing/overlap/bond)
        facts."""
        by_hardware: dict[tuple, str] = {}
        by_pair: dict[frozenset, str] = {}
        for n in self.nodes_of_kind("derived_fact"):
            subjects = n.attrs["subjects"]
            rule = n.attrs["rule"]
            if rule.endswith(".required_hardware") and len(subjects) == 1:
                by_hardware[(n.attrs["connection"], subjects[0])] = n.id
            elif rule.endswith(".bearing_pairs") and len(subjects) == 2:
                by_pair[frozenset(subjects)] = n.id
        return {"hardware": by_hardware, "pair": by_pair}

    # -- construction-graph edges (part -> part) -----------------------------

    def _add_construction_edges(self, connection_checks) -> None:
        for e in (connection_checks.edges if connection_checks else []):
            self.add_edge(_part_nid(e.a), _part_nid(e.b), e.kind, e.connection)

    # -- finding nodes (req 5b: every check traces to its generator) ---------

    def _add_findings(self, report, name_to_id, connection_checks, conn_labels) -> None:
        idx = self._fact_index()
        # override records let a connection_override finding trace to the
        # winning connection's declaration (none on rock_anchor/platform today).
        for i, f in enumerate(report.findings):
            nid = _finding_nid(i)
            self.add_node(
                "finding", nid, str(f),
                check=f.check, subject=f.subject, passed=bool(f.passed),
                detail=f.detail,
            )
            self._link_finding(nid, f, idx, name_to_id, conn_labels)

    def _link_finding(self, nid, f, idx, name_to_id, conn_labels) -> None:
        """Wire a finding to (a) the fact/declaration that GENERATED it
        [req 5b] and (b) the parts it CONCERNS. Every finding gets a generator
        so ``_verify`` finds no orphan check.

        The two installability AXIS kinds (task INSTALL v1) get NO
        ``concerns`` edges DELIBERATELY, exactly like a subject the parser
        cannot resolve: their subject names only the driven fastener, but the
        verdict depends on a geometric NEIGHBORHOOD — the members the shank
        crosses, the entry face, and every part near the swept tool corridor
        (including parts of other connections and, composed, other details).
        Attributing them to the fastener alone is the partial-attribution
        soundness hazard this method's all-or-nothing rule exists to prevent:
        a one-sided member move changes the measured exit/embedment/corridor
        while the fastener itself is untouched, so an affected region seeded
        at the member would miss the flip (caught live by
        test_affected_region on the platform's -Y bolts). Until the axis
        checks persist their true dependency sets, the honest sound home is
        the zero-attribution floor — always revisited on a non-empty edit.
        ``install_method`` (contract resolution, no geometry) keeps its
        attribution."""
        check = f.check
        if check in ("install_termination", "install_access"):
            parts = []
        else:
            parts = _subject_part_ids(f.subject, name_to_id)
        for pid in parts:
            self.add_edge(nid, _part_nid(pid), "concerns")

        if check == "bearing" and len(parts) == 2:
            fact = idx["pair"].get(frozenset(parts))
            if fact:
                self.add_edge(fact, nid, "generated")
                self.add_edge(fact, nid, "proven_by")
                return
        if check == "connection_hardware":
            label, _, part_name = f.subject.partition(": ")
            pid = name_to_id.get(part_name.strip())
            fact = idx["hardware"].get((label.strip(), pid)) if pid else None
            if fact:
                self.add_edge(fact, nid, "generated")
                self.add_edge(fact, nid, "proven_by")
                return
        if check == "connection_override":
            label = f.detail  # not reliably parseable; trace to intrinsic decl
            # fall through to imperative attribution below

        # Imperative / intrinsic checks (and any connection check whose fact
        # could not be resolved) trace to an imperative declaration node.
        decl = self._imperative_decl(*_IMPERATIVE_DECL.get(
            check, (f"check:{check}", f"{check} checks")))
        self.add_edge(decl, nid, "generated")

    # -- family-verdict nodes (req 5c) ---------------------------------------

    def _add_family_verdicts(self, report) -> None:
        rows = report.coverage_matrix()
        for row in rows:
            nid = _family_nid(row.family)
            self.add_node(
                "family_verdict", nid, f"{row.family}: {row.verdict}",
                family=row.family, verdict=row.verdict,
                checks_run=row.checks_run, findings=row.findings,
                failures=row.failures,
                ran_kinds=[list(rk) for rk in row.ran_kinds],
                note=row.note,
            )
        # substantiates: every non-provenance finding rolls into exactly the
        # family the coverage matrix attributes it to (same ``family_of`` +
        # same PROVENANCE_ONLY exclusion), so the two provenance views agree by
        # construction — proven by test_family_verdicts_match_coverage_matrix.
        for n in self.nodes_of_kind("finding"):
            check = n.attrs["check"]
            if check in PROVENANCE_ONLY_KINDS:
                continue
            self.add_edge(n.id, _family_nid(family_of(check)), "substantiates")

    # -- assumptions ---------------------------------------------------------

    def _attach_assumption(self, src_nid: str, text: str) -> None:
        aid = _assume_nid(text)
        self.add_node("assumption", aid, text, source_type="authoritative")
        self.add_edge(src_nid, aid, "assumes")

    # -- ONTOLOGY (task ONTOLOGY): roles, transfer claims, load paths ---------

    def _add_roles(self, roles: dict) -> None:
        """One ``role`` node per roled part + a ``has_role`` edge part→role. A
        role is the author's direct declaration of what a part IS in the load
        system — ``authoritative`` ground truth, not an inference."""
        for pid, role in sorted(roles.items()):
            rid = _role_nid(pid)
            self.add_node("role", rid, role, role=role, part=_part_nid(pid),
                          source_type="authoritative")
            self.add_edge(_part_nid(pid), rid, "has_role")

    def _add_transfer_claims(self, connections) -> None:
        """One ``transfer_claim`` node per TransferCapability claim on each
        declared connection's type + a ``declares_transfer`` edge from the
        connection declaration. These are the reusable knowledge the load-path
        proof stands on; each carries its own confidence / source_type /
        reference provenance verbatim."""
        for conn in connections or []:
            decl = _conn_decl_nid(conn.label)
            for claim in getattr(type(conn.kind), "transfer_claims", ()):
                cid = _claim_nid(conn.label, claim.load_class)
                self.add_node(
                    "transfer_claim", cid, claim.describe(),
                    load_class=claim.load_class, transfers=bool(claim.transfers),
                    confidence=claim.confidence, source_type=claim.source_type,
                    reference=claim.reference, connection=conn.label)
                self.add_edge(decl, cid, "declares_transfer", conn.label)

    def _add_load_paths(self, roles: dict, connections, connection_checks,
                        name_to_id) -> None:
        """One ``load_path`` node per support→ground result (for the provable
        ``downward_load`` class), computed from the SAME loadpath helpers the
        report uses (so the graph can't drift from the finding). Links each part
        on the chain (``on_load_path``) and the load_path finding the node
        explains (``represents``), so ``how_verified`` / ``what_depends_on`` on
        any part in the chain surface the whole represented path."""
        if not roles:
            return
        from .loadpath import check_load_path, transfers_by_connection

        load_class = "downward_load"
        edges = connection_checks.edges if connection_checks else []
        transfers = transfers_by_connection(connections or [], load_class)
        name_of = {p: nm for nm, p in name_to_id.items() if p}
        result = check_load_path(load_class=load_class, roles=roles,
                                 edges=edges, transfers=transfers,
                                 name_of=name_of)
        # index the load_path findings by their support-name subject so a node
        # can link the finding it explains
        lp_findings = {n.attrs["subject"]: n.id
                       for n in self.nodes_of_kind("finding")
                       if n.attrs["check"] == "load_path"}
        for lp in result.paths:
            nid = _loadpath_nid(load_class, lp.support)
            self.add_node(
                "load_path", nid,
                f"{load_class}: {name_of.get(lp.support, lp.support)}",
                load_class=load_class, represented=lp.represented,
                support=lp.support, reached_ground=lp.reached_ground,
                chain=list(lp.chain),
                chain_names=[name_of.get(p, p) for p in lp.chain],
                note=lp.note, source_type="verified_heuristic")
            for pid in lp.chain:
                self.add_edge(nid, _part_nid(pid), "on_load_path")
            for subject, fid in lp_findings.items():
                # match the finding whose support this path is about
                if name_of.get(lp.support, lp.support) in subject:
                    self.add_edge(nid, fid, "represents")

    def load_paths_through(self, part_id: str) -> list[dict]:
        """The represented/broken load paths a part participates in (ONTOLOGY) —
        a small query the Inspector-facing methods fold in additively."""
        pid = self._resolve_part(part_id)
        out = []
        for e in self.edges_into(pid):
            if e.kind != "on_load_path":
                continue
            lp = self.nodes[e.src]
            rg = lp.attrs["reached_ground"]
            rg_name = (self.nodes[_part_nid(rg)].attrs.get("name", rg)
                       if rg and _part_nid(rg) in self.nodes else rg)
            out.append({
                "load_class": lp.attrs["load_class"],
                "represented": lp.attrs["represented"],
                "chain": lp.attrs["chain_names"],
                "reached_ground": rg_name,
                "note": lp.attrs["note"],
            })
        return out

    # -- structural verification ---------------------------------------------

    def _verify(self) -> None:
        """Every edge endpoint resolves to a real node; every finding has a
        generator (req 5b); every fact has a declaration (req 5a, already
        enforced at add time — re-checked here as a belt-and-braces net)."""
        for e in self.edges:
            if e.src not in self.nodes or e.dst not in self.nodes:
                raise EvidenceGraphError(
                    f"dangling edge {e.kind}: {e.src} -> {e.dst} "
                    f"(missing {'src' if e.src not in self.nodes else 'dst'})")
        for f in self.nodes_of_kind("finding"):
            if not any(e.kind == "generated" for e in self.edges_into(f.id)):
                raise EvidenceGraphError(
                    f"orphan finding {f.id} ({f.label!r}): no generator edge — "
                    f"every generated check must trace to the fact or "
                    f"declaration that produced it.")
        for fa in self.nodes_of_kind("derived_fact"):
            if not any(e.kind == "derived_from" for e in self.edges_from(fa.id)):
                raise EvidenceGraphError(
                    f"orphan derived fact {fa.id}: no declaration.")

    # ======================================================================
    # Inspector query API (req 4) — plain JSON-serializable returns
    # ======================================================================

    def _resolve_part(self, ref: str) -> str:
        """Resolve a part reference to its ``part:`` node id. Accepts a ``part:``
        node id, a bare ``Placed.id``, or a part's unique display NAME — the
        Inspector clicks a GLB node whose name is the ``Placed.name`` (CLAUDE.md
        viewer contract), so name resolution is the ergonomic default. An
        ambiguous name raises rather than guessing (P1)."""
        if ref in self.nodes and self.nodes[ref].kind == "part":
            return ref
        nid = _part_nid(ref)
        if nid in self.nodes:
            return nid
        matches = [n.id for n in self.nodes_of_kind("part")
                   if n.attrs["name"] == ref]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise KeyError(f"no part {ref!r} in evidence graph")
        raise KeyError(f"part name {ref!r} is ambiguous ({matches}); "
                       f"use a Placed.id")

    def what_is(self, part_id: str) -> dict:
        """Descriptor for a part: type / material / dimensions / params /
        assumptions / datums. Accepts a ``Placed.id``, a ``part:`` node id, or
        a part's unique display name."""
        node = self.nodes[self._resolve_part(part_id)]
        a = node.attrs
        return {
            "id": node.id, "part_id": node.id.removeprefix("part:"),
            "kind": "part", "name": a["name"],
            "component_type": a["component_type"], "material": a["material"],
            "descriptor": a["descriptor"], "bom_label": a["bom_label"],
            "params": a["params"], "assumptions": a["assumptions"],
            "datums": a["datums"], "source_type": a["source_type"],
        }

    def why_here(self, part_id: str) -> dict:
        """Authored-vs-derived provenance for a part: which declarations name
        it (authored intent) and which facts were derived about it (with the
        rule, confidence, source_type and assumptions behind each), plus a
        readable declaration→fact chain."""
        pid = self._resolve_part(part_id)
        authored = []
        for e in self.edges_into(pid):
            if e.kind != "involves":
                continue
            d = self.nodes[e.src]
            authored.append({
                "declaration": d.id, "label": d.label,
                "subtype": d.attrs.get("subtype"),
                "connection_type": d.attrs.get("connection_type"),
                "source_type": d.attrs.get("source_type"),
                "assumptions": d.attrs.get("assumptions", []),
            })
        derived, chain = [], []
        for e in self.edges_into(pid):
            if e.kind != "concerns":
                continue
            src = self.nodes[e.src]
            if src.kind != "derived_fact":
                continue
            decl = next((self.nodes[de.dst].label
                         for de in self.edges_from(src.id)
                         if de.kind == "derived_from"), None)
            derived.append({
                "fact": src.attrs["fact"], "rule": src.attrs["rule"],
                "connection": src.attrs["connection"],
                "confidence": src.attrs["confidence"],
                "source_type": src.attrs["source_type"],
                "assumptions": src.attrs["assumptions"],
                "derived_from": decl,
            })
            chain.append(f"{decl}  --[{src.attrs['rule']}]-->  {src.attrs['fact']}")
        return {"part": pid, "name": self.nodes[pid].attrs["name"],
                "authored": authored, "derived": derived, "chain": chain}

    def how_verified(self, target: str) -> dict:
        """How a part or a finding is verified: the findings covering it, the
        family verdicts they roll into, and a readable evidence chain — never a
        bare 'PASS'. Accepts a ``Placed.id`` / ``part:`` id, or a
        ``finding:`` id."""
        if str(target).startswith("finding:") and target in self.nodes:
            finding_ids, tkind = [target], "finding"
        else:
            pid = self._resolve_part(target)
            finding_ids = [e.src for e in self.edges_into(pid)
                           if e.kind == "concerns"
                           and self.nodes[e.src].kind == "finding"]
            tkind = "part"
        findings, families, chain = [], {}, []
        for fid in finding_ids:
            fn = self.nodes[fid]
            gen = [self.nodes[e.src] for e in self.edges_into(fid)
                   if e.kind == "generated"]
            findings.append({
                "finding": fid, "check": fn.attrs["check"],
                "subject": fn.attrs["subject"],
                "passed": fn.attrs["passed"], "detail": fn.attrs["detail"],
                "generated_by": [gnode_summary(g) for g in gen],
                "explanation": _explain_finding(fn, gen),
            })
            for e in self.edges_from(fid):
                if e.kind != "substantiates":
                    continue
                fam = self.nodes[e.dst]
                families.setdefault(fam.id, {
                    "family": fam.attrs["family"], "verdict": fam.attrs["verdict"],
                    "checks_run": fam.attrs["checks_run"],
                    "failures": fam.attrs["failures"], "note": fam.attrs["note"],
                })
            for g in gen:
                chain.append(_explain_finding(fn, [g]))
        # ONTOLOGY (additive): the load paths this target participates in, so a
        # verdict on the rod/leg surfaces the whole REPRESENTED chain, not just
        # its own findings. Empty for a part on no declared load path.
        load_paths = (self.load_paths_through(target)
                      if tkind == "part" else [])
        return {"target": target, "kind": tkind,
                "findings": findings,
                "family_verdicts": list(families.values()),
                "evidence_chain": chain,
                "load_paths": load_paths,
                "standing_note": _STANDING_NOTE()}

    def what_depends_on(self, part_id: str) -> dict:
        """Change-impact for a part: its construction-graph neighbours (via
        ``bears_on`` / ``fastened_by`` / ``transfers_load_to`` / ``bonded_to``
        / ``installed_before``) and the facts + checks that would be invalidated
        (need re-derivation / re-checking) if the part changed."""
        pid = self._resolve_part(part_id)
        neighbors = []
        for e in self.edges_from(pid):
            if e.kind in _CONSTRUCTION_EDGE_KINDS:
                neighbors.append({"edge": e.kind, "direction": "out",
                                  "other": e.dst,
                                  "other_name": self.nodes[e.dst].attrs.get("name"),
                                  "provenance": e.provenance})
        for e in self.edges_into(pid):
            if e.kind in _CONSTRUCTION_EDGE_KINDS:
                neighbors.append({"edge": e.kind, "direction": "in",
                                  "other": e.src,
                                  "other_name": self.nodes[e.src].attrs.get("name"),
                                  "provenance": e.provenance})
        invalidated = []
        for e in self.edges_into(pid):
            if e.kind != "concerns":
                continue
            src = self.nodes[e.src]
            if src.kind == "derived_fact":
                invalidated.append({"type": "derived_fact", "id": src.id,
                                    "rule": src.attrs["rule"],
                                    "summary": src.attrs["fact"]})
            elif src.kind == "finding":
                invalidated.append({"type": "finding", "id": src.id,
                                    "check": src.attrs["check"],
                                    "summary": src.attrs["subject"]})
        return {"part": pid, "name": self.nodes[pid].attrs["name"],
                "construction_neighbors": neighbors,
                "invalidated_if_changed": invalidated,
                # ONTOLOGY (additive): change-impact along represented load paths
                "load_paths": self.load_paths_through(pid)}

    def how_made(self, part_id: str) -> dict:
        """How a fabricated part is made from what you buy (FAB-4 projection): the
        derived, walkable ``stock -> ordered steps -> installed geometry`` chain,
        each step traceable back to the design intent that generated it (its
        ``provenance`` — the FEATURE / ``holes`` entry / implicit crosscut). The
        installed geometry is DERIVED (``fold(stock, steps)``), not a stored solid.

        A purchased-as-is part returns ``purchased=True`` with no steps and no
        stock — the honest 'bought, not made' story, legible as the ABSENCE of any
        ``process_step`` the graph projects for it."""
        pid = self._resolve_part(part_id)
        step_nodes = sorted(
            (self.nodes[e.dst] for e in self.edges_from(pid)
             if e.kind == "produced_by"),
            key=lambda n: n.attrs["order"])
        stock = None
        steps = []
        for n in step_nodes:
            a = n.attrs
            if stock is None:
                stock = {"profile": a["stock_profile"], "form": a["stock_form"],
                         "section": a["stock_section"],
                         "material": a["stock_material"]}
            steps.append({
                "step": n.id, "kind": a["step_kind"], "order": a["order"],
                "params": a["params"], "intent": a["provenance"],
                "source_type": a["source_type"],
            })
        return {"part": pid, "name": self.nodes[pid].attrs["name"],
                "purchased": not steps, "stock": stock, "steps": steps,
                "installed": ("derived: fold(stock, steps)" if steps else None)}


# -- the llm-hypothesis non-blocking guarantee (req 2) -----------------------


def assert_llm_nonblocking(graph: EvidenceGraph) -> None:
    """Enforce the KNOWLEDGE-STRATEGY guarantee that an ``llm_hypothesis`` node
    is NON-BUILD-BLOCKING by construction: it may ANNOTATE, but may never
    ``generated`` or ``proven_by`` a check (a generated check can fail, and a
    candidate LLM rule must never be able to fail a build). Raises
    :class:`EvidenceGraphError` on any violation. Run on every built graph."""
    for n in graph.nodes.values():
        if n.attrs.get("source_type") != "llm_hypothesis":
            continue
        for e in graph.edges_from(n.id):
            if e.kind in ("generated", "proven_by") and \
                    graph.nodes[e.dst].kind == "finding":
                raise EvidenceGraphError(
                    f"llm_hypothesis node {n.id} {n.label!r} {e.kind} a check "
                    f"({e.dst}): an llm_hypothesis may only annotate, never "
                    f"generate or prove a check — it must be non-build-blocking "
                    f"by construction (KNOWLEDGE STRATEGY). Promote it to "
                    f"verified_heuristic after review before it may gate a "
                    f"build.")


# -- finding-kind -> imperative declaration (aspect, label) ------------------

_IMPERATIVE_DECL: dict[str, tuple[str, str]] = {
    "interference": ("interference", "pairwise interference sweep (intrinsic)"),
    "through_hole": ("through_holes", "fastener through-hole probes"),
    "floating": ("ground", "floating-part connectivity (no-floaters)"),
    "dimension": ("dimension", "design-intent dimension checks"),
    "contact": ("contact", "flush-contact checks"),
    "parameters": ("parameters", "component parameter self-consistency"),
    "connection_override": ("override", "connection dedup override records"),
    # ONTOLOGY (task ONTOLOGY): the load-path check is a lifecycle/graph check
    # (roles + Construction-Graph reachability), not a geometric sweep — its
    # finding traces to this intrinsic declaration, and the load_path NODE
    # additionally ``represents`` it (a richer, non-generating edge).
    "load_path": ("load_path", "load-path REPRESENTATION reachability"),
    # INSTALL (task INSTALL): the three installability kinds — a fastener's
    # installation contract (REPRESENTED rung), its geometric termination
    # (axis 1) and static tool access (axis 2). Mapped ahead of their
    # emitters, like the coverage-family entry.
    "install_method": ("install_method",
                       "fastener installation-method REPRESENTATION"),
    "install_termination": ("install_termination",
                            "fastener geometric-termination checks (axis 1)"),
    "install_access": ("install_access",
                       "fastener static tool-access checks (axis 2)"),
}


# -- helpers -----------------------------------------------------------------


def gnode_summary(n: Node) -> dict:
    if n.kind == "derived_fact":
        return {"kind": "derived_fact", "id": n.id, "rule": n.attrs["rule"],
                "source_type": n.attrs["source_type"],
                "confidence": n.attrs["confidence"], "fact": n.attrs["fact"]}
    return {"kind": n.kind, "id": n.id, "label": n.label,
            "source_type": n.attrs.get("source_type")}


def _explain_finding(fn: Node, generators: list[Node]) -> str:
    verdict = "PASS" if fn.attrs["passed"] else "FAIL"
    detail = f" — {fn.attrs['detail']}" if fn.attrs["detail"] else ""
    if generators:
        g = generators[0]
        if g.kind == "derived_fact":
            why = (f"generated from the {g.attrs['source_type']} fact "
                   f"{g.attrs['fact']!r} (rule {g.attrs['rule']})")
        else:
            why = f"an intrinsic {g.label}"
        return (f"{verdict} {fn.attrs['check']}: {fn.attrs['subject']}{detail} "
                f"— {why}")
    return f"{verdict} {fn.attrs['check']}: {fn.attrs['subject']}{detail}"


def _STANDING_NOTE() -> str:
    from .coverage import STANDING_NOTE
    return STANDING_NOTE


def _name_to_id(assembly) -> dict:
    """``name -> Placed.id``, but only for names that are UNAMBIGUOUS in the
    assembly. A duplicated display name maps to ``None`` so a finding subject
    that mentions it yields no (possibly wrong) ``concerns`` edge — silence
    over a guess (P1)."""
    counts = Counter(p.name for p in assembly.parts)
    out = {}
    for p in assembly.parts:
        out[p.name] = p.id if counts[p.name] == 1 else None
    return out


#: A trailing qualifier clause on a structured subject that is NOT itself a part
#: name — ``symmetric_about`` appends ``about <plane>`` to the pair (``beam +Y <->
#: beam -Y about XZ``). Stripped per operand so BOTH parts of the pair resolve, not
#: only the first (this is the mirror of ``views._SUBJECT_CLAUSE``; the two subject
#: parsers must attribute the same parts — the ``faces …`` clause is deliberately NOT
#: stripped here: its target IS a part the ``A faces B`` grammar hides, so a
#: faces_* finding names two parts the ``<->`` split cannot recover and stays
#: honestly in the zero-attribution floor rather than being half-attributed).
_SUBJECT_ABOUT_CLAUSE = re.compile(r" about \S+$")


def _subject_name_tokens(subject: str) -> list[str]:
    """The raw candidate part-name tokens in a structured finding subject — the
    strings the graph TRIES to resolve to parts, before resolution. Handles the two
    shapes the graph attributes (``A <-> B`` and ``label: name``) and strips a
    trailing ``about <plane>`` qualifier from each operand. A subject in neither shape
    yields no tokens (it names no part the graph can attribute — it falls in the
    zero-attribution floor). Exposed so a guard can assert every token a finding
    yields actually resolves, so no subject is silently HALF-attributed (an operand
    dropped) — the soundness hazard for the affected-region computation."""
    if " <-> " in subject:
        raw = subject.split(" <-> ")
    elif ": " in subject:
        raw = [subject.partition(": ")[2]]
    else:
        return []
    return [_SUBJECT_ABOUT_CLAUSE.sub("", t).strip() for t in raw]


def _subject_part_ids(subject: str, name_to_id: dict) -> list[str]:
    """Resolution of a finding subject to the ``Placed.id``\\ s it names, from the two
    structured subject shapes the graph attributes (``A <-> B``, optionally with an
    ``about <plane>`` qualifier; ``label: name``).

    **All-or-nothing attribution.** A subject is attributed to its parts only when
    EVERY candidate operand token resolves. If any token does not resolve, the subject
    is not one this parser fully understands (e.g. the ``connection_hardware`` shape
    ``A <-> B (type): hardware``, whose middle operand carries the joint type and
    hardware name), so it gets NO ``concerns`` edges and falls in the zero-attribution
    floor — always revisited — rather than being HALF-attributed to only the operand
    that happened to parse. A partial ``concerns`` set is the soundness hazard for the
    affected-region computation: a change to the dropped operand would escape a region
    seeded elsewhere. Whole attribution or none; never a misleading partial."""
    tokens = _subject_name_tokens(subject)
    ids = [name_to_id.get(name) for name in tokens]
    if any(pid is None for pid in ids):
        return []
    return ids


def _json_params(comp) -> dict:
    out = {}
    for k, v in _safe_params(comp).items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = [x for x in v if isinstance(x, (str, int, float, bool))]
        else:
            out[k] = str(v)
    return out


def _safe_params(comp) -> dict:
    try:
        return comp.params()
    except Exception:
        return {}


def _safe(fn) -> str:
    try:
        return fn()
    except Exception:
        return ""


def _part_nid(pid: str) -> str:
    return pid if pid.startswith("part:") else f"part:{pid}"


def _conn_decl_nid(label: str) -> str:
    return f"decl:conn:{label}"


def _imp_decl_nid(aspect: str) -> str:
    return f"decl:imp:{aspect}"


def _fact_nid(i) -> str:
    return f"fact:{i}"


def _fact_sort_key(fact) -> tuple:
    """A total-order key over a ``DerivedFact``'s full node payload, so the
    ``fact:i`` ids are assigned canonically regardless of the compiled list's
    (process-varying) order. Equal keys ⇒ byte-identical nodes+edges, so no
    tiebreak is needed for genuine duplicates."""
    return (fact.fact, fact.connection, fact.rule, fact.confidence,
            fact.source_type, tuple(fact.assumptions), tuple(fact.subjects))


def _finding_nid(i) -> str:
    return i if str(i).startswith("finding:") else f"finding:{i}"


def _family_nid(family: str) -> str:
    return f"family:{family}"


def _assume_nid(text: str) -> str:
    return "assume:" + hashlib.sha1(text.encode()).hexdigest()[:12]


# -- FAB-4 (fabrication projection) helpers ----------------------------------


def _fabrication_record_of(component):
    """The component's ``ProcessRecord`` (``stock -> ordered steps ->
    installed geometry``), or ``None`` for a part with no fabrication record —
    a purchased-as-is component (the base ``Component``: a pier block, a bolt).
    Read-only + best-effort: never raises here, so the graph cannot fail to
    build over a fabrication surface the lifecycle already produced."""
    fn = getattr(component, "fabrication_record", None)
    if not callable(fn):
        return None
    try:
        return fn()
    except Exception:
        return None


def _id_token(v) -> str:
    """A stable string for one component of a step's content ``identity`` (a kind
    tag, or a ``drill``'s authored ``(x, z)`` / a ``notch``'s feature). ``repr``
    on a float is round-trip stable, so the node id is deterministic."""
    return repr(v) if isinstance(v, float) else str(v)


def _step_nid(part_id: str, step) -> str:
    """A ``process_step`` node id keyed on the part id + the step's CONTENT
    identity (``ProcessStep.identity``) — never a positional ordinal, so
    inserting a step leaves the other steps' node ids untouched (the ordinal trap
    INCR rejects, incr-design.md:51-59). Identity is unique within a record
    (collisions are rejected at ``ProcessRecord`` construction), so the part-id
    prefix makes it globally unique."""
    ident = ":".join(_id_token(t) for t in step.identity)
    return f"step:{part_id}:{ident}"


def _step_label(step) -> str:
    """A readable one-line label for a fabrication step: kind + its params."""
    params = ", ".join(f"{k}={v}" for k, v in step.params)
    return f"{step.kind}: {params}" if params else step.kind


def _json_step_params(step) -> dict:
    """The step's params as a JSON-native dict (floats/strings already; any
    non-native value is stringified, matching :func:`_json_params`)."""
    out = {}
    for k, v in step.params:
        out[k] = v if isinstance(v, (str, int, float, bool)) or v is None else str(v)
    return out


# -- ONTOLOGY (task ONTOLOGY) helpers ----------------------------------------


def _role_nid(pid: str) -> str:
    return f"role:{pid}"


def _claim_nid(label: str, load_class: str) -> str:
    return f"claim:{label}:{load_class}"


def _loadpath_nid(load_class: str, support: str) -> str:
    return f"loadpath:{load_class}:{support}"


def _detail_roles(detail) -> dict:
    """``{Placed.id: role}`` from a detail's ``roles()`` declaration surface (a
    ``{display_name: role}`` mapping on both the imperative and spec paths), or
    ``{}`` when the detail declares none. Read-only + best-effort: a name that
    resolves to no part is skipped, never a hard error here (the load-path CHECK
    already validates roles loudly; the graph must not fail to build over a
    declaration the report already reported on)."""
    fn = getattr(detail, "roles", None)
    if not callable(fn):
        return {}
    out = {}
    for name, role in (fn() or {}).items():
        try:
            out[detail.assembly._resolve(name).id] = role
        except Exception:
            continue
    return out
