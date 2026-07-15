"""Reusable adhesive-and-corner-key miter connection semantics."""

import math

import pytest

from detailgen.assemblies import Connection, DetailAssembly, connection_types
from detailgen.components import HardwoodPanel, Lumber, StructuralScrew, WoodDowel
from detailgen.core.units import IN


def _corner():
    assembly = DetailAssembly("reinforced miter probe")
    top = assembly.add(
        HardwoodPanel(
            8 * IN,
            5.5 * IN,
            0.75 * IN,
            miter_ends=("far",),
            name="top panel",
        )
    )
    side = assembly.add(
        HardwoodPanel(
            7.75 * IN,
            5.5 * IN,
            0.75 * IN,
            miter_ends=("far",),
            name="side panel",
        )
    )
    pin_length = math.sqrt(2) * 0.75 * IN
    front = assembly.add(WoodDowel(0.375 * IN, pin_length, "front key"))
    back = assembly.add(WoodDowel(0.375 * IN, pin_length, "back key"))
    return assembly, top, side, front, back


def _connection(top, side, front, back):
    from detailgen.assemblies.connection import DowelReinforcedMiter

    return Connection(
        kind=DowelReinforcedMiter(),
        parts=[top, side],
        hardware=[front, back],
        assumptions=[
            "Hardwood miter faces and corner-key dowels receive wood glue; "
            "clamp and cure per the selected adhesive label; capacity NOT analyzed."
        ],
        label="top -> side (dowel-reinforced miter)",
    )


def test_dowel_reinforced_miter_is_registered():
    from detailgen.assemblies.connection import DowelReinforcedMiter

    assert connection_types.get("dowel_reinforced_miter") is DowelReinforcedMiter


def test_reinforced_miter_derives_bond_keys_intersections_and_order():
    assembly, top, side, front, back = _corner()
    checks = _connection(top, side, front, back).generate_checks(assembly)

    assert checks.expected_overlaps == {
        (front, top),
        (front, side),
        (back, top),
        (back, side),
    }
    assert set(checks.bonds) == {
        (top, side),
        (front, top),
        (front, side),
        (back, top),
        (back, side),
    }
    assert [(edge.a, edge.b, edge.kind) for edge in checks.edges] == [
        (top.id, front.id, "installed_before"),
        (side.id, front.id, "installed_before"),
        (top.id, back.id, "installed_before"),
        (side.id, back.id, "installed_before"),
        (top.id, side.id, "bonded_to"),
        (top.id, side.id, "keyed_by"),
    ]
    assert checks.installs == []
    assert len([f for f in checks.findings if f.check == "connection_hardware"]) == 2
    assert not [f for f in checks.findings if f.check == "install_method"]


def test_reinforced_miter_owns_label_governed_cure_and_unanalyzed_claims():
    assembly, top, side, front, back = _corner()
    conn = _connection(top, side, front, back)

    assert conn.kind.supported_process_kinds() == frozenset({"cure"})
    (cure,) = conn.kind.process_events(conn)
    assert cure.completion == "selected_label_full_cure"
    assert cure.provenance == "connectiontype_default"
    assert "actual shop conditions" in cure.why
    claims = {claim.load_class: claim for claim in conn.kind.transfer_claims}
    assert set(claims) == {"pull_out", "shear"}
    assert all(claim.confidence == "placeholder" for claim in claims.values())
    assert all("capacity NOT analyzed" in claim.reference for claim in claims.values())
    assert conn.kind.install_contract(conn) == ()


def test_reinforced_miter_requires_two_panels_and_exactly_two_wood_dowels():
    from detailgen.assemblies.connection import DowelReinforcedMiter

    assembly, top, side, front, back = _corner()
    third = assembly.add(
        HardwoodPanel(4 * IN, 5.5 * IN, 0.75 * IN, name="third panel")
    )
    with pytest.raises(ValueError, match="EXACTLY two mitered panels"):
        Connection(
            kind=DowelReinforcedMiter(),
            parts=[top, side, third],
            hardware=[front, back],
        ).generate_checks(assembly)

    screw = assembly.add(StructuralScrew(0.19 * IN, 1.25 * IN, "wrong key"))
    with pytest.raises(ValueError, match="must be a WoodDowel"):
        Connection(
            kind=DowelReinforcedMiter(),
            parts=[top, side],
            hardware=[front, screw],
        ).generate_checks(assembly)

    with pytest.raises(ValueError, match="expected 2 hardware"):
        Connection(
            kind=DowelReinforcedMiter(),
            parts=[top, side],
            hardware=[front],
        ).generate_checks(assembly)

    wrong_member = assembly.add(Lumber("1x6", 8 * IN, name="wrong panel type"))
    with pytest.raises(ValueError, match="must be HardwoodPanel"):
        Connection(
            kind=DowelReinforcedMiter(),
            parts=[top, wrong_member],
            hardware=[front, back],
        ).generate_checks(assembly)


def test_keyed_by_is_retained_by_load_path_evidence_and_incremental_consumers():
    from detailgen.validation.evidence import EDGE_KINDS, _CONSTRUCTION_EDGE_KINDS
    from detailgen.validation.loadpath import LOAD_BEARING_EDGE_KINDS

    assert "keyed_by" in LOAD_BEARING_EDGE_KINDS
    assert "keyed_by" in EDGE_KINDS
    assert "keyed_by" in _CONSTRUCTION_EDGE_KINDS
