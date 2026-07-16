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


@pytest.mark.parametrize(
    "mode,edge_kind,role",
    [
        ("pivot", "pivoted_by", "pivot_screw"),
        ("latch", "latched_by", "latch_screw"),
    ],
)
def test_parameterized_service_panel_connection_semantics(
    mode, edge_kind, role
):
    from detailgen.assemblies import (
        Connection,
        ServicePanelScrewed,
        connection_types,
    )

    assembly, frame, panel, screw = _service_joint()
    assert connection_types.get("service_panel_screwed") is ServicePanelScrewed
    kind = ServicePanelScrewed(mode)
    conn = Connection(kind=kind, parts=[frame, panel], hardware=[screw])

    checks = conn.generate_checks(assembly)

    assert checks.expected_overlaps == {(screw, frame), (screw, panel)}
    assert set(checks.bonds) == {(screw, frame), (screw, panel)}
    assert (panel.id, screw.id, edge_kind) in {
        (edge.a, edge.b, edge.kind) for edge in checks.edges
    }
    assert not any(
        edge.kind in {"fastened_by", "bears_on"} for edge in checks.edges
    )
    assert kind.transfer_claims == ()
    (install,) = checks.installs
    assert install.role == role


def test_parameterized_service_panel_rejects_unknown_mode():
    from detailgen.assemblies import ServicePanelScrewed

    with pytest.raises(ValueError, match="pivot.*latch"):
        ServicePanelScrewed("hinge-ish")


def test_service_panel_connections_require_one_exterior_screw():
    from detailgen.assemblies import Connection, connection_types
    from detailgen.components import StructuralScrew

    assembly, frame, panel, screw = _service_joint()
    kind = connection_types.get("pivot_screwed")()

    with pytest.raises(ValueError, match="expected 1 hardware"):
        Connection(kind=kind, parts=[frame, panel], hardware=[]).generate_checks(assembly)

    wrong = assembly.add(StructuralScrew(0.164 * IN, 1.5 * IN, name="wrong screw"))
    with pytest.raises(ValueError, match="exterior_use.*ordinary_wood_screw"):
        Connection(kind=kind, parts=[frame, panel], hardware=[wrong]).generate_checks(assembly)


def test_parameterized_service_panel_requires_ordinary_exterior_capabilities():
    from detailgen.assemblies import Connection, ServicePanelScrewed
    from detailgen.components import StructuralScrew, WoodScrew

    assembly, frame, panel, _screw = _service_joint()
    kind = ServicePanelScrewed("pivot")
    wrong = (
        assembly.add(
            StructuralScrew(0.164 * IN, 1.5 * IN, name="structural screw")
        ),
        assembly.add(
            WoodScrew(
                0.164 * IN,
                1.5 * IN,
                exposure="interior",
                name="interior screw",
            )
        ),
    )

    for placed in wrong:
        with pytest.raises(
            ValueError, match="exterior_use.*ordinary_wood_screw"
        ):
            Connection(
                kind=kind, parts=[frame, panel], hardware=[placed]
            ).generate_checks(assembly)


def test_service_panel_semantics_do_not_build_cad(monkeypatch):
    from detailgen.assemblies import Connection, ServicePanelScrewed
    from detailgen.components import CedarPanel, WoodScrew

    def fail_build(_self):
        pytest.fail("service-panel semantic check built CAD")

    monkeypatch.setattr(CedarPanel, "_build", fail_build)
    monkeypatch.setattr(WoodScrew, "_build", fail_build)
    from detailgen.assemblies import DetailAssembly

    assembly = DetailAssembly("no CAD service panel")
    frame = assembly.add(
        CedarPanel(8 * IN, 5.5 * IN, 0.75 * IN, name="frame")
    )
    panel = assembly.add(
        CedarPanel(8 * IN, 4 * IN, 0.75 * IN, name="panel")
    )
    screw = assembly.add(
        WoodScrew(0.164 * IN, 1.5 * IN, name="retainer")
    )

    for mode in ("pivot", "latch"):
        checks = Connection(
            kind=ServicePanelScrewed(mode),
            parts=[frame, panel],
            hardware=[screw],
        ).generate_checks(assembly)
        assert checks.installs


def test_parameterized_service_panel_compiles_from_detail_spec():
    from detailgen.spec.compiler import compile_spec
    from detailgen.spec.loader import load_spec_text

    detail = compile_spec(
        load_spec_text(
            """
name: service panel compiler probe
type: probe
units: in
components:
  - id: frame
    type: fabricated_panel
    params: {length: 8 in, width: 5.5 in, thickness: 0.75 in, material_key: cedar}
  - id: panel
    type: fabricated_panel
    params: {length: 8 in, width: 4 in, thickness: 0.75 in, material_key: cedar}
  - id: retainer
    type: wood_screw
    params: {diameter: 0.164 in, length: 1.5 in}
connections:
  - type: service_panel_screwed
    params: {mode: pivot}
    parts: [frame, panel]
    hardware: [retainer]
"""
        )
    )

    detail.build()
    facts = detail.derivation_report()

    assert any(
        fact.rule == "ServicePanelScrewed.edges"
        and "pivoted_by" in fact.fact
        for fact in facts
    )


def test_butt_screwed_accepts_an_exterior_wood_screw_for_fixed_cedar_joints():
    from detailgen.assemblies import Connection, connection_types

    assembly, frame, panel, screw = _service_joint()
    kind = connection_types.get("butt_screwed")(n_screws=1)
    conn = Connection(kind=kind, parts=[frame, panel], hardware=[screw])

    assert kind._unpack(conn)[2] == [screw]


def test_service_edge_kinds_are_traceable_but_never_load_bearing():
    from detailgen.validation.evidence import EDGE_KINDS, _CONSTRUCTION_EDGE_KINDS
    from detailgen.validation.loadpath import LOAD_BEARING_EDGE_KINDS

    for kind in ("pivoted_by", "latched_by"):
        assert kind in EDGE_KINDS
        assert kind in _CONSTRUCTION_EDGE_KINDS
        assert kind not in LOAD_BEARING_EDGE_KINDS
