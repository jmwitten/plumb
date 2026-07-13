"""Composition of proven single-cabinet models into one straight cabinet run."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ...spec.schema import (
    AuthoredStage,
    BondSpec,
    ContactSpec,
    DetailSpecDoc,
    OverlapSpec,
    SequenceSpec,
    ValidationSpec,
)
from .artifacts import (
    CabinetArtifacts,
    HardwareItem,
    WorkStep,
    build_artifacts,
)
from .catalogs import get_assembly_fastener
from .evidence import EvidenceRecord
from .lowering import _component, lower_model
from .model import (
    CabinetModel,
    HardwareSystem,
    PartModel,
    Provenance,
    build_model,
)
from .schema import CabinetrySection
from .validation import CabinetFinding, CabinetReport, validate_model


@dataclass(frozen=True)
class CabinetRunModel:
    project_name: str
    mode: str
    profile: object
    hinge: object
    wall_anchor: object
    section: CabinetrySection
    cabinets: tuple[CabinetModel, ...]
    parts: tuple[object, ...]
    machining: tuple[object, ...]
    hardware: tuple[object, ...]
    derived: tuple[object, ...]
    source_map: dict
    anchor_stud_ids: tuple[str, ...]
    connector_groups: tuple[tuple[str, str, tuple[str, ...]], ...]


def build_run_model(section: CabinetrySection, *, project_name: str) -> CabinetRunModel:
    models = tuple(
        build_model(replace(section, cabinets=(cabinet,)), project_name=project_name)
        for cabinet in section.cabinets
    )
    first = models[0]
    site_parts = tuple(
        part for part in first.parts if part.role.startswith("wall_stud_")
    )
    cabinet_parts = tuple(
        part for model in models for part in model.parts
        if not part.role.startswith("wall_stud_")
    )
    source_map = dict(first.source_map)
    for model in models[1:]:
        source_map.update({
            key: value for key, value in model.source_map.items()
            if not key.startswith("site.")
        })
    connector = get_assembly_fastener(
        "grk_low_profile_cabinet_8x1_1_4_114069@2026.1"
    )
    connector_parts: list[PartModel] = []
    connector_groups: list[tuple[str, str, tuple[str, ...]]] = []
    for left, right in zip(models, models[1:]):
        left_cabinet = left.section.cabinets[0]
        right_cabinet = right.section.cabinets[0]
        boundary_x = right.part("left_end").at_mm[0]
        face_x = boundary_x - left.profile.carcass_thickness_mm
        wall_y = section.site.wall.plane_origin_mm[1]
        front_y = wall_y - left_cabinet.depth_mm
        z0 = left.part("right_end").at_mm[2]
        h = left.part("right_end").length_mm
        positions = (
            (front_y + left_cabinet.depth_mm * 0.25, z0 + h * 0.32),
            (front_y + left_cabinet.depth_mm * 0.75, z0 + h * 0.32),
            (front_y + left_cabinet.depth_mm * 0.25, z0 + h * 0.68),
            (front_y + left_cabinet.depth_mm * 0.75, z0 + h * 0.68),
        )
        ids: list[str] = []
        pair = f"{left_cabinet.cabinet_id}_to_{right_cabinet.cabinet_id}"
        for index, (y, z) in enumerate(positions, start=1):
            part_id = (
                f"cabinetry.{left_cabinet.cabinet_id}."
                f"case_connector_to_{right_cabinet.cabinet_id}_{index}"
            )
            ids.append(part_id)
            connector_parts.append(PartModel(
                part_id=part_id,
                role=f"case_connector_{pair}_{index}",
                name=f"{left_cabinet.cabinet_id} to "
                     f"{right_cabinet.cabinet_id} case connector {index}",
                component_type="structural_screw",
                params=(("diameter", connector.diameter_mm),
                        ("length", connector.length_mm)),
                at_mm=(face_x, y, z),
                rotate=(("Y", -90.0),),
                length_mm=connector.length_mm,
                width_mm=connector.diameter_mm,
                thickness_mm=connector.diameter_mm,
                surface_class="concealed",
            ))
            source_map[part_id] = Provenance(
                declared_at=f"cabinetry.run.{pair}",
                rule="cabinetry.run.case_connector",
                profile_id=first.profile.profile_id,
                catalog_id=connector.product_id,
                archetype_id=(
                    left_cabinet.source_archetype
                    if left_cabinet.source_archetype == right_cabinet.source_archetype
                    else ""
                ),
            )
        connector_groups.append((
            f"cabinetry.{left_cabinet.cabinet_id}.right_end",
            f"cabinetry.{right_cabinet.cabinet_id}.left_end",
            tuple(ids),
        ))
    run_hardware = (
        HardwareSystem(
            system_id="cabinetry.run.case_connectors",
            kind="cabinet_to_cabinet_connection",
            product_id=connector.product_id,
            quantity=len(connector_parts),
            related_parts=tuple(part.part_id for part in connector_parts),
            evidence="manufacturer_rated",
            source_url=connector.source_url,
        ),
    ) if connector_parts else ()
    return CabinetRunModel(
        project_name=project_name,
        mode=section.mode,
        profile=first.profile,
        hinge=first.hinge,
        wall_anchor=first.wall_anchor,
        section=section,
        cabinets=models,
        parts=cabinet_parts + tuple(connector_parts) + site_parts,
        machining=tuple(item for model in models for item in model.machining),
        hardware=(tuple(item for model in models for item in model.hardware)
                  + run_hardware),
        derived=tuple(item for model in models for item in model.derived),
        source_map=source_map,
        anchor_stud_ids=tuple(dict.fromkeys(
            stud_id for model in models for stud_id in model.anchor_stud_ids
        )),
        connector_groups=tuple(connector_groups),
    )


def lower_run_model(run: CabinetRunModel) -> DetailSpecDoc:
    docs = tuple(lower_model(model) for model in run.cabinets)
    first = docs[0]
    site_ids = {component.id for component in first.components
                if component.id.startswith("site.")}
    components = list(first.components)
    bonds = list(first.validation.bonds)
    contacts = list(first.validation.contacts)
    overlaps = list(first.validation.expected_overlaps)
    roles = dict(first.roles)
    grounds = set(first.context_grounds)
    for doc in docs[1:]:
        components.extend(component for component in doc.components
                          if component.id not in site_ids)
        bonds.extend(doc.validation.bonds)
        contacts.extend(doc.validation.contacts)
        overlaps.extend(doc.validation.expected_overlaps)
        roles.update(doc.roles)
        grounds.update(doc.context_grounds)

    connector_ids = {
        connector_id
        for _, _, group in run.connector_groups
        for connector_id in group
    }
    components.extend(
        _component(part) for part in run.parts if part.part_id in connector_ids
    )
    for left_id, right_id, group in run.connector_groups:
        contacts.append(ContactSpec(left_id, right_id))
        for connector_id in group:
            bonds.extend((
                BondSpec(connector_id, left_id),
                BondSpec(connector_id, right_id),
            ))
            overlaps.extend((
                OverlapSpec(connector_id, left_id),
                OverlapSpec(connector_id, right_id),
            ))

    wall_anchor_ids = tuple(sorted(
        component.id for component in components
        if ".wall_anchor_" in component.id
    ))
    join_ids = tuple(sorted(connector_ids))
    stages = [
        AuthoredStage(
            name="set_neighboring_cases",
            why=("The adjacent case ends are set level, plumb, and flush before "
                 "connector pilots are drilled."),
            parts=tuple(sorted({
                part_id for left_id, right_id, _ in run.connector_groups
                for part_id in (left_id, right_id)
            })),
        ),
        AuthoredStage(
            name="join_neighboring_cases",
            why=("Neighboring cases are clamped flush and joined while their "
                 "wall fasteners remain loose."),
            parts=join_ids,
        ),
    ]
    if wall_anchor_ids:
        stages.append(AuthoredStage(
            name="anchor_run_to_wall",
            why=("Wall anchors are tightened only after the connected run has "
                 "one aligned face and level plane."),
            parts=wall_anchor_ids,
        ))
    sequence = SequenceSpec(stages=tuple(stages))

    return DetailSpecDoc(
        name=run.project_name,
        type="cabinetry_frameless_base_run",
        units="mm",
        components=components,
        validation=ValidationSpec(
            bonds=bonds,
            contacts=contacts,
            expected_overlaps=overlaps,
        ),
        roles=roles,
        context_grounds=frozenset(grounds),
        sequence=sequence,
    )


def validate_run_model(run: CabinetRunModel) -> CabinetReport:
    findings: list[CabinetFinding] = []
    evidence: list[EvidenceRecord] = []
    for model in run.cabinets:
        cabinet_id = model.section.cabinets[0].cabinet_id
        report = validate_model(model)
        for item in report.evidence:
            evidence_id = f"evidence:cabinetry.{cabinet_id}:{item.evidence_id}"
            evidence.append(replace(item, evidence_id=evidence_id))
        for finding in report.findings:
            evidence_ids = tuple(
                f"evidence:cabinetry.{cabinet_id}:{item}"
                for item in finding.evidence_ids
            )
            findings.append(replace(
                finding,
                rule=f"cabinetry.{cabinet_id}.{finding.rule.removeprefix('cabinetry.')}",
                evidence_ids=evidence_ids,
            ))

    run_message = (
        f"Straight run contains {len(run.cabinets)} touching cabinets in "
        "surveyed left-to-right order with reciprocal adjacent-end conditions."
    )
    run_evidence_id = "evidence:cabinetry.run.adjacency"
    evidence.append(EvidenceRecord(
        evidence_id=run_evidence_id,
        subject="cabinetry.run.adjacency",
        level="derived",
        statement=run_message,
    ))
    findings.append(CabinetFinding(
        rule="cabinetry.run.adjacency",
        verdict="PASS",
        severity="required",
        message=run_message,
        evidence_level="derived",
        evidence_ids=(run_evidence_id,),
        affected=tuple(
            f"cabinetry.{model.section.cabinets[0].cabinet_id}"
            for model in run.cabinets
        ),
    ))
    return CabinetReport(
        mode=run.mode,
        findings=tuple(sorted(findings, key=lambda item: item.rule)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
    )


def _prefixed_steps(cabinet_id: str, steps, offset: int):
    return tuple(
        replace(step, phase=offset + step.phase,
                step_id=f"{cabinet_id}.{step.step_id}")
        for step in steps
    )


def build_run_artifacts(run: CabinetRunModel, report: CabinetReport) -> CabinetArtifacts:
    singles = tuple(
        build_artifacts(model, validate_model(model)) for model in run.cabinets
    )
    connector = get_assembly_fastener(
        "grk_low_profile_cabinet_8x1_1_4_114069@2026.1"
    )
    related = tuple(
        part_id
        for left, right in zip(run.cabinets, run.cabinets[1:])
        for part_id in (
            f"cabinetry.{left.section.cabinets[0].cabinet_id}.right_end",
            f"cabinetry.{right.section.cabinets[0].cabinet_id}.left_end",
        )
    )
    run_hardware = HardwareItem(
        system_id="cabinetry.run.case_connectors",
        kind="cabinet_to_cabinet_connection",
        product_id=connector.product_id,
        quantity=4 * (len(run.cabinets) - 1),
        source_url=connector.source_url,
        evidence="manufacturer_rated",
        related_parts=related,
    )
    fabrication_steps = tuple(
        step for index, (model, artifact) in enumerate(zip(run.cabinets, singles))
        for step in _prefixed_steps(
            model.section.cabinets[0].cabinet_id,
            artifact.fabrication_steps,
            index * 1000,
        )
    )
    assembly_steps = tuple(
        step for index, (model, artifact) in enumerate(zip(run.cabinets, singles))
        for step in _prefixed_steps(
            model.section.cabinets[0].cabinet_id,
            artifact.assembly_steps,
            index * 1000,
        )
    )
    before_join = [
        replace(step, step_id=(
            f"{model.section.cabinets[0].cabinet_id}.{step.step_id}"
        ))
        for model, artifact in zip(run.cabinets, singles)
        for step in artifact.installation_steps
        if step.phase <= 50
    ]
    after_join = [
        replace(step, step_id=(
            f"{model.section.cabinets[0].cabinet_id}.{step.step_id}"
        ))
        for model, artifact in zip(run.cabinets, singles)
        for step in artifact.installation_steps
        if step.phase > 50
    ]
    ordered = before_join + [
        WorkStep(
            phase=0,
            step_id="run.join_cabinets",
            instruction=(
                "After each neighboring case is independently level, plumb, and "
                "shimmed, clamp the finished front edges flush, verify the door "
                "reveal plane, pilot clear of hinge plates and shelf-pin rows, "
                "then install four scheduled GRK #8 x 1-1/4 in cabinet connectors "
                "through each paired side before final wall-anchor tightening."
            ),
            affected=related,
            evidence="manufacturer_rated",
        ),
    ] + after_join
    installation_steps = tuple(
        replace(step, phase=(index + 1) * 10)
        for index, step in enumerate(ordered)
    )
    return CabinetArtifacts(
        schema="detailgen/cabinetry-artifacts/v1",
        project=run.project_name,
        pack="cabinetry.frameless@1.0.0",
        profile=run.profile.profile_id,
        mode=run.mode,
        release_ready=False,
        cut_list=tuple(item for artifact in singles for item in artifact.cut_list),
        edge_banding=tuple(item for artifact in singles
                           for item in artifact.edge_banding),
        hardware_schedule=(
            tuple(item for artifact in singles for item in artifact.hardware_schedule)
            + (run_hardware,)
        ),
        machining_schedule=tuple(item for artifact in singles
                                 for item in artifact.machining_schedule),
        fabrication_steps=fabrication_steps,
        assembly_steps=assembly_steps,
        installation_steps=installation_steps,
    )
