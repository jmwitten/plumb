"""Cabinet-domain rules with explicit proof and unknown boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.units import IN
from .evidence import EvidenceRecord
from .model import CabinetModel

_LBF_TO_N = 4.4482216153
_FT2_TO_MM2 = (12.0 * IN) ** 2


@dataclass(frozen=True)
class CabinetFinding:
    rule: str
    verdict: str
    severity: str
    message: str
    evidence_level: str
    evidence_ids: tuple[str, ...]
    affected: tuple[str, ...] = ()
    # Optional bridge into an existing base-language invariant family.  Packs
    # may add a finding only when they actually ran a domain-specific check;
    # this does not invent a base connection or silently upgrade capacity.
    base_check: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity == "required" and self.verdict in {"FAIL", "UNKNOWN"}


@dataclass(frozen=True)
class CabinetReport:
    mode: str
    findings: tuple[CabinetFinding, ...]
    evidence: tuple[EvidenceRecord, ...]

    @property
    def blocking(self) -> tuple[CabinetFinding, ...]:
        return tuple(finding for finding in self.findings if finding.blocking)

    @property
    def release_ready(self) -> bool:
        return not self.blocking

    def by_rule(self, rule: str) -> CabinetFinding:
        matches = [finding for finding in self.findings if finding.rule == rule]
        if len(matches) != 1:
            raise KeyError(
                f"expected one finding for {rule!r}, found "
                f"{[finding.rule for finding in matches]}"
            )
        return matches[0]

    def evidence_by_id(self, evidence_id: str) -> EvidenceRecord:
        try:
            return next(item for item in self.evidence
                        if item.evidence_id == evidence_id)
        except StopIteration:
            raise KeyError(f"unknown cabinet evidence {evidence_id!r}") from None

    @property
    def summary(self) -> str:
        counts: dict[tuple[str, str], int] = {}
        for finding in self.findings:
            key = (finding.severity, finding.verdict)
            counts[key] = counts.get(key, 0) + 1
        pieces = [
            f"{count} {severity} {verdict.lower()}"
            for (severity, verdict), count in sorted(counts.items())
        ]
        readiness = "ready" if self.release_ready else "blocked"
        return (
            f"Cabinet {self.mode} validation: {readiness}; "
            f"{', '.join(pieces)}. KCMA physical testing: not performed."
        )


def _shelf_deflection(model: CabinetModel) -> tuple[float, float]:
    shelf = model.part("adjustable_shelf")
    cabinet = model.section.cabinets[0]
    pressure_n_mm2 = cabinet.design_load_psf * _LBF_TO_N / _FT2_TO_MM2
    line_load_n_mm = pressure_n_mm2 * shelf.width_mm
    inertia_mm4 = shelf.width_mm * shelf.thickness_mm ** 3 / 12.0
    e_n_mm2 = model.section.material_evidence.modulus_elasticity_mpa
    deflection = (
        5.0 * line_load_n_mm * shelf.length_mm ** 4
        / (384.0 * e_n_mm2 * inertia_mm4)
    )
    limit = min(1.6 * shelf.length_mm / 305.0, 6.4)
    return deflection, limit


def _door_weight_kg(model: CabinetModel, role: str) -> float:
    door = model.part(role)
    volume_m3 = door.length_mm * door.width_mm * door.thickness_mm / 1e9
    return volume_m3 * model.section.material_evidence.density_kg_m3


def _boxes_intersect(a, b) -> bool:
    return all(a[index] < b[index + 3] and a[index + 3] > b[index]
               for index in range(3))


def _dimension_facts(model):
    cabinet = model.section.cabinets[0]
    profile = model.profile
    clear = cabinet.width_mm - 2 * profile.carcass_thickness_mm
    return clear, (
        clear > 0
        and cabinet.height_mm > cabinet.toe_kick_height_mm
        + 2 * profile.carcass_thickness_mm
        and cabinet.depth_mm > profile.stretcher_depth_mm
    )


def _oversize_panel_ids(model) -> list[str]:
    return [
        part.part_id for part in model.parts
        if part.component_type == "plywood_panel"
        and (min(part.length_mm, part.width_mm) > 48 * IN
             or max(part.length_mm, part.width_mm) > 96 * IN)
    ]


def _material_facts(model):
    material = model.section.material_evidence
    return (
        material,
        material.tsca_title_vi == "verified" and bool(material.reference),
        bool(material.product and material.property_reference),
    )


def _toe_support_facts(model):
    toe_roles = {"toe_front", "toe_rear", "toe_left", "toe_right"}
    return toe_roles, toe_roles <= {part.role for part in model.parts}


def _stud_facts(model):
    stud_by_id = {stud.stud_id: stud for stud in model.section.site.wall.studs}
    unverified = [stud_id for stud_id in model.anchor_stud_ids
                  if not stud_by_id[stud_id].verified]
    if len(model.anchor_stud_ids) < 2:
        return (
            "FAIL",
            f"Only {len(model.anchor_stud_ids)} stud center(s) fall inside the "
            "cabinet span; v1 requires at least two wall anchors.",
            "derived",
        )
    if unverified:
        return (
            "UNKNOWN",
            f"Anchor targets {unverified} are declared but not field-verified; "
            "verify stud centers before drilling.",
            "unknown",
        )
    return (
        "PASS",
        "Two or more field-verified stud centers are inside the cabinet "
        f"span: {list(model.anchor_stud_ids)}.",
        "field_verified",
    )


def _anchor_embedment_facts(model):
    profile = model.profile
    stack = (
        profile.carcass_thickness_mm + profile.back_thickness_mm
        + profile.back_inset_mm + model.section.site.wall.finish_thickness_mm
    )
    embedment = model.wall_anchor.length_mm - stack
    minimum = 1.25 * IN
    return stack, embedment, minimum, embedment + 1e-9 >= minimum


def _missing_site_conditions(model) -> list[str]:
    environment = model.section.site.environment
    missing = []
    if not environment.building_enclosed:
        missing.append("building not enclosed")
    if not environment.wet_work_complete:
        missing.append("wet work incomplete")
    if not environment.hvac_operating:
        missing.append("HVAC not operating")
    if environment.acclimation_hours < 72:
        missing.append(f"acclimation {environment.acclimation_hours:g} h < 72 h")
    if not model.section.site.floor.verified:
        missing.append("floor high point not field-verified")
    return missing


def _countertop_support_ok(model) -> bool:
    return model.section.cabinets[0].countertop_support in {
        "cabinet_stretchers", "continuous_subtop"
    }


def _validate_drawer_model(model) -> CabinetReport:
    """Validate the drawer product without running door/hinge/shelf rules."""

    findings: list[CabinetFinding] = []
    evidence: list[EvidenceRecord] = []

    def add(
        rule: str,
        verdict: str,
        severity: str,
        message: str,
        level: str,
        *,
        source: str = "",
        standard_ref: str = "",
        affected: tuple[str, ...] = (),
    ) -> None:
        evidence_id = f"evidence:{rule}"
        evidence.append(EvidenceRecord(
            evidence_id=evidence_id,
            subject=rule,
            level=level,
            statement=message,
            source=source,
            standard_ref=standard_ref,
        ))
        findings.append(CabinetFinding(
            rule=rule,
            verdict=verdict,
            severity=severity,
            message=message,
            evidence_level=level,
            evidence_ids=(evidence_id,),
            affected=affected,
        ))

    cabinet = model.section.cabinets[0]
    profile = model.profile
    bank = model.drawer_bank
    runner = bank.runner
    front_parts = tuple(model.part(f"drawer_front_{cell.cell_id}")
                        for cell in bank.cells)
    box_part_ids = tuple(part.part_id for part in bank.parts
                         if not part.role.startswith("drawer_front_"))

    clear, dimensions_ok = _dimension_facts(model)
    add(
        "cabinetry.geometry.dimensions",
        "PASS" if dimensions_ok else "FAIL",
        "required",
        (f"Cabinet dimensional relationships are coherent; clear width "
         f"{clear:.2f} mm." if dimensions_ok else
         "Cabinet dimensions do not leave a positive, buildable carcass opening."),
        "derived",
        affected=(f"cabinetry.{cabinet.cabinet_id}",),
    )

    oversize = _oversize_panel_ids(model)
    add(
        "cabinetry.fabrication.panel_stock",
        "FAIL" if oversize else "PASS",
        "required",
        (f"Panels outside the 4x8 stock envelope: {oversize}." if oversize else
         "Every generated plywood panel fits within a 4x8 stock envelope; "
         "sheet nesting and yield are separate artifacts."),
        "derived",
        affected=tuple(oversize),
    )

    material, material_ok, properties_ok = _material_facts(model)
    add(
        "cabinetry.material.tsca_title_vi",
        "PASS" if material_ok else "UNKNOWN",
        "required",
        (f"TSCA Title VI material record supplied: {material.reference}."
         if material_ok else
         "TSCA Title VI compliance is required but no verified procurement "
         "record is attached."),
        "field_verified" if material_ok else "unknown",
        source=material.reference,
        affected=("carcass_panels", "drawer_panels"),
    )
    add(
        "cabinetry.material.design_properties",
        "PASS" if properties_ok else "UNKNOWN",
        "required",
        (f"Pinned panel {material.product!r}: density "
         f"{material.density_kg_m3:g} kg/m3 and MOE "
         f"{material.modulus_elasticity_mpa:g} MPa from "
         f"{material.property_reference}." if properties_ok else
         "Drawer mass calculations require a selected panel product with a "
         "traceable density reference."),
        "manufacturer_rated" if properties_ok else "unknown",
        source=material.property_reference,
        affected=("carcass_panels", "drawer_panels"),
    )

    required_front_total = (
        bank.opening_height_mm - 2 * 1.5 - (len(front_parts) - 1) * 2.0
    )
    actual_front_total = sum(part.width_mm for part in front_parts)
    front_allocation_ok = abs(actual_front_total - required_front_total) <= 1e-6
    add(
        "cabinetry.drawer.front_allocation",
        "PASS" if front_allocation_ok else "FAIL",
        "required",
        f"Applied-front material totals {actual_front_total:.2f} mm; the "
        f"{bank.opening_height_mm:.2f} mm opening requires "
        f"{required_front_total:.2f} mm after two 1.50 mm edge reveals and "
        "two 2.00 mm inter-front gaps.",
        "derived",
        affected=tuple(part.part_id for part in front_parts),
    )

    expected_inside_width = bank.opening_width_mm - runner.inside_width_deduction_mm
    expected_outside_width = expected_inside_width + 2 * runner.maximum_side_thickness_mm
    width_parts_ok = all(
        abs(model.part(f"drawer_{cell.cell_id}_{role}").length_mm
            - expected_inside_width) <= 1e-6
        for cell in bank.cells for role in ("front", "back")
    )
    width_ok = (
        abs(bank.inside_box_width_mm - expected_inside_width) <= 1e-6
        and abs(bank.outside_box_width_mm - expected_outside_width) <= 1e-6
        and width_parts_ok
    )
    add(
        "cabinetry.drawer.width_formula",
        "PASS" if width_ok else "FAIL",
        "required",
        f"Runner formula requires inside box width {expected_inside_width:.2f} mm "
        f"and outside width {expected_outside_width:.2f} mm from the "
        f"{bank.opening_width_mm:.2f} mm opening; model values are "
        f"{bank.inside_box_width_mm:.2f} mm and "
        f"{bank.outside_box_width_mm:.2f} mm.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=box_part_ids,
    )

    side_parts = tuple(
        model.part(f"drawer_{cell.cell_id}_side_{hand}")
        for cell in bank.cells for hand in ("left", "right")
    )
    maximum_side = max(part.thickness_mm for part in side_parts)
    side_ok = maximum_side <= runner.maximum_side_thickness_mm + 1e-6
    add(
        "cabinetry.drawer.side_thickness",
        "PASS" if side_ok else "FAIL",
        "required",
        f"Maximum generated drawer-side thickness is {maximum_side:.2f} mm; "
        f"{runner.sku} permits at most {runner.maximum_side_thickness_mm:.2f} mm.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(part.part_id for part in side_parts),
    )

    depth_ok = bank.inside_depth_mm + 1e-6 >= runner.minimum_inside_depth_mm
    add(
        "cabinetry.drawer.inside_depth",
        "PASS" if depth_ok else "FAIL",
        "required",
        f"Usable inside depth is {bank.inside_depth_mm:.2f} mm; {runner.sku} "
        f"requires at least {runner.minimum_inside_depth_mm:.2f} mm for the "
        f"{runner.nominal_length_mm:.0f} mm drawer.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(bank.mounting_part_ids),
    )

    height_rows = []
    for cell in bank.cells:
        actual = max(model.part(f"drawer_{cell.cell_id}_side_{hand}").width_mm
                     for hand in ("left", "right"))
        limit = model.part(f"drawer_front_{cell.cell_id}").width_mm \
            - runner.opening_height_deduction_mm
        height_rows.append((cell.cell_id, actual, limit))
    height_ok = all(actual <= limit + 1e-6
                    for _, actual, limit in height_rows)
    add(
        "cabinetry.drawer.box_height",
        "PASS" if height_ok else "FAIL",
        "required",
        "Drawer-side heights versus opening-minus-"
        f"{runner.opening_height_deduction_mm:.0f} mm limits: "
        + ", ".join(f"{cell} {actual:.2f} mm <= {limit:.2f} mm"
                    for cell, actual, limit in height_rows) + ".",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(part.part_id for part in side_parts),
    )

    bottom_rows = []
    for cell in bank.cells:
        side = model.part(f"drawer_{cell.cell_id}_side_left")
        bottom = model.part(f"drawer_{cell.cell_id}_bottom")
        front = model.part(f"drawer_front_{cell.cell_id}")
        bottom_rows.append((
            cell.cell_id,
            bottom.at_mm[2] - side.at_mm[2],
            cell.bottom_clearance_mm,
            bottom.thickness_mm,
        ))
    bottom_ok = all(
        abs(recess - runner.bottom_recess_mm) <= 1e-6
        and abs(clearance - runner.bottom_clearance_mm) <= 1e-6
        and abs(thickness - 12.0) <= 1e-6
        for _, recess, clearance, thickness in bottom_rows
    )
    add(
        "cabinetry.drawer.bottom_geometry",
        "PASS" if bottom_ok else "FAIL",
        "required",
        "Captured-bottom geometry (recess/clearance/thickness): "
        + ", ".join(
            f"{cell} recess {recess:.2f} mm, clearance {clearance:.2f} mm, "
            f"thickness {thickness:.2f} mm"
            for cell, recess, clearance, thickness in bottom_rows
        )
        + f"; required {runner.bottom_recess_mm:.2f}/"
        f"{runner.bottom_clearance_mm:.2f}/12.00 mm.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(model.part(f"drawer_{cell.cell_id}_bottom").part_id
                       for cell in bank.cells),
    )

    rear_notches = tuple(item for item in model.machining
                         if item.kind == "runner_rear_notch")
    hook_bores = tuple(item for item in model.machining
                       if item.kind == "runner_hook_bore")
    expected_rear_count = len(bank.cells) * 2
    rear_ok = (
        len(rear_notches) == expected_rear_count
        and len(hook_bores) == expected_rear_count
        and all(item.width_mm + 1e-6 >= runner.minimum_rear_notch_mm
                for item in rear_notches)
        and all(abs(item.diameter_mm - runner.hook_bore_mm[0]) <= 1e-6
                and abs(item.location_mm[1] - runner.hook_bore_mm[1]) <= 1e-6
                for item in hook_bores)
    )
    add(
        "cabinetry.drawer.rear_preparation",
        "PASS" if rear_ok else "FAIL",
        "required",
        f"Rear preparation has runner_rear_notch {len(rear_notches)} of "
        f"{expected_rear_count} and runner_hook_bore {len(hook_bores)} of "
        f"{expected_rear_count}; required notch >= "
        f"{runner.minimum_rear_notch_mm:.0f} mm and hook bore "
        f"{runner.hook_bore_mm[0]:.0f} x {runner.hook_bore_mm[1]:.0f} mm.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(item.part_id for item in rear_notches + hook_bores)
                 or box_part_ids,
    )

    fixing = tuple(item for item in model.machining
                   if item.kind == "runner_fixing_station")
    expected_fixing_count = (
        len(bank.cells) * len(bank.mounting_part_ids)
        * len(runner.required_rear_fixing_stations_mm)
    )
    valid_x = {
        runner.front_setback_mm + station
        for station in runner.required_rear_fixing_stations_mm
    }
    fixing_ok = (
        len(fixing) == expected_fixing_count
        and all(item.part_id in bank.mounting_part_ids
                and item.location_mm[0] in valid_x for item in fixing)
    )
    add(
        "cabinetry.drawer.runner_fixing",
        "PASS" if fixing_ok else "FAIL",
        "required",
        f"Runner mounting schedule contains {len(fixing)} of "
        f"{expected_fixing_count} required fixing stations at front setback "
        f"{runner.front_setback_mm:.0f} mm plus stations "
        f"{list(runner.required_rear_fixing_stations_mm)}.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(bank.mounting_part_ids),
    )

    locking_missing = []
    stabilizer_missing = []
    for cell in bank.cells:
        locking = [system for system in model.hardware
                   if system.kind == "drawer_locking_device_pair"
                   and f".{cell.cell_id}." in system.system_id]
        if len(locking) != 1 or locking[0].quantity != 2 \
                or locking[0].product_id != bank.locking_device.product_id:
            locking_missing.append(cell.cell_id)
        stabilizers = [system for system in model.hardware
                       if system.kind == "drawer_lateral_stabilizer"
                       and f".{cell.cell_id}." in system.system_id]
        if bank.opening_width_mm >= bank.stabilizer.recommended_from_opening_mm \
                and (len(stabilizers) != 1
                     or stabilizers[0].quantity != 1
                     or stabilizers[0].product_id != bank.stabilizer.product_id):
            stabilizer_missing.append(cell.cell_id)
    add(
        "cabinetry.drawer.locking_devices",
        "FAIL" if locking_missing else "PASS",
        "required",
        (f"Missing or wrong-handed locking-device pair for cells "
         f"{locking_missing}; each requires one T51.7601 left/right pair."
         if locking_missing else
         "Each drawer has one pinned T51.7601 left/right locking-device pair."),
        "manufacturer_rated",
        source=bank.locking_device.source_url,
        affected=tuple(
            model.part(f"drawer_{cell.cell_id}_bottom").part_id
            for cell in bank.cells
        ),
    )
    add(
        "cabinetry.drawer.lateral_stabilizer",
        "FAIL" if stabilizer_missing else "PASS",
        "required",
        (f"Wide-opening stabilizer is missing or wrong for cells "
         f"{stabilizer_missing}; {bank.opening_width_mm:.2f} mm exceeds the "
         f"{bank.stabilizer.recommended_from_opening_mm:.2f} mm recommendation."
         if stabilizer_missing else
         f"All drawers carry the pinned lateral stabilizer required for the "
         f"{bank.opening_width_mm:.2f} mm opening."),
        "manufacturer_rated",
        source=bank.stabilizer.source_url,
        affected=tuple(
            model.part(f"drawer_{cell.cell_id}_bottom").part_id
            for cell in bank.cells
        ),
    )

    capacity_credit = bank.stabilizer.capacity_increase_lb
    stabilizer_capacity_ok = abs(capacity_credit) <= 1e-9
    add(
        "cabinetry.drawer.stabilizer_capacity_credit",
        "PASS" if stabilizer_capacity_ok else "FAIL",
        "required",
        f"Lateral stabilizer capacity credit is {capacity_credit:.2f} lb; "
        "required credit is 0.00 lb because synchronization does not increase "
        "runner capacity.",
        "manufacturer_rated",
        source=bank.stabilizer.source_url,
        affected=tuple(
            model.part(f"drawer_{cell.cell_id}_bottom").part_id
            for cell in bank.cells
        ),
    )

    overloaded = [cell for cell in bank.cells
                  if cell.rated_moving_load_lb > runner.dynamic_rating_lb + 1e-6]
    load_ok = not overloaded
    add(
        "cabinetry.drawer.moving_load",
        "PASS" if load_ok else "FAIL",
        "required",
        "Moving assembly plus declared contents by cell: "
        + ", ".join(f"{cell.cell_id} {cell.rated_moving_load_lb:.2f} lb"
                    for cell in bank.cells)
        + f"; selected runner dynamic rating is {runner.dynamic_rating_lb:.2f} lb.",
        "calculated",
        source=runner.source_url,
        affected=tuple(part_id for cell in bank.cells for part_id in cell.part_ids),
    )

    box_front_thickness = min(
        model.part(f"drawer_{cell.cell_id}_front").thickness_mm
        for cell in bank.cells
    )
    applied_front_thickness = min(part.thickness_mm for part in front_parts)
    stack = box_front_thickness + applied_front_thickness
    fastener_ok = (
        model.front_fastener.length_mm > box_front_thickness
        and model.front_fastener.length_mm < stack - 0.5
    )
    add(
        "cabinetry.drawer.front_fastener_stack",
        "PASS" if fastener_ok else "FAIL",
        "required",
        f"Applied-front fastener length is {model.front_fastener.length_mm:.2f} mm "
        f"through a {stack:.2f} mm material stack; it must engage the applied "
        "front without approaching the finished face within 0.50 mm.",
        "calculated",
        source=model.front_fastener.source_url,
        affected=tuple(part.part_id for part in front_parts),
    )

    fronts_by_z = sorted(front_parts, key=lambda part: part.at_mm[2])
    bottom_reveal = fronts_by_z[0].at_mm[2] \
        - (model.shell.base_z_mm + cabinet.toe_kick_height_mm)
    gaps = [fronts_by_z[index + 1].at_mm[2]
            - (fronts_by_z[index].at_mm[2] + fronts_by_z[index].width_mm)
            for index in range(len(fronts_by_z) - 1)]
    top_reveal = (model.shell.base_z_mm + cabinet.toe_kick_height_mm
                  + model.shell.body_height_mm
                  - (fronts_by_z[-1].at_mm[2] + fronts_by_z[-1].width_mm))
    left_reveals = [part.at_mm[0] - model.shell.x0_mm for part in front_parts]
    right_reveals = [cabinet.width_mm - reveal - part.length_mm
                     for reveal, part in zip(left_reveals, front_parts)]
    reveals_ok = (
        abs(bottom_reveal - 1.5) <= 1e-6
        and abs(top_reveal - 1.5) <= 1e-6
        and all(abs(gap - 2.0) <= 1e-6 for gap in gaps)
        and all(abs(reveal - 1.5) <= 1e-6
                for reveal in left_reveals + right_reveals)
    )
    add(
        "cabinetry.drawer.closed_reveals",
        "PASS" if reveals_ok else "FAIL",
        "required",
        "Closed front gaps are "
        + ", ".join(f"{gap:.2f} mm" for gap in gaps) + "; "
        f"bottom/top reveals are {bottom_reveal:.2f}/{top_reveal:.2f} mm and "
        f"side reveals are {left_reveals + right_reveals}; targets are 2.00 mm "
        "gaps and 1.50 mm edge reveals.",
        "derived",
        affected=tuple(part.part_id for part in front_parts),
    )

    collisions = []
    for cell in bank.cells:
        front = model.part(f"drawer_front_{cell.cell_id}")
        swept = (
            front.at_mm[0],
            front.at_mm[1] - runner.nominal_length_mm - front.thickness_mm,
            front.at_mm[2],
            front.at_mm[0] + front.length_mm,
            bank.opening_origin_mm[1] + runner.nominal_length_mm,
            front.at_mm[2] + front.width_mm,
        )
        collisions.extend(
            (cell.cell_id, obstruction.obstruction_id)
            for obstruction in model.declared_obstructions
            if _boxes_intersect(swept, obstruction.bounds_mm)
        )
    add(
        "cabinetry.drawer.extended_clearance",
        "FAIL" if collisions else "PASS",
        "required",
        (f"Full-extension swept envelopes collide with declared obstructions: "
         f"{collisions}." if collisions else
         "Full-extension swept envelopes are clear of every declared obstruction."),
        "calculated",
        affected=(tuple(obstruction.obstruction_id
                        for obstruction in model.declared_obstructions)
                  or tuple(part.part_id for part in front_parts)),
    )

    required_sequence = (
        "shop.adjust_drawers",
        "ship.record_adjustment_identity",
        "ship.remove_drawers",
        "ship.empty_carcass",
        "install.anchor_empty_carcass",
        "install.reinstall_by_identity",
        "install.commission_drawers",
    )
    positions = {step: index for index, step in enumerate(model.drawer_process_sequence)}
    sequence_ok = (
        all(step in positions for step in required_sequence)
        and all(positions[first] < positions[second]
                for first, second in zip(required_sequence, required_sequence[1:]))
    )
    add(
        "cabinetry.drawer.ship_install_sequence",
        "PASS" if sequence_ok else "FAIL",
        "required",
        ("Sequence adjusts drawers, record adjustment identity, removes and "
         "ships them separately, anchors the empty carcass, reinstalls by "
         "identity, and commissions in that order." if sequence_ok else
         "Sequence must record adjustment identity before drawer removal, ship "
         "and anchor the empty carcass, then reinstall by identity before "
         "commissioning."),
        "derived",
        affected=tuple(part.part_id for part in front_parts),
    )

    toe_roles, toe_ok = _toe_support_facts(model)
    add(
        "cabinetry.install.base_support",
        "PASS" if toe_ok else "FAIL",
        "required",
        ("Independent toe-kick base has front/rear rails and two sleepers "
         "supporting the floor-resting cabinet." if toe_ok else
         "Independent toe-kick base is missing a required support member."),
        "derived",
        affected=tuple(f"cabinetry.{cabinet.cabinet_id}.{role}"
                       for role in sorted(toe_roles)),
    )

    stud_verdict, stud_message, stud_level = _stud_facts(model)
    add(
        "cabinetry.install.studs", stud_verdict, "required", stud_message,
        stud_level,
        affected=tuple(f"site.{cabinet.wall_id}.{stud_id}"
                       for stud_id in model.anchor_stud_ids),
    )

    anchor_stack, embedment, min_embedment, embedment_ok = \
        _anchor_embedment_facts(model)
    add(
        "cabinetry.install.anchor_embedment",
        "PASS" if embedment_ok else "FAIL",
        "required",
        f"{model.wall_anchor.product} leaves {embedment / IN:.3f} in stud "
        f"embedment after the modeled {anchor_stack / IN:.3f} in stack; pack "
        f"minimum is {min_embedment / IN:.2f} in.",
        "calculated",
        source=model.wall_anchor.source_url,
        affected=tuple(f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
                       for stud_id in model.anchor_stud_ids),
    )

    missing_conditions = _missing_site_conditions(model)
    add(
        "cabinetry.install.site_readiness",
        "FAIL" if missing_conditions else "PASS",
        "required",
        ("Site is not ready: " + "; ".join(missing_conditions) + "."
         if missing_conditions else
         "Building enclosure, wet-work completion, operating HVAC, 72-hour "
         "acclimation, and floor high point are verified."),
        "field_verified",
        source="AWI care and storage installation prerequisites",
        standard_ref="ANSI/AWI 200 care and storage",
    )

    countertop_ok = _countertop_support_ok(model)
    add(
        "cabinetry.install.countertop_support",
        "PASS" if countertop_ok else "FAIL",
        "required",
        f"Countertop support is declared as {cabinet.countertop_support!r}.",
        "derived",
        affected=(model.part("front_stretcher").part_id,
                  model.part("rear_stretcher").part_id),
    )
    add(
        "cabinetry.performance.anchor_capacity",
        "UNKNOWN",
        "advisory",
        "The floor-supported base cabinet has anchor product, count, location, "
        "and embedment represented; lateral/withdrawal demand and connection "
        "capacity are not calculated in v1.",
        "unknown",
        source=model.wall_anchor.source_url,
        affected=tuple(f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
                       for stud_id in model.anchor_stud_ids),
    )
    add(
        "cabinetry.performance.whole_cabinet_capacity",
        "UNKNOWN",
        "advisory",
        "Runner compatibility and moving load are checked, but drawer joinery, "
        "carcass, toe platform, countertop, and complete-cabinet structural "
        "capacity have not been physically or analytically qualified.",
        "unknown",
        affected=tuple(part.part_id for part in model.parts
                       if not part.role.startswith("wall_stud_")),
    )
    add(
        "cabinetry.performance.physical_tests",
        "UNKNOWN",
        "advisory",
        "KCMA cyclic, impact, sustained-load, and finish tests were not performed; "
        "the engine makes no conformity claim.",
        "unknown",
        standard_ref="ANSI/KCMA A161.1-2022",
    )

    return CabinetReport(
        mode=model.mode,
        findings=tuple(sorted(findings, key=lambda finding: finding.rule)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
    )


def validate_model(model: CabinetModel) -> CabinetReport:
    """Run deterministic pack rules; never convert an unknown into a pass."""

    if hasattr(model, "drawer_bank"):
        return _validate_drawer_model(model)

    findings: list[CabinetFinding] = []
    evidence: list[EvidenceRecord] = []

    def add(
        rule: str,
        verdict: str,
        severity: str,
        message: str,
        level: str,
        *,
        source: str = "",
        standard_ref: str = "",
        affected: tuple[str, ...] = (),
    ) -> None:
        evidence_id = f"evidence:{rule}"
        evidence.append(EvidenceRecord(
            evidence_id=evidence_id,
            subject=rule,
            level=level,
            statement=message,
            source=source,
            standard_ref=standard_ref,
        ))
        findings.append(CabinetFinding(
            rule=rule,
            verdict=verdict,
            severity=severity,
            message=message,
            evidence_level=level,
            evidence_ids=(evidence_id,),
            affected=affected,
        ))

    cabinet = model.section.cabinets[0]
    profile = model.profile

    clear, dimensions_ok = _dimension_facts(model)
    add(
        "cabinetry.geometry.dimensions",
        "PASS" if dimensions_ok else "FAIL",
        "required",
        (f"Cabinet dimensional relationships are coherent; clear width "
         f"{clear:.2f} mm." if dimensions_ok else
         "Cabinet dimensions do not leave a positive, buildable carcass opening."),
        "derived",
        affected=(f"cabinetry.{cabinet.cabinet_id}",),
    )

    oversize = _oversize_panel_ids(model)
    add(
        "cabinetry.fabrication.panel_stock",
        "FAIL" if oversize else "PASS",
        "required",
        (f"Panels outside the 4x8 stock envelope: {oversize}." if oversize else
         "Every generated plywood panel fits within a 4x8 stock envelope; "
         "sheet nesting and yield are separate artifacts."),
        "derived",
        affected=tuple(oversize),
    )

    material, material_ok, properties_ok = _material_facts(model)
    add(
        "cabinetry.material.tsca_title_vi",
        "PASS" if material_ok else "UNKNOWN",
        "required",
        (f"TSCA Title VI material record supplied: {material.reference}." if material_ok
         else "TSCA Title VI compliance is required but no verified procurement "
              "record is attached."),
        "field_verified" if material_ok else "unknown",
        source=material.reference,
        affected=("carcass_panels", "door_panels"),
    )

    add(
        "cabinetry.material.design_properties",
        "PASS" if properties_ok else "UNKNOWN",
        "required",
        (f"Pinned panel {material.product!r}: density "
         f"{material.density_kg_m3:g} kg/m3 and MOE "
         f"{material.modulus_elasticity_mpa:g} MPa from "
         f"{material.property_reference}." if properties_ok else
         "Shelf and door calculations require a selected panel product with "
         "a traceable density and modulus reference."),
        "manufacturer_rated" if properties_ok else "unknown",
        source=material.property_reference,
        affected=("carcass_panels", "door_panels"),
    )

    overlay = model.derived_value("hinge_overlay").value
    door_t = profile.door_thickness_mm
    hinge_fit = (
        model.hinge.overlay_range_mm[0] <= overlay <= model.hinge.overlay_range_mm[1]
        and model.hinge.door_thickness_range_mm[0]
        <= door_t <= model.hinge.door_thickness_range_mm[1]
    )
    add(
        "cabinetry.hardware.hinge_fit",
        "PASS" if hinge_fit else "FAIL",
        "required",
        (f"Blum H002 overlay {overlay:.2f} mm and door thickness {door_t:.2f} "
         "mm are inside the manufacturer adapter ranges." if hinge_fit else
         f"Blum H002 cannot support overlay {overlay:.2f} mm and door thickness "
         f"{door_t:.2f} mm within its documented ranges."),
        "manufacturer_rated",
        source=model.hinge.source_url,
        affected=(model.part("door_left").part_id, model.part("door_right").part_id),
    )

    door_weights = {
        role: _door_weight_kg(model, role)
        for role in ("door_left", "door_right")
    }
    door_heights = {
        role: model.part(role).width_mm for role in ("door_left", "door_right")
    }
    door_widths = {
        role: model.part(role).length_mm for role in ("door_left", "door_right")
    }
    quantity_ok = all(
        door_weights[role] <= model.hinge.max_two_hinge_door_weight_kg
        and door_heights[role] <= model.hinge.max_two_hinge_door_height_mm
        and door_widths[role] <= model.hinge.max_chart_door_width_mm
        for role in door_weights
    )
    add(
        "cabinetry.hardware.hinge_quantity",
        "PASS" if quantity_ok else "FAIL",
        "required",
        ("Two hinges per door are within the pinned Blum chart limits "
         f"(600 mm width, 1000 mm height, 6 kg): "
         + ", ".join(f"{role} {door_widths[role]:.1f} mm wide/"
                     f"{door_heights[role]:.1f} mm high/{door_weights[role]:.2f} kg"
                     for role in sorted(door_weights)) if quantity_ok else
         "Two hinges per door exceed the pinned Blum 600 mm width, 1000 mm "
         "height, or 6 kg chart limit: "
         + ", ".join(
             f"{role} {door_widths[role]:.1f} mm wide/"
             f"{door_heights[role]:.1f} mm high/{door_weights[role]:.2f} kg"
             for role in sorted(door_weights)
         )),
        "manufacturer_rated",
        source=model.hinge.quantity_source_url,
        affected=(model.part("door_left").part_id, model.part("door_right").part_id),
    )

    deflection, deflection_limit = _shelf_deflection(model)
    shelf_ok = deflection <= deflection_limit
    add(
        "cabinetry.shelf.deflection",
        "PASS" if shelf_ok else "FAIL",
        "required",
        f"Calculated shelf deflection {deflection:.3f} mm "
        f"{'<=' if shelf_ok else '>'} {deflection_limit:.3f} mm limit under "
        f"{cabinet.design_load_psf:g} psf uniform load; calculation is not the "
        "KCMA seven-day physical test.",
        "calculated",
        standard_ref="ANSI/KCMA A161.1-2022 §5.1 reference target",
        affected=(model.part("adjustable_shelf").part_id,),
    )

    toe_roles, toe_ok = _toe_support_facts(model)
    add(
        "cabinetry.install.base_support",
        "PASS" if toe_ok else "FAIL",
        "required",
        ("Independent toe-kick base has front/rear rails and two sleepers "
         "supporting the floor-resting cabinet." if toe_ok else
         "Independent toe-kick base is missing a required support member."),
        "derived",
        affected=tuple(f"cabinetry.{cabinet.cabinet_id}.{role}"
                       for role in sorted(toe_roles)),
    )

    stud_verdict, stud_message, stud_level = _stud_facts(model)
    add(
        "cabinetry.install.studs", stud_verdict, "required", stud_message,
        stud_level,
        affected=tuple(f"site.{cabinet.wall_id}.{stud_id}"
                       for stud_id in model.anchor_stud_ids),
    )

    stack, embedment, min_embedment, embedment_ok = \
        _anchor_embedment_facts(model)
    add(
        "cabinetry.install.anchor_embedment",
        "PASS" if embedment_ok else "FAIL",
        "required",
        f"{model.wall_anchor.product} leaves {embedment / IN:.3f} in stud "
        f"embedment after the modeled {stack / IN:.3f} in stack; pack minimum "
        f"is {min_embedment / IN:.2f} in.",
        "calculated",
        source=model.wall_anchor.source_url,
        affected=tuple(
            f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
            for stud_id in model.anchor_stud_ids
        ),
    )

    missing_conditions = _missing_site_conditions(model)
    add(
        "cabinetry.install.site_readiness",
        "FAIL" if missing_conditions else "PASS",
        "required",
        ("Site is not ready: " + "; ".join(missing_conditions) + "." if missing_conditions
         else "Building enclosure, wet-work completion, operating HVAC, "
              "72-hour acclimation, and floor high point are verified."),
        "field_verified" if not missing_conditions else "field_verified",
        source="AWI care and storage installation prerequisites",
        standard_ref="ANSI/AWI 200 care and storage",
    )

    countertop_ok = _countertop_support_ok(model)
    add(
        "cabinetry.install.countertop_support",
        "PASS" if countertop_ok else "FAIL",
        "required",
        f"Countertop support is declared as {cabinet.countertop_support!r}.",
        "derived",
        affected=(model.part("front_stretcher").part_id,
                  model.part("rear_stretcher").part_id),
    )

    add(
        "cabinetry.performance.anchor_capacity",
        "UNKNOWN",
        "advisory",
        "The floor-supported base cabinet has anchor product, count, location, "
        "and embedment represented; lateral/withdrawal demand and connection "
        "capacity are not calculated in v1.",
        "unknown",
        source=model.wall_anchor.source_url,
        affected=tuple(
            f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
            for stud_id in model.anchor_stud_ids
        ),
    )
    add(
        "cabinetry.performance.physical_tests",
        "UNKNOWN",
        "advisory",
        "KCMA cyclic, impact, sustained-load, and finish tests were not performed; "
        "the engine makes no conformity claim.",
        "unknown",
        standard_ref="ANSI/KCMA A161.1-2022",
    )

    return CabinetReport(
        mode=model.mode,
        findings=tuple(sorted(findings, key=lambda finding: finding.rule)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
    )
