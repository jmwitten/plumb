"""Unit probes for the installability axis checks (task INSTALL v1) — the
design's conceptual acceptance tests (installability-design.md §CATs, owner
amendment #5) built as SYNTHETIC minimal assemblies, so each verdict's
mechanism is exercised in isolation from any shipped spec.

The owner's success criterion: pocket screws, through-bolts, same-connection
obstruction and sequence-dependent access each receive DIFFERENT CORRECT
VERDICTS from the SAME general model. Every test here drives
``check_installability`` directly on a hand-built assembly + Connection, so
the geometry is exactly known and the pinned wording is verified against it.
"""

from __future__ import annotations

import pytest

from detailgen.core import IN
from detailgen.assemblies import (
    BoltedClamp, Connection, ConnectionType, DetailAssembly,
    compile_connections, connection_types,
)
from detailgen.assemblies.connection import Edge
from detailgen.assemblies.installation import (
    EntryFace, Exit, ToolAxis, straight_screw_group,
)
from detailgen.components import HexBolt, HexNut, Lumber, StructuralScrew, Washer
from detailgen.components.concrete import Boulder
from detailgen.validation.install import check_installability


def _run(assembly, *conns):
    checks = compile_connections(assembly, list(conns))
    return check_installability(assembly, list(conns), checks)


def _by_kind(findings, kind):
    return [f for f in findings if f.check == kind]


# -- CAT-A: pocket screw vs driven-straight — same joint, different verdicts --


def _cleat_joint(install=None):
    """The caddy's shape in miniature: a standing 2x4 'rail', a flat 2x4
    'top' on its end grain, one screw driven UP with its head mid-rail
    (40 mm above the rail's bottom free face, 48.9 mm below the interface)."""
    a = DetailAssembly("cat-a")
    rail = a.add(Lumber("2x4", 6 * IN, name="rail"))            # z 0..88.9
    top = a.add(Lumber("2x4", 6 * IN, name="top"), at=(0, 0, 88.9))
    screw = a.add(StructuralScrew(0.19 * IN, 2 * IN, name="up screw"),
                  at=(76.2, 19.05, 40.0), rotate=[("Y", 180)])  # shank +Z
    conn = Connection(kind=connection_types.get("cleat_screwed")(n_screws=1),
                      parts=[rail, top], hardware=[screw], label="cat-a joint",
                      install=install or {})
    return a, conn


def test_cat_a_driven_straight_fails_access_buried():
    """CAT-1's would-have-caught property, preserved inside the general
    model: under today's declaration (driven_straight, proud head) the
    buried head is an impossible joint — axis-2 FAIL."""
    a, conn = _cleat_joint()
    (acc,) = _by_kind(_run(a, conn), "install_access")
    assert acc.verdict == "FAIL"
    assert "entry face buried" in acc.detail
    assert "mid-plate" in acc.detail
    assert "rail" in acc.detail


def test_cat_a_pocket_head_reads_represented_never_bare_pass():
    """The SAME joint with a declared pocket head: the burial is judged as
    declared (no modeled void exists — vocabulary work order #1), the
    corridor sweeps from the recess mouth on the entry face, and the verdict
    wording is guardrail #6's, never a bare PASS."""
    a, conn = _cleat_joint(install={"": {"head": "recessed_in_pocket"}})
    (acc,) = _by_kind(_run(a, conn), "install_access")
    assert acc.passed
    assert "Installation method represented" in acc.detail
    assert "recess geometry not analyzed" in acc.detail
    assert "judged as declared, not geometry-proven" in acc.detail


def test_cat_a_angled_pocket_contract_is_represented_on_both_axes():
    """The full CAT-A contract (pocket_screw, angled idealized axis, entry
    on the rail's INNER face — the descriptor the caddy fix authors): axis 1
    does not measure the straight drawn solid (it is not the technique's
    path), axis 2 sweeps the DECLARED angle off the rail's cheek faces —
    both worded 'represented; <X> not analyzed', and the declared pocket
    head carries guardrail #6's exact acceptance wording (no modeled void
    exists — vocabulary work order #1)."""
    a, conn = _cleat_joint(install={"": {
        "method": "pocket_screw",
        "entry_face": EntryFace("lumber-0", "inner_face"),
        "tool_axis": ToolAxis("angled", angle_deg=15.0, axis_idealized=True),
        "head": "recessed_in_pocket",
    }})
    findings = _run(a, conn)
    (term,) = _by_kind(findings, "install_termination")
    assert term.passed
    assert "Installation method represented" in term.detail
    assert "angled shank path not analyzed" in term.detail
    assert "15° pocket_screw technique" in term.detail
    (acc,) = _by_kind(findings, "install_access")
    assert acc.passed
    assert "angled tool path not analyzed" in acc.detail
    assert "cheek face is clear of third-party material" in acc.detail
    assert "recess geometry not analyzed" in acc.detail
    assert "judged as declared, not geometry-proven" in acc.detail


# -- CAT-C: through-bolt — the exit is REQUIRED (the screw cases' inverse) ----


def _clamp_joint(bolt_len, install=None):
    """Two 2x4 plates stacked across their thicknesses (y 0..38.1 and
    38.1..76.2), one bolt driven +Y from the y=0 head-side face."""
    a = DetailAssembly("cat-c")
    p1 = a.add(Lumber("2x4", 4 * IN, name="head plate"))
    p2 = a.add(Lumber("2x4", 4 * IN, name="nut plate"), at=(0, 38.1, 0))
    bolt = a.add(HexBolt(0.375 * IN, bolt_len, name="clamp bolt"),
                 at=(50.0, 0.0, 44.0), rotate=[("X", 90)])   # shank +Y
    hw = a.add(Washer(0.4 * IN, name="head washer"), at=(50.0, -2.0, 44.0))
    nw = a.add(Washer(0.4 * IN, name="nut washer"), at=(50.0, 78.0, 44.0))
    nut = a.add(HexNut(0.375 * IN, name="clamp nut"), at=(50.0, 80.0, 44.0))
    conn = Connection(kind=BoltedClamp(axis="Y", hardware_area=1,
                                       end_plate_area=1),
                      parts=[p1, p2], hardware=[bolt, hw, nw, nut],
                      label="cat-c clamp", install=install or {})
    return a, conn


def test_cat_c_missing_through_exit_fails():
    a, conn = _clamp_joint(bolt_len=2.5 * IN)   # 63.5mm < the 76.2mm stack
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "FAIL"
    assert "REQUIRED through-exit absent" in term.detail
    assert "terminates inside nut plate" in term.detail


def test_cat_c_present_through_exit_passes_with_two_sided_access():
    a, conn = _clamp_joint(bolt_len=3.5 * IN)   # 88.9mm > 76.2mm — exits
    findings = _run(a, conn)
    (term,) = _by_kind(findings, "install_termination")
    assert term.verdict == "PASS"
    assert "REQUIRED through-exit is present" in term.detail
    (acc,) = _by_kind(findings, "install_access")
    assert acc.verdict == "PASS"
    assert "driver side (bolt head): clear" in acc.detail
    assert "wrench side (from the exit face, past the nut): clear" in acc.detail


def test_cat_c_inverse_verdict_derives_from_the_contract():
    """The direct proof global tip/head rules were the wrong shape: the SAME
    no-exit geometry under an exit=none contract PASSes — the verdict is the
    contract's, not a universal rule's."""
    a, conn = _clamp_joint(
        bolt_len=2.5 * IN,
        install={"": {"exit": Exit("none"), "embedment": None}})
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "PASS"
    assert "terminates inside nut plate" in term.detail
    assert "no undeclared exit" in term.detail


def test_cat_c_authored_exit_without_faces_is_honest_unknown():
    """The schema-mechanics review's trap: an authored through_exit_required
    whose Exit carries NO face-set replaces the type default's nut-side face
    — the required exit becomes uncheckable, and the honest verdict is a
    blocking UNKNOWN naming exactly what is missing (the spec loader
    additionally refuses to author this — see test_install_spec_surface)."""
    a, conn = _clamp_joint(
        bolt_len=3.5 * IN,
        install={"": {"exit": Exit("through_exit_required")}})
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "UNKNOWN" and term.blocking
    assert "declares NO far-side exit face" in term.detail
    assert "declare exit_faces" in term.detail


# -- CAT-E / CAT-F: corridor obstruction — party vs foreign vs sequenced ------


class _ScrewedPlate(ConnectionType):
    """Minimal test type: one screw group entering parts[0]'s free face.
    No edges — the same-connection blocker below is UNORDERED, i.e. present
    at the joint's own install step (the design's party ⇒ FAIL rule)."""

    label = "test_screwed_plate"

    def install_contract(self, conn):
        return (straight_screw_group(
            "screws", [p for p in conn.hardware], conn.parts[0].id),)


class _SequencedScrewedPlate(_ScrewedPlate):
    """Same type, but its edges DECLARE that the second part installs after
    the screws (the FaceMountHanger pattern: fasten first, drop the member
    in after)."""

    label = "test_sequenced_screwed_plate"

    def edges(self, conn):
        return [Edge(s.id, conn.parts[1].id, "installed_before", conn.label)
                for s in conn.hardware]


def _blocked_corridor(kind, blocker_in_connection):
    """A plate with one screw driven straight down into it (head on the top
    face at z=88.9), and a slab hovering over the head across the 6in driver
    corridor (z 120..150)."""
    a = DetailAssembly("cat-ef")
    plate = a.add(Lumber("2x4", 4 * IN, name="plate"))
    far = a.add(Lumber("2x4", 4 * IN, name="far member"), at=(500, 0, 0))
    blocker = a.add(Boulder(60, 60, 30, name="hovering slab"),
                    at=(50.0, 19.0, 150.0))                  # z 120..150
    screw = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="down screw"),
                  at=(50.0, 19.0, 88.9))                     # shank -Z
    parts = [plate, blocker] if blocker_in_connection else [plate, far]
    conn = Connection(kind=kind(), parts=parts, hardware=[screw],
                      label="cat-ef joint")
    return a, conn


def test_cat_e_same_connection_blocker_fails_naming_it():
    """F-7 re-pin (CAT-E lineage, deliberate): a same-connection MEMBER
    occupant keeps its FAIL — but as a DERIVED order fact now, never a
    party-presence assumption: structural necessity proves the member is
    present when its own connection's fastener is driven, and the proving
    edge prints with its provenance family."""
    a, conn = _blocked_corridor(_ScrewedPlate, blocker_in_connection=True)
    (acc,) = _by_kind(_run(a, conn), "install_access")
    assert acc.verdict == "FAIL"
    assert "blocked by hovering slab" in acc.detail
    assert "provably present when this fastener is driven" in acc.detail
    assert "structural_necessity" in acc.detail
    assert "must exist before its screws fasteners are driven" in acc.detail


def test_cat_e_foreign_blocker_is_named_unknown():
    """Re-pinned to the §4.1 wording: the CPG exists now, so the UNKNOWN
    names the occupant AND the missing order fact, and teaches the v1-core
    authoring surfaces that would resolve it (sequence: stage / technique
    edge) — staging only as an explicitly-future mechanism."""
    a, conn = _blocked_corridor(_ScrewedPlate, blocker_in_connection=False)
    (acc,) = _by_kind(_run(a, conn), "install_access")
    assert acc.verdict == "UNKNOWN" and acc.blocking
    assert "UNKNOWN — build order underdetermined" in acc.detail
    assert "hovering slab" in acc.detail
    assert "no order fact relates" in acc.detail
    assert "authored sequence: stage" in acc.detail
    assert "technique edge" in acc.detail
    assert "FUTURE mechanism, not authorable today" in acc.detail
    # the slab participates in no connection — the verdict says exactly
    # that, so the reader knows no derived fact can ever exist for it
    assert "participates in no connection" in acc.detail


def test_f1_authored_stage_cannot_flip_a_member_fail_to_declared_pass():
    """Review-cpgcore F-1's end-to-end construction, pinned on the exact
    CAT-E member-FAIL fixture: staging the joint before its own blocking
    MEMBER must never flip the derived presence FAIL to a declared-order
    PASS — the compile refuses with the merged cycle error naming the
    authored claim AND the structural-necessity claim. UNKNOWN→FAIL is
    CAT-I's falsifiability for hardware occupants; this is the member
    class's: authoring is tested by the checks, never a waiver channel."""
    from detailgen.assemblies.event_graph import (
        EventOrderCycleError, ResolvedStage)

    a, conn = _blocked_corridor(_ScrewedPlate, blocker_in_connection=True)
    stages = (
        ResolvedStage(name="screw first", why="wrongly authored",
                      connections=("cat-ef joint",)),
        ResolvedStage(name="slab later", why="silencing attempt",
                      parts=(conn.parts[1].id,)),
    )
    with pytest.raises(EventOrderCycleError) as err:
        compile_connections(a, [conn], sequence=stages)
    msg = str(err.value)
    assert "authored_sequence" in msg and "structural_necessity" in msg
    assert "hovering slab" in msg


class _TwoGroupPlate(ConnectionType):
    """F-7's live delta fixture: TWO role groups on one connection, no
    edges — the groups' drives are mutually unordered."""

    label = "test_two_group_plate"

    def install_contract(self, conn):
        return (
            straight_screw_group("grp_a", [conn.hardware[0]],
                                 conn.parts[0].id),
            straight_screw_group("grp_b", [conn.hardware[1]],
                                 conn.parts[0].id),
        )


def test_f7_delta_unordered_cross_group_hardware_is_named_unknown():
    """The deliberate F-7 party-rule delta, pinned: same-connection HARDWARE
    in a DIFFERENT role group with no order path either way was a FAIL
    under the old party-presence assumption; on the event graph it is an
    honest blocking UNKNOWN naming the occupant and the missing order fact
    — the old rule ASSUMED presence, the new one reports that the model
    does not know, and names the fix. (No shipped detail hits this — the
    hanger's two groups are ordered by its own technique edges, bolt
    stacks are one group — so this synthetic pin is the delta's whole
    regression surface.)"""
    a = DetailAssembly("cat-f7")
    plate = a.add(Lumber("2x4", 4 * IN, name="plate"))
    far = a.add(Lumber("2x4", 4 * IN, name="far member"), at=(500, 0, 0))
    # group A's screw: driven straight down, head on the top face
    screw_a = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="screw A"),
                    at=(50.0, 19.0, 88.9))                   # shank -Z
    # group B's screw hovers INSIDE screw A's 6in driver corridor
    screw_b = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="screw B"),
                    at=(50.0, 19.0, 160.0))
    conn = Connection(kind=_TwoGroupPlate(), parts=[plate, far],
                      hardware=[screw_a, screw_b], label="two-group joint")
    findings = [f for f in _by_kind(_run(a, conn), "install_access")
                if "screw A" in f.subject]
    (acc,) = findings
    assert acc.verdict == "UNKNOWN" and acc.blocking
    assert "UNKNOWN — build order underdetermined" in acc.detail
    assert "screw B" in acc.detail
    assert "no order fact relates" in acc.detail


def test_cat_f_v1_foreign_corridor_blocker_names_owner_connection():
    """CAT-F's v1 half: the blocker belongs to ANOTHER connection whose
    stage is unknowable — the UNKNOWN names both the blocker and its owning
    connection, so Phase 3 can resolve exactly this finding by mechanism."""
    a = DetailAssembly("cat-f")
    plate = a.add(Lumber("2x4", 4 * IN, name="plate"))
    far = a.add(Lumber("2x4", 4 * IN, name="far member"), at=(500, 0, 0))
    slab = a.add(Boulder(60, 60, 30, name="later slab"), at=(50.0, 19.0, 150.0))
    other = a.add(Lumber("2x4", 4 * IN, name="slab carrier"), at=(0, 0, 150.0))
    screw = a.add(StructuralScrew(0.19 * IN, 1.5 * IN, name="down screw"),
                  at=(50.0, 19.0, 88.9))
    conn = Connection(kind=_ScrewedPlate(), parts=[plate, far],
                      hardware=[screw], label="screwed joint")
    other_conn = Connection(kind=_ScrewedPlate(), parts=[slab, other],
                            hardware=[], label="slab joint")
    findings = _run(a, conn, other_conn)
    accs = [f for f in _by_kind(findings, "install_access")
            if f.subject.startswith("screwed joint")]
    (acc,) = accs
    assert acc.verdict == "UNKNOWN"
    assert "later slab (slab joint)" in acc.detail


def test_cat_e_party_ordered_after_the_fastener_is_disclosed_not_blocked():
    """When a DECLARED technique edge places the blocker after the fastener
    (the FaceMountHanger pattern), the corridor is honestly clear at the
    fastener's own install step — PASS with the deciding declaration and
    its provenance family printed inline (§4.3: geometry proven at the
    DECLARED build order), never a silent pass, never a false FAIL, never
    a SEQUENCE-PROVEN claim."""
    a, conn = _blocked_corridor(_SequencedScrewedPlate,
                                blocker_in_connection=True)
    (acc,) = _by_kind(_run(a, conn), "install_access")
    assert acc.verdict == "PASS"
    assert "provably arrive later" in acc.detail
    assert "hovering slab" in acc.detail
    assert "technique_default" in acc.detail   # the deciding family, on paper
    # HON-F3 qualified rung, generalized: never a bare GEOMETRY-PROVEN on a
    # declared-order premise — the exact §4.3 wording is pinned.
    assert "geometry proven at the DECLARED build order" in acc.detail
    assert "declared, not sequence-proven" in acc.detail
    assert "insertion travel is not analyzed" in acc.detail


# -- descriptor honesty --------------------------------------------------------


def test_unmappable_entry_descriptor_degrades_to_unknown_never_a_guess():
    # the rail is the assembly's first Lumber — its Placed.id is stable
    a, conn = _cleat_joint(install={"": {
        "entry_face": EntryFace("lumber-0", "mystery_face")}})
    findings = _run(a, conn)
    assert len(findings) == 2
    for f in findings:
        assert f.verdict == "UNKNOWN" and f.blocking
        assert "mystery_face" in f.detail
        assert "no geometric mapping" in f.detail
        assert "never guessed" in f.detail


# -- FIX-FIRST regression pins (review-install-axes-geometry / -honesty) ------
#
# Each test below reproduces a reviewer's confirmed counterexample verbatim
# (geometry review probes A/A2/B/C, the CAT-A knife-edge, honesty review F1)
# and pins the corrected verdict, so the masked-breach / unswept-nut-zone /
# unmatched-concealed-exit classes cannot silently return.


def _stacked_screw_joint(screw_len, extra=()):
    """A screw driven +Z from z=0 through plate A (z 0-38.1) into anchor B
    (z 38.1-76.2), plus caller-placed extra bodies. Boulder(top pad at Z=0,
    body down) placed at z = its top."""
    a = DetailAssembly("probe")
    plate = a.add(Boulder(80, 80, 38.1, name="head plate"), at=(0, 0, 38.1))
    anchor = a.add(Boulder(80, 80, 38.1, name="anchor block"), at=(0, 0, 76.2))
    extras = [a.add(comp, at=at) for comp, at in extra]
    screw = a.add(StructuralScrew(0.19 * IN, screw_len, name="probe screw"),
                  at=(0.0, 0.0, 0.0), rotate=[("Y", 180)])   # shank +Z
    conn = Connection(kind=connection_types.get("cleat_screwed")(n_screws=1),
                      parts=[plate, anchor], hardware=[screw],
                      label="probe joint")
    return a, conn, extras


def test_geo_probe_a_gap_jump_foreign_bite_is_an_undeclared_exit():
    """Geometry review Probe A: the shank breaches the anchor's far face,
    crosses a 5 mm air gap, and bites into a FOREIGN slab. The old deepest-
    chord rule credited the foreign bite and reported no exit; the
    membership + continuity walk FAILs the undeclared exit at the anchor's
    face and discloses the foreign material without crediting it."""
    # A 5.5in screw: through A (1.5in) + B (1.5in), breach, gap, into slab C.
    a, conn, (slab,) = _stacked_screw_joint(
        5.5 * IN,
        extra=[(Boulder(80, 80, 38.1, name="foreign slab"),
                (0, 0, 76.2 + 12.7 + 5.0 + 38.1))])   # C: z 81.2+12.7..bottom
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "FAIL"
    assert "undeclared exit" in term.detail
    assert "anchor block's +Z face" in term.detail
    assert "FOREIGN to this connection: foreign slab" in term.detail
    assert "never credited" in term.detail
    assert "bite into foreign slab" not in term.detail


def test_geo_probe_a2_authored_no_minimum_still_fails_the_exit():
    """Probe A2: with embedment=None authored the old rule read a clean
    'terminates inside foreign slab' PASS; the exit FAIL must stand on its
    own."""
    a, conn, _ = _stacked_screw_joint(
        5.5 * IN,
        extra=[(Boulder(80, 80, 38.1, name="foreign slab"),
                (0, 0, 76.2 + 12.7 + 5.0 + 38.1))])
    conn.install = {"": {"embedment": None}}
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "FAIL"
    assert "undeclared exit" in term.detail
    assert "terminates inside" not in term.detail


def test_geo_probe_b_parallel_stud_cannot_mask_an_open_air_breach():
    """Geometry review Probe B (the fully-silent flavor): the screw breaches
    the anchor's far face by 0.50in into OPEN AIR; a parallel stud 2.2 mm
    off the shank SURFACE (never touched) used to register a phantom chord
    under the oversized probe and the verdict read 'PASS terminates inside
    parallel stud' — every clause false, shipping CLEAN. The thin foreign
    probe + membership walk FAIL the breach and never name the stud as a
    terminator."""
    # screw 3.5in: tip z=88.9, anchor far face 76.2 -> 0.50" open-air breach.
    # stud near face 4.6mm off the axis (shank r 2.41 + 2.2mm air).
    a, conn, (stud,) = _stacked_screw_joint(
        3.5 * IN,
        extra=[(Boulder(30, 30, 100, name="parallel stud"),
                (4.6 + 15.0, 0, 120.0))])   # x 4.6..34.6, z 20..120
    findings = _run(a, conn)
    (term,) = _by_kind(findings, "install_termination")
    assert term.verdict == "FAIL"
    assert "undeclared exit" in term.detail
    assert "anchor block's +Z face" in term.detail
    assert "by 0.50\"" in term.detail
    assert "terminates inside" not in term.detail
    # the stud is genuinely 2.2mm clear of the shank surface: it is NOT
    # on-path material at the thin probe, so it is not even disclosed here.
    assert "parallel stud" not in term.detail


def test_geo_probe_c_nut_zone_obstruction_is_swept():
    """Geometry review Probe C: a foreign body wrapped around the nut's
    station — inside the [far face → tip] overshoot zone the old sweep
    started PAST — must obstruct the wrench side, not read 'clear'."""
    a = DetailAssembly("cat-c-nut-zone")
    p1 = a.add(Lumber("2x4", 4 * IN, name="head plate"))
    p2 = a.add(Lumber("2x4", 4 * IN, name="nut plate"), at=(0, 38.1, 0))
    bolt = a.add(HexBolt(0.375 * IN, 4 * IN, name="clamp bolt"),
                 at=(50.0, 0.0, 44.0), rotate=[("X", 90)])   # tip y=101.6
    hw = a.add(Washer(0.4 * IN, name="head washer"), at=(50.0, -2.0, 44.0))
    nw = a.add(Washer(0.4 * IN, name="nut washer"), at=(50.0, 78.0, 44.0))
    nut = a.add(HexNut(0.375 * IN, name="clamp nut"), at=(50.0, 80.0, 44.0))
    # foreign block radially 10-12mm off the bolt axis (x 60-62; nearest
    # surface 10mm out at the bolt's z), y 78.8-101.2 — the nut's
    # neighborhood, inside the 12.7mm corridor radius. Boulder signature is
    # (width->Y, length->X, depth->Z from the top pad down).
    blocker = a.add(Boulder(22.4, 2.0, 20, name="nut-hugging block"),
                    at=(50.0 + 10.0 + 1.0, 90.0, 44.0 + 10.0))
    conn = Connection(kind=BoltedClamp(axis="Y", hardware_area=1,
                                       end_plate_area=1),
                      parts=[p1, p2], hardware=[bolt, hw, nw, nut],
                      label="cat-c clamp")
    (acc,) = _by_kind(_run(a, conn), "install_access")
    assert acc.verdict == "UNKNOWN" and acc.blocking
    assert "nut-hugging block" in acc.detail
    assert "wrench side (from the exit face, past the nut): obstructed" \
        in acc.detail
    assert "driver side (bolt head): clear" in acc.detail


def test_cat_a_knife_edge_tip_at_interface_reads_zero_bite():
    """CAT-A verifier's knife-edge: a screw whose tip lands exactly ON the
    A/B interface must not credit A's whole thickness as 'bite' — the
    deepest-entered qualifying chord (the anchor) wins the tie and the
    honest ~zero bite FAILs the declared minimum."""
    a, conn, _ = _stacked_screw_joint(1.5 * IN)   # tip exactly at z=38.1
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "FAIL"
    assert "embedment below the declared minimum" in term.detail
    assert "0.00\" bite into anchor block" in term.detail
    # the knife-edge residual is display dust, never a signed measurement
    assert "-0.00" not in term.detail


def test_hon_concealed_exit_through_undeclared_member_fails():
    """Honesty review F1: a concealed_exit declaration discloses only the
    faces it NAMES — a breach through any other member is the silent
    show-face-breach class and must FAIL naming both the actual and the
    declared faces. The matched twin keeps its disclosed PASS."""
    a = DetailAssembly("concealed-probe")
    rail = a.add(Lumber("2x4", 6 * IN, name="rail"))            # z 0..88.9
    top = a.add(Lumber("2x4", 6 * IN, name="top"), at=(0, 0, 88.9))
    screw = a.add(StructuralScrew(0.19 * IN, 8 * IN, name="long screw"),
                  at=(76.2, 19.05, 0.0), rotate=[("Y", 180)])   # tip z=203.2
    mismatch = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=1),
        parts=[rail, top], hardware=[screw], label="probe joint",
        install={"": {"exit": Exit("concealed_exit",
                                   faces=(EntryFace(rail.id, "free_face"),))}})
    (term,) = _by_kind(_run(a, mismatch), "install_termination")
    assert term.verdict == "FAIL"
    assert "exit through an UNDECLARED member" in term.detail
    assert "top's +Z face" in term.detail
    assert "declared concealed faces are" in term.detail

    matched = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=1),
        parts=[rail, top], hardware=[screw], label="probe joint",
        # embedment authored to no-minimum so the twin isolates the exit
        # question (the honest half-length default would FAIL 3.5" < 4").
        install={"": {"exit": Exit("concealed_exit",
                                   faces=(EntryFace(top.id, "free_face"),)),
                      "embedment": None}})
    (term2,) = _by_kind(_run(a, matched), "install_termination")
    assert term2.passed
    assert "a DECLARED concealed exit" in term2.detail


def test_standoff_gap_cross_into_own_anchor_is_credited_with_disclosure():
    """The controller-caught false alarm (the tree-lag class, refining
    GEO-F1): a gap-cross into the connection's OWN anchor member is a
    legitimate standoff technique — the gap is a BEARING fact the bearing
    checks own, not a termination defect. Credited, with the gap length and
    destination DISCLOSED in the verdict. Membership stays absolute: the
    same geometry with the far body foreign (probe A) or absent (probe B)
    still FAILs — the breach test runs on the full member walk."""
    a = DetailAssembly("standoff")
    plate = a.add(Boulder(80, 80, 38.1, name="head plate"), at=(0, 0, 38.1))
    # OWN anchor member across a 5mm air gap: z 43.1..81.2
    anchor = a.add(Boulder(80, 80, 38.1, name="standoff anchor"),
                   at=(0, 0, 81.2))
    screw = a.add(StructuralScrew(0.19 * IN, 3.0 * IN, name="standoff screw"),
                  at=(0.0, 0.0, 0.0), rotate=[("Y", 180)])   # tip z=76.2
    conn = Connection(kind=connection_types.get("cleat_screwed")(n_screws=1),
                      parts=[plate, anchor], hardware=[screw],
                      label="standoff joint",
                      # no-minimum authored so the pin isolates the gap
                      # semantics (the half-length default would honestly
                      # FAIL the 1.30in bite < 1.50in and hide the point)
                      install={"": {"embedment": None}})
    (term,) = _by_kind(_run(a, conn), "install_termination")
    assert term.verdict == "PASS"
    assert "terminates inside standoff anchor" in term.detail
    assert "crosses a 0.20\" air gap before entering standoff anchor" \
        in term.detail
    assert "gap disclosed, own-member bite beyond it credited" in term.detail


def test_tree_lag_standoff_fixture_reads_the_honest_pass():
    """The CL3 tree-lag fixture verbatim (the controller's specimen): a
    free-standing beam deliberately stands 1.5in clear of its cleat — the
    pinned expected divergence is the BEARING fail; the lag's REQUIRED
    through-exit into the beam across that gap is geometrically real and
    must read PASS with the gap disclosed, never a new termination FAIL."""
    from detailgen.spec.compiler import compile_spec_file
    from pathlib import Path as _P

    fixture = (_P(__file__).resolve().parents[1] / "tests" / "fixtures"
               / "cl3" / "tree_lag.spec.yaml")
    d = compile_spec_file(fixture)
    rep = d.validate()
    terms = [f for f in rep.findings if f.check == "install_termination"]
    (term,) = terms
    assert term.verdict == "PASS"
    assert "exits beam +Y's far face by 0.62\"" in term.detail
    assert "REQUIRED through-exit is present" in term.detail
    assert "crosses a 1.50\" air gap before entering beam +Y" in term.detail
    assert "gap disclosed" in term.detail
