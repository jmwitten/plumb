from dataclasses import dataclass
from types import SimpleNamespace

from detailgen.assemblies import Connection, DetailAssembly, connection_types
from detailgen.components import Lumber, WoodScrew
from detailgen.core import IN
from detailgen.core.base import Component
from detailgen.details import Detail
from detailgen.package.projections import (
    fabrication_projection,
    installation_projection,
    technical_projection,
)


def test_fabrication_projection_uses_component_protocol_only():
    record = SimpleNamespace(
        stock=SimpleNamespace(profile="generic stock"),
        steps=(
            SimpleNamespace(
                kind="crosscut",
                params_dict=lambda: {"to_length_mm": 100.0},
            ),
        ),
        fab_note=lambda: "crosscut to length",
    )
    component = SimpleNamespace(fabrication_record=lambda part_id: record)
    part = SimpleNamespace(id="part-a", name="Part A", component=component)
    detail = SimpleNamespace(assembly=SimpleNamespace(parts=(part,)))

    assert fabrication_projection(detail) == (
        {
            "part_id": "part-a",
            "part_name": "Part A",
            "stock_profile": "generic stock",
            "steps": (
                {"kind": "crosscut", "params": {"to_length_mm": 100.0}},
            ),
            "note": "crosscut to length",
        },
    )


class _PurchasedPart(Component):
    def _build(self):
        raise AssertionError("projection should not build purchased geometry")


def test_fabrication_projection_skips_parts_without_a_fabrication_record():
    part = SimpleNamespace(
        id="purchased-a",
        name="Purchased A",
        component=_PurchasedPart("Purchased A"),
    )
    detail = SimpleNamespace(assembly=SimpleNamespace(parts=(part,)))

    assert fabrication_projection(detail) == ()


@dataclass(frozen=True)
class _ConnectedParams:
    pass


class _ConnectedDetail(Detail):
    name = "generic connected detail"
    Params = _ConnectedParams

    def assemble(self, assembly: DetailAssembly) -> None:
        assembly.add(Lumber("2x4", 8 * IN, name="first member"))
        assembly.add(
            Lumber("2x4", 8 * IN, name="second member"),
            at=(0, 1.5 * IN, 0),
        )
        assembly.add(
            WoodScrew(0.164 * IN, 1.5 * IN, name="joint screw"),
            at=(4 * IN, 0, 1 * IN),
        )

    def connections(self):
        return [
            Connection(
                kind=connection_types.get("butt_screwed")(n_screws=1),
                parts=[self["first member"], self["second member"]],
                hardware=[self["joint screw"]],
                label="generic joint",
            )
        ]


def test_detail_exposes_public_lifecycle_facts_after_validation():
    detail = _ConnectedDetail()

    assert detail.resolved_installations == ()
    assert detail.construction_event_graph is None

    detail.validate()

    assert len(detail.resolved_installations) == 1
    assert detail.resolved_installations[0].connection == "generic joint"
    assert detail.construction_event_graph is not None
    assert detail.construction_event_graph is detail._connection_checks.event_graph


def test_generic_document_projections_reuse_validated_detail_facts(tmp_path):
    detail = _ConnectedDetail()
    detail.validate()

    technical = technical_projection(detail, (tmp_path / "iso.png",))
    installation = installation_projection(detail)

    assert technical["title"] == detail.name
    assert technical["views"] == ("iso.png",)
    assert len(technical["coverage"]) == 9
    assert technical["bom"] == tuple(detail.bom_table())
    assert installation["installs"] == detail.resolved_installations
    assert installation["event_graph"] is detail.construction_event_graph
    assert installation["connection_edges"] == tuple(detail.connection_edges)
