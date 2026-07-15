"""Task #20 — the three owner-reported viewer findings, scoped:

1. PLATFORM EXPLODE — a spec with no ``explode:`` block still drives the
   viewer's explode slider, from vectors DERIVED off the model's declared
   contacts (``web_viewer.explode.derive_explode_vectors``). Deterministic; every
   part moves; directions are honest (no part driven into the assembly).
2. FAB-NOTE TOOLTIPS — a notched part's hover tooltip carries the derived
   fabrication note (the trunk notch) beside its overall dims, read from the ONE
   source the cut plan reads (``ProcessRecord.fab_note``).
3. PANEL E INTERACTIVE — the pier-foundation panel gains a scoped 3D viewer slot
   (additive to the stills) with a working vertical explode.

The platform build is module-scoped (one compile) so the three platform-backed
suites share it; the Panel E markup / payload-wiring checks stay render-free.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

from detailgen.rendering.web_viewer import build_viewer_payload
from detailgen.rendering.web_viewer.explode import (
    _unit,
    derive_explode_vectors,
    derive_vertical_stack_explode,
)
from detailgen.spec.compiler import compile_spec_file

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"


@pytest.fixture(scope="module")
def platform():
    d = compile_spec_file(DETAILS / "platform.spec.yaml")
    d.validate()  # NOT require_clean: the platform holds its 3 blocking UNKNOWNs
    return d


@pytest.fixture(scope="module")
def platform_payload(platform):
    return build_viewer_payload(platform)


def _load_consolidated_report():
    path = ROOT / "scripts" / "consolidated_report.py"
    spec = importlib.util.spec_from_file_location("cr_explode_fab_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cr_explode_fab_test"] = mod
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# Finding 3 (fab-note tooltips)
# --------------------------------------------------------------------------- #
def test_notched_deck_board_tooltip_carries_the_notch_beside_dims(platform_payload):
    """The owner hovered a notched deck board and read only '48 in'. Now the
    overall dims (the true finished length) stay, AND the fab note names the
    on-site trunk notch that '48 in' alone hid."""
    deck = platform_payload["parts"]["deck 3"]
    assert "48" in deck["dims"], f"dims lost the overall length: {deck['dims']!r}"
    assert deck["fab"].startswith("notch:"), f"no notch note: {deck['fab']!r}"
    assert "trunk" in deck["fab"]


def test_plain_part_has_no_fab_note(platform_payload):
    """A part with no material-removing step carries an empty fab note — a plain
    part, truthfully — so the tooltip stays quiet rather than inventing a step."""
    assert platform_payload["parts"]["rail +Y"]["fab"] == ""


def test_tooltip_fab_note_is_the_cut_plan_single_source(platform, platform_payload):
    """The tooltip note is byte-identical to what the cut-plan renderer produces
    for the same part — both delegate to ``ProcessRecord.fab_note`` — so the
    hover and the cut list can never describe different fabrication."""
    cr = _load_consolidated_report()
    comp = platform["deck 3"].component
    record = comp.fabrication_record()
    assert platform_payload["parts"]["deck 3"]["fab"] == record.fab_note()
    assert cr._cutlist_fab_note(record) == record.fab_note()


# --------------------------------------------------------------------------- #
# Finding 1 (platform explode)
# --------------------------------------------------------------------------- #
def test_platform_authors_no_explode_block(platform):
    """The premise of the fix: the slider was a no-op because the spec declares
    zero explode vectors."""
    assert platform.explode_vectors() == {}


def test_derived_explode_is_deterministic(platform):
    spec = platform.validation_spec()
    ev1 = derive_explode_vectors(platform.assembly, spec)
    ev2 = derive_explode_vectors(platform.assembly, spec)
    assert ev1 == ev2
    assert set(ev1) == {p.name for p in platform.assembly.parts}


def test_derived_explode_moves_every_built_part(platform_payload):
    """A working slider: every BUILT part gets a nonzero offset (a zero would
    freeze it while the rest pulls apart). Existing/context bodies are the fixed
    frame and are deliberately pinned (asserted separately)."""
    for name, row in platform_payload["parts"].items():
        if row["existing"]:
            continue
        v = row["explode"]
        assert any(abs(c) > 1e-6 for c in v), f"{name}: zero explode vector"


def test_existing_context_bodies_are_pinned(platform_payload):
    """The live trunk and the boulder are the fixed reference frame the built
    parts pull away from — a context body flying apart is visual nonsense — so
    the derived path pins every existing/context body at zero."""
    for name in ("trunk", "boulder"):
        row = platform_payload["parts"][name]
        assert row["existing"] is True
        assert row["explode"] == [0.0, 0.0, 0.0], f"{name} exploded: {row['explode']!r}"


def test_caddy_sofa_arm_is_pinned():
    """Same pin in the caddy viewer: the sofa arm the caddy saddles is an
    existing body, so it never explodes while the caddy boards pull off it."""
    caddy = compile_spec_file(DETAILS / "armchair_caddy.spec.yaml")
    caddy.validate()
    payload = build_viewer_payload(caddy)
    arm = payload["parts"]["sofa arm"]
    assert arm["existing"] is True
    assert arm["explode"] == [0.0, 0.0, 0.0]


def test_caddy_corner_keys_explode_along_their_declared_axes():
    caddy = compile_spec_file(DETAILS / "armchair_caddy.spec.yaml")
    caddy.validate()
    payload = build_viewer_payload(caddy)

    keys = [
        part for part in caddy.assembly.parts
        if part.reader_name == "Corner key"
    ]
    assert len(keys) == 4
    for part in keys:
        vector = payload["parts"][part.name]["explode"]
        local_axis = part.component.datum("axis").z_axis
        world_axis = part.world_frame.transform_direction(local_axis)
        cross = (
            vector[1] * world_axis[2] - vector[2] * world_axis[1],
            vector[2] * world_axis[0] - vector[0] * world_axis[2],
            vector[0] * world_axis[1] - vector[1] * world_axis[0],
        )

        assert math.sqrt(sum(value * value for value in cross)) < 1e-6
        assert sum(
            vector[index] * world_axis[index] for index in range(3)
        ) > 0


def test_explode_unit_rejects_nonfinite_directions():
    assert _unit((math.nan, 0.0, 0.0)) is None
    assert _unit((math.inf, 0.0, 0.0)) is None


def test_derived_explode_directions_are_honest(platform_payload):
    """Spot-check the derived directions against physical pull-apart:
      - a deck board lifts UP off its joists (+Z dominant);
      - a pier block drops DOWN out from under its leg (-Z);
      - an interior joist is clamped between BOTH beams, so the opposed Y
        bearings CANCEL — it must not be driven into either beam (net Y ~ 0)."""
    deck = platform_payload["parts"]["deck 3"]["explode"]
    assert deck[2] > 0 and abs(deck[2]) > max(abs(deck[0]), abs(deck[1]))

    block = platform_payload["parts"]["pier tree +Y"]["explode"]
    assert block[2] < 0 and abs(block[2]) > max(abs(block[0]), abs(block[1]))

    joist = platform_payload["parts"]["joist 0"]["explode"]
    assert abs(joist[1]) < 1e-6, f"clamped joist got a net Y push: {joist!r}"


def test_authored_explode_wins_over_derivation():
    """A detail that DOES author explode vectors keeps them verbatim — the
    derivation is only the fallback, so the rock-anchor / tree / trolley goldens
    are untouched. Proven on the precedence logic without a slow build."""
    from detailgen.rendering.web_viewer import _explode_for

    class _Authored:
        def explode_vectors(self):
            return {"widget": (1.0, 2.0, 3.0)}

    assert _explode_for(_Authored(), assembly=None) == {"widget": (1.0, 2.0, 3.0)}


# --------------------------------------------------------------------------- #
# Finding 2 (interactive Panel E)
# --------------------------------------------------------------------------- #
def test_vertical_stack_explode_pulls_the_pier_apart_vertically(platform):
    """The scoped pier stack pulls apart along Z only, block below → leg above,
    so the standoff air gap the panel exists to show reads."""
    cr = _load_consolidated_report()
    view = cr._pier_foundation_view_assembly(platform)
    ev = derive_vertical_stack_explode(view)
    for name, v in ev.items():
        assert v[0] == 0.0 and v[1] == 0.0, f"{name}: non-vertical explode {v!r}"
    assert ev["pier tree +Y"][2] < ev["post base pier tree +Y"][2] < ev["leg tree +Y"][2]


def test_panel_e_has_an_interactive_viewer_slot():
    """Panel E renders a viewer slot + launch button over its hero still — the
    same affordance the per-detail panels carry — scoped to the pier assembly."""
    cr = _load_consolidated_report()

    class _Report:
        blocking = []

    html_out = cr.render_pier_foundation_section({}, _Report(), None)
    assert 'class="viewer-slot"' in html_out
    assert f'data-detail="{cr.PIER_FOUNDATION_SLUG}"' in html_out
    assert "Explore in 3D" in html_out
    # the stills are still there (the viewer is additive, not a replacement)
    assert 'class="sub"' in html_out


def test_pier_payload_reuses_platform_rows_with_vertical_explode(platform, platform_payload):
    """The Panel E payload is the SAME three platform part rows (item/dims/fab),
    keyed by the names their GLB nodes carry, with explode overridden to the
    vertical stack — no second tooltip derivation."""
    cr = _load_consolidated_report()
    details = {"platform": platform}
    payload = cr.pier_foundation_payload(platform_payload, details)

    assert payload["slug"] == cr.PIER_FOUNDATION_SLUG
    assert set(payload["parts"]) == set(cr._PIER_FOUNDATION_PARTS)
    for name in cr._PIER_FOUNDATION_PARTS:
        assert payload["parts"][name]["fab"] == platform_payload["parts"][name]["fab"]
        v = payload["parts"][name]["explode"]
        assert v[0] == 0.0 and v[1] == 0.0  # vertical


def test_main_skips_panel_e_when_platform_absent(monkeypatch, tmp_path):
    """The doc build must never crash on a detail SUBSET. With no ``platform``
    detail, main() reaches the vault-copy decision without a KeyError and simply
    omits Panel E's pier viewer (retro R33: the real-main() path is the blind
    spot — this exercises it directly)."""
    cr = _load_consolidated_report()

    class _FakeReport:
        ok = False
        blocking: list = []

    class _FakeSite:
        def validate(self):
            return _FakeReport()

        class assembly:
            parts: list = []

    monkeypatch.setattr(cr, "HTML_OUT", tmp_path / "doc.html")
    monkeypatch.setattr(cr, "OUT_DIR", tmp_path)
    monkeypatch.setattr(cr, "RENDERS", tmp_path / "renders")
    monkeypatch.setattr(cr, "load_details", lambda: {})  # no platform in the subset
    monkeypatch.setattr(cr, "load_site", lambda: _FakeSite())
    monkeypatch.setattr(cr, "pier_foundation_images", lambda details: {})
    monkeypatch.setattr(cr, "assert_details_fabrication_sound", lambda details: None)
    monkeypatch.setattr(cr, "build_review_block", lambda: "")
    captured = {}

    def _fake_build_html(*a, **k):
        # payloads is the 7th positional arg (see build_html's signature)
        captured["payloads"] = a[6]
        return "<html></html>"

    monkeypatch.setattr(cr, "build_html", _fake_build_html)

    cr.main([])  # must not raise
    assert cr.PIER_FOUNDATION_SLUG not in captured["payloads"]


def test_viewer_assets_emit_pier_scripts_only_when_present():
    """``render_viewer_assets`` stays additive: it emits the pier scripts when a
    pier payload+GLB are supplied, and never KeyErrors when they aren't (the
    text-layer golden and the escaping unit test stub only the four panels)."""
    cr = _load_consolidated_report()
    names = ["platform", "tree_attachment", "rock_anchor", "trolley_launch"]
    base = {n: {"slug": n, "name": n, "parts": {}, "dimensions": []} for n in names}
    glb = {n: "QUJD" for n in names}

    without = cr.render_viewer_assets(base, glb)
    assert "detail-data-pier_foundation" not in without

    with_pier = dict(base, pier_foundation={"slug": cr.PIER_FOUNDATION_SLUG,
                                            "name": "Pier foundation",
                                            "parts": {}, "dimensions": []})
    with_pier_glb = dict(glb, pier_foundation="QUJD")
    out = cr.render_viewer_assets(with_pier, with_pier_glb)
    assert "detail-data-pier_foundation" in out
    assert "detail-glb-pier_foundation" in out
