"""The Construction Process Graph's ASSEMBLY slice (task CPGCORE,
``stepdoc-cpg-design.md`` §2–§3, v1-core scope per owner amendment 1).

The Construction Graph says what exists; this graph says in what order it can
be built. It is a DAG of install EVENTS — one node kind, open-tagged like
every other kind in this codebase (``cure``/``join`` are later increments and
deliberately NOT built here; the tag headroom is the point):

- ``place(part)`` — the part arrives at its final relative pose. Identity:
  the part's id (repeat instances already carry their index).
- ``drive(connection, role_group)`` — the group's fasteners are driven,
  ATOMIC: same-group siblings are co-driven in free order, exactly the
  axis-2 stack-exclusion semantics. A connection with no fastener role
  groups (a glued bond, a connector like a standoff post base) still gets
  ONE drive event (``group=""``) — the glue-up / set-the-connector act is a
  real installation act even though no fastener is driven (``bond`` = drive
  with an empty hardware set).

Identity is CONTENT, never an ordinal (the INCR/FAB-Q3 lesson): regrouping
presentation can never move a verdict, because verdicts bind to events and
the partial order, not to any linearization (§4.1).

Edge families in v1-core, every edge provenance-stamped with its family AND
the source claim it came from:

1. ``technique_default`` — each ConnectionType's ``installed_before`` part
   edges LIFTED to event edges. Two lift rules, both pinned by test with the
   adversarial review's live constructions:

   - **Same-event drop (review F-5).** An edge whose two endpoints map to
     the SAME event is order-vacuous and DROPS — it expresses intra-event
     assembly order the event's atomicity already owns. The platform's 40
     intra-bolt-stack ``bolt → washer → washer → nut`` edges all collapse
     into their single ``drive(conn, bolt_stack)`` event; without the drop
     every bolted detail would fail at load, day one, on self-loop "cycles".
   - **Multi-stack mapping (review R-2).** Hardware riding MULTIPLE role
     groups' stacks maps to the drive event its OWN type edges place it
     at-or-before. The FaceMountHanger's hanger piece rides BOTH screw
     groups' stacks; its ``hanger → header screws`` edge names the
     HEADER-side drive, so it maps there and the collapse is consistent.
     The alternative (hung-side) mapping is the pinned counterexample: it
     lifts ``hanger → hung`` to ``drive(hung-side) → place(hung)``, which
     cycles with ``place(hung) → drive(hung-side)`` — every hanger-bearing
     detail would fail at load. Ambiguity (zero or 2+ at-or-before groups)
     is a loud teaching error, never a guess.
   - **Mid-event member interleave (third rule, found live in this task on
     the shipped ThreadedRodEpoxyAnchor — same defect class as the two
     above).** A member placed MID-hardware-chain (the anchor bracket seats
     after the rod+leveling stack, before the upper clamping stack) lifts
     to BOTH directions between its place event and the ONE drive event —
     a 2-cycle the part-level chain never had. Both directions express the
     member's arrival DURING the atomic drive event, so both drop as
     intra-event order; structural necessity supplies the surviving,
     conservative direction (the member is PRESENT at the drive event —
     never quietly "later").

2. ``structural_necessity`` — derived: a member must exist before its own
   connection's fasteners are driven (``place(member) → drive(conn, g)``),
   EXCEPT where a TECHNIQUE path already orders the opposite way (the
   hanger hangs its header screws before the hung member arrives —
   connection.py's ``header screws installed_before hung`` edge). Only
   type-declared technique knowledge may claim the exception; an AUTHORED
   stage claiming the opposite direction leaves both edges in the graph
   and is a loud cycle error naming both claims (design §6 rule 1 — a
   declared order contradicting structural necessity must be tested, never
   silenced; review-cpgcore F-1). A residual contradiction is a loud
   cycle. Every derived edge points INTO
   a drive event — no derived family ever places an occupant AFTER a
   fastener, which is why §4.3's rung ceiling holds: v1 claims
   SEQUENCE-PROVEN for no clear, anywhere.

3. ``authored_sequence`` — declared: a spec's ``sequence:`` stages (already
   loaded/validated by SEQSCHEMA and RESOLVED to compiled labels/ids —
   :class:`ResolvedStage`). A stage orders its connections' drive events
   and its parts' place events; stage k's events precede stage k+1's,
   WITHIN the stage's chain only (a site fragment's stages never order
   another fragment's — cross-fragment order does not exist in v1, §3.2).

Vocabulary discipline (owner amendment 5, BINDING): a "stage" is the
AUTHORED grouping (:class:`ResolvedStage` here, ``AuthoredStage`` in the
spec schema); a "step" is the READER presentation unit
(:class:`ReaderStep`). Distinct types; never interchangeable.

The merged cycle check is the whole-graph generalization of
``connection.py``'s part-level ``_check_install_order`` (which stays, for
intra-event hardware-chain contradictions the event collapse would mask):
one Kahn pass over every family combined, and the teaching error names the
conflicting edges AND their provenance families, so a cycle between an
authored stage and a technique edge tells the author which claim to fix.
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

#: The three v1-core edge families (open set — ``staging`` is a later
#: increment and deliberately not built).
FAMILY_TECHNIQUE = "technique_default"
FAMILY_NECESSITY = "structural_necessity"
FAMILY_AUTHORED = "authored_sequence"
FAMILY_STAGING = "staging"

#: Families whose facts are DECLARED claims (authored or type-declared
#: technique knowledge) vs DERIVED. Structural necessity is the one derived
#: family in v1-core; the split is what the epistemic-contract table and the
#: §4.3 rung wording print.
DECLARED_FAMILIES = frozenset({
    FAMILY_TECHNIQUE, FAMILY_AUTHORED, FAMILY_STAGING})


@dataclass(frozen=True)
class Event:
    """One install event, content-keyed (§2): ``place`` keyed by the part's
    id, ``drive`` keyed by ``(connection label, role-group key)``. ``kind``
    is an open tag — ``cure``/``join`` are later increments."""

    kind: str          # "place" | "drive" | "join"
    subject: str       # place: part id; drive: connection label; join: unit
    group: str = ""    # drive only: the role-group key ("" = the single
                       # install unit of a group-less connection)


@dataclass(frozen=True)
class EventEdge:
    """One order fact between two events, provenance-stamped: ``family`` is
    the edge family (above), ``source`` the human-readable claim it came
    from (the connection edge, the derivation rule, or the authored stage
    pair WITH its why)."""

    a: Event
    b: Event
    family: str
    source: str


@dataclass(frozen=True)
class PresenceFact:
    """A frame-presence proof that is not itself a graph-order edge.

    Bench-frame exclusion and explicit in-situ context are presence rules of
    the authored staging declaration, not invented cross-unit precedence.
    They still carry the same family/source interface as :class:`EventEdge`
    so verdicts can print one provenance vocabulary.
    """

    family: str
    source: str


@dataclass(frozen=True)
class PresenceDecision:
    """Presence of one occupant at one drive event."""

    state: str  # present | absent | unordered | coincident
    event: Event | None
    facts: tuple = ()
    declared_trust: bool = False


@dataclass(frozen=True)
class ResolvedStage:
    """One authored ``sequence:`` stage, RESOLVED to the compiled surface:
    ``connections`` are compiled connection labels (repeat templates
    expanded to their instances), ``parts`` are built ``Placed.id``\\ s.
    ``chain`` scopes the total order: stages order only against other
    stages of the SAME chain (one chain per authored document; a site
    replays each fragment's stages under the fragment's own chain, so no
    cross-fragment order is ever invented). Vocabulary (amendment 5): this
    is a STAGE — an authored grouping — never a reader step."""

    name: str
    why: str
    chain: str = ""
    connections: tuple = ()
    parts: tuple = ()


@dataclass(frozen=True)
class ResolvedUnit:
    """One authored bench unit resolved to built ``Placed.id`` values."""

    name: str
    why: str
    parts: tuple = ()


@dataclass(frozen=True)
class ResolvedStaging:
    """The one compiled staging surface consumed by graph/check/readers.

    ``mode`` is ``subassemblies``, ``bench_then_set``, or ``in_situ``.
    Whole-detail sugar is already normalized into ``units``; context parts
    are built ids for every authored ``role: existing`` body.
    """

    mode: str
    why: str = ""
    units: tuple[ResolvedUnit, ...] = ()
    context_parts: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ReaderStep:
    """One READER presentation unit (§5.1) — a deterministic grouping of
    events in the canonical linearization; NEVER an authored stage
    (amendment 5). Regrouping presentation can never change a verdict:
    checks bind to events and the partial order, the document binds to
    reader steps. ``stage`` carries the authored stage this step presents
    (with its why), or ``None`` for a per-connection install unit."""

    title: str
    stage: ResolvedStage | None
    connections: tuple = ()   # labels driven in this step, declaration order
    parts_placed: tuple = ()  # part ids whose place events fold into it


class EventOrderCycleError(ValueError):
    """The merged event graph contradicts itself — an unrepresentable
    construction sequence (P1: a hard diagnostic, never a guess). The
    message names the conflicting edges and their provenance families."""


class EventGraph:
    """The built assembly-slice CPG: events, provenance-stamped edges, the
    part → governing-event map, and memoized reachability. Deterministic by
    construction (connection declaration order, then group order, then part
    order everywhere)."""

    def __init__(self, events, edges, event_of, part_names, conn_labels,
                 drives_of, members_of, stages, staging=None, frame_of=None,
                 unit_of=None, join_of=None):
        self.events: tuple[Event, ...] = tuple(events)
        self.edges: tuple[EventEdge, ...] = tuple(edges)
        #: part id -> its governing event (fastener/stack hardware -> its
        #: drive event; every other part -> its place event).
        self.event_of: dict[str, Event] = event_of
        self.part_names: dict[str, str] = part_names
        self.conn_labels: tuple[str, ...] = tuple(conn_labels)
        #: connection label -> its drive events, group declaration order.
        self.drives_of: dict[str, tuple[Event, ...]] = drives_of
        #: connection label -> its member part ids, declaration order.
        self.members_of: dict[str, tuple[str, ...]] = members_of
        self.stages: tuple[ResolvedStage, ...] = tuple(stages)
        self.staging: ResolvedStaging | None = staging
        #: Event -> frame name. ``root`` is the assembled detail; every other
        #: value is a declared bench-unit name.
        self.frame_of: dict[Event, str] = dict(frame_of or {})
        #: Built part id -> declared bench unit (constructed parts only).
        self.unit_of: dict[str, str] = dict(unit_of or {})
        self.join_of: dict[str, Event] = dict(join_of or {})
        self.units: dict[str, ResolvedUnit] = {
            u.name: u for u in (staging.units if staging is not None else ())}
        self.context_parts = frozenset(
            staging.context_parts if staging is not None else ())
        connected = set()
        for mids in self.members_of.values():
            connected.update(mids)
        self._connected_parts = frozenset(connected)
        self._out: dict[Event, list[tuple[Event, EventEdge]]] = {}
        for ev in self.events:
            self._out.setdefault(ev, [])
        for e in self.edges:
            self._out[e.a].append((e.b, e))
        self._descendants: dict[Event, frozenset] = {}

    # -- queries ---------------------------------------------------------

    def describe(self, ev: Event) -> str:
        if ev.kind == "place":
            return f"place({self.part_names.get(ev.subject, ev.subject)})"
        if ev.kind == "join":
            return f"join({ev.subject})"
        grp = ev.group or "install"
        return f"drive({ev.subject}, {grp})"

    def _presence_event(self, part_id: str, at_frame: str) -> Event | None:
        """The event governing ``part_id`` in ``at_frame``.

        Inside its own bench frame a unit part is governed by its internal
        place/drive event. At root, the whole unit is governed by its join.
        """
        if at_frame == "root" and part_id in self.unit_of:
            return self.join_of[self.unit_of[part_id]]
        return self.event_of.get(part_id)

    def presence_at(self, drive: Event, part_id: str) -> PresenceDecision:
        """Classify one occupant at ``drive`` using graph + frame semantics.

        No linearization is selected. A bench frame excludes every non-member
        by the declaration's meaning, without inventing order between units.
        Root presence uses place/join reachability; undeclared context remains
        unordered, while explicit ``in_situ`` is the authored present mirror.
        """
        if drive not in self.frame_of:
            raise ValueError(
                f"presence query names unknown event {drive!r}")
        frame = self.frame_of[drive]
        own_event = self.event_of.get(part_id)
        if own_event == drive:
            return PresenceDecision("coincident", own_event)

        staging = self.staging
        if frame != "root" and self.unit_of.get(part_id) != frame:
            unit = self.units[frame]
            governed = self._presence_event(part_id, "root")
            trust = (part_id in self.context_parts
                     and part_id not in self._connected_parts)
            marker = " DECLARED TRUST:" if trust else ""
            src = (
                f"{marker} staging claim for subassembly {unit.name!r}: its "
                f"bench frame contains only that unit's parts, so "
                f"{self.part_names.get(part_id, part_id)} is absent while "
                f"this unit is assembled (why: {unit.why}); insertion travel "
                f"is not analyzed (P1)")
            return PresenceDecision(
                "absent", governed,
                (PresenceFact(FAMILY_STAGING, src),),
                declared_trust=trust)

        if (frame == "root" and part_id in self.context_parts
                and staging is not None and staging.mode == "in_situ"):
            src = (
                f"staging claim assembly mode 'in_situ': context body "
                f"{self.part_names.get(part_id, part_id)} is present from "
                f"the root build (why: {staging.why})")
            return PresenceDecision(
                "present", own_event,
                (PresenceFact(FAMILY_STAGING, src),))

        governed = self._presence_event(part_id, frame)
        if governed is None:
            return PresenceDecision("unordered", None)
        if governed == drive:
            return PresenceDecision("coincident", governed)
        if self.precedes(governed, drive):
            return PresenceDecision(
                "present", governed, self.path_edges(governed, drive))
        if self.precedes(drive, governed):
            return PresenceDecision(
                "absent", governed, self.path_edges(drive, governed))
        return PresenceDecision("unordered", governed)

    def descendants(self, ev: Event) -> frozenset:
        """Every event strictly reachable FROM ``ev`` (memoized BFS)."""
        cached = self._descendants.get(ev)
        if cached is not None:
            return cached
        seen: set[Event] = set()
        frontier = deque([ev])
        while frontier:
            for nxt, _e in self._out.get(frontier.popleft(), ()):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        out = frozenset(seen)
        self._descendants[ev] = out
        return out

    def precedes(self, a: Event, b: Event) -> bool:
        """Whether a provable order path ``a -> ... -> b`` exists."""
        return b in self.descendants(a)

    def path_edges(self, a: Event, b: Event) -> tuple[EventEdge, ...]:
        """The edges of ONE shortest proof path ``a -> ... -> b`` (BFS —
        deterministic because adjacency is built in declaration order).
        Empty when no path exists."""
        if a == b:
            return ()
        prev: dict[Event, tuple[Event, EventEdge]] = {}
        frontier = deque([a])
        seen = {a}
        while frontier:
            cur = frontier.popleft()
            for nxt, edge in self._out.get(cur, ()):
                if nxt in seen:
                    continue
                seen.add(nxt)
                prev[nxt] = (cur, edge)
                if nxt == b:
                    out: list[EventEdge] = []
                    node = b
                    while node != a:
                        node, e = prev[node]
                        out.append(e)
                    return tuple(reversed(out))
                frontier.append(nxt)
        return ()

    def describe_path(self, edges: tuple[EventEdge, ...]) -> str:
        """One order-fact proof line: every edge with its provenance family
        and source claim, arrow-chained — the facts a FAIL or a
        declared-order clear puts on paper."""
        if not edges:
            return ""
        bits = [self.describe(edges[0].a)]
        for e in edges:
            bits.append(f"->[{e.family}: {e.source}] {self.describe(e.b)}")
        return " ".join(bits)


def _stage_events(stage: ResolvedStage, drives_of, event_of,
                  part_names) -> list[Event]:
    """The events an authored stage claims: every listed connection's drive
    events plus every listed part's governing event. Unknown names are loud
    load-time teaching errors (the unknown-key registry discipline)."""
    out: list[Event] = []
    for label in stage.connections:
        drives = drives_of.get(label)
        if drives is None:
            known = sorted(drives_of)
            raise ValueError(
                f"sequence stage {stage.name!r}: connection {label!r} names "
                f"no compiled connection; compiled labels: {known}. An "
                f"authored order claim can only order connections that "
                f"exist.")
        out.extend(drives)
    for pid in stage.parts:
        ev = event_of.get(pid)
        if ev is None:
            known = sorted(part_names.get(p, p) for p in event_of)
            raise ValueError(
                f"sequence stage {stage.name!r}: part {pid!r} names no "
                f"built part; known parts: {known}. An authored order claim "
                f"can only order parts that exist.")
        out.append(ev)
    return out


def build_event_graph(assembly, connections, edges, installs,
                      stages=(), staging=None) -> EventGraph:
    """Build the merged assembly-slice CPG from the compiled surfaces
    (:func:`~detailgen.assemblies.connection.compile_connections` calls
    this after aggregation) and run the merged cycle check.

    ``edges`` are the raw part-level Construction-Graph edges (only
    ``installed_before`` is lifted), ``installs`` the resolved
    :class:`~detailgen.assemblies.installation.ResolvedInstallation`
    contracts, ``stages`` the resolved authored stages
    (:class:`ResolvedStage`; plain ``AuthoredStage``-shaped objects are
    accepted — ``chain`` defaults to one chain)."""
    parts = list(assembly.parts)
    part_names = {p.id: p.name for p in parts}

    # Defense below the loader/compiler: direct Python callers must not be
    # able to place one built part in two units or name an unbuilt/context
    # part as a unit member. The event graph is the semantic trust boundary.
    unit_of: dict[str, str] = {}
    if staging is not None:
        for unit in staging.units:
            for pid in unit.parts:
                if pid not in part_names:
                    raise ValueError(
                        f"staging subassembly {unit.name!r}: part {pid!r} "
                        f"names no built part; a bench unit can contain only "
                        f"parts in this compiled assembly.")
                prior = unit_of.get(pid)
                if prior is not None:
                    raise ValueError(
                        f"staging: part {part_names[pid]!r} belongs to both "
                        f"subassemblies {prior!r} and {unit.name!r} — a part "
                        f"may belong to at most one subassembly; nesting is "
                        f"unsupported.")
                if pid in staging.context_parts:
                    raise ValueError(
                        f"staging subassembly {unit.name!r}: context part "
                        f"{part_names[pid]!r} cannot be a constructed bench-"
                        f"unit member.")
                unit_of[pid] = unit.name
        unknown_context = set(staging.context_parts) - set(part_names)
        if unknown_context:
            raise ValueError(
                f"staging context part(s) {sorted(unknown_context)} name no "
                f"built part in this compiled assembly.")

    # -- drive events + the hardware -> drive mapping ---------------------
    conn_labels = [c.label for c in connections]
    if len(set(conn_labels)) != len(conn_labels):
        dupes = sorted({l for l in conn_labels if conn_labels.count(l) > 1})
        raise ValueError(
            f"event graph: duplicate connection label(s) {dupes} — a drive "
            f"event's identity is (connection label, role group), so two "
            f"connections sharing a label would silently merge into one "
            f"event. Give every connection a unique label.")
    members_of: dict[str, tuple[str, ...]] = {
        c.label: tuple(p.id for p in c.parts) for c in connections}
    installs_of: dict[str, list] = {}
    for ri in installs:
        installs_of.setdefault(ri.connection, []).append(ri)

    drives_of: dict[str, tuple[Event, ...]] = {}
    event_of: dict[str, Event] = {}
    fastener_of: dict[Event, tuple[str, ...]] = {}
    stack_candidates: dict[str, list[Event]] = {}
    for c in connections:
        ris = installs_of.get(c.label, [])
        if ris:
            evs = []
            for ri in ris:
                ev = Event("drive", c.label, ri.role)
                evs.append(ev)
                fastener_of[ev] = ri.fasteners
                for fid in ri.fasteners:
                    event_of[fid] = ev
                for hid in ri.stack:
                    stack_candidates.setdefault(hid, []).append(ev)
            drives_of[c.label] = tuple(evs)
        else:
            # A connection with no fastener role groups is still ONE real
            # installation act (a glued bond, a set connector): one drive
            # event, empty hardware set. Its declared hardware (if any) is
            # co-installed at it.
            ev = Event("drive", c.label, "")
            drives_of[c.label] = (ev,)
            fastener_of[ev] = ()
            for h in c.hardware:
                event_of.setdefault(h.id, ev)

    # Multi-stack resolution (review R-2): stack hardware maps to the drive
    # event its OWN type edges place it at-or-before; single-stack hardware
    # maps to its one group's drive. Ambiguity is loud, never a guess.
    before_of: dict[str, set[str]] = {}
    for e in edges:
        if e.kind == "installed_before":
            before_of.setdefault(e.a, set()).add(e.b)
    for hid, candidates in stack_candidates.items():
        if hid in event_of:
            continue  # already a driven fastener of some group
        uniq = list(dict.fromkeys(candidates))
        if len(uniq) == 1:
            event_of[hid] = uniq[0]
            continue
        at_or_before = [
            ev for ev in uniq
            if any(t in fastener_of.get(ev, ()) for t in before_of.get(hid, ()))]
        if len(at_or_before) != 1:
            names = ", ".join(f"drive({ev.subject}, {ev.group})" for ev in uniq)
            raise ValueError(
                f"event lift: hardware {part_names.get(hid, hid)!r} rides "
                f"{len(uniq)} role groups' stacks ({names}) and its own type "
                f"edges place it at-or-before "
                f"{len(at_or_before)} of them — the lift needs exactly one "
                f"(review R-2: multi-stack hardware maps to the drive event "
                f"its OWN type edges place it at-or-before, e.g. the "
                f"face-mount hanger's 'hanger -> header screws' edge names "
                f"the header-side drive). Declare the ordering edge on the "
                f"ConnectionType.")
        event_of[hid] = at_or_before[0]

    # Every remaining part gets a place event — including parts in no
    # connection (context bodies): their isolated node is exactly what an
    # UNKNOWN — build-order-underdetermined verdict points at.
    for p in parts:
        if p.id not in event_of:
            event_of[p.id] = Event("place", p.id)

    # -- frames + join events -------------------------------------------------
    # A connection is bench-scoped iff ALL its structural members belong to
    # the SAME declared unit. Anything crossing a unit boundary (or touching a
    # root part) is root-scoped. Hardware inherits its drive event's frame.
    connection_frame: dict[str, str] = {}
    for label, mids in members_of.items():
        units = {unit_of[mid] for mid in mids if mid in unit_of}
        if mids and len(units) == 1 and all(mid in unit_of for mid in mids):
            connection_frame[label] = next(iter(units))
        else:
            connection_frame[label] = "root"
    join_of: dict[str, Event] = {
        unit.name: Event("join", unit.name)
        for unit in (staging.units if staging is not None else ())}
    frame_of: dict[Event, str] = {}
    for pid, ev in event_of.items():
        if ev.kind == "place":
            frame_of[ev] = unit_of.get(pid, "root")
    for label, drives in drives_of.items():
        for dev in drives:
            frame_of[dev] = connection_frame[label]
    for join in join_of.values():
        frame_of[join] = "root"

    events: list[Event] = []
    seen_ev: set[Event] = set()
    for p in parts:
        ev = event_of[p.id]
        if ev not in seen_ev:
            seen_ev.add(ev)
            events.append(ev)
    for label in conn_labels:
        for ev in drives_of[label]:
            if ev not in seen_ev:
                seen_ev.add(ev)
                events.append(ev)
    for unit in (staging.units if staging is not None else ()):
        ev = join_of[unit.name]
        if ev not in seen_ev:
            seen_ev.add(ev)
            events.append(ev)

    # -- family 1: technique_default (lifted, F-5 same-event drop) --------
    lifted: list[tuple[Event, Event, str, EventEdge]] = []
    def _edge_event(pid: str, connection: str) -> Event | None:
        """Lift a part edge in the frame of its owning connection."""
        ev = event_of.get(pid)
        if (connection_frame.get(connection) == "root"
                and pid in members_of.get(connection, ())
                and pid in unit_of):
            return join_of[unit_of[pid]]
        return ev

    for e in edges:
        if e.kind != "installed_before":
            continue
        ea, eb = _edge_event(e.a, e.connection), _edge_event(e.b, e.connection)
        if ea is None or eb is None:
            # An installed_before edge naming a never-placed part: the
            # hardware-presence finding already blocks it; no event exists
            # to order.
            continue
        if ea == eb:
            continue  # order-vacuous intra-event edge (review F-5) — drop
        src = (f"{e.connection}: {part_names.get(e.a, e.a)} installed_before "
               f"{part_names.get(e.b, e.b)}")
        lifted.append((ea, eb, e.connection,
                       EventEdge(ea, eb, FAMILY_TECHNIQUE, src)))
    # Mid-event member interleave (third lift rule, found live on the
    # ThreadedRodEpoxyAnchor — same defect class as F-5/R-2, an order fact
    # the lift must handle): a member placed MID-hardware-chain (the anchor
    # bracket seats after the rod+leveling stack and before the upper
    # clamping stack) lifts to BOTH ``drive -> place(member)`` and
    # ``place(member) -> drive`` for the SAME (drive, member) pair of ONE
    # connection — a 2-cycle that would fail the shipped rock anchor at
    # load. Both directions express the member's arrival DURING the atomic
    # drive event, which event granularity cannot represent, so both drop
    # as intra-event order; structural necessity below supplies the
    # conservative surviving direction (the member is PRESENT at the drive
    # event — an occupant is never quietly ordered "later" by a fact this
    # coarse).
    directed = {(ea, eb, conn) for ea, eb, conn, _e in lifted}
    graph_edges: list[EventEdge] = []
    for ea, eb, conn, edge in lifted:
        if (eb, ea, conn) in directed and {ea.kind, eb.kind} == {
                "place", "drive"}:
            drive_ev = ea if ea.kind == "drive" else eb
            place_ev = eb if ea.kind == "drive" else ea
            if (drive_ev.subject == conn
                    and place_ev.subject in members_of.get(conn, ())):
                continue  # mid-event interleave — intra-event order, drop
        graph_edges.append(edge)

    # -- family 3: authored_sequence (declared, per chain) -----------------
    norm_stages = [
        st if isinstance(st, ResolvedStage) else ResolvedStage(
            name=st.name, why=st.why, chain=getattr(st, "chain", ""),
            connections=tuple(st.connections), parts=tuple(st.parts))
        for st in stages]
    chains: dict[str, list[ResolvedStage]] = {}
    for st in norm_stages:
        chains.setdefault(st.chain, []).append(st)
    for chain_stages in chains.values():
        for prev, nxt in zip(chain_stages, chain_stages[1:]):
            prev_events = _stage_events(prev, drives_of, event_of, part_names)
            next_events = _stage_events(nxt, drives_of, event_of, part_names)
            src = (f"authored sequence: stage {prev.name!r} precedes stage "
                   f"{nxt.name!r} (stage {prev.name!r} why: {prev.why})")
            for a in prev_events:
                for b in next_events:
                    if a != b:
                        graph_edges.append(
                            EventEdge(a, b, FAMILY_AUTHORED, src))
        # a single-stage chain still validates its names loudly
        if len(chain_stages) == 1:
            _stage_events(chain_stages[0], drives_of, event_of, part_names)

    # -- family 2: structural_necessity (derived, TECHNIQUE-path exception) -
    # The exception is scoped to FAMILY_TECHNIQUE edges ONLY (design §3.1:
    # the default yields "where a technique edge orders the opposite way" —
    # type-declared construction knowledge the type's docstring defends).
    # An AUTHORED stage must NEVER reach this walk: if it did, a sequence:
    # stage ordering a member after its own connection's drive would
    # SUPPRESS the derived presence fact instead of contradicting it — the
    # exact declared-order-silencing-a-check waiver channel §6 rule 1
    # forbids (review-cpgcore F-1, both live constructions). With the walk
    # technique-only, an authored-vs-necessity contradiction leaves both
    # edges in the merged graph and the cycle check below errors loudly,
    # naming both claims and both provenance families.
    technique_out: dict[Event, set[Event]] = {}
    for e in graph_edges:
        if e.family == FAMILY_TECHNIQUE:
            technique_out.setdefault(e.a, set()).add(e.b)

    def _technique_reaches(a: Event, b: Event) -> bool:
        seen = {a}
        frontier = deque([a])
        while frontier:
            for nxt in technique_out.get(frontier.popleft(), ()):
                if nxt == b:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return False

    for c in connections:
        for mid in members_of[c.label]:
            # In a root-scoped connection, a member already assembled inside
            # a unit becomes present at the unit's JOIN, not at its internal
            # bench-frame place event. Bench/root members keep their own place.
            if connection_frame[c.label] == "root" and mid in unit_of:
                mev = join_of[unit_of[mid]]
            else:
                mev = event_of.get(mid)
            if mev is None:
                continue
            for dev in drives_of[c.label]:
                if mev == dev:
                    continue
                if _technique_reaches(dev, mev):
                    # A TECHNIQUE path orders the member AFTER this drive
                    # (the hanger's hung member): the default is not
                    # emitted — a residual contradiction elsewhere still
                    # cycles loudly.
                    continue
                src = (f"{c.label}: member "
                       f"{part_names.get(mid, mid)} must exist before its "
                       f"{dev.group or 'install'} fasteners are driven")
                graph_edges.append(
                    EventEdge(mev, dev, FAMILY_NECESSITY, src))

    # -- family 4: staging (R-1 bench-events-before-join) ---------------------
    # This edge rule is derived from the staging declaration's own content:
    # "assembled apart" means every internal place/drive happens BEFORE the
    # unit enters root. It deliberately emits no cross-unit order.
    for unit in (staging.units if staging is not None else ()):
        join = join_of[unit.name]
        src = (
            f"bench events precede join for subassembly {unit.name!r} — "
            f"derived from the staging claim (why: {unit.why})")
        for ev in events:
            if frame_of.get(ev) == unit.name:
                graph_edges.append(
                    EventEdge(ev, join, FAMILY_STAGING, src))

    graph = EventGraph(events, graph_edges, event_of, part_names,
                       conn_labels, drives_of, members_of, norm_stages,
                       staging=staging, frame_of=frame_of,
                       unit_of=unit_of, join_of=join_of)
    _check_event_order(graph)
    return graph


def _check_event_order(graph: EventGraph) -> None:
    """The merged cycle check (§3's consistency check): one Kahn pass over
    every family combined. The teaching error names the conflicting edges
    AND their provenance families — a cycle between an authored stage and a
    technique edge tells the author which claim to fix."""
    indeg: dict[Event, int] = {ev: 0 for ev in graph.events}
    for e in graph.edges:
        indeg[e.b] += 1
    q = deque(ev for ev, d in indeg.items() if d == 0)
    seen = 0
    while q:
        ev = q.popleft()
        seen += 1
        for nxt, _e in graph._out.get(ev, ()):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    if seen == len(graph.events):
        return
    remaining = {ev for ev, d in indeg.items() if d > 0}
    cyclic = [e for e in graph.edges if e.a in remaining and e.b in remaining]
    lines = [f"  {graph.describe(e.a)} -> {graph.describe(e.b)} "
             f"[{e.family}] ({e.source})" for e in cyclic]
    raise EventOrderCycleError(
        "Construction process graph has a cycle — the order facts "
        "contradict each other, so no build order satisfies them all. "
        "Conflicting order facts (with provenance family and source "
        "claim):\n" + "\n".join(lines) + "\n"
        "Fix the claim that is wrong: when an authored sequence: stage "
        "contradicts a ConnectionType's technique edge or a derived "
        "structural-necessity fact (a member must exist before its own "
        "connection's fasteners are driven), one of the two is not how "
        "this joint is built.")


# -- canonical linearization + reader steps (§5.1) ----------------------------


def linearize(graph: EventGraph) -> tuple[Event, ...]:
    """ONE deterministic linearization of the event graph (Kahn; ties broken
    by declared stage order, then connection declaration order, then part
    id — byte-stable docs, the house rule). Purely presentational: verdicts
    never depend on it (§4.1 judges the partial order)."""
    stage_idx: dict[Event, int] = {}
    for i, st in enumerate(graph.stages):
        for label in st.connections:
            for ev in graph.drives_of.get(label, ()):
                stage_idx.setdefault(ev, i)
        for pid in st.parts:
            ev = graph.event_of.get(pid)
            if ev is not None:
                stage_idx.setdefault(ev, i)
    conn_idx = {label: i for i, label in enumerate(graph.conn_labels)}
    first_consumer: dict[str, int] = {}
    for label, mids in graph.members_of.items():
        for mid in mids:
            ci = conn_idx[label]
            if mid not in first_consumer or ci < first_consumer[mid]:
                first_consumer[mid] = ci

    big = len(graph.conn_labels) + len(graph.stages) + 10**6

    def key(ev: Event):
        si = stage_idx.get(ev, big)
        if ev.kind == "drive":
            return (si, conn_idx.get(ev.subject, big), 1, ev.group)
        return (si, first_consumer.get(ev.subject, big), 0, ev.subject)

    indeg: dict[Event, int] = {ev: 0 for ev in graph.events}
    for e in graph.edges:
        indeg[e.b] += 1
    heap = [(key(ev), ev) for ev, d in indeg.items() if d == 0]
    heapq.heapify(heap)
    out: list[Event] = []
    released: set[Event] = set(ev for _k, ev in heap)
    while heap:
        _k, ev = heapq.heappop(heap)
        out.append(ev)
        for nxt, _e in graph._out.get(ev, ()):
            indeg[nxt] -= 1
            if indeg[nxt] == 0 and nxt not in released:
                released.add(nxt)
                heapq.heappush(heap, (key(nxt), nxt))
    return tuple(out)


def derive_reader_steps(graph: EventGraph) -> tuple[ReaderStep, ...]:
    """The reader-step grouping (§5.1), a PURE function of the graph — one
    step per authored stage where stages exist, else one step per
    connection install unit; ``place`` events fold into the step of the
    first connection that consumes the part (a stage's explicitly listed
    parts fold into that stage's step). Parts consumed by no connection and
    claimed by no stage have no order fact and are reported by the renderer
    as exactly that, never given an invented position. Regrouping cannot
    change a verdict (§2)."""
    order = linearize(graph)
    pos = {ev: i for i, ev in enumerate(order)}

    stage_of_conn: dict[str, ResolvedStage] = {}
    stage_of_part: dict[str, ResolvedStage] = {}
    for st in graph.stages:
        for label in st.connections:
            stage_of_conn.setdefault(label, st)
        for pid in st.parts:
            stage_of_part.setdefault(pid, st)

    conn_idx = {label: i for i, label in enumerate(graph.conn_labels)}

    # bucket key: ("stage", chain, name) or ("conn", label)
    buckets: dict[tuple, dict] = {}

    def bucket_for(key: tuple, stage: ResolvedStage | None, title: str):
        b = buckets.get(key)
        if b is None:
            b = {"stage": stage, "title": title, "connections": [],
                 "parts": [], "first": len(order) + 1}
            buckets[key] = b
        return b

    for label in graph.conn_labels:
        st = stage_of_conn.get(label)
        if st is not None:
            key = ("stage", st.chain, st.name)
            b = bucket_for(key, st, f"stage {st.name!r} (declared order)")
        else:
            key = ("conn", label)
            b = bucket_for(key, None, f"install {label}")
        b["connections"].append(label)
        for ev in graph.drives_of[label]:
            b["first"] = min(b["first"], pos.get(ev, len(order)))

    # fold place events: stage-claimed parts to their stage's step; every
    # other consumed part to its FIRST consuming connection's step.
    for p_id, ev in graph.event_of.items():
        if ev.kind != "place":
            continue
        st = stage_of_part.get(p_id)
        if st is not None:
            b = bucket_for(("stage", st.chain, st.name), st,
                           f"stage {st.name!r} (declared order)")
            b["parts"].append(p_id)
            b["first"] = min(b["first"], pos.get(ev, len(order)))
            continue
        consumers = [label for label in graph.conn_labels
                     if p_id in graph.members_of[label]]
        if not consumers:
            continue  # no order fact — the renderer says so
        first = min(consumers, key=lambda lbl: conn_idx[lbl])
        st2 = stage_of_conn.get(first)
        key = (("stage", st2.chain, st2.name) if st2 is not None
               else ("conn", first))
        buckets[key]["parts"].append(p_id)

    steps = []
    for b in sorted(buckets.values(), key=lambda b: b["first"]):
        steps.append(ReaderStep(
            title=b["title"], stage=b["stage"],
            connections=tuple(b["connections"]),
            parts_placed=tuple(sorted(b["parts"]))))
    return tuple(steps)


def unordered_parts(graph: EventGraph) -> tuple[str, ...]:
    """Part ids with NO order fact at all: consumed by no connection and
    claimed by no stage — their place event is isolated. The reader surface
    names them as exactly that (context bodies, unfastened parts) rather
    than inventing a position."""
    claimed: set[str] = set()
    for st in graph.stages:
        claimed.update(st.parts)
    consumed: set[str] = set()
    for mids in graph.members_of.values():
        consumed.update(mids)
    out = []
    for pid, ev in graph.event_of.items():
        if ev.kind != "place" or pid in consumed or pid in claimed:
            continue
        if not graph._out.get(ev) and not any(
                e.b == ev for e in graph.edges):
            out.append(pid)
    return tuple(sorted(out))
