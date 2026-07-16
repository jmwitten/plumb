from pathlib import Path

import pytest

from detailgen.package.views import render_standard_views


def test_standard_views_reject_unknown_camera(tmp_path):
    with pytest.raises(ValueError, match="unknown standard view"):
        render_standard_views(object(), tmp_path, ("not-a-camera",))


def test_standard_views_use_one_existing_assembly(monkeypatch, tmp_path):
    calls = []
    detail = type("D", (), {"assembly": object()})()
    monkeypatch.setattr(
        "detailgen.package.views.export_png",
        lambda assembly, path, view: calls.append(
            (assembly, Path(path), view)
        )
        or Path(path),
    )

    paths = render_standard_views(detail, tmp_path, ("iso", "front"))

    assert [path.name for path in paths] == ["iso.png", "front.png"]
    assert all(call[0] is detail.assembly for call in calls)
