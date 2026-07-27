#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(directory: Path) -> dict:
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name in {"evidence-manifest.json", "evidence-manifest.sha256"}:
            continue
        files.append(
            {
                "path": path.relative_to(directory).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {"schema": "hotel-pms-staging-evidence-v1", "files": files}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    manifest = build_manifest(root)
    output = root / "evidence-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha256_file(output)
    (root / "evidence-manifest.sha256").write_text(f"{digest}  evidence-manifest.json\n", encoding="utf-8")
    print(json.dumps({"manifest": str(output), "sha256": digest, "files": len(manifest["files"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
