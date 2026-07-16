"""Ordinary exterior wood screws are distinct from structural screws."""

import pytest

from detailgen.core.registry import components
from detailgen.core.units import IN


def test_exterior_wood_screw_is_registered_and_truthfully_named():
    from detailgen.components import ExteriorWoodScrew, StructuralScrew

    assert components.get("exterior_wood_screw") is ExteriorWoodScrew
    screw = ExteriorWoodScrew(0.164 * IN, 1.5 * IN)

    assert not isinstance(screw, StructuralScrew)
    assert screw.material_key == "steel_galv"
    assert screw.bom_label() == "Exterior wood screw"
    assert "exterior wood screw" in screw.describe().lower()
    assert "structural" not in screw.describe().lower()
    assert "capacity" in screw.assumptions().lower()
    assert '2.25"' in ExteriorWoodScrew(0.164 * IN, 2.25 * IN).describe()


def test_exterior_wood_screw_has_a_round_head_and_pointed_shank():
    from detailgen.components import ExteriorWoodScrew

    screw = ExteriorWoodScrew(0.164 * IN, 1.5 * IN)
    bb = screw.solid.val().BoundingBox()

    assert bb.zmin == pytest.approx(-screw.length)
    assert bb.zmax == pytest.approx(screw.head_height)
    assert bb.xlen == pytest.approx(screw.head_diameter)
    assert screw.datum("head_bearing").origin == pytest.approx((0, 0, 0))
    assert screw.datum("tip").origin[2] == pytest.approx(-screw.length)


def test_exterior_wood_screw_is_fastener_class_hardware():
    from detailgen.assemblies import DetailAssembly
    from detailgen.assemblies.installation import is_fastener
    from detailgen.components import ExteriorWoodScrew

    assembly = DetailAssembly("exterior screw probe")
    screw = assembly.add(ExteriorWoodScrew(0.164 * IN, 1.5 * IN))

    assert is_fastener(screw)
