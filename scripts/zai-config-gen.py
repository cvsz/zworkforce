#!/usr/bin/env python3
"""Compatibility entry point for the ZC configuration generator.

The implementation lives with the ZC service; this stable repository-level
entry point keeps existing automation and tests working from the monorepo root.
"""

from pathlib import Path
import runpy


IMPLEMENTATION = Path(__file__).resolve().parents[1] / "services" / "zc" / "scripts" / "zai-config-gen.py"

if __name__ == "__main__":
    runpy.run_path(str(IMPLEMENTATION), run_name="__main__")
