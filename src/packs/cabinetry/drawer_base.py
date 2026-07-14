"""Floor-supported drawer-base product composed from shell and drawer bank."""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalogs import AssemblyFastenerProduct, WallAnchorProduct, get_assembly_fastener
from .drawers import (
    DrawerBankModel,
    build_drawer_bank,
    solid_fastener_mass_upper_bound_kg,
)
from .profiles import ConstructionProfile
from .schema import CabinetrySection, DrawerBaseDecl
from .shell import (
    BaseShellModel,
    DerivedValue,
    HardwareProvenance,
    HardwareSystem,
    MachiningFeature,
    PartModel,
    Provenance,
    build_base_shell,
)


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

    def catalog_manifest(self) -> dict[str, str]:
        return {
            "drawer_box_joinery_fastener": (
                self.drawer_bank.joinery_fastener.product_id
            ),
            "front_fastener": self.front_fastener.product_id,
            "lateral_stabilizer": self.drawer_bank.stabilizer.product_id,
            "locking_device": self.drawer_bank.locking_device.product_id,
            "locking_device_screw": (
                self.drawer_bank.locking_device.installation_screw_product_id
            ),
            "pull": self.drawer_bank.pull_product.product_id,
            "pull_mounting_screw": (
                self.drawer_bank.pull_product.mounting_screw_product_id
            ),
            "runner": self.drawer_bank.runner.product_id,
            "runner_installation_screw": (
                self.drawer_bank.runner.installation_screw_product_id
            ),
            "wall_anchor": self.wall_anchor.product_id,
        }

    def catalog_source_manifest(self) -> dict[str, str]:
        return {
            "drawer_box_joinery_fastener": (
                self.drawer_bank.joinery_fastener.source_url
            ),
            "front_fastener": self.front_fastener.source_url,
            "lateral_stabilizer": self.drawer_bank.stabilizer.source_url,
            "locking_device": self.drawer_bank.locking_device.source_url,
            "locking_device_screw": self.drawer_bank.locking_device.source_url,
            "pull": self.drawer_bank.pull_product.source_url,
            "pull_mounting_screw": (
                self.drawer_bank.pull_product.mounting_screw_source_url
            ),
            "runner": self.drawer_bank.runner.source_url,
            "runner_installation_screw": self.drawer_bank.runner.source_url,
            "wall_anchor": self.wall_anchor.source_url,
        }

    def sizing_policy_manifest(self) -> tuple[str, ...]:
        return (self.section.cabinets[0].drawer_bank.sizing_policy_id,)

    def derived_fact_manifest(self) -> dict[str, object]:
        """Expose build-driving dimensions and loads as structured facts."""

        bank = self.drawer_bank
        return {
            "drawer_bank": {
                "opening_width_mm": bank.opening_width_mm,
                "opening_height_mm": bank.opening_height_mm,
                "inside_depth_mm": bank.inside_depth_mm,
                "inside_box_width_mm": bank.inside_box_width_mm,
                "outside_box_width_mm": bank.outside_box_width_mm,
                "box_length_mm": bank.box_length_mm,
                "front_edge_reveal_mm": bank.front_edge_reveal_mm,
                "front_gap_mm": bank.front_gap_mm,
            },
            "drawer_cells": {
                cell.cell_id: {
                    "front_height_mm": cell.front_height_mm,
                    "box_height_mm": cell.box_height_mm,
                    "bottom_clearance_mm": cell.bottom_clearance_mm,
                    "wood_mass_kg": cell.wood_mass_kg,
                    "moving_hardware_mass_kg": cell.moving_hardware_mass_kg,
                    "moving_mass_kg": cell.moving_mass_kg,
                    "contents_load_lb": cell.contents_load_lb,
                    "calculated_moving_load_lb": cell.calculated_moving_load_lb,
                }
                for cell in bank.cells
            },
        }


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
            shell.base_z_mm + cabinet.toe_kick_height_mm
            + shell.profile.carcass_thickness_mm,
        ),
        opening_width_mm=shell.inside_width_mm,
        opening_height_mm=shell.body_height_mm,
        inside_depth_mm=shell.inside_depth_mm,
        front_origin_mm=(
            shell.x0_mm + shell.profile.door_side_reveal_mm,
            shell.front_y_mm,
            shell.base_z_mm + cabinet.toe_kick_height_mm,
        ),
        front_width_mm=(
            cabinet.width_mm - 2 * shell.profile.door_side_reveal_mm
        ),
        front_thickness_mm=_FRONT_THICKNESS_MM,
        mounting_part_ids=(
            f"cabinetry.{cabinet.cabinet_id}.left_end",
            f"cabinetry.{cabinet.cabinet_id}.right_end",
        ),
        material_density_kg_m3=section.material_evidence.density_kg_m3,
        front_attachment_fastener_mass_upper_bound_kg=(
            solid_fastener_mass_upper_bound_kg(
                front_fastener.diameter_mm,
                front_fastener.length_mm,
                4,
            )
        ),
        front_edge_reveal_mm=shell.profile.door_top_reveal_mm,
        front_gap_mm=shell.profile.door_center_gap_mm,
    )

    drawer_hardware: list[HardwareSystem] = []
    bank_hardware_by_id = {system.system_id: system for system in bank.hardware}
    for cell in bank.cells:
        drawer_hardware.extend(
            bank_hardware_by_id[system_id] for system_id in cell.hardware_ids
        )
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
    for system in (*drawer_hardware, *shell.hardware):
        source_map[system.system_id] = HardwareProvenance(
            declared_at=f"hardware.{system.kind}",
            rule=f"hardware.{system.kind}",
            catalog_id=system.product_id,
            archetype_id=cabinet.source_archetype,
            source_url=system.source_url,
        )
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
                "front_width",
                cabinet.width_mm - 2 * shell.profile.door_side_reveal_mm,
                "mm",
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
            "install.countertop",
        ),
        anchor_stud_ids=shell.anchor_stud_ids,
    )
