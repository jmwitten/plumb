"""Pivoting cleanout-panel connections without fixed-joint claims."""

import pytest

from detailgen.core.units import IN


def _service_joint():
    from detailgen.assemblies import DetailAssembly
    from detailgen.components import CedarPanel, ExteriorWoodScrew

    assembly = DetailAssembly("service panel probe")
    frame = assembly.add(CedarPanel(8 * IN, 5.5 * IN, 0.75 * IN, name="front"))
    panel = assembly.add(
        CedarPanel(8 * IN, 4 * IN, 0.75 * IN, name="cleanout side"),
        at=(20, 0, 0),
    )
    screw = assembly.add(
        ExteriorWoodScrew(0.164 * IN, 1.5 * IN, name="service screw"),
        at=(10, 0, 0),
    )
    return assembly, frame, panel, screw


@pytest.mark.parametrize(
    "type_name,class_name,edge_kind,role",
    [
        ("pivot_screwed", "PivotScrewed", "pivoted_by", "pivot_screw"),
        ("service_latch_screwed", "ServiceLatchScrewed", "latched_by", "latch_screw"),
    ],
)
def test_service_panel_connection_semantics(type_name, class_name, edge_kind, role):
    from detailgen.assemblies import Connection, connection_types

    assembly, frame, panel, screw = _service_joint()
    kind_cls = connection_types.get(type_name)
    assert kind_cls.__name__ == class_name
    conn = Connection(
        kind=kind_cls(),
        parts=[frame, panel],
        hardware=[screw],
        label=f"{type_name} probe",
    )
    checks = conn.generate_checks(assembly)

    assert checks.expected_overlaps == {(screw, frame), (screw, panel)}
    assert set(checks.bonds) == {(screw, frame), (screw, panel)}
    assert {(edge.a, edge.b, edge.kind) for edge in checks.edges} == {
        (frame.id, screw.id, "installed_before"),
        (panel.id, screw.id, "installed_before"),
        (panel.id, screw.id, edge_kind),
    }
    assert not any(edge.kind in {"fastened_by", "bears_on"} for edge in checks.edges)
    assert kind_cls.transfer_claims == ()
    (install,) = checks.installs
    assert install.role == role
    assert install.contract.method == "driven_straight"
    assert install.contract.entry_face.part == frame.id
    assert install.fasteners == (screw.id,)


def test_service_panel_connections_require_one_exterior_screw():
    from detailgen.assemblies import Connection, connection_types
    from detailgen.components import StructuralScrew

    assembly, frame, panel, screw = _service_joint()
    kind = connection_types.get("pivot_screwed")()

    with pytest.raises(ValueError, match="expected 1 hardware"):
        Connection(kind=kind, parts=[frame, panel], hardware=[]).generate_checks(assembly)

    wrong = assembly.add(StructuralScrew(0.164 * IN, 1.5 * IN, name="wrong screw"))
    with pytest.raises(ValueError, match="must be a ExteriorWoodScrew"):
        Connection(kind=kind, parts=[frame, panel], hardware=[wrong]).generate_checks(assembly)


def test_butt_screwed_accepts_an_exterior_wood_screw_for_fixed_cedar_joints():
    from detailgen.assemblies import Connection, connection_types

    assembly, frame, panel, screw = _service_joint()
    kind = connection_types.get("butt_screwed")(n_screws=1)
    conn = Connection(kind=kind, parts=[frame, panel], hardware=[screw])

    assert kind._unpack(conn)[2] == [screw]


def test_cleat_screwed_accepts_an_exterior_wood_screw_for_mounting_cleats():
    from detailgen.assemblies import Connection, connection_types

    assembly, cleat, back, screw = _service_joint()
    kind = connection_types.get("cleat_screwed")(n_screws=1)
    conn = Connection(kind=kind, parts=[cleat, back], hardware=[screw])

    assert kind._unpack(conn)[2] == [screw]


def test_service_edge_kinds_are_traceable_but_never_load_bearing():
    from detailgen.validation.evidence import EDGE_KINDS, _CONSTRUCTION_EDGE_KINDS
    from detailgen.validation.loadpath import LOAD_BEARING_EDGE_KINDS

    for kind in ("pivoted_by", "latched_by"):
        assert kind in EDGE_KINDS
        assert kind in _CONSTRUCTION_EDGE_KINDS
        assert kind not in LOAD_BEARING_EDGE_KINDS
