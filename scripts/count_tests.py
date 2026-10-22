"""Print the real test count (collected by pytest, not estimated).

Usage: python scripts/count_tests.py
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    count = sum(1 for line in result.stdout.splitlines() if "::" in line)
    print(count)


if __name__ == "__main__":
    main()
