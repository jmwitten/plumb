"""End-to-end contract for the separate illustrated caddy manual."""

import json
import re
import shutil
import sys
import html as html_module
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import caddy_documents as CD
import single_detail_report as SDR


@pytest.fixture(scope="module")
def legacy_caddy_spec(tmp_path_factory):
    spec_dir = tmp_path_factory.mktemp("legacy-caddy-spec")
    raw = yaml.safe_load(SDR.CADDY_SPEC.read_text())
    raw.pop("design_review")
    path = spec_dir / SDR.CADDY_SPEC.name
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    return path


@pytest.fixture(scope="module")
def pair(tmp_path_factory, legacy_caddy_spec):
    out_dir = tmp_path_factory.mktemp("caddy-document-pair")
    return CD.build_caddy_document_pair(
        out_dir, image_size=(1200, 900), spec_path=legacy_caddy_spec)


def _visible_text(html: str) -> str:
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                   flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return html_module.unescape(re.sub(r"\s+", " ", value))


def test_pair_has_exact_distinct_basenames_and_reciprocal_relative_links(pair):
    technical = Path(pair["technical_path"])
    manual = Path(pair["manual_path"])

    assert technical.name == "armchair_caddy_build_document.html"
    assert manual.name == "armchair_caddy_assembly_manual.html"
    assert technical.parent == manual.parent
    assert technical != manual
    assert f'href="{manual.name}"' in technical.read_text()
    assert f'href="{technical.name}"' in manual.read_text()
    assert "file://" not in technical.read_text() + manual.read_text()


def test_technical_companion_uses_the_same_five_panel_schedule(pair):
    technical = Path(pair["technical_path"]).read_text()
    match = re.search(
        r'<script type="application/json" id="detail-data-armchair_caddy">'
        r'(.*?)</script>',
        technical,
        flags=re.S,
    )
    assert match is not None
    payload = json.loads(match.group(1))

    assert [panel["number"] for panel in payload["instruction_panels"]] == [
        1, 2, 3, 4, 5]
    assert payload["parts"]["top board"]["first_panel"] == 1
    assert payload["parts"]["rail-side screw +X upper 0"]["first_panel"] == 4
    assert payload["parts"]["sofa arm"]["first_panel"] == 5


def test_pair_compiles_the_detail_only_once(
    monkeypatch, tmp_path, legacy_caddy_spec,
):
    calls = []
    real_compile = CD.compile_spec_file

    def counted_compile(path):
        calls.append(Path(path))
        return real_compile(path)

    monkeypatch.setattr(CD, "compile_spec_file", counted_compile)
    monkeypatch.setattr(SDR, "compile_spec_file", counted_compile)

    CD.build_caddy_document_pair(
        tmp_path, image_size=(320, 240), spec_path=legacy_caddy_spec)

    assert calls == [legacy_caddy_spec]


def test_pair_compiles_once_when_ignored_legacy_views_are_missing(
    monkeypatch, tmp_path, legacy_caddy_spec,
):
    calls = []
    rendered_details = []
    real_compile = CD.compile_spec_file
    consumer = SDR.CONSUMERS[SDR.CADDY_SPEC.name]
    missing_views = tmp_path / "clean-checkout-views"

    def counted_compile(path):
        calls.append(Path(path))
        return real_compile(path)

    def render_from_compiled(detail, out_dir):
        rendered_details.append(detail)
        out_dir.mkdir(parents=True)
        for basename in consumer["view_files"].values():
            (out_dir / basename).write_bytes(b"model-backed-test-view")

    monkeypatch.setattr(CD, "compile_spec_file", counted_compile)
    monkeypatch.setattr(SDR, "compile_spec_file", counted_compile)
    monkeypatch.setitem(consumer, "views_dir", missing_views)
    monkeypatch.setitem(consumer, "render_views", render_from_compiled)
    monkeypatch.setitem(
        consumer,
        "ensure_views",
        lambda: pytest.fail("clean pair must not launch a compiling subprocess"),
    )

    CD.build_caddy_document_pair(
        tmp_path / "pair",
        image_size=(320, 240),
        spec_path=legacy_caddy_spec,
    )

    assert calls == [legacy_caddy_spec]
    assert len(rendered_details) == 1
    assert rendered_details[0].report is not None


def test_ordinary_technical_header_has_no_broken_companion_link():
    detail = SDR.compile_spec_file(SDR.CADDY_SPEC)
    detail.validate()
    headline = "Physical geometry — PASS"
    plain = SDR._title_block(detail, headline, SDR.CADDY_TITLE_BLOCK)
    linked = SDR._title_block(
        detail, headline, SDR.CADDY_TITLE_BLOCK,
        companion_href="armchair_caddy_assembly_manual.html")

    assert "assembly manual" not in plain.lower()
    assert 'href="armchair_caddy_assembly_manual.html"' in linked
    with pytest.raises(ValueError, match="relative HTML basename"):
        SDR._title_block(
            detail, headline, SDR.CADDY_TITLE_BLOCK,
            companion_href="../manual.html")


def test_manual_is_self_contained_and_has_one_model_backed_panel_per_cohort(pair):
    html = Path(pair["manual_path"]).read_text()

    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert html.count('class="instruction-panel"') == 5
    assert html.count("data:image/png;base64,") == 5
    assert "src=\"http" not in html and "href=\"http" not in html
    visible = _visible_text(html)
    assert "Prepare Top board, 2 × Side board, and 2 × Registration rail" in visible
    assert "Bond 2 × Registration rail and Top board" in visible
    assert "Hold 2 adhesive bonds to full cure" in visible
    assert "Fasten 2 × Registration rail and 2 × Side board" in visible
    assert "Set completed armchair caddy over Sofa arm" in visible
    assert '<input id="panel-slider" type="range" min="1" max="5"' in html
    assert 'id="panel-progress"' in html
    assert "ArrowLeft" in html and "ArrowRight" in html
    assert "hashchange" in html
    assert "@media print" in html and ".panel-controls{display:none}" in html


def test_manual_renders_typed_resource_icons_and_release_boundary(pair):
    html = Path(pair["manual_path"]).read_text()
    visible = _visible_text(html)

    for icon in ("screw", "adhesive", "clamp", "driver"):
        assert f'data-icon="{icon}"' in html
        assert f'aria-label="{icon} icon"' in html
    assert html.count('class="resource-icon"') >= 4
    assert "A blocking modeled failure blocks release" in visible
    assert "Prototype only" in visible
    assert html.count(f'href="{Path(pair["technical_path"]).name}"') == 2
    assert '<footer class="manual-foot">' in html


def test_manual_carries_typed_gates_stations_rationales_and_declared_trust(pair):
    visible = _visible_text(Path(pair["manual_path"]).read_text())

    for text in (
        "4-3/4\" from either end",
        "front/back edges flush",
        "2.15\" from each rail end",
        "3/4\" below the top underside",
        "No generic duration is represented",
        "Why this order",
        "DECLARED TRUST",
        "insertion travel is not analyzed",
    ):
        assert text in visible
    for machine_term in ("+X", "-X", "lumber-", "structural_screw-"):
        assert machine_term not in visible


def test_manual_explains_callout_numbers_with_shared_reader_names(pair):
    visible = _visible_text(Path(pair["manual_path"]).read_text())

    assert "Picture key" in visible
    assert "Top board" in visible
    assert "Side board" in visible
    assert "Registration rail" in visible
    assert "Rail-to-side screw" in visible
    assert "Sofa arm" in visible


def test_pair_reports_content_hashes_and_five_keyed_panel_images(pair):
    assert len(pair["technical_sha256"]) == 64
    assert len(pair["manual_sha256"]) == 64
    assert pair["technical_sha256"] != pair["manual_sha256"]
    paths = tuple(Path(path) for path in pair["panel_images"])
    assert len(paths) == 5
    assert all(re.fullmatch(r"[0-9a-f]{64}\.png", path.name)
               for path in paths)
    assert all(path.exists() for path in paths)
    assert pair["panel_count"] == 5
    assert pair["asset_keys"] == tuple(path.stem for path in paths)


def test_pair_regeneration_is_deterministic_after_generated_stamp_normalization(
        tmp_path, legacy_caddy_spec):
    first = CD.build_caddy_document_pair(
        tmp_path / "first",
        image_size=(320, 240),
        spec_path=legacy_caddy_spec,
    )
    second = CD.build_caddy_document_pair(
        tmp_path / "second",
        image_size=(320, 240),
        spec_path=legacy_caddy_spec,
    )

    stamp = re.compile(
        r"Generated \d{4}-\d{2}-\d{2} \d{2}:\d{2} [A-Z]+")

    def normalize_generated_stamp(value):
        value = stamp.sub("Generated <normalized>", value)
        return re.sub(
            r"(<dt>Generated</dt><dd>)\d{4}-\d{2}-\d{2} \d{2}:\d{2} [A-Z]+",
            r"\1<normalized>",
            value,
        )

    for key in ("technical_path", "manual_path"):
        left = normalize_generated_stamp(Path(first[key]).read_text())
        right = normalize_generated_stamp(Path(second[key]).read_text())
        assert left == right

    assert first["asset_keys"] == second["asset_keys"]
    assert [Path(path).read_bytes() for path in first["panel_images"]] == [
        Path(path).read_bytes() for path in second["panel_images"]]

    manual_path = Path(first["manual_path"])
    before = manual_path.read_bytes()
    shutil.rmtree(manual_path.parent / "instruction_panels")
    assert manual_path.read_bytes() == before
    assert before.count(b"data:image/png;base64,") == 5
    assert b"instruction_panels/" not in before
