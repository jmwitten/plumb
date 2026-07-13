"""Load-path REPRESENTATION check (Wave 3, task ONTOLOGY, P5).

The honest, capacity-free question this check answers: **is there a typed graph
path by which a declared ``support`` reaches ``ground``, through connections
that CLAIM to transfer the load class?** If yes, the path is *REPRESENTED*. That
is emphatically NOT "safe": no force, area, or capacity is computed anywhere
here (see the binding WAVE 3 wording rule). A REPRESENTED path only means the
author has declared, and the ontology can trace, an unbroken chain of
load-transferring joints from the member down to the earth.

What it consumes (all already produced by the lifecycle):

- **roles** — ``{part_id: role}`` (:mod:`detailgen.core.ontology`), the
  author's declaration of which parts are ``support`` / ``connector`` /
  ``ground``.
- **edges** — the Construction-Graph load-path edges a ``ConnectionType``
  already emits (``bears_on`` / ``transfers_load_to`` / ``fastened_by`` /
  ``bonded_to``); these ARE the connectivity, so the check invents no geometry.
- **transfers** — ``{connection_label: True|False|None}``: does that connection
  transfer the load class? Derived from the connection types'
  :class:`~detailgen.core.ontology.TransferClaim`\\ s. An edge only carries load
  if its owning connection CLAIMS to transfer the class (``True``). ``False``
  (an honest does_not_transfer) or ``None`` (no claim — unknown) DROPS the edge
  from the load-path graph, which is exactly how a defect surfaces.

The reachability is deliberately UNDIRECTED: "no direction initially" (WAVE 3
SHAPE). We assert a *connected* load-transferring chain support↔ground, not a
directed flow — direction (and then capacity) are later, finer commitments.

THE DEFECT CLASS this makes visible (the live gravity-seated-rail bug): a member
that merely RESTS on its support with a ``bears_on`` edge but whose connection
does_not_transfer (or has no fastener that transfers) the load leaves no
represented path — the support reaches no ground, and the check FAILS naming the
break. Proven on rock-anchor geometry in ``tests/test_loadpath.py``.

The check kind is ``load_path``; it is family-tagged to "Load-path
representation" in :data:`detailgen.validation.coverage.KIND_TO_FAMILY` (the
registration that matters for the coverage matrix). It is not a
``validate_assembly`` sweep stage — it needs roles + the compiled
Construction-Graph edges, which are lifecycle outputs, not sweep inputs — so a
detail opts in by emitting its findings from ``extra_checks`` (see
:func:`load_path_findings`). A detail that declares no roles gets no finding and
the family honestly stays UNKNOWN.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..core.ontology import GROUND_ROLE, LOAD_CLASSES, ROLES, SUPPORT_ROLE
from .checks import Finding

#: Construction-Graph edge kinds that carry load (a subset of a connection's
#: edges — install-order edges are sequencing, not load). Open by intent: a
#: later, finer load model can add kinds without changing callers.
#: ``bonded_to`` (task GLUE) is the adhesive analog of ``fastened_by`` — an
#: adhesive bond carries load between the bonded members exactly as a
#: fastener does, gated per class by its connection's transfer claims like
#: every other edge here.
LOAD_BEARING_EDGE_KINDS: frozenset[str] = frozenset(
    {"bears_on", "transfers_load_to", "fastened_by", "bonded_to"})


@dataclass(frozen=True)
class LoadPath:
    """One support's load-path result for a load class. ``represented`` is the
    honest verdict; ``chain`` is the part-id path support→…→ground when
    represented, or the reachable frontier when not (so the break is visible)."""

    load_class: str
    support: str                 # part id of the originating support-role part
    represented: bool
    reached_ground: str | None   # part id of the ground it reached, or None
    chain: tuple[str, ...]       # part ids, support first
    note: str


@dataclass
class LoadPathResult:
    findings: list[Finding] = field(default_factory=list)
    paths: list[LoadPath] = field(default_factory=list)


def _adjacency(edges, transfers) -> tuple[dict, dict]:
    """Undirected adjacency over load-bearing edges whose owning connection
    CLAIMS to transfer the class (``transfers[label] is True``). Returns
    ``(adj, dropped)`` where ``dropped`` records, per excluded connection, why
    (``does_not_transfer`` / ``no transfer claim``) — the audit trail behind a
    failure message."""
    adj: dict[str, set[str]] = {}
    dropped: dict[str, str] = {}
    for e in edges:
        kind = getattr(e, "kind", None)
        if kind not in LOAD_BEARING_EDGE_KINDS:
            continue
        label = getattr(e, "connection", "")
        verdict = transfers.get(label)
        if verdict is not True:
            dropped[label] = ("does_not_transfer" if verdict is False
                              else "no transfer claim")
            continue
        a, b = e.a, e.b
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    return adj, dropped


def _bfs_path(adj: dict, start: str, goals: set[str]) -> tuple[list[str], set[str]]:
    """Shortest undirected path from ``start`` to any node in ``goals``.
    Returns ``(path, visited)``; ``path`` is empty if no goal is reachable.
    Neighbour iteration is sorted so the represented chain is deterministic
    (byte-identical across spec/imperative paths)."""
    prev: dict[str, str | None] = {start: None}
    q: deque[str] = deque([start])
    while q:
        n = q.popleft()
        if n in goals:
            path = [n]
            while prev[path[-1]] is not None:
                path.append(prev[path[-1]])
            path.reverse()
            return path, set(prev)
        for m in sorted(adj.get(n, ())):
            if m not in prev:
                prev[m] = n
                q.append(m)
    return [], set(prev)


def check_load_path(*, load_class: str, roles: dict, edges, transfers: dict,
                    name_of: dict | None = None) -> LoadPathResult:
    """Prove (as REPRESENTATION only) a load path from every ``support`` to a
    ``ground``, for ``load_class``, over the load-transferring construction
    edges. One :class:`~detailgen.validation.checks.Finding` (kind
    ``load_path``) per support, deterministic in support-id order.

    ``load_class`` must be a currently-PROVABLE class (a reachability proof
    only exists for those) — a reserved class here is a teaching
    :class:`~detailgen.core.ontology.OntologyError`."""
    LOAD_CLASSES.require(load_class)
    name_of = name_of or {}

    def nm(pid: str) -> str:
        return name_of.get(pid, pid)

    supports = sorted(p for p, r in roles.items() if r == SUPPORT_ROLE)
    grounds = {p for p, r in roles.items() if r == GROUND_ROLE}
    adj, dropped = _adjacency(edges, transfers)

    result = LoadPathResult()
    verb = load_class.replace("_", "-")
    for s in supports:
        if not grounds:
            note = (f"no part is declared role {GROUND_ROLE!r}; a load path "
                    f"cannot be REPRESENTED without a terminal Support")
            result.paths.append(LoadPath(load_class, s, False, None, (s,), note))
            result.findings.append(Finding(
                "load_path", f"{load_class}: {nm(s)} -> ground", False,
                f"{verb} path BROKEN: {note}"))
            continue
        path, visited = _bfs_path(adj, s, grounds)
        if path:
            g = path[-1]
            chain = " -> ".join(nm(p) for p in path)
            note = f"{verb} path REPRESENTED: {chain}"
            result.paths.append(LoadPath(load_class, s, True, g, tuple(path), note))
            result.findings.append(Finding(
                "load_path", f"{load_class}: {nm(s)} -> {nm(g)}", True, note))
        else:
            reached = sorted(visited - {s})
            reached_txt = ", ".join(nm(p) for p in reached) or "nothing"
            why = ""
            if dropped:
                why = (" — connection(s) not carrying this load: "
                       + "; ".join(f"{lbl} ({reason})"
                                   for lbl, reason in sorted(dropped.items())))
            note = (f"{verb} path BROKEN: {nm(s)} reaches no ground/Support "
                    f"(reached: {reached_txt}); no {load_class}-transferring "
                    f"connection completes the chain{why}")
            result.paths.append(LoadPath(load_class, s, False, None,
                                         tuple([s] + reached), note))
            result.findings.append(Finding(
                "load_path", f"{load_class}: {nm(s)} -> ground", False, note))
    return result


def transfers_by_connection(connections, load_class: str) -> dict:
    """``{connection.label: True|False|None}`` for ``load_class``, read from
    each connection's type's :class:`~detailgen.core.ontology.TransferClaim`\\ s.
    ``True``/``False`` = an explicit transfers/does_not_transfer claim; ``None``
    = the type makes no claim about this class (so the load-path proof cannot
    route through it — unknown, not assumed)."""
    out: dict[str, bool | None] = {}
    for c in connections:
        verdict: bool | None = None
        for claim in getattr(type(c.kind), "transfer_claims", ()):
            if claim.load_class == load_class:
                verdict = claim.transfers
        out[c.label] = verdict
    return out


def load_path_findings(*, roles_by_name: dict, assembly, connections,
                       edges, load_class: str = "downward_load") -> list[Finding]:
    """The detail-facing entry point, shared by the imperative and spec paths so
    both emit BYTE-IDENTICAL load-path findings.

    ``roles_by_name`` maps a part's DISPLAY NAME (the authoring surface — an
    author writes ``leg: support``) to a role; it is resolved to part ids
    against ``assembly`` here (a name that resolves to no unique part is a hard
    error, never a silent drop). Returns the findings to append in
    ``extra_checks``; empty when no roles are declared (the family stays
    honestly UNKNOWN)."""
    if not roles_by_name:
        return []
    roles = {}
    name_of = {}
    for name, role in roles_by_name.items():
        ROLES.require(role)               # teaching error on reserved/unknown role
        placed = assembly._resolve(name)  # loud on unknown/ambiguous name
        roles[placed.id] = role
        name_of[placed.id] = placed.name
    transfers = transfers_by_connection(connections, load_class)
    result = check_load_path(load_class=load_class, roles=roles, edges=edges,
                             transfers=transfers, name_of=name_of)
    return result.findings
