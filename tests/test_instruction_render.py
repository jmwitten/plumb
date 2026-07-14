"""Geometry-station and image-rendering acceptance tests for +presentation."""

from dataclasses import replace
from pathlib import Path

import pytest

from detailgen.rendering.caddy_stations import attach_caddy_stations
from detailgen.rendering.instruction_panels import (
    InstructionPresentationError,
    build_instruction_manual,
)
from detailgen.rendering.instruction_render import (
    panel_content_key,
    render_instruction_images,
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


def test_prepare_station_locates_bore_from_both_top_board_ends(caddy, stationed):
    prepare = _panel(stationed, "prepare")
    bore = next(station for station in prepare.stations
                if station.feature == "cup hole center")

    assert bore.reference_part_id == next(
        part.id for part in caddy.assembly.parts
        if part.reader_name == "Top board")
    assert bore.reference_length_mm == pytest.approx(241.3)
    assert bore.near_mm == pytest.approx(120.65)
    assert bore.far_mm == pytest.approx(120.65)
    assert "from either end" in bore.label
    assert "width centerline" in bore.label
    assert "+X" not in bore.label and "-X" not in bore.label


def test_bond_stations_locate_each_rail_from_top_and_flush_datums(stationed):
    bond = _panel(stationed, "bond")

    assert len(bond.stations) == 2
    assert {station.feature for station in bond.stations} == {
        "registration rail placement"}
    for station in bond.stations:
        assert station.near_mm == pytest.approx(19.05)
        assert station.far_mm == pytest.approx(222.25)
        assert station.reference_length_mm == pytest.approx(241.3)
        assert "front/back edges flush" in station.label
        assert "top underside" in station.label
        assert "+X" not in station.label and "-X" not in station.label


def test_fasten_stations_locate_symmetric_pairs_from_either_rail_end(stationed):
    fasten = _panel(stationed, "fasten")

    assert len(fasten.stations) == 4
    assert {round(station.near_mm, 2) for station in fasten.stations} == {
        54.61}
    assert all(
        station.near_mm + station.far_mm
        == pytest.approx(station.reference_length_mm)
        for station in fasten.stations
    )
    labels = "\n".join(station.label for station in fasten.stations)
    assert {round(station.secondary_mm, 2)
            for station in fasten.stations} == {19.05, 101.6}
    assert all(station.q0 is not None and station.q1 is not None
               for station in fasten.stations)
    assert all(station.mirror_p0 is not None and station.mirror_p1 is not None
               for station in fasten.stations)
    assert '3/4" below the top underside' in labels
    assert '4" below the top underside' in labels
    assert "from each rail end" in labels
    assert "front rail end" not in labels and "back rail end" not in labels
    assert "+X" not in labels and "-X" not in labels


def test_moving_authored_screw_offset_moves_raw_stations_and_rekeys(
    caddy, stationed, tmp_path,
):
    changed_spec = tmp_path / SPEC.name
    changed_spec.write_text(
        SPEC.read_text().replace("screw_dy_h: 0.6", "screw_dy_h: 0.8"))
    changed = compile_spec_file(changed_spec)
    changed.validate()
    changed_manual = attach_caddy_stations(
        changed, build_instruction_manual(changed))

    original = _panel(stationed, "fasten")
    moved = _panel(changed_manual, "fasten")
    assert {round(station.near_mm, 2) for station in moved.stations} == {
        49.53}
    assert tuple(station.near_mm for station in original.stations) != tuple(
        station.near_mm for station in moved.stations)
    assert panel_content_key(caddy, original) != panel_content_key(changed, moved)
    for action in ("prepare", "bond", "cure"):
        assert panel_content_key(caddy, _panel(stationed, action)) == \
            panel_content_key(changed, _panel(changed_manual, action))
    assert panel_content_key(
        caddy, _panel(stationed, "join")) != panel_content_key(
            changed, _panel(changed_manual, "join"))


def test_asymmetric_screw_pair_without_a_physical_end_anchor_fails_closed(
    caddy, tmp_path,
):
    changed_spec = tmp_path / SPEC.name
    changed_spec.write_text(SPEC.read_text().replace(
        'place: {raw: {at: ["$rail_inner_x", "$screw_dy_h", '
        '"$sidescrew_z_u"], rotate: [["Y", -90]]}}',
        'place: {raw: {at: ["$rail_inner_x", "= screw_dy_h + 0.2", '
        '"$sidescrew_z_u"], rotate: [["Y", -90]]}}',
        1,
    ))
    changed = compile_spec_file(changed_spec)
    changed.validate()

    with pytest.raises(
        InstructionPresentationError,
        match="screw pair.*not end-symmetric.*physical end anchor",
    ):
        attach_caddy_stations(changed, build_instruction_manual(changed))


def test_content_key_ignores_prose_but_covers_station_inputs(caddy, stationed):
    panel = _panel(stationed, "fasten")
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
    panel = _panel(stationed, "fasten")
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
    image = Image.open(paths[_panel(stationed, "fasten").index]).convert("RGB")
    colors = dict((color, count) for count, color in image.getcolors(1_000_000))

    assert colors[(37, 99, 235)] > 50  # dimension leaders/text
    assert colors[(17, 24, 39)] > 50  # callout outlines/numbers


def test_image_size_is_part_of_the_content_key(caddy, stationed):
    panel = stationed.panels[0]
    assert panel_content_key(caddy, panel, size=(1200, 900)) != \
        panel_content_key(caddy, panel, size=(1500, 1100))
