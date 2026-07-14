"""Reusable drawer-bank geometry, machining, hardware, and load semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import pi

from .catalogs import (
    AssemblyFastenerProduct,
    DrawerLockingDeviceProduct,
    DrawerPullProduct,
    DrawerRunnerProduct,
    LateralStabilizerProduct,
    get_drawer_locking_device,
    get_drawer_pull,
    get_drawer_runner,
    get_assembly_fastener,
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
_LB_PER_KG = 2.2046226218
_STEEL_DENSITY_KG_M3 = 7850.0


@dataclass(frozen=True)
class DrawerCellModel:
    """One independently operable drawer within a reusable bank."""

    cell_id: str
    front_height_mm: float
    box_height_mm: float
    contents_load_lb: float
    wood_mass_kg: float
    moving_hardware_mass_kg: float
    moving_mass_kg: float
    calculated_moving_load_lb: float
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
    joinery_fastener: AssemblyFastenerProduct
    front_edge_reveal_mm: float
    front_gap_mm: float
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


def solid_fastener_mass_upper_bound_kg(
    diameter_mm: float,
    length_mm: float,
    quantity: int,
) -> float:
    """Return a conservative solid-steel cylinder mass for small fasteners."""

    volume_m3 = pi * (diameter_mm / 2) ** 2 * length_mm * quantity * 1e-9
    return volume_m3 * _STEEL_DENSITY_KG_M3


def _pull_solid_envelope_mass_kg(pull: DrawerPullProduct) -> float:
    """Bound pull mass as a solid bar plus two solid mounting legs."""

    cross_width, cross_height = pull.cross_section_mm
    leg_length = max(pull.height_mm - cross_height, 0.0)
    solid_length = pull.overall_length_mm + 2 * leg_length
    volume_m3 = cross_width * cross_height * solid_length * 1e-9
    return volume_m3 * pull.material_density_upper_bound_kg_m3


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
    front_attachment_fastener_mass_upper_bound_kg: float,
    front_edge_reveal_mm: float,
    front_gap_mm: float,
) -> DrawerBankModel:
    """Build a drawer bank using only its declared zone and product adapters."""

    for value, name in (
        (opening_width_mm, "opening_width_mm"),
        (opening_height_mm, "opening_height_mm"),
        (inside_depth_mm, "inside_depth_mm"),
        (front_width_mm, "front_width_mm"),
        (front_thickness_mm, "front_thickness_mm"),
        (material_density_kg_m3, "material_density_kg_m3"),
        (front_attachment_fastener_mass_upper_bound_kg,
         "front_attachment_fastener_mass_upper_bound_kg"),
        (front_edge_reveal_mm, "front_edge_reveal_mm"),
        (front_gap_mm, "front_gap_mm"),
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
    joinery_fastener = get_assembly_fastener(
        "hafele_confirmat_7x50_264_42_190@2026.1"
    )

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
    required_reveals = 2 * front_edge_reveal_mm + (
        max(len(declaration.cells) - 1, 0) * front_gap_mm
    )
    if declared_front_total + required_reveals > opening_height_mm + 1e-6:
        raise ValueError(
            "drawer fronts and required reveals exceed the declared opening height"
        )

    front_bottom_by_cell: dict[str, float] = {}
    cursor_z = front_origin_mm[2] + front_edge_reveal_mm
    for cell in reversed(declaration.cells):
        front_bottom_by_cell[cell.cell_id] = cursor_z
        cursor_z += cell.front_height_mm + front_gap_mm

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

        # Two mechanically fixed butt joints at the front and two at the back.
        # The fastener centerlines stay above the captured-bottom groove; the
        # receiving edge is named so a row cannot silently account only for
        # the through-hole in the side panel.
        lower_joinery_y = max(
            38.1,
            runner.bottom_recess_mm + _BOTTOM_THICKNESS_MM + 10.0,
        )
        upper_joinery_y = cell.box_height_mm - 25.4
        if upper_joinery_y <= lower_joinery_y:
            raise ValueError(
                f"drawer {cell.cell_id!r} box height {cell.box_height_mm:g} mm "
                "cannot fit two corner fasteners clear of the bottom groove"
            )
        for side, handed in ((side_left, "left"), (side_right, "right")):
            for receiving, end_x, end_name in (
                (box_front, _SIDE_THICKNESS_MM / 2, "front"),
                (box_back, runner.nominal_length_mm - _SIDE_THICKNESS_MM / 2,
                 "back"),
            ):
                cell_machining.append(MachiningFeature(
                    feature_id=(f"{side.part_id}.confirmat_{end_name}"),
                    kind="drawer_box_confirmat_step_drill",
                    part_id=side.part_id,
                    location_mm=(end_x, lower_joinery_y),
                    diameter_mm=joinery_fastener.blind_pilot_diameter_mm,
                    depth_mm=(joinery_fastener.length_mm
                              - _SIDE_THICKNESS_MM),
                    pitch_mm=upper_joinery_y - lower_joinery_y,
                    count=2,
                    source=joinery_fastener.product_id,
                    width_mm=joinery_fastener.through_shank_diameter_mm,
                    length_mm=joinery_fastener.countersink_diameter_mm,
                    face="outside",
                    coordinate_system=(
                        f"{handed} drawer-side outside face; "
                        "origin=front-bottom corner; +X=rearward/cut-list "
                        "length; +Y=up/cut-list width"
                    ),
                    pitch_axis="Y",
                    receiving_part_id=receiving.part_id,
                ))

        for grooved_part in (side_left, side_right, box_front, box_back):
            if "side_" in grooved_part.role:
                groove_datum = (
                    "drawer-side inside face; origin=front-bottom corner; "
                    "+X=rearward/cut-list length; +Y=up/cut-list width"
                )
            else:
                groove_datum = (
                    "drawer-front/back inside face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                )
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
                coordinate_system=groove_datum,
            ))
        for handed, x_location in (
            ("left", 0.0),
            ("right", box_back.length_mm - runner.minimum_rear_notch_mm),
        ):
            cell_machining.append(MachiningFeature(
                feature_id=f"{box_back.part_id}.runner_rear_notch_{handed}",
                kind="runner_rear_notch",
                part_id=box_back.part_id,
                location_mm=(x_location, 0.0),
                depth_mm=runner.minimum_rear_notch_height_mm,
                width_mm=runner.minimum_rear_notch_mm,
                source=runner.product_id,
                face="rear_face_lower_edge",
                coordinate_system=(
                    "drawer-back rear face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                ),
            ))
        for handed, x_location in (
            ("left", runner.hook_bore_inset_from_side_mm),
            ("right", inside_box_width - runner.hook_bore_inset_from_side_mm),
        ):
            cell_machining.append(MachiningFeature(
                feature_id=f"{box_back.part_id}.runner_hook_{handed}",
                kind="runner_hook_bore",
                part_id=box_back.part_id,
                location_mm=(x_location, runner.hook_bore_height_from_bottom_mm),
                diameter_mm=runner.hook_bore_mm[0],
                depth_mm=runner.hook_bore_mm[1],
                source=runner.product_id,
                face="rear",
                coordinate_system=(
                    "drawer-back rear face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                ),
            ))
        for handed in ("left", "right"):
            for bore_index in range(1, locking_device.pilot_bores_per_device + 1):
                cell_machining.append(MachiningFeature(
                    feature_id=(f"{box_front.part_id}.locking_device_{handed}_"
                                f"pilot_{bore_index}"),
                    kind="locking_device_bore",
                    part_id=box_front.part_id,
                    location_mm=(),
                    diameter_mm=locking_device.pilot_bore_diameter_mm,
                    depth_mm=locking_device.pilot_bore_depth_mm,
                    source=locking_device.product_id,
                    face=f"{handed}_front_corner_at_75_deg",
                    coordinate_system=(
                        f"Blum {locking_device.template_sku} template at "
                        "drawer front corner"
                    ),
                ))
        for mounting_part_id in mounting_part_ids:
            for station in runner.required_fixing_stations_mm:
                side_name = "left" if mounting_part_id == mounting_part_ids[0] else "right"
                cell_machining.append(MachiningFeature(
                    feature_id=(f"{mounting_part_id}.{cell.cell_id}.runner_"
                                f"fixing_{side_name}_{station:g}"),
                    kind="runner_fixing_station",
                    part_id=mounting_part_id,
                    location_mm=(
                        station,
                        box_z - front_origin_mm[2]
                        + runner.mounting_line_mm - runner.bottom_clearance_mm,
                    ),
                    diameter_mm=runner.installation_pilot_diameter_mm,
                    depth_mm=runner.installation_pilot_depth_mm,
                    source=runner.product_id,
                    face="inside",
                    coordinate_system=(
                        "cabinet-side inside face; origin=front-bottom of side "
                        "blank; +X=rearward/cut-list width; "
                        "+Y=up/cut-list length"
                    ),
                ))
        for index, location in enumerate((
            (inside_box_width * 0.25, cell.box_height_mm * 0.25),
            (inside_box_width * 0.75, cell.box_height_mm * 0.25),
            (inside_box_width * 0.25, cell.box_height_mm * 0.75),
            (inside_box_width * 0.75, cell.box_height_mm * 0.75),
        ), start=1):
            cell_machining.append(MachiningFeature(
                feature_id=f"{box_front.part_id}.applied_front_attachment_{index}",
                kind="applied_front_attachment",
                part_id=box_front.part_id,
                location_mm=location,
                diameter_mm=5.0,
                depth_mm=box_front.thickness_mm,
                source="drawer_front.applied",
                face="inside",
                coordinate_system=(
                    "drawer box-front inside face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                ),
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
                coordinate_system=(
                    "applied-front finished face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                ),
            ))
        stabilizer_system_id = f"{namespace}.{cell.cell_id}.lateral_stabilizer"
        cell_machining.extend((
            MachiningFeature(
                feature_id=f"{stabilizer_system_id}.gear_rack_cut",
                kind="stabilizer_gear_rack_cut",
                part_id=stabilizer_system_id,
                location_mm=(0.0,),
                length_mm=stabilizer.gear_rack_length_mm,
                source=stabilizer.product_id,
                face="hardware_stock",
                coordinate_system=(
                    "hardware stock; origin=one cut end; +X=stock length"
                ),
            ),
            MachiningFeature(
                feature_id=f"{stabilizer_system_id}.linkage_rod_cut",
                kind="stabilizer_linkage_rod_cut",
                part_id=stabilizer_system_id,
                location_mm=(0.0,),
                length_mm=(opening_width_mm
                           - stabilizer.linkage_rod_cut_deduction_mm),
                source=stabilizer.product_id,
                face="hardware_stock",
                coordinate_system=(
                    "hardware stock; origin=one cut end; +X=stock length"
                ),
            ),
        ))

        related_box_parts = tuple(part.part_id for part in cell_parts[:5])
        cell_hardware.extend((
            HardwareSystem(
                system_id=f"{namespace}.{cell.cell_id}.box_joinery_confirmats",
                kind="drawer_box_joinery_fastener",
                product_id=joinery_fastener.product_id,
                quantity=8,
                related_parts=(
                    side_left.part_id, side_right.part_id,
                    box_front.part_id, box_back.part_id,
                ),
                evidence="manufacturer_rated",
                source_url=joinery_fastener.source_url,
            ),
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
                system_id=f"{namespace}.{cell.cell_id}.runner_installation_screws",
                kind="drawer_runner_installation_screw",
                product_id=runner.installation_screw_product_id,
                quantity=2 * runner.installation_screws_per_runner,
                related_parts=mounting_part_ids,
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
                system_id=(f"{namespace}.{cell.cell_id}."
                           "locking_device_installation_screws"),
                kind="drawer_locking_device_screw",
                product_id=locking_device.installation_screw_product_id,
                quantity=(locking_device.quantity_per_drawer
                          * locking_device.installation_screw_quantity_per_device),
                related_parts=(bottom.part_id, box_front.part_id),
                evidence="manufacturer_rated",
                source_url=locking_device.source_url,
            ),
            HardwareSystem(
                system_id=stabilizer_system_id,
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
            HardwareSystem(
                system_id=f"{namespace}.{cell.cell_id}.pull_mounting_screws",
                kind="drawer_pull_mounting_screw",
                product_id=pull.mounting_screw_product_id,
                quantity=(pull.quantity_per_drawer
                          * pull.mounting_screw_quantity_per_pull),
                related_parts=(applied_front.part_id,),
                evidence="manufacturer_rated",
                source_url=pull.mounting_screw_source_url,
            ),
        ))

        wood_mass = sum(
            part.length_mm * part.width_mm * part.thickness_mm * 1e-9
            * material_density_kg_m3
            for part in cell_parts
        )
        moving_hardware_mass = (
            _pull_solid_envelope_mass_kg(pull)
            + locking_device.quantity_per_drawer
            * locking_device.mass_per_device_kg
            + stabilizer.shipping_mass_kg
            + solid_fastener_mass_upper_bound_kg(
                locking_device.installation_screw_diameter_mm,
                locking_device.installation_screw_length_mm,
                locking_device.quantity_per_drawer
                * locking_device.installation_screw_quantity_per_device,
            )
            + solid_fastener_mass_upper_bound_kg(
                pull.thread_diameter_mm,
                pull.mounting_screw_length_mm,
                pull.quantity_per_drawer
                * pull.mounting_screw_quantity_per_pull,
            )
            + front_attachment_fastener_mass_upper_bound_kg
            + solid_fastener_mass_upper_bound_kg(
                joinery_fastener.diameter_mm,
                joinery_fastener.length_mm,
                8,
            )
        )
        moving_mass = wood_mass + moving_hardware_mass
        calculated_moving_load = moving_mass * _LB_PER_KG + cell.contents_load_lb
        cells.append(DrawerCellModel(
            cell_id=cell.cell_id,
            front_height_mm=cell.front_height_mm,
            box_height_mm=cell.box_height_mm,
            contents_load_lb=cell.contents_load_lb,
            wood_mass_kg=wood_mass,
            moving_hardware_mass_kg=moving_hardware_mass,
            moving_mass_kg=moving_mass,
            calculated_moving_load_lb=calculated_moving_load,
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
        joinery_fastener=joinery_fastener,
        front_edge_reveal_mm=front_edge_reveal_mm,
        front_gap_mm=front_gap_mm,
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
