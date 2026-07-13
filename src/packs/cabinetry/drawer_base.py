"""Floor-supported drawer-base product composed from shell and drawer bank."""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalogs import AssemblyFastenerProduct, WallAnchorProduct, get_assembly_fastener
from .drawers import DrawerBankModel, build_drawer_bank
from .profiles import ConstructionProfile
from .schema import CabinetrySection, DrawerBaseDecl
from .shell import (
    BaseShellModel,
    DerivedValue,
    HardwareSystem,
    MachiningFeature,
    PartModel,
    Provenance,
    build_base_shell,
)


_SIDE_REVEAL_MM = 1.5
_FRONT_THICKNESS_MM = 19.05
_FRONT_FASTENER_ID = "grk_low_profile_cabinet_8x1_1_4_114069@2026.1"


@dataclass(frozen=True)
class ObstructionEnvelope:
    """A declared room obstruction checked against a drawer's swept envelope."""

    obstruction_id: str
    bounds_mm: tuple[float, float, float, float, float, float]

    def __post_init__(self):
        if not self.obstruction_id.strip():
            raise ValueError("obstruction_id must be non-empty")
        if len(self.bounds_mm) != 6:
            raise ValueError("obstruction bounds must be xmin,ymin,zmin,xmax,ymax,zmax")
        if any(self.bounds_mm[index] >= self.bounds_mm[index + 3]
               for index in range(3)):
            raise ValueError("obstruction bounds must have positive extent")


@dataclass(frozen=True)
class DrawerBaseModel:
    """The DB40 parent product with the common packed-project model protocol."""

    project_name: str
    mode: str
    profile: ConstructionProfile
    wall_anchor: WallAnchorProduct
    front_fastener: AssemblyFastenerProduct
    section: CabinetrySection
    shell: BaseShellModel
    drawer_bank: DrawerBankModel
    parts: tuple[PartModel, ...]
    machining: tuple[MachiningFeature, ...]
    hardware: tuple[HardwareSystem, ...]
    derived: tuple[DerivedValue, ...]
    source_map: dict[str, Provenance] = field(compare=True)
    declared_obstructions: tuple[ObstructionEnvelope, ...] = ()
    drawer_process_sequence: tuple[str, ...] = ()
    anchor_stud_ids: tuple[str, ...] = ()

    def part(self, role: str) -> PartModel:
        matches = [part for part in self.parts if part.role == role]
        if len(matches) != 1:
            raise KeyError(
                f"expected one drawer-base part with role {role!r}, found "
                f"{[part.role for part in matches]}"
            )
        return matches[0]

    def derived_value(self, name: str) -> DerivedValue:
        try:
            return next(value for value in self.derived if value.name == name)
        except StopIteration:
            raise KeyError(
                f"unknown derived drawer-base value {name!r}; known: "
                f"{[value.name for value in self.derived]}"
            ) from None


def build_drawer_base_model(
    section: CabinetrySection, *, project_name: str
) -> DrawerBaseModel:
    """Compose a floor-supported shell around one full-width drawer bank."""

    cabinet = section.cabinets[0]
    if not isinstance(cabinet, DrawerBaseDecl):
        raise TypeError(
            f"drawer-base builder requires DrawerBaseDecl, got {type(cabinet).__name__}"
        )
    shell = build_base_shell(section, cabinet)
    front_fastener = get_assembly_fastener(_FRONT_FASTENER_ID)
    bank = build_drawer_bank(
        cabinet.drawer_bank,
        namespace=f"cabinetry.{cabinet.cabinet_id}",
        opening_origin_mm=(
            shell.x0_mm + shell.profile.carcass_thickness_mm,
            shell.front_y_mm,
            shell.base_z_mm + cabinet.toe_kick_height_mm,
        ),
        opening_width_mm=shell.inside_width_mm,
        opening_height_mm=shell.body_height_mm,
        inside_depth_mm=shell.inside_depth_mm,
        front_origin_mm=(
            shell.x0_mm + _SIDE_REVEAL_MM,
            shell.front_y_mm,
            shell.base_z_mm + cabinet.toe_kick_height_mm,
        ),
        front_width_mm=cabinet.width_mm - 2 * _SIDE_REVEAL_MM,
        front_thickness_mm=_FRONT_THICKNESS_MM,
        mounting_part_ids=(
            f"cabinetry.{cabinet.cabinet_id}.left_end",
            f"cabinetry.{cabinet.cabinet_id}.right_end",
        ),
        material_density_kg_m3=section.material_evidence.density_kg_m3,
    )

    drawer_hardware: list[HardwareSystem] = []
    for index, cell in enumerate(bank.cells):
        drawer_hardware.extend(bank.hardware[index * 4:(index + 1) * 4])
        drawer_hardware.append(HardwareSystem(
            system_id=(f"cabinetry.{cabinet.cabinet_id}.{cell.cell_id}."
                       "applied_front_fasteners"),
            kind="applied_front_fastener_system",
            product_id=front_fastener.product_id,
            quantity=4,
            related_parts=(
                f"cabinetry.{cabinet.cabinet_id}.drawer_{cell.cell_id}_front",
                f"cabinetry.{cabinet.cabinet_id}.drawer_front_{cell.cell_id}",
            ),
            evidence="manufacturer_rated",
            source_url=front_fastener.source_url,
        ))

    source_map = dict(shell.source_map)
    source_map.update(bank.source_map)
    return DrawerBaseModel(
        project_name=project_name,
        mode=section.mode,
        profile=shell.profile,
        wall_anchor=shell.wall_anchor,
        front_fastener=front_fastener,
        section=section,
        shell=shell,
        drawer_bank=bank,
        parts=shell.carcass_parts + bank.parts + shell.support_parts,
        machining=(shell.groove_machining + bank.machining
                   + shell.joinery_machining),
        hardware=tuple(drawer_hardware) + shell.hardware,
        derived=shell.derived + bank.derived + (
            DerivedValue(
                "front_width", cabinet.width_mm - 2 * _SIDE_REVEAL_MM, "mm",
                ("cabinet_width", "side_reveals"),
                "drawer_front.full_overlay_width",
            ),
            DerivedValue(
                "frontable_body_height", shell.body_height_mm, "mm",
                ("cabinet_height", "toe_kick_height"),
                "drawer_front.body_height",
            ),
        ),
        source_map=source_map,
        declared_obstructions=(),
        drawer_process_sequence=(
            "shop.adjust_drawers",
            "ship.record_adjustment_identity",
            "ship.remove_drawers",
            "ship.empty_carcass",
            "install.anchor_empty_carcass",
            "install.reinstall_by_identity",
            "install.commission_drawers",
        ),
        anchor_stud_ids=shell.anchor_stud_ids,
    )
