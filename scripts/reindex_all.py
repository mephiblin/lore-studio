#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request

API = os.getenv("LORE_STUDIO_API", "http://127.0.0.1:18000/api/v1").rstrip("/")


def request(method: str, path: str, payload: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.loads(response.read())


def main() -> int:
    projects = request("GET", "/projects")
    total_chunks = 0
    for project in projects:
        job = request("POST", "/index/jobs", {"project_id": project["id"]})
        result = request("POST", f"/index/jobs/{job['id']}/run")
        chunks = int(result.get("stats_json", {}).get("chunks", 0))
        total_chunks += chunks
        print(f"{project['name']}: {result['status']} ({chunks} chunks)")
    print(f"총 {len(projects)}개 프로젝트, {total_chunks}개 청크")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
