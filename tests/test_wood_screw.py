"""Reusable ordinary wood screws and capability-based wood joints."""

import pytest

from detailgen.assemblies import Connection, DetailAssembly, connection_types
from detailgen.components import HexBolt, Lumber, Washer
from detailgen.core.base import Component
from detailgen.core.buildinfo import geometry_hash
from detailgen.core.registry import components
from detailgen.core.units import IN


class _CapableWoodScrew(Component):
    CAPABILITIES = frozenset({"installation_fastener", "wood_screw"})

    def __init__(self, length, name="capable screw"):
        super().__init__(name)
        self.length = length

    def _build(self):
        raise AssertionError("semantic wood-joint check built CAD")


def _wood_joint(hardware):
    assembly = DetailAssembly("wood joint")
    first = assembly.add(Lumber("2x4", 8 * IN, name="first member"))
    second = assembly.add(
        Lumber("2x4", 8 * IN, name="second member"), at=(0, 40, 0)
    )
    placed = [assembly.add(item) for item in hardware]
    return assembly, first, second, placed


def test_wood_screw_is_registered_truthful_and_exterior_by_default():
    from detailgen.components import ExteriorWoodScrew, WoodScrew

    assert components.get("wood_screw") is WoodScrew
    screw = WoodScrew(0.164 * IN, 1.5 * IN)

    assert screw.material_key == "steel_galv"
    assert screw.exposure == "exterior"
    assert screw.representation == "envelope"
    assert {
        "installation_fastener",
        "wood_screw",
        "ordinary_wood_screw",
        "exterior_use",
    } <= screw.capability_tags()
    assert "structural" not in screw.describe().lower()
    assert "structural" not in screw.bom_label().lower()
    assumptions = screw.assumptions().lower()
    assert "threads" in assumptions and "omitted" in assumptions
    assert "drive" in assumptions and "capacity" in assumptions
    assert ExteriorWoodScrew(0.164 * IN, 1.5 * IN).bom_label() == (
        "Exterior wood screw"
    )


def test_interior_wood_screw_omits_only_exterior_capability():
    from detailgen.components import WoodScrew

    exterior = WoodScrew(0.164 * IN, 1.5 * IN).capability_tags()
    interior = WoodScrew(
        0.164 * IN, 1.5 * IN, exposure="interior"
    ).capability_tags()

    assert exterior - interior == {"exterior_use"}


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"exposure": "wetish"}, "interior.*exterior"),
        ({"representation": "helixish"}, "envelope.*represented_threads"),
        ({"material_key": "missing_material"}, "unknown.*material"),
    ],
)
def test_wood_screw_rejects_unknown_closed_values(kwargs, match):
    from detailgen.components import WoodScrew

    with pytest.raises(ValueError, match=match):
        WoodScrew(0.164 * IN, 1.5 * IN, **kwargs)


def test_envelope_geometry_never_calls_threaded_shaft(monkeypatch):
    from detailgen.components import WoodScrew
    from detailgen.components import fasteners

    monkeypatch.setattr(
        fasteners,
        "threaded_shaft",
        lambda *args, **kwargs: pytest.fail(
            "envelope screw built represented threads"
        ),
    )
    screw = WoodScrew(0.164 * IN, 1.5 * IN)
    bb = screw.solid.val().BoundingBox()

    assert bb.zmin == pytest.approx(-screw.length)
    assert bb.zmax == pytest.approx(screw.head_height)
    assert bb.xlen == pytest.approx(screw.head_diameter)


def test_exterior_wrapper_preserves_represented_thread_geometry_hash():
    from detailgen.components import ExteriorWoodScrew

    assert geometry_hash(ExteriorWoodScrew(0.164 * IN, 1.5 * IN).solid) == (
        "9fea70e8c0facd592ff729f0e443d54dde64257d8bfe80f229ba3d9b6856db22"
    )


@pytest.mark.parametrize("connection_name", ["cleat_screwed", "butt_screwed"])
def test_wood_screw_works_in_capability_based_wood_joints(connection_name):
    from detailgen.components import WoodScrew

    assembly, first, second, (screw,) = _wood_joint(
        [WoodScrew(0.164 * IN, 1.5 * IN)]
    )
    kind = connection_types.get(connection_name)(n_screws=1)
    conn = Connection(kind=kind, parts=[first, second], hardware=[screw])

    checks = conn.generate_checks(assembly)

    assert checks.installs[0].fasteners == (screw.id,)


def test_test_only_wood_screw_capability_passes_without_building_cad():
    assembly, first, second, (screw,) = _wood_joint(
        [_CapableWoodScrew(1.5 * IN)]
    )
    kind = connection_types.get("butt_screwed")(n_screws=1)
    conn = Connection(kind=kind, parts=[first, second], hardware=[screw])

    checks = conn.generate_checks(assembly)

    assert checks.installs[0].fasteners == (screw.id,)


@pytest.mark.parametrize(
    "wrong",
    [HexBolt(0.25 * IN, 2 * IN, name="wrong bolt"), Washer(0.25 * IN)],
)
def test_wood_joint_capability_error_names_slot_required_actual_and_part(wrong):
    assembly, first, second, (placed,) = _wood_joint([wrong])
    kind = connection_types.get("butt_screwed")(n_screws=1)

    with pytest.raises(ValueError) as caught:
        Connection(
            kind=kind, parts=[first, second], hardware=[placed]
        ).generate_checks(assembly)

    message = str(caught.value)
    assert "slot 0" in message
    assert "wood_screw" in message
    assert type(wrong).__name__ in message
    assert placed.name in message


def test_wood_joint_wrong_count_keeps_positional_diagnostic():
    assembly, first, second, _placed = _wood_joint([])
    kind = connection_types.get("butt_screwed")(n_screws=1)

    with pytest.raises(ValueError, match="expected 1 hardware item"):
        Connection(
            kind=kind, parts=[first, second], hardware=[]
        ).generate_checks(assembly)
