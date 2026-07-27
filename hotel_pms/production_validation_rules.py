from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re


def canonical_source_hash(entries):
    """Hash ordered ``(relative_path, bytes)`` entries deterministically."""
    digest = hashlib.sha256()
    for path, content in sorted(entries, key=lambda item: item[0]):
        path_bytes = str(path).replace('\\', '/').encode('utf-8')
        data = bytes(content)
        digest.update(len(path_bytes).to_bytes(8, 'big'))
        digest.update(path_bytes)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()


SOURCE_EXTENSIONS = {".py", ".json", ".js", ".html", ".css", ".sh", ".yml", ".yaml", ".toml"}
SOURCE_DIRECTORIES = ("hotel_pms", "ci", "deploy", ".github/workflows")
TOP_LEVEL_SOURCE_FILES = ("pyproject.toml", "patches.txt")
VERSION_FILE = "hotel_pms/__init__.py"
VERSION_PATTERN = re.compile(rb'__version__\s*=\s*["\'][^"\']+["\']')
BASE_REQUIRED_PARALLEL_METRICS = {"RESERVATIONS","ROOM_NIGHTS","ROOM_REVENUE","TAX_TOTAL","PAYMENTS","DEPOSITS","REFUNDS","AR_OUTSTANDING","CASHIER_CASH"}


def normalized_source_bytes(relative_path, content):
    if str(relative_path).replace("\\", "/") == VERSION_FILE:
        return VERSION_PATTERN.sub(b'__version__ = "<PROMOTION_VERSION>"', bytes(content))
    return bytes(content)


def iter_source_entries(root):
    root = Path(root)
    seen = set()
    for directory in SOURCE_DIRECTORIES:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            if any(part in {"__pycache__", "node_modules", ".git"} for part in path.parts):
                continue
            relative = path.relative_to(root).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            yield relative, normalized_source_bytes(relative, path.read_bytes())
    for filename in TOP_LEVEL_SOURCE_FILES:
        path = root / filename
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative not in seen:
                yield relative, path.read_bytes()


def source_fingerprint(root):
    return canonical_source_hash(iter_source_entries(root))

def numeric_variance(left, right):
    try:
        return abs(Decimal(str(left or 0)) - Decimal(str(right or 0)))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('Infinity')


def classify_parallel_row(legacy_value, pms_value, tolerance, warning_multiplier=0.5):
    tolerance = Decimal(str(tolerance or 0))
    variance = numeric_variance(legacy_value, pms_value)
    if variance <= tolerance:
        return 'Passed', variance
    warning_limit = tolerance * (Decimal('1') + Decimal(str(warning_multiplier or 0)))
    if tolerance > 0 and variance <= warning_limit:
        return 'Warning', variance
    return 'Failed', variance


def summarize_parallel_rows(rows):
    result = {'total': 0, 'passed': 0, 'warnings': 0, 'failed': 0}
    for row in rows:
        result['total'] += 1
        status = row.get('status')
        if status == 'Passed':
            result['passed'] += 1
        elif status == 'Warning':
            result['warnings'] += 1
        else:
            result['failed'] += 1
    result['status'] = 'Failed' if result['failed'] else ('Warning' if result['warnings'] else 'Passed')
    return result


def rehearsal_matches(record, release_version, source_fingerprint, image_digest):
    if not record or record.get('status') != 'Passed':
        return False
    if record.get('release_version') != release_version:
        return False
    if source_fingerprint and record.get('source_fingerprint') != source_fingerprint:
        return False
    if image_digest and record.get('image_digest') != image_digest:
        return False
    return True


def promotion_blockers(gate, manifest, rehearsal_statuses, parallel_status):
    blockers = []
    if not gate or gate.get('go_live_decision') != 'Go' or gate.get('status') != 'Approved':
        blockers.append('Production Gate must be Approved with a Go decision.')
    if not manifest or manifest.get('status') != 'Frozen':
        blockers.append('Release manifest must be Frozen.')
    for run_type, passed in rehearsal_statuses.items():
        if not passed:
            blockers.append(f'{run_type} rehearsal is missing or does not match the frozen release.')
    if parallel_status != 'Passed':
        blockers.append('Parallel-run reconciliation must pass without warnings or failures.')
    return blockers
