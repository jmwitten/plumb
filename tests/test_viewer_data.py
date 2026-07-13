"""Hover-join correctness for the interactive build-document viewer's data
contract (``detailgen.rendering.web_viewer.build_viewer_payload``).

No browser, no new deps: the exported web GLB's JSON chunk is parsed with
stdlib ``struct``+``json`` per the documented GLB binary layout (12-byte
header, then length-prefixed chunks, first chunk type ``JSON``) and checked
against the payload for the same detail — the actual join a (future) viewer
performs at runtime by raycasting to a mesh's node name.

Runtime budget: the default run builds ONE detail (rock_anchor, ~60-90s) and
exports its coarse web GLB (the same tolerance the generator will use). The
other three details are covered by the full sweep gated behind
``VIEWER_FULL=1`` — slow (four builds) and not needed for every test run since
the join logic itself doesn't vary by detail.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import struct
import sys
from pathlib import Path

import pytest

import baseline_lib as bl
from detailgen.rendering.export import export_glb
from detailgen.rendering.web_viewer import (
    build_viewer_payload,
    viewer_css,
    viewer_js,
)
from detailgen.spec import compile_spec, compile_spec_file, load_spec_text

ROOT = Path(__file__).resolve().parents[1]
DETAILS = ROOT / "details"


TWO_RAILS_YAML = """
name: reader-name-two-rails-viewer
components:
  - id: rail_pos
    type: lumber
    name: registration rail +X
    reader_name: Registration rail
    params: {nominal: "2x6", length: "6 in"}
  - id: rail_neg
    type: lumber
    name: registration rail -X
    reader_name: Registration rail
    params: {nominal: "2x6", length: "6 in"}
"""


def build_text(text: str):
    detail = compile_spec(load_spec_text(text))
    detail.build()
    return detail


def _load_detail_class(modname: str, filename: str, clsname: str):
    """Return a zero-arg factory that compiles the detail's ``spec.yaml`` — the
    imperative ``.py`` mirrors are retired, so viewer payloads build from the
    compiled spec. ``modname`` / ``clsname`` are retained for call-site parity
    with the old file-path loader (the fixtures below bind the result to the
    detail's class name and call it)."""
    return lambda: compile_spec_file(DETAILS / filename)


def _glb_json_chunk(path: Path) -> dict:
    """Parse a GLB's first (JSON) chunk from the raw binary layout: a 12-byte
    header (magic, version, total length) followed by length-prefixed chunks;
    the first chunk is always type ``JSON``."""
    data = path.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF", f"not a GLB: magic={magic!r}"
    chunk_length, chunk_type = struct.unpack_from("<I4s", data, 12)
    assert chunk_type == b"JSON", f"first chunk must be JSON, got {chunk_type!r}"
    chunk_data = data[20:20 + chunk_length]
    return json.loads(chunk_data)


def _mesh_owning_node_names(gltf: dict) -> set[str]:
    return {node["name"] for node in gltf.get("nodes", []) if "mesh" in node}


def _assert_payload_join(detail, glb_path: Path) -> dict:
    """Shared assertions: GLB mesh-node names == payload part keys, plus field
    sanity. Returns the payload for any additional detail-specific checks."""
    gltf = _glb_json_chunk(glb_path)
    node_names = _mesh_owning_node_names(gltf)
    payload = build_viewer_payload(detail)

    assert node_names, "GLB has no mesh-owning nodes"
    assert node_names == set(payload["parts"].keys())

    assert payload["slug"]
    assert payload["name"] == detail.name
    assert payload["parts"]

    for name, row in payload["parts"].items():
        assert row["item"], f"{name}: empty item"
        assert row["dims"], f"{name}: empty dims"
        assert row["qty"] >= 1, f"{name}: qty < 1"
        assert isinstance(row["existing"], bool), f"{name}: existing not bool"
        assert len(row["explode"]) == 3, f"{name}: explode not 3-vector"
        assert all(math.isfinite(v) for v in row["explode"]), f"{name}: non-finite explode"
        for label, value in row["specs"]:
            assert isinstance(label, str) and isinstance(value, str), (
                f"{name}: spec {label!r} not a (str, str) pair"
            )

    explode_keys = set(detail.explode_vectors().keys())
    assert explode_keys <= set(payload["parts"].keys()), (
        f"explode_vectors() references unknown part(s): {explode_keys - set(payload['parts'].keys())}"
    )

    for dim in payload["dimensions"]:
        assert dim["label"]
        for pt in (dim["p0"], dim["p1"]):
            assert len(pt) == 3
            assert all(math.isfinite(v) for v in pt), f"non-finite dimension endpoint in {dim!r}"

    json.dumps(payload)  # must be JSON-serializable end-to-end
    return payload


def _load_consolidated_report():
    """Load ``scripts/consolidated_report.py`` by path (it's a script, not a
    package module; module-level import is side-effect-free — ``main()`` only
    runs under ``__main__``)."""
    path = ROOT / "scripts" / "consolidated_report.py"
    spec = importlib.util.spec_from_file_location("consolidated_report_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["consolidated_report_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_viewer_assets_inline_structure_and_escaping():
    """The appended viewer block must carry two data scripts per panel (JSON
    payload + text/plain base64 GLB), inline the vendored three.js + viewer JS
    once, and escape ``</`` inside the JSON so a payload string can't close the
    <script> early. No geometry build — pure string assembly."""
    cr = _load_consolidated_report()
    names = ["platform", "tree_attachment", "rock_anchor", "trolley_launch"]
    # A hostile string that would break out of <script> if not escaped.
    payloads = {
        n: {"slug": n, "name": n, "parts": {"x": {"item": "</script><b>hi"}},
            "dimensions": []}
        for n in names
    }
    glb_b64 = {n: "QUJD" for n in names}  # base64("ABC")

    html_out = cr.render_viewer_assets(payloads, glb_b64)

    for n in names:
        assert f'id="detail-data-{n}"' in html_out
        assert f'id="detail-glb-{n}"' in html_out
    assert 'type="application/json"' in html_out
    assert 'type="text/plain"' in html_out
    # No raw "</script" survives inside the inlined JSON payloads.
    assert "</script><b>hi" not in html_out
    assert "<\\/script><b>hi" in html_out
    # three.js + viewer are inlined exactly once each.
    assert html_out.count("THREE") >= 1
    assert "GLTFLoader" in html_out
    assert html_out.count("<style>") == 1


def test_viewer_keeps_machine_keys_and_adds_reader_fields():
    payload = build_viewer_payload(build_text(TWO_RAILS_YAML))
    assert "registration rail +X" in payload["parts"]
    row = payload["parts"]["registration rail +X"]
    assert row["reader_name"] == "Registration rail"
    assert (row["instance_index"], row["instance_count"]) == (1, 2)


def test_tooltip_uses_reader_name_but_not_as_lookup_key():
    js = viewer_js()
    assert "p.reader_name || partName" in js
    assert "instance_index" in js and "instance_count" in js
    assert "payload.parts[partName]" in js
    assert 'class="v-tip-name"' in js
    assert 'class="v-tip-stock"' in js

    css = viewer_css()
    assert ".v-tip-name" in css
    assert ".v-tip-stock" in css


@pytest.fixture(scope="module")
def rock_anchor_detail():
    RockAnchor = _load_detail_class("ra_detail_viewer_test", "rock_anchor.spec.yaml", "RockAnchor")
    detail = RockAnchor()
    detail.require_clean()
    return detail


@pytest.fixture(scope="module")
def rock_anchor_web_glb(tmp_path_factory, rock_anchor_detail):
    out = tmp_path_factory.mktemp("viewer_glb") / "rock_anchor.web.glb"
    export_glb(rock_anchor_detail.assembly, path=out, tolerance=0.25, angular_tolerance=0.3)
    return out


def test_glb_join_and_field_sanity(rock_anchor_detail, rock_anchor_web_glb):
    payload = _assert_payload_join(rock_anchor_detail, rock_anchor_web_glb)
    assert len(payload["parts"]) == bl.load_baseline("detail_counts")["rock_anchor"]["parts"]


@pytest.fixture(scope="module")
def tree_attachment_detail():
    # No GLB export here — build_viewer_payload only needs the assembly, and
    # tree_attachment builds fast (unlike the VIEWER_FULL-gated GLB sweep
    # above), so this stub_of contract test runs on every pytest invocation.
    TreeAttachment = _load_detail_class(
        "tree_detail_stubviz_test", "tree_attachment.spec.yaml", "TreeAttachment")
    detail = TreeAttachment()
    detail.require_clean()
    return detail


def test_stub_of_payload_contract(rock_anchor_detail, tree_attachment_detail):
    """STUBVIZ data contract: the three partial-member stubs (tree_attachment's
    two beam ends, rock_anchor's leg) carry ``stub_of`` metadata whose
    ``full_dims`` becomes the tooltip's PRIMARY dims line (not the modeled
    stub length); ordinary parts carry no ``stub_of`` at all."""
    ra_payload = build_viewer_payload(rock_anchor_detail)
    ta_payload = build_viewer_payload(tree_attachment_detail)

    leg = ra_payload["parts"]["leg"]
    assert leg["stub_of"] is not None
    assert leg["dims"] == leg["stub_of"]["full_dims"]
    assert '63.5"' in leg["stub_of"]["full_dims"]
    assert "continuous run" in leg["stub_of"]["full_dims"]
    assert '14.0"' in leg["stub_of"]["modeled_dims"]
    assert "platform detail" in leg["stub_of"]["note"]
    labels = [s[0] for s in leg["specs"]]
    assert labels[:2] == ["Full length", "Modeled portion"]

    for side in ("beam +Y", "beam -Y"):
        beam = ta_payload["parts"][side]
        assert beam["stub_of"] is not None
        assert beam["dims"] == beam["stub_of"]["full_dims"]
        assert '60.0"' in beam["stub_of"]["full_dims"]  # BEAMFIX: 48" deck run + 12" overhang
        # TREEFREE: the tree beams are now plain Lumber stubs (lags retired), so the
        # stub_of wording is Lumber's "(continuous run)" / "full run in the platform
        # detail" rather than SlottedBeamEnd's "(continuous beam)" / "trunk-end".
        assert "continuous run" in beam["stub_of"]["full_dims"]
        assert '24.0"' in beam["stub_of"]["modeled_dims"]
        assert "platform detail" in beam["stub_of"]["note"]

    # ordinary (non-stub) parts carry no stub_of, and their dims line is the
    # plain describe() string, unchanged.
    assert ra_payload["parts"]["boulder"]["stub_of"] is None
    assert ta_payload["parts"]["trunk"]["stub_of"] is None
    assert ta_payload["parts"]["trunk"]["dims"] == \
        tree_attachment_detail["trunk"].component.describe()


def test_stub_of_absent_from_bom_row_for_ordinary_parts(tree_attachment_detail):
    """The BOM row (DetailAssembly.bom_table) carries the same stub_of field —
    None for ordinary parts, the metadata dict for the stub rows — confirming
    requirement 1's "wire it through the BOM row", independent of the viewer."""
    rows = {r["item"]: r for r in tree_attachment_detail.bom_table()}
    beam_row = rows["PT 2x6 lumber"]
    assert beam_row["qty"] == 2  # both beam stubs fold into one aggregated row
    assert beam_row["stub_of"] is not None
    assert '60.0"' in beam_row["stub_of"]["full_dims"]  # BEAMFIX: 48" deck run + 12" overhang
    # the BOM row's own "dimensions" column is the plain-Lumber modeled stub length
    # (TREEFREE: the beams are plain Lumber stubs now, so no SlottedBeamEnd
    # "(trunk-end stub)" suffix); only the viewer's tooltip swaps in the full dims.
    assert beam_row["dimensions"] == '2x6 x 24.0"'
    assert rows["Tree trunk (existing)"]["stub_of"] is None


def test_partial_view_note_renders_in_panel_html():
    """PANEL PROSE requirement: the tree-attachment and rock-anchor panels get
    a panel-level partial-view note distinct from the tooltip (not tooltip-
    buried) — rendered directly into the generated HTML."""
    cr = _load_consolidated_report()
    for name in ("tree_attachment", "rock_anchor"):
        cfg = cr.PANELS[name]
        image_uris = {v: "data:," for v in cfg["views"]}
        html_out = cr.render_panel(name, cfg, None, image_uris, [], name)
        assert "partial-note" in html_out
        assert cr.esc(cfg["partial_view_note"]) in html_out
    # the other two panels have no partial-view note and render no such block.
    for name in ("platform", "trolley_launch"):
        cfg = cr.PANELS[name]
        image_uris = {v: "data:," for v in cfg["views"]}
        html_out = cr.render_panel(name, cfg, None, image_uris, [], name)
        assert "partial-note" not in html_out


@pytest.mark.skipif(
    not os.environ.get("VIEWER_FULL"),
    reason="full 4-detail GLB<->payload sweep — set VIEWER_FULL=1 to run (slow: builds all four details)",
)
@pytest.mark.parametrize(
    "modname,filename,clsname",
    [
        ("tree_detail_viewer_test", "tree_attachment.spec.yaml", "TreeAttachment"),
        ("trolley_detail_viewer_test", "trolley_launch.spec.yaml", "TrolleyLaunch"),
        ("platform_detail_viewer_test", "platform.spec.yaml", "Platform"),
    ],
)
def test_other_details_join_glb_full(modname, filename, clsname, tmp_path):
    cls = _load_detail_class(modname, filename, clsname)
    detail = cls()
    # validate(), NOT require_clean(): the platform deliberately holds 3 blocking
    # foundation_capacity UNKNOWNs (engineer-of-record), so require_clean() raises
    # on it. The GLB<->payload JOIN this test checks needs only a built+validated
    # assembly, not a clean verdict (cleanliness is guarded by the coverage tests).
    detail.validate()
    out = tmp_path / "detail.web.glb"
    export_glb(detail.assembly, path=out, tolerance=0.25, angular_tolerance=0.3)
    _assert_payload_join(detail, out)
