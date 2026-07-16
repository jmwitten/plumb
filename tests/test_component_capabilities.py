"""Closed semantic component capabilities, independent of CAD classes."""

import pytest

from detailgen.assemblies import DetailAssembly
from detailgen.assemblies.installation import is_fastener
from detailgen.components import (
    ExteriorWoodScrew,
    HexBolt,
    HexNut,
    JoistHanger,
    LagScrew,
    StructuralScrew,
    ThreadedRod,
    Washer,
)
from detailgen.core.base import Component
from detailgen.core.units import IN


class _SemanticFastener(Component):
    CAPABILITIES = frozenset({"installation_fastener"})

    def _build(self):
        raise AssertionError("semantic capability check built CAD")


class _UnknownCapability(Component):
    CAPABILITIES = frozenset({"magic_fastener"})

    def _build(self):
        raise AssertionError("capability validation built CAD")


def test_installation_fastener_capability_accepts_new_class_without_building():
    assembly = DetailAssembly("capability probe")
    placed = assembly.add(_SemanticFastener("semantic fastener"))

    assert is_fastener(placed)
    assert placed.component.capability_tags() == frozenset(
        {"installation_fastener"}
    )


def test_ordinary_component_has_no_capabilities():
    assert Washer(0.25 * IN).capability_tags() == frozenset()


def test_unknown_capability_fails_with_closed_vocabulary():
    with pytest.raises(ValueError, match="magic_fastener.*installation_fastener"):
        _UnknownCapability("unknown").capability_tags()


@pytest.mark.parametrize(
    "component,required",
    [
        (LagScrew(0.25 * IN, 2 * IN), {"installation_fastener", "wood_screw"}),
        (
            StructuralScrew(0.25 * IN, 2 * IN),
            {"installation_fastener", "wood_screw"},
        ),
        (
            ExteriorWoodScrew(0.164 * IN, 1.5 * IN),
            {
                "installation_fastener",
                "wood_screw",
                "ordinary_wood_screw",
                "exterior_use",
            },
        ),
        (HexBolt(0.25 * IN, 2 * IN), {"installation_fastener"}),
        (ThreadedRod(0.5 * IN, 8 * IN), {"installation_fastener"}),
    ],
)
def test_fastener_components_declare_required_capabilities(component, required):
    assert required <= component.capability_tags()


@pytest.mark.parametrize(
    "component",
    [Washer(0.25 * IN), HexNut(0.25 * IN), JoistHanger(1.5 * IN, 5.5 * IN)],
)
def test_stack_and_connector_hardware_are_not_installation_fasteners(component):
    assembly = DetailAssembly("non-fastener probe")
    placed = assembly.add(component)

    assert not is_fastener(placed)
