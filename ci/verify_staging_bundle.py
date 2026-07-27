#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REQUIRED_FILES = {
    "00-environment.txt",
    "10-migrate.log",
    "20-preflight.json",
    "30-smoke.json",
    "40-reconciliation.json",
    "50-cutover-bundle.json",
    "60-gate-checks.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(directory: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = directory / "evidence-manifest.json"
    checksum_path = directory / "evidence-manifest.sha256"
    if not manifest_path.is_file():
        return ["missing evidence-manifest.json"]
    if not checksum_path.is_file():
        errors.append("missing evidence-manifest.sha256")
    else:
        expected = checksum_path.read_text(encoding="utf-8").split()[0]
        actual = sha256_file(manifest_path)
        if expected != actual:
            errors.append("manifest checksum mismatch")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema") != "hotel-pms-staging-evidence-v1":
        errors.append("unsupported evidence schema")
    rows = {row.get("path"): row for row in data.get("files") or []}
    missing = sorted(REQUIRED_FILES - set(rows))
    errors.extend(f"missing required evidence file: {name}" for name in missing)
    for relative, row in rows.items():
        path = directory / relative
        if not path.is_file():
            errors.append(f"manifest file missing: {relative}")
            continue
        if int(row.get("size") or -1) != path.stat().st_size:
            errors.append(f"size mismatch: {relative}")
        if row.get("sha256") != sha256_file(path):
            errors.append(f"checksum mismatch: {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    errors = verify(args.directory.resolve())
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
