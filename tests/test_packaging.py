"""The optional pack ships and its public/architectural contract is documented."""

from pathlib import Path
import tomllib

ROOT = Path(__file__).parents[1]


def test_wheel_configuration_lists_pack_packages():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    packages = set(data["tool"]["setuptools"]["packages"])

    assert "detailgen.packs" in packages
    assert "detailgen.packs.cabinetry" in packages


def test_public_pack_api_is_importable():
    from detailgen.packs import (
        PackedProject,
        ProjectReleaseError,
        compile_project_file,
        load_project_file,
    )

    assert callable(compile_project_file)
    assert callable(load_project_file)
    assert issubclass(ProjectReleaseError, RuntimeError)
    assert PackedProject.__module__ == "detailgen.packs.project"


def test_readme_documents_explicit_pack_activation_and_truth_boundary():
    text = (ROOT / "README.md").read_text()

    assert "cabinetry.frameless@1" in text
    assert "compile_project_file" in text
    assert "does not claim KCMA certification" in text


def test_project_memory_records_the_pack_boundary_and_entry_point():
    text = (ROOT / "CLAUDE.md").read_text()

    assert "src/packs/" in text
    assert "compile_project_file" in text
    assert "must not mutate the global base registries" in text

