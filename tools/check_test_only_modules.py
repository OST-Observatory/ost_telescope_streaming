#!/usr/bin/env python3
"""
CI check: flag modules under code/ that are only referenced by tests/ and not
referenced by main entry points (overlay_pipeline.py) or calibration scripts.

Heuristic:
- For each Python file in code/ (direct children and subpackages), derive its
  importable module name as the stem (e.g., code/video_capture.py -> video_capture).
- Search repository for imports of that module ("from <mod> import" or "import <mod>").
- If the module is referenced in any non-test file (overlay_pipeline.py, code/** except itself,
  calibration/**), it's considered used. Otherwise, if it is referenced in tests/**, it's flagged.

Exit non-zero if any such modules are found, printing a concise report.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = REPO_ROOT / "code"
TESTS_DIR = REPO_ROOT / "tests"
CAL_DIR = REPO_ROOT / "calibration"
OVERLAY_PIPELINE = REPO_ROOT / "overlay_pipeline.py"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def find_import_usages(module: str) -> dict[str, list[Path]]:
    """Return mapping of area -> file paths where the module is imported.

    Areas: tests, code, calibration, overlay
    """
    pattern = re.compile(rf"\b(from\s+{re.escape(module)}\b|import\s+{re.escape(module)}\b)")
    result: dict[str, list[Path]] = {"tests": [], "code": [], "calibration": [], "overlay": []}

    # Search tests
    if TESTS_DIR.exists():
        for p in TESTS_DIR.rglob("*.py"):
            if pattern.search(read_text(p)):
                result["tests"].append(p)

    # Search code (excluding the module's own file, handled by caller)
    if CODE_DIR.exists():
        for p in CODE_DIR.rglob("*.py"):
            if pattern.search(read_text(p)):
                result["code"].append(p)

    # Search calibration scripts
    if CAL_DIR.exists():
        for p in CAL_DIR.rglob("*.py"):
            if pattern.search(read_text(p)):
                result["calibration"].append(p)

    # overlay_pipeline entry point
    if OVERLAY_PIPELINE.exists():
        if pattern.search(read_text(OVERLAY_PIPELINE)):
            result["overlay"].append(OVERLAY_PIPELINE)

    return result


def main() -> int:
    flagged: list[tuple[str, Path, dict[str, list[Path]]]] = []

    if not CODE_DIR.exists():
        print("No code/ directory found; skipping check")
        return 0

    for py_file in CODE_DIR.rglob("*.py"):
        # Skip package initializers and generated caches
        if py_file.name == "__init__.py":
            continue

        module = py_file.stem

        usages = find_import_usages(module)

        # Exclude self-reference in code list if present
        if py_file in usages["code"]:
            usages["code"] = [p for p in usages["code"] if p != py_file]

        non_test_refs = len(usages["overlay"]) + len(usages["calibration"]) + len(usages["code"]) > 0
        test_refs = len(usages["tests"]) > 0

        if test_refs and not non_test_refs:
            flagged.append((module, py_file, usages))

    if flagged:
        print("\nThe following modules appear to be referenced only in tests and not in overlay_pipeline/calibration/code:")
        for module, path, usages in flagged:
            print(f"- {module} ({path.relative_to(REPO_ROOT)})")
            if usages["tests"]:
                print(f"  tests: {len(usages['tests'])} refs (e.g., {usages['tests'][0].relative_to(REPO_ROOT)})")
        print("\nIf these are truly obsolete, consider removing them along with their tests.")
        return 1

    print("check_test_only_modules: OK - no test-only modules found")
    return 0


if __name__ == "__main__":
    sys.exit(main())


