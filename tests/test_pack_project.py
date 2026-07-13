"""Packed-project front-end contract.

The pack layer is additive: it has its own strict loader and compilation-local
registry, and importing it cannot mutate DetailSpec's process-wide vocabulary.
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest

from detailgen.core.registry import components


def test_pack_package_exists_without_mutating_base_component_registry():
    before = tuple(components.names())
    assert importlib.util.find_spec("detailgen.packs") is not None
    importlib.import_module("detailgen.packs")
    assert tuple(components.names()) == before


def _api():
    from detailgen.packs.project import (
        PackRegistry,
        ProjectSchemaError,
        compile_project,
        load_project_text,
    )

    return PackRegistry, ProjectSchemaError, compile_project, load_project_text


class _EchoPack:
    pack_id = "example.echo"
    major_version = 1
    version = "1.0.0"
    section_keys = ("echo",)

    def compile(self, doc):
        return {
            "name": doc.name,
            "units": doc.units,
            "payload": doc.sections["echo"],
        }


def test_project_loads_and_resolves_an_exact_pack_in_local_registry():
    PackRegistry, _, compile_project, load_project_text = _api()
    registry = PackRegistry([_EchoPack()])
    doc = load_project_text(
        """
name: hello pack
units: in
packs: [example.echo@1]
echo: {message: hello}
"""
    )

    result = compile_project(doc, registry=registry)

    assert result == {
        "name": "hello pack",
        "units": "in",
        "payload": {"message": "hello"},
    }


def test_unknown_pack_lists_available_exact_versions():
    PackRegistry, ProjectSchemaError, compile_project, load_project_text = _api()
    registry = PackRegistry([_EchoPack()])
    doc = load_project_text(
        "name: x\nunits: in\npacks: [example.missing@1]\n"
        "example: {}\n"
    )

    with pytest.raises(ProjectSchemaError) as exc:
        compile_project(doc, registry=registry)

    message = str(exc.value)
    assert "unknown pack 'example.missing@1'" in message
    assert "example.echo@1" in message


def test_wrong_major_version_is_not_silently_upgraded_or_downgraded():
    PackRegistry, ProjectSchemaError, compile_project, load_project_text = _api()
    registry = PackRegistry([_EchoPack()])
    doc = load_project_text(
        "name: x\nunits: in\npacks: [example.echo@2]\necho: {}\n"
    )

    with pytest.raises(ProjectSchemaError, match=r"unknown pack 'example\.echo@2'.*example\.echo@1"):
        compile_project(doc, registry=registry)


def test_duplicate_pack_activation_is_rejected_at_load():
    _, ProjectSchemaError, _, load_project_text = _api()

    with pytest.raises(ProjectSchemaError, match="duplicate pack activation"):
        load_project_text(
            "name: x\nunits: in\n"
            "packs: [example.echo@1, example.echo@1]\necho: {}\n"
        )


def test_pack_reference_requires_explicit_integer_major_version():
    _, ProjectSchemaError, _, load_project_text = _api()

    for bad in ("example.echo", "example.echo@latest", "example.echo@1.0"):
        with pytest.raises(ProjectSchemaError, match="<pack-id>@<major-version>"):
            load_project_text(
                f"name: x\nunits: in\npacks: [{bad}]\necho: {{}}\n"
            )


def test_project_rejects_unclaimed_top_level_section_with_near_match():
    PackRegistry, ProjectSchemaError, compile_project, load_project_text = _api()
    registry = PackRegistry([_EchoPack()])
    doc = load_project_text(
        "name: x\nunits: in\npacks: [example.echo@1]\necoh: {}\n"
    )

    with pytest.raises(ProjectSchemaError) as exc:
        compile_project(doc, registry=registry)

    message = str(exc.value)
    assert "unclaimed project section 'ecoh'" in message
    assert "echo" in message


def test_project_loader_rejects_unknown_units_and_non_mapping_sections():
    _, ProjectSchemaError, _, load_project_text = _api()

    with pytest.raises(ProjectSchemaError, match="units.*one of"):
        load_project_text("name: x\nunits: cm\npacks: [example.echo@1]\necho: {}\n")

    with pytest.raises(ProjectSchemaError, match="section 'echo'.*mapping"):
        load_project_text("name: x\nunits: in\npacks: [example.echo@1]\necho: nope\n")

