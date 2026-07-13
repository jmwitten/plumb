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
        if part.role.startswith("door_") and edge in {"left", "right"}:
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


def artifact_json(artifacts: CabinetArtifacts) -> str:
    return json.dumps(
        artifacts.to_dict(), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
