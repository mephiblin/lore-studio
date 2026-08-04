#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import sys
import urllib.request
from pathlib import Path


def download(repo: str, filename: str, destination: Path) -> None:
    url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    offset = destination.stat().st_size if destination.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    with urllib.request.urlopen(request) as response:
        append = offset > 0 and response.status == 206 and response.headers.get("Content-Range", "").startswith(
            f"bytes {offset}-"
        )
        if offset and not append:
            print(f"서버가 resume을 지원하지 않아 처음부터 다시 받습니다: {destination}")
        with destination.open("ab" if append else "wb") as target:
            while chunk := response.read(8 * 1024 * 1024):
                target.write(chunk)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    if os.getenv("ALLOW_MODEL_DOWNLOAD", "false").lower() != "true":
        print("ALLOW_MODEL_DOWNLOAD=true가 아니므로 다운로드하지 않습니다.", file=sys.stderr)
        return 2
    repo = os.getenv("FALLBACK_MODEL_HF_REPO", "").strip()
    files = [os.getenv("FALLBACK_MODEL_HF_FILE", "").strip(), os.getenv("FALLBACK_MMPROJ_HF_FILE", "").strip()]
    files = [value for value in files if value]
    if not repo or not files:
        print("FALLBACK_MODEL_HF_REPO와 다운로드할 파일을 명시하십시오.", file=sys.stderr)
        return 2
    root = Path(os.getenv("LORE_STUDIO_MODEL_DIR", "/models/lore-studio")) / repo.replace("/", "--")
    for filename in files:
        destination = root / Path(filename).name
        download(repo, filename, destination)
        expected_size = os.getenv("FALLBACK_MODEL_SIZE_BYTES", "")
        if expected_size and destination.stat().st_size != int(expected_size):
            raise RuntimeError(f"파일 크기 불일치: {destination}")
        expected_sha = os.getenv("FALLBACK_MODEL_SHA256", "").lower()
        if expected_sha:
            digest = sha256_file(destination)
            if digest != expected_sha:
                raise RuntimeError(f"SHA256 불일치: {destination}")
        print(f"verified: {destination} ({destination.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
