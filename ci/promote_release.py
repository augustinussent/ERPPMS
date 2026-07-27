#!/usr/bin/env python3
from argparse import ArgumentParser
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hotel_pms.production_validation_rules import source_fingerprint  # noqa: E402


def main():
    parser = ArgumentParser(description="Promote an approved RC without changing executable source bytes.")
    parser.add_argument("--source-dir", default=str(ROOT))
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--target-version", default="1.0.0")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(args.source_dir).resolve()
    before = source_fingerprint(root)
    if before != args.expected_fingerprint:
        raise SystemExit(f"fingerprint mismatch before promotion: {before}")
    version_file = root / "hotel_pms/__init__.py"
    original = version_file.read_text()
    promoted, count = re.subn(r'__version__\s*=\s*["\'][^"\']+["\']', f'__version__ = "{args.target_version}"', original, count=1)
    if count != 1:
        raise SystemExit("could not find exactly one version assignment")
    if args.apply:
        version_file.write_text(promoted)
        after = source_fingerprint(root)
        if after != before:
            version_file.write_text(original)
            raise SystemExit("normalized source fingerprint changed during promotion")
    print({"source_fingerprint": before, "target_version": args.target_version, "applied": args.apply})


if __name__ == "__main__":
    main()
