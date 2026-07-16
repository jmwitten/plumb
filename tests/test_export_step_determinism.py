import cadquery as cq

from detailgen.assemblies import DetailAssembly
from detailgen.components import ConcretePier, Lumber, Washer
from detailgen.core import IN
from detailgen.rendering.export import export_step


def _colored_assembly():
    assembly = DetailAssembly("deterministic STEP")
    assembly.add(Lumber("2x4", 4 * IN, name="board"))
    assembly.add(Washer(0.25 * IN, name="washer"), at=(20, 50, 20))
    assembly.add(
        ConcretePier(8 * IN, 12 * IN, name="transparent concrete"),
        at=(200, 0, 0),
    )
    return assembly


def test_step_export_is_byte_stable_and_reimportable(tmp_path):
    first = export_step(_colored_assembly(), tmp_path / "first.step")
    second = export_step(_colored_assembly(), tmp_path / "second.step")

    assert first.read_bytes() == second.read_bytes()
    imported = cq.importers.importStep(str(first))
    assert imported.solids().size() == 3
