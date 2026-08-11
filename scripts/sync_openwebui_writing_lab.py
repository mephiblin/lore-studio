#!/usr/bin/env python3
"""Add or update Lore Studio writing-lab workspace models in OpenWebUI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml


def request_json(
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    payload: dict | None = None,
) -> dict | list | bool:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenWebUI {path} failed ({exc.code}): {detail}") from exc


def model_payloads(spec: dict) -> list[dict]:
    common = str(spec["common_system"]).strip()
    payloads: list[dict] = []
    for profile_key, profile in spec["profiles"].items():
        system = f"{common}\n\n{str(profile['system']).strip()}"
        for runtime_key, runtime in spec["base_models"].items():
            params = {"system": system, **profile["sampling"]}
            if runtime_key == "qwen":
                params["qwen_thinking"] = bool(runtime.get("thinking", False))
            payloads.append(
                {
                    "id": f"lore-lab-{profile_key}-{runtime_key}",
                    "base_model_id": runtime["id"],
                    "name": f"LAB {runtime['label']} · {profile['title']}",
                    "params": params,
                    "meta": {
                        "profile_image_url": None,
                        "description": f"Lore Studio 카드 분해 전 검증용: {profile['description']}",
                        "capabilities": {
                            "file_context": True,
                            "vision": False,
                            "file_upload": True,
                            "web_search": False,
                            "image_generation": False,
                            "code_interpreter": False,
                            "terminal": False,
                            "citations": False,
                            "status_updates": False,
                            "builtin_tools": False,
                        },
                        "tags": [
                            {"name": "LAB"},
                            {"name": "writing"},
                            {"name": "lore-studio"},
                            {"name": runtime_key},
                        ],
                        "suggestion_prompts": [
                            {
                                "title": [profile["title"], "회백항 검증 자료"],
                                "content": (
                                    f"{spec['tests']['prompts'][profile_key]}\n\n"
                                    f"{spec['tests']['shared_corpus']}"
                                ),
                            }
                        ],
                    },
                    "access_grants": [],
                    "is_active": True,
                }
            )
    return payloads


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("docs/model-evaluations/writing-profile-lab.yaml"),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:12000")
    parser.add_argument("--gemma-provider", default="http://host.docker.internal:18093/v1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec = yaml.safe_load(args.spec.read_text(encoding="utf-8"))
    models = model_payloads(spec)
    if args.dry_run:
        print(json.dumps({"model_ids": [model["id"] for model in models]}, ensure_ascii=False, indent=2))
        return 0

    token = os.environ.get("LORE_OPENWEBUI_TOKEN", "").strip()
    if not token:
        email = os.environ.get("LORE_OPENWEBUI_EMAIL", "").strip()
        password = os.environ.get("LORE_OPENWEBUI_PASSWORD", "")
        if not email or not password:
            print(
                "LORE_OPENWEBUI_TOKEN or LORE_OPENWEBUI_EMAIL/LORE_OPENWEBUI_PASSWORD is required",
                file=sys.stderr,
            )
            return 2
        session = request_json(
            args.base_url,
            "/api/v1/auths/signin",
            payload={"email": email, "password": password},
        )
        token = str(session["token"])

    provider = request_json(args.base_url, "/openai/config", token=token)
    urls = list(provider.get("OPENAI_API_BASE_URLS") or [])
    keys = list(provider.get("OPENAI_API_KEYS") or [])
    configs = dict(provider.get("OPENAI_API_CONFIGS") or {})
    if args.gemma_provider not in urls:
        urls.append(args.gemma_provider)
        keys.append("EMPTY")
        provider = request_json(
            args.base_url,
            "/openai/config/update",
            token=token,
            payload={
                "ENABLE_OPENAI_API": provider.get("ENABLE_OPENAI_API", True),
                "OPENAI_API_BASE_URLS": urls,
                "OPENAI_API_KEYS": keys,
                "OPENAI_API_CONFIGS": configs,
            },
        )

    imported = request_json(
        args.base_url,
        "/api/v1/models/import",
        token=token,
        payload={"models": models},
    )
    print(
        json.dumps(
            {
                "provider_count": len(provider.get("OPENAI_API_BASE_URLS") or urls),
                "workspace_models": len(models),
                "imported": bool(imported),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
