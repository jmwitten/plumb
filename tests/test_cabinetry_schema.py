"""Author-facing schema, construction profile, and real catalog contracts."""

from __future__ import annotations

import copy
import math

import pytest
import yaml

from detailgen.core.units import IN
from detailgen.packs import ProjectSchemaError, load_project_text


def _mapping() -> dict:
    return {
        "name": "B30 frameless base cabinet",
        "units": "in",
        "packs": ["cabinetry.frameless@1"],
        "site": {
            "wall": {
                "id": "north_wall",
                "type": "stud_wall",
                "plane": {
                    "origin": [0, 23.25, 0],
                    "normal": [0, -1, 0],
                },
                "length": 120,
                "height": 96,
                "finish_thickness": 0.5,
                "studs": [
                    {"id": "stud_32", "position": 32, "verified": True},
                    {"id": "stud_48", "position": 48, "verified": True},
                ],
            },
            "floor": {"high_point_elevation": 0, "verified": True},
            "environment": {
                "building_enclosed": True,
                "wet_work_complete": True,
                "hvac_operating": True,
                "acclimation_hours": 72,
            },
        },
        "cabinetry": {
            "mode": "release",
            "profile": "frameless_plywood_shop_v1@1.0.0",
            "material_evidence": {
                "tsca_title_vi": "verified",
                "reference": "supplier label and lot record",
                "product": "Garnica Duraply 3/4 in",
                "density_kg_m3": 500,
                "modulus_elasticity_mpa": 3400,
                "property_reference": "Garnica Duraply North America spec 2025/01",
            },
            "cabinets": [
                {
                    "id": "B30",
                    "type": "base",
                    "width": 30,
                    "placement": {
                        "against": "north_wall",
                        "from_left_datum": 24,
                    },
                    "front": {"doors": 2},
                    "interior": {
                        "adjustable_shelves": 1,
                        "design_load_psf": 15,
                    },
                    "conditions": {
                        "left_end": "exposed",
                        "right_end": "adjacent_cabinet",
                    },
                    "countertop": {
                        "type": "field_installed",
                        "support": "cabinet_stretchers",
                    },
                }
            ],
        },
    }


def _parse(mapping: dict | None = None):
    from detailgen.packs.cabinetry import FramelessCabinetryPack

    mapping = _mapping() if mapping is None else mapping
    doc = load_project_text(yaml.safe_dump(mapping, sort_keys=False))
    return FramelessCabinetryPack().parse(doc)


def test_parse_approved_vertical_slice_resolves_project_units_to_mm():
    section = _parse()
    cabinet = section.cabinets[0]

    assert section.mode == "release"
    assert section.profile_id == "frameless_plywood_shop_v1@1.0.0"
    assert cabinet.cabinet_id == "B30"
    assert cabinet.kind == "base"
    assert cabinet.width_mm == pytest.approx(30 * IN)
    assert cabinet.from_left_datum_mm == pytest.approx(24 * IN)
    assert cabinet.door_count == 2
    assert cabinet.adjustable_shelf_count == 1
    assert section.site.wall.studs[0].position_mm == pytest.approx(32 * IN)
    assert all(stud.verified for stud in section.site.wall.studs)


def test_explicit_quantity_overrides_project_units():
    raw = _mapping()
    raw["cabinetry"]["cabinets"][0]["width"] = "762 mm"
    raw["site"]["wall"]["finish_thickness"] = "12.7 mm"

    section = _parse(raw)

    assert section.cabinets[0].width_mm == pytest.approx(762.0)
    assert section.site.wall.finish_thickness_mm == pytest.approx(12.7)


@pytest.mark.parametrize(
    ("path", "value", "phrase"),
    [
        (("cabinetry", "cabinets", 0, "front", "doors"), 3,
         "v1 requires exactly two overlay doors"),
        (("cabinetry", "cabinets", 0, "interior", "adjustable_shelves"), 2,
         "v1 requires exactly one adjustable shelf"),
        (("cabinetry", "profile"), "not-real", "known profiles"),
        (("cabinetry", "cabinets", 0, "width"), True,
         "width must be a length"),
    ],
)
def test_v1_rejects_unsupported_or_ambiguous_input(path, value, phrase):
    raw = _mapping()
    target = raw
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value

    with pytest.raises(ProjectSchemaError, match=phrase):
        _parse(raw)


def test_unknown_nested_key_has_teaching_diagnostic():
    raw = _mapping()
    raw["cabinetry"]["cabinets"][0]["front"]["doros"] = 2

    with pytest.raises(ProjectSchemaError) as exc:
        _parse(raw)

    message = str(exc.value)
    assert "unknown key 'doros'" in message
    assert "doors" in message


def test_wall_reference_and_unique_ids_are_checked():
    raw = _mapping()
    raw["cabinetry"]["cabinets"][0]["placement"]["against"] = "south_wall"
    with pytest.raises(ProjectSchemaError, match="unknown wall 'south_wall'.*north_wall"):
        _parse(raw)

    raw = _mapping()
    raw["site"]["wall"]["studs"].append(
        copy.deepcopy(raw["site"]["wall"]["studs"][0])
    )
    with pytest.raises(ProjectSchemaError, match="duplicate stud id 'stud_32'"):
        _parse(raw)


@pytest.mark.parametrize("offset", [-1, 100])
def test_cabinet_placement_must_fit_inside_surveyed_wall(offset):
    raw = _mapping()
    raw["cabinetry"]["cabinets"][0]["placement"]["from_left_datum"] = offset

    with pytest.raises(ProjectSchemaError, match="cabinet span.*surveyed wall"):
        _parse(raw)


@pytest.mark.parametrize(
    ("mutator", "phrase"),
    [
        (lambda raw: raw["site"]["wall"]["studs"][0].update(id=""),
         "studs\\[0\\].id must be non-empty"),
        (lambda raw: raw["site"]["wall"].update(stud_width=2),
         "only nominal 2x4 studs"),
        (lambda raw: raw["site"]["wall"].update(stud_depth=6),
         "only nominal 2x4 studs"),
        (lambda raw: raw["cabinetry"]["cabinets"][0]["countertop"].update(
            type="shop_installed"), "v1 supports only field_installed"),
        (lambda raw: raw["cabinetry"]["cabinets"][0]["countertop"].update(
            support="continuous_subtop"), "v1 supports only cabinet_stretchers"),
    ],
)
def test_v1_rejects_inputs_it_does_not_lower(mutator, phrase):
    raw = _mapping()
    mutator(raw)

    with pytest.raises(ProjectSchemaError, match=phrase):
        _parse(raw)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda raw: raw["site"]["wall"].update(length=math.nan),
        lambda raw: raw["site"]["wall"]["studs"][0].update(position=math.inf),
        lambda raw: raw["site"]["environment"].update(acclimation_hours=math.nan),
        lambda raw: raw["cabinetry"]["cabinets"][0]["interior"].update(
            design_load_psf=math.inf),
    ],
)
def test_non_finite_numbers_are_rejected(mutator):
    raw = _mapping()
    mutator(raw)

    with pytest.raises(ProjectSchemaError, match="finite"):
        _parse(raw)


def test_wall_plane_is_explicit_and_v1_axis_aligned():
    section = _parse()

    assert section.site.wall.plane_origin_mm == pytest.approx(
        (0.0, 23.25 * IN, 0.0)
    )
    assert section.site.wall.plane_normal == (0.0, -1.0, 0.0)

    raw = _mapping()
    raw["site"]["wall"]["plane"]["normal"] = [1, 0, 0]
    with pytest.raises(ProjectSchemaError, match="normal.*\\[0, -1, 0\\]"):
        _parse(raw)


def test_profile_encodes_the_approved_conventional_shop_baseline():
    from detailgen.packs.cabinetry.profiles import get_profile

    profile = get_profile("frameless_plywood_shop_v1@1.0.0")

    assert profile.construction == "frameless"
    assert profile.carcass_thickness_mm == pytest.approx(0.75 * IN)
    assert profile.back_thickness_mm == pytest.approx(0.25 * IN)
    assert profile.base_assembly == "independent_toe_kick"
    assert profile.joinery == "glue_and_cabinet_screws"
    assert profile.edge_treatment == "applied_edge_band"
    assert profile.hinge_product_id == "blum_clip_top_blumotion_110_h002@2025.1"
    assert profile.performance_reference == "ANSI_KCMA_A161_1_2022"


def test_blum_adapter_records_product_specific_geometry_and_source():
    from detailgen.packs.cabinetry.catalogs import get_hinge_product

    hinge = get_hinge_product("blum_clip_top_blumotion_110_h002@2025.1")

    assert hinge.manufacturer == "Blum"
    assert hinge.product == "CLIP top BLUMOTION 110° screw-on hinge kit H002"
    assert hinge.cup_diameter_mm == 35.0
    assert hinge.cup_depth_mm == 13.0
    assert hinge.plate_line_mm == 37.0
    assert hinge.plate_hole_spacing_mm == 32.0
    assert hinge.door_thickness_range_mm == (16.0, 26.0)
    assert hinge.overlay_range_mm == (14.0, 18.0)
    assert hinge.opening_angle_deg == 110.0
    assert hinge.source_url.startswith("https://d2.blum.com/")
