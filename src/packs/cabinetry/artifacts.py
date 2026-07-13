"""Deterministic cabinet shop, assembly, and installation deliverables."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

from .evidence import EVIDENCE_LEVELS
from .model import CabinetModel, MachiningFeature
from .validation import CabinetReport


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


@dataclass(frozen=True)
class HardwareItem:
    system_id: str
    kind: str
    product_id: str
    quantity: int
    source_url: str
    evidence: str
    related_parts: tuple[str, ...]


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

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _edge_length(part, edge: str) -> float:
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


def _hardware_source(model: CabinetModel, product_id: str) -> str:
    if product_id == model.hinge.product_id:
        return model.hinge.source_url
    if product_id == model.wall_anchor.product_id:
        return model.wall_anchor.source_url
    return "frameless_plywood_shop_v1@1.0.0"


def build_artifacts(model: CabinetModel, report: CabinetReport) -> CabinetArtifacts:
    if hasattr(model, "drawer_bank"):
        return _build_drawer_artifacts(model)

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
            length_mm=part.length_mm,
            width_mm=part.width_mm,
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
            material="applied matching edge band",
            source_rule="surface_policy.exposed_or_semi_exposed_edge",
        )
        for part in fabricated
        for edge in part.edge_bands
    )
    hardware_schedule = tuple(
        HardwareItem(
            system_id=system.system_id,
            kind=system.kind,
            product_id=system.product_id,
            quantity=system.quantity,
            source_url=(system.source_url
                        or _hardware_source(model, system.product_id)),
            evidence=system.evidence,
            related_parts=system.related_parts,
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
            40, "fab.edge_band",
            "Apply, trim, and inspect every edge band in the derived edge-band "
            "map; do not band concealed captured-back groove edges.",
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
            "to the approved carcass joints, seat the bottom and stretchers "
            "between the ends within the 4-6 minute open time, and install the "
            "remaining scheduled 7 x 50 mm Confirmat screws without over-driving.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "front_stretcher",
                   "rear_stretcher")),
        ),
        WorkStep(
            30, "assembly.back",
            "Slide and seat the captured back in its grooves, install the anchor "
            "strip against the back, then pull the carcass square by matching diagonals.",
            (f"cabinetry.{cabinet.cabinet_id}.captured_back",
             f"cabinetry.{cabinet.cabinet_id}.anchor_strip"),
        ),
        WorkStep(
            35, "assembly.toe_attach",
            "Seat the carcass on the shop-leveled toe base and drive 6 GRK #8 x "
            "1-1/4 in Low Profile Cabinet screws through the bottom into the front "
            "and rear toe rails at the generated three-per-rail spacing.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("bottom", "toe_front", "toe_rear")),
            "manufacturer_rated",
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
    studs = ", ".join(model.anchor_stud_ids)
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
            f"Drive the scheduled GRK cabinet screws through the anchor strip "
            f"into field-verified studs {studs}; do not substitute a drywall anchor "
            "or rely on gypsum board for structural attachment.",
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
        schema="detailgen/cabinetry-artifacts/v1",
        project=model.project_name,
        pack="cabinetry.frameless@1.0.0",
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


def _build_drawer_artifacts(model) -> CabinetArtifacts:
    """Build shop-to-commissioning data for a conventional drawer shipment."""

    fabricated = tuple(sorted(
        (part for part in model.parts if part.component_type == "plywood_panel"),
        key=lambda part: part.part_id,
    ))
    cut_list = tuple(CutListItem(
        part_id=part.part_id,
        role=part.role,
        description=part.name,
        quantity=1,
        length_mm=part.length_mm,
        width_mm=part.width_mm,
        thickness_mm=part.thickness_mm,
        material=("1/4-inch plywood back" if part.role == "captured_back"
                  else "prefinished plywood"),
        surface_class=part.surface_class,
        source_rule=model.source_map[part.part_id].rule,
    ) for part in fabricated)
    edge_banding = tuple(EdgeBandItem(
        part_id=part.part_id,
        edge=edge,
        operation="band",
        length_mm=_edge_length(part, edge),
        material="applied matching edge band",
        source_rule="surface_policy.exposed_or_semi_exposed_edge",
    ) for part in fabricated for edge in part.edge_bands)
    hardware_schedule = tuple(HardwareItem(
        system_id=system.system_id,
        kind=system.kind,
        product_id=system.product_id,
        quantity=system.quantity,
        source_url=system.source_url,
        evidence=system.evidence,
        related_parts=system.related_parts,
    ) for system in sorted(model.hardware, key=lambda item: item.system_id))
    cabinet = model.section.cabinets[0]
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
            40, "fab.drawer_bottom_grooves",
            "Machine the twelve captured drawer-bottom grooves at the generated "
            "13 mm bottom recess; use a common setup so opposing parts agree.",
            machining_by_kind.get("drawer_bottom_groove", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            50, "fab.drawer_rear_preparation",
            "Cut both 50 mm minimum rear notches and drill both 6 x 10 mm rear "
            "hook bores on each drawer exactly from the MOVENTO schedule.",
            tuple(dict.fromkeys(
                machining_by_kind.get("runner_rear_notch", ())
                + machining_by_kind.get("runner_hook_bore", ())
            )),
            "manufacturer_rated",
        ),
        WorkStep(
            60, "fab.runner_fixing",
            "Drill the generated left/right runner fixing stations at the 3 mm "
            "setback and the required 261 mm and 357 mm rear stations; keep each "
            "drawer elevation tied to its top/middle/bottom identity.",
            model.drawer_bank.mounting_part_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            70, "fab.stabilizer_preparation",
            "For every drawer, cut the 21-inch MOVENTO stabilizer gear racks to "
            "560 mm. Cut each linkage rod to opening width minus 318 mm = "
            "659.90 mm; deburr cuts and retain the left/right pinion parts as a set.",
            machining_by_kind.get("stabilizer_gear_rack_cut", ())
            + machining_by_kind.get("stabilizer_linkage_rod_cut", ()),
            "manufacturer_rated",
        ),
        WorkStep(
            80, "fab.fronts_and_pulls",
            "Drill four generated applied-front attachment holes per drawer and "
            "the centered Häfele pull pattern at exactly 224 mm center-to-center; "
            "use a backer to protect the finished face.",
            front_ids,
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
            "Apply, trim, and inspect every generated edge band, including all "
            "four edges of the three fronts and the exposed top edges of each "
            "drawer box; do not band captured-groove edges.",
            tuple(dict.fromkeys(item.part_id for item in edge_banding)),
        ),
    )

    assembly_steps = (
        WorkStep(
            10, "assembly.toe_base",
            "Assemble the independent toe-kick front/rear rails and two sleepers "
            "square on a flat surface; verify the 4-inch height and 3-inch setback.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("toe_front", "toe_rear", "toe_left", "toe_right")),
        ),
        WorkStep(
            20, "assembly.carcass",
            "Apply the pinned wood adhesive within its open time, seat the bottom "
            "and stretchers between the ends, and install the scheduled Confirmat "
            "screws without over-driving.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "front_stretcher",
                   "rear_stretcher")),
        ),
        WorkStep(
            30, "assembly.back",
            "Seat the captured back in all four grooves, install the anchor strip, "
            "and pull the carcass square by matching diagonals before cure.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("captured_back", "anchor_strip")),
        ),
        WorkStep(
            40, "assembly.toe_attach",
            "Seat the carcass on the shop-leveled toe platform and drive the six "
            "scheduled GRK #8 x 1-1/4 inch screws into the front and rear rails.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("bottom", "toe_front", "toe_rear")),
            "manufacturer_rated",
        ),
        WorkStep(
            50, "assembly.drawer_boxes",
            "Assemble each labeled box square: sides around front/back, 12 mm "
            "bottom fully seated in all four grooves, equal diagonals, and rear "
            "notches/hooks unobstructed.",
            drawer_box_ids,
        ),
        WorkStep(
            60, "assembly.drawer_hardware",
            "Attach pinion housings and gear racks, install runner pairs at the "
            "generated stations, close the runners, fit the cut linkage rods and "
            "pinion adapters, install locking clips, and fit the handed T51.7601 "
            "locking devices.",
            drawer_box_ids + model.drawer_bank.mounting_part_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            70, "assembly.fronts_pulls",
            "Attach each applied front with four pinned short fasteners and install "
            "one centered 224 mm Häfele pull using its two M4 mounting screws; "
            "inspect the finished face for breakthrough.",
            front_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            80, "shop.adjust_drawers",
            "Install all three drawers and use MOVENTO side-to-side, height, tilt, "
            "and depth adjustments to establish 1.50 mm perimeter reveals, "
            "2.00 mm inter-front gaps, flush faces, and free full-extension travel.",
            drawer_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            90, "ship.record_adjustment_identity",
            "Record each adjusted drawer/front as DB40-top, DB40-middle, or "
            "DB40-bottom; label the box, front, runner position, and hardware bag "
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
            "Ship the empty carcass and toe platform without drawer weight, brace "
            "the opening against racking, protect exposed edges, and transport the "
            "three labeled drawers separately.",
            case_ids,
        ),
    )

    studs = ", ".join(model.anchor_stud_ids)
    installation_steps = (
        WorkStep(
            10, "install.release_gate",
            "Confirm the pack release report has no required FAIL or UNKNOWN "
            "finding and retain the explicit whole-cabinet capacity limitation.",
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
            "Set the independent toe platform at the 3-inch setback, shim only "
            "over stable bearing points, and make it level and square to the datum.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("toe_front", "toe_rear", "toe_left", "toe_right")),
        ),
        WorkStep(
            50, "install.set_empty_carcass",
            "Set and level the empty carcass on the toe platform; check plumb and "
            "equal diagonals and shim the wall interface without twisting the box.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("left_end", "right_end", "bottom", "anchor_strip")),
        ),
        WorkStep(
            60, "install.wall_anchor",
            f"Drive the scheduled GRK cabinet screws through the anchor strip "
            f"into field-verified studs {studs}; do not substitute drywall "
            "anchors or rely on gypsum board.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.wall_anchor_{stud_id}"
                  for stud_id in model.anchor_stud_ids),
            "manufacturer_rated",
        ),
        WorkStep(
            70, "install.countertop",
            "Verify the front and rear stretchers provide the declared countertop "
            "support plane, then follow the countertop supplier's attachment and "
            "overhang requirements.",
            tuple(f"cabinetry.{cabinet.cabinet_id}.{role}" for role in
                  ("front_stretcher", "rear_stretcher")),
        ),
        WorkStep(
            80, "install.reinstall_by_identity",
            "Reinstall each drawer by its DB40-top/middle/bottom label, engage both "
            "locking devices, restore its recorded runner position, and verify the "
            "stabilizer linkage and locking clips are seated.",
            drawer_ids,
            "manufacturer_rated",
        ),
        WorkStep(
            90, "install.commission_drawers",
            "Commission and record acceptance: cycle every drawer through full "
            "extension; verify quiet BLUMOTION closure, 1.50 mm perimeter reveals, "
            "2.00 mm inter-front gaps, flush faces, and no racking; repeat operation "
            "with the declared 40 lb clothing load; inspect runner, locking-device, "
            "stabilizer, pull, front, toe, and wall-anchor fastener seating; enter "
            "measurements and corrections in the signed acceptance record.",
            drawer_ids + case_ids,
            "unknown",
        ),
    )
    return CabinetArtifacts(
        schema="detailgen/cabinetry-artifacts/v1",
        project=model.project_name,
        pack="cabinetry.frameless@1.0.0",
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
    )


def artifact_json(artifacts: CabinetArtifacts) -> str:
    return json.dumps(
        artifacts.to_dict(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
