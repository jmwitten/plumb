"""Prepared-model reuse seam for single-detail reader documents."""

from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import single_detail_report as SDR


def test_build_document_forwards_prepared_documentation_without_temp_export(
    monkeypatch, tmp_path
):
    prepared = tmp_path / "prepared-model"
    prepared.mkdir()
    spec = tmp_path / "probe.spec.yaml"
    out = tmp_path / "probe.html"
    detail = SimpleNamespace(
        report=SimpleNamespace(),
        validate=lambda: SimpleNamespace(),
    )
    consumer = {
        "name": "probe",
        "spec": spec,
        "views_dir": tmp_path / "views",
        "panel": {},
        "view_files": {},
        "store": None,
    }
    captured = {}

    monkeypatch.setattr(SDR, "_consumer_for", lambda _path: consumer)
    monkeypatch.setattr(SDR, "_ensure_consumer_views", lambda *_args: None)
    monkeypatch.setattr(
        SDR,
        "coverage_matrix",
        lambda _report: [],
    )
    monkeypatch.setattr(
        SDR,
        "render_headline_line",
        lambda _matrix: "clean",
    )

    def fake_build_single_detail_html(
        _name,
        _detail,
        _views_dir,
        _panel,
        _view_files,
        _store,
        work_dir,
        **kwargs,
    ):
        captured["work_dir"] = work_dir
        captured["documentation_prepared"] = kwargs["documentation_prepared"]
        return "<!doctype html><html><body>probe</body></html>"

    monkeypatch.setattr(
        SDR, "build_single_detail_html", fake_build_single_detail_html
    )

    SDR.build_document(
        out,
        spec_path=spec,
        compiled_detail=detail,
        prepared_documentation_dir=prepared,
    )

    assert captured == {
        "work_dir": prepared,
        "documentation_prepared": True,
    }
    assert out.is_file()
