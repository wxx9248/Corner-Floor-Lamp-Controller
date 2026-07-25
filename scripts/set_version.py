#!/usr/bin/env python3
"""Stamp a release version into every version field of the project.

Usage: python scripts/set_version.py X.Y.Z

The repo permanently commits `0.0.0` placeholders; the release workflow runs
this script in its workspace to stamp the real version before building
artifacts. Each substitution must match exactly the expected number of times —
any drift in the files aborts the release instead of shipping mismatched
artifacts.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, pattern, replacement template, expected match count)
SUBSTITUTIONS = [
    (
        ROOT / "library" / "pyproject.toml",
        r'^version = "\d+\.\d+\.\d+"$',
        'version = "{v}"',
        1,
    ),
    (
        ROOT / "library" / "src" / "duoco_stripx" / "__init__.py",
        r'^__version__ = "\d+\.\d+\.\d+"$',
        '__version__ = "{v}"',
        1,
    ),
    (
        ROOT / "home-assistant" / "custom_components" / "duoco_stripx" / "manifest.json",
        r'^  "version": "\d+\.\d+\.\d+"$',
        '  "version": "{v}"',
        1,
    ),
    (
        # requirement URL: .../download/vX.Y.Z/duoco_stripx-X.Y.Z-py3-none-any.whl
        ROOT / "home-assistant" / "custom_components" / "duoco_stripx" / "manifest.json",
        r"/download/v\d+\.\d+\.\d+/duoco_stripx-\d+\.\d+\.\d+-py3-none-any\.whl",
        "/download/v{v}/duoco_stripx-{v}-py3-none-any.whl",
        1,
    ),
]


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        print(f"usage: {sys.argv[0]} X.Y.Z", file=sys.stderr)
        return 2
    version = sys.argv[1]

    for path, pattern, template, expected in SUBSTITUTIONS:
        text = path.read_text()
        new_text, count = re.subn(
            pattern, template.format(v=version), text, flags=re.MULTILINE
        )
        if count != expected:
            print(
                f"ERROR: {path.relative_to(ROOT)}: pattern {pattern!r} matched "
                f"{count} times, expected {expected} — refusing to stamp",
                file=sys.stderr,
            )
            return 1
        path.write_text(new_text)
        print(f"stamped {version} into {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
