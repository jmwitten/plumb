"""The opt-in ``cabinetry.frameless@1`` compiler front end."""

from __future__ import annotations

from ...spec import compile_spec
from ..project import PackedProject, ProjectSchemaError
from .artifacts import build_artifacts
from .drawer_base import build_drawer_base_model
from .lowering import lower_model
from .model import build_model
from .presets import expand_cabinetry_project
from .run import (
    build_run_artifacts,
    build_run_model,
    lower_run_model,
    validate_run_model,
)
from .schema import CabinetrySection, DrawerBaseDecl, parse_cabinetry_project
from .validation import validate_model
from .vanity import FramelessVanityPack


class FramelessCabinetryPack:
    pack_id = "cabinetry.frameless"
    major_version = 1
    version = "1.0.0"
    section_keys = ("site", "cabinetry")

    def parse(self, doc) -> CabinetrySection:
        expanded, source_archetypes = expand_cabinetry_project(doc)
        return parse_cabinetry_project(expanded, source_archetypes)

    def compile(self, doc):
        expanded, source_archetypes = expand_cabinetry_project(doc)
        section = parse_cabinetry_project(expanded, source_archetypes)
        drawer_bases = tuple(
            cabinet for cabinet in section.cabinets
            if isinstance(cabinet, DrawerBaseDecl)
        )
        if drawer_bases and len(section.cabinets) != 1:
            raise ProjectSchemaError(
                "cabinetry.frameless@1 v1 supports drawer_base_three@1 only as "
                "a single-cabinet project; mixed straight runs are not yet "
                "implemented"
            )
        if len(section.cabinets) == 1:
            if drawer_bases:
                model = build_drawer_base_model(section, project_name=doc.name)
            else:
                model = build_model(section, project_name=doc.name)
            lowered = lower_model(model)
            report = validate_model(model)
            artifacts = build_artifacts(model, report)
        else:
            model = build_run_model(section, project_name=doc.name)
            lowered = lower_run_model(model)
            report = validate_run_model(model)
            artifacts = build_run_artifacts(model, report)
        detail = compile_spec(lowered)
        return PackedProject(
            project_doc=doc,
            model=model,
            lowered_doc=lowered,
            detail=detail,
            report=report,
            artifacts=artifacts,
            pack_id=self.pack_id,
            pack_version=self.version,
            expanded_project_doc=expanded,
        )


__all__ = [
    "CabinetrySection", "FramelessCabinetryPack", "FramelessVanityPack"
]
