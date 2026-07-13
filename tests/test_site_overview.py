"""Composition smoke tests for the "Site overview" section
(scripts/_site_overview.py + scripts/consolidated_report.py's wiring of it).

Loads ``scripts/consolidated_report.py`` by file path (same pattern as
``test_cutplan_integration.py`` — see that file's docstring for why: the
detail modules shadow the stdlib ``platform`` module). Never calls ``main()``
so it never renders/exports or touches the real vault file; the one test
that DOES render (``test_process_site_overview_hash_gates_and_renders_pngs``)
redirects RENDERS to a scratch directory first.
"""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from detailgen.core import IN

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report_mod():
    return _load("consolidated_report_test_so", REPO_ROOT / "scripts" / "consolidated_report.py")


@pytest.fixture(scope="module")
def so(report_mod):
    return report_mod._site_overview


@pytest.fixture(scope="module")
def details(report_mod):
    return report_mod.load_details()


@pytest.fixture(scope="module")
def overview(so, details):
    return so.build_site_overview(details)


# --------------------------------------------------------------------------- #
# All four load + place.
# --------------------------------------------------------------------------- #
def test_details_contribute_parts(overview):
    # TREEFREE: the free-standing tree_attachment is now pure clearance context —
    # its trunk is deduped to the platform's and its two beam stubs bind onto the
    # platform's real beams, so it contributes NO new members to the overview. The
    # three structural details still each contribute.
    for name in ("platform", "rock_anchor", "trolley_launch"):
        assert overview.kept_counts[name] > 0, f"{name} contributed zero parts"
    assert overview.kept_counts["tree_attachment"] == 0
    total_kept = sum(overview.kept_counts.values())
    assert len(overview.assembly.parts) == total_kept


def test_composition_preserves_reader_name_and_machine_identity(so, details):
    original = details["platform"].assembly.parts[0]
    readable = replace(original, reader_name="Readable platform part")
    platform = SimpleNamespace(
        params=details["platform"].params,
        assembly=SimpleNamespace(
            parts=[readable, *details["platform"].assembly.parts[1:]],
        ),
    )
    composed = so.build_site_overview({**details, "platform": platform})
    copied = next(
        part for part in composed.assembly.parts
        if part.id == f"platform-{original.id}"
    )

    assert copied.reader_name == "Readable platform part"
    assert copied.name == original.name
    assert copied.id == f"platform-{original.id}"


def test_platform_parts_are_never_dropped(so, details):
    """The platform detail is always canonical (requirement #3) — nothing of
    its is ever hidden, even though some of ITS parts (the trunk, the
    boulder) match the dedup predicates that drop OTHER details' copies."""
    result = so.build_site_overview(details)
    assert result.dropped_counts["platform"] == 0
    dropped_from_platform = [d for d in result.dropped if d["detail"] == "platform"]
    assert dropped_from_platform == []


# --------------------------------------------------------------------------- #
# Dedup rule drops the right parts.
# --------------------------------------------------------------------------- #
def test_stub_of_tagged_parts_are_dropped(so, overview):
    """tree_attachment's beam-end stubs and rock_anchor's leg stub are
    formally tagged via stub_of() (STUBVIZ) — the dedup rule must drop
    every one of them, and none may survive into the composed assembly."""
    stub_drops = [d for d in overview.dropped if d["reason"] == so.REASON_STUB]
    assert any(d["detail"] == "tree_attachment" for d in stub_drops)
    assert any(d["detail"] == "rock_anchor" for d in stub_drops)

    kept_components = [p.component for p in overview.assembly.parts]
    assert all(c.stub_of() is None for c in kept_components), (
        "a stub_of-tagged component survived into the composed overview"
    )


def test_existing_context_duplicates_are_deduped_to_platform(overview, details):
    """Exactly one TreeTrunk and one Boulder survive (platform's), even
    though tree_attachment and rock_anchor each model their own copy for
    context."""
    kept = overview.assembly.parts
    trunk_count = sum(1 for p in kept if type(p.component).__name__ == "TreeTrunk")
    boulder_count = sum(1 for p in kept if type(p.component).__name__ == "Boulder")
    assert trunk_count == 1, f"expected exactly one TreeTrunk in the overview, got {trunk_count}"
    assert boulder_count == 1, f"expected exactly one Boulder in the overview, got {boulder_count}"

    # And the survivor is platform's, not a dropped detail's.
    platform_ids = {id(p.component) for p in details["platform"].assembly.parts}
    trunk = next(p for p in kept if type(p.component).__name__ == "TreeTrunk")
    boulder = next(p for p in kept if type(p.component).__name__ == "Boulder")
    assert id(trunk.component) in platform_ids
    assert id(boulder.component) in platform_ids


def test_existing_hardware_unique_to_one_detail_is_kept(overview):
    """The zipline cable/trolley wheel/hanger/grab bar are 'existing' context
    but have no platform counterpart to dedupe against — they must survive."""
    kept_types = {type(p.component).__name__ for p in overview.assembly.parts}
    for expected in ("Cable", "TrolleyWheel", "Hanger", "GrabBar"):
        assert expected in kept_types, f"{expected} was dropped but has no platform duplicate"


def test_trolley_structural_lumber_is_deduped(overview):
    """trolley_launch's launch posts + deck-edge rim are structural duplicates of
    the platform's legs / end joist and must be dropped from the site overview.
    Since the task-4B-2 stub fix they carry ``stub_of`` (derived from
    leg_height/deck_width, in lockstep with the spec), so they now drop via the
    PRECISE stub path — the same one the tree/rock stubs use — instead of the
    name-agnostic lumber-duplicate fallback. Either way all three are deduped."""
    dropped_names = {
        d["name"] for d in overview.dropped if d["detail"] == "trolley_launch"
    }
    for expected in ("launch post", "far post", "deck edge rim"):
        assert expected in dropped_names, f"{expected} was not deduped from the overview"
    stub_dropped = [
        d for d in overview.dropped
        if d["detail"] == "trolley_launch" and "stub_of metadata" in d["reason"]
    ]
    assert len(stub_dropped) == 3, stub_dropped


def test_dedup_rule_is_metadata_driven_not_a_name_list(so):
    """The predicates only ever consult component metadata (stub_of, source,
    bom_label) — never a literal part-name string — so a future fifth detail
    inherits the behavior automatically. Static sanity check: the drop
    function's source doesn't reference any of the actual part display names
    used in the four existing details (a regression indicating a hand list
    crept in)."""
    import inspect

    src = inspect.getsource(so._drop_reason) + inspect.getsource(so.build_site_overview)
    banned_literals = ["leg +Y", "leg -Y", "beam +Y", "beam -Y", "launch post 0",
                        "launch post 1", "deck-edge rim"]
    for lit in banned_literals:
        assert lit not in src, f"dedup logic references a hand-listed part name: {lit!r}"


# --------------------------------------------------------------------------- #
# Placement transforms.
# --------------------------------------------------------------------------- #
def test_identity_placements_for_platform_and_tree(so, details):
    transforms = so.compute_site_transforms(details)
    origin = (0.0, 0.0, 0.0)
    assert transforms["platform"].origin == pytest.approx(origin, abs=1e-9)
    assert transforms["tree_attachment"].origin == pytest.approx(origin, abs=1e-9)
    # identity rotation too
    assert transforms["platform"].x_axis == pytest.approx((1, 0, 0), abs=1e-9)
    assert transforms["tree_attachment"].x_axis == pytest.approx((1, 0, 0), abs=1e-9)


def test_rock_anchor_translated_to_launch_leg_station(so, details):
    transforms = so.compute_site_transforms(details)
    pf = details["platform"].params
    # 4B-3: private imperative accessor ``_beam_outer_y`` retired with the .py
    # detail; the public compiled-spec params surface is the equivalent (values
    # identical: ``outer_y * IN`` == the old ``_beam_outer_y`` mm).
    beam_outer_y_mm = details["platform"].params.outer_y * IN
    origin = transforms["rock_anchor"].origin
    assert origin[0] == pytest.approx(pf.leg_station * IN, abs=1e-6)
    assert origin[1] == pytest.approx(beam_outer_y_mm, abs=1e-6)
    assert origin[2] == pytest.approx(0.0, abs=1e-6)
    # no rotation, per rock_anchor's own frame already matching platform's axes
    assert transforms["rock_anchor"].x_axis == pytest.approx((1, 0, 0), abs=1e-9)
    assert transforms["rock_anchor"].y_axis == pytest.approx((0, 1, 0), abs=1e-9)


def test_trolley_launch_transform_maps_deck_corners_onto_platform_leg_line(so, details):
    """trolley_launch's local posts sit at X=0 and X=deck_width (Y=0, the
    launch edge). After the site transform, those two points must land
    exactly on the platform's launch-edge / leg line: X=beam_len,
    Y=-beam_outer_y and Y=+beam_outer_y."""
    transforms = so.compute_site_transforms(details)
    t = transforms["trolley_launch"]
    pf = details["platform"].params
    beam_outer_y_in = details["platform"].params.outer_y * IN / IN
    tl = details["trolley_launch"].params

    p_minus = t.transform_point((0.0, 0.0, 0.0))
    p_plus = t.transform_point((tl.deck_width * IN, 0.0, 0.0))

    assert p_minus[0] == pytest.approx(pf.beam_len * IN, abs=1e-6)
    assert p_minus[1] == pytest.approx(-beam_outer_y_in * IN, abs=1e-6)
    assert p_plus[0] == pytest.approx(pf.beam_len * IN, abs=1e-6)
    assert p_plus[1] == pytest.approx(beam_outer_y_in * IN, abs=1e-6)


# --------------------------------------------------------------------------- #
# Scene bbox sanity vs. the expected site envelope.
# --------------------------------------------------------------------------- #
def test_composed_scene_bbox_matches_expected_site_envelope(overview, details):
    pf = details["platform"].params
    bbox = overview.assembly.compound().BoundingBox()

    # X: from the beam's tree-end corner (-tree_overhang) out past the launch
    # edge (beam_len). The upper slack accommodates the ILLUSTRATIVE zipline cable
    # (A3 demonstration geometry): it represents the whole ride, so it runs from
    # the tree anchor out past the launch edge — reaching ~14" beyond beam_len.
    # This is labeled illustrative in the doc and excluded from the engineered BOM.
    assert bbox.xmin > -(pf.tree_overhang + 6) * IN
    assert bbox.xmax < (pf.beam_len + 20) * IN   # incl. the demonstration cable run
    assert bbox.xmax > pf.beam_len * IN * 0.9

    # Y: within the deck width plus a little slack for rails/mesh/hardware.
    beam_outer_y_in = details["platform"].params.outer_y * IN / IN
    assert bbox.ymin > -(beam_outer_y_in + 12) * IN
    assert bbox.ymax < (beam_outer_y_in + 12) * IN

    # Z: the boulder extends below Z=0 (context body, real rock); everything
    # else runs from ground up to around the grab bar height.
    tl = details["trolley_launch"].params
    assert bbox.zmin > -(pf.boulder_depth + 6) * IN
    assert bbox.zmax > pf.deck_height * IN * 0.9
    assert bbox.zmax < (tl.bar_height_ground + 24) * IN


# --------------------------------------------------------------------------- #
# Doc section renders.
# --------------------------------------------------------------------------- #
def test_site_overview_section_renders(report_mod, overview, details):
    fake_images = {"iso": "data:image/png;base64,AAAA", "top": "data:image/png;base64,BBBB"}
    html_out = report_mod.render_site_overview(overview, fake_images, details)
    assert "Whole-Assembly Overview" in html_out
    assert "REPRESENTED for orientation" in html_out
    assert "NOT ANALYZED" in html_out
    assert "platform" in html_out
    assert "rock_anchor" in html_out
    assert "trolley_launch" in html_out
    assert "tree_attachment" in html_out
    assert "EXACT" in html_out
    assert "ASSUMED" in html_out
    assert "Known Y-divergence" in html_out or "Y-divergence" in html_out
    assert fake_images["iso"] in html_out
    assert fake_images["top"] in html_out


def test_y_divergence_numbers_are_computed_not_hardcoded(so, details):
    y = so.tree_vs_platform_beam_y(details)
    assert y["tree_inner_y_in"] == pytest.approx(details["tree_attachment"].params.trunk_dia / 2)
    assert y["platform_outer_y_in"] == pytest.approx(details["platform"].params.outer_y * IN / IN)
    # the whole reason this note exists: they must actually disagree today.
    assert y["tree_outer_y_in"] != pytest.approx(y["platform_outer_y_in"])


# --------------------------------------------------------------------------- #
# Hash-gating + render (redirected to scratch — never touches the real
# outputs/consolidated tree or the vault).
# --------------------------------------------------------------------------- #
def test_process_site_overview_hash_gates_and_renders_pngs(report_mod, details, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RENDERS", tmp_path / "renders")

    overview1, manifest1, images1, reused1 = report_mod.process_site_overview(details)
    assert reused1 is False
    assert set(images1) == {"iso", "top"}
    for uri in images1.values():
        assert uri.startswith("data:image/png;base64,")
        assert len(uri) > 1000  # a real render, not a stub

    overview2, manifest2, images2, reused2 = report_mod.process_site_overview(details)
    assert reused2 is True, "second call with unchanged geometry should hash-gate to REUSE"
    assert manifest2["assembly_hash"] == manifest1["assembly_hash"]
    assert images2 == images1


# --------------------------------------------------------------------------- #
# Size budget: the two new PNGs stay small relative to the doc ceiling.
# --------------------------------------------------------------------------- #
def test_site_overview_pngs_are_small_relative_to_the_html_ceiling(report_mod, details, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RENDERS", tmp_path / "renders")
    _overview, _manifest, images, _reused = report_mod.process_site_overview(details)
    total_bytes = sum(len(uri) for uri in images.values())
    # Two 1200x900 PNGs of a modest scene should be well under 1/8 of the
    # 8MB HTML ceiling; this is a regression guard, not a tight budget.
    assert total_bytes < report_mod.MAX_HTML_BYTES / 8
