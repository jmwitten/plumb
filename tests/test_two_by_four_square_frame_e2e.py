"""End-to-end guards for the four-foot square 2x4 frame."""

from collections import Counter
from pathlib import Path

import pytest

from detailgen.spec import compile_spec_file


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "details/two_by_four_square_frame.spec.yaml"
IN = 25.4


@pytest.fixture(scope="module")
def compiled_frame():
    detail = compile_spec_file(SPEC)
    return detail, detail.validate()


def test_exact_requested_envelope_and_face_orientation(compiled_frame):
    detail, _report = compiled_frame
    boxes = [part.world_solid().val().BoundingBox()
             for part in detail.assembly.parts
             if "2x4" in part.name]

    assert min(box.xmin for box in boxes) / IN == pytest.approx(0.0, abs=0.01)
    assert max(box.xmax for box in boxes) / IN == pytest.approx(48.0, abs=0.01)
    assert min(box.zmin for box in boxes) / IN == pytest.approx(0.0, abs=0.01)
    assert max(box.zmax for box in boxes) / IN == pytest.approx(48.0, abs=0.01)
    assert all((box.ymax - box.ymin) / IN == pytest.approx(1.5, abs=0.01)
               for box in boxes)


def test_all_twelve_screws_are_driveable_from_the_outside_edges(compiled_frame):
    _detail, report = compiled_frame
    installs = [finding for finding in report.findings
                if finding.check in {"install_access", "install_termination"}]

    assert Counter(finding.verdict for finding in installs) == Counter({"PASS": 24})
    assert report.failures == [], "\n".join(str(item) for item in report.failures)
    assert report.blocking == []
    assert report.ok
