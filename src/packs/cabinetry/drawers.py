"""Reusable drawer-bank geometry, machining, hardware, and load semantics."""

from __future__ import annotations

from dataclasses import dataclass, field

from .catalogs import (
    DrawerLockingDeviceProduct,
    DrawerPullProduct,
    DrawerRunnerProduct,
    LateralStabilizerProduct,
    get_drawer_locking_device,
    get_drawer_pull,
    get_drawer_runner,
    get_lateral_stabilizer,
)
from .schema import DrawerBankDecl
from .shell import (
    DerivedValue,
    HardwareSystem,
    MachiningFeature,
    PartModel,
    Provenance,
    params,
)


_SIDE_THICKNESS_MM = 16.0
_BOTTOM_THICKNESS_MM = 12.0
_BOTTOM_GROOVE_DEPTH_MM = 6.0
_FRONT_EDGE_REVEAL_MM = 1.5
_FRONT_GAP_MM = 2.0
_MOVING_HARDWARE_ALLOWANCE_KG = 0.25
_LB_PER_KG = 2.2046226218


@dataclass(frozen=True)
class DrawerCellModel:
    """One independently operable drawer within a reusable bank."""

    cell_id: str
    front_height_mm: float
    box_height_mm: float
    contents_load_lb: float
    moving_mass_kg: float
    rated_moving_load_lb: float
    bottom_clearance_mm: float
    part_ids: tuple[str, ...]
    machining_ids: tuple[str, ...]
    hardware_ids: tuple[str, ...]


@dataclass(frozen=True)
class DrawerBankModel:
    """A parent-agnostic bank that can be placed in a cabinet or vanity zone."""

    namespace: str
    opening_origin_mm: tuple[float, float, float]
    opening_width_mm: float
    opening_height_mm: float
    inside_depth_mm: float
    outside_box_width_mm: float
    inside_box_width_mm: float
    box_length_mm: float
    runner: DrawerRunnerProduct
    locking_device: DrawerLockingDeviceProduct
    stabilizer: LateralStabilizerProduct
    pull_product: DrawerPullProduct
    cells: tuple[DrawerCellModel, ...]
    parts: tuple[PartModel, ...]
    machining: tuple[MachiningFeature, ...]
    hardware: tuple[HardwareSystem, ...]
    derived: tuple[DerivedValue, ...]
    mounting_part_ids: tuple[str, ...]
    source_map: dict[str, Provenance] = field(compare=True)

    def part(self, role: str) -> PartModel:
        """Return the uniquely named bank part for a stable semantic role."""

        for part in self.parts:
            if part.role == role:
                return part
        raise KeyError(role)


def _positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {value!r}")


def build_drawer_bank(
    declaration: DrawerBankDecl,
    *,
    namespace: str,
    opening_origin_mm: tuple[float, float, float],
    opening_width_mm: float,
    opening_height_mm: float,
    inside_depth_mm: float,
    front_origin_mm: tuple[float, float, float],
    front_width_mm: float,
    front_thickness_mm: float,
    mounting_part_ids: tuple[str, ...],
    material_density_kg_m3: float,
) -> DrawerBankModel:
    """Build a drawer bank using only its declared zone and product adapters."""

    for value, name in (
        (opening_width_mm, "opening_width_mm"),
        (opening_height_mm, "opening_height_mm"),
        (inside_depth_mm, "inside_depth_mm"),
        (front_width_mm, "front_width_mm"),
        (front_thickness_mm, "front_thickness_mm"),
        (material_density_kg_m3, "material_density_kg_m3"),
    ):
        _positive(value, name)
    if not namespace.strip():
        raise ValueError("namespace must be non-empty")
    if len(mounting_part_ids) != 2:
        raise ValueError("mounting_part_ids must contain left and right sides")

    runner = get_drawer_runner(declaration.runner_product_id)
    locking_device = get_drawer_locking_device(
        declaration.locking_device_product_id
    )
    stabilizer = get_lateral_stabilizer(declaration.stabilizer_product_id)
    pull = get_drawer_pull(declaration.pull_product_id)

    if _SIDE_THICKNESS_MM > runner.maximum_side_thickness_mm:
        raise ValueError(
            f"drawer side thickness {_SIDE_THICKNESS_MM:g} mm exceeds "
            f"{runner.product_id} maximum {runner.maximum_side_thickness_mm:g} mm"
        )
    if inside_depth_mm < runner.minimum_inside_depth_mm:
        raise ValueError(
            f"inside depth {inside_depth_mm:g} mm is less than the "
            f"{runner.product_id} minimum {runner.minimum_inside_depth_mm:g} mm"
        )
    if opening_width_mm > stabilizer.maximum_opening_mm:
        raise ValueError(
            f"opening width {opening_width_mm:g} mm exceeds the "
            f"{stabilizer.product_id} maximum {stabilizer.maximum_opening_mm:g} mm"
        )

    inside_box_width = opening_width_mm - runner.inside_width_deduction_mm
    outside_box_width = inside_box_width + 2 * _SIDE_THICKNESS_MM
    if inside_box_width < locking_device.minimum_inside_drawer_width_mm:
        raise ValueError(
            f"inside drawer width {inside_box_width:g} mm is less than the "
            f"{locking_device.product_id} minimum "
            f"{locking_device.minimum_inside_drawer_width_mm:g} mm"
        )

    declared_front_total = sum(cell.front_height_mm for cell in declaration.cells)
    required_reveals = 2 * _FRONT_EDGE_REVEAL_MM + (
        max(len(declaration.cells) - 1, 0) * _FRONT_GAP_MM
    )
    if declared_front_total + required_reveals > opening_height_mm + 1e-6:
        raise ValueError(
            "drawer fronts and required reveals exceed the declared opening height"
        )

    front_bottom_by_cell: dict[str, float] = {}
    cursor_z = front_origin_mm[2] + _FRONT_EDGE_REVEAL_MM
    for cell in reversed(declaration.cells):
        front_bottom_by_cell[cell.cell_id] = cursor_z
        cursor_z += cell.front_height_mm + _FRONT_GAP_MM

    parts: list[PartModel] = []
    machining: list[MachiningFeature] = []
    hardware: list[HardwareSystem] = []
    cells: list[DrawerCellModel] = []
    source_map: dict[str, Provenance] = {}
    bottom_blank_width = inside_box_width + 2 * _BOTTOM_GROOVE_DEPTH_MM
    inside_box_depth = runner.nominal_length_mm - 2 * _SIDE_THICKNESS_MM
    bottom_blank_depth = inside_box_depth + 2 * _BOTTOM_GROOVE_DEPTH_MM
    x_clearance = (opening_width_mm - outside_box_width) / 2
    display_namespace = namespace.split(".", 1)[-1]

    for cell in declaration.cells:
        cell_parts: list[PartModel] = []
        cell_machining: list[MachiningFeature] = []
        cell_hardware: list[HardwareSystem] = []
        box_z = max(
            front_bottom_by_cell[cell.cell_id] + runner.bottom_clearance_mm,
            opening_origin_mm[2] + runner.bottom_clearance_mm,
        )
        box_x = opening_origin_mm[0] + x_clearance
        box_y = opening_origin_mm[1]

        def add_part(
            role: str,
            *,
            length: float,
            width: float,
            thickness: float,
            at: tuple[float, float, float],
            rule: str,
            rotate: tuple[tuple[str, float], ...] = (),
            surface: str = "drawer_interior",
            bands: tuple[str, ...] = (),
        ) -> PartModel:
            part_id = f"{namespace}.{role}"
            part = PartModel(
                part_id=part_id,
                role=role,
                name=f"{display_namespace} {role.replace('_', ' ')}",
                component_type="plywood_panel",
                params=params(length=length, width=width, thickness=thickness),
                at_mm=at,
                rotate=rotate,
                length_mm=length,
                width_mm=width,
                thickness_mm=thickness,
                surface_class=surface,
                edge_bands=bands,
            )
            parts.append(part)
            cell_parts.append(part)
            source_map[part_id] = Provenance(
                declared_at=f"drawer_bank.cells.{cell.cell_id}",
                rule=rule,
                catalog_id=(pull.product_id if role == f"drawer_front_{cell.cell_id}"
                            else runner.product_id),
            )
            return part

        side_left = add_part(
            f"drawer_{cell.cell_id}_side_left",
            length=runner.nominal_length_mm,
            width=cell.box_height_mm,
            thickness=_SIDE_THICKNESS_MM,
            at=(box_x, box_y, box_z),
            rule="drawer_box.side_left",
            rotate=(("X", 90.0), ("Z", 90.0)),
            bands=("top",),
        )
        side_right = add_part(
            f"drawer_{cell.cell_id}_side_right",
            length=runner.nominal_length_mm,
            width=cell.box_height_mm,
            thickness=_SIDE_THICKNESS_MM,
            at=(box_x + outside_box_width - _SIDE_THICKNESS_MM, box_y, box_z),
            rule="drawer_box.side_right",
            rotate=(("X", 90.0), ("Z", 90.0)),
            bands=("top",),
        )
        box_front = add_part(
            f"drawer_{cell.cell_id}_front",
            length=inside_box_width,
            width=cell.box_height_mm,
            thickness=_SIDE_THICKNESS_MM,
            at=(box_x + _SIDE_THICKNESS_MM,
                box_y + _SIDE_THICKNESS_MM, box_z),
            rule="drawer_box.front",
            rotate=(("X", 90.0),),
            bands=("top",),
        )
        box_back = add_part(
            f"drawer_{cell.cell_id}_back",
            length=inside_box_width,
            width=cell.box_height_mm,
            thickness=_SIDE_THICKNESS_MM,
            at=(box_x + _SIDE_THICKNESS_MM,
                box_y + runner.nominal_length_mm, box_z),
            rule="drawer_box.back",
            rotate=(("X", 90.0),),
            bands=("top",),
        )
        bottom = add_part(
            f"drawer_{cell.cell_id}_bottom",
            length=bottom_blank_width,
            width=bottom_blank_depth,
            thickness=_BOTTOM_THICKNESS_MM,
            at=(box_x + _SIDE_THICKNESS_MM - _BOTTOM_GROOVE_DEPTH_MM,
                box_y + _SIDE_THICKNESS_MM - _BOTTOM_GROOVE_DEPTH_MM,
                box_z + runner.bottom_recess_mm),
            rule="drawer_box.captured_bottom",
        )
        applied_front = add_part(
            f"drawer_front_{cell.cell_id}",
            length=front_width_mm,
            width=cell.front_height_mm,
            thickness=front_thickness_mm,
            at=(front_origin_mm[0], front_origin_mm[1],
                front_bottom_by_cell[cell.cell_id]),
            rule="drawer_front.applied",
            rotate=(("X", 90.0),),
            surface="exposed_exterior",
            bands=("top", "bottom", "left", "right"),
        )

        for grooved_part in (side_left, side_right, box_front, box_back):
            cell_machining.append(MachiningFeature(
                feature_id=f"{grooved_part.part_id}.bottom_groove",
                kind="drawer_bottom_groove",
                part_id=grooved_part.part_id,
                location_mm=(0.0, runner.bottom_recess_mm),
                depth_mm=_BOTTOM_GROOVE_DEPTH_MM,
                width_mm=_BOTTOM_THICKNESS_MM,
                length_mm=grooved_part.length_mm,
                face="inside",
                source="drawer_box.captured_bottom",
            ))
        for side in (side_left, side_right):
            cell_machining.append(MachiningFeature(
                feature_id=f"{side.part_id}.runner_rear_notch",
                kind="runner_rear_notch",
                part_id=side.part_id,
                location_mm=(runner.nominal_length_mm - runner.minimum_rear_notch_mm,
                             0.0),
                depth_mm=runner.bottom_clearance_mm,
                width_mm=runner.minimum_rear_notch_mm,
                source=runner.product_id,
                face="rear_bottom",
            ))
        for handed, x_location in (("left", 6.0),
                                   ("right", inside_box_width - 6.0)):
            cell_machining.append(MachiningFeature(
                feature_id=f"{box_back.part_id}.runner_hook_{handed}",
                kind="runner_hook_bore",
                part_id=box_back.part_id,
                location_mm=(x_location, runner.hook_bore_mm[1]),
                diameter_mm=runner.hook_bore_mm[0],
                depth_mm=_SIDE_THICKNESS_MM,
                source=runner.product_id,
                face="rear",
            ))
            cell_machining.append(MachiningFeature(
                feature_id=f"{bottom.part_id}.locking_device_{handed}",
                kind="locking_device_bore",
                part_id=bottom.part_id,
                location_mm=(x_location, 37.0),
                diameter_mm=5.0,
                depth_mm=_BOTTOM_THICKNESS_MM,
                source=locking_device.product_id,
                face="bottom",
            ))
        for mounting_part_id in mounting_part_ids:
            for station in runner.required_rear_fixing_stations_mm:
                side_name = "left" if mounting_part_id == mounting_part_ids[0] else "right"
                cell_machining.append(MachiningFeature(
                    feature_id=(f"{mounting_part_id}.{cell.cell_id}.runner_"
                                f"fixing_{side_name}_{station:g}"),
                    kind="runner_fixing_station",
                    part_id=mounting_part_id,
                    location_mm=(runner.front_setback_mm + station,
                                 box_z - opening_origin_mm[2]
                                 + runner.mounting_line_mm),
                    diameter_mm=5.0,
                    depth_mm=13.0,
                    source=runner.product_id,
                    face="inside",
                ))
        for index, location in enumerate((
            (front_width_mm * 0.25, cell.front_height_mm * 0.25),
            (front_width_mm * 0.75, cell.front_height_mm * 0.25),
            (front_width_mm * 0.25, cell.front_height_mm * 0.75),
            (front_width_mm * 0.75, cell.front_height_mm * 0.75),
        ), start=1):
            cell_machining.append(MachiningFeature(
                feature_id=f"{applied_front.part_id}.attachment_{index}",
                kind="applied_front_attachment",
                part_id=applied_front.part_id,
                location_mm=location,
                diameter_mm=4.0,
                depth_mm=front_thickness_mm,
                source="drawer_front.applied",
                face="rear",
            ))
        pull_center_x = front_width_mm / 2
        for handed, x_location in (
            ("left", pull_center_x - pull.hole_spacing_mm / 2),
            ("right", pull_center_x + pull.hole_spacing_mm / 2),
        ):
            cell_machining.append(MachiningFeature(
                feature_id=f"{applied_front.part_id}.pull_{handed}",
                kind="pull_bore",
                part_id=applied_front.part_id,
                location_mm=(x_location, cell.front_height_mm / 2),
                diameter_mm=5.0,
                depth_mm=front_thickness_mm,
                source=pull.product_id,
                face="front",
            ))
        cell_machining.extend((
            MachiningFeature(
                feature_id=f"{bottom.part_id}.stabilizer_gear_rack_cut",
                kind="stabilizer_gear_rack_cut",
                part_id=bottom.part_id,
                location_mm=(0.0,),
                length_mm=stabilizer.gear_rack_length_mm,
                source=stabilizer.product_id,
                face="hardware_stock",
            ),
            MachiningFeature(
                feature_id=f"{bottom.part_id}.stabilizer_linkage_rod_cut",
                kind="stabilizer_linkage_rod_cut",
                part_id=bottom.part_id,
                location_mm=(0.0,),
                length_mm=(opening_width_mm
                           - stabilizer.linkage_rod_cut_deduction_mm),
                source=stabilizer.product_id,
                face="hardware_stock",
            ),
        ))

        related_box_parts = tuple(part.part_id for part in cell_parts[:5])
        cell_hardware.extend((
            HardwareSystem(
                system_id=f"{namespace}.{cell.cell_id}.runner_pair",
                kind="drawer_runner_pair",
                product_id=runner.product_id,
                quantity=2,
                related_parts=related_box_parts + mounting_part_ids,
                evidence="manufacturer_rated",
                source_url=runner.source_url,
            ),
            HardwareSystem(
                system_id=f"{namespace}.{cell.cell_id}.locking_device_pair",
                kind="drawer_locking_device_pair",
                product_id=locking_device.product_id,
                quantity=locking_device.quantity_per_drawer,
                related_parts=(bottom.part_id, box_front.part_id),
                evidence="manufacturer_rated",
                source_url=locking_device.source_url,
            ),
            HardwareSystem(
                system_id=f"{namespace}.{cell.cell_id}.lateral_stabilizer",
                kind="drawer_lateral_stabilizer",
                product_id=stabilizer.product_id,
                quantity=stabilizer.quantity_per_drawer,
                related_parts=related_box_parts + mounting_part_ids,
                evidence="manufacturer_rated",
                source_url=stabilizer.source_url,
            ),
            HardwareSystem(
                system_id=f"{namespace}.{cell.cell_id}.pull",
                kind="drawer_pull",
                product_id=pull.product_id,
                quantity=pull.quantity_per_drawer,
                related_parts=(applied_front.part_id,),
                evidence="manufacturer_rated",
                source_url=pull.source_url,
            ),
        ))

        moving_mass = sum(
            part.length_mm * part.width_mm * part.thickness_mm * 1e-9
            * material_density_kg_m3
            for part in cell_parts
        ) + _MOVING_HARDWARE_ALLOWANCE_KG
        rated_moving_load = moving_mass * _LB_PER_KG + cell.contents_load_lb
        cells.append(DrawerCellModel(
            cell_id=cell.cell_id,
            front_height_mm=cell.front_height_mm,
            box_height_mm=cell.box_height_mm,
            contents_load_lb=cell.contents_load_lb,
            moving_mass_kg=moving_mass,
            rated_moving_load_lb=rated_moving_load,
            bottom_clearance_mm=runner.bottom_clearance_mm,
            part_ids=tuple(part.part_id for part in cell_parts),
            machining_ids=tuple(feature.feature_id for feature in cell_machining),
            hardware_ids=tuple(system.system_id for system in cell_hardware),
        ))
        machining.extend(cell_machining)
        hardware.extend(cell_hardware)

    return DrawerBankModel(
        namespace=namespace,
        opening_origin_mm=opening_origin_mm,
        opening_width_mm=opening_width_mm,
        opening_height_mm=opening_height_mm,
        inside_depth_mm=inside_depth_mm,
        outside_box_width_mm=outside_box_width,
        inside_box_width_mm=inside_box_width,
        box_length_mm=runner.nominal_length_mm,
        runner=runner,
        locking_device=locking_device,
        stabilizer=stabilizer,
        pull_product=pull,
        cells=tuple(cells),
        parts=tuple(parts),
        machining=tuple(machining),
        hardware=tuple(hardware),
        derived=(
            DerivedValue(
                "inside_box_width", inside_box_width, "mm",
                ("opening_width", "runner_inside_width_deduction"),
                "drawer_runner.inside_width",
            ),
            DerivedValue(
                "outside_box_width", outside_box_width, "mm",
                ("inside_box_width", "drawer_side_thickness"),
                "drawer_box.outside_width",
            ),
            DerivedValue(
                "box_length", runner.nominal_length_mm, "mm",
                ("runner_nominal_length",), "drawer_runner.box_length",
            ),
        ),
        mounting_part_ids=mounting_part_ids,
        source_map=source_map,
    )
