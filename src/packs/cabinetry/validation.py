"""Cabinet-domain rules with explicit proof and unknown boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.units import IN
from .catalogs import get_assembly_fastener
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
class InstallationUsePolicy:
    """One sourced owner-clearance contract projected to every reader surface."""

    policy_id: str
    blocking_rules: tuple[str, ...]
    hazard_statement: str
    clearance_authority: str
    required_evidence: tuple[str, ...]
    source_url: str
    scope_source_url: str
    scope_note: str

    def reader_notice(self, *, released: bool = False) -> str:
        evidence = "; ".join(self.required_evidence)
        if released:
            return (
                "Installation/use release: PASS. Preserve the signed, "
                f"project-specific acceptance covering {evidence}, and follow "
                "its installation, inspection, loading, and use conditions."
            )
        return (
            f"{self.hazard_statement} INSTALLATION/USE HOLD: only "
            f"{self.clearance_authority} may clear this hold with signed, "
            f"project-specific acceptance covering {evidence}. "
            "Do not load, commission, or put the cabinet into service; do not "
            "anchor it or attach a countertop until that acceptance exists. "
            f"{self.scope_note}"
        )

    def release_gate_instruction(self, *, released: bool = False) -> str:
        return (
            "Confirm the fabrication/model gate has no required FAIL or UNKNOWN. "
            + self.reader_notice(released=released)
        )


@dataclass(frozen=True)
class CabinetReport:
    mode: str
    findings: tuple[CabinetFinding, ...]
    evidence: tuple[EvidenceRecord, ...]
    # Some products can be safely fabricated while project-specific structural
    # work still blocks installation and use. The typed policy is the one source
    # for blocker ownership, reader wording, clearance authority, and evidence.
    installation_use_policy: InstallationUsePolicy | None = None

    def __post_init__(self):
        if self.installation_use_policy is None:
            return
        finding_rules = {finding.rule for finding in self.findings}
        blockers = self.installation_use_policy.blocking_rules
        if not blockers:
            raise ValueError("installation/use policy must name blocking rules")
        if len(blockers) != len(set(blockers)):
            raise ValueError("installation/use policy has duplicate blocking rules")
        missing = sorted(set(blockers) - finding_rules)
        if missing:
            raise ValueError(
                "installation/use policy references unknown blocking rules: "
                f"{missing}"
            )

    @property
    def installation_use_blocking_rules(self) -> tuple[str, ...]:
        return (
            self.installation_use_policy.blocking_rules
            if self.installation_use_policy is not None else ()
        )

    @property
    def blocking(self) -> tuple[CabinetFinding, ...]:
        return tuple(finding for finding in self.findings if finding.blocking)

    @property
    def fabrication_ready(self) -> bool:
        return not self.blocking

    @property
    def installation_use_blocking(self) -> tuple[CabinetFinding, ...]:
        rules = set(self.installation_use_blocking_rules)
        return tuple(
            finding for finding in self.findings
            if finding.rule in rules and finding.verdict != "PASS"
        )

    @property
    def installation_use_ready(self) -> bool:
        return self.fabrication_ready and not self.installation_use_blocking

    @property
    def release_ready(self) -> bool:
        """Conservative compatibility alias for complete installation/use release."""

        return self.installation_use_ready

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
        if self.fabrication_ready and not self.installation_use_ready:
            readiness = "fabrication ready; installation/use held"
        else:
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


def anchor_embedment_facts(model):
    """Derive the anchor path from the placed screws and wall geometry.

    The catalog adapter supplies the intended product.  Release truth comes
    from the modeled screw instances: each must begin at the anchor-strip
    head plane, align to its declared stud, and retain the catalog geometry.
    """

    anchor_strip = model.part("anchor_strip")
    expected_head_plane_y = anchor_strip.at_mm[1] - anchor_strip.thickness_mm
    stud_front_plane_y = (
        model.section.site.wall.plane_origin_mm[1]
        + model.section.site.wall.finish_thickness_mm
    )
    expected_z = anchor_strip.at_mm[2] + anchor_strip.width_mm / 2
    studs = {
        stud.stud_id: stud for stud in model.section.site.wall.studs
    }
    anchors = []
    geometry_ok = bool(model.anchor_stud_ids)
    expected_ids = set()
    for stud_id in model.anchor_stud_ids:
        part_id = (
            f"cabinetry.{model.section.cabinets[0].cabinet_id}."
            f"wall_anchor_{stud_id}"
        )
        expected_ids.add(part_id)
        try:
            anchor = model.part(f"wall_anchor_{stud_id}")
            stud = studs[stud_id]
        except KeyError:
            geometry_ok = False
            continue
        anchors.append(anchor)
        expected_x = (
            model.section.site.wall.plane_origin_mm[0] + stud.position_mm
        )
        geometry_ok = geometry_ok and (
            anchor.part_id == part_id
            and anchor.component_type == "structural_screw"
            and anchor.rotate == (("X", 90.0),)
            and all(abs(actual - expected) <= 1e-6 for actual, expected in zip(
                anchor.at_mm,
                (expected_x, expected_head_plane_y, expected_z),
            ))
            and abs(anchor.length_mm - model.wall_anchor.length_mm) <= 1e-6
            and abs(anchor.width_mm - model.wall_anchor.diameter_mm) <= 1e-6
            and abs(anchor.thickness_mm - model.wall_anchor.diameter_mm) <= 1e-6
            and abs(anchor.params_dict().get("length", -1)
                    - model.wall_anchor.length_mm) <= 1e-6
            and abs(anchor.params_dict().get("diameter", -1)
                    - model.wall_anchor.diameter_mm) <= 1e-6
        )

    systems = tuple(
        system for system in model.hardware
        if system.kind == "wall_anchor_system"
    )
    geometry_ok = geometry_ok and (
        len(anchors) == len(model.anchor_stud_ids)
        and len(systems) == 1
        and systems[0].product_id == model.wall_anchor.product_id
        and systems[0].quantity == len(model.anchor_stud_ids)
        and set(systems[0].related_parts) == expected_ids
    )
    if anchors:
        paths = tuple(stud_front_plane_y - anchor.at_mm[1]
                      for anchor in anchors)
        stack = max(paths)
        embedment = min(
            anchor.length_mm - path
            for anchor, path in zip(anchors, paths)
        )
    else:
        stack = stud_front_plane_y - expected_head_plane_y
        embedment = 0.0
    minimum = 1.25 * IN
    return (
        stack,
        embedment,
        minimum,
        geometry_ok and embedment + 1e-9 >= minimum,
    )


def _anchor_affected(model) -> tuple[str, ...]:
    cabinet_id = model.section.cabinets[0].cabinet_id
    return (
        tuple(
            f"cabinetry.{cabinet_id}.wall_anchor_{stud_id}"
            for stud_id in model.anchor_stud_ids
        )
        or (model.part("anchor_strip").part_id,)
    )


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


def _expanded_locations_in_bounds(row, part) -> bool:
    """Check every repeated X/Y feature location against its cut blank."""

    if row.count < 1 or len(row.location_mm) != 2:
        return False
    x, y = row.location_mm
    end_x, end_y = x, y
    if row.count > 1:
        if row.pitch_mm <= 0 or row.pitch_axis not in {"X", "Y"}:
            return False
        if row.pitch_axis == "X":
            end_x += row.pitch_mm * (row.count - 1)
        else:
            end_y += row.pitch_mm * (row.count - 1)
    return (
        -1e-6 <= x <= part.length_mm + 1e-6
        and -1e-6 <= end_x <= part.length_mm + 1e-6
        and -1e-6 <= y <= part.width_mm + 1e-6
        and -1e-6 <= end_y <= part.width_mm + 1e-6
    )


def _shell_joinery_facts(model):
    """Validate common carcass/toe machining independently of its generator."""

    rows = tuple(row for row in model.machining
                 if row.kind == "confirmat_step_drill")
    systems = tuple(system for system in model.hardware
                    if system.kind == "carcass_confirmat_system")
    product = get_assembly_fastener(
        "hafele_confirmat_7x50_264_42_190@2026.1"
    )
    part_by_id = {part.part_id: part for part in model.parts}
    part = model.part
    carcass_depth = part("bottom").width_mm
    expected_rows = {}
    for side_role in ("left_end", "right_end"):
        side = part(side_role)
        for receiving_role, count, location, pitch, axis in (
            ("bottom", 3, (side.thickness_mm / 2, 50.0),
             (carcass_depth - 100.0) / 2, "Y"),
            ("front_stretcher", 2,
             (side.length_mm - side.thickness_mm / 2, 25.0), 50.0, "Y"),
            ("rear_stretcher", 2,
             (side.length_mm - side.thickness_mm / 2,
              carcass_depth - part("rear_stretcher").width_mm + 25.0),
             50.0, "Y"),
            ("anchor_strip", 2,
             (side.length_mm - part("anchor_strip").width_mm + 25.0,
              carcass_depth - part("captured_back").thickness_mm
              - side.thickness_mm / 2),
             50.0, "X"),
        ):
            feature_id = f"{side.part_id}.confirmat_{receiving_role}"
            expected_rows[feature_id] = (
                side.part_id,
                part(receiving_role).part_id,
                count,
                location,
                pitch,
                axis,
            )
    for rail_role in ("toe_front", "toe_rear"):
        rail = part(rail_role)
        for sleeper_role, x in (
            ("toe_left", rail.thickness_mm / 2),
            ("toe_right", rail.length_mm - rail.thickness_mm / 2),
        ):
            feature_id = f"{rail.part_id}.confirmat_{sleeper_role}"
            expected_rows[feature_id] = (
                rail.part_id,
                part(sleeper_role).part_id,
                2,
                (x, rail.width_mm * 0.3),
                rail.width_mm * 0.4,
                "Y",
            )
    actual_by_id = {row.feature_id: row for row in rows}
    expected_related_parts = {
        part(role).part_id for role in (
            "left_end", "right_end", "bottom", "front_stretcher",
            "rear_stretcher", "anchor_strip", "toe_front", "toe_rear",
            "toe_left", "toe_right",
        )
    }
    valid = (
        len(systems) == 1
        and systems[0].product_id == product.product_id
        and bool(systems[0].source_url)
        and systems[0].quantity == 26
        and set(systems[0].related_parts) == expected_related_parts
        and set(actual_by_id) == set(expected_rows)
        and sum(row.count for row in rows) == systems[0].quantity
        and all(
            (
                row.part_id,
                row.receiving_part_id,
                row.count,
                row.location_mm,
                row.pitch_mm,
                row.pitch_axis,
            ) == expected_rows[row.feature_id]
            and row.part_id in part_by_id
            and row.receiving_part_id in part_by_id
            and row.receiving_part_id != row.part_id
            and row.face == "outside"
            and bool(row.coordinate_system.strip())
            and _expanded_locations_in_bounds(row, part_by_id[row.part_id])
            and abs(row.depth_mm - (
                product.length_mm - part_by_id[row.part_id].thickness_mm
            )) <= 1e-6
            and abs(row.diameter_mm - product.blind_pilot_diameter_mm) <= 1e-6
            and abs(row.width_mm - product.through_shank_diameter_mm) <= 1e-6
            and abs(row.length_mm - product.countersink_diameter_mm) <= 1e-6
            and row.source == product.product_id
            for row in rows
        )
    )
    return rows, product, valid


def toe_attachment_facts(model):
    """Validate the bottom-to-toe schedule and its solid-material path."""

    rows = tuple(row for row in model.machining
                 if row.kind == "toe_attachment_station")
    systems = tuple(system for system in model.hardware
                    if system.kind == "toe_base_attachment_system")
    product = get_assembly_fastener(
        "grk_low_profile_cabinet_8x1_1_4_114069@2026.1"
    )
    bottom = model.part("bottom")
    toe_t = model.part("toe_front").thickness_mm
    groove_rows = tuple(
        row for row in model.machining
        if row.kind == "captured_back_groove"
        and row.part_id == bottom.part_id
    )
    if len(groove_rows) == 1:
        groove = groove_rows[0]
        groove_front_y = groove.location_mm[1]
        groove_ok = (
            abs(groove_front_y + groove.width_mm - bottom.width_mm) <= 1e-6
        )
    else:
        groove = None
        groove_front_y = bottom.width_mm
        groove_ok = False

    expected = {}
    datum = (
        "cabinet-bottom top face; origin=front-left corner; "
        "+X=right/cut-list length; +Y=toward wall/cut-list width"
    )
    y_by_role = {
        "toe_front": (
            model.section.cabinets[0].toe_kick_setback_mm + toe_t / 2
        ),
        "toe_rear": groove_front_y - toe_t / 2,
    }
    for role in ("toe_front", "toe_rear"):
        feature_id = f"{bottom.part_id}.toe_attachment_{role}"
        expected[feature_id] = (
            model.part(role).part_id,
            (bottom.length_mm / 4, y_by_role[role]),
        )
    actual = {row.feature_id: row for row in rows}
    penetration = product.length_mm - bottom.thickness_mm
    path_ok = groove_ok and penetration > 0
    for role in ("toe_front", "toe_rear"):
        rail = model.part(role)
        rail_front_y = rail.at_mm[1] - rail.thickness_mm - bottom.at_mm[1]
        rail_back_y = rail.at_mm[1] - bottom.at_mm[1]
        station_y = y_by_role[role]
        path_ok = path_ok and (
            station_y - product.diameter_mm / 2 >= rail_front_y - 1e-6
            and station_y + product.diameter_mm / 2 <= rail_back_y + 1e-6
            and penetration <= rail.width_mm + 1e-6
        )
    path_ok = path_ok and (
        model.part("toe_rear").at_mm[1] - bottom.at_mm[1]
        == groove_front_y
        and all(
            abs(model.part(role).length_mm - (
                groove_front_y
                - model.section.cabinets[0].toe_kick_setback_mm
                - 2 * toe_t
            )) <= 1e-6
            for role in ("toe_left", "toe_right")
        )
    )
    cabinet = model.section.cabinets[0]
    toe_height = cabinet.toe_kick_height_mm
    toe_x = bottom.at_mm[0] - toe_t
    toe_z = bottom.at_mm[2] - toe_height
    front_back_y = (
        bottom.at_mm[1] + cabinet.toe_kick_setback_mm + toe_t
    )
    rear_back_y = bottom.at_mm[1] + groove_front_y
    sleeper_length = (
        groove_front_y - cabinet.toe_kick_setback_mm - 2 * toe_t
    )
    expected_geometry = {
        "toe_front": (
            (toe_x, front_back_y, toe_z),
            (("X", 90.0),),
            bottom.length_mm + 2 * toe_t,
        ),
        "toe_rear": (
            (toe_x, rear_back_y, toe_z),
            (("X", 90.0),),
            bottom.length_mm + 2 * toe_t,
        ),
        "toe_left": (
            (toe_x, front_back_y, toe_z),
            (("X", 90.0), ("Z", 90.0)),
            sleeper_length,
        ),
        "toe_right": (
            (bottom.at_mm[0] + bottom.length_mm, front_back_y, toe_z),
            (("X", 90.0), ("Z", 90.0)),
            sleeper_length,
        ),
    }
    for role, (expected_at, expected_rotation, expected_length) in \
            expected_geometry.items():
        member = model.part(role)
        path_ok = path_ok and (
            all(abs(actual - expected) <= 1e-6
                for actual, expected in zip(member.at_mm, expected_at))
            and member.rotate == expected_rotation
            and abs(member.length_mm - expected_length) <= 1e-6
            and abs(member.width_mm - toe_height) <= 1e-6
            and abs(member.thickness_mm - toe_t) <= 1e-6
        )
    expected_related = {
        bottom.part_id,
        model.part("toe_front").part_id,
        model.part("toe_rear").part_id,
    }
    valid = (
        len(systems) == 1
        and systems[0].product_id == product.product_id
        and systems[0].quantity == 6
        and set(systems[0].related_parts) == expected_related
        and set(actual) == set(expected)
        and sum(row.count for row in rows) == systems[0].quantity
        and all(
            row.part_id == bottom.part_id
            and (row.receiving_part_id, row.location_mm)
            == expected[row.feature_id]
            and row.count == 3
            and abs(row.pitch_mm - bottom.length_mm / 4) <= 1e-6
            and row.pitch_axis == "X"
            and row.diameter_mm == 0
            and row.depth_mm == 0
            and row.width_mm == 0
            and row.length_mm == 0
            and row.source == product.product_id
            and row.face == "top"
            and row.coordinate_system == datum
            and _expanded_locations_in_bounds(row, bottom)
            for row in rows
        )
        and path_ok
    )
    return rows, product, penetration, valid


def _validate_drawer_model(model) -> CabinetReport:
    """Validate the drawer product without running door/hinge/shelf rules."""

    findings: list[CabinetFinding] = []
    evidence: list[EvidenceRecord] = []
    installation_policy = InstallationUsePolicy(
        policy_id="cabinetry.db40.installation_use@1",
        blocking_rules=(
            "cabinetry.performance.anchor_capacity",
            "cabinetry.performance.whole_cabinet_capacity",
        ),
        hazard_statement=(
            "TIP-OVER HAZARD — an unsecured or under-designed cabinet can tip "
            "and cause serious or fatal crushing injury."
        ),
        clearance_authority="a qualified cabinet or structural design professional",
        required_evidence=(
            "cabinet, toe-platform, and anchor load-path calculations",
            "dead, countertop, contents, and service loads",
            "substrate species, grade, and condition",
            "fastener count, spacing, edge/end distances, and embedment",
        ),
        source_url=(
            "https://www.cpsc.gov/Safety-Education/Safety-Education-Centers/"
            "AnchorItgov"
        ),
        scope_source_url=(
            "https://www.cpsc.gov/Business--Manufacturing/Business-Education/"
            "Business-Guidance/Clothing-Storage-Units"
        ),
        scope_note=(
            "This is conservative CPSC-informed owner guidance, not a claim "
            "that 16 CFR part 1261 applies; CPSC excludes built-in units intended "
            "to be permanently attached from that clothing-storage-unit scope."
        ),
    )

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

    shell_rows, shell_fastener, shell_joinery_ok = _shell_joinery_facts(model)
    add(
        "cabinetry.joinery.shell_machining",
        "PASS" if shell_joinery_ok else "FAIL",
        "required",
        f"Carcass/toe joinery has {len(shell_rows)} machining rows and "
        f"{sum(row.count for row in shell_rows)} fastener positions; each "
        "position must be in its cut blank, name its receiving part and "
        f"datum, and match {shell_fastener.sku} step-drill geometry.",
        "manufacturer_rated",
        source=shell_fastener.source_url,
        affected=tuple(row.part_id for row in shell_rows),
    )

    toe_rows, toe_fastener, toe_penetration, toe_attachment_ok = \
        toe_attachment_facts(model)
    add(
        "cabinetry.joinery.toe_attachment_machining",
        "PASS" if toe_attachment_ok else "FAIL",
        "required",
        f"Toe attachment has {len(toe_rows)} rows / "
        f"{sum(row.count for row in toe_rows)} stations for "
        f"{toe_fastener.sku}; modeled rail penetration is "
        f"{toe_penetration:.2f} mm. Stations must remain in solid bottom/rail "
        "stock ahead of the captured-back groove. Pilot diameter/depth, torque, "
        "and connection capacity are not claimed.",
        "calculated",
        source=toe_fastener.source_url,
        affected=tuple(row.part_id for row in toe_rows)
                 or (model.part("bottom").part_id,),
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
        bank.opening_height_mm
        - 2 * bank.front_edge_reveal_mm
        - (len(front_parts) - 1) * bank.front_gap_mm
    )
    actual_front_total = sum(part.width_mm for part in front_parts)
    front_allocation_ok = abs(actual_front_total - required_front_total) <= 1e-6
    add(
        "cabinetry.drawer.front_allocation",
        "PASS" if front_allocation_ok else "FAIL",
        "required",
        f"Applied-front material totals {actual_front_total:.2f} mm; the "
        f"{bank.opening_height_mm:.2f} mm opening requires "
        f"{required_front_total:.2f} mm after two "
        f"{bank.front_edge_reveal_mm:.2f} mm edge reveals and "
        f"two {bank.front_gap_mm:.2f} mm inter-front gaps.",
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
    groove_rows = tuple(
        row for row in model.machining if row.kind == "drawer_bottom_groove"
    )
    part_by_id = {part.part_id: part for part in model.parts}
    groove_geometry_ok = True
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
        expected_ids = {
            model.part(f"drawer_{cell.cell_id}_{role}").part_id
            for role in ("side_left", "side_right", "front", "back")
        }
        cell_grooves = tuple(row for row in groove_rows
                             if row.part_id in expected_ids)
        groove_geometry_ok = groove_geometry_ok and (
            len(cell_grooves) == 4
            and {row.part_id for row in cell_grooves} == expected_ids
            and all(
                row.location_mm == (0.0, runner.bottom_recess_mm)
                and row.count == 1
                and row.pitch_mm == 0
                and row.pitch_axis == ""
                and 0 < row.depth_mm <= part_by_id[row.part_id].thickness_mm
                and abs(row.width_mm - bottom.thickness_mm) <= 1e-6
                and abs(row.length_mm
                        - part_by_id[row.part_id].length_mm) <= 1e-6
                and row.face == "inside"
                and row.source == "drawer_box.captured_bottom"
                and bool(row.coordinate_system.strip())
                and row.location_mm[0] + row.length_mm
                    <= part_by_id[row.part_id].length_mm + 1e-6
                and row.location_mm[1] + row.width_mm
                    <= part_by_id[row.part_id].width_mm + 1e-6
                for row in cell_grooves
            )
        )
    bottom_ok = all(
        abs(recess - runner.bottom_recess_mm) <= 1e-6
        and abs(clearance - runner.bottom_clearance_mm) <= 1e-6
        and abs(thickness - 12.0) <= 1e-6
        for _, recess, clearance, thickness in bottom_rows
    ) and groove_geometry_ok
    add(
        "cabinetry.drawer.bottom_geometry",
        "PASS" if bottom_ok else "FAIL",
        "required",
        "Captured-bottom geometry and groove machining "
        "(recess/clearance/thickness): "
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

    joinery_rows = tuple(
        item for item in model.machining
        if item.kind == "drawer_box_confirmat_step_drill"
    )
    joinery_systems = tuple(
        system for system in model.hardware
        if system.kind == "drawer_box_joinery_fastener"
    )
    expected_joinery_pairs = {
        (
            model.part(f"drawer_{cell.cell_id}_side_{hand}").part_id,
            model.part(f"drawer_{cell.cell_id}_{end}").part_id,
        )
        for cell in bank.cells
        for hand in ("left", "right")
        for end in ("front", "back")
    }
    actual_joinery_pairs = {
        (row.part_id, row.receiving_part_id) for row in joinery_rows
    }
    expected_joinery_geometry = {}
    for cell in bank.cells:
        side = model.part(f"drawer_{cell.cell_id}_side_left")
        lower_y = max(
            38.1,
            runner.bottom_recess_mm
            + model.part(f"drawer_{cell.cell_id}_bottom").thickness_mm
            + 10.0,
        )
        upper_y = side.width_mm - 25.4
        for hand in ("left", "right"):
            side_id = model.part(
                f"drawer_{cell.cell_id}_side_{hand}"
            ).part_id
            expected_joinery_geometry[
                (side_id, model.part(f"drawer_{cell.cell_id}_front").part_id)
            ] = ((side.thickness_mm / 2, lower_y), upper_y - lower_y)
            expected_joinery_geometry[
                (side_id, model.part(f"drawer_{cell.cell_id}_back").part_id)
            ] = ((side.length_mm - side.thickness_mm / 2, lower_y),
                 upper_y - lower_y)
    expected_system_ids = {
        f"{bank.namespace}.{cell.cell_id}.box_joinery_confirmats"
        for cell in bank.cells
    }
    joinery_ok = (
        len(joinery_rows) == len(bank.cells) * 4
        and sum(row.count for row in joinery_rows) == len(bank.cells) * 8
        and actual_joinery_pairs == expected_joinery_pairs
        and all(
            row.count == 2
            and row.pitch_axis == "Y"
            and (row.location_mm, row.pitch_mm)
            == expected_joinery_geometry[
                (row.part_id, row.receiving_part_id)
            ]
            and row.source == bank.joinery_fastener.product_id
            and row.part_id in part_by_id
            and row.receiving_part_id in part_by_id
            and row.receiving_part_id != row.part_id
            and row.face == "outside"
            and bool(row.coordinate_system.strip())
            and _expanded_locations_in_bounds(row, part_by_id[row.part_id])
            and abs(
                row.depth_mm
                - (bank.joinery_fastener.length_mm
                   - part_by_id[row.part_id].thickness_mm)
            ) <= 1e-6
            and abs(row.diameter_mm
                    - bank.joinery_fastener.blind_pilot_diameter_mm) <= 1e-6
            and abs(row.width_mm
                    - bank.joinery_fastener.through_shank_diameter_mm) <= 1e-6
            and abs(row.length_mm
                    - bank.joinery_fastener.countersink_diameter_mm) <= 1e-6
            for row in joinery_rows
        )
        and {system.system_id for system in joinery_systems}
        == expected_system_ids
        and all(
            system.quantity == 8
            and system.product_id == bank.joinery_fastener.product_id
            and bool(system.source_url)
            for system in joinery_systems
        )
    )
    add(
        "cabinetry.drawer.box_joinery_completeness",
        "PASS" if joinery_ok else "FAIL",
        "required",
        (
            f"Drawer-box corner joinery has {len(joinery_rows)} machining "
            f"rows / {sum(row.count for row in joinery_rows)} fastener "
            f"positions and {len(joinery_systems)} sourced hardware systems; "
            f"required {len(bank.cells) * 4} rows / {len(bank.cells) * 8} "
            f"positions / {len(bank.cells)} systems."
        ),
        "manufacturer_rated",
        source=bank.joinery_fastener.source_url,
        affected=tuple(sorted({
            part_id for pair in expected_joinery_pairs for part_id in pair
        })),
    )

    rear_notches = tuple(item for item in model.machining
                         if item.kind == "runner_rear_notch")
    hook_bores = tuple(item for item in model.machining
                       if item.kind == "runner_hook_bore")
    expected_rear_count = len(bank.cells) * 2
    expected_hook_x = (
        runner.hook_bore_inset_from_side_mm,
        bank.inside_box_width_mm - runner.hook_bore_inset_from_side_mm,
    )
    notch_positions_ok = all(
        len(cell_notches := tuple(
            item for item in rear_notches
            if item.part_id == model.part(
                f"drawer_{cell.cell_id}_back"
            ).part_id
        )) == 2
        and {item.location_mm for item in cell_notches} == {
            (0.0, 0.0),
            (bank.inside_box_width_mm - runner.minimum_rear_notch_mm, 0.0),
        }
        for cell in bank.cells
    )
    hook_positions_ok = all(
        len(cell_bores := tuple(
            item for item in hook_bores
            if item.part_id == model.part(f"drawer_{cell.cell_id}_back").part_id
        )) == 2
        and all(
            sum(abs(item.location_mm[0] - expected_x) <= 1e-6
                for item in cell_bores) == 1
            for expected_x in expected_hook_x
        )
        for cell in bank.cells
    )
    rear_ok = (
        len(rear_notches) == expected_rear_count
        and len(hook_bores) == expected_rear_count
        and all(abs(item.width_mm - runner.minimum_rear_notch_mm) <= 1e-6
                and abs(item.depth_mm
                        - runner.minimum_rear_notch_height_mm) <= 1e-6
                and item.count == 1
                and item.face == "rear_face_lower_edge"
                and item.source == runner.product_id
                and item.coordinate_system == (
                    "drawer-back rear face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                )
                for item in rear_notches)
        and all(abs(item.diameter_mm - runner.hook_bore_mm[0]) <= 1e-6
                and abs(item.depth_mm - runner.hook_bore_mm[1]) <= 1e-6
                and abs(item.location_mm[1]
                        - runner.hook_bore_height_from_bottom_mm) <= 1e-6
                and item.count == 1
                and item.face == "rear"
                and item.source == runner.product_id
                and item.coordinate_system == (
                    "drawer-back rear face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                )
                for item in hook_bores)
        and hook_positions_ok
        and notch_positions_ok
    )
    add(
        "cabinetry.drawer.rear_preparation",
        "PASS" if rear_ok else "FAIL",
        "required",
        f"Rear preparation has runner_rear_notch {len(rear_notches)} of "
        f"{expected_rear_count} and runner_hook_bore {len(hook_bores)} of "
        f"{expected_rear_count}; required notch "
        f"{runner.minimum_rear_notch_mm:.0f} x "
        f"{runner.minimum_rear_notch_height_mm:.0f} mm in each drawer back "
        f"and hook bore "
        f"Ø{runner.hook_bore_mm[0]:.0f} x {runner.hook_bore_mm[1]:.0f} mm "
        f"at {runner.hook_bore_inset_from_side_mm:.0f} mm side inset and "
        f"{runner.hook_bore_height_from_bottom_mm:.0f} mm bottom height.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(item.part_id for item in rear_notches + hook_bores)
                 or box_part_ids,
    )

    fixing = tuple(item for item in model.machining
                   if item.kind == "runner_fixing_station")
    expected_fixing_count = (
        len(bank.cells) * len(bank.mounting_part_ids)
        * len(runner.required_fixing_stations_mm)
    )
    expected_fixing_y = {
        cell.cell_id: (
            model.part(f"drawer_{cell.cell_id}_side_left").at_mm[2]
            - model.part("left_end").at_mm[2]
            + runner.mounting_line_mm
            - runner.bottom_clearance_mm
        )
        for cell in bank.cells
    }
    expected_fixing = {}
    for cell in bank.cells:
        for index, mounting_part_id in enumerate(bank.mounting_part_ids):
            side_name = "left" if index == 0 else "right"
            for station in runner.required_fixing_stations_mm:
                feature_id = (
                    f"{mounting_part_id}.{cell.cell_id}.runner_"
                    f"fixing_{side_name}_{station:g}"
                )
                expected_fixing[feature_id] = (
                    mounting_part_id,
                    (station, expected_fixing_y[cell.cell_id]),
                )
    actual_fixing = {item.feature_id: item for item in fixing}
    fixing_ok = (
        len(fixing) == expected_fixing_count
        and set(actual_fixing) == set(expected_fixing)
        and all(
                (item.part_id, item.location_mm)
                == expected_fixing[item.feature_id]
                and abs(item.diameter_mm
                        - runner.installation_pilot_diameter_mm) <= 1e-6
                and abs(item.depth_mm
                        - runner.installation_pilot_depth_mm) <= 1e-6
                and item.source == runner.product_id
                and item.face == "inside"
                and item.count == 1
                and item.pitch_mm == 0
                and item.pitch_axis == ""
                and item.coordinate_system == (
                    "cabinet-side inside face; origin=front-bottom of side "
                    "blank; +X=rearward/cut-list width; "
                    "+Y=up/cut-list length"
                )
                for item in fixing)
    )
    runner_pair_missing = []
    runner_screw_missing = []
    for cell in bank.cells:
        runner_pairs = [
            system for system in model.hardware
            if system.kind == "drawer_runner_pair"
            and f".{cell.cell_id}." in system.system_id
        ]
        if (len(runner_pairs) != 1
                or runner_pairs[0].quantity != 2
                or runner_pairs[0].product_id != runner.product_id):
            runner_pair_missing.append(cell.cell_id)
        runner_screws = [
            system for system in model.hardware
            if system.kind == "drawer_runner_installation_screw"
            and f".{cell.cell_id}." in system.system_id
        ]
        required_runner_screws = 2 * runner.installation_screws_per_runner
        if (len(runner_screws) != 1
                or runner_screws[0].quantity != required_runner_screws
                or runner_screws[0].product_id
                != runner.installation_screw_product_id):
            runner_screw_missing.append(cell.cell_id)
    fixing_ok = (
        fixing_ok and not runner_pair_missing and not runner_screw_missing
    )
    add(
        "cabinetry.drawer.runner_fixing",
        "PASS" if fixing_ok else "FAIL",
        "required",
        f"Runner mounting schedule contains {len(fixing)} of "
        f"{expected_fixing_count} required fixing stations at cabinet-front "
        f"coordinates {list(runner.required_fixing_stations_mm)} mm and "
        f"elevations {expected_fixing_y}; the {runner.front_setback_mm:.0f} mm "
        f"runner-front setback is not added to those coordinates; missing/wrong runner "
        f"pairs: {runner_pair_missing}; missing/wrong "
        f"{runner.installation_screw_sku} fixing-screw sets: "
        f"{runner_screw_missing}. Preparation is Ø"
        f"{runner.installation_pilot_diameter_mm:g} mm with "
        f"{runner.installation_drive} drive; the adapter does not claim a "
        "cabinet-side pilot depth.",
        "manufacturer_rated",
        source=runner.source_url,
        affected=tuple(bank.mounting_part_ids),
    )

    locking_missing = []
    locking_screw_missing = []
    stabilizer_missing = []
    for cell in bank.cells:
        locking = [system for system in model.hardware
                   if system.kind == "drawer_locking_device_pair"
                   and f".{cell.cell_id}." in system.system_id]
        if len(locking) != 1 or locking[0].quantity != 2 \
                or locking[0].product_id != bank.locking_device.product_id:
            locking_missing.append(cell.cell_id)
        locking_screws = [system for system in model.hardware
                          if system.kind == "drawer_locking_device_screw"
                          and f".{cell.cell_id}." in system.system_id]
        required_screws = (
            bank.locking_device.quantity_per_drawer
            * bank.locking_device.installation_screw_quantity_per_device
        )
        if (len(locking_screws) != 1
                or locking_screws[0].quantity != required_screws
                or locking_screws[0].product_id
                != bank.locking_device.installation_screw_product_id):
            locking_screw_missing.append(cell.cell_id)
        stabilizers = [system for system in model.hardware
                       if system.kind == "drawer_lateral_stabilizer"
                       and f".{cell.cell_id}." in system.system_id]
        if bank.opening_width_mm >= bank.stabilizer.recommended_from_opening_mm \
                and (len(stabilizers) != 1
                     or stabilizers[0].quantity != 1
                     or stabilizers[0].product_id != bank.stabilizer.product_id):
            stabilizer_missing.append(cell.cell_id)
    locking_bores = tuple(item for item in model.machining
                          if item.kind == "locking_device_bore")
    expected_locking_bores = (
        len(bank.cells) * bank.locking_device.quantity_per_drawer
        * bank.locking_device.pilot_bores_per_device
    )
    expected_locking_faces = {
        f"{handed}_front_corner_at_"
        f"{bank.locking_device.installation_angle_deg:g}_deg"
        for handed in ("left", "right")
    }
    expected_coordinate_system = (
        f"Blum {bank.locking_device.template_sku} template at drawer front corner"
    )
    locking_bores_by_cell_ok = all(
        len(cell_bores := tuple(
            item for item in locking_bores
            if item.part_id == model.part(f"drawer_{cell.cell_id}_front").part_id
        )) == (
            bank.locking_device.quantity_per_drawer
            * bank.locking_device.pilot_bores_per_device
        )
        and all(
            sum(item.face == face for item in cell_bores)
            == bank.locking_device.pilot_bores_per_device
            for face in expected_locking_faces
        )
        for cell in bank.cells
    )
    locking_bores_ok = (
        len(locking_bores) == expected_locking_bores
        and locking_bores_by_cell_ok
        and all(
            abs(item.diameter_mm
                - bank.locking_device.pilot_bore_diameter_mm) <= 1e-6
            and abs(item.depth_mm
                    - bank.locking_device.pilot_bore_depth_mm) <= 1e-6
            and item.coordinate_system == expected_coordinate_system
            and item.source == bank.locking_device.product_id
            and not item.location_mm
            and item.count == 1
            and item.pitch_mm == 0
            and item.pitch_axis == ""
            for item in locking_bores
        )
    )
    locking_ok = (
        not locking_missing and not locking_screw_missing and locking_bores_ok
    )
    add(
        "cabinetry.drawer.locking_devices",
        "PASS" if locking_ok else "FAIL",
        "required",
        (f"Each drawer has one pinned {bank.locking_device.left_sku} / "
         f"{bank.locking_device.right_sku} locking-device pair, "
         f"four {bank.locking_device.installation_screw_sku} screws, and two "
         f"Ø{bank.locking_device.pilot_bore_diameter_mm:g} x "
         f"{bank.locking_device.pilot_bore_depth_mm:g} mm template bores per "
         "device." if locking_ok else
         f"Missing/wrong locking-device pairs: {locking_missing}; "
         f"missing/wrong installation-screw sets: {locking_screw_missing}; "
         f"template pilot bores: {len(locking_bores)} of "
         f"{expected_locking_bores}."),
        "manufacturer_rated",
        source=bank.locking_device.source_url,
        affected=tuple(
            model.part(f"drawer_{cell.cell_id}_front").part_id
            for cell in bank.cells
        ),
    )
    stabilizer_cut_issues = []
    stabilizer_cuts = tuple(
        item for item in model.machining
        if item.kind in {
            "stabilizer_gear_rack_cut", "stabilizer_linkage_rod_cut",
        }
    )
    cuts_by_id = {item.feature_id: item for item in stabilizer_cuts}
    expected_cut_ids = set()
    cut_datum = "hardware stock; origin=one cut end; +X=stock length"
    for cell in bank.cells:
        system_id = f"{bank.namespace}.{cell.cell_id}.lateral_stabilizer"
        for kind, suffix, length in (
            ("stabilizer_gear_rack_cut", "gear_rack_cut",
             bank.stabilizer.gear_rack_length_mm),
            ("stabilizer_linkage_rod_cut", "linkage_rod_cut",
             bank.opening_width_mm
             - bank.stabilizer.linkage_rod_cut_deduction_mm),
        ):
            feature_id = f"{system_id}.{suffix}"
            expected_cut_ids.add(feature_id)
            item = cuts_by_id.get(feature_id)
            if item is None or not (
                item.kind == kind
                and item.part_id == system_id
                and item.location_mm == (0.0,)
                and abs(item.length_mm - length) <= 1e-6
                and item.count == 1
                and item.pitch_mm == 0
                and item.pitch_axis == ""
                and item.source == bank.stabilizer.product_id
                and item.face == "hardware_stock"
                and item.coordinate_system == cut_datum
            ):
                stabilizer_cut_issues.append(
                    f"{cell.cell_id}:{kind}"
                )
    if set(cuts_by_id) != expected_cut_ids:
        stabilizer_cut_issues.append("unexpected_or_duplicate_stabilizer_cut")

    add(
        "cabinetry.drawer.lateral_stabilizer",
        "FAIL" if stabilizer_missing or stabilizer_cut_issues else "PASS",
        "required",
        (f"Wide-opening stabilizer is missing or wrong for cells "
         f"{stabilizer_missing}; stock-cut issues: {stabilizer_cut_issues}; "
         f"{bank.opening_width_mm:.2f} mm exceeds the "
         f"{bank.stabilizer.recommended_from_opening_mm:.2f} mm recommendation."
         if stabilizer_missing or stabilizer_cut_issues else
         f"All drawers carry the pinned lateral stabilizer and both exact "
         f"stock cuts required for the {bank.opening_width_mm:.2f} mm opening."),
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

    mass_sources = tuple(dict.fromkeys((
        bank.locking_device.mass_source_url,
        bank.locking_device.source_url,
        bank.stabilizer.mass_source_url,
        bank.pull_product.source_url,
        bank.pull_product.mounting_screw_source_url,
        bank.joinery_fastener.source_url,
        model.front_fastener.source_url,
    )))
    mass_sources_ok = all(source.strip() for source in mass_sources)
    mass_math_ok = all(
        cell.wood_mass_kg > 0
        and cell.moving_hardware_mass_kg > 0
        and abs(
            cell.moving_mass_kg
            - cell.wood_mass_kg
            - cell.moving_hardware_mass_kg
        ) <= 1e-9
        for cell in bank.cells
    )
    mass_verdict = (
        "UNKNOWN" if not mass_sources_ok else ("PASS" if mass_math_ok else "FAIL")
    )
    add(
        "cabinetry.drawer.moving_hardware_mass",
        mass_verdict,
        "required",
        "Auditable moving-mass decomposition by cell (wood + hardware): "
        + ", ".join(
            f"{cell.cell_id} {cell.wood_mass_kg:.3f} + "
            f"{cell.moving_hardware_mass_kg:.3f} = "
            f"{cell.moving_mass_kg:.3f} kg"
            for cell in bank.cells
        )
        + ("; all moving-hardware mass inputs have "
           "traceable sources." if mass_sources_ok else
           "; one or more moving-hardware mass inputs "
           "lack a traceable source."),
        "calculated" if mass_sources_ok else "unknown",
        source=" | ".join(source for source in mass_sources if source),
        affected=tuple(
            system_id for cell in bank.cells for system_id in cell.hardware_ids
        ),
    )

    overloaded = [cell for cell in bank.cells
                  if cell.calculated_moving_load_lb >
                  runner.dynamic_rating_lb + 1e-6]
    load_ok = not overloaded
    add(
        "cabinetry.drawer.moving_load",
        "PASS" if load_ok else "FAIL",
        "required",
        "Moving assembly plus declared contents by cell: "
        + ", ".join(f"{cell.cell_id} "
                    f"{cell.calculated_moving_load_lb:.2f} lb"
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
    front_fastener_ok = (
        model.front_fastener.length_mm > box_front_thickness
        and model.front_fastener.length_mm < stack - 0.5
    )
    pull = bank.pull_product
    pull_system_missing = []
    pull_screw_missing = []
    front_system_missing = []
    machining_issues = []
    for cell in bank.cells:
        pull_systems = [
            system for system in model.hardware
            if system.kind == "drawer_pull"
            and f".{cell.cell_id}." in system.system_id
        ]
        if (len(pull_systems) != 1
                or pull_systems[0].product_id != pull.product_id
                or pull_systems[0].quantity != pull.quantity_per_drawer):
            pull_system_missing.append(cell.cell_id)
        pull_screw_systems = [
            system for system in model.hardware
            if system.kind == "drawer_pull_mounting_screw"
            and f".{cell.cell_id}." in system.system_id
        ]
        if (len(pull_screw_systems) != 1
                or pull_screw_systems[0].product_id
                != pull.mounting_screw_product_id
                or pull_screw_systems[0].quantity != (
                    pull.quantity_per_drawer
                    * pull.mounting_screw_quantity_per_pull
                )):
            pull_screw_missing.append(cell.cell_id)
        front_systems = [
            system for system in model.hardware
            if system.kind == "applied_front_fastener_system"
            and f".{cell.cell_id}." in system.system_id
        ]
        if (len(front_systems) != 1
                or front_systems[0].product_id
                != model.front_fastener.product_id
                or front_systems[0].quantity != 4):
            front_system_missing.append(cell.cell_id)

        applied_front = model.part(f"drawer_front_{cell.cell_id}")
        box_front = model.part(f"drawer_{cell.cell_id}_front")
        pull_bores = [
            item for item in model.machining
            if item.kind == "pull_bore" and item.part_id == applied_front.part_id
        ]
        expected_pull_x = {
            applied_front.length_mm / 2 - pull.hole_spacing_mm / 2,
            applied_front.length_mm / 2 + pull.hole_spacing_mm / 2,
        }
        pull_bores_ok = (
            len(pull_bores) == 2
            and {item.location_mm[0] for item in pull_bores} == expected_pull_x
            and all(
                abs(item.location_mm[1] - applied_front.width_mm / 2) <= 1e-6
                and abs(item.diameter_mm - 5.0) <= 1e-6
                and abs(item.depth_mm - applied_front.thickness_mm) <= 1e-6
                and item.source == pull.product_id
                and item.face == "front"
                and item.coordinate_system == (
                    "applied-front finished face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                )
                and item.count == 1
                and item.pitch_mm == 0
                and item.pitch_axis == ""
                and _expanded_locations_in_bounds(item, applied_front)
                for item in pull_bores
            )
        )
        if not pull_bores_ok:
            machining_issues.append(f"{cell.cell_id}:pull_bore")

        attachment_holes = [
            item for item in model.machining
            if item.kind == "applied_front_attachment"
            and item.part_id == box_front.part_id
        ]
        attachment_holes_ok = (
            len(attachment_holes) == 4
            and {item.location_mm for item in attachment_holes} == {
                (bank.inside_box_width_mm * x_factor,
                 cell.box_height_mm * y_factor)
                for x_factor in (0.25, 0.75)
                for y_factor in (0.25, 0.75)
            }
            and all(
                abs(item.diameter_mm - 5.0) <= 1e-6
                and abs(item.depth_mm - box_front.thickness_mm) <= 1e-6
                and item.face == "inside"
                and item.source == "drawer_front.applied"
                and item.coordinate_system == (
                    "drawer box-front inside face; origin=lower-left corner; "
                    "+X=right/cut-list length; +Y=up/cut-list width"
                )
                and item.count == 1
                and item.pitch_mm == 0
                and item.pitch_axis == ""
                and _expanded_locations_in_bounds(item, box_front)
                for item in attachment_holes
            )
        )
        if not attachment_holes_ok:
            machining_issues.append(
                f"{cell.cell_id}:applied_front_attachment"
            )
    pull_engagement = pull.mounting_screw_length_mm - applied_front_thickness
    minimum_pull_engagement = (
        pull.thread_diameter_mm * pull.minimum_thread_engagement_factor
    )
    pull_fastener_ok = (
        not pull_system_missing
        and not pull_screw_missing
        and not front_system_missing
        and not machining_issues
        and pull_engagement + 1e-6 >= minimum_pull_engagement
    )
    fastener_ok = front_fastener_ok and pull_fastener_ok
    add(
        "cabinetry.drawer.front_fastener_stack",
        "PASS" if fastener_ok else "FAIL",
        "required",
        f"Applied-front fastener length is {model.front_fastener.length_mm:.2f} mm "
        f"through a {stack:.2f} mm material stack; pull screw "
        f"{pull.mounting_screw_sku} is {pull.mounting_screw_length_mm:.2f} mm "
        f"through the {applied_front_thickness:.2f} mm applied front for "
        f"{pull_engagement:.2f} mm nominal engagement (minimum "
        f"{minimum_pull_engagement:.2f} mm); missing/wrong pull systems: "
        f"{pull_system_missing}; missing/wrong pull screw sets: "
        f"{pull_screw_missing}; missing/wrong applied-front fastener systems: "
        f"{front_system_missing}; machining issues: {machining_issues}. The "
        "front fastener must remain 0.50 mm short of the finished face, and "
        "all attachment clearance holes must be in the box front, not the "
        "decorative applied front.",
        "calculated",
        source=pull.thread_engagement_reference_url,
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
        abs(bottom_reveal - bank.front_edge_reveal_mm) <= 1e-6
        and abs(top_reveal - bank.front_edge_reveal_mm) <= 1e-6
        and all(abs(gap - bank.front_gap_mm) <= 1e-6 for gap in gaps)
        and all(abs(reveal - bank.front_edge_reveal_mm) <= 1e-6
                for reveal in left_reveals + right_reveals)
    )
    add(
        "cabinetry.drawer.closed_reveals",
        "PASS" if reveals_ok else "FAIL",
        "required",
        "Closed front gaps are "
        + ", ".join(f"{gap:.2f} mm" for gap in gaps) + "; "
        f"bottom/top reveals are {bottom_reveal:.2f}/{top_reveal:.2f} mm and "
        f"side reveals are {left_reveals + right_reveals}; targets are "
        f"{bank.front_gap_mm:.2f} mm gaps and "
        f"{bank.front_edge_reveal_mm:.2f} mm edge reveals.",
        "derived",
        affected=tuple(part.part_id for part in front_parts),
    )

    collisions = []
    intrinsic_failures = []
    body_bottom = model.shell.base_z_mm + cabinet.toe_kick_height_mm
    body_top = body_bottom + model.shell.body_height_mm
    opening_left = bank.opening_origin_mm[0]
    opening_right = opening_left + bank.opening_width_mm
    inside_depth_plane = bank.opening_origin_mm[1] + bank.inside_depth_mm
    front_intervals = []
    for cell in bank.cells:
        front = model.part(f"drawer_front_{cell.cell_id}")
        side_left = model.part(f"drawer_{cell.cell_id}_side_left")
        side_right = model.part(f"drawer_{cell.cell_id}_side_right")
        box_back = model.part(f"drawer_{cell.cell_id}_back")
        bottom = model.part(f"drawer_{cell.cell_id}_bottom")
        front_intervals.append((cell.cell_id, front.at_mm[2],
                                front.at_mm[2] + front.width_mm))
        if front.at_mm[0] < model.shell.x0_mm - 1e-6 or (
            front.at_mm[0] + front.length_mm
            > model.shell.x0_mm + cabinet.width_mm + 1e-6
        ):
            intrinsic_failures.append(
                f"{cell.cell_id}:applied front exceeds cabinet side planes"
            )
        if side_left.at_mm[0] < opening_left - 1e-6 or (
            side_right.at_mm[0] + side_right.thickness_mm
            > opening_right + 1e-6
        ):
            intrinsic_failures.append(
                f"{cell.cell_id}:drawer box exceeds opening side planes"
            )
        if front.at_mm[2] < body_bottom - 1e-6:
            intrinsic_failures.append(
                f"{cell.cell_id}:front intersects toe-platform plane"
            )
        if front.at_mm[2] + front.width_mm > body_top + 1e-6:
            intrinsic_failures.append(
                f"{cell.cell_id}:front intersects countertop/body-top plane"
            )
        box_rear = max(
            side_left.at_mm[1] + side_left.length_mm,
            side_right.at_mm[1] + side_right.length_mm,
            box_back.at_mm[1] + box_back.thickness_mm,
            bottom.at_mm[1] + bottom.width_mm,
        )
        if box_rear > inside_depth_plane + 1e-6:
            intrinsic_failures.append(
                f"{cell.cell_id}:drawer box exceeds closed inside-depth plane"
            )
        box_top = max(
            side_left.at_mm[2] + side_left.width_mm,
            side_right.at_mm[2] + side_right.width_mm,
        )
        if box_top + runner.minimum_top_clearance_mm > (
            front.at_mm[2] + front.width_mm + 1e-6
        ):
            intrinsic_failures.append(
                f"{cell.cell_id}:drawer box violates top-clearance envelope"
            )
        swept = (
            front.at_mm[0],
            front.at_mm[1] - runner.physical_length_mm - front.thickness_mm,
            front.at_mm[2],
            front.at_mm[0] + front.length_mm,
            box_rear,
            front.at_mm[2] + front.width_mm,
        )
        if swept[1] >= front.at_mm[1] - 1e-6:
            intrinsic_failures.append(
                f"{cell.cell_id}:full extension does not move away from wall"
            )
        collisions.extend(
            (cell.cell_id, obstruction.obstruction_id)
            for obstruction in model.declared_obstructions
            if _boxes_intersect(swept, obstruction.bounds_mm)
        )
    for index, (cell_id, z0, z1) in enumerate(front_intervals):
        for other_id, other_z0, other_z1 in front_intervals[index + 1:]:
            if min(z1, other_z1) > max(z0, other_z0) + 1e-6:
                intrinsic_failures.append(
                    f"{cell_id}/{other_id}:closed fronts overlap vertically"
                )
    clearance_ok = not intrinsic_failures and not collisions
    add(
        "cabinetry.drawer.extended_clearance",
        "PASS" if clearance_ok else "FAIL",
        "required",
        "Intrinsic envelope failures: "
        f"{intrinsic_failures}; declared-obstruction collisions: {collisions}. "
        f"Checked {len(bank.cells)} drawer sweeps against cabinet sides, toe "
        "platform, countertop/body-top plane, wall/inside-depth plane, and "
        f"other closed fronts, plus {len(model.declared_obstructions)} declared "
        "room obstruction(s).",
        "calculated",
        affected=(
            tuple(part.part_id for part in front_parts)
            + tuple(
                model.part(f"drawer_{cell.cell_id}_{role}").part_id
                for cell in bank.cells
                for role in ("side_left", "side_right", "back", "bottom")
            )
            + tuple(obstruction.obstruction_id
                    for obstruction in model.declared_obstructions)
        ),
    )

    required_sequence = (
        "shop.adjust_drawers",
        "ship.record_adjustment_identity",
        "ship.remove_drawers",
        "ship.empty_carcass",
        "install.anchor_empty_carcass",
        "install.reinstall_by_identity",
        "install.commission_drawers",
        "install.countertop",
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
        ("Sequence adjusts drawers, records adjustment identity, removes and "
         "ships them separately, anchors the empty carcass, reinstalls by "
         "identity, commissions, and installs the countertop last." if sequence_ok else
         "Sequence must record adjustment identity before drawer removal, ship "
         "and anchor the empty carcass, then reinstall by identity before "
         "commissioning and install the countertop last."),
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
        anchor_embedment_facts(model)
    add(
        "cabinetry.install.anchor_embedment",
        "PASS" if embedment_ok else "FAIL",
        "required",
        f"The modeled wall-anchor path for {model.wall_anchor.product} leaves "
        f"{embedment / IN:.3f} in stud embedment after the modeled "
        f"{anchor_stack / IN:.3f} in stack; pack minimum is "
        f"{min_embedment / IN:.2f} in. Every modeled screw must start at the "
        "anchor-strip head plane, align with its declared stud, and retain "
        "the selected catalog geometry.",
        "calculated",
        source=model.wall_anchor.source_url,
        affected=_anchor_affected(model),
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
        (
            "The floor-supported base cabinet has anchor product, count, "
            "location, and embedment represented; lateral/withdrawal demand "
            "and connection capacity are not calculated in v1."
            if embedment_ok else
            "A complete, geometrically valid wall-anchor path is not represented; "
            "lateral/withdrawal demand and connection capacity also remain "
            "uncalculated."
        ),
        "unknown",
        source=model.wall_anchor.source_url,
        affected=_anchor_affected(model),
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
    add(
        "cabinetry.safety.tip_over_policy",
        "PASS",
        "advisory",
        (
            "A sourced, conservative tip-over notice and owner-clearance policy "
            "is attached to the installation/use gate. It does not establish "
            "connection capacity or assert that 16 CFR part 1261 applies."
        ),
        "public_guidance",
        source=(installation_policy.source_url + " | "
                + installation_policy.scope_source_url),
        standard_ref=(
            "CPSC Anchor It! general guidance; permanently attached built-ins "
            "are outside the cited clothing-storage-unit rule scope"
        ),
    )

    return CabinetReport(
        mode=model.mode,
        findings=tuple(sorted(findings, key=lambda finding: finding.rule)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        installation_use_policy=installation_policy,
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

    shell_rows, shell_fastener, shell_joinery_ok = _shell_joinery_facts(model)
    add(
        "cabinetry.joinery.shell_machining",
        "PASS" if shell_joinery_ok else "FAIL",
        "required",
        f"Carcass/toe joinery has {len(shell_rows)} machining rows and "
        f"{sum(row.count for row in shell_rows)} fastener positions; each "
        "position must be in its cut blank, name its receiving part and "
        f"datum, and match {shell_fastener.sku} step-drill geometry.",
        "manufacturer_rated",
        source=shell_fastener.source_url,
        affected=tuple(row.part_id for row in shell_rows),
    )

    toe_rows, toe_fastener, toe_penetration, toe_attachment_ok = \
        toe_attachment_facts(model)
    add(
        "cabinetry.joinery.toe_attachment_machining",
        "PASS" if toe_attachment_ok else "FAIL",
        "required",
        f"Toe attachment has {len(toe_rows)} rows / "
        f"{sum(row.count for row in toe_rows)} stations for "
        f"{toe_fastener.sku}; modeled rail penetration is "
        f"{toe_penetration:.2f} mm. Stations must remain in solid bottom/rail "
        "stock ahead of the captured-back groove. Pilot diameter/depth, torque, "
        "and connection capacity are not claimed.",
        "calculated",
        source=toe_fastener.source_url,
        affected=tuple(row.part_id for row in toe_rows)
                 or (model.part("bottom").part_id,),
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
        anchor_embedment_facts(model)
    add(
        "cabinetry.install.anchor_embedment",
        "PASS" if embedment_ok else "FAIL",
        "required",
        f"The modeled wall-anchor path for {model.wall_anchor.product} leaves "
        f"{embedment / IN:.3f} in stud embedment after the modeled "
        f"{stack / IN:.3f} in stack; pack minimum is "
        f"{min_embedment / IN:.2f} in. Every modeled screw must start at the "
        "anchor-strip head plane, align with its declared stud, and retain "
        "the selected catalog geometry.",
        "calculated",
        source=model.wall_anchor.source_url,
        affected=_anchor_affected(model),
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
        (
            "The floor-supported base cabinet has anchor product, count, "
            "location, and embedment represented; lateral/withdrawal demand "
            "and connection capacity are not calculated in v1."
            if embedment_ok else
            "A complete, geometrically valid wall-anchor path is not represented; "
            "lateral/withdrawal demand and connection capacity also remain "
            "uncalculated."
        ),
        "unknown",
        source=model.wall_anchor.source_url,
        affected=_anchor_affected(model),
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
