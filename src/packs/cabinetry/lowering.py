"""Lower cabinet-domain semantics into the existing frozen DetailSpec IR."""

from __future__ import annotations

from ...spec.schema import (
    BondSpec,
    ComponentSpec,
    ContactSpec,
    DetailSpecDoc,
    OverlapSpec,
    RawSpec,
    ValidationSpec,
)
from .model import CabinetModel


def _component(part) -> ComponentSpec:
    return ComponentSpec(
        id=part.part_id,
        type=part.component_type,
        name=part.name,
        params=part.params_dict(),
        place=RawSpec(at=part.at_mm, rotate=part.rotate),
    )


def lower_model(model: CabinetModel) -> DetailSpecDoc:
    """Produce ordinary base-language parts and relationships only."""

    cabinet = model.section.cabinets[0]
    prefix = f"cabinetry.{cabinet.cabinet_id}."

    def cid(role: str) -> str:
        return prefix + role

    bonds = [
        BondSpec(cid("bottom"), cid("left_end")),
        BondSpec(cid("bottom"), cid("right_end")),
        BondSpec(cid("front_stretcher"), cid("left_end")),
        BondSpec(cid("front_stretcher"), cid("right_end")),
        BondSpec(cid("rear_stretcher"), cid("left_end")),
        BondSpec(cid("rear_stretcher"), cid("right_end")),
        BondSpec(cid("captured_back"), cid("left_end")),
        BondSpec(cid("captured_back"), cid("right_end")),
        BondSpec(cid("captured_back"), cid("bottom")),
        BondSpec(cid("anchor_strip"), cid("left_end")),
        BondSpec(cid("anchor_strip"), cid("right_end")),
        BondSpec(cid("toe_front"), cid("toe_left")),
        BondSpec(cid("toe_front"), cid("toe_right")),
        BondSpec(cid("toe_rear"), cid("toe_left")),
        BondSpec(cid("toe_rear"), cid("toe_right")),
        BondSpec(cid("bottom"), cid("toe_front")),
        BondSpec(cid("bottom"), cid("toe_rear")),
    ]
    contacts = [ContactSpec(bond.a, bond.b) for bond in bonds]
    overlaps: list[OverlapSpec] = []
    for stud_id in model.anchor_stud_ids:
        screw = cid(f"wall_anchor_{stud_id}")
        overlaps.extend((
            OverlapSpec(screw, cid("anchor_strip")),
            OverlapSpec(screw, cid("captured_back")),
            OverlapSpec(screw, f"site.{cabinet.wall_id}.{stud_id}"),
        ))

    stud_ids = tuple(
        part.part_id for part in model.parts if part.role.startswith("wall_stud_")
    )
    return DetailSpecDoc(
        name=model.project_name,
        type="cabinetry_frameless_base",
        units="mm",
        components=[_component(part) for part in model.parts],
        validation=ValidationSpec(
            bonds=bonds,
            contacts=contacts,
            expected_overlaps=overlaps,
        ),
        roles={stud_id: "existing" for stud_id in stud_ids},
        context_grounds=frozenset(stud_ids),
    )

