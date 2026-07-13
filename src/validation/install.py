"""Axis-1 (geometric termination) and axis-2 (static tool access) fastener
installability checks (task INSTALL v1, ``installability-design.md`` §Verdict
axes — owner amendment #2).

Every verdict here DERIVES from a fastener's resolved
:class:`~detailgen.assemblies.installation.FastenerInstallation` contract
(consumed from ``ConnectionChecks.installs`` — never re-resolved, never a
global geometric rule; owner amendment #1). The same checker gives the
design's flavors their DIFFERENT correct verdicts: a screw contract
(``exit: none``) FAILs an undeclared face exit that a through-bolt contract
(``through_exit_required``) REQUIRES; a buried entry face FAILs a
driven-straight screw while a declared pocket/countersunk head reads
REPRESENTED against the declared (unmodeled) void.

The epistemic ladder (owner guardrail #6) is enforced in wording:

- Results judged against MODELED geometry along the MODELED axis are
  GEOMETRY-PROVEN and say so.
- Results resting on declared-but-unmodeled conditions (an
  ``axis_idealized`` angled tool axis, an unmodeled pocket/countersink
  void) are REPRESENTED-rung, worded "represented; <X> not analyzed" —
  never a bare PASS.
- Corridor occupancy is judged on the merged Construction Process Graph
  (task CPGCORE, axis 3): an occupant provably present when the fastener is
  driven FAILs with the proving order facts + provenance on paper; an
  occupant provably later is a disclosed clear worded "geometry proven at
  the DECLARED build order" (never SEQUENCE-PROVEN — no derived order fact
  can place an occupant after a fastener, so every clear leans on at least
  one declared claim); an occupant with no order path either way is a
  blocking ``UNKNOWN — build order underdetermined`` naming the occupant
  AND the missing order fact, because neither PASS nor FAIL would be
  honest. Parts are assumed to accrete at their final pose, and insertion
  travel is not analyzed at any rung (P1) — both stated in the verdicts.

Mechanisms (all OCCT boolean probes, the ``check_through_hole`` idiom):

- **Axis 1 — termination.** A thin probe cylinder on the fastener's datum
  axis (``head_bearing``→``tip``; the drawn thread solid is a display
  exaggeration and is never measured) is intersected per-member with
  ``.vals()`` (multi-solid honesty); per-member chords along the axis give
  the entry-face station, the interface station, the tip's terminating
  member, the embedded bite, and any far-face breach. Judged against the
  CONTRACT's ``exit`` condition and ``embedment`` minimum only — nothing
  the contract does not declare is judged. The probe extends well behind
  the head (a buried head's entry face lies BEHIND it — the caddy class)
  and past the tip (a breach lies beyond it).
- **Axis 2 — static access.** The CONTRACT's tool envelope (always resolved;
  its used value prints in every verdict) is swept as a cylinder along the
  CONTRACT's tool axis from the entry face, against final geometry,
  per-part (never fused — the verdict names the blocker). A head stationed
  inside the entry member is the measured Phase-0 defect class: mid-plate =
  the caddy's impossible joint; at the far face = the stool's
  station-at-interface. ``through_bolt`` sweeps BOTH ends (driver side from
  the head, wrench side past the nut — the stack order names which end is
  which).

Angled (idealized) axes: the declared ``angle_deg`` off the entry face IS
the semantics; the drawn solid is straight. The sweep runs along the
DECLARED angle from each of the entry member's two cheek faces (the faces
across its thinnest dimension perpendicular to the drive axis — where a toe
or pocket screw physically enters). The joint's own member parts are what
the declared angle negotiates and are NOT judged along an idealized axis
(that is exactly the unmodeled portion — stated in the wording);
third-party material in the corridor IS judged, and an installer needs only
one workable cheek, so a single clear candidate is a (REPRESENTED-rung)
pass naming the face it used.

Deliberately NOT cached: the persistent verdict cache in ``checks.py`` is
salted with ``_CHECKS_FP``, which fingerprints ``checks.py`` +
``core/config.py`` only — it does not cover this module's source, so wiring
these findings into that cache would let an edit here serve stale verdicts.
v1 recomputes every time; joining the fingerprint is a later, deliberate
step.

Prefilter honesty: every (probe, part) pair is either AABB-prefiltered or
exactly intersected — ``skipped + checked == total`` is asserted per call,
the same accounting rule as the interference stage's audit trail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq

from ..assemblies.assembly import DetailAssembly, Placed
from ..assemblies.event_graph import PresenceFact
from ..assemblies.installation import ResolvedInstallation, is_fastener
from ..core.config import DEFAULT, Tolerances
from ..core.units import fmt_in
from .checks import Finding, UNKNOWN_VERDICT, _aabb_gap, _part_bbox, _AABB

#: Thin-probe radius (mm) for axis-1 shank-path chords against parts that
#: are NOT members of the fastener's connection. The connection's OWN
#: members get an oversized probe (shank radius + ``_HOLE_CLEARANCE``) so a
#: modeled clearance/epoxy bore's wall still registers as member material
#: (the ``check_through_hole`` "present" probe's lesson); everything else
#: gets this needle, because an oversized probe against foreign material
#: fabricates phantom chords from anything within a few mm of the shank
#: surface (geometry review F1b). Chord endpoint stations are read off the
#: intersection solids' bounding boxes projected onto the axis — exact for
#: the axis-aligned members every shipped detail drives into; a member
#: face tilted θ from axis-perpendicular carries an r·tan θ station error
#: (≈ r only for θ ≤ 45°; no shipped shank-mode fastener is tilted).
_PROBE_R = 0.5

#: How far past the shank radius the chord probe reaches (mm): enough to
#: register member material past a modeled clearance hole (bolt holes are
#: shank + 0.25 mm; the rock anchor's epoxy annulus is 1.6 mm).
_HOLE_CLEARANCE = 2.5

#: How far behind the head the axis-1 probe reaches (mm) to find the entry
#: member's tool-side face when the head is buried inside it — the deepest
#: shipped burial is 4in (the caddy); 12in covers any plausible member.
_BEHIND_SPAN = 305.0

#: Station-classification window (mm): a head/tip within this of a face
#: plane counts as AT that face. Authored stations land exactly on planes;
#: probe-projection noise is bounded by ``_PROBE_R``.
_FACE_TOL = 1.0

#: Embedment acceptance cushion (mm): measured bite may under-read by up to
#: a probe radius at each member face, so a declared minimum is enforced
#: with this much slack — an exactly-at-minimum bite passes; the shipped
#: shortfalls (3+ mm) still fail.
_EMBED_TOL = 1.0

#: Forward offset (mm) of a tool corridor's base along the sweep direction,
#: so the corridor's butt disc does not register a zero-thickness tangency
#: against the face plane it starts on.
_CORRIDOR_EPS = 0.5

#: Entry-face descriptors this checker can map to geometry, per tool-axis
#: mode. The descriptor set is OPEN (schema report): an unmappable
#: descriptor degrades to honest UNKNOWN, never a guess. For a shank axis
#: every mapped descriptor resolves the same way — the entry member's
#: tool-side face along the drive axis; the names differ only in the
#: construction role they record. For an angled axis the descriptor names
#: the cheek-face technique (`exposed_face`; `free_face` accepted for an
#: authored pocket variant on a straight-screw type; `inner_face` — the
#: concealed interior face an authored pocket contract enters, which IS
#: one of the two cheek candidates the angled sweep tries).
_MAPPABLE_SHANK_FACES = frozenset({"free_face", "hanger_face", "drilled_face"})
_MAPPABLE_ANGLED_FACES = frozenset({"exposed_face", "free_face", "inner_face"})

_GEOMETRY_PROVEN = "GEOMETRY-PROVEN against modeled geometry"


def _fmt(mm: float) -> str:
    # Clamp the negative side of a knife-edge zero so a ~-1e-9 bite prints
    # '0.00"', never the confusing '-0.00"' (display only; verdict math is
    # untouched).
    return fmt_in(0.0 if -0.005 * 25.4 < mm < 0.0 else mm)


def _axis_name(v: cq.Vector) -> str:
    """Human name for a direction: ``+X``/``-Y``/... when world-axis
    aligned, else the rounded components (never a guessed name)."""
    comps = (v.x, v.y, v.z)
    for i, ax in enumerate("XYZ"):
        if comps[i] > 0.99:
            return f"+{ax}"
        if comps[i] < -0.99:
            return f"-{ax}"
    return "(%.2f, %.2f, %.2f)" % comps


@dataclass(frozen=True)
class _Chord:
    """One part's material span along the shank axis: stations (mm,
    measured from the fastener head along the drive direction) of first
    entry and last exit."""

    part: Placed
    s_in: float
    s_out: float


class _Sweep:
    """Shared per-call geometry context: every part's world AABB computed
    once, plus the prefilter accounting (``skipped + checked == total``
    asserted at the end of the call — the interference stage's honesty
    rule)."""

    def __init__(self, assembly: DetailAssembly, tol: Tolerances):
        self.parts = list(assembly.parts)
        self.tol = tol
        self.boxes = {p.id: _part_bbox(p) for p in self.parts}
        self.pairs_total = 0
        self.pairs_prefiltered = 0
        self.pairs_checked = 0

    def _cyl_bbox(self, base: cq.Vector, direction: cq.Vector, radius: float,
                  length: float) -> _AABB:
        end = base + direction * length
        return _AABB(
            xmin=min(base.x, end.x) - radius, xmax=max(base.x, end.x) + radius,
            ymin=min(base.y, end.y) - radius, ymax=max(base.y, end.y) + radius,
            zmin=min(base.z, end.z) - radius, zmax=max(base.z, end.z) + radius,
        )

    def intersections(self, base: cq.Vector, direction: cq.Vector,
                      radius: float, length: float, skip_ids: set[str],
                      ) -> list[tuple[Placed, list]]:
        """Intersect a probe cylinder with every candidate part
        (AABB-prefiltered, accounted). Returns ``(part, solids)`` per part
        whose intersection volume clears ``tol.noise_volume``, in assembly
        (build) order — deterministic."""
        probe = cq.Solid.makeCylinder(radius, length, base, direction)
        pbox = self._cyl_bbox(base, direction, radius, length)
        threshold = self.tol.bbox_prefilter_gap
        out = []
        for p in self.parts:
            if p.id in skip_ids:
                continue
            self.pairs_total += 1
            if _aabb_gap(pbox, self.boxes[p.id]) > threshold:
                self.pairs_prefiltered += 1
                continue
            self.pairs_checked += 1
            inter = p.world_solid().intersect(probe)
            solids = inter.vals()
            vol = sum(s.Volume() for s in solids) if solids else 0.0
            if vol > self.tol.noise_volume:
                out.append((p, solids))
        return out

    def chords(self, head: cq.Vector, direction: cq.Vector, ahead: float,
               skip_ids: set[str], shank_radius: float,
               member_ids: set[str]) -> list[_Chord]:
        """Per-part material chords along the shank axis, stations relative
        to the head. The probe runs from ``_BEHIND_SPAN`` behind the head (a
        buried head's entry face lies behind it) to ``ahead`` past it.

        TWO probe radii, scoped by connection membership (geometry review
        F1b): the connection's OWN member parts get the OVERSIZED probe
        (``shank_radius + _HOLE_CLEARANCE``) so a modeled clearance/epoxy
        bore's wall still registers as the member's material — those are
        the only parts the fastener legitimately runs a hole through.
        Every OTHER part gets the thin ``_PROBE_R`` needle: an oversized
        probe against foreign material fabricates phantom chords from
        anything within ~2.5 mm of the shank surface (a parallel stud, a
        neighboring bore wall), which masked a real open-air breach as
        "terminates inside <foreign part>".

        Each hit part's stations are the projections of its intersection
        solids onto the axis (multi-solid honesty: a part the axis crosses
        twice yields its true overall span). Station error for a member
        face tilted θ from axis-perpendicular is r·tan θ — "≈ one probe
        radius" only for θ ≤ 45°; every shipped shank-mode fastener meets
        its members square-on (θ = 0, exact)."""
        base = head - direction * _BEHIND_SPAN
        length = _BEHIND_SPAN + ahead
        r_member = max(_PROBE_R, shank_radius + _HOLE_CLEARANCE)
        probe_member = cq.Solid.makeCylinder(r_member, length, base, direction)
        probe_thin = cq.Solid.makeCylinder(_PROBE_R, length, base, direction)
        pbox = self._cyl_bbox(base, direction, r_member, length)
        threshold = self.tol.bbox_prefilter_gap
        out = []
        for p in self.parts:
            if p.id in skip_ids or is_fastener(p):
                continue
            self.pairs_total += 1
            if _aabb_gap(pbox, self.boxes[p.id]) > threshold:
                self.pairs_prefiltered += 1
                continue
            self.pairs_checked += 1
            probe = probe_member if p.id in member_ids else probe_thin
            inter = p.world_solid().intersect(probe)
            solids = inter.vals()
            vol = sum(s.Volume() for s in solids) if solids else 0.0
            if vol <= self.tol.noise_volume:
                continue
            lo, hi = math.inf, -math.inf
            for s in solids:
                bb = s.BoundingBox()
                for cx in (bb.xmin, bb.xmax):
                    for cy in (bb.ymin, bb.ymax):
                        for cz in (bb.zmin, bb.zmax):
                            t = ((cx - head.x) * direction.x
                                 + (cy - head.y) * direction.y
                                 + (cz - head.z) * direction.z)
                            lo, hi = min(lo, t), max(hi, t)
            out.append(_Chord(p, lo, hi))
        out.sort(key=lambda c: c.s_in)
        return out

    def far_face_station(self, part: Placed, head: cq.Vector,
                         direction: cq.Vector) -> float:
        """The station (mm from the head along the drive direction) of the
        part's farthest extent — the true "far face" distance a verdict may
        print (geometry review F3: the chord probe is capped ~50 mm past
        the tip, so a chord's ``s_out`` saturates at the cap for a deep
        member and must never be printed as the face distance). Computed
        from the part's world AABB corners projected onto the axis — exact
        for the axis-aligned members every shipped detail drives into. For
        a ROTATED member the AABB projection sits OUTWARD of the true far
        face, so the reader-facing "N short of its far face" note would
        OVERSTATE the remaining margin — ANTI-conservative in presentation,
        the same named residual as the angled sweep's cheek planes (no
        rotated member ships)."""
        b = self.boxes[part.id]
        corners = [(x, y, z) for x in (b.xmin, b.xmax)
                   for y in (b.ymin, b.ymax) for z in (b.zmin, b.zmax)]
        return max((cx - head.x) * direction.x + (cy - head.y) * direction.y
                   + (cz - head.z) * direction.z for cx, cy, cz in corners)

    def assert_accounted(self) -> None:
        assert self.pairs_prefiltered + self.pairs_checked == self.pairs_total, (
            "install sweep prefilter accounting broken: "
            f"{self.pairs_prefiltered} skipped + {self.pairs_checked} checked "
            f"!= {self.pairs_total} total")


@dataclass(frozen=True)
class _Scope:
    """One resolved contract bound to its geometric scope: the fastener's
    connection's member parts vs full party set (member = ``conn.parts``;
    party additionally includes hardware), the same-connection stack union,
    the ONE merged event graph (task CPGCORE — the axis-3 order truth;
    the old own-connection ``installed_after`` closure is now a projection
    of this graph, so there is a single order truth, not two), the
    owner index for naming blockers, and the composed-site fragment map."""

    ri: ResolvedInstallation
    members: set[str]          # this connection's member-part ids
    party: set[str]            # members + this connection's hardware ids
    stack: set[str]            # the fastener's OWN role group's stack ids
    graph: object              # the merged EventGraph (one order truth)
    owners: dict               # part id -> sorted owning connection labels
    fragments: dict            # connection label -> site fragment id ({} standalone)


def _head_tip(placed: Placed) -> tuple[cq.Vector, cq.Vector]:
    """The fastener's head-end and tip-end datum origins in world
    coordinates. Headed fasteners carry ``head_bearing``/``tip``; a rod
    carries ``top``/``bottom`` (its head end is the exposed top its nut
    stack clamps, its "tip" the embedded bottom). A fastener component with
    neither pair is a loud teaching error (design §Verdict axes: head/tip
    identification comes from the component's own datums)."""
    datums = placed.component.datums
    if "head_bearing" in datums and "tip" in datums:
        return (cq.Vector(*placed.datum_world("head_bearing").origin),
                cq.Vector(*placed.datum_world("tip").origin))
    if "top" in datums and "bottom" in datums:
        return (cq.Vector(*placed.datum_world("top").origin),
                cq.Vector(*placed.datum_world("bottom").origin))
    raise ValueError(
        f"installability: fastener {placed.name!r} "
        f"({type(placed.component).__name__}) declares neither "
        f"head_bearing/tip nor top/bottom datums — the axis checks cannot "
        f"identify its head and tip; add the datums to the component")


def check_installability(assembly: DetailAssembly, connections: list,
                         checks, tol: Tolerances = DEFAULT) -> list[Finding]:
    """Run axis 1 + axis 2 over every resolved installation contract on
    ``checks`` (the aggregated :class:`ConnectionChecks` —
    ``checks.installs`` supplies the contracts, ``checks.edges`` each
    connection's own declared install order).

    Sees ALL connections at once: party-vs-foreign classification of a
    corridor blocker needs global membership (which connection, if any, a
    blocking part belongs to), which per-connection scope cannot supply.
    Findings are emitted in ``installs`` declaration order, per fastener in
    contract order, axis 1 then axis 2 — deterministic by construction.
    """
    installs: list[ResolvedInstallation] = checks.installs
    sweep = _Sweep(assembly, tol)
    by_id = {p.id: p for p in assembly.parts}
    members_of: dict[str, set[str]] = {}
    party_of: dict[str, set[str]] = {}
    owners: dict[str, list[str]] = {}
    for conn in connections:
        members_of[conn.label] = {p.id for p in conn.parts}
        ids = members_of[conn.label] | {p.id for p in conn.hardware}
        party_of[conn.label] = ids
        for pid in sorted(ids):
            owners.setdefault(pid, []).append(conn.label)
    graph = checks.event_graph
    if graph is None:
        # A hand-assembled ConnectionChecks (tests): build the same one
        # graph compile_connections would have — never a second order truth.
        from ..assemblies.event_graph import build_event_graph
        graph = build_event_graph(assembly, connections, checks.edges,
                                  checks.installs, checks.sequence,
                                  getattr(checks, "staging", None))

    findings: list[Finding] = []
    for ri in installs:
        # Stack exclusion is the fastener's OWN role group's stack only
        # (geometry review F6): a sibling role group's hardware is real
        # material this fastener can meet.
        scope = _Scope(ri=ri,
                       members=members_of.get(ri.connection, set()),
                       party=party_of.get(ri.connection, set()),
                       stack=set(ri.stack),
                       graph=graph,
                       owners=owners,
                       fragments=dict(getattr(checks, "fragments", {}) or {}))
        env = ri.contract.tool_envelope
        env_txt = env.describe() if env else "tool envelope not declared"
        for fid in ri.fasteners:
            f = by_id.get(fid)
            if f is None:
                # Declared-but-unplaced hardware already carries a blocking
                # connection_hardware FAIL; there is no geometry to judge.
                continue
            subject = f"{ri.connection}: {f.name}"
            findings.extend(
                _check_fastener(sweep, by_id, scope, f, subject, env_txt))
    sweep.assert_accounted()
    return findings


def _unknown_pair(subject: str, why: str, env_txt: str) -> list[Finding]:
    detail = f"UNKNOWN — not analyzable: {why}; {env_txt}"
    return [Finding(kind, subject, False, detail, verdict=UNKNOWN_VERDICT)
            for kind in ("install_termination", "install_access")]


def _check_fastener(sweep: _Sweep, by_id, scope: _Scope, f: Placed,
                    subject: str, env_txt: str) -> list[Finding]:
    c = scope.ri.contract

    missing = [name for name, val in (("entry_face", c.entry_face),
                                      ("tool_axis", c.tool_axis),
                                      ("exit", c.exit))
               if val is None]
    if missing:
        return _unknown_pair(
            subject,
            f"the contract declares no {', '.join(missing)} — author the "
            f"missing field(s) in the install: block",
            env_txt)

    mode = c.tool_axis.mode
    mappable = (_MAPPABLE_SHANK_FACES if mode == "shank"
                else _MAPPABLE_ANGLED_FACES)
    entry = by_id.get(c.entry_face.part)
    if entry is None:
        return _unknown_pair(
            subject,
            f"the declared entry member {c.entry_face.part!r} is not a part "
            f"of this assembly",
            env_txt)
    if c.entry_face.face not in mappable:
        return _unknown_pair(
            subject,
            f"entry-face descriptor {c.entry_face.face!r} has no geometric "
            f"mapping for a {mode!r} tool axis (mappable: "
            f"{', '.join(sorted(mappable))}); judged as declared only, "
            f"never guessed",
            env_txt)

    head, tip = _head_tip(f)
    shank_len = (tip - head).Length
    d = (tip - head) * (1.0 / shank_len)

    if mode == "angled":
        return [_termination_represented(subject, c, env_txt),
                _access_angled(sweep, scope, f, entry, head, d, subject,
                               env_txt)]

    skip = {f.id} | scope.stack
    shank_r = getattr(f.component, "diameter", 2 * _PROBE_R) / 2.0
    chords = sweep.chords(head, d, shank_len + max(2 * _FACE_TOL, 50.0), skip,
                          shank_r, scope.members)
    entry_chord = next((ch for ch in chords if ch.part.id == entry.id), None)
    return [
        _termination_shank(sweep, chords, scope, shank_len, head, d, subject,
                           env_txt),
        _access_shank(sweep, scope, f, entry, entry_chord, chords, head, tip,
                      d, shank_len, subject, env_txt),
    ]


# -- axis 1: geometric termination --------------------------------------------


def _describe_embedment(emb) -> str:
    if emb == "through":
        return "through"
    if emb is None:
        return "no declared minimum"
    return f"{_fmt(emb)} min bite"


def _termination_represented(subject: str, c, env_txt: str) -> Finding:
    """An idealized angled axis: the modeled solid's exit/embedment is the
    display simplification's, not the declared technique's — measuring it
    would judge the idealization. REPRESENTED rung, worded per guardrail
    #6; never a bare PASS."""
    return Finding(
        "install_termination", subject, True,
        f"Installation method represented; angled shank path not analyzed — "
        f"the drawn solid is a straight display idealization of the declared "
        f"{c.tool_axis.angle_deg:g}° {c.method} technique, so the modeled "
        f"exit/embedment is not the technique's (contract: "
        f"exit={c.exit.describe()}, "
        f"embedment={_describe_embedment(c.embedment)}); {env_txt}")


def _termination_shank(sweep, chords, scope: _Scope, shank_len, head, d,
                       subject, env_txt) -> Finding:
    c = scope.ri.contract
    # Material actually on the shank path: entered at/before the tip AND
    # not entirely behind the head (a part behind the head is
    # driver-corridor territory, axis 2's question). The boundary is
    # inclusive at the tip: a blind hole drilled exactly shank-deep puts
    # the terminating member's material AT the tip station (the rock
    # anchor's epoxy bore).
    on_path = [ch for ch in chords
               if ch.s_in < shank_len + _FACE_TOL and ch.s_out > _FACE_TOL]
    # MEMBERSHIP (geometry review F1): only the connection's own member
    # parts can terminate the shank, carry its bite, or host its exit —
    # material foreign to the connection on the path is disclosed, never
    # credited (a bite "into" a part the contract never named is not this
    # joint's embedment; a foreign chord past the tip must not mask a
    # breach). Party hardware on the path (a hanger flange the screw
    # passes) is co-installed by design — disclosed, not judged.
    members = [ch for ch in on_path if ch.part.id in scope.members]
    hardware = [ch for ch in on_path
                if ch.part.id in scope.party and ch.part.id not in scope.members]
    foreign = [ch for ch in on_path if ch.part.id not in scope.party]
    disclosures: list[str] = []
    if hardware:
        disclosures.append(
            "path passes this connection's hardware: "
            + ", ".join(ch.part.name for ch in hardware))
    if foreign:
        disclosures.append(
            "the shank path also meets material FOREIGN to this "
            "connection: "
            + ", ".join(ch.part.name for ch in foreign)
            + " — never credited as termination or bite (any real overlap "
              "is the interference sweep's finding)")
    disc_txt = ("; " + "; ".join(disclosures)) if disclosures else ""

    if not members:
        why = (f"the modeled shank path meets no MEMBER of this connection "
               f"(contract/geometry mismatch){disc_txt}")
        return Finding(
            "install_termination", subject, False,
            f"UNKNOWN — not analyzable: {why}; {env_txt}",
            verdict=UNKNOWN_VERDICT)

    # CONTINUITY (geometry review F1, refined after the tree-lag standoff
    # false alarm): walk the member chords in station order. MEMBERSHIP is
    # absolute — foreign material is never credited (probes A/B) — but a
    # gap-cross into the connection's OWN member is a legitimate technique
    # (a standoff lag's shank crosses the declared clearance before biting
    # its anchor; that gap is a BEARING fact the bearing checks own, not a
    # termination defect), so it is CREDITED with the gap DISCLOSED by
    # length and destination. The breach test still runs on the FULL walk:
    # a tip past the LAST own-member material — into open air (probe B) or
    # foreign material (probe A) — FAILs regardless of any gap crossed
    # before it. The walk is anchored at the CONTRACT's entry member when
    # it is on the path: an epoxy rod threads through its bracket's
    # modeled hole and stands proud in air BEFORE entering the drilled
    # base — member material ahead of the entry face is legitimate
    # pass-through (the through_holes check owns those holes), disclosed
    # and never treated as the termination span.
    members.sort(key=lambda ch: ch.s_in)
    entry_part_id = c.entry_face.part
    start = next((i for i, ch in enumerate(members)
                  if ch.part.id == entry_part_id), 0)
    pre_entry = members[:start]
    if pre_entry:
        disclosures.append(
            "path passes member material ahead of the entry face (modeled "
            "through-holes, not the termination span): "
            + ", ".join(ch.part.name for ch in pre_entry))
    walk = members[start:]
    span_end = walk[0].s_out
    end_owner = walk[0]
    for ch in walk[1:]:
        if ch.s_in > span_end + _FACE_TOL:
            disclosures.append(
                f"the shank crosses a {_fmt(ch.s_in - span_end)} air gap "
                f"before entering {ch.part.name} — a standoff joint's "
                f"clearance (a bearing fact, judged by the bearing checks); "
                f"gap disclosed, own-member bite beyond it credited")
        if ch.s_out > span_end:
            span_end, end_owner = ch.s_out, ch
    disc_txt = ("; " + "; ".join(disclosures)) if disclosures else ""

    contiguous = walk
    # Anchor = the contiguous member chord containing the tip. Tie-break at
    # an exact interface (CAT-A review): the DEEPEST-entered qualifying
    # chord wins, so a screw whose tip just kisses the next member reads an
    # honest ~zero bite into it instead of crediting the whole through
    # member's thickness as "embedment".
    tip_candidates = [ch for ch in contiguous
                      if ch.s_in - _FACE_TOL <= shank_len <= ch.s_out + _FACE_TOL]
    tip_member = (max(tip_candidates, key=lambda ch: ch.s_in)
                  if tip_candidates else None)
    breaches = shank_len > span_end + _FACE_TOL
    exit_point = head + d * span_end
    exit_face = (f"{end_owner.part.name}'s {_axis_name(d)} face at "
                 f"({_fmt(exit_point.x)}, {_fmt(exit_point.y)}, "
                 f"{_fmt(exit_point.z)})")

    def _short_of_far_face(ch: _Chord) -> str:
        # True face distance (geometry review F3): the chord probe is capped
        # ~50 mm past the tip, so a deep member's chord saturates at the cap
        # — print the part's real far extent instead.
        far = sweep.far_face_station(ch.part, head, d)
        return f"{_fmt(far - shank_len)} short of its far face"

    problems: list[str] = []
    notes: list[str] = []

    cond = c.exit.condition
    if cond == "none":
        if breaches:
            problems.append(
                f"undeclared exit: the shank breaches {exit_face} by "
                f"{_fmt(shank_len - span_end)} — the contract declares "
                f"exit=none")
        else:
            anchor_ch = tip_member or end_owner
            notes.append(f"terminates inside {anchor_ch.part.name} "
                         f"({_short_of_far_face(anchor_ch)}) — no "
                         f"undeclared exit")
    elif cond == "concealed_exit":
        declared_parts = {x.part for x in c.exit.faces}
        declared = ", ".join(x.describe() for x in c.exit.faces) or "(none)"
        if breaches and end_owner.part.id in declared_parts:
            notes.append(
                f"exits {exit_face} by {_fmt(shank_len - span_end)} — a "
                f"DECLARED concealed exit (declared faces: {declared}); a "
                f"disclosed design fact, not a defect")
        elif breaches:
            # Honesty review F1: a concealed_exit declaration is a
            # disclosure of the NAMED faces, never a waiver for every face
            # of every member — an exit anywhere else is exactly the silent
            # show-face-breach class this checker exists for.
            problems.append(
                f"exit through an UNDECLARED member: the shank breaches "
                f"{exit_face} by {_fmt(shank_len - span_end)}, but the "
                f"declared concealed faces are {declared} — a concealed-"
                f"exit declaration discloses only the faces it names")
        else:
            notes.append(
                f"terminates inside {(tip_member or end_owner).part.name}; "
                f"the declared concealed exit ({declared}) is unused")
    elif cond == "through_exit_required":
        declared_parts = {x.part for x in c.exit.faces}
        if not declared_parts:
            return Finding(
                "install_termination", subject, False,
                f"UNKNOWN — not analyzable: exit=through_exit_required but "
                f"the contract declares NO far-side exit face, so the "
                f"required exit is uncheckable as declared; declare "
                f"exit_faces (the nut side); {env_txt}",
                verdict=UNKNOWN_VERDICT)
        if not breaches:
            anchor_ch = tip_member or end_owner
            problems.append(
                f"REQUIRED through-exit absent: the shank terminates inside "
                f"{anchor_ch.part.name} ({_short_of_far_face(anchor_ch)}) — "
                f"a through fastener must exit the declared far side to "
                f"take its nut")
        elif end_owner.part.id not in declared_parts:
            names = ", ".join(
                sorted(x.describe() for x in c.exit.faces))
            problems.append(
                f"through-exit through the WRONG member: the shank breaches "
                f"{exit_face}, but the contract requires the exit at {names}")
        else:
            notes.append(
                f"exits {end_owner.part.name}'s far face by "
                f"{_fmt(shank_len - span_end)} — the REQUIRED "
                f"through-exit is present on the declared nut side")
    else:
        return Finding(
            "install_termination", subject, False,
            f"UNKNOWN — not analyzable: unknown exit condition {cond!r}; "
            f"{env_txt}", verdict=UNKNOWN_VERDICT)

    emb = c.embedment
    if emb is None:
        notes.append("no declared embedment minimum — bite judged only as "
                     "declared (none)")
    elif emb == "through":
        notes.append("embedment=through — judged by the through-exit rule")
    else:
        anchor = tip_member or end_owner
        bite = min(shank_len, anchor.s_out) - max(0.0, anchor.s_in)
        src = scope.ri.provenance_map.get("embedment", "?")
        if bite + _EMBED_TOL < emb:
            problems.append(
                f"embedment below the declared minimum: {_fmt(bite)} bite "
                f"into {anchor.part.name} < {_fmt(emb)} minimum [{src}]")
        else:
            notes.append(f"{_fmt(bite)} bite into {anchor.part.name} >= "
                         f"{_fmt(emb)} declared minimum [{src}]")

    if problems:
        return Finding("install_termination", subject, False,
                       "; ".join(problems) + disc_txt
                       + f" ({_GEOMETRY_PROVEN}); {env_txt}")
    return Finding("install_termination", subject, True,
                   "; ".join(notes) + disc_txt
                   + f" ({_GEOMETRY_PROVEN}); {env_txt}")


# -- axis 2: static tool access ------------------------------------------------


def _owner_note(pid: str, scope: _Scope) -> str:
    labels = scope.owners.get(pid)
    return f" ({'; '.join(labels)})" if labels else ""


def _classify(hits, scope: _Scope, fastener_id: str):
    """Corridor hits judged on the ONE merged event graph (task CPGCORE,
    design §4.1 — the same hit sets axis 2 measured, RECLASSIFIED against
    the partial order; assembly order preserved). Under the stated
    accretion assumption (parts accrete at their final relative pose) the
    partial assembly at any step is a subset of final-pose solids, so this
    reclassification is exact, not an approximation:

    - ``present`` — the occupant's governing event provably precedes (or
      is) this fastener's drive event: it IS there when the fastener is
      driven ⇒ FAIL, with the proving order facts and their provenance
      families on paper. A same-connection MEMBER keeps its old party-rule
      FAIL this way (structural necessity proves it present) — but as a
      derived FACT now, never an assumption.
    - ``later`` — the fastener's drive event provably precedes the
      occupant's: disclosed, not blocked. Every such path necessarily
      includes at least one DECLARED order fact (no derived family points
      out of a drive event — design §4.3/F-8), so the clear is worded
      "geometry proven at the DECLARED build order", never sequence-proven.
      NEVER declare an order fact (type edge, sequence: stage) to silence
      a blocker: a declared order is a construction-sequence CLAIM its
      author must defend, and every use prints in the verdict sentence.
    - ``absent`` — an authored bench frame excludes the occupant without
      inventing cross-unit order.  Connection-free context absence carries
      the stronger DECLARED TRUST ceiling; ordinary opposite-unit membership
      is still a declared-order clear but not declared trust.
    - ``unordered`` — no order path either way (including every context
      body that participates in no connection): honest blocking
      ``UNKNOWN — build order underdetermined`` naming the occupant AND the
      missing order fact. This includes same-connection hardware in a
      different, unordered role group — the deliberate F-7 party-rule
      delta: the old rule ASSUMED co-presence; the graph reports that the
      model does not know, and names the fix."""
    graph = scope.graph
    e_f = graph.event_of[fastener_id]
    present: list = []   # (part, proof-path/presence facts)
    later: list = []     # (part, proof-path edges)
    absent: list = []    # (part, presence facts, declared-trust bool)
    unordered: list = []
    for p, _s in hits:
        decision = graph.presence_at(e_f, p.id)
        if decision.state == "coincident":
            # co-installed at this very event — same-group material is
            # already skipped; anything mapping here is co-driven in free
            # order, disclosed by the sibling/stack notes, never a blocker.
            continue
        if decision.state == "present":
            present.append((p, decision.facts))
        elif decision.state == "absent":
            if any(isinstance(fact, PresenceFact)
                   for fact in decision.facts):
                absent.append((p, decision.facts,
                               decision.declared_trust))
            else:
                later.append((p, decision.facts))
        else:
            unordered.append(p)
    return present, later, absent, unordered


def _order_facts(items, graph) -> tuple[str, str]:
    """``(occupant summary, deciding order facts)`` for a list of
    ``(part, proof-path edges)`` pairs: every occupant named with its own
    governing event, every deciding edge printed ONCE with its provenance
    family and source claim (several occupants often share one deciding
    declaration — the platform's four bolt-stack occupants share the one
    authored stage — and repeating a multi-sentence why per occupant would
    bury the verdict)."""
    occ = ", ".join(
        f"{p.name} (at {graph.describe(graph.event_of[p.id])})"
        for p, _path in items)
    claims: list[str] = []
    for _p, path in items:
        for e in path:
            desc = f"[{e.family}] {e.source}"
            if desc not in claims:
                claims.append(desc)
    return occ, "; ".join(claims)


def _later_note(later, scope: _Scope) -> str:
    """The disclosed-clear note (§4.1's second bullet), generalized from
    the old own-connection wording to the global graph: each occupant's
    later arrival is proved by named order facts, each stamped with its
    provenance family and source claim."""
    if not later:
        return ""
    occ, claims = _order_facts(later, scope.graph)
    return (f"; occupants of the corridor in final geometry provably "
            f"arrive later: {occ} — deciding order facts: {claims} "
            f"(declared, not sequence-proven)")


def _frame_absence_note(absent) -> str:
    """Disclose a clear decided by authored frame-presence semantics.

    This is deliberately separate from ``_later_note``: another unit or a
    context body is absent from the bench frame; the graph does not claim it
    merely arrives later in some invented total order.
    """
    if not absent:
        return ""
    occupants = ", ".join(p.name for p, _facts, _trust in absent)
    claims: list[str] = []
    for _part, facts, _trust in absent:
        for fact in facts:
            desc = f"[{fact.family}] {fact.source}"
            if desc not in claims:
                claims.append(desc)
    return (f"; occupants of the corridor in final geometry are absent from "
            f"bench frame: {occupants} — deciding presence facts: "
            f"{'; '.join(claims)} (declared, not sequence-proven)")


#: The §4.3 rung sentence every axis-3 clear that leans on a declared order
#: carries: geometry is proven, the order is DECLARED — v1 claims
#: SEQUENCE-PROVEN nowhere — and the accretion assumption + the
#: insertability gap (P1) are stated in the verdict, not a footnote.
_DECLARED_ORDER_RUNG = (
    " (geometry proven at the DECLARED build order — the order facts above "
    "are declared claims with their provenance printed, not "
    "sequence-proven; parts are assumed to accrete at their final pose, "
    "and insertion travel is not analyzed at any rung (P1))")


def _unordered_clauses(parts, scope: _Scope) -> str:
    """The teaching tail of an underdetermined verdict: name the missing
    order fact and the authoring surfaces that EXIST in v1-core (an
    authored ``sequence:`` stage; a ConnectionType technique edge) — a
    staging declaration is an authorable frame/presence mechanism. Adds the
    composed-site cross-fragment gap and the epoxy-rod insertion gap where
    they are the true missing mechanisms."""
    graph = scope.graph
    e_f = graph.event_of[scope.ri.fasteners[0]] if scope.ri.fasteners else None
    f_desc = graph.describe(e_f) if e_f is not None else "this fastener"
    clauses = []
    own_frag = scope.fragments.get(scope.ri.connection, "")
    cross_frags = set()
    no_conn = []
    for p in parts:
        owning = scope.owners.get(p.id, [])
        if not owning:
            no_conn.append(p.name)
        elif scope.fragments:
            frags = {scope.fragments.get(lbl, "") for lbl in owning}
            if own_frag not in frags:
                cross_frags |= {f for f in frags if f}
    clauses.append(
        f"no order fact relates {f_desc} to the occupants' own events — an "
        f"authored sequence: stage ordering them, or a ConnectionType "
        f"technique edge, would resolve it; an authorable staging declaration "
        f"can instead establish the honest bench frame/presence context")
    if no_conn:
        clauses.append(
            f"{', '.join(no_conn)} participates in no connection, so no "
            f"order fact can be derived for it — only an authored order or "
            f"staging declaration can resolve it")
    if cross_frags:
        clauses.append(
            f"the occupants belong to another site fragment "
            f"({', '.join(sorted(cross_frags))}) and this fastener to "
            f"{own_frag or 'its own fragment'!r} — no site-level "
            f"cross-fragment sequencing exists in v1 (a CPG v2 site graph "
            f"would order them)")
    if scope.ri.contract.method == "epoxy_set":
        clauses.append(
            "this epoxy-set rod's corridor is its own body's insertion "
            "path — insertion travel is not analyzed at any rung (P1)")
    return "; ".join(clauses)


def _blocked_finding(subject, present, unordered, scope: _Scope, prefix,
                     env_txt, rung_note="") -> Finding:
    graph = scope.graph
    if present:
        names = ", ".join(p.name + _owner_note(p.id, scope)
                          for p, _path in present)
        _occ, facts = _order_facts(present, graph)
        extra = ""
        if unordered:
            extra = ("; additionally obstructed by "
                     + ", ".join(p.name + _owner_note(p.id, scope)
                                 for p in unordered)
                     + ", whose order against this fastener is "
                       "underdetermined")
        return Finding(
            "install_access", subject, False,
            f"{prefix}tool corridor blocked by {names} — provably present "
            f"when this fastener is driven (order facts: {facts}){extra}"
            f"{rung_note}; {env_txt}")
    names = ", ".join(p.name + _owner_note(p.id, scope) for p in unordered)
    return Finding(
        "install_access", subject, False,
        f"UNKNOWN — build order underdetermined: {prefix}the tool corridor "
        f"is obstructed by {names}; "
        f"{_unordered_clauses(unordered, scope)}{rung_note}; {env_txt}",
        verdict=UNKNOWN_VERDICT)


def _access_shank(sweep, scope: _Scope, f, entry, entry_chord, chords,
                  head, tip, d, shank_len, subject, env_txt) -> Finding:
    c = scope.ri.contract
    env = c.tool_envelope

    # Head-station classification against the entry member's chord — the
    # measured Phase-0 class. Station 0 = the head-bearing plane; the entry
    # member's tool-side face is its chord's first station.
    represented_note = ""
    base = head
    if entry_chord is not None and entry_chord.s_in + _FACE_TOL < 0.0:
        depth = -entry_chord.s_in
        if c.head in ("recessed_in_pocket", "flush_countersunk"):
            # A declared recess/countersink is an unmodeled void (vocabulary
            # work order #1): the burial is judged as declared, and the
            # corridor sweeps from the recess mouth on the entry face.
            represented_note = (
                f" Installation method represented; recess geometry not "
                f"analyzed — head condition {c.head!r} is declared but no "
                f"modeled void exists, so the head's {_fmt(depth)} station "
                f"inside {entry.name} is judged as declared, not "
                f"geometry-proven.")
            base = head + d * entry_chord.s_in  # the recess mouth
        elif entry_chord.s_out > -_FACE_TOL and entry_chord.s_out < _FACE_TOL:
            return Finding(
                "install_access", subject, False,
                f"head stationed AT the joint interface, not on the free "
                f"face: the head-bearing plane sits {_fmt(depth)} past "
                f"{entry.name}'s free face — exactly at its far-face joint "
                f"plane (station-not-face: the fastener is modeled "
                f"unbuildable even though its length and bite are right; "
                f"the head station belongs on the free face) "
                f"({_GEOMETRY_PROVEN}); {env_txt}")
        else:
            return Finding(
                "install_access", subject, False,
                f"entry face buried: the head-bearing plane is stationed "
                f"{_fmt(depth)} inside {entry.name} from its free face "
                f"(mid-plate, {_fmt(entry_chord.s_out)} short of its far "
                f"face) — no driver reaches a head inside solid material; "
                f"an impossible joint as declared ({_GEOMETRY_PROVEN}); "
                f"{env_txt}")

    # Same-role-group siblings are co-driven at the same step in free order
    # and are not corridor BLOCKERS of each other (four hanger screws on a
    # manufacturer schedule sit closer than a crude 1in driver cylinder) —
    # but a sibling bodily inside the corridor is DISCLOSED (geometry review
    # F6/CAT-E: never a silently unconditional exclusion). Stack exclusion
    # is the fastener's OWN role group's stack only.
    siblings = set(scope.ri.fasteners) - {f.id}
    skip = {f.id} | scope.stack | siblings
    radius = env.dia / 2.0
    sides = [("", base, d * -1.0)]
    if c.exit.condition == "through_exit_required":
        # Wrench-side sweep starts at the DECLARED exit face's station, not
        # the bolt tip (geometry review F2): the [far face → tip] overshoot
        # zone is exactly where the nut lives — an obstruction wrapped
        # around a protruding bolt end must not read "clear". The own-stack
        # skip keeps the nut/washers themselves from self-blocking.
        member_outs = [ch.s_out for ch in chords
                       if ch.part.id in scope.members
                       and ch.s_in < shank_len + _FACE_TOL
                       and ch.s_out > _FACE_TOL]
        exit_station = min(max(member_outs), shank_len) if member_outs \
            else shank_len
        wrench_base = head + d * exit_station
        sides = [("driver side (bolt head): ", base, d * -1.0),
                 ("wrench side (from the exit face, past the nut): ",
                  wrench_base, d)]

    side_notes: list[str] = []
    later_all: list = []
    later_seen: set[str] = set()
    absent_all: list = []
    absent_seen: set[str] = set()
    sibling_hits: list = []
    worst: Finding | None = None
    for prefix, s_base, s_dir in sides:
        hits = sweep.intersections(s_base + s_dir * _CORRIDOR_EPS, s_dir,
                                   radius, env.length, skip)
        present, later, absent, unordered = _classify(hits, scope, f.id)
        for p, path in later:
            if p.id not in later_seen:
                later_seen.add(p.id)
                later_all.append((p, path))
        for p, facts, trust in absent:
            if p.id not in absent_seen:
                absent_seen.add(p.id)
                absent_all.append((p, facts, trust))
        if siblings:
            for p, _s in sweep.intersections(
                    s_base + s_dir * _CORRIDOR_EPS, s_dir, radius,
                    env.length, set(sweep.boxes) - siblings):
                if p not in sibling_hits:
                    sibling_hits.append(p)
        if present or unordered:
            fnd = _blocked_finding(subject, present, unordered, scope,
                                   prefix, env_txt)
            if worst is None or (worst.verdict == UNKNOWN_VERDICT
                                 and fnd.verdict == "FAIL"):
                worst = fnd
            side_notes.append(prefix + "obstructed")
        else:
            side_notes.append((prefix or "corridor: ") + "clear")
    sibling_note = ""
    if sibling_hits:
        sibling_note = (
            f" Same-group sibling fastener(s) "
            f"{', '.join(p.name for p in sibling_hits)} intersect the "
            f"corridor — co-driven at this group's own step in free order, "
            f"disclosed, not counted as blockers.")
    if worst is not None:
        if len(sides) > 1:
            worst.detail += " [" + "; ".join(side_notes) + "]"
        worst.detail += _later_note(later_all, scope)
        worst.detail += _frame_absence_note(absent_all)
        if represented_note or sibling_note:
            worst.detail += "." + sibling_note + represented_note
        return worst
    # A clearance that leans on DECLARED order facts is not a bare geometry
    # proof (§4.3): geometry is proven AT the declared build order — the
    # deciding declarations print with the later-arrival facts above, and
    # v1 claims SEQUENCE-PROVEN nowhere.
    if represented_note:
        rung = ""
    elif later_all or absent_all:
        rung = _DECLARED_ORDER_RUNG
    else:
        rung = f" ({_GEOMETRY_PROVEN})"
    return Finding(
        "install_access", subject, True,
        f"clear tool corridor along the shank axis "
        f"({'; '.join(side_notes)}){_later_note(later_all, scope)}"
        f"{_frame_absence_note(absent_all)}{rung}."
        f"{sibling_note}{represented_note} {env_txt}",
        # amendment 3, structured (review F-2): this clear leans on
        # declared order facts iff any occupant's later arrival decided it
        declared_order=bool(later_all or absent_all),
        declared_trust=any(trust for _p, _facts, trust in absent_all))


def _cheek_candidates(entry: Placed, d: cq.Vector,
                      ) -> list[tuple[cq.Vector, float]]:
    """The entry member's two cheek-face normals for an angled technique:
    the ± world directions of the part's thinnest local extent usefully
    perpendicular to the drive axis (a toe/pocket screw enters the wide
    face across the thin dimension, crossing it quickly into the seat).
    Returns ``[(outward normal, world face-plane offset along it), ...]``
    — empty when no local axis is usefully perpendicular (degenerate;
    caller degrades to UNKNOWN). Face-plane offsets come from the part's
    world AABB projected onto the normal: exact for the axis-aligned
    members every shipped detail uses. For a ROTATED member the AABB plane
    sits OUTWARD of the true cheek face, so the corridor base starts too
    far out and a blocker hugging the true face can be under-swept —
    ANTI-conservative for blocker detection (geometry review F5), a named
    residual until a rotated angled-entry member ships (none does; the
    result is REPRESENTED-rung either way). Only the thinnest
    perpendicular pair is offered: a member whose only open toe face is
    the WIDE pair reads a false block/UNKNOWN — conservative, disclosed
    here rather than guessed."""
    frame = entry.world_frame
    vals = entry.component.solid.vals()
    lo = [min(s.BoundingBox().xmin for s in vals),
          min(s.BoundingBox().ymin for s in vals),
          min(s.BoundingBox().zmin for s in vals)]
    hi = [max(s.BoundingBox().xmax for s in vals),
          max(s.BoundingBox().ymax for s in vals),
          max(s.BoundingBox().zmax for s in vals)]
    locals_ = [(hi[i] - lo[i],
                ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))[i])
               for i in range(3)]
    perp = []
    for extent, axis in locals_:
        w = cq.Vector(*frame.transform_direction(axis))
        if abs(w.dot(d)) < 0.5:
            perp.append((extent, w))
    if not perp:
        return []
    perp.sort(key=lambda e: e[0])
    _extent, n = perp[0]
    wb = _part_bbox(entry)
    corners = [(x, y, z) for x in (wb.xmin, wb.xmax)
               for y in (wb.ymin, wb.ymax) for z in (wb.zmin, wb.zmax)]
    projections = [n.x * cx + n.y * cy + n.z * cz for cx, cy, cz in corners]
    return [(n, max(projections)), (n * -1.0, -min(projections))]


def _access_angled(sweep, scope: _Scope, f, entry, head, d, subject,
                   env_txt) -> Finding:
    c = scope.ri.contract
    env = c.tool_envelope
    theta = math.radians(c.tool_axis.angle_deg)
    member_names = ", ".join(
        p.name for p in sweep.parts if p.id in scope.members)
    rung_note = (
        f"; represented axis — the declared {c.tool_axis.angle_deg:g}° "
        f"angle is not modeled by the drawn solid, and the joint's own "
        f"members ({member_names}) are negotiated by the declared "
        f"technique, not analyzed")
    if c.head in ("recessed_in_pocket", "flush_countersunk"):
        # The declared recess/countersink is an unmodeled void (vocabulary
        # work order #1) — guardrail #6's CAT-A acceptance wording, same as
        # the shank path's declared-head case: the head condition is judged
        # as declared, never geometry-proven.
        rung_note += (
            f". Installation method represented; recess geometry not "
            f"analyzed — head condition {c.head!r} is declared but no "
            f"modeled void exists (judged as declared, not geometry-proven)")
    candidates = _cheek_candidates(entry, d)
    if not candidates:
        return Finding(
            "install_access", subject, False,
            f"UNKNOWN — not analyzable: {entry.name} has no local axis "
            f"usefully perpendicular to the drive axis, so no cheek face "
            f"anchors the declared {c.tool_axis.angle_deg:g}° corridor"
            f"{rung_note}; {env_txt}",
            verdict=UNKNOWN_VERDICT)

    skip = ({f.id} | scope.stack | scope.members
            | (set(scope.ri.fasteners) - {f.id}))
    radius = env.dia / 2.0
    all_present: list = []
    present_seen: set[str] = set()
    all_unordered: list[Placed] = []
    tried: list[str] = []
    for n, plane in candidates:
        face_name = f"{_axis_name(n)} cheek face"
        h_proj = head.x * n.x + head.y * n.y + head.z * n.z
        entry_pt = head + n * (plane - h_proj)
        t_dir = (n * math.sin(theta)) - (d * math.cos(theta))
        hits = sweep.intersections(entry_pt + t_dir * _CORRIDOR_EPS, t_dir,
                                   radius, env.length, skip)
        present, later, absent, unordered = _classify(hits, scope, f.id)
        if not present and not unordered:
            # One workable cheek is a pass — REPRESENTED rung (the angle is
            # declared, not modeled). A clear that leans on later-arrival
            # order facts says so and stays a DECLARED-order claim (§4.3):
            # the deciding declarations print inline, never sequence-proven,
            # and insertion travel stays un-analyzed (P1).
            later_note = _later_note(later, scope)
            absent_note = _frame_absence_note(absent)
            order_note = ""
            if later or absent:
                order_note = (
                    " — clear at the DECLARED build order only: the "
                    "deciding order facts above are declared claims (a "
                    "declared build strategy, not derived and not "
                    "sequence-proven), parts are assumed to accrete at "
                    "their final pose, and insertion travel is not "
                    "analyzed at any rung (P1)")
            return Finding(
                "install_access", subject, True,
                f"Installation method represented; angled tool path not "
                f"analyzed against the drawn solid — the declared "
                f"{c.tool_axis.angle_deg:g}° corridor off {entry.name}'s "
                f"{face_name} is clear of third-party material"
                f"{later_note}{absent_note}{order_note}{rung_note}; "
                f"{env_txt}",
                declared_order=bool(later or absent),
                declared_trust=any(
                    trust for _p, _facts, trust in absent))
        tried.append(face_name)
        for p, path in present:
            if p.id not in present_seen:
                present_seen.add(p.id)
                all_present.append((p, path))
        all_unordered.extend(p for p in unordered if p not in all_unordered)
    prefix = (f"every declared {c.tool_axis.angle_deg:g}° corridor "
              f"candidate (off {entry.name}'s {' and '.join(tried)}) is "
              f"obstructed: ")
    return _blocked_finding(subject, all_present, all_unordered, scope,
                            prefix, env_txt, rung_note=rung_note)


# -- per-detail doc disclosure (owner guardrail #7's doc half) -----------------


#: Framing sentences of the epistemic-contract table (owner amendment 2) —
#: shared verbatim by the markdown and HTML renderings so the two per-detail
#: surfaces cannot drift.
EPISTEMIC_TABLE_TITLE = "Epistemic contract — where each order fact comes from"
EPISTEMIC_TABLE_LEDE = (
    "Axis-3 verdicts judge tool corridors against the merged Construction "
    "Process Graph under the stated assumption that parts accrete at their "
    "final pose. Every order fact belongs to one of these families:")
EPISTEMIC_TABLE_CODA = (
    "A clear that rests on a DECLARED order fact reads \"geometry proven "
    "at the DECLARED build order\" — resolved on paper, never proved: no "
    "verdict in this document claims a sequence-proven rung.")
EPISTEMIC_TABLE_HEADER = ("Order-fact family", "Standing", "Source")


def epistemic_contract_rows(checks) -> list[tuple[str, str, str]]:
    """The epistemic-contract table's rows (STEPDOC owner amendment 2):
    which order-fact families the axis-3 verdicts stand on are DERIVED,
    which are DECLARED (with the detail's actual authored stages + whys on
    paper), and which remain UNKNOWN — auditable at a glance. Static
    content plus this detail's own declared stages; nothing hand-typed per
    detail. One source for both reader surfaces."""
    stages = tuple(getattr(checks, "sequence", ()) or ())
    if stages:
        declared_seq = "; ".join(
            f"stage {st.name!r} (why: {st.why})" for st in stages)
        declared_seq = f"this detail authors: {declared_seq}"
    else:
        declared_seq = "none authored by this detail"
    staging = getattr(checks, "staging", None)
    if staging is None:
        declared_staging = "none authored by this detail"
    elif staging.mode == "in_situ":
        declared_staging = (
            f"this detail authors assembly mode 'in_situ' "
            f"(why: {staging.why})")
    else:
        units = "; ".join(
            f"unit {u.name!r} (why: {u.why})" for u in staging.units)
        trust = (
            "; connection-free context exclusion carries DECLARED TRUST "
            "until insertability is analyzed (P1)"
            if staging.context_parts else "")
        declared_staging = (
            f"this detail authors assembly mode {staging.mode!r}: "
            f"{units}{trust}")
    return [
        ("Structural necessity (a member exists before its own "
         "connection's fasteners are driven)",
         "DERIVED",
         "derived from connection membership; points only INTO a drive "
         "event, so no derived fact ever clears a corridor"),
        ("Technique defaults (a ConnectionType's own installed_before "
         "edges, lifted to events)",
         "DECLARED (type-level construction knowledge, defended in the "
         "type's docstring)",
         "each edge prints with its owning connection"),
        ("Authored sequence: stages",
         "DECLARED (authored claim; a why is required and prints with "
         "every verdict that leans on it)",
         declared_seq),
        ("Bench events before join (R-1)",
         "DERIVED",
         "all place/drive events inside a declared bench unit precede that "
         "unit's join event; no order is invented between separate units"),
        ("Authored staging frames",
         "DECLARED (frame/presence claim; every unit or assembly requires a "
         "why; connection-free context absence is DECLARED TRUST)",
         declared_staging),
        ("Undeclared context bodies, cross-fragment order, insertion travel",
         "UNKNOWN — undeclared context/site order has no mechanism in this "
         "increment; insertability remains P1",
         "verdicts that meet these gaps stay blocking UNKNOWNs and name the "
         "missing declaration or analysis"),
    ]


def _epistemic_contract_table(checks) -> list[str]:
    """The markdown rendering of the epistemic-contract table."""
    lines = [f"### {EPISTEMIC_TABLE_TITLE}", "", EPISTEMIC_TABLE_LEDE, "",
             "| " + " | ".join(EPISTEMIC_TABLE_HEADER) + " |",
             "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |"
              for a, b, c in epistemic_contract_rows(checks)]
    lines += ["", EPISTEMIC_TABLE_CODA, ""]
    return lines


def render_install_disclosures_md(detail) -> str:
    """The per-detail reader surface for the installation contracts and the
    axis verdicts (honesty review F2): every resolved contract's one-line
    ``describe()`` — each field WITH its provenance source — plus its
    assumption notes, and every NON-passing installability finding's full
    verdict text (which carries the measured numbers, the ``[assumption]``
    embedment provenance, and the used tool-envelope value). Deterministic:
    contracts in declaration order, findings in report order. Returns ""
    for a detail with no installation contracts — the coverage matrix's
    ``UNKNOWN — NOT ANALYZED`` row is that detail's whole truth."""
    checks = getattr(detail, "_connection_checks", None)
    installs = checks.installs if checks is not None else []
    if not installs:
        return ""
    lines = ["## Fastener installation — contracts and axis verdicts", ""]
    lines.append(
        "Every fastener's installation method is DECLARED by a resolved "
        "contract (each field stamped with its provenance — a reviewer can "
        "see which values are assumption-grade) and judged by the axis "
        "checks below it. A represented method is a declared claim, not "
        "proof the fastener can be driven.")
    lines.append("")
    lines.extend(_epistemic_contract_table(checks))
    lines.append("### Resolved contracts")
    for ri in installs:
        lines.append(f"- {ri.describe()}")
        for note in ri.notes:
            lines.append(f"  - assumption: {note}")
    open_findings = [f for f in detail.report.findings
                     if f.check in ("install_method", "install_termination",
                                    "install_access") and not f.passed]
    lines.append("")
    if open_findings:
        lines.append("### Open installability verdicts (blocking)")
        for f in open_findings:
            lines.append(f"- **[{f.verdict}]** `{f.check}` {f.subject} — "
                         f"{f.detail}")
    else:
        lines.append("### Open installability verdicts")
        lines.append("- none — every axis check on every contracted "
                     "fastener passed (see the coverage matrix row for the "
                     "family verdict and its rung).")
    lines.append("")
    return "\n".join(lines)
