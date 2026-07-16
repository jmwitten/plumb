"""Complete preview-package contract for the model-backed family birdhouse."""

import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from detailgen.design_review import DesignReviewGateError


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import family_birdhouse_report as FBR


pytestmark = pytest.mark.detail_gate(
    "family_birdhouse",
    contracts=("documents",),
    cadence="release",
)


def test_still_shading_is_invariant_to_tessellation_winding():
    face = FBR.np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    )

    colors = FBR._shade((0.7, 0.4, 0.2), [face, face[[0, 2, 1]]])

    assert colors[0] == pytest.approx(colors[1])


def test_still_frame_uses_clean_axis_free_orthographic_presentation():
    calls = []

    class _Axis:
        def __getattr__(self, name):
            return lambda *args, **kwargs: calls.append((name, args, kwargs))

    FBR._configure_still_axis(
        _Axis(),
        FBR.np.array([0.0, 0.0, 0.0]),
        FBR.np.array([1.0, 2.0, 3.0]),
        elev=20,
        azim=-40,
        title="Probe",
    )

    assert ("set_proj_type", ("ortho",), {}) in calls
    assert ("set_axis_off", (), {}) in calls


def test_still_faces_do_not_draw_internal_tessellation_edges():
    assert FBR._still_edge_style() == {
        "edgecolors": "none",
        "linewidths": 0.0,
    }


def test_five_still_views_tessellate_each_placed_part_once(monkeypatch, tmp_path):
    class _Component:
        material_key = "cedar"

        @staticmethod
        def capability_tags():
            return frozenset()

    parts = [
        SimpleNamespace(name=f"part {index}", component=_Component())
        for index in range(3)
    ]

    class _Detail:
        assembly = SimpleNamespace(parts=parts)

        @staticmethod
        def build():
            return None

        @staticmethod
        def explode_vectors():
            return {parts[-1].name: (1.0, 0.0, 0.0)}

    calls = []

    def fake_part_polys(part):
        calls.append(part.name)
        return (
            FBR.np.array(
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 1.0]]
            ),
            ((0, 1, 2),),
        )

    monkeypatch.setattr(FBR, "_part_polys", fake_part_polys)

    written = FBR.render_family_birdhouse_views(_Detail(), tmp_path)

    assert len(written) == 5
    assert calls == [part.name for part in parts]


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    out = tmp_path_factory.mktemp("family-birdhouse-package")
    result = FBR.build_family_birdhouse_package(
        out,
        image_size=(520, 380),
        preview=True,
    )
    return out, result


def test_package_contains_model_documents_data_and_model_exports(package):
    out, result = package
    expected = {
        "technical_path",
        "manual_path",
        "fabrication_path",
        "installation_path",
        "design_review_path",
        "bom_csv_path",
        "cut_csv_path",
        "package_manifest_path",
        "step_path",
        "glb_path",
        "model_manifest_path",
    }
    assert expected <= set(result)
    assert all(Path(result[key]).is_file() for key in expected)
    assert result["preview"] is True
    assert result["panel_count"] >= 3
    assert len(result["panel_images"]) == result["panel_count"]
    assert all(Path(path).is_file() for path in result["panel_images"])
    assert len(list((out / "views").glob("*.png"))) == 5
    expected_phases = {
        "compile_validate",
        "documentation_export",
        "still_views",
        "instruction_panels",
        "technical_document",
        "companion_documents",
        "package_hashing",
        "total",
    }
    assert expected_phases == set(result["performance_seconds"])
    assert all(
        seconds >= 0.0
        for seconds in result["performance_seconds"].values()
    )


def test_every_reader_document_is_reciprocal_offline_and_unmistakably_preview(package):
    _out, result = package
    docs = {
        "technical": Path(result["technical_path"]).read_text(),
        "manual": Path(result["manual_path"]).read_text(),
        "fabrication": Path(result["fabrication_path"]).read_text(),
        "installation": Path(result["installation_path"]).read_text(),
    }
    basenames = {
        Path(result[key]).name
        for key in (
            "technical_path",
            "manual_path",
            "fabrication_path",
            "installation_path",
        )
    }
    for name, html in docs.items():
        assert FBR.PREVIEW_NOTICE in html, name
        # Vendored Three.js contains namespace constants such as
        # http://www.w3.org/1999/xhtml; the offline contract is that the
        # document never fetches a remote script, image, or model asset.
        assert 'src="http://' not in html
        assert "src='http://" not in html
        assert 'src="https://' not in html
        assert "src='https://" not in html
        assert "file://" not in html
        assert sum(basename in html for basename in basenames - {Path(result[name + "_path"]).name}) >= 2
    assert 'id="detail-data-' in docs["technical"]
    assert 'id="detail-glb-' in docs["technical"]
    assert "model-backed" in docs["technical"].lower()


def test_guides_carry_model_facts_family_boundaries_and_field_holds(package):
    _out, result = package
    joined = "\n".join(
        Path(result[key]).read_text()
        for key in (
            "technical_path",
            "manual_path",
            "fabrication_path",
            "installation_path",
        )
    )
    for phrase in (
        "1 1/8",
        "four high side vents",
        "four floor drains",
        "ADULT-ONLY",
        "CHILD-SUITABLE",
        "pivot",
        "latch",
        "no exterior perch",
        "FIELD HOLD",
        "predator baffle",
        "utilities",
        "capacity NOT analyzed",
    ):
        assert phrase.lower() in joined.lower()


def test_family_manual_uses_birdhouse_join_and_member_neutral_fastener_copy(package):
    _out, result = package
    manual = Path(result["manual_path"]).read_text()

    for stale in ("sofa arm", "hot-drink", "along-arm", "through the rail"):
        assert stale not in manual.lower()
    assert "Bench assembly complete" in manual
    assert "field installation remains on hold" in manual
    assert "11 × Exterior wood screw" in manual
    assert "6 × Exterior wood screw" in manual
    assert "15 × Exterior wood screw" in manual
    assert "17 × fixed-side front lower screw" not in manual


def test_reader_documents_compact_print_only_content_without_orphan_pages(package):
    _out, result = package
    manual = Path(result["manual_path"]).read_text()
    fabrication = Path(result["fabrication_path"]).read_text()

    assert ".overview{display:flex;flex-direction:column" in manual
    assert ".overview>div:last-child{order:-1" in manual
    assert ".inventory{columns:2" in manual
    assert ".manual-head{padding:.65rem 1.2rem" in manual
    assert ".inventory{font-size:.68rem" in manual
    assert ".manual-foot{display:none}" in manual
    assert "footer{display:none}" in fabrication


def test_csvs_and_manifest_are_derived_and_fingerprint_bound(package):
    _out, result = package
    with Path(result["bom_csv_path"]).open(newline="") as handle:
        bom = list(csv.DictReader(handle))
    with Path(result["cut_csv_path"]).open(newline="") as handle:
        cuts = list(csv.DictReader(handle))
    manifest = json.loads(Path(result["package_manifest_path"]).read_text())
    model_manifest = json.loads(Path(result["model_manifest_path"]).read_text())

    assert any(row["item"] == "3/4 in cedar panel" for row in bom)
    assert any(row["item"] == "Exterior wood screw" for row in bom)
    assert len(cuts) == 7
    assert sum(int(row["bore_count"]) for row in cuts) == 9
    assert manifest["release_state"] == FBR.PREVIEW_NOTICE
    assert manifest["geometry_authority"] == "compiled Plumb DetailSpec"
    assert manifest["validation"]["blocking_count"] == 0
    assert manifest["facts"]["cedar_part_count"] == 7
    assert manifest["facts"]["exterior_screw_count"] == 21
    assert manifest["facts"]["bore_count"] == 9
    assert manifest["selection_fingerprint"]
    assert manifest["model_fingerprint"]
    assert manifest["assembly_hash"] == model_manifest["build"]["assembly_hash"]
    assert all(len(value) == 64 for value in manifest["file_sha256"].values())


def test_unconfirmed_delivery_writes_nothing(tmp_path):
    out = tmp_path / "delivery"

    with pytest.raises(DesignReviewGateError, match="delivery confirmation"):
        FBR.build_family_birdhouse_package(
            out,
            image_size=(320, 240),
            preview=False,
        )

    assert not out.exists()
