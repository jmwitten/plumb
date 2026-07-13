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


def validate_model(model: CabinetModel) -> CabinetReport:
    """Run deterministic pack rules; never convert an unknown into a pass."""

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

    clear = cabinet.width_mm - 2 * profile.carcass_thickness_mm
    dimensions_ok = (
        clear > 0
        and cabinet.height_mm > cabinet.toe_kick_height_mm
        + 2 * profile.carcass_thickness_mm
        and cabinet.depth_mm > profile.stretcher_depth_mm
    )
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

    oversize = [
        part.part_id for part in model.parts
        if part.component_type == "plywood_panel"
        and (min(part.length_mm, part.width_mm) > 48 * IN
             or max(part.length_mm, part.width_mm) > 96 * IN)
    ]
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

    material = model.section.material_evidence
    material_ok = material.tsca_title_vi == "verified" and bool(material.reference)
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

    properties_ok = bool(material.product and material.property_reference)
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

    toe_roles = {"toe_front", "toe_rear", "toe_left", "toe_right"}
    toe_ok = toe_roles <= {part.role for part in model.parts}
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

    stud_by_id = {stud.stud_id: stud for stud in model.section.site.wall.studs}
    unverified = [stud_id for stud_id in model.anchor_stud_ids
                  if not stud_by_id[stud_id].verified]
    if len(model.anchor_stud_ids) < 2:
        stud_verdict = "FAIL"
        stud_message = (
            f"Only {len(model.anchor_stud_ids)} stud center(s) fall inside the "
            "cabinet span; v1 requires at least two wall anchors."
        )
        stud_level = "derived"
    elif unverified:
        stud_verdict = "UNKNOWN"
        stud_message = (
            f"Anchor targets {unverified} are declared but not field-verified; "
            "verify stud centers before drilling."
        )
        stud_level = "unknown"
    else:
        stud_verdict = "PASS"
        stud_message = (
            f"Two or more field-verified stud centers are inside the cabinet "
            f"span: {list(model.anchor_stud_ids)}."
        )
        stud_level = "field_verified"
    add(
        "cabinetry.install.studs", stud_verdict, "required", stud_message,
        stud_level,
        affected=tuple(f"site.{cabinet.wall_id}.{stud_id}"
                       for stud_id in model.anchor_stud_ids),
    )

    stack = (
        profile.carcass_thickness_mm
        + profile.back_thickness_mm
        + profile.back_inset_mm
        + model.section.site.wall.finish_thickness_mm
    )
    embedment = model.wall_anchor.length_mm - stack
    min_embedment = 1.25 * IN
    embedment_ok = embedment + 1e-9 >= min_embedment
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

    environment = model.section.site.environment
    missing_conditions: list[str] = []
    if not environment.building_enclosed:
        missing_conditions.append("building not enclosed")
    if not environment.wet_work_complete:
        missing_conditions.append("wet work incomplete")
    if not environment.hvac_operating:
        missing_conditions.append("HVAC not operating")
    if environment.acclimation_hours < 72:
        missing_conditions.append(
            f"acclimation {environment.acclimation_hours:g} h < 72 h"
        )
    if not model.section.site.floor.verified:
        missing_conditions.append("floor high point not field-verified")
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

    countertop_ok = cabinet.countertop_support in {
        "cabinet_stretchers", "continuous_subtop"
    }
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
