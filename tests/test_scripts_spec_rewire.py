"""Task 4B-3/4B-4b — no consumer loads an imperative detail ``.py`` anymore; the
load path is ``compile_spec_file(... .spec.yaml)``.

4B-3 pinned the three SCRIPTS: (1) no script imports/execs a detail ``.py``; (2)
``load_details()`` returns compiled ``SpecDetail``s; (3) the report's
``--vault-copy`` flag defaults OFF. 4B-4b removed the four imperative mirrors
outright, so this also guards (4) that no TEST loads a detail ``.py`` either and
(5) that ``scripts/capture_frozen_truth.py`` — the one script allowed to name the
``.py`` — now refuses to run, teaching why, instead of writing an empty corpus.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
THREE_SCRIPTS = ("consolidated_report.py", "_site_overview.py", "build_inspector.py")
DETAIL_NAMES = ("platform", "rock_anchor", "tree_attachment", "trolley_launch")


def _load(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def report_mod():
    return _load("consolidated_report_rewire", SCRIPTS / "consolidated_report.py")


# --------------------------------------------------------------------------- #
# (1) grep-level: no detail .py is loaded by any of the three scripts.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("script", THREE_SCRIPTS)
def test_no_detail_py_is_loaded_by_script(script):
    src = (SCRIPTS / script).read_text()
    # No ``"<detail>.py"`` string literal (the old spec_from_file_location /
    # module-path load target). The spec path references ``<detail>.spec.yaml``.
    for name in DETAIL_NAMES:
        assert f"{name}.py" not in src, (
            f"{script} still references details/{name}.py — the 4B-3 rewire loads "
            f"the detail from {name}.spec.yaml via compile_spec_file, not the "
            f"imperative module"
        )
    # And nothing loads a bare ``.py`` detail by file path at all.
    assert not re.search(r'spec_from_file_location\([^)]*\.py"', src), (
        f"{script} loads a module by explicit .py path — no detail module should "
        f"be exec'd anymore"
    )
    # Nor a DOTTED import of the details package — ``import details.platform`` /
    # ``from details import platform`` carry no ".py" substring (so the checks
    # above miss them) but still import the imperative module, re-triggering the
    # stdlib-``platform`` shadow the spec path exists to avoid.
    assert not re.search(r'^\s*import\s+details\.', src, re.M), (
        f"{script} does ``import details.<module>`` — details are loaded via "
        f"compile_spec_file(<name>.spec.yaml), never imported as modules"
    )
    assert not re.search(r'^\s*from\s+details\s+import\b', src, re.M), (
        f"{script} does ``from details import ...`` — details are loaded via "
        f"compile_spec_file(<name>.spec.yaml), never imported as modules"
    )


def test_consolidated_report_and_inspector_use_compile_spec_file():
    for script in ("consolidated_report.py", "build_inspector.py"):
        src = (SCRIPTS / script).read_text()
        assert "compile_spec_file" in src, (
            f"{script} must load details via compile_spec_file (the spec path)"
        )


# --------------------------------------------------------------------------- #
# (2) load_details() returns compiled SpecDetails.
# --------------------------------------------------------------------------- #
def test_load_details_returns_spec_details(report_mod):
    from detailgen.spec.compiler import SpecDetail

    details = report_mod.load_details()
    assert set(details) == set(DETAIL_NAMES)
    for name, d in details.items():
        assert isinstance(d, SpecDetail), (
            f"load_details()[{name!r}] is {type(d).__name__}, expected a "
            f"SpecDetail from the spec path"
        )


# --------------------------------------------------------------------------- #
# (3) --vault-copy defaults OFF: a plain run never invokes the vault copy.
# --------------------------------------------------------------------------- #
class _FakeReport:
    ok = False
    failures: list = []
    blocking: list = []   # STRUCT: main()'s summary counts blocking (FAILs + UNKNOWNs)


class _FakeAssembly:
    parts: list = []


class _FakeSite:
    assembly = _FakeAssembly()

    def validate(self):
        return _FakeReport()


def _stub_pipeline(report_mod, monkeypatch, tmp_path, copy_calls):
    """Stub the heavy build so main() reaches the vault-copy decision fast,
    and record every copy_to_vault invocation."""
    monkeypatch.setattr(report_mod, "HTML_OUT", tmp_path / "doc.html")
    monkeypatch.setattr(report_mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(report_mod, "RENDERS", tmp_path / "renders")
    monkeypatch.setattr(report_mod, "load_details", lambda: {})
    monkeypatch.setattr(report_mod, "load_site", lambda: _FakeSite())
    # Panel E's pier-foundation zoom is a heavy render step in main() (it renders
    # from the platform's placed parts); stub it alongside build_html so this
    # vault-copy behavior test stays fast and detail-free.
    monkeypatch.setattr(report_mod, "pier_foundation_images", lambda details: {})
    monkeypatch.setattr(report_mod, "build_html", lambda *a, **k: "<html></html>")
    monkeypatch.setattr(report_mod, "copy_to_vault",
                        lambda p: copy_calls.append(p))


def test_vault_copy_off_by_default(report_mod, monkeypatch, tmp_path):
    copy_calls: list = []
    _stub_pipeline(report_mod, monkeypatch, tmp_path, copy_calls)
    report_mod.main([])
    assert copy_calls == [], "a plain run must not copy the document to the vault"
    assert (tmp_path / "doc.html").exists(), "the doc is still written to the repo output"


def test_vault_copy_flag_opts_in(report_mod, monkeypatch, tmp_path):
    copy_calls: list = []
    _stub_pipeline(report_mod, monkeypatch, tmp_path, copy_calls)
    report_mod.main(["--vault-copy"])
    assert len(copy_calls) == 1, "--vault-copy must invoke the vault copy exactly once"


# --------------------------------------------------------------------------- #
# (4) grep-level: no TEST loads a detail .py either (4B-4b removed the four
#     imperative mirrors; every consumer builds through the spec compiler).
# --------------------------------------------------------------------------- #
_TESTS_DIR = REPO / "tests"
_ALL_TEST_FILES = sorted(
    p for p in _TESTS_DIR.glob("test_*.py") if p.name != Path(__file__).name)


@pytest.mark.parametrize("test_file", _ALL_TEST_FILES, ids=lambda p: p.name)
def test_no_test_loads_a_detail_py(test_file):
    """No test imports or execs any of the four retired imperative details. The
    guard targets the LOAD mechanisms, not prose: the frozen-truth oracles still
    name ``details/platform.py`` etc. in docstrings as the historical source of
    the corpus, which is true and must stay."""
    src = test_file.read_text()
    # (a) bare import of a detail module. ``platform`` is omitted — it collides
    #     with the stdlib module, so the detail was only ever loaded by file path
    #     (caught by (b)); a bare ``import platform`` is always the stdlib one.
    for name in ("rock_anchor", "tree_attachment", "trolley_launch"):
        assert not re.search(rf'^\s*(?:from|import)\s+{name}\b', src, re.M), (
            f"{test_file.name} imports the retired detail module {name!r} — build "
            f"it via compile_spec_file({name}.spec.yaml) instead")
    # (b) module-by-file-path exec of a detail .py — the importlib load target,
    #     by literal name OR (the blind spot the first cut of this guard had) a
    #     variable filename. A test only builds a ``.py`` filename from a
    #     variable to load a detail by iterating names; the retained script loads
    #     use literal filenames ("consolidated_report.py"). Signals:
    #       - a ``.py`` path resolved against the details dir,
    #       - an f-string that interpolates a name and ends in ``.py``,
    #       - a bare-quoted ``"<name>.py"`` for one of the four deleted details
    #         (the ROOT/"details"/"platform.py" path-join class), and
    #       - a same-line spec_from_file_location(...<name>.py).
    #     ``deck_ledger_example.py`` is the one demo detail that stays imperative;
    #     ``.spec.yaml`` joins never match (different extension), and prose
    #     ``details/platform.py`` never matches (no quote hugs the filename).
    detail_py = [
        m for m in
        re.findall(r'(?:DETAILS|DETAILS_DIR)\s*/\s*f?["\'][^"\']*\.py["\']', src)
        # an f-string that is a BARE filename (no spaces/slashes) interpolating a
        # name and ending in .py — e.g. f"{stem}.py", f"det_{fname}.py". The
        # no-space/no-slash bound keeps prose f-strings (…details/{slug}.py) out.
        + re.findall(r'f["\'][^"\'/\s]*\{[^}]+\}[^"\'/\s]*\.py["\']', src)
        # a bare-quoted literal filename for one of the four deleted details,
        # e.g. ROOT / "details" / "platform.py" — the quotes hug the filename, so
        # a prose "details/platform.py" (slash before the name) does not match.
        + re.findall(
            r'["\'](?:platform|rock_anchor|tree_attachment|trolley_launch)\.py["\']', src)
        + re.findall(
            r'spec_from_file_location\((?:[^)]|\n)*?'
            r'(?:platform|rock_anchor|tree_attachment|trolley_launch)\.py', src)
        if "deck_ledger_example" not in m]
    assert not detail_py, (
        f"{test_file.name} execs a detail .py by file path ({detail_py}) — the "
        f"four imperative mirrors are gone; compile the spec.yaml instead")
    # (c) dotted details-package import (carries no ".py" substring, so (a)/(b)
    #     miss it, but still imports the retired module).
    assert not re.search(r'^\s*import\s+details\.', src, re.M), (
        f"{test_file.name} does ``import details.<module>`` — load via compile_spec_file")
    assert not re.search(r'^\s*from\s+details\s+import\b', src, re.M), (
        f"{test_file.name} does ``from details import ...`` — load via compile_spec_file")


# --------------------------------------------------------------------------- #
# (5) capture_frozen_truth is the one script allowed to name the .py — and now
#     that they are gone it refuses to run, teaching why, not writing an empty
#     corpus.
# --------------------------------------------------------------------------- #
def test_capture_frozen_truth_refuses_without_the_imperative_py():
    cap = _load("capture_frozen_truth_guard", SCRIPTS / "capture_frozen_truth.py")
    with pytest.raises(SystemExit) as e:
        cap._load_imperative("platform")
    msg = str(e.value)
    assert "is gone" in msg and "spec path is now the only path" in msg, msg
