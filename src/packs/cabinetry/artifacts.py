"""Deterministic cabinet shop, assembly, and installation deliverables."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

from ...core.units import IN
from .evidence import EVIDENCE_LEVELS
from .model import CabinetModel, MachiningFeature
from .validation import (
    CabinetReport,
    anchor_embedment_facts,
    toe_attachment_facts,
)


@dataclass(frozen=True)
class CutListItem:
    part_id: str
    role: str
    description: str
    quantity: int
    length_mm: float
    width_mm: float
    thickness_mm: float
    material: str
    surface_class: str
    source_rule: str


@dataclass(frozen=True)
class EdgeBandItem:
    part_id: str
    edge: str
    operation: str
    length_mm: float
    material: str
    source_rule: str
    thickness_mm: float = 0.0
    product_id: str = ""
    cut_size_basis: str = ""


@dataclass(frozen=True)
class HardwareItem:
    system_id: str
    kind: str
    product_id: str
    quantity: int
    source_url: str
    evidence: str
    related_parts: tuple[str, ...]
    quantity_unit: str = "piece"
    procurement_note: str = ""
    procedure_url: str = ""
    procedure_label: str = ""


@dataclass(frozen=True)
class WorkStep:
    phase: int
    step_id: str
    instruction: str
    affected: tuple[str, ...] = ()
    evidence: str = "derived"

    def __post_init__(self):
        if self.evidence not in EVIDENCE_LEVELS:
            raise ValueError(
                f"unknown evidence level {self.evidence!r}; known: "
                f"{sorted(EVIDENCE_LEVELS)}"
            )


@dataclass(frozen=True)
class CabinetArtifacts:
    schema: str
    project: str
    pack: str
    profile: str
    mode: str
    release_ready: bool
    cut_list: tuple[CutListItem, ...]
    edge_banding: tuple[EdgeBandItem, ...]
    hardware_schedule: tuple[HardwareItem, ...]
    machining_schedule: tuple[MachiningFeature, ...]
    fabrication_steps: tuple[WorkStep, ...]
    assembly_steps: tuple[WorkStep, ...]
    installation_steps: tuple[WorkStep, ...]
    fabrication_ready: bool = False
    installation_use_ready: bool = False
    release_scope: str = "unified"
    release_contract: str = "unified"
    fabrication_audit: dict | None = None

    def to_dict(self) -> dict:
        payload = dataclasses.asdict(self)
        if payload["fabrication_audit"] is None:
            payload.pop("fabrication_audit")
        # Procedure metadata is additive v2 detail. Preserve the established
        # artifact bytes for product lines that have no typed procedure link.
        for item in payload["hardware_schedule"]:
            if not item["procedure_url"] and not item["procedure_label"]:
                item.pop("procedure_url")
                item.pop("procedure_label")
        # The split gate is additive.  Products using the established unified
        # release contract retain byte-identical artifact payloads.
        if payload["release_scope"] == "unified":
            payload.pop("fabrication_ready")
            payload.pop("installation_use_ready")
            payload.pop("release_scope")
            payload.pop("release_contract")
        return payload


def _toe_attachment_schedule_instruction(model) -> str:
    _rows, _product, _penetration, valid = toe_attachment_facts(model)
    if not valid:
        return (
            "STOP — the toe-attachment model or two-row station schedule is "
            "invalid. Do not drill or attach the carcass to the platform until "
            "the required validation finding passes."
        )
    rows = tuple(sorted(
        (item for item in model.machining
         if item.kind == "toe_attachment_station"),
        key=lambda item: item.receiving_part_id,
    ))
    if len(rows) != 2:  # defensive mirror of toe_attachment_facts
        raise AssertionError("valid toe attachment must contain exactly two rows")
    x_stations = tuple(
        rows[0].location_mm[0] + rows[0].pitch_mm * index
        for index in range(rows[0].count)
    )
    y_by_receiver = {
        row.receiving_part_id.rsplit(".", 1)[-1]: row.location_mm[1]
        for row in rows
    }
    return (
        "Mark the six bottom-to-toe screw centers from the cabinet-bottom "
        "front-left origin: X "
        + ", ".join(f"{value:.3f} mm" for value in x_stations)
        + f" on both rows; front-rail Y {y_by_receiver['toe_front']:.3f} mm "
        f"and rear-rail Y {y_by_receiver['toe_rear']:.3f} mm. These are "
        "layout centers for the scheduled #8 x 1-1/4 in screws. The selected "
        "adapter does not establish a pilot diameter/depth, installation "
        "torque, or connection capacity; do not invent those values."
    )


def edge_band_length(part, edge: str) -> float:
    """Return the canonical physical run for a named modeled panel edge."""
    if edge in {"left", "right", "front"}:
        # On door slabs left/right are vertical (panel width); on carcass/shelf
        # front edges the run is the panel length.
        if (part.role.startswith("door_")
                or part.role.startswith("drawer_front_")) \
                and edge in {"left", "right"}:
            return part.width_mm
        return part.length_mm
    if edge in {"top", "bottom"}:
        return part.length_mm
    raise ValueError(f"unknown edge-band edge {edge!r} on {part.part_id}")


_edge_length = edge_band_length


def _preband_cut_dimensions(part, thickness_mm: float) -> tuple[float, float]:
    """Return raw blank dimensions for finished-size modeled panels."""

    length = part.length_mm - thickness_mm * sum(
        edge in {"left", "right"} for edge in part.edge_bands
    )
    width = part.width_mm - thickness_mm * sum(
        edge in {"top", "bottom", "front", "back"}
        for edge in part.edge_bands
    )
    if length <= 0 or width <= 0:
        raise ValueError(
            f"edge band consumes the raw blank for {part.part_id}: "
            f"{length:g} x {width:g} mm"
        )
    return length, width


def _human_list(values: tuple[str, ...]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return ", ".join(values[:-1]) + f", and {values[-1]}"


def _hardware_source(model: CabinetModel, product_id: str) -> str:
    if product_id == model.hinge.product_id:
        return model.hinge.source_url
    if product_id == model.wall_anchor.product_id:
        return model.wall_anchor.source_url
    return "frameless_plywood_shop_v1@1.0.0"


def _hardware_quantity_contract(kind: str, quantity: int) -> tuple[str, str]:
    """Translate numeric hardware counts into an unambiguous buying meaning."""

    if kind in {"drawer_runner_pair", "drawer_locking_device_pair"}:
        return "handed piece", f"{quantity} handed pieces = 1 left/right pair"
    if kind in {
        "drawer_runner_installation_screw", "drawer_locking_device_screw",
        "drawer_pull_mounting_screw", "applied_front_fastener_system",
        "drawer_box_joinery_fastener", "carcass_confirmat_system",
        "toe_base_attachment_system", "wall_anchor_system",
        "cabinet_to_cabinet_connection", "wall_hung_structural_anchor_system",
    }:
        return "screw", f"{quantity} individual screws"
    if kind == "drawer_lateral_stabilizer":
        return "complete set", "1 complete stabilizer set per drawer"
    if kind == "drawer_pull":
        return "pull", "1 pull per drawer"
    if kind == "concealed_hinge_system":
        return "hinge", f"{quantity} complete hinges"
    if kind == "adjustable_shelf_support_system":
        return "support", f"{quantity} individual shelf supports"
    if kind == "wood_adhesive":
        return "container", "shop supply; quantity is one procurement line"
    return "piece", f"{quantity} individual pieces"


def _hardware_item(
    system,
    *,
    source_url: str,
    procedure_url: str = "",
    procedure_label: str = "",
) -> HardwareItem:
    unit, note = _hardware_quantity_contract(system.kind, system.quantity)
    return HardwareItem(
        system_id=system.system_id,
        kind=system.kind,
        product_id=system.product_id,
        quantity=system.quantity,
        source_url=source_url,
        evidence=system.evidence,
        related_parts=system.related_parts,
        quantity_unit=unit,
        procurement_note=note,
        procedure_url=procedure_url,
        procedure_label=procedure_label,
    )


def _drawer_hardware_procedure(model, system) -> tuple[str, str]:
    """Keep product evidence and controlling procedures as separate fields."""

    runner = model.drawer_bank.runner
    locking = model.drawer_bank.locking_device
    stabilizer = model.drawer_bank.stabilizer
    if system.kind == "drawer_runner_pair":
        return (
            runner.source_url,
            "Blum MOVENTO guide — pages 9–10 (adjustment, insertion, and "
            "removal), pages 11–15 (drawer preparation and runner mounting), "
            "and page 41 (T65.1600.01 template)",
        )
    if system.kind == "drawer_runner_installation_screw":
        return (
            runner.source_url,
            "Blum MOVENTO guide — pages 14–15 (runner stations and 606N fixing)",
        )
    if system.kind == "drawer_locking_device_pair":
        return (
            locking.source_url,
            "Blum MOVENTO guide — pages 11 and 32, plus page 41 "
            "(locking-device template)",
        )
    if system.kind == "drawer_locking_device_screw":
        return (
            locking.source_url,
            "Blum MOVENTO guide — page 11 (two-hole, 75° locking-device "
            "installation) and page 41 (T65.1600.01 template)",
        )
    if system.kind == "drawer_lateral_stabilizer":
        return (
            stabilizer.source_url,
            "Blum lateral-stabilizer installation — steps 1–9, pages 1–2",
        )
    return "", ""


def build_artifacts(model: CabinetModel, report: CabinetReport) -> CabinetArtifacts:
    if hasattr(model, "drawer_bank"):
        return _build_drawer_artifacts(model, report)

    cabinet = model.section.cabinets[0]
    fabricated = sorted(
        (
            part for part in model.parts
            if part.component_type == "plywood_panel"
            and not part.role.startswith("wall_stud_")
        ),
        key=lambda part: part.part_id,
    )
    cut_list = tuple(
        CutListItem(
            part_id=part.part_id,
            role=part.role,
            description=part.name,
            quantity=1,
            length_mm=_preband_cut_dimensions(
                part, model.profile.edge_band_thickness_mm
            )[0],
            width_mm=_preband_cut_dimensions(
                part, model.profile.edge_band_thickness_mm
            )[1],
            thickness_mm=part.thickness_mm,
            material=("prefinished plywood" if part.role != "captured_back"
                      else "1/4-inch plywood back"),
            surface_class=part.surface_class,
            source_rule=model.source_map[part.part_id].rule,
        )
        for part in fabricated
    )
    edge_banding = tuple(
        EdgeBandItem(
            part_id=part.part_id,
            edge=edge,
            operation="band",
            length_mm=_edge_length(part, edge),
            material=(f"declared {model.profile.edge_band_thickness_mm:g} mm "
                      "matching edge band; final SKU pending"),
            source_rule="surface_policy.exposed_or_semi_exposed_edge",
            thickness_mm=model.profile.edge_band_thickness_mm,
            product_id=model.profile.edge_band_product_id,
            cut_size_basis=("model geometry is finished size; cut list is the "
                            "pre-band blank"),
        )
        for part in fabricated
        for edge in part.edge_bands
    )
    hardware_schedule = tuple(
        _hardware_item(
            system,
            source_url=(system.source_url
                        or _hardware_source(model, system.product_id)),
        )
        for system in sorted(model.hardware, key=lambda item: item.system_id)
    )

    panel_ids = tuple(item.part_id for item in cut_list)
    fabrication_steps = (
        WorkStep(
            10, "fab.verify_material",
            "Verify panel thicknesses, flatness, finish faces, and the attached "
            "TSCA Title VI supplier label/lot record before breakdown.",
            panel_ids, "unknown",
        ),
        WorkStep(
            20, "fab.breakdown",
            "Break down the 3/4-inch prefinished plywood and 1/4-inch back from "
            "sheet stock using the cut list; maintain finish-face orientation "
            "and stable part ids on every label.",
            panel_ids,
        ),
        WorkStep(
            30, "fab.back_grooves",
            "Machine the captured-back grooves in the two ends, bottom, and rear "
            "stretcher from the one back-plane derivation; dry-fit the back before glue.",
            (
                f"cabinetry.{cabinet.cabinet_id}.left_end",
                f"cabinetry.{cabinet.cabinet_id}.right_end",
                f"cabinetry.{cabinet.cabinet_id}.bottom",
                f"cabinetry.{cabinet.cabinet_id}.captured_back",
            ),
        ),
        WorkStep(
            35, "fab.joinery_step_drill",
            "Machine the canonical 26-connector joinery schedule for the "
            "Häfele 7 x 50 mm Confirmat screws: 5 mm blind pilot in the receiving "
            "edge, 7 mm through-shank hole, and 10 mm countersink. Preserve the "
            "generated start coordinates, counts, and pitch; do not eyeball spacing.",
            tuple(
                item.part_id for item in model.machining
                if item.kind == "confirmat_step_drill"
            ),
            "manufacturer_rated",
        ),
        WorkStep(
            37, "fab.toe_attachment",
            _toe_attachment_schedule_instruction(model),
            (model.part("bottom").part_id,),
            "calculated",
        ),
        WorkStep(
            40, "fab.edge_band",
            f"Apply the declared {model.profile.edge_band_thickness_mm:g} mm "
            "finished-thickness edge band in the derived map, then trim and "
            "inspect. "
            "Cut-list dimensions are pre-band blanks; finished model geometry "
            "includes the band. Do not band concealed captured-back groove edges.",
            tuple(item.part_id for item in edge_banding),
        ),
        WorkStep(
            50, "fab.hinge_machine",
            "Bore the four 35 mm hinge cups 13 mm deep and drill the 37 mm-line, "
            "32 mm-spaced Blum mounting-plate holes from the pinned H002 adapter.",
            (f"cabinetry.{cabinet.cabinet_id}.door_left",
             f"cabinetry.{cabinet.cabinet_id}.door_right"),
            "manufacturer_rated",
        ),
        WorkStep(
            60, "fab.shelf_machine",
            "Drill the four 5 mm System-32 shelf-pin rows from the generated "
            "hole-row schedule; use a fence or boring jig so opposing rows agree.",
            (f"cabinetry.{cabinet.cabinet_id}.left_end",
             f"cabinetry.{cabinet.cabinet_id}.right_end"),
        ),
        WorkStep(
            70, "fab.dry_fit",
            "Dry-fit the carcass, captured back, stretchers, shelf, doors, and "
            "independent toe base; verify diagonals and hardware clearances before glue.",
            panel_ids,
        ),
    )
    assembly_steps = (
        WorkStep(
            10, "assembly.toe_base",
            "Assemble the independent toe-kick front/rear rails and two sleepers "
            "square on a flat surface with 8 of the scheduled 7 x 50 mm Confirmat "
            "screws; confirm the finished height and setback.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("toe_front", "toe_rear", "toe_left", "toe_right")),
        ),
        WorkStep(
            20, "assembly.carcass",
            "Apply Titebond Original at the manufacturer's minimum 6 mil spread "
            "to the approved joints. Lay the left side flat, attach the bottom "
            "and front stretcher within the 4-6 minute open time, and leave the "
            "right side and rear stretcher off so the captured-back grooves remain "
            "open. Install only the corresponding 7 x 50 mm Confirmats.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "front_stretcher",
                   "rear_stretcher")),
        ),
        WorkStep(
            30, "assembly.back",
            "Slide the captured back into the open left-side and bottom grooves; "
            "seat the rear stretcher groove over its top edge, add the right side "
            "to close the fourth groove, and drive the remaining Confirmats. "
            "Install the anchor strip, then pull the carcass square by matching "
            "diagonals before cure.",
            (f"cabinetry.{cabinet.cabinet_id}.captured_back",
             f"cabinetry.{cabinet.cabinet_id}.anchor_strip"),
        ),
        WorkStep(
            35, "assembly.toe_attach",
            "Seat the carcass on the shop-leveled toe base, align the two marked "
            "rows over the front/rear rail centerlines, and drive 6 GRK #8 x "
            "1-1/4 in Low Profile Cabinet screws at the scheduled centers "
            "through the bottom "
            "without entering the captured-back groove.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("bottom", "toe_front", "toe_rear")),
            "calculated",
        ),
        WorkStep(
            40, "assembly.hardware_dry_fit",
            "Dry-fit the Blum hinges, mounting plates, shelf supports, shelf, and "
            "doors; confirm the adjustment range can establish the specified reveals.",
            (f"cabinetry.{cabinet.cabinet_id}.door_left",
             f"cabinetry.{cabinet.cabinet_id}.door_right",
             f"cabinetry.{cabinet.cabinet_id}.adjustable_shelf"),
            "manufacturer_rated",
        ),
        WorkStep(
            50, "assembly.delivery",
            "Protect finished surfaces and ship the doors detached, with shelf "
            "supports and adjustment hardware bagged under the cabinet id.",
            panel_ids,
        ),
    )
    studs = ", ".join(model.anchor_stud_ids) or "no modeled stud targets"
    if model.anchor_stud_ids:
        wall_anchor_instruction = (
            "Drive the scheduled GRK cabinet screws through the anchor strip "
            f"into field-verified studs {studs}; do not substitute a drywall "
            "anchor or rely on gypsum board for structural attachment."
        )
    else:
        wall_anchor_instruction = (
            "STOP — no modeled structural anchor targets are available. Do not "
            "drill or install the cabinet until at least two field-verified stud "
            "targets and their matching modeled screw paths have been released."
        )
    installation_steps = (
        WorkStep(
            10, "install.release_gate",
            "Confirm the release report has no required FAIL or UNKNOWN finding; "
            "maintain enclosure/HVAC conditions and the completed 72-hour acclimation.",
            evidence="unknown",
        ),
        WorkStep(
            20, "install.survey",
            f"Field-verify stud centers {studs}, wall flatness, services, and the "
            "highest floor point before drilling or setting the toe base.",
            tuple(f"site.{cabinet.wall_id}.{stud_id}"
                  for stud_id in model.anchor_stud_ids),
            "unknown",
        ),
        WorkStep(
            30, "install.datum",
            "Transfer a level cabinet-top datum from the highest floor point; "
            "record deviations rather than forcing the cabinet to follow the floor.",
            evidence="unknown",
        ),
        WorkStep(
            40, "install.toe_base",
            "Set the independent toe base, shim only over stable bearing points, "
            "and make it level and plumb to the established datum before fastening.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("toe_front", "toe_rear", "toe_left", "toe_right")),
        ),
        WorkStep(
            50, "install.set_cabinet",
            "Set the carcass on the leveled base, check level and plumb in both "
            "directions, and shim the wall interface without twisting the box.",
            (f"cabinetry.{cabinet.cabinet_id}.left_end",
             f"cabinetry.{cabinet.cabinet_id}.right_end"),
        ),
        WorkStep(
            60, "install.wall_anchor",
            wall_anchor_instruction,
            tuple(f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
                  for stud_id in model.anchor_stud_ids),
            "manufacturer_rated",
        ),
        WorkStep(
            70, "install.fillers",
            "Check the exposed end and adjacent-cabinet condition; scribe and "
            "field-trim fillers where the surveyed wall requires them, preserving "
            "door swing and reveal clearance.",
        ),
        WorkStep(
            80, "install.countertop",
            "Verify both cabinet stretchers bear the field-installed countertop "
            "support plane; follow the countertop supplier's attachment and "
            "overhang requirements before fastening.",
            (f"cabinetry.{cabinet.cabinet_id}.front_stretcher",
             f"cabinetry.{cabinet.cabinet_id}.rear_stretcher"),
        ),
        WorkStep(
            90, "install.fronts",
            "Install the shelf and doors, then adjust the Blum hinges in side, "
            "height, and depth until gaps, flushness, closure, and clearances agree.",
            (f"cabinetry.{cabinet.cabinet_id}.door_left",
             f"cabinetry.{cabinet.cabinet_id}.door_right",
             f"cabinetry.{cabinet.cabinet_id}.adjustable_shelf"),
            "manufacturer_rated",
        ),
        WorkStep(
            100, "install.commission",
            "Commission the installation: recheck level, plumb, square, anchor "
            "heads, shims, countertop bearing, door cycles, soft close, shelf "
            "support seating, edge damage, and final clean-up.",
            evidence="unknown",
        ),
    )
    return CabinetArtifacts(
        schema="detailgen/cabinetry-artifacts/v2",
        project=model.project_name,
        pack="cabinetry.frameless@1.1.0",
        profile=model.profile.profile_id,
        mode=model.mode,
        # This builder has only the pack report. The project wrapper flips the
        # immutable artifact set to true only after the base geometry sweep also
        # passes; UNKNOWN-before-analysis is the same honesty rule as elsewhere.
        release_ready=False,
        cut_list=cut_list,
        edge_banding=edge_banding,
        hardware_schedule=hardware_schedule,
        machining_schedule=tuple(
            sorted(model.machining, key=lambda item: item.feature_id)
        ),
        fabrication_steps=fabrication_steps,
        assembly_steps=assembly_steps,
        installation_steps=installation_steps,
    )


def _build_drawer_artifacts(model, report: CabinetReport) -> CabinetArtifacts:
    """Build shop-to-commissioning data for a conventional drawer shipment."""

    def material_label(part) -> str:
        if abs(part.thickness_mm - model.profile.carcass_thickness_mm) <= 1e-6:
            return (
                f"{model.section.material_evidence.product} — declared primary "
                "panel; finish face/grain to verify"
            )
        return (
            f"{part.thickness_mm:g} mm plywood — product/finish not pinned; "
            "verify actual thickness and TSCA record"
        )

    fabricated = tuple(sorted(
        (part for part in model.parts if part.component_type == "plywood_panel"),
        key=lambda part: part.part_id,
    ))
    cut_list = tuple(CutListItem(
        part_id=part.part_id,
        role=part.role,
        description=part.name,
        quantity=1,
        length_mm=_preband_cut_dimensions(
            part, model.profile.edge_band_thickness_mm
        )[0],
        width_mm=_preband_cut_dimensions(
            part, model.profile.edge_band_thickness_mm
        )[1],
        thickness_mm=part.thickness_mm,
        material=material_label(part),
        surface_class=part.surface_class,
        source_rule=model.source_map[part.part_id].rule,
    ) for part in fabricated)
    edge_banding = tuple(EdgeBandItem(
        part_id=part.part_id,
        edge=edge,
        operation="band",
        length_mm=_edge_length(part, edge),
        material=(f"declared {model.profile.edge_band_thickness_mm:g} mm "
                  "matching edge band; final SKU pending"),
        source_rule="surface_policy.exposed_or_semi_exposed_edge",
        thickness_mm=model.profile.edge_band_thickness_mm,
        product_id=model.profile.edge_band_product_id,
        cut_size_basis=("model geometry is finished size; cut list is the "
                        "pre-band blank"),
    ) for part in fabricated for edge in part.edge_bands)
    hardware_schedule = tuple(
        _hardware_item(
            system,
            source_url=system.source_url,
            procedure_url=_drawer_hardware_procedure(model, system)[0],
            procedure_label=_drawer_hardware_procedure(model, system)[1],
        )
        for system in sorted(model.hardware, key=lambda item: item.system_id)
    )
    cabinet = model.section.cabinets[0]
    runner = model.drawer_bank.runner
    stabilizer = model.drawer_bank.stabilizer
    pull = model.drawer_bank.pull_product
    locking = model.drawer_bank.locking_device
    drawer_joinery = model.drawer_bank.joinery_fastener
    linkage_rod_cut_mm = (
        model.drawer_bank.opening_width_mm
        - stabilizer.linkage_rod_cut_deduction_mm
    )
    fixing_stations = _human_list(tuple(
        f"{station:g} mm" for station in runner.required_fixing_stations_mm
    ))
    locking_skus = f"{locking.left_sku} / {locking.right_sku}"
    minimum_pull_engagement_mm = (
        pull.thread_diameter_mm * pull.minimum_thread_engagement_factor
    )
    box_bottom_thickness = model.part("drawer_top_bottom").thickness_mm
    panel_ids = tuple(item.part_id for item in cut_list)
    drawer_ids = tuple(part.part_id for part in model.drawer_bank.parts)
    drawer_box_ids = tuple(
        part.part_id for part in model.drawer_bank.parts
        if not part.role.startswith("drawer_front_")
    )
    front_ids = tuple(
        part.part_id for part in model.drawer_bank.parts
        if part.role.startswith("drawer_front_")
    )
    case_ids = tuple(
        part.part_id for part in model.parts
        if part.part_id.startswith(f"cabinetry.{cabinet.cabinet_id}.")
        and part.part_id not in drawer_ids
    )
    machining_by_kind = {
        kind: tuple(item.part_id for item in model.machining if item.kind == kind)
        for kind in {item.kind for item in model.machining}
    }
    front_attachment_diameter_mm = next(
        item.diameter_mm for item in model.machining
        if item.kind == "applied_front_attachment"
    )
    identity_labels = "/".join(
        f"{cabinet.cabinet_id}-{cell.cell_id}" for cell in model.drawer_bank.cells
    )

    fabrication_steps = (
        WorkStep(
            10, "fab.verify_material",
            "Verify panel thickness, density record, flatness, finish faces, and "
            "the attached TSCA Title VI supplier label/lot record before breakdown.",
            panel_ids, "unknown",
        ),
        WorkStep(
            20, "fab.breakdown",
            "Break down sheet stock from the generated cut list, preserve finish-"
            "face orientation, and label every carcass, front, and drawer-box part "
            "with its stable part id.",
            panel_ids,
        ),
        WorkStep(
            30, "fab.shell_back_grooves",
            "Machine the four captured-back grooves from the common back-plane "
            "derivation and dry-fit the 1/4-inch back before adhesive assembly.",
            machining_by_kind.get("captured_back_groove", ()),
        ),
        WorkStep(
            35, "fab.toe_attachment",
            _toe_attachment_schedule_instruction(model),
            machining_by_kind.get("toe_attachment_station", ()),
            "calculated",
        ),
        WorkStep(
            40, "fab.drawer_bottom_grooves",
            "Machine the twelve captured drawer-bottom grooves at the generated "
            f"{runner.bottom_recess_mm:g} mm bottom recess; use a common setup "
            "so opposing parts agree.",
            machining_by_kind.get("drawer_bottom_groove", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            45, "fab.drawer_box_joinery",
            f"Step-drill the two generated positions at each front and rear "
            f"corner of every drawer side for the pinned "
            f"{drawer_joinery.diameter_mm:g} x "
            f"{drawer_joinery.length_mm:g} mm Confirmat: "
            f"{drawer_joinery.blind_pilot_diameter_mm:g} mm receiving-edge "
            f"pilot, {drawer_joinery.through_shank_diameter_mm:g} mm side-panel "
            f"shank hole, and {drawer_joinery.countersink_diameter_mm:g} mm "
            f"countersink using Häfele {drawer_joinery.tooling_sku}. Keep every "
            "lower fastener above the captured-bottom groove and use the named "
            "receiving part in the machining schedule. First drill a clamped "
            "same-lot plywood coupon at the 16 mm setting; reject splitting, "
            "delamination, or void breakout.",
            machining_by_kind.get("drawer_box_confirmat_step_drill", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            50, "fab.drawer_rear_preparation",
            f"On each drawer back—not the side panels—cut the two "
            f"{runner.minimum_rear_notch_mm:g} x "
            f"{runner.minimum_rear_notch_height_mm:g} mm lower-corner notches. "
            f"From the same back-face lower-left datum drill the two Ø"
            f"{runner.hook_bore_mm[0]:g} x {runner.hook_bore_mm[1]:g} mm hook "
            f"bores at {runner.hook_bore_inset_from_side_mm:g} mm from each "
            f"side and {runner.hook_bore_height_from_bottom_mm:g} mm above the "
            "back bottom, exactly from the MOVENTO schedule.",
            tuple(dict.fromkeys(
                machining_by_kind.get("runner_rear_notch", ())
                + machining_by_kind.get("runner_hook_bore", ())
            )),
            "manufacturer_rated",
        ),
        WorkStep(
            55, "fab.locking_device_preparation",
            f"Seat the {locking.template_sku} concealed-runner template in each "
            f"drawer front corner. Bore {locking.pilot_bores_per_device} pilot "
            f"holes per side with the Ø{locking.pilot_bore_diameter_mm:g} mm "
            f"extension bit to {locking.pilot_bore_depth_mm:g} mm depth; the "
            f"template establishes the required {locking.installation_angle_deg:g}° "
            "angle. Do not substitute freehand coordinates.",
            machining_by_kind.get("locking_device_bore", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            60, "fab.runner_fixing",
            f"Lay out and mark the generated left/right runner fixing stations "
            f"at the required {fixing_stations} coordinates measured directly "
            f"from the cabinet front; do not add the "
            f"{runner.front_setback_mm:g} mm runner-front setback to those hole "
            f"coordinates. Keep each drawer elevation tied "
            f"to its top/middle/bottom identity. Mark these for "
            f"{runner.installation_screw_sku} installation screws at "
            f"{runner.installation_screws_per_runner} screws per runner; drill "
            f"the source-backed Ø{runner.installation_pilot_diameter_mm:g} mm "
            f"pilots and drive with {runner.installation_drive}. The cited Blum "
            "schedule does not specify a cabinet-side pilot depth, so pilot "
            "depth is not claimed; set it for the selected side material and "
            "screw without breaking through.",
            model.drawer_bank.mounting_part_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            70, "fab.stabilizer_preparation",
            f"For every drawer, cut the {stabilizer.sku} stabilizer gear racks to "
            f"{stabilizer.gear_rack_length_mm:g} mm. Cut each linkage rod to "
            f"opening width minus {stabilizer.linkage_rod_cut_deduction_mm:g} mm "
            f"= {linkage_rod_cut_mm:.2f} mm; deburr cuts and retain the left/right "
            "pinion parts as a set.",
            machining_by_kind.get("stabilizer_gear_rack_cut", ())
            + machining_by_kind.get("stabilizer_linkage_rod_cut", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            80, "fab.fronts_and_pulls",
            f"Drill the four generated Ø{front_attachment_diameter_mm:g} mm "
            "through-clearance holes in each box "
            "front from inside; never drill attachment holes through the "
            "decorative applied front. Separately drill the centered Häfele pull "
            f"pattern through the applied front at exactly "
            f"{pull.hole_spacing_mm:g} mm center-to-center with a backer to "
            "protect the finished face.",
            tuple(dict.fromkeys(
                machining_by_kind.get("applied_front_attachment", ())
                + machining_by_kind.get("pull_bore", ())
            )),
            "manufacturer_rated",
        ),
        WorkStep(
            90, "fab.joinery_step_drill",
            "Machine the canonical carcass and toe-base Confirmat step-drill "
            "schedule: 5 mm blind pilot, 7 mm through-shank hole, and 10 mm "
            "countersink at every generated coordinate.",
            machining_by_kind.get("confirmat_step_drill", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            100, "fab.edge_band",
            f"Apply the declared {model.profile.edge_band_thickness_mm:g} mm "
            "finished-thickness band to every generated edge, then trim and "
            "inspect, including all "
            "four edges of the three fronts and the exposed top edges of each "
            "drawer box. Cut-list length/width values are the pre-band blanks; "
            "finished model dimensions and reveals include the band. Do not band "
            "captured-groove edges.",
            tuple(dict.fromkeys(item.part_id for item in edge_banding)),
        ),
    )

    assembly_steps = (
        WorkStep(
            10, "assembly.toe_base",
            "Assemble the independent toe-kick front/rear rails and two sleepers "
            f"square on a flat surface; verify the {cabinet.toe_kick_height_mm:g} "
            f"mm height and {cabinet.toe_kick_setback_mm:g} mm setback.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("toe_front", "toe_rear", "toe_left", "toe_right")),
        ),
        WorkStep(
            20, "assembly.carcass",
            "Apply the pinned wood adhesive within its open time. Lay the left side "
            "flat, attach the bottom and front stretcher, and leave the right side "
            "and rear stretcher off so the captured-back grooves remain open. "
            "Drive only the corresponding Confirmats without over-driving.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "front_stretcher",
                   "rear_stretcher")),
        ),
        WorkStep(
            30, "assembly.back",
            "Slide the captured back into the open left-side and bottom grooves; "
            "seat the rear stretcher groove over its top edge, add the right side "
            "to close the fourth groove, and drive the remaining Confirmats. "
            "Install the anchor strip and pull the carcass square by matching "
            "diagonals before cure.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("captured_back", "anchor_strip")),
        ),
        WorkStep(
            40, "assembly.toe_attach",
            "Seat the carcass on the shop-leveled toe platform, align the two "
            "marked rows over the front/rear rail centerlines, and drive the six "
            "scheduled toe-attachment screws through the bottom without entering "
            "the captured-back groove.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("bottom", "toe_front", "toe_rear")),
            "calculated",
        ),
        WorkStep(
            50, "assembly.drawer_boxes",
            f"Assemble each labeled box square with two Confirmat screws at "
            f"each of four corners—never a glue-only butt joint: sides around "
            f"front/back, "
            f"{box_bottom_thickness:g} mm bottom fully seated in all four "
            "grooves, equal diagonals, and rear notches/hooks unobstructed. "
            "Use no glue-strength credit on prefinished faces; the drawer-box "
            "capacity remains explicitly unqualified.",
            drawer_box_ids,
        ),
        WorkStep(
            60, "assembly.drawer_hardware",
            "Attach pinion housings and gear racks, install runner pairs at the "
            f"generated stations with {runner.installation_screws_per_runner} "
            f"{runner.installation_screw_sku} screws per runner, close the runners, "
            "fit the cut linkage rods and pinion adapters, install locking clips, "
            f"and fit the handed {locking_skus} locking devices flush to the "
            f"drawer bottom with "
            f"{locking.installation_screw_quantity_per_device} "
            f"{locking.installation_screw_sku} screws, each "
            f"{locking.installation_screw_length_mm:g} mm long, per device "
            f"at the template-controlled {locking.installation_angle_deg:g}° angle.",
            drawer_box_ids + model.drawer_bank.mounting_part_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            70, "assembly.fronts_pulls",
            "Clamp and spacer-align each applied front, then drive its four pinned "
            "short fasteners from inside the drawer box through the Ø5 mm clearance "
            "holes into—not through—the applied front. Install "
            f"one centered {pull.hole_spacing_mm:g} mm Häfele pull using its "
            f"{pull.mounting_screw_quantity_per_pull} {pull.thread} x "
            f"{pull.mounting_screw_length_mm:g} mm mounting screws "
            f"({pull.mounting_screw_sku}) with at least "
            f"{minimum_pull_engagement_mm:.2f} mm thread engagement; hand-tighten "
            "without bottoming and inspect the finished face for breakthrough.",
            front_ids + tuple(
                model.part(f"drawer_{cell.cell_id}_front").part_id
                for cell in model.drawer_bank.cells
            ),
            "manufacturer_rated",
        ),
        WorkStep(
            80, "shop.adjust_drawers",
            "Install all three drawers and use MOVENTO side-to-side, height, tilt, "
            f"and depth adjustments to establish {model.drawer_bank.front_edge_reveal_mm:.2f} "
            f"mm perimeter reveals, {model.drawer_bank.front_gap_mm:.2f} mm "
            "inter-front gaps, flush faces, and free full-extension travel.",
            drawer_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            90, "ship.record_adjustment_identity",
            f"Record each adjusted drawer/front as {identity_labels}; label the "
            "box, front, runner position, and hardware bag "
            "before disturbing the adjustment state.",
            drawer_ids,
        ),
        WorkStep(
            100, "ship.remove_drawers",
            "Release the locking devices and remove the three labeled drawer "
            "assemblies in accordance with the MOVENTO removal procedure; protect "
            "fronts and keep every handed hardware set with its identity.",
            drawer_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            110, "ship.empty_carcass",
            "Brace and ship the empty carcass and its attached toe platform as "
            "one unit without drawer weight; protect exposed edges and transport "
            "the three labeled drawers separately. The six bottom-to-toe screws "
            "remain the final modeled attachment and are not removed for shipping.",
            case_ids,
        ),
    )

    studs = ", ".join(model.anchor_stud_ids) or "no modeled stud targets"
    anchor_layout = ", ".join(
        f"{stud_id} at "
        f"{model.part(f'wall_anchor_{stud_id}').at_mm[0] - model.shell.x0_mm:.2f} mm"
        for stud_id in model.anchor_stud_ids
    )
    if model.anchor_stud_ids:
        first_anchor = model.part(f"wall_anchor_{model.anchor_stud_ids[0]}")
        anchor_height_text = (
            f"all {first_anchor.at_mm[2] - model.shell.base_z_mm:.2f} mm "
            "above the verified high-floor datum"
        )
    else:
        anchor_height_text = (
            "no anchor elevation can be released until at least two targets "
            "are modeled"
        )
    anchor_stack_mm, anchor_embedment_mm, _, _ = anchor_embedment_facts(model)
    if model.anchor_stud_ids:
        wall_anchor_instruction = (
            "Drive the scheduled GRK cabinet screws through the anchor strip "
            f"into field-verified studs {studs}. From the cabinet's left edge, "
            f"the modeled centers are {anchor_layout}, and {anchor_height_text}. "
            f"The {anchor_stack_mm / IN:.3f} in modeled stack leaves "
            f"{anchor_embedment_mm / IN:.3f} in stud embedment. Do not "
            "substitute drywall anchors or rely on gypsum board. The selected "
            "adapter provides no installation torque, so no installation torque "
            "is claimed here; follow the current GRK instructions and seat the "
            "washer head without crushing the anchor strip."
        )
    else:
        wall_anchor_instruction = (
            "STOP — no modeled structural anchor targets are available. Do not "
            "drill or install the cabinet until at least two field-verified stud "
            "targets and their matching modeled screw paths have been released."
        )
    installation_steps = (
        WorkStep(
            10, "install.release_gate",
            report.installation_use_policy.release_gate_instruction(released=False),
            evidence="unknown",
        ),
        WorkStep(
            20, "install.survey",
            f"Field-verify stud centers {studs}, wall flatness, room obstructions, "
            "services, and the highest floor point before setting the base.",
            tuple(f"site.{cabinet.wall_id}.{stud_id}"
                  for stud_id in model.anchor_stud_ids),
            "unknown",
        ),
        WorkStep(
            30, "install.datum",
            "Transfer a level cabinet-top datum from the verified high floor point "
            "and record wall/floor deviations before shimming.",
        ),
        WorkStep(
            40, "install.toe_base",
            "After the installation/use hold is cleared, set the empty cabinet "
            "and its attached toe platform together at the "
            f"{cabinet.toe_kick_setback_mm:g} mm setback, shim only "
            "over stable bearing points, and make it level and square to the datum.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("toe_front", "toe_rear", "toe_left", "toe_right")),
        ),
        WorkStep(
            50, "install.set_empty_carcass",
            "With the attached toe platform bearing on its final shims, verify the "
            "empty carcass is level and plumb with equal diagonals; shim the wall "
            "interface without twisting the box and recheck all six toe screws.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "anchor_strip")),
        ),
        WorkStep(
            60, "install.wall_anchor",
            wall_anchor_instruction,
            tuple(f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
                  for stud_id in model.anchor_stud_ids),
            "manufacturer_rated",
        ),
        WorkStep(
            80, "install.reinstall_by_identity",
            f"Reinstall each drawer by its {identity_labels} label, engage both "
            "locking devices, restore its recorded runner position, and verify the "
            "stabilizer linkage and locking clips are seated.",
            drawer_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            90, "install.commission_drawers",
            "Unloaded fit check only: cycle every drawer through full "
            f"extension; verify quiet BLUMOTION closure, "
            f"{model.drawer_bank.front_edge_reveal_mm:.2f} mm perimeter reveals, "
            f"{model.drawer_bank.front_gap_mm:.2f} mm inter-front gaps, flush faces, "
            "and no racking; inspect "
            "runner, locking-device, "
            "stabilizer, pull, front, toe, and wall-anchor fastener seating; enter "
            "measurements and corrections in the signed fit record. Do not load "
            "or use the cabinet; the declared clothing load is a design input, "
            "not an authorized commissioning load, until the whole load path is "
            "qualified.",
            drawer_ids + case_ids,
            "unknown",
        ),
        WorkStep(
            100, "install.countertop",
            "HOLD countertop attachment until the project-specific load-path "
            "review and countertop selection are complete. Then verify the front "
            "and rear stretchers provide the declared support plane and follow the "
            "countertop supplier's attachment and overhang requirements.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("front_stretcher", "rear_stretcher")),
        ),
    )
    return CabinetArtifacts(
        schema="detailgen/cabinetry-artifacts/v2",
        project=model.project_name,
        pack="cabinetry.frameless@1.1.0",
        profile=model.profile.profile_id,
        mode=model.mode,
        release_ready=False,
        cut_list=cut_list,
        edge_banding=edge_banding,
        hardware_schedule=hardware_schedule,
        machining_schedule=tuple(sorted(
            model.machining, key=lambda item: item.feature_id
        )),
        fabrication_steps=fabrication_steps,
        assembly_steps=assembly_steps,
        installation_steps=installation_steps,
        release_scope="none",
        release_contract="split",
    )


def artifact_json(artifacts: CabinetArtifacts) -> str:
    return json.dumps(
        artifacts.to_dict(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
