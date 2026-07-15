import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from scripts import blind_caddy_certification as certification


def test_run_challenge_copies_identical_bytes_and_uses_each_worktree_source(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fixture = tmp_path / "challenge.spec.yaml"
    fixture.write_bytes(b"kind: detail\nname: blind_cleated_caddy\n")
    python = tmp_path / "venv" / "python"
    python.parent.mkdir()
    base_python = tmp_path / "runtime" / "python3"
    base_python.parent.mkdir()
    base_python.touch()
    python.symlink_to(base_python)

    worktree_refs = {}
    added = []
    removed = []
    copied_by_ref = {}
    pytest_calls = []
    commits = {
        certification.LEGACY_REF: "1" * 40,
        certification.GENERIC_REF: "2" * 40,
    }
    node_ids = (
        "tests/test_generic_certification.py::test_compile",
        "tests/test_generic_certification.py::TestGate::test_validation",
    )

    def fake_run(command, *, cwd=None, env=None, check=False):
        command = tuple(str(part) for part in command)
        if command[0] == "git" and command[3:6] == (
            "worktree",
            "add",
            "--detach",
        ):
            worktree = Path(command[6])
            ref = command[7]
            worktree_refs[worktree] = ref
            added.append(worktree)
            (worktree / "details").mkdir(parents=True)
            (worktree / "src").mkdir()
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[0] == "git" and command[3:] == ("rev-parse", "HEAD"):
            ref = worktree_refs[Path(command[2])]
            return subprocess.CompletedProcess(
                command, 0, stdout=f"{commits[ref]}\n", stderr=""
            )
        if command[0] == "git" and command[3:6] == (
            "worktree",
            "remove",
            "--force",
        ):
            worktree = Path(command[6])
            ref = worktree_refs[worktree]
            copied_by_ref[ref] = (
                worktree / "details" / "armchair_caddy.spec.yaml"
            ).read_bytes()
            removed.append(worktree)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        pytest_calls.append(
            {"command": command, "cwd": Path(cwd), "env": env, "check": check}
        )
        ref = worktree_refs[Path(cwd)]
        if command[1:] == certification.COLLECT_ARGS:
            stdout = "\n".join((*node_ids, "2 tests collected in 0.01s", ""))
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        if command[1:] == certification.GATE_ARGS:
            return subprocess.CompletedProcess(
                command,
                7 if ref == certification.LEGACY_REF else 9,
                stdout=f"{ref} gate stdout\n",
                stderr=f"{ref} gate stderr\n",
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(certification, "_run", fake_run)

    legacy, generic = certification.run_challenge(
        repo_root / ".." / "repo",
        python=python.parent / ".." / "venv" / "python",
        fixture=fixture.parent / "." / fixture.name,
    )

    fixture_bytes = fixture.read_bytes()
    digest = hashlib.sha256(fixture_bytes).hexdigest()
    assert copied_by_ref == {
        certification.LEGACY_REF: fixture_bytes,
        certification.GENERIC_REF: fixture_bytes,
    }
    assert legacy.fixture_sha256 == generic.fixture_sha256 == digest
    assert (legacy.name, legacy.ref, legacy.commit) == (
        "legacy",
        certification.LEGACY_REF,
        commits[certification.LEGACY_REF],
    )
    assert (generic.name, generic.ref, generic.commit) == (
        "generic",
        certification.GENERIC_REF,
        commits[certification.GENERIC_REF],
    )

    expected_gate = (str(python), *certification.GATE_ARGS)
    expected_collect = (str(python), *certification.COLLECT_ARGS)
    assert legacy.gate_command == generic.gate_command == expected_gate
    assert legacy.collect_command == generic.collect_command == expected_collect
    assert legacy.node_ids == generic.node_ids == node_ids
    assert (legacy.returncode, generic.returncode) == (7, 9)
    assert legacy.output == "5e1498e gate stdout\n5e1498e gate stderr\n"
    assert generic.output == "HEAD gate stdout\nHEAD gate stderr\n"

    assert len(pytest_calls) == 4
    for call in pytest_calls:
        ref = worktree_refs[call["cwd"]]
        assert call["command"][0] == str(python)
        assert call["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
        assert call["env"]["PYTHONPATH"].split(os.pathsep)[0] == str(
            call["cwd"] / "src"
        )
        if call["command"][1:] == certification.GATE_ARGS:
            assert call["check"] is False
        assert ref in {certification.LEGACY_REF, certification.GENERIC_REF}

    assert len(added) == 2
    assert [worktree_refs[path] for path in added] == [
        certification.LEGACY_REF,
        certification.GENERIC_REF,
    ]
    assert removed == list(reversed(added))


def test_run_challenge_removes_the_first_worktree_when_second_setup_fails(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fixture = tmp_path / "challenge.spec.yaml"
    fixture.write_bytes(b"kind: detail\n")
    python = tmp_path / "python"

    worktree_refs = {}
    successfully_added = []
    removed = []
    setup_failure = subprocess.CalledProcessError(
        128,
        ("git", "worktree", "add"),
        output="generic setup stdout",
        stderr="generic setup stderr",
    )

    def fake_run(command, *, cwd=None, env=None, check=False):
        command = tuple(str(part) for part in command)
        if command[0] == "git" and command[3:6] == (
            "worktree",
            "add",
            "--detach",
        ):
            worktree = Path(command[6])
            ref = command[7]
            if ref == certification.GENERIC_REF:
                raise setup_failure
            worktree_refs[worktree] = ref
            successfully_added.append(worktree)
            (worktree / "details").mkdir(parents=True)
            (worktree / "src").mkdir()
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[0] == "git" and command[3:] == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess(
                command, 0, stdout=f"{'a' * 40}\n", stderr=""
            )
        if command[0] == "git" and command[3:6] == (
            "worktree",
            "remove",
            "--force",
        ):
            removed.append(Path(command[6]))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[1:] == certification.COLLECT_ARGS:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="tests/test_gate.py::test_rejection\n",
                stderr="",
            )
        if command[1:] == certification.GATE_ARGS:
            return subprocess.CompletedProcess(
                command, 1, stdout="expected rejection\n", stderr=""
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(certification, "_run", fake_run)

    with pytest.raises(subprocess.CalledProcessError) as raised:
        certification.run_challenge(
            repo_root, python=python, fixture=fixture
        )

    assert raised.value is setup_failure
    assert removed == successfully_added
    assert len(removed) == 1
    assert worktree_refs[removed[0]] == certification.LEGACY_REF


def test_cli_prints_hash_commands_nodes_and_output_without_writing_results(
    tmp_path, monkeypatch, capsys
):
    digest = "d" * 64
    python = tmp_path / "oracle-python"
    results = (
        certification.OracleResult(
            name="legacy",
            ref=certification.LEGACY_REF,
            commit="a" * 40,
            fixture_sha256=digest,
            collect_command=(
                str(python),
                *certification.COLLECT_ARGS,
            ),
            node_ids=("tests/test_gate.py::test_legacy",),
            gate_command=(str(python), *certification.GATE_ARGS),
            returncode=3,
            output="legacy stdout\nlegacy stderr\n",
        ),
        certification.OracleResult(
            name="generic",
            ref=certification.GENERIC_REF,
            commit="b" * 40,
            fixture_sha256=digest,
            collect_command=(
                str(python),
                *certification.COLLECT_ARGS,
            ),
            node_ids=("tests/test_gate.py::test_generic",),
            gate_command=(str(python), *certification.GATE_ARGS),
            returncode=5,
            output="generic stdout\ngeneric stderr\n",
        ),
    )
    calls = []

    def fake_run_challenge(repo_root, **kwargs):
        calls.append((repo_root, kwargs))
        return results

    monkeypatch.setattr(certification, "run_challenge", fake_run_challenge)

    returncode = certification.main(
        ["--repo-root", str(tmp_path), "--python", str(python)]
    )

    assert returncode == 0
    assert calls == [
        (
            tmp_path.resolve(),
            {
                "python": python.resolve(),
                "legacy_ref": certification.LEGACY_REF,
                "generic_ref": certification.GENERIC_REF,
            },
        )
    ]
    stdout = capsys.readouterr().out
    for result in results:
        assert f"name: {result.name}" in stdout
        assert f"ref: {result.ref}" in stdout
        assert f"commit: {result.commit}" in stdout
        assert f"fixture_sha256: {result.fixture_sha256}" in stdout
        assert f"collect_command: {' '.join(result.collect_command)}" in stdout
        assert result.node_ids[0] in stdout
        assert f"gate_command: {' '.join(result.gate_command)}" in stdout
        assert f"returncode: {result.returncode}" in stdout
        assert result.output in stdout
    assert stdout.index("name: legacy") < stdout.index("name: generic")
    assert list(tmp_path.iterdir()) == []
