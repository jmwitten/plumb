"""The **semantic-analysis pass** for MOUNT relations (CL-1 slice of
cl0-design.md §3.5) — declaration-time teaching errors, fired BEFORE any
geometry is built.

The recorded pain (retro R4, amplified by R6): a spatial or reference mistake
was found only after a full build + validate loop — ~3 minutes, run 8–15× per
task. This pass turns that class into an instant compile error. It checks each
mount against the ontology and against the others:

- **dangling reference** — a ``to:`` that names a component that does not exist;
- **under-constrained** — a mount that does not pin all six degrees of freedom
  (an in-plane axis left free by neither ``center`` nor ``raise``);
- **over-constrained** — two clauses fighting over one axis (Z both centered and
  raised, or a ``raise`` along the standoff axis);
- **un-realisable mirror** — a ``mirror`` whose opposite hand is not a single
  rigid rotation (the part is not centered on every non-mirror axis but one);
- **relation cycle** — a mount chain A→B→A (no part can register against a part
  that registers against it).

Every failure is a :class:`SemanticError` in the teaching style: it NAMES the
missing or conflicting constraint and how to fix it — never a bare raise, never
a silent guess. Purity guarantee: this reads only the loaded declarations (ids,
axes, clauses), never geometry — so it runs in milliseconds, before the kernel.
"""

from __future__ import annotations

import difflib

from .schema import (
    MOUNT_AXES,
    ComponentSpec,
    ConnectionSpec,
    FeatureSpec,
    MountSpec,
    RepeatSpec,
)
from .lowering import feature_identity


class SemanticError(ValueError):
    """A declaration-time semantic problem in a mount relation, in the teaching
    style (what is wrong + the constraint to add / remove)."""


def require_connection_process_capability(conn: ConnectionSpec, kind: str,
                                          *, owner: str) -> frozenset[str]:
    """Resolve one registered process capability or fail with teaching text.

    This is the declaration-time trust boundary shared by standalone and site
    connections.  Registry resolution happens exactly once: an unknown type
    keeps the registry's established known-types / did-you-mean diagnostic
    instead of being mislabeled as a known type with no capability.
    """
    from ..assemblies.connection import connection_types

    try:
        type_cls = connection_types.get(conn.type)
    except KeyError as e:
        raise SemanticError(str(e)) from None
    supported = frozenset(type_cls.supported_process_kinds())
    if kind not in supported:
        raise SemanticError(
            f"{owner}: registered connection type {conn.type!r} does not "
            f"support process-kind capability {kind!r}; its supported "
            f"process kinds are "
            f"{sorted(supported)}.")
    return supported


def analyze_mounts(doc) -> None:
    """Run the mount semantic-analysis pass over a loaded ``DetailSpecDoc``.
    Raises the FIRST :class:`SemanticError` found (declaration order), so the
    author fixes one named constraint at a time. A doc with no mounts is a
    no-op."""
    mounts = list(_walk_mounts(doc.components))
    if not mounts:
        return
    declared = _declared_ids(doc.components)
    for cid, mount in mounts:
        _check_dangling(cid, mount, declared)
        _check_dof(cid, mount)
        _check_mirror(cid, mount)
    _check_cycles(mounts)


def analyze_features(doc) -> None:
    """The FEATURE slice of the §3.5 declaration-time pass (CL-2). Runs at COMPILE,
    before any geometry, and checks each feature against the ontology:

    - **dangling reference** — a ``clearance_cut around:`` that names a component
      that does not exist (a feature fits a part around a MEMBER; the member must
      exist);
    - **duplicate feature identity** — two features on ONE part that collide on
      their identity (Q3 / fab-design §9: FAB keys the process step on the
      feature's identity, so a collision would make two ops indistinguishable),
      and two AUTHORED ids that collide across the whole detail (a cross-part key
      must be unique).

    (A negative ``gap`` and the geometric no-op — a clearance_cut whose member
    never reaches the part footprint — depend on RESOLVED values / placed
    geometry, so they are teaching errors in the compiler's post-placement
    feature pass, not here.)"""
    feats = list(_walk_features(doc.components))
    if not feats:
        return
    declared = _declared_ids(doc.components)
    authored: dict[str, str] = {}
    per_part: dict[str, set] = {}
    for cid, feat in feats:
        if feat.kind == "clearance_cut" and "{" not in feat.around \
                and feat.around not in declared:
            hint = difflib.get_close_matches(feat.around, sorted(declared), n=3)
            tip = f" — did you mean one of {hint}?" if hint else ""
            raise SemanticError(
                f"feature on {cid!r}: clearance_cut around {feat.around!r} is not "
                f"a declared component{tip}. A clearance_cut fits this part around "
                f"a MEMBER; the member must exist (declare it in 'components').")
        ident = feature_identity(feat)
        seen = per_part.setdefault(cid, set())
        if ident in seen:
            raise SemanticError(
                f"feature on {cid!r}: two features collide on identity {ident!r}. "
                f"Each feature on a part needs a distinct identity so its "
                f"fabrication step is addressable — give one an explicit 'id'.")
        seen.add(ident)
        if feat.id:
            if feat.id in authored and authored[feat.id] != cid:
                raise SemanticError(
                    f"feature id {feat.id!r} is declared on both "
                    f"{authored[feat.id]!r} and {cid!r}. An authored feature id is "
                    f"a detail-wide key (FAB/INCR/cut-notes reference it); make it "
                    f"unique or drop it to fall back to the content key.")
            authored[feat.id] = cid


def analyze_retires(doc) -> None:
    """The RETIRE slice of the §3.5 declaration-time pass (CL-3, retro R10). Runs
    at COMPILE, before any geometry, so a retirement that cannot be honoured is a
    teaching error in milliseconds, never a silent no-op or a check left
    validating against a part that is gone:

    - **orphan retirement** — a ``retire: {connection: <label>}`` whose label
      names no connection, or a ``retire: {member: <id>}`` whose id names no
      component. You cannot retire what does not exist (did-you-mean on the near
      misses);
    - **retire-with-dependents** — a ``retire: {member: <id>}`` where a SURVIVING
      declaration (a connection not itself retired, a bearing/bond/overlap/
      through-hole/dimension, a mount ``to:``, a feature ``around:``, a mate
      target, or a role) still references the id. The error LISTS the dependents
      so the author retires or re-points them explicitly — never a dangling
      reference the compiler discovers three minutes later.

    Retiring a CONNECTION is always safe (its whole derived closure — bearings,
    interferences, hardware findings, evidence edges, attached expectations — is
    OWNED by it, so it unwinds by construction); only a MEMBER can have surviving
    dependents, because a member is referenced by many declarations."""
    if not doc.retire:
        return
    conn_labels = {c.label for c in _walk_connections(doc.connections) if c.label}
    member_ids = _declared_ids(doc.components)
    retired_conn = {r.target for r in doc.retire if r.kind == "connection"}
    for r in doc.retire:
        if r.kind == "connection":
            if r.target not in conn_labels:
                hint = difflib.get_close_matches(r.target, sorted(conn_labels), n=3)
                tip = f" — did you mean one of {hint}?" if hint else ""
                raise SemanticError(
                    f"retire: connection {r.target!r} names no declared "
                    f"connection{tip}. You cannot retire a joint that does not "
                    f"exist; retire by the connection's 'label'.")
        else:  # member
            if r.target not in member_ids:
                hint = difflib.get_close_matches(r.target, sorted(member_ids), n=3)
                tip = f" — did you mean one of {hint}?" if hint else ""
                raise SemanticError(
                    f"retire: member {r.target!r} names no declared "
                    f"component{tip}. You cannot retire a member that does not "
                    f"exist.")
            deps = _member_dependents(doc, r.target, retired_conn)
            if deps:
                listed = "; ".join(deps)
                raise SemanticError(
                    f"retire: member {r.target!r} is still referenced by "
                    f"{len(deps)} surviving declaration(s): {listed}. Retire or "
                    f"re-point each one first — a retirement must not leave a "
                    f"check validating against a member that is gone. (Retiring "
                    f"the connection that owns a reference removes it with the "
                    f"joint; a hand-authored reference you re-point or drop.)")


def analyze_sequence(doc) -> None:
    """The SEQSCHEMA slice of the §3.5 declaration-time pass (task SEQSCHEMA,
    stepdoc-cpg-design.md §3.1 family 3, ``authored_sequence``). Runs at
    COMPILE, before any geometry: every ``connections:``/``parts:`` entry in
    a ``sequence:`` stage must name an EXISTING connection label / component
    authored id.

    The loader (:func:`~detailgen.spec.loader._build_sequence`) already
    proved the block's own internal structure (why required, no cross-stage
    double-claim, stage names unique); this pass is the one check that needs
    the REST of the doc — the same split as :func:`analyze_retires`, whose
    target-existence check is likewise deferred here rather than done at
    load. Did-you-mean on the near misses, same style throughout this
    module."""
    connections = list(_walk_connections(doc.connections))
    conn_by_label: dict[str, list] = {}
    for conn in connections:
        if conn.label:
            conn_by_label.setdefault(conn.label, []).append(conn)

    # A process refinement is meaningful only where the registered
    # ConnectionType declares that capability.  The runtime graph asks the
    # same capability surface and also confirms an event was actually emitted;
    # no display key (including ``glued``) is a second authority.
    for conn in connections:
        if conn.process.cure is not None:
            require_connection_process_capability(
                conn, "cure",
                owner=f"connection {conn.label or conn.type!r}: process.cure")

    if (not doc.sequence.stages and not doc.sequence.subassemblies
            and doc.sequence.assembly is None and not doc.sequence.after):
        return
    conn_labels = set(conn_by_label)
    member_ids = _declared_ids(doc.components)
    for stage in doc.sequence.stages:
        for label in stage.connections:
            if label not in conn_labels:
                hint = difflib.get_close_matches(label, sorted(conn_labels), n=3)
                tip = f" — did you mean one of {hint}?" if hint else ""
                raise SemanticError(
                    f"sequence stage {stage.name!r}: connection {label!r} "
                    f"names no declared connection{tip}. An authored order "
                    f"claim can only reference a connection by its 'label'.")
        for pid in stage.parts:
            if pid not in member_ids:
                hint = difflib.get_close_matches(pid, sorted(member_ids), n=3)
                tip = f" — did you mean one of {hint}?" if hint else ""
                raise SemanticError(
                    f"sequence stage {stage.name!r}: part {pid!r} names no "
                    f"declared component{tip}. An authored order claim can "
                    f"only reference a part by its authored component id.")
    for unit in doc.sequence.subassemblies:
        for pid in unit.parts:
            if pid not in member_ids:
                hint = difflib.get_close_matches(pid, sorted(member_ids), n=3)
                tip = f" — did you mean one of {hint}?" if hint else ""
                raise SemanticError(
                    f"sequence subassembly {unit.name!r}: part {pid!r} "
                    f"names no declared component{tip}. A staging claim can "
                    f"only reference a part by its authored component id.")
            if doc.roles.get(pid) == "existing":
                raise SemanticError(
                    f"sequence subassembly {unit.name!r}: part {pid!r} is "
                    f"declared role 'existing' — a pre-existing context body "
                    f"cannot be a constructed bench-unit member. Leave context "
                    f"out of subassemblies and declare its presence through "
                    f"assembly mode when needed.")

    for claim in doc.sequence.after:
        _require_unique_sequence_connection(
            claim.connection, conn_by_label,
            f"sequence after target connection {claim.connection!r}")
        for ref in claim.after:
            source = _require_unique_sequence_connection(
                ref.connection, conn_by_label,
                f"sequence after {ref.kind} source {ref.connection!r}")
            require_connection_process_capability(
                source, ref.kind,
                owner=(f"sequence after target {claim.connection!r}: "
                       f"{ref.kind} source {ref.connection!r}"))


def _require_unique_sequence_connection(label: str, by_label: dict[str, list],
                                        owner: str):
    """Resolve one authored connection label at declaration time.

    Repeat templates appear once here and are deliberately resolved later.
    Two independently authored declarations reusing one label are ambiguous
    immediately and therefore loud before geometry.
    """
    matches = by_label.get(label, [])
    if not matches:
        known = sorted(by_label)
        hint = difflib.get_close_matches(label, known, n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise SemanticError(
            f"{owner} names no declared connection{tip}. A point constraint "
            f"can only reference a connection by its 'label'.")
    if len(matches) != 1:
        raise SemanticError(
            f"{owner} is ambiguous: {len(matches)} declared connections reuse "
            f"that label. Point constraints require one unique authored "
            f"connection label.")
    return matches[0]


def _member_dependents(doc, mid: str, retired_conn: set) -> list[str]:
    """Every SURVIVING declaration that references member ``mid`` — the list a
    retire-with-dependents error names. A reference owned by a connection that is
    ITSELF being retired is excluded (it retires with the joint)."""
    deps: list[str] = []
    for c in _walk_connections(doc.connections):
        if c.label in retired_conn:
            continue
        if mid in c.parts or any(getattr(h, "id", h) == mid for h in c.hardware):
            deps.append(f"connection {c.label or c.type!r}")
    v = doc.validation
    for b in v.bearings:
        if mid in (b.a, b.b):
            deps.append(f"bearing {b.a}<->{b.b}")
    for b in v.bonds:
        if mid in (b.a, b.b):
            deps.append(f"bond {b.a}<->{b.b}")
    for o in v.expected_overlaps:
        if mid in (o.a, o.b):
            deps.append(f"expected_overlap {o.a}<->{o.b}")
    for t in v.through_holes:
        if mid == t.part or mid in t.passes_through:
            deps.append(f"through_hole on {t.part}")
    for dspec in v.dimensions:
        if mid in (dspec.part, dspec.minus_part):
            deps.append(f"dimension {dspec.name!r}")
    for cid, mount in _walk_mounts(doc.components):
        if mount.to == mid and cid != mid:
            deps.append(f"mount {cid!r} to {mid}")
    for cid, feat in _walk_features(doc.components):
        if feat.kind == "clearance_cut" and feat.around == mid and cid != mid:
            deps.append(f"feature on {cid!r} around {mid}")
    if mid in doc.roles:
        deps.append(f"role {doc.roles[mid]!r}")
    return deps


def _walk_connections(entries):
    """Yield every :class:`ConnectionSpec`, recursing into repeat bodies (a
    repeated joint is a declaration like a hand one)."""
    for e in entries:
        if isinstance(e, ConnectionSpec):
            yield e
        elif isinstance(e, RepeatSpec):
            yield from _walk_connections(e.body)


def _walk_features(entries):
    """Yield ``(component_id, FeatureSpec)`` for every featured component,
    recursing into repeat bodies (a repeated feature is checked like a hand one)."""
    for e in entries:
        if isinstance(e, ComponentSpec):
            for feat in e.features:
                yield e.id, feat
        elif isinstance(e, RepeatSpec):
            yield from _walk_features(e.body)


def _walk_mounts(entries):
    """Yield ``(component_id, MountSpec)`` for every mounted component, recursing
    into repeat bodies (a repeated placement is checked like a hand-placed one)."""
    for e in entries:
        if isinstance(e, ComponentSpec):
            if isinstance(e.place, MountSpec):
                yield e.id, e.place
        elif isinstance(e, RepeatSpec):
            yield from _walk_mounts(e.body)


def _declared_ids(entries) -> set:
    out = set()
    for e in entries:
        if isinstance(e, ComponentSpec):
            out.add(e.id)
        elif isinstance(e, RepeatSpec):
            out |= _declared_ids(e.body)
    return out


def _check_dangling(cid: str, mount: MountSpec, declared: set) -> None:
    # A repeat-templated id (contains '{var}') resolves per iteration — its
    # existence is a build-time fact, checked there; skip the static screen.
    if "{" in mount.to:
        return
    if mount.to not in declared:
        hint = difflib.get_close_matches(mount.to, sorted(declared), n=3)
        tip = f" — did you mean one of {hint}?" if hint else ""
        raise SemanticError(
            f"mount of {cid!r}: target {mount.to!r} is not a declared "
            f"component{tip}. A mount registers this part against another; the "
            f"target must exist (declare it earlier in 'components').")


def _in_plane_axes(mount: MountSpec) -> list:
    return [a for a in MOUNT_AXES if a != mount.axis]


def _check_dof(cid: str, mount: MountSpec) -> None:
    """All six DOF must be pinned. The standoff pins the normal axis (one
    translation); the face-pair facing pins all three rotations (``spin`` is an
    optional re-aim, not a required pin). Each of the two IN-PLANE translations
    must be pinned by ``center`` (to the target axis) or, for Z, by ``ground``
    (the base height above grade)."""
    # over-constraint: ground along the standoff axis, or Z both centered +
    # grounded. (The standoff-axis-Z case is also caught at load, belt-and-braces.)
    if mount.ground is not None and mount.axis == "Z":
        raise SemanticError(
            f"mount of {cid!r}: 'ground' registers the base along Z, but Z is the "
            f"standoff axis here — that over-constrains the mate normal. Drop "
            f"'ground', or choose a standoff axis other than Z.")
    if mount.ground is not None and "Z" in mount.center:
        raise SemanticError(
            f"mount of {cid!r}: Z is both centered and grounded — two clauses "
            f"fighting over one axis. Keep 'center' OR 'ground' for Z, not both.")
    gaps = []
    for b in _in_plane_axes(mount):
        pinned = (b in mount.center) or (b == "Z" and mount.ground is not None)
        if not pinned:
            gaps.append(b)
    if gaps:
        raise SemanticError(
            f"mount of {cid!r}: under-constrained — the in-plane axis/axes "
            f"{gaps} are pinned by nothing. Add each to 'center' (register on the "
            f"target axis), or use 'ground: {{above: <len>}}' to set the Z height "
            f"above grade. A mount must pin all six degrees of freedom; the "
            f"compiler never guesses the missing one.")


def _check_mirror(cid: str, mount: MountSpec) -> None:
    if not mount.mirror:
        return
    remaining = [a for a in MOUNT_AXES if a != mount.mirror and a not in mount.center]
    if len(remaining) != 1:
        raise SemanticError(
            f"mount of {cid!r}: mirror {mount.mirror!r} cannot be realised as a "
            f"single rigid rotation — the part must be centered on every "
            f"non-mirror axis but one, leaving exactly one rotation axis; "
            f"centered on {list(mount.center)} leaves {remaining}. Add the "
            f"missing axis to 'center'.")


def _check_cycles(mounts) -> None:
    """No mount chain may cycle (A registers against B, B against A). The graph
    is tiny; a depth-first walk naming the cycle is enough."""
    edges = {cid: mount.to for cid, mount in mounts}
    for start in edges:
        seen = [start]
        cur = edges[start]
        while cur in edges:
            if cur in seen:
                cycle = " -> ".join(seen[seen.index(cur):] + [cur])
                raise SemanticError(
                    f"mount relation cycle: {cycle}. A part cannot register "
                    f"against a part that (transitively) registers against it; "
                    f"break the cycle by grounding one part on a fixed target.")
            seen.append(cur)
            cur = edges[cur]
