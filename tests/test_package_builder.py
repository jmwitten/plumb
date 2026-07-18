from pathlib import Path

from detailgen.package import PackageRequest
from detailgen.package.builder import build_package


ROOT = Path(__file__).resolve().parents[1]


def test_builder_compiles_once_and_writes_content_addressed_manifest(
    monkeypatch, tmp_path
):
    import detailgen.package.builder as builder_module

    calls = {"compile": 0}
    spec = ROOT / "details" / "armchair_caddy.spec.yaml"
    real_compile = builder_module.compile_spec_file

    def compile_once(path):
        calls["compile"] += 1
        return real_compile(path)

    monkeypatch.setattr(
        "detailgen.package.builder.compile_spec_file",
        compile_once,
    )
    out = tmp_path / "out"
    result = build_package(PackageRequest(spec, out, views=("iso",)))

    assert calls["compile"] == 1
    assert result.validation_ok is True
    assert (out / "package-manifest.json").is_file()
    assert all(len(artifact.sha256) == 64 for artifact in result.artifacts)

    technical = (out / "technical.html").read_text(encoding="utf-8")
    assembly = (out / "assembly.html").read_text(encoding="utf-8")
    assert 'src="views/iso.png"' in technical
    assert 'class="viewer-section"' in assembly
    assert 'src="views/iso.png"' in assembly
    assert 'id="detail-data-' in assembly
    assert 'id="detail-glb-' in assembly
    assert "Explode" in assembly
    assert assembly.index('class="viewer-section"') < assembly.index(
        'class="overview"'
    ) < assembly.index('id="panel-1"')
    installation = out / "installation.html"
    assert installation.is_file()
    assert "Installation contracts" in installation.read_text(encoding="utf-8")
    assert "installation.html" in {
        artifact.relative_path for artifact in result.artifacts
    }


def test_two_existing_governed_details_share_the_same_builder(tmp_path):
    specs = (
        ROOT / "details" / "armchair_caddy.spec.yaml",
        ROOT / "details" / "family_birdhouse.spec.yaml",
    )

    results = [
        build_package(
            PackageRequest(spec, tmp_path / spec.stem, views=("iso",))
        )
        for spec in specs
    ]

    assert all(result.validation_ok for result in results)
    assert all(len(result.artifacts) >= 8 for result in results)
    assert all(
        (result.request.output_dir / "installation.html").is_file()
        for result in results
    )
    birdhouse_installation = (
        results[1].request.output_dir / "installation.html"
    ).read_text(encoding="utf-8")
    assert "pivoted_by" in birdhouse_installation
    assert "latched_by" in birdhouse_installation
