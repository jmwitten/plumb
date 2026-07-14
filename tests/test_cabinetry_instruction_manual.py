"""Cabinetry adapter over the shared CPG instruction-panel engine."""

from hashlib import sha256
from pathlib import Path
import json
import re
import sys

import yaml

from detailgen.packs import compile_project_file


ROOT = Path(__file__).parents[1]
DB40 = ROOT / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"


def _manual():
    from detailgen.packs.cabinetry.instruction_manual import (
        build_cabinetry_instruction_manual,
    )

    project = compile_project_file(DB40)
    project.require_fabrication_release()
    manual = build_cabinetry_instruction_manual(
        project,
        technical_href="frameless_three_drawer_40_build_document.html",
        basename="frameless_three_drawer_40_assembly_manual.html",
    )
    return project, manual


def test_manual_uses_six_canonical_cpg_milestones_and_excludes_only_site_studs():
    project, manual = _manual()

    assert [panel.title for panel in manual.panels] == [
        "Build and square the toe-kick platform",
        "Assemble the open carcass",
        "Close the captured back and attach the toe platform",
        "Build and equip the three drawer boxes",
        "Fit, adjust, label, and remove the drawer fronts",
        "Install and commission the empty cabinet",
    ]
    assert [panel.action for panel in manual.panels] == [
        "fabricate", "assemble", "assemble", "equip", "fit", "install",
    ]
    scheduled = {part_id for part_id, _panel in manual.part_schedule}
    excluded = set(manual.excluded_part_ids)
    placed = {part.id for part in project.detail.assembly.parts}
    assert scheduled.isdisjoint(excluded)
    assert scheduled | excluded == placed
    assert excluded
    assert all(
        project.detail.roles().get(part.name) == "existing"
        for part in project.detail.assembly.parts if part.id in excluded
    )


def test_manual_operation_diagrams_are_typed_and_derived_from_release_facts():
    project, manual = _manual()

    assert [[diagram.diagram_id for diagram in panel.diagrams]
            for panel in manual.panels] == [
        ["toe-platform-plan"],
        ["open-carcass-sequence"],
        ["captured-back-close", "toe-attachment-pattern"],
        ["drawer-box-joinery", "runner-fixing-pattern", "drawer-hardware-plan"],
        ["applied-front-pattern"],
        ["wall-anchor-path"],
    ]
    assert all(
        diagram.source_refs
        for panel in manual.panels
        for diagram in panel.diagrams
    )
    assert all(
        primitive.fact_ref
        for panel in manual.panels
        for diagram in panel.diagrams
        for primitive in diagram.primitives
        if primitive.model_point_mm
    )
    assert all(
        link.href.startswith("https://") and link.source_ref
        for panel in manual.panels
        for link in panel.procedure_links
    )
    assert all(panel.procedure_links for panel in manual.panels)
    assert any("movento_ep" in link.href
               for link in manual.panels[4].procedure_links)
    assert any("movento_ep" in link.href
               for link in manual.panels[5].procedure_links)
    procedure_links = tuple(
        link for panel in manual.panels for link in panel.procedure_links
        if link.kind == "procedure"
    )
    assert procedure_links
    assert all("page" in link.label.lower() or "step" in link.label.lower()
               for link in procedure_links)
    assert all(link.kind in {"procedure", "product_reference"}
               for panel in manual.panels for link in panel.procedure_links)
    assert not any("Hafele_Serbia_catalog.pdf" in link.href
                   for panel in manual.panels for link in panel.procedure_links)
    movento_by_panel = {
        panel.index: next(
            link.label for link in panel.procedure_links
            if "movento_ep" in link.href
        )
        for panel in manual.panels[3:]
    }
    assert "pages 9–10" in movento_by_panel[4]
    assert "pages 14–15" in movento_by_panel[4]
    assert "pages 11 and 32" in movento_by_panel[4]
    assert "pages 9–10" in movento_by_panel[5]
    assert "pages 9–10" in movento_by_panel[6]

    assert sum(
        primitive.role == "station"
        for primitive in manual.panels[0].diagrams[0].primitives
    ) == 8
    assert sum(
        primitive.role == "station"
        for primitive in manual.panels[1].diagrams[0].primitives
    ) == 5
    drawer_joinery = manual.panels[3].diagrams[0]
    assert sum(primitive.role == "station"
               for primitive in drawer_joinery.primitives) == 24
    front_pattern = manual.panels[4].diagrams[0]
    assert sum(primitive.role == "hardware"
               for primitive in front_pattern.primitives) == 6
    assert sum(primitive.role == "fastener"
               for primitive in front_pattern.primitives) == 12
    close_back = manual.panels[2].diagrams[0]
    assert sum(primitive.role == "station"
               for primitive in close_back.primitives) == 13
    assert "13 generated close-out Confirmat positions" in close_back.caption
    hardware = manual.panels[3].diagrams[2]
    assert sum(primitive.role == "fastener"
               for primitive in hardware.primitives) == 4
    assert "4 template-controlled screws per drawer × 3 drawers = 12" \
        in hardware.caption

    toe = manual.panels[2].diagrams[1]
    toe_stations = [
        primitive for primitive in toe.primitives
        if primitive.role == "station"
    ]
    assert len(toe_stations) == 6
    toe_rows = [row for row in project.model.machining
                if row.kind == "toe_attachment_station"]
    expected_toe_points = {
        (row.location_mm[0] + index * row.pitch_mm, row.location_mm[1])
        for row in toe_rows for index in range(row.count)
    }
    assert {primitive.model_point_mm for primitive in toe_stations} == expected_toe_points

    runner = manual.panels[3].diagrams[1]
    runner_stations = [
        primitive for primitive in runner.primitives
        if primitive.role == "station"
    ]
    expected_runner_points = {
        row.location_mm
        for row in project.model.machining
        if row.kind == "runner_fixing_station" and row.part_id.endswith("left_end")
    }
    assert {primitive.model_point_mm for primitive in runner_stations} == expected_runner_points


def test_visible_diagram_dimensions_follow_a_released_width_variant(tmp_path):
    from detailgen.packs.cabinetry.instruction_manual import (
        build_cabinetry_instruction_manual,
    )

    raw = yaml.safe_load(DB40.read_text())
    raw["name"] = "DB42 released width-variant probe"
    raw["cabinetry"]["cabinets"][0]["width"] = 42
    project_path = tmp_path / "db42.project.yaml"
    project_path.write_text(yaml.safe_dump(raw, sort_keys=False))
    project = compile_project_file(project_path)
    project.require_fabrication_release()
    manual = build_cabinetry_instruction_manual(
        project, technical_href="db42_build.html", basename="db42_manual.html",
    )
    by_id = {
        diagram.diagram_id: diagram
        for panel in manual.panels
        for diagram in panel.diagrams
    }

    hardware_caption = by_id["drawer-hardware-plan"].caption
    front_caption = by_id["applied-front-pattern"].caption
    assert "(979.700, 24.000) mm" in hardware_caption
    assert "1063.800 mm-wide" in front_caption
    assert "246.675/740.025 mm" in front_caption
    assert "419.900/643.900 mm" in front_caption
    for stale in ("(928.9, 24)", "1013.0 mm-wide", "233.975/701.925",
                  "394.500/618.500"):
        assert stale not in hardware_caption + front_caption


def test_manual_instructions_and_inventory_are_pack_model_backed():
    project, manual = _manual()
    text = "\n".join(
        value
        for panel in manual.panels
        for value in (
            panel.title, *panel.instructions, *panel.rationales,
            *panel.honesty, *(row.label for row in panel.hardware),
            *(row.label for row in panel.tools),
        )
    )
    inventory = "\n".join(row.label for row in manual.inventory)
    policy = project.report.installation_use_policy
    assert policy is not None
    hold_notice = policy.reader_notice(released=False)
    assert hold_notice in manual.lede
    assert any(hold_notice in item for item in manual.panels[5].honesty)
    assert hold_notice in next(
        step.instruction for step in project.artifacts.installation_steps
        if step.step_id == "install.release_gate"
    )
    assert policy.source_url.startswith("https://www.cpsc.gov/")
    assert policy.scope_source_url.startswith("https://www.cpsc.gov/")
    assert policy.scope_source_url != policy.source_url
    assert "16 CFR part 1261 applies" in policy.scope_note
    assert "permanently attached" in policy.scope_note

    for phrase in (
        "leave the right side and rear stretcher off",
        "Slide the captured back into the open left-side and bottom grooves",
        "5 606N screws per runner",
        "pilot depth is not claimed",
        "remove the three labeled drawer assemblies",
        "whole-cabinet structural capacity remains unqualified",
        "Safety glasses",
        "ship the empty carcass and its attached toe platform as one unit",
        "set the empty cabinet and its attached toe platform together",
        "Do not load or use the cabinet",
        "qualified cabinet or structural design professional",
        "serious or fatal crushing injury",
    ):
        assert phrase in text
    for item in project.artifacts.hardware_schedule:
        assert item.product_id in inventory
    assert "50 individual screws" in inventory
    assert "42 individual screws" in inventory
    assert "18 individual screws" in inventory
    assert "6 handed pieces = 3 left/right pairs" in inventory
    assert "3 complete sets; one set per drawer" in inventory
    assert "Shop-supply line — titebond_original_5064@2026.1" in inventory
    assert "Procurement HOLD — edge band" in inventory
    assert "Procurement HOLD — sheet nesting" in inventory
    assert "per drawer: left/right pinion housings, two racks" in inventory
    assert "40 lb" not in "\n".join(manual.panels[5].instructions)
    assert "shop supply; quantity is one procurement line" in inventory
    assert "1 container — titebond_original_5064@2026.1" not in inventory
    assert "pre-band" in inventory
    assert "finished model size" in manual.lede

    panel_hardware = ["\n".join(row.label for row in panel.hardware)
                      for panel in manual.panels]
    assert "8 screw — hafele_confirmat" in panel_hardware[0]
    assert "5 screw — hafele_confirmat" in panel_hardware[1]
    assert "13 screw — hafele_confirmat" in panel_hardware[2]
    assert "24 screw — hafele_confirmat" in panel_hardware[3]
    assert "30 screw — blum_606n" in panel_hardware[3]


def test_real_document_set_has_relative_links_and_six_shared_panel_assets(
        tmp_path, monkeypatch):
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        import cabinetry_documents as documents
    finally:
        sys.path.remove(str(scripts))

    calls = {"compile_project_file": 0, "render_product_views": 0}
    real_compile_project_file = documents.compile_project_file
    real_render_views = documents.CPR._render_views

    def counted_compile_project_file(*args, **kwargs):
        calls["compile_project_file"] += 1
        return real_compile_project_file(*args, **kwargs)

    def counted_render_views(*args, **kwargs):
        calls["render_product_views"] += 1
        return real_render_views(*args, **kwargs)

    monkeypatch.setattr(
        documents, "compile_project_file", counted_compile_project_file,
    )
    monkeypatch.setattr(documents.CPR, "_render_views", counted_render_views)

    result = documents.build_cabinetry_document_pair(
        tmp_path, project_path=DB40, image_size=(480, 360)
    )
    assert calls == {"compile_project_file": 1, "render_product_views": 1}
    path_keys = (
        "technical_path", "manual_path", "fabrication_path", "audit_path",
    )
    hash_keys = (
        "technical_sha256", "manual_sha256", "fabrication_sha256",
        "audit_sha256",
    )
    missing_keys = (set(path_keys) | set(hash_keys)) - result.keys()
    assert not missing_keys, (
        f"document set is missing output keys: {sorted(missing_keys)}"
    )

    paths = {key: Path(result[key]) for key in path_keys}
    expected_basenames = {
        "technical_path": "frameless_three_drawer_40_build_document.html",
        "manual_path": "frameless_three_drawer_40_assembly_manual.html",
        "fabrication_path": "frameless_three_drawer_40_fabrication_packet.html",
        "audit_path": "frameless_three_drawer_40_review_trace.html",
    }
    assert {key: path.name for key, path in paths.items()} == expected_basenames
    assert all(path.is_file() for path in paths.values())
    for path_key, hash_key in zip(path_keys, hash_keys):
        assert result[hash_key] == sha256(paths[path_key].read_bytes()).hexdigest()

    documents_by_key = {
        key: path.read_text(encoding="utf-8") for key, path in paths.items()
    }
    technical = documents_by_key["technical_path"]
    manual = documents_by_key["manual_path"]
    fabrication = documents_by_key["fabrication_path"]
    audit = documents_by_key["audit_path"]

    assert result["panel_count"] == 6
    assert len(result["panel_images"]) == 6
    assert len(set(result["asset_keys"])) == 6
    assert all(Path(path).is_file() for path in result["panel_images"])
    required_links = {
        "technical_path": (
            expected_basenames["manual_path"],
            expected_basenames["fabrication_path"],
            expected_basenames["audit_path"],
        ),
        "manual_path": (
            expected_basenames["technical_path"],
            expected_basenames["fabrication_path"],
            expected_basenames["audit_path"],
        ),
        "fabrication_path": (
            expected_basenames["technical_path"],
            expected_basenames["manual_path"],
        ),
        "audit_path": (expected_basenames["technical_path"],),
    }
    for source_key, targets in required_links.items():
        for target in targets:
            assert f'href="{target}"' in documents_by_key[source_key]
    viewer_markers = ('id="detail-data-', 'id="detail-glb-', "THREE.GLTFLoader")
    for marker in viewer_markers:
        assert marker in technical
        assert marker not in manual
        assert marker not in fabrication
        assert marker not in audit
    assert '"instruction_panels":[' in technical
    payload = json.loads(re.search(
        r'<script type="application/json" id="detail-data-[^"]+">(.*?)</script>',
        technical,
        re.DOTALL,
    ).group(1))
    assert [panel["number"] for panel in payload["instruction_panels"]] == [
        1, 2, 3, 4, 5, 6,
    ]
    assert manual.count('class="instruction-panel"') == 6
    assert manual.count('class="operation-diagram"') == 9
    # Exact station facts must be visible and keyboard/screen-reader readable;
    # hover-only SVG titles are not an instruction surface.
    assert manual.count('class="diagram-coordinate-key"') == 9
    assert manual.count('class="diagram-coordinate-row"') == 95
    assert 'aria-describedby="coordinate-key-toe-attachment-pattern"' in manual
    assert "Toe attachment screw center — X 244.475 mm, Y 85.725 mm" in manual
    assert "Runner fixing station — X 10.000 mm, Z 652.450 mm" in manual
    assert 'data-model-point="244.475,85.725"' in manual
    assert manual.count('class="procedure-links"') == 6
    assert "Manufacturer procedures and product references" in manual
    assert "Safety throughout" in manual
    assert "external manufacturer links require internet" in manual
    assert 'aria-label="Toe attachment screw center' in manual
    assert 'aria-label="Runner fixing station' in manual
    assert "data:image/png;base64," in manual
    assert '<link rel="icon" href="data:,">' in manual
    assert "file://" not in technical + manual + fabrication + audit
    for stale in ("armchair caddy", "sofa arm", "hot-drink"):
        assert stale not in manual.lower()
