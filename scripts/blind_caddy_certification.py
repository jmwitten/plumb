"""Run a frozen detail fixture against disposable legacy and generic oracles."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence


LEGACY_REF = "5e1498e"
GENERIC_REF = "HEAD"
FIXTURE = Path("tests/fixtures/certification/blind_cleated_caddy.spec.yaml")
GATE_ARGS = ("-m", "pytest", "--detail-gate", "armchair_caddy", "-q", "-n", "4")
COLLECT_ARGS = (
    "-m",
    "pytest",
    "--detail-gate",
    "armchair_caddy",
    "--collect-only",
    "-q",
)


@dataclass(frozen=True)
class OracleResult:
    name: str
    ref: str
    commit: str
    fixture_sha256: str
    collect_command: tuple[str, ...]
    node_ids: tuple[str, ...]
    gate_command: tuple[str, ...]
    returncode: int
    output: str


def _run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        tuple(command),
        cwd=cwd,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


def _combined_output(process: subprocess.CompletedProcess[str]) -> str:
    return (process.stdout or "") + (process.stderr or "")


def _absolute_executable(path: Path) -> Path:
    """Make an executable path absolute without dereferencing a venv symlink."""
    return Path(os.path.abspath(path.expanduser()))


def run_challenge(
    repo_root: Path,
    *,
    python: Path,
    fixture: Path | None = None,
    legacy_ref: str = LEGACY_REF,
    generic_ref: str = GENERIC_REF,
) -> tuple[OracleResult, OracleResult]:
    repo_root = repo_root.expanduser().resolve()
    python = _absolute_executable(python)
    fixture = (
        fixture.expanduser().resolve()
        if fixture is not None
        else (repo_root / FIXTURE).resolve()
    )

    fixture_bytes = fixture.read_bytes()
    fixture_sha256 = hashlib.sha256(fixture_bytes).hexdigest()
    collect_command = (str(python), *COLLECT_ARGS)
    gate_command = (str(python), *GATE_ARGS)
    added_worktrees: list[Path] = []
    results: list[OracleResult] = []
    primary_failure = False

    with TemporaryDirectory(prefix="blind-caddy-certification-") as temporary:
        temporary_root = Path(temporary)
        try:
            for name, ref in (("legacy", legacy_ref), ("generic", generic_ref)):
                worktree = temporary_root / name
                _run(
                    (
                        "git",
                        "-C",
                        str(repo_root),
                        "worktree",
                        "add",
                        "--detach",
                        str(worktree),
                        ref,
                    ),
                    check=True,
                )
                added_worktrees.append(worktree)

                destination = worktree / "details" / "armchair_caddy.spec.yaml"
                destination.write_bytes(fixture_bytes)
                copied_sha256 = hashlib.sha256(destination.read_bytes()).hexdigest()
                if copied_sha256 != fixture_sha256:
                    raise RuntimeError(
                        f"fixture copy hash mismatch at {destination}: "
                        f"expected {fixture_sha256}, got {copied_sha256}"
                    )

                commit = _run(
                    ("git", "-C", str(worktree), "rev-parse", "HEAD"),
                    check=True,
                ).stdout.strip()
                env = os.environ.copy()
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                source = str(worktree / "src")
                inherited_pythonpath = env.get("PYTHONPATH")
                env["PYTHONPATH"] = (
                    source
                    if not inherited_pythonpath
                    else source + os.pathsep + inherited_pythonpath
                )

                collection = _run(
                    collect_command,
                    cwd=worktree,
                    env=env,
                    check=True,
                )
                node_ids = tuple(
                    line
                    for raw_line in _combined_output(collection).splitlines()
                    if "::" in (line := raw_line.strip())
                    and line.startswith("tests/")
                )
                gate = _run(
                    gate_command,
                    cwd=worktree,
                    env=env,
                    check=False,
                )
                results.append(
                    OracleResult(
                        name=name,
                        ref=ref,
                        commit=commit,
                        fixture_sha256=fixture_sha256,
                        collect_command=collect_command,
                        node_ids=node_ids,
                        gate_command=gate_command,
                        returncode=gate.returncode,
                        output=_combined_output(gate),
                    )
                )
        except BaseException:
            primary_failure = True
            raise
        finally:
            cleanup_failures = []
            for worktree in reversed(added_worktrees):
                try:
                    _run(
                        (
                            "git",
                            "-C",
                            str(repo_root),
                            "worktree",
                            "remove",
                            "--force",
                            str(worktree),
                        ),
                        check=True,
                    )
                except BaseException as failure:
                    cleanup_failures.append(failure)
            if cleanup_failures and not primary_failure:
                raise cleanup_failures[0]

    return results[0], results[1]


def _print_result(result: OracleResult) -> None:
    print(f"name: {result.name}")
    print(f"ref: {result.ref}")
    print(f"commit: {result.commit}")
    print(f"fixture_sha256: {result.fixture_sha256}")
    print(f"collect_command: {' '.join(result.collect_command)}")
    print("node_ids:")
    for node_id in result.node_ids:
        print(f"  {node_id}")
    print(f"gate_command: {' '.join(result.gate_command)}")
    print(f"returncode: {result.returncode}")
    print("output:")
    print(result.output, end="" if result.output.endswith("\n") else "\n")


def main(argv: Sequence[str] | None = None) -> int:
    default_repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run the disposable blind-caddy dual-oracle challenge."
    )
    parser.add_argument("--repo-root", type=Path, default=default_repo_root)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--legacy-ref", default=LEGACY_REF)
    parser.add_argument("--generic-ref", default=GENERIC_REF)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.expanduser().resolve()
    python = (
        _absolute_executable(args.python)
        if args.python is not None
        else _absolute_executable(repo_root / ".venv" / "bin" / "python")
    )
    results = run_challenge(
        repo_root,
        python=python,
        legacy_ref=args.legacy_ref,
        generic_ref=args.generic_ref,
    )
    for index, result in enumerate(results):
        if index:
            print()
        _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
