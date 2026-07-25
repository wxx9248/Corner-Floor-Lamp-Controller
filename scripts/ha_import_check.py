#!/usr/bin/env python3
"""Import the custom component against the installed Home Assistant.

Fails if any module fails to import or if importing raises a
DeprecationWarning originating from our code — the early-warning signal that
a new HA release deprecated an API the integration uses.
"""
from __future__ import annotations

import importlib
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "home-assistant" / "custom_components"

MODULES = [
    "const",
    "entity",
    "stream",
    "config_flow",
    "__init__",
    "light",
    "switch",
    "select",
    "number",
]


def main() -> int:
    from homeassistant.const import __version__ as ha_version

    print(f"Home Assistant {ha_version} on Python {sys.version.split()[0]}")

    # HA expects the component importable as custom_components.duoco_stripx
    staging = Path(tempfile.mkdtemp())
    (staging / "custom_components").symlink_to(COMPONENT)
    sys.path.insert(0, str(staging))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for module in MODULES:
            importlib.import_module(f"custom_components.duoco_stripx.{module}")
            print(f"import OK: {module}")

    ours = [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and ("duoco" in str(w.filename) or "duoco" in str(w.message))
    ]
    for w in ours:
        print(f"DEPRECATION {w.filename}:{w.lineno}: {w.message}", file=sys.stderr)
    if ours:
        print(f"FAIL: {len(ours)} deprecation warning(s) from our code", file=sys.stderr)
        return 1
    print("no deprecation warnings from our code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
