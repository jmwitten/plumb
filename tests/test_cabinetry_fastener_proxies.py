"""Schematic fastener proxies for the DB40 presentation explode scene.

The proxies are a PRESENTATION-only overlay: opt-in, positioned only at typed
machining stations, and they must never perturb the validated model surfaces.
These tests pin the count contract (one proxy per scheduled fastener in a
covered class), the position contract (every proxy sits on the machined part's
own face at its typed station), the opt-in contract (off by default leaves the
scene and payload byte-for-byte unproxied), and the honesty contract (each
proxy discloses itself as schematic in its tooltip).
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cabinetry_project_report as CPR  # noqa: E402
from detailgen.packs import compile_project_file  # noqa: E402
from detailgen.packs.cabinetry.fastener_proxies import (  # noqa: E402
    _COVERED,
    SKIPPED_KINDS,
    append_fastener_proxies,
    proxy_stations,
    _FastenerProxy,
    _thickness_axis,
)

PROJECT = ROOT / "tests/fixtures/cabinetry/frameless_three_drawer_40.project.yaml"

#: Covered machining kind -> hardware-schedule kind whose summed quantity must
#: equal the number of proxies produced. Each covered class is one scheduled
#: fastener product, so the count is a hard cross-check against the release BOM.
_HARDWARE_FOR_KIND = {
    "confirmat_step_drill": "carcass_confirmat_system",
    "drawer_box_confirmat_step_drill": "drawer_box_joinery_fastener",
    "toe_attachment_station": "toe_base_attachment_system",
    "applied_front_attachment": "applied_front_fastener_system",
    "runner_fixing_station": "drawer_runner_installation_screw",
}


@pytest.fixture(scope="module")
def project():
    compiled = compile_project_file(PROJECT)
    compiled.require_fabrication_release()
    return compiled


@pytest.fixture(scope="module")
def scene(project):
    """A fresh product-view presentation assembly (no proxies)."""
    return CPR.product_view_assembly(project)


@pytest.fixture(scope="module")
def stations(project, scene):
    return proxy_stations(project, scene)


def _hardware_qty(project, kind: str) -> int:
    return sum(item.quantity for item in project.artifacts.hardware_schedule
               if item.kind == kind)


def test_covered_and_skipped_kinds_partition_every_machining_kind(project):
    """Every machining kind the model emits is a deliberate decision: either a
    covered proxy class or an explicitly skipped one — nothing falls through."""
    assert set(_COVERED) & set(SKIPPED_KINDS) == set()
    emitted = {row.kind for row in project.model.machining}
    undecided = emitted - set(_COVERED) - set(SKIPPED_KINDS)
    assert undecided == set(), f"machining kinds with no proxy decision: {undecided}"


def test_proxy_count_per_class_matches_the_hardware_schedule(project, stations):
    """One proxy per individual scheduled fastener, per covered class."""
    per_kind = Counter(station.kind for station in stations)
    for kind, hardware_kind in _HARDWARE_FOR_KIND.items():
        assert per_kind[kind] == _hardware_qty(project, hardware_kind), kind
    assert sum(per_kind.values()) == len(stations)


def test_proxy_total_equals_covered_machining_expansion(project, stations):
    """The proxy set is exactly the covered rows expanded by their counts —
    no row dropped, none double-counted."""
    covered_rows = [r for r in project.model.machining if r.kind in _COVERED]
    assert len(stations) == sum(r.count for r in covered_rows)
    per_feature = Counter(station.feature_id for station in stations)
    for row in covered_rows:
        assert per_feature[row.feature_id] == row.count, row.feature_id


def test_every_proxy_sits_exactly_on_its_typed_machining_station(
        project, scene, stations):
    """Each proxy's world position lies on the machined part's own face at the
    thickness-axis extreme, and inside the part footprint — a real point on the
    typed station's part, never an invented location."""
    placed_by_name = {p.name: p for p in scene.parts}
    name_by_id = {p.part_id: p.name for p in project.model.parts}
    rows_by_feature = {r.feature_id: r for r in project.model.machining}

    for station in stations:
        row = rows_by_feature[station.feature_id]
        assert row.kind in _COVERED
        placed = placed_by_name[name_by_id[station.part_id]]
        bbox = placed.world_solid().val().BoundingBox()
        mins = (bbox.xmin, bbox.ymin, bbox.zmin)
        maxs = (bbox.xmax, bbox.ymax, bbox.zmax)
        n = _thickness_axis(placed)
        point = station.world_point
        # Head sits on a thickness-axis face of the machined part.
        assert (abs(point[n] - mins[n]) < 0.6
                or abs(point[n] - maxs[n]) < 0.6), station.feature_id
        # And within the part footprint on every axis (on the face, not off it).
        for k in range(3):
            assert mins[k] - 0.7 <= point[k] <= maxs[k] + 0.7, station.feature_id


def test_explode_vector_runs_along_the_drive_axis(scene, stations, project):
    """A proxy backs out along its drive (thickness) axis only — the explode is
    a nonzero vector purely on the machined face normal."""
    placed_by_name = {p.name: p for p in scene.parts}
    name_by_id = {p.part_id: p.name for p in project.model.parts}
    for station in stations:
        placed = placed_by_name[name_by_id[station.part_id]]
        n = _thickness_axis(placed)
        for k in range(3):
            if k == n:
                assert abs(station.explode[k]) > 1.0, station.feature_id
            else:
                assert station.explode[k] == 0.0, station.feature_id


def test_proxy_diameter_and_length_come_from_the_typed_catalog(stations):
    """Proxy bodies are sized from real catalog products, not guessed."""
    for station in stations:
        assert station.diameter_mm > 0.0
        assert station.length_mm > 0.0
        assert station.catalog  # a named catalog product


def test_append_preserves_the_base_scene_and_adds_only_proxies(project):
    """Appending proxies leaves every wood/anchor part in place and adds exactly
    the proxy bodies — the GLB input for the real parts is unchanged."""
    scene = CPR.product_view_assembly(project)
    base_names = [p.name for p in scene.parts]
    rows = append_fastener_proxies(project, scene)
    after_names = [p.name for p in scene.parts]
    assert after_names[:len(base_names)] == base_names
    added = [p for p in scene.parts if isinstance(p.component, _FastenerProxy)]
    assert len(added) == len(rows)
    assert {p.name for p in added} == set(rows)
    assert len(rows) == sum(r.count for r in project.model.machining
                            if r.kind in _COVERED)


def test_flag_off_render_leaves_payload_and_glb_unproxied(project, tmp_path):
    """Default off: the technical-document pipeline is byte-identical — no proxy
    parts in the scene and no proxy rows in the payload."""
    assets = CPR.render_shared_product_assets(project, tmp_path / "off")
    assert not any(isinstance(p.component, _FastenerProxy)
                   for p in assets.assembly.parts)
    baseline = CPR.product_viewer_payload(
        project, CPR.product_view_assembly(project))
    assert assets.viewer_payload["parts"].keys() == baseline["parts"].keys()
    assert assets.viewer_payload == baseline


def test_flag_on_render_adds_proxies_with_the_schematic_disclosure(
        project, tmp_path):
    """Opt-in: proxies enter the GLB and every proxy row discloses, in its own
    tooltip, that it is a schematic placeholder placed from the machining
    schedule."""
    off = CPR.render_shared_product_assets(project, tmp_path / "base")
    on = CPR.render_shared_product_assets(
        project, tmp_path / "on", include_fastener_proxies=True)

    added = [p for p in on.assembly.parts
             if isinstance(p.component, _FastenerProxy)]
    assert len(added) == sum(r.count for r in project.model.machining
                             if r.kind in _COVERED)
    assert on.glb_bytes != off.glb_bytes  # proxy bodies changed the mesh

    proxy_names = {p.name for p in added}
    new_rows = {name: row for name, row in on.viewer_payload["parts"].items()
                if name in proxy_names}
    assert new_rows.keys() == proxy_names
    # The pure model rows are untouched by the overlay.
    assert (off.viewer_payload["parts"].keys()
            <= on.viewer_payload["parts"].keys())
    for name in off.viewer_payload["parts"]:
        assert on.viewer_payload["parts"][name] == off.viewer_payload["parts"][name]
    for row in new_rows.values():
        assert "schematic" in row["assumptions"].lower()
        assert any("machining station" in str(value) for _, value in row["specs"])
        assert row["reader_name"] in set(_COVERED.values())
        assert row["instance_count"] >= 1
