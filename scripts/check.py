"""Every check, one line each when it passes: lint, format, types, the tests.

    uv run python scripts/check.py    # or `make`

Runs from the repository's folder wherever it is called from; prints a failing check's output
in full and exits 1 if any check failed.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Each check: its name and the command that runs it.
CHECKS = [
    ("ruff", ["uv", "run", "ruff", "check", "-q", "--output-format", "concise", "."]),
    ("format", ["uv", "run", "ruff", "format", "-q", "--check", "."]),
    ("ty", ["uv", "run", "ty", "check", "-q", "--output-format", "concise"]),
    ("pytest", ["uv", "run", "-q", "pytest"]),
]


def run(name: str, command: list[str]) -> bool:
    """Run one check; say `name: ok` (pytest's last line too) or its output and FAILED."""
    done = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    out = (done.stdout + done.stderr).strip()
    if done.returncode == 0:
        last = out.splitlines()[-1] if name == "pytest" and out else ""
        print(f"{name}: {last + ' ' if last else ''}ok")
        return True
    print(out)
    print(f"{name}: FAILED")
    return False


def main() -> int:
    """Run every check, even after one fails; 0 if all passed, else 1."""
    passed = [run(name, command) for name, command in CHECKS]
    return 0 if all(passed) else 1


if __name__ == "__main__":
    sys.exit(main())
