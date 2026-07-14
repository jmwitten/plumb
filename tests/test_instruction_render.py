"""Geometry-station and image-rendering acceptance tests for +presentation."""

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from detailgen.rendering.caddy_stations import attach_caddy_stations
from detailgen.rendering.instruction_panels import (
    InstructionPresentationError,
    build_instruction_manual,
)
from detailgen.rendering.instruction_render import (
    _stations_for_overlay,
    panel_content_key,
    render_instruction_images,
    render_instruction_panel,
)
from detailgen.spec.compiler import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details" / "armchair_caddy.spec.yaml"


@pytest.fixture(scope="module")
def caddy():
    detail = compile_spec_file(SPEC)
    detail.validate()
    return detail


@pytest.fixture(scope="module")
def stationed(caddy):
    manual = build_instruction_manual(caddy)
    return attach_caddy_stations(caddy, manual)


def _panel(manual, action):
    return next(panel for panel in manual.panels if panel.action == action)


def _write_ungoverned_variant(path, text):
    raw = yaml.safe_load(text)
    raw.pop("design_review", None)
    path.write_text(yaml.safe_dump(raw, sort_keys=False))


def test_instruction_rendering_api_is_public():
    from detailgen.rendering import (
        attach_caddy_stations,
        panel_content_key,
        render_instruction_manual_html,
        render_instruction_images,
        render_instruction_panel,
    )

    assert all(callable(value) for value in (
        attach_caddy_stations,
        panel_content_key,
        render_instruction_manual_html,
        render_instruction_images,
        render_instruction_panel,
    ))


def test_prepare_station_locates_bore_from_both_top_panel_ends(caddy, stationed):
    prepare = _panel(stationed, "prepare")
    bore = next(station for station in prepare.stations
                if station.feature == "cup hole center")

    assert bore.reference_part_id == next(
        part.id for part in caddy.assembly.parts
        if part.reader_name == "Top panel")
    assert bore.reference_length_mm == pytest.approx(203.2)
    assert bore.near_mm == pytest.approx(101.6)
    assert bore.far_mm == pytest.approx(101.6)
    assert "from either end" in bore.label
    assert "width centerline" in bore.label
    assert "+X" not in bore.label and "-X" not in bore.label


def test_bond_stations_locate_each_corner_key_pair_from_panel_edges(stationed):
    bond = _panel(stationed, "bond")

    assert len(bond.stations) == 2
    assert {station.feature for station in bond.stations} == {
        "symmetric corner-key pair"}
    for station in bond.stations:
        assert station.near_mm == pytest.approx(30.1625)
        assert station.far_mm == pytest.approx(109.5375)
        assert station.reference_length_mm == pytest.approx(139.7)
        assert "from each front/back edge" in station.label
        assert "miter faces close without a gap" in station.label
        assert station.mirror_p0 is not None and station.mirror_p1 is not None
        assert "+X" not in station.label and "-X" not in station.label
    labels = "\n".join(station.label for station in bond.stations)
    assert "Side panel (1 of 2)" in labels
    assert "Side panel (2 of 2)" in labels


def test_bond_stations_reconcile_symmetric_pairs_from_either_panel_edge(stationed):
    bond = _panel(stationed, "bond")

    assert len(bond.stations) == 2
    assert {round(station.near_mm, 2) for station in bond.stations} == {30.16}
    assert all(
        station.near_mm + station.far_mm
        == pytest.approx(station.reference_length_mm)
        for station in bond.stations
    )
    labels = "\n".join(station.label for station in bond.stations)
    assert '1-3/16" from each front/back edge' in labels
    assert "+X" not in labels and "-X" not in labels
    instructions = "\n".join(bond.instructions)
    assert instructions.count("Dry-fit the 45-degree miter") == 2
    assert instructions.count("Insert both corner keys") == 2


def test_bond_overlay_draws_every_corner_key_station(
    stationed,
):
    bond = _panel(stationed, "bond")

    markers, dimensions = _stations_for_overlay(bond)

    assert markers == bond.stations
    assert dimensions == bond.stations
    assert len({station.reference_part_id for station in markers}) == 1


def test_moving_authored_dowel_offset_moves_raw_stations_and_rekeys(
    caddy, stationed, tmp_path,
):
    changed_spec = tmp_path / SPEC.name
    _write_ungoverned_variant(
        changed_spec,
        SPEC.read_text().replace(
            "dowel_edge_station: 1.1875", "dowel_edge_station: 1.0"),
    )
    changed = compile_spec_file(changed_spec)
    changed.validate()
    changed_manual = attach_caddy_stations(
        changed, build_instruction_manual(changed))

    original = _panel(stationed, "bond")
    moved = _panel(changed_manual, "bond")
    assert {round(station.near_mm, 2) for station in moved.stations} == {
        25.4}
    assert tuple(station.near_mm for station in original.stations) != tuple(
        station.near_mm for station in moved.stations)
    assert panel_content_key(caddy, original) != panel_content_key(changed, moved)
    assert panel_content_key(caddy, _panel(stationed, "prepare")) == \
        panel_content_key(changed, _panel(changed_manual, "prepare"))
    assert panel_content_key(caddy, _panel(stationed, "cure")) != \
        panel_content_key(changed, _panel(changed_manual, "cure"))
    assert panel_content_key(
        caddy, _panel(stationed, "join")) != panel_content_key(
            changed, _panel(changed_manual, "join"))


def test_asymmetric_corner_key_pair_without_a_physical_edge_anchor_fails_closed(
    caddy, tmp_path,
):
    changed_spec = tmp_path / SPEC.name
    _write_ungoverned_variant(
        changed_spec,
        SPEC.read_text().replace(
            'at: ["$side_inner_x", "$dowel_station_far", "$top_top_z"]',
            'at: ["$side_inner_x", "= dowel_station_far - 0.2", "$top_top_z"]',
            1,
        ),
    )
    changed = compile_spec_file(changed_spec)
    changed.validate()

    with pytest.raises(
        InstructionPresentationError,
        match="corner keys.*not symmetric.*front/back edges",
    ):
        attach_caddy_stations(changed, build_instruction_manual(changed))


def test_content_key_ignores_prose_but_covers_station_inputs(caddy, stationed):
    panel = _panel(stationed, "bond")
    prose_only = replace(
        panel,
        title="Editor-only alternate title",
        rationales=("Review-store wording that does not change the image.",),
    )
    moved_station = replace(panel.stations[0], near_mm=panel.stations[0].near_mm + 1)
    changed_station = replace(
        panel, stations=(moved_station, *panel.stations[1:]))

    assert panel_content_key(caddy, prose_only) == panel_content_key(caddy, panel)
    assert panel_content_key(caddy, changed_station) != panel_content_key(caddy, panel)


def test_content_key_covers_source_event_identity(caddy, stationed):
    panel = _panel(stationed, "bond")
    changed_event = replace(
        panel,
        source_events=(*panel.source_events[:-1], ("drive", "different", "role")),
    )

    assert panel.source_events
    assert panel_content_key(caddy, changed_event) != panel_content_key(caddy, panel)


def test_renderer_writes_stable_keyed_png_for_every_panel(
    caddy, stationed, tmp_path,
):
    from PIL import Image

    paths = render_instruction_images(caddy, stationed, tmp_path, size=(1200, 900))
    assert set(paths) == {panel.index for panel in stationed.panels}

    before = {}
    for panel in stationed.panels:
        path = paths[panel.index]
        key = panel_content_key(caddy, panel, size=(1200, 900))
        assert path.name == f"{key}.png"
        assert path.stat().st_size > 20_000
        before[path] = (path.read_bytes(), path.stat().st_mtime_ns)
        with Image.open(path) as image:
            assert image.size == (1200, 900)
            assert image.info["detailgen_panel_key"] == key
            assert int(image.info["detailgen_callout_count"]) > 0
            assert int(image.info["detailgen_station_count"]) == len(panel.stations)
            assert image.getcolors(maxcolors=1_000_000) is not None
            assert len(image.getcolors(maxcolors=1_000_000)) > 50

    repeated = render_instruction_images(caddy, stationed, tmp_path, size=(1200, 900))
    assert repeated == paths
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == value
               for path, value in before.items())


def test_overlay_failure_does_not_publish_or_poison_a_content_key(
    caddy, stationed, tmp_path, monkeypatch,
):
    from PIL import Image
    import detailgen.rendering.instruction_render as renderer_module

    panel = _panel(stationed, "bond")
    key = panel_content_key(caddy, panel, size=(320, 240))
    expected = tmp_path / f"{key}.png"
    real_draw_overlay = renderer_module._draw_overlay

    def interrupted_overlay(*args, **kwargs):
        raise RuntimeError("simulated overlay interruption")

    monkeypatch.setattr(renderer_module, "_draw_overlay", interrupted_overlay)
    with pytest.raises(RuntimeError, match="simulated overlay interruption"):
        render_instruction_panel(
            caddy, panel, tmp_path, size=(320, 240))
    assert not expected.exists()

    monkeypatch.setattr(renderer_module, "_draw_overlay", real_draw_overlay)
    retried = render_instruction_panel(
        caddy, panel, tmp_path, size=(320, 240))
    with Image.open(retried) as image:
        assert image.info["detailgen_panel_key"] == key


def test_invalid_cached_png_is_rebuilt_instead_of_reused(
    caddy, stationed, tmp_path,
):
    from PIL import Image

    panel = _panel(stationed, "prepare")
    size = (320, 240)
    key = panel_content_key(caddy, panel, size=size)
    poisoned = tmp_path / f"{key}.png"
    Image.new("RGB", size, "white").save(poisoned)

    rebuilt = render_instruction_panel(caddy, panel, tmp_path, size=size)

    with Image.open(rebuilt) as image:
        assert image.info["detailgen_panel_key"] == key
        assert int(image.info["detailgen_callout_count"]) > 0


def test_process_and_join_panels_render_their_semantic_roles(
    caddy, stationed, tmp_path,
):
    from PIL import Image

    paths = render_instruction_images(caddy, stationed, tmp_path, size=(1200, 900))
    cure = _panel(stationed, "cure")
    join = _panel(stationed, "join")
    context_id = next(part.id for part in caddy.assembly.parts
                      if part.reader_name == "Sofa arm")

    assert cure.arrival_part_ids == ()
    assert cure.focus_part_ids
    with Image.open(paths[cure.index]) as image:
        assert int(image.info["detailgen_ghost_count"]) > 0
        assert int(image.info["detailgen_focus_count"]) == len(cure.focus_part_ids)
    with Image.open(paths[join.index]) as image:
        assert context_id in image.info["detailgen_visible_part_ids"].split(",")
        assert int(image.info["detailgen_arrival_count"]) == 1


def test_stationed_panels_draw_dimension_blue_and_numbered_callouts(
    caddy, stationed, tmp_path,
):
    from PIL import Image

    paths = render_instruction_images(caddy, stationed, tmp_path, size=(1200, 900))
    image = Image.open(paths[_panel(stationed, "bond").index]).convert("RGB")
    colors = dict((color, count) for count, color in image.getcolors(1_000_000))

    assert colors[(37, 99, 235)] > 50  # dimension leaders/text
    assert colors[(17, 24, 39)] > 50  # callout outlines/numbers


def test_image_size_is_part_of_the_content_key(caddy, stationed):
    panel = stationed.panels[0]
    assert panel_content_key(caddy, panel, size=(1200, 900)) != \
        panel_content_key(caddy, panel, size=(1500, 1100))


def test_high_contrast_style_rekeys_but_default_key_is_unchanged(
        caddy, stationed):
    panel = stationed.panels[0]
    base = panel_content_key(caddy, panel)
    assert panel_content_key(caddy, panel, style="technical") == base
    assert panel_content_key(caddy, panel, style="high_contrast") != base


def test_unknown_style_is_rejected():
    from detailgen.rendering.instruction_render import instruction_style
    with pytest.raises(ValueError, match="style"):
        instruction_style("sepia")


def test_high_contrast_style_is_dark_work_on_light_prior():
    from detailgen.rendering.instruction_render import instruction_style

    def luminance(rgb):
        r, g, b = rgb
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    style = instruction_style("high_contrast")
    assert style.use_material_color is False
    assert luminance(style.work_color) < 0.25
    assert luminance(style.prior_color) > 0.7
    # grayscale printing: fills must be far apart in luminance
    assert luminance(style.prior_color) - luminance(style.work_color) >= 0.5
    assert style.prior_opacity == 1.0
    assert style.edge_color == (0.0, 0.0, 0.0)
    assert style.edge_visibility is True


def test_technical_style_matches_established_rendering():
    from detailgen.rendering.instruction_render import instruction_style
    style = instruction_style("technical")
    assert style.use_material_color is True
    assert style.prior_color == (0.72, 0.72, 0.72)
    assert style.prior_opacity == 0.16
    assert style.edge_visibility is False


def test_render_frame_images_keys_by_frame_with_frame_focus(
        caddy, stationed, tmp_path):
    from detailgen.rendering.action_frames import ActionFrame, FrameIllustration
    from detailgen.rendering.instruction_render import render_frame_images

    panel = stationed.panels[0]
    frames = tuple(
        ActionFrame(
            frame_id=f"prepare.{part_id}",
            caption="Prepare the part.",
            source_step_ids=("prepare",),
            owned_events=(("place", part_id, ""),),
            focus_part_ids=(part_id,),
            illustration=FrameIllustration(
                intent="assembly_scene", panel_index=panel.index),
        )
        for part_id in panel.focus_part_ids[:2]
    )
    paths = render_frame_images(
        caddy, stationed, frames, tmp_path, size=(300, 220),
        style="high_contrast")
    assert set(paths) == {frame.frame_id for frame in frames}
    resolved = {frame_id: str(path) for frame_id, path in paths.items()}
    assert len(set(resolved.values())) == 2  # distinct focus -> distinct keys
    for path in paths.values():
        assert path.is_file() and path.suffix == ".png"


def test_render_frame_images_skips_hold_gate_frames(caddy, stationed,
                                                    tmp_path):
    from detailgen.rendering.action_frames import ActionFrame, FrameIllustration
    from detailgen.rendering.instruction_render import render_frame_images

    panel = stationed.panels[0]
    frames = (ActionFrame(
        frame_id="hold.gate",
        caption="Stop until cleared.",
        source_step_ids=("gate",),
        owned_events=(),
        focus_part_ids=(panel.focus_part_ids[0],),
        is_hold_gate=True,
        illustration=FrameIllustration(
            intent="assembly_scene", panel_index=panel.index),
    ),)
    assert render_frame_images(
        caddy, stationed, frames, tmp_path, size=(200, 150)) == {}
