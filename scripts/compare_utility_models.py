#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for path in args.reports:
        if not path.exists():
            rows.append((path.stem, "NOT_RUN", "-", "-", "-"))
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        metrics = data["metrics"]
        rows.append((data.get("health", {}).get("model", path.stem), "PASS" if data.get("passed") else "FAIL", f"{metrics['json_valid_rate']:.1%}", f"{metrics['semantic_accuracy']:.1%}", f"{metrics['average_latency_seconds']:.2f}s"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("# Utility Model Comparison\n\n| Model | Gate | JSON valid | Meaning | Latency |\n|---|---|---:|---:|---:|\n" + "\n".join(f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
