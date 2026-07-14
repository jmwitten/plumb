"""Lower cabinet-domain semantics into the existing frozen DetailSpec IR."""

from __future__ import annotations

from ...spec.schema import (
    AuthoredStage,
    BondSpec,
    ComponentSpec,
    ContactSpec,
    DetailSpecDoc,
    OverlapSpec,
    RawSpec,
    SequenceSpec,
    ValidationSpec,
)
from .model import CabinetModel
from .labels import reader_name_for_part


def _component(part) -> ComponentSpec:
    return ComponentSpec(
        id=part.part_id,
        type=part.component_type,
        name=part.name,
        reader_name=reader_name_for_part(part),
        params=part.params_dict(),
        place=RawSpec(at=part.at_mm, rotate=part.rotate),
    )


def lower_model(model: CabinetModel | object) -> DetailSpecDoc:
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

    drawer_bank = getattr(model, "drawer_bank", None)
    if drawer_bank is not None:
        for cell in drawer_bank.cells:
            box = {
                role: cid(f"drawer_{cell.cell_id}_{role}")
                for role in ("side_left", "side_right", "front", "back", "bottom")
            }
            joinery = (
                (box["side_left"], box["front"]),
                (box["side_right"], box["front"]),
                (box["side_left"], box["back"]),
                (box["side_right"], box["back"]),
                (box["bottom"], box["side_left"]),
                (box["bottom"], box["side_right"]),
                (box["bottom"], box["front"]),
                (box["bottom"], box["back"]),
                (box["front"], cid(f"drawer_front_{cell.cell_id}")),
            )
            bonds.extend(BondSpec(a, b) for a, b in joinery)
            contacts.extend(ContactSpec(a, b) for a, b in joinery)
            overlaps.extend(OverlapSpec(box["bottom"], box[role]) for role in (
                "side_left", "side_right", "front", "back"
            ))
            # The purchased runner connects the moving box to both case ends.
            # It is scheduled hardware rather than invented base geometry, so
            # these are connectivity bonds only, not false face contacts.
            bonds.extend((
                BondSpec(box["side_left"], cid("left_end")),
                BondSpec(box["side_right"], cid("right_end")),
            ))
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
    sequence = SequenceSpec()
    if drawer_bank is not None:
        toe_ids = tuple(cid(role) for role in (
            "toe_front", "toe_rear", "toe_left", "toe_right",
        ))
        carcass_ids = tuple(cid(role) for role in (
            "left_end", "right_end", "bottom", "captured_back",
            "front_stretcher", "rear_stretcher", "anchor_strip",
        ))
        drawer_ids = tuple(part.part_id for part in drawer_bank.parts)
        anchor_ids = tuple(
            cid(f"wall_anchor_{stud_id}") for stud_id in model.anchor_stud_ids
        )
        stages = [
            AuthoredStage(
                name="assembly.toe_base",
                why=("The independent toe platform is assembled square before "
                     "it supports the cabinet carcass."),
                parts=toe_ids,
            ),
            AuthoredStage(
                name="assembly.carcass",
                why=("The empty carcass and captured back are assembled square "
                     "before drawer assemblies are fitted."),
                parts=carcass_ids,
            ),
            AuthoredStage(
                name="assembly.drawer_boxes",
                why=("Drawer boxes, applied fronts, and their adjustments are "
                     "completed in the shop before conventional shipment."),
                parts=drawer_ids,
            ),
        ]
        if anchor_ids:
            stages.append(AuthoredStage(
                name="install.wall_anchor",
                why=("The labeled drawers are removed for shipment and the "
                     "empty carcass is set level and plumb before wall anchors "
                     "are driven."),
                parts=anchor_ids,
            ))
        sequence = SequenceSpec(stages=tuple(stages))
    return DetailSpecDoc(
        name=model.project_name,
        type=("cabinetry_frameless_drawer_base" if drawer_bank is not None
              else "cabinetry_frameless_base"),
        units="mm",
        components=[_component(part) for part in model.parts],
        validation=ValidationSpec(
            bonds=bonds,
            contacts=contacts,
            expected_overlaps=overlaps,
        ),
        roles={stud_id: "existing" for stud_id in stud_ids},
        context_grounds=frozenset(stud_ids),
        sequence=sequence,
    )
