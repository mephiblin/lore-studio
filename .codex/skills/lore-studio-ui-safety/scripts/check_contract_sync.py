#!/usr/bin/env python3
"""Read-only Lore Studio contract and repository consistency preflight."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def repository_root() -> Path:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("FAIL: run this checker inside the Lore Studio git repository") from exc
    return Path(value)


ROOT = repository_root()
FAILURES: list[str] = []
PASSES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def passed(message: str) -> None:
    PASSES.append(message)


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        fail(f"missing required file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


required_files = [
    "AGENTS.md",
    "PROJECT_MANIFEST.txt",
    "VERIFICATION.md",
    "docs/UI_PAGE_CONTRACT.md",
    "docs/CHANGE_SAFETY_CHECKLIST.md",
    "docs/INFORMATION_ARCHITECTURE.md",
    "docs/DEVELOPMENT.md",
    "docs/DATA_MODEL.md",
    "docs/IMPLEMENTATION_STATUS.md",
    "docs/ACCEPTANCE_TESTS.md",
    "docs/product-audit/recursive-audit.md",
    ".codex/skills/lore-studio-ui-safety/SKILL.md",
    ".codex/skills/lore-studio-ui-safety/agents/openai.yaml",
    ".codex/skills/lore-studio-ui-safety/scripts/check_contract_sync.py",
]
for required in required_files:
    read(required)
if not FAILURES:
    passed("required contracts and project-local skill files exist")

ui_contract = read("docs/UI_PAGE_CONTRACT.md")
checklist = read("docs/CHANGE_SAFETY_CHECKLIST.md")
information_architecture = read("docs/INFORMATION_ARCHITECTURE.md")
readme = read("README.md")
agents = read("AGENTS.md")

route_files = {
    "/": "frontend/src/routes/+page.svelte",
    "/editor": "frontend/src/routes/editor/+page.svelte",
    "/playbook": "frontend/src/routes/playbook/+page.svelte",
    "/documents": "frontend/src/routes/documents/+page.svelte",
    "/lorebook": "frontend/src/routes/lorebook/+page.svelte",
    "/settings": "frontend/src/routes/settings/+page.svelte",
}
for route, relative in route_files.items():
    if not (ROOT / relative).is_file():
        fail(f"documented route {route} has no file: {relative}")
    if f"`{route}`" not in ui_contract:
        fail(f"UI_PAGE_CONTRACT.md does not document route {route}")
if not any("documented route" in item or "does not document route" in item for item in FAILURES):
    passed("five lifecycle routes and the settings utility route exist and are documented")

link_expectations = [
    ("README.md", readme, "docs/UI_PAGE_CONTRACT.md"),
    ("README.md", readme, "docs/CHANGE_SAFETY_CHECKLIST.md"),
    ("CHANGE_SAFETY_CHECKLIST.md", checklist, "UI_PAGE_CONTRACT.md"),
    ("CHANGE_SAFETY_CHECKLIST.md", checklist, "lore-studio-ui-safety"),
    ("UI_PAGE_CONTRACT.md", ui_contract, "lore-studio-ui-safety"),
    ("INFORMATION_ARCHITECTURE.md", information_architecture, "UI_PAGE_CONTRACT.md"),
    ("AGENTS.md", agents, "lore-studio-ui-safety"),
]
for owner, content, needle in link_expectations:
    if needle not in content:
        fail(f"{owner} does not reference {needle}")
if not any("does not reference" in item for item in FAILURES):
    passed("contract, checklist, README, IA, and AGENTS references are connected")

migration_dir = ROOT / "backend/alembic/versions"
revisions: set[str] = set()
parents: set[str] = set()
for migration in migration_dir.glob("*.py"):
    source = migration.read_text(encoding="utf-8")
    revision_match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    parent_match = re.search(r'^down_revision\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if revision_match:
        revisions.add(revision_match.group(1))
    if parent_match:
        parents.add(parent_match.group(1))
heads = sorted(revisions - parents)
if len(heads) != 1:
    fail(f"expected one Alembic head, found: {heads or 'none'}")
else:
    head = heads[0]
    for relative in [
        "docs/DEVELOPMENT.md",
        "docs/DATA_MODEL.md",
        "docs/IMPLEMENTATION_STATUS.md",
        "VERIFICATION.md",
    ]:
        if head not in read(relative):
            fail(f"{relative} does not mention current Alembic head {head}")
    if not any("Alembic head" in item for item in FAILURES):
        passed(f"migration and status documents agree on Alembic head {head}")

manifest_entries = {
    line.strip()
    for line in read("PROJECT_MANIFEST.txt").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
}
for required in required_files:
    if required not in manifest_entries:
        fail(f"PROJECT_MANIFEST.txt is missing {required}")
missing_manifest_files = sorted(entry for entry in manifest_entries if not (ROOT / entry).is_file())
for relative in missing_manifest_files:
    fail(f"manifest entry does not exist: {relative}")
try:
    tracked = set(
        subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    )
    deleted = set(
        subprocess.check_output(["git", "ls-files", "--deleted"], cwd=ROOT, text=True).splitlines()
    )
    tracked -= deleted
except (OSError, subprocess.CalledProcessError):
    tracked = set()
for relative in sorted(tracked - manifest_entries):
    fail(f"tracked stable file is missing from PROJECT_MANIFEST.txt: {relative}")
if not any("MANIFEST" in item or "manifest entry" in item or "tracked stable" in item for item in FAILURES):
    passed("project manifest covers all tracked stable files")

conflict_pattern = re.compile(r"^(<{7}|={7}|>{7})(?:\s|$)", re.MULTILINE)
debug_pattern = re.compile(r"console\.(?:log|debug)\s*\(|\bdebugger\s*;|\b(?:TODO|FIXME|HACK)\b")
code_roots = ["backend/app", "frontend/src", "scripts", "schema", "config"]
code_suffixes = {".py", ".js", ".svelte", ".css", ".json", ".yaml", ".yml", ".md"}
for root_name in code_roots:
    for path in (ROOT / root_name).rglob("*"):
        if not path.is_file() or path.suffix not in code_suffixes:
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT).as_posix()
        if conflict_pattern.search(source):
            fail(f"merge-conflict marker remains in {relative}")
        if root_name in {"backend/app", "frontend/src", "scripts"} and debug_pattern.search(source):
            fail(f"debug/TODO marker remains in product code: {relative}")
if not any("merge-conflict" in item or "debug/TODO" in item for item in FAILURES):
    passed("product code contains no conflict or debug markers")

api_path = ROOT / "frontend/src/lib/api.js"
for path in (ROOT / "frontend/src").rglob("*"):
    if not path.is_file() or path.suffix not in {".js", ".svelte"} or path == api_path:
        continue
    if re.search(r"\bfetch\s*\(", path.read_text(encoding="utf-8", errors="replace")):
        fail(f"direct fetch bypasses src/lib/api.js: {path.relative_to(ROOT).as_posix()}")
if not any("direct fetch" in item for item in FAILURES):
    passed("frontend server calls remain centralized in src/lib/api.js")

for message in PASSES:
    print(f"PASS: {message}")
for message in FAILURES:
    print(f"FAIL: {message}")
print(f"SUMMARY: {len(PASSES)} passed checks, {len(FAILURES)} failures")
sys.exit(1 if FAILURES else 0)
