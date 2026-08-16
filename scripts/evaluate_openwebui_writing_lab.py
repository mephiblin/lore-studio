#!/usr/bin/env python3
"""Run the shared writing fixture through every OpenWebUI LAB workspace model."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import yaml


def request_json(base_url: str, path: str, token: str, payload: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenWebUI {path} failed ({exc.code}): {detail}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("docs/model-evaluations/writing-profile-lab.yaml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/model-evaluations/writing-profile-lab-results.json"),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:12000")
    parser.add_argument(
        "--runtime",
        action="append",
        choices=("qwen", "gemma"),
        help="Runtime to evaluate; repeat to run both (default: both)",
    )
    parser.add_argument(
        "--comparison",
        help="Run the named tests.comparisons entry with one shared prompt",
    )
    parser.add_argument(
        "--profile",
        action="append",
        help="Profile key to evaluate; repeat to select more than one",
    )
    args = parser.parse_args()

    token = os.environ.get("LORE_OPENWEBUI_TOKEN", "").strip()
    if not token:
        raise SystemExit("LORE_OPENWEBUI_TOKEN is required")

    spec = yaml.safe_load(args.spec.read_text(encoding="utf-8"))
    request_json(args.base_url, "/api/models", token)
    comparison = (spec.get("tests", {}).get("comparisons") or {}).get(args.comparison)
    if args.comparison and not comparison:
        raise SystemExit(f"Unknown comparison: {args.comparison}")
    fixture = comparison.get("fixture") if comparison else "회백항 동부 수문"
    profile_keys = list(comparison.get("profiles") or []) if comparison else list(spec["profiles"])
    if args.profile:
        unknown_profiles = sorted(set(args.profile) - set(spec["profiles"]))
        if unknown_profiles:
            raise SystemExit(f"Unknown profile(s): {', '.join(unknown_profiles)}")
        profile_keys = [key for key in profile_keys if key in args.profile]
    results = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "fixture": fixture,
        "comparison": args.comparison,
        "results": [],
    }
    runtimes = tuple(args.runtime or ("qwen", "gemma"))
    for runtime_key in runtimes:
        for profile_key in profile_keys:
            model_id = f"lore-lab-{profile_key}-{runtime_key}"
            task_prompt = comparison["prompt"] if comparison else spec["tests"]["prompts"][profile_key]
            prompt = f"{task_prompt}\n\n{spec['tests']['shared_corpus']}"
            started = time.monotonic()
            try:
                data = request_json(
                    args.base_url,
                    "/api/chat/completions",
                    token,
                    {
                        "model": model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                )
                message = data["choices"][0]["message"]
                result = {
                    "runtime": runtime_key,
                    "profile": profile_key,
                    "workspace_model": model_id,
                    "served_model": data.get("model"),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "usage": data.get("usage") or {},
                    "finish_reason": data["choices"][0].get("finish_reason"),
                    "content": message.get("content", ""),
                }
            except (
                RuntimeError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                urllib.error.URLError,
                TimeoutError,
            ) as exc:  # keep the rest of the matrix running after expected request/shape failures
                result = {
                    "runtime": runtime_key,
                    "profile": profile_key,
                    "workspace_model": model_id,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "error": str(exc),
                }
            results["results"].append(result)
            args.output.write_text(
                json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"{runtime_key:5} {profile_key:22} "
                f"{result['elapsed_seconds']:7.2f}s "
                f"{len(result.get('content', '')):5} chars"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
