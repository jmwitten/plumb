"""Tests for the FastenerInstallation contract resolution (task INSTALL v1,
schema branch).

Covers: the type-default contracts of all 8 registered ConnectionTypes (each
honest to its own docstring), authored-override-wins-per-field with correct
per-field provenance (owner guardrail #7), the role-group targeting rules,
the blocking ``UNKNOWN — NO INSTALLATION METHOD REPRESENTED`` finding for
fastener-class hardware whose contract does not resolve (owner amendment #4),
and the determinism of the derived facts.

Deliberately geometry-free: Connections operate on ``Placed`` handles, and
``generate_checks`` builds no solids — so these tests construct tiny
assemblies directly (the ``test_connection.py`` pattern) instead of
compiling specs.
"""

import pytest

from detailgen.core import IN
from detailgen.components import (
    Epoxy, HexBolt, HexNut, JoistHanger, Lumber, PostBase, StructuralScrew,
    ThreadedRod, Washer,
)
from detailgen.components.concrete import Boulder, PierBlock
from detailgen.assemblies import (
    BoltedClamp, Connection, ConnectionType, DetailAssembly, FaceMountHanger,
    RailCapScrewed, ThreadedRodEpoxyAnchor, ToeScrewed, compile_connections,
    connection_types,
)
from detailgen.assemblies.installation import (
    DEFAULT_TOOL_ENVELOPE, EntryFace, PROVENANCE_ASSUMPTION,
    PROVENANCE_AUTHORED, PROVENANCE_TYPE_DEFAULT, TOE_SCREW_ANGLE_DEG,
    CONTRACT_FIELDS, is_fastener,
)
from detailgen.validation.checks import UNKNOWN_VERDICT


# -- fixtures -----------------------------------------------------------------


def _screws(a, n, length=1.5 * IN):
    return [a.add(StructuralScrew(0.25 * IN, length, name=f"screw {i}"),
                  at=(i * IN, 0, 30)) for i in range(n)]


@pytest.fixture()
def screwed_joint():
    """A generic two-member + two-screws assembly reused by every screwed
    type (the derivations don't read the placement)."""
    a = DetailAssembly("screwed joint")
    m1 = a.add(Lumber("2x4", 8 * IN, name="member one"))
    m2 = a.add(Lumber("2x6", 12 * IN, name="member two"), at=(0, 0, 40))
    screws = _screws(a, 2)
    return a, m1, m2, screws


def _install_of(conn, a):
    checks = conn.generate_checks(a)
    return checks, checks.installs


def _prov(resolved):
    return dict(resolved.provenance)


# -- per-type defaults (all 8 registered types) -------------------------------


def test_cleat_screwed_default(screwed_joint):
    a, cleat, member, screws = screwed_joint
    conn = Connection(kind=connection_types.get("cleat_screwed")(n_screws=2),
                      parts=[cleat, member], hardware=screws, label="cleat jt")
    checks, installs = _install_of(conn, a)
    (r,) = installs
    c = r.contract
    assert r.role == "cleat_screws"
    assert c.method == "driven_straight"
    # entry on the THROUGH member's (the cleat's) free face
    assert c.entry_face == EntryFace(cleat.id, "free_face")
    assert c.tool_axis.mode == "shank" and not c.tool_axis.axis_idealized
    assert c.exit.condition == "none"
    assert c.embedment == pytest.approx(0.75 * IN)  # half the 1.5in screw
    assert c.head == "seated"
    assert c.tool_envelope == DEFAULT_TOOL_ENVELOPE
    assert c.stage == "own_connection"
    assert r.fasteners == tuple(s.id for s in screws)
    # per-field provenance: everything type default except the half-length
    # embedment rule, which is assumption-grade (guardrail #7)
    assert r.assumption_fields == ("embedment",)
    assert _prov(r)["method"] == PROVENANCE_TYPE_DEFAULT
    assert not [f for f in checks.findings if f.check == "install_method"]


def test_butt_screwed_default(screwed_joint):
    a, face_member, butting, screws = screwed_joint
    conn = Connection(kind=connection_types.get("butt_screwed")(n_screws=2),
                      parts=[face_member, butting], hardware=screws)
    _checks, (r,) = _install_of(conn, a)
    # entry on the FACE member's free face (parts[0])
    assert r.contract.entry_face.part == face_member.id
    assert r.role == "butt_screws"
    assert r.contract.method == "driven_straight"


def test_rail_cap_screwed_default(screwed_joint):
    a, support, cap, screws = screwed_joint
    conn = Connection(kind=RailCapScrewed(n_screws=2),
                      parts=[support, cap], hardware=screws)
    _checks, (r,) = _install_of(conn, a)
    # entry on the CAP's free face — the cap is parts[1] for this type
    assert r.contract.entry_face.part == cap.id
    assert r.role == "cap_screws"


def test_toe_screwed_default_is_angled_and_idealized(screwed_joint):
    a, header, hung, screws = screwed_joint
    conn = Connection(kind=ToeScrewed(n_screws=2),
                      parts=[header, hung], hardware=screws)
    _checks, (r,) = _install_of(conn, a)
    c = r.contract
    assert c.method == "toe_screw"
    # the angled semantics off the EXPOSED HUNG-member face, with the drawn-
    # straight display idealization flagged ON the contract (amendment #3)
    assert c.entry_face == EntryFace(hung.id, "exposed_face")
    assert c.tool_axis.mode == "angled"
    assert c.tool_axis.angle_deg == TOE_SCREW_ANGLE_DEG
    assert c.tool_axis.axis_idealized
    # the angle is an assumed technique value, and the embedment the
    # half-length rule — BOTH visible as assumption-grade fields
    assert r.assumption_fields == ("tool_axis", "embedment")
    assert "idealization" in " ".join(r.notes)


def test_bolted_clamp_default_is_two_sided_through_bolt():
    a = DetailAssembly("clamp")
    p1 = a.add(Lumber("2x4", 8 * IN, name="plate head side"))
    p2 = a.add(Lumber("2x4", 8 * IN, name="plate nut side"), at=(0, 0, 40))
    bolt = a.add(HexBolt(0.5 * IN, 5 * IN, name="bolt"))
    w1 = a.add(Washer(0.5 * IN, name="head washer"))
    w2 = a.add(Washer(0.5 * IN, name="nut washer"))
    nut = a.add(HexNut(0.5 * IN, name="nut"))
    conn = Connection(kind=BoltedClamp("Z", 100.0, 400.0),
                      parts=[p1, p2], hardware=[bolt, w1, w2, nut])
    _checks, (r,) = _install_of(conn, a)
    c = r.contract
    assert c.method == "through_bolt"
    assert c.embedment == "through"
    assert c.head == "nut_and_washer"
    # BOTH sides checkable from the contract: entry = head side (plates[0]),
    # required exit = nut side (plates[-1]) — the stack order names the ends
    assert c.entry_face == EntryFace(p1.id, "free_face")
    assert c.exit.condition == "through_exit_required"
    assert c.exit.faces == (EntryFace(p2.id, "free_face"),)
    # one contract for the whole stack: the bolt is the driven fastener,
    # washers + nut ride as stack — never separate contracts
    assert r.fasteners == (bolt.id,)
    assert r.stack == (w1.id, w2.id, nut.id)
    assert r.assumption_fields == ()


def test_threaded_rod_epoxy_anchor_default_is_epoxy_set():
    a = DetailAssembly("anchor")
    base = a.add(Boulder(500, 500, 400, name="boulder"))
    bracket = a.add(Lumber("2x4", 8 * IN, name="bracket"), at=(0, 0, 410))
    target = a.add(Lumber("4x4", 20 * IN, name="leg"), at=(100, 0, 400))
    epoxy = a.add(Epoxy(0.75 * IN, 0.625 * IN, 8 * IN, name="epoxy"))
    rod = a.add(ThreadedRod(0.625 * IN, 14 * IN, name="rod"))
    lev = a.add(HexNut(0.625 * IN, name="leveling nut"))
    lo = a.add(Washer(0.625 * IN, name="lower washer"))
    up = a.add(Washer(0.625 * IN, name="upper washer"))
    lock = a.add(HexNut(0.625 * IN, name="lock nut"))
    jam = a.add(HexNut(0.625 * IN, name="jam nut"))
    conn = Connection(
        kind=ThreadedRodEpoxyAnchor("Z", 100.0, 200.0, "X", 300.0),
        parts=[base, bracket, target],
        hardware=[epoxy, rod, lev, lo, up, lock, jam])
    _checks, (r,) = _install_of(conn, a)
    c = r.contract
    # an epoxy-set rod is NOT "driven" — the open tag represents what is true
    assert c.method == "epoxy_set"
    assert c.entry_face == EntryFace(base.id, "drilled_face")
    assert c.exit.condition == "none"
    assert c.head == "nut_and_washer"
    # no type-level embedment minimum — honest None, provenance assumption
    assert c.embedment is None
    assert r.assumption_fields == ("embedment",)
    assert r.fasteners == (rod.id,)
    assert set(r.stack) == {epoxy.id, lev.id, lo.id, up.id, lock.id, jam.id}


def test_standoff_post_base_declares_empty_not_none():
    a = DetailAssembly("foundation")
    post = a.add(Lumber("4x4", 20 * IN, name="post"))
    block = a.add(PierBlock(200, 200, 150, name="block"))
    pb = a.add(PostBase(3.5 * IN, name="post base"))
    kind = connection_types.get("standoff_post_base")()
    conn = Connection(kind=kind, parts=[post, block], hardware=[pb])
    # the explicit () — no fastener-class hardware by the type's own
    # semantics (field fasteners live on the post base's BOM line) —
    # distinct from the base None ("cannot represent")
    assert kind.install_contract(conn) == ()
    checks, installs = _install_of(conn, a)
    assert installs == []
    assert not is_fastener(pb)
    assert not [f for f in checks.findings if f.check == "install_method"]


def test_face_mount_hanger_two_role_groups():
    a = DetailAssembly("hanger joint")
    header = a.add(Lumber("2x8", 30 * IN, name="beam"))
    hung = a.add(Lumber("2x6", 20 * IN, name="joist"), at=(0, 100, 0))
    hanger = a.add(JoistHanger(1.5 * IN, 5.5 * IN, name="hanger"))
    hs = _screws(a, 2)
    js = [a.add(StructuralScrew(0.25 * IN, 1.5 * IN, name=f"joist screw {i}"),
                at=(i * IN, 50, 30)) for i in range(2)]
    conn = Connection(kind=FaceMountHanger("Z", 500.0, 2, 2),
                      parts=[header, hung], hardware=[hanger, *hs, *js])
    _checks, installs = _install_of(conn, a)
    by_role = {r.role: r for r in installs}
    assert set(by_role) == {"header_screws", "hung_screws"}
    hdr, hng = by_role["header_screws"], by_role["hung_screws"]
    assert hdr.contract.entry_face == EntryFace(header.id, "hanger_face")
    assert hng.contract.entry_face == EntryFace(hung.id, "hanger_face")
    assert hdr.fasteners == tuple(s.id for s in hs)
    assert hng.fasteners == tuple(s.id for s in js)
    # the hanger is connector hardware, never a contract of its own — it
    # rides BOTH groups' stacks (each screw group drives through one of its
    # flanges; the axes' own-role-group stack scoping needs each group to
    # name the connector its fasteners pass)
    assert hdr.stack == (hanger.id,)
    assert hng.stack == (hanger.id,)


# -- authored overrides: per-field wins + provenance --------------------------


def test_authored_override_wins_per_field_and_stamps_provenance(screwed_joint):
    a, cleat, member, screws = screwed_joint
    conn = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=2),
        parts=[cleat, member], hardware=screws,
        install={"": {"method": "pocket_screw", "head": "recessed_in_pocket"}})
    _checks, (r,) = _install_of(conn, a)
    pm = _prov(r)
    assert r.contract.method == "pocket_screw"
    assert r.contract.head == "recessed_in_pocket"
    assert pm["method"] == PROVENANCE_AUTHORED
    assert pm["head"] == PROVENANCE_AUTHORED
    # un-overridden fields keep the DEFAULT value and its default provenance,
    # including the assumption stamp on the half-length embedment
    assert r.contract.entry_face == EntryFace(cleat.id, "free_face")
    assert pm["entry_face"] == PROVENANCE_TYPE_DEFAULT
    assert pm["embedment"] == PROVENANCE_ASSUMPTION
    # the derivation-log fact carries every field WITH its source
    fact = [d for d in _checks.derived
            if d.rule.endswith(".install_contract")][0]
    assert "method=pocket_screw [authored_override]" in fact.fact
    assert "[connectiontype_default]" in fact.fact
    assert fact.subjects == tuple(s.id for s in screws)
    # mixed authored/default contract is a derivation, not a verbatim
    # authored fact (the override-identity pattern, transposed per field)
    assert fact.confidence == "inferred"
    assert fact.source_type == "verified_heuristic"


def test_authored_embedment_drops_the_stale_half_length_note(screwed_joint):
    """A note explaining an overridden field's DEFAULT must not survive the
    override: 'embedment default = half the under-head length' beside
    ``embedment=... [authored_override]`` would be an honest-looking lie
    (the caddy fix arc's authored minimums surfaced this). The authored WHY
    belongs in the connection's own assumptions. Notes for un-overridden
    fields stay."""
    a, cleat, member, screws = screwed_joint
    conn = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=2),
        parts=[cleat, member], hardware=screws,
        install={"": {"embedment": 12.7}})
    _checks, (r,) = _install_of(conn, a)
    assert _prov(r)["embedment"] == PROVENANCE_AUTHORED
    assert not any("embedment default" in n for n in r.notes)
    # the un-overridden twin keeps the default's explanatory note
    plain = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=2),
        parts=[cleat, member], hardware=screws)
    _c2, (r2,) = _install_of(plain, a)
    assert any("embedment default" in n for n in r2.notes)


def test_fully_authored_contract_is_official_authoritative(screwed_joint):
    from detailgen.assemblies.installation import (
        Exit, ToolAxis, ToolEnvelope)
    a, cleat, member, screws = screwed_joint
    overrides = {
        "method": "pocket_screw",
        "entry_face": EntryFace(cleat.id, "inner_face"),
        "tool_axis": ToolAxis("angled", 15.0, axis_idealized=True),
        "exit": Exit("none"),
        "embedment": 20.0,
        "head": "recessed_in_pocket",
        "tool_envelope": ToolEnvelope(100.0, 20.0),
        "stage": "own_connection",
    }
    assert set(overrides) == set(CONTRACT_FIELDS)
    conn = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=2),
        parts=[cleat, member], hardware=screws, install={"": overrides})
    checks, (r,) = _install_of(conn, a)
    assert r.assumption_fields == ()
    assert all(src == PROVENANCE_AUTHORED for _f, src in r.provenance)
    fact = [d for d in checks.derived
            if d.rule.endswith(".install_contract")][0]
    assert fact.confidence == "official"
    assert fact.source_type == "authoritative"


def test_role_targeted_override_beats_blanket_override():
    a = DetailAssembly("hanger joint")
    header = a.add(Lumber("2x8", 30 * IN, name="beam"))
    hung = a.add(Lumber("2x6", 20 * IN, name="joist"), at=(0, 100, 0))
    hanger = a.add(JoistHanger(1.5 * IN, 5.5 * IN, name="hanger"))
    hs = _screws(a, 2)
    js = [a.add(StructuralScrew(0.25 * IN, 1.5 * IN, name=f"js {i}"),
                at=(i * IN, 50, 30)) for i in range(2)]
    conn = Connection(
        kind=FaceMountHanger("Z", 500.0, 2, 2),
        parts=[header, hung], hardware=[hanger, *hs, *js],
        install={"": {"embedment": 10.0},
                 "hung_screws": {"embedment": 25.0}})
    _checks, installs = _install_of(conn, a)
    by_role = {r.role: r for r in installs}
    assert by_role["header_screws"].contract.embedment == 10.0
    assert by_role["hung_screws"].contract.embedment == 25.0
    for r in installs:
        assert _prov(r)["embedment"] == PROVENANCE_AUTHORED


def test_unknown_role_group_is_a_teaching_error(screwed_joint):
    a, cleat, member, screws = screwed_joint
    conn = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=2),
        parts=[cleat, member], hardware=screws,
        install={"cleet_screws": {"embedment": 10.0}})
    with pytest.raises(ValueError, match="cleat_screws"):
        conn.generate_checks(a)


def test_unknown_contract_field_is_a_teaching_error(screwed_joint):
    a, cleat, member, screws = screwed_joint
    conn = Connection(
        kind=connection_types.get("cleat_screwed")(n_screws=2),
        parts=[cleat, member], hardware=screws,
        install={"": {"embedmint": 10.0}})
    with pytest.raises(ValueError, match="embedmint"):
        conn.generate_checks(a)


# -- the core invariant: unresolvable contract => blocking UNKNOWN ------------


class _NoContractType(ConnectionType):
    """A synthetic type that keeps the BASE install_contract (None) — the
    'cannot represent an installation method' case."""
    label = "no_contract"


def test_fastener_without_resolvable_contract_is_blocking_unknown(screwed_joint):
    a, m1, m2, screws = screwed_joint
    conn = Connection(kind=_NoContractType(), parts=[m1, m2],
                      hardware=screws, label="mystery joint")
    checks = conn.generate_checks(a)
    assert checks.installs == []
    (f,) = [f for f in checks.findings if f.check == "install_method"]
    assert f.verdict == UNKNOWN_VERDICT
    assert f.blocking and not f.passed
    assert "NO INSTALLATION METHOD REPRESENTED" in f.detail
    assert f.subject.startswith("mystery joint:")
    assert "screw 0" in f.subject and "screw 1" in f.subject
    # cross-branch contract (sdd/install-family, merged): the kind is mapped
    # into the ninth coverage family, so this blocking UNKNOWN surfaces as a
    # Fastener installability row — never an UnmappedCheckKind crash.
    from detailgen.validation.coverage import KIND_TO_FAMILY
    assert KIND_TO_FAMILY["install_method"] == "Fastener installability"


def test_non_fastener_hardware_never_demands_a_contract(screwed_joint):
    a, m1, m2, _screws_unused = screwed_joint
    nut = a.add(HexNut(0.5 * IN, name="lone nut"))
    conn = Connection(kind=_NoContractType(), parts=[m1, m2], hardware=[nut])
    checks = conn.generate_checks(a)
    assert not [f for f in checks.findings if f.check == "install_method"]


def test_authored_only_contract_resolves_a_defaultless_type(screwed_joint):
    a, m1, m2, screws = screwed_joint
    conn = Connection(
        kind=_NoContractType(), parts=[m1, m2], hardware=screws,
        install={"": {"method": "captive"}})
    checks = conn.generate_checks(a)
    (r,) = checks.installs
    assert r.role == "authored"
    assert r.contract.method == "captive"
    assert r.fasteners == tuple(s.id for s in screws)
    pm = _prov(r)
    assert pm["method"] == PROVENANCE_AUTHORED
    # every un-authored field: honest not-declared content, assumption-grade
    assert pm["entry_face"] == PROVENANCE_ASSUMPTION
    assert r.contract.entry_face is None
    # tool envelope still resolves (printable used-value in every verdict)
    assert r.contract.tool_envelope == DEFAULT_TOOL_ENVELOPE
    assert not [f for f in checks.findings if f.check == "install_method"]


def test_authored_override_without_method_stays_unknown(screwed_joint):
    a, m1, m2, screws = screwed_joint
    conn = Connection(
        kind=_NoContractType(), parts=[m1, m2], hardware=screws,
        install={"": {"embedment": 10.0}})
    checks = conn.generate_checks(a)
    assert checks.installs == []
    (f,) = [f for f in checks.findings if f.check == "install_method"]
    assert f.verdict == UNKNOWN_VERDICT


def test_role_key_on_defaultless_type_is_a_teaching_error(screwed_joint):
    a, m1, m2, screws = screwed_joint
    conn = Connection(
        kind=_NoContractType(), parts=[m1, m2], hardware=screws,
        install={"somewhere": {"method": "captive"}})
    with pytest.raises(ValueError, match="no default contract"):
        conn.generate_checks(a)


# -- aggregation + determinism -------------------------------------------------


def test_compile_connections_aggregates_installs(screwed_joint):
    a, cleat, member, screws = screwed_joint
    c1 = Connection(kind=connection_types.get("cleat_screwed")(n_screws=2),
                    parts=[cleat, member], hardware=screws, label="jt one")
    c2 = Connection(kind=connection_types.get("butt_screwed")(n_screws=2),
                    parts=[cleat, member], hardware=screws, label="jt two")
    out = compile_connections(a, [c1, c2])
    assert [r.connection for r in out.installs] == ["jt one", "jt two"]


def test_install_resolution_is_deterministic(screwed_joint):
    a, cleat, member, screws = screwed_joint
    def run():
        conn = Connection(
            kind=connection_types.get("cleat_screwed")(n_screws=2),
            parts=[cleat, member], hardware=screws, label="jt",
            install={"": {"method": "pocket_screw"}})
        checks = conn.generate_checks(a)
        return ([r.describe() for r in checks.installs],
                [r.provenance for r in checks.installs],
                [d.fact for d in checks.derived
                 if d.rule.endswith(".install_contract")])
    assert run() == run()
