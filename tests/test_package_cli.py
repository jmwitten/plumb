import subprocess
import sys


def test_package_cli_help_is_fast():
    proc = subprocess.run(
        [sys.executable, "-m", "detailgen.package", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode == 0
    assert "--tests-skipped" in proc.stdout
    assert "--delivery" in proc.stdout
