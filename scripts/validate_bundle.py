#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

for path in ROOT.glob("schema/*.json"):
    json.loads(path.read_text(encoding="utf-8"))

for path in ROOT.glob("config/**/*.yaml"):
    yaml.safe_load(path.read_text(encoding="utf-8"))

for path in ROOT.glob("backend/**/*.py"):
    py_compile.compile(str(path), doraise=True)

package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
assert package["name"] == "lore-studio-frontend"

print("Bundle validation passed.")
