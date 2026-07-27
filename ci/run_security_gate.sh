#!/usr/bin/env bash
set -euo pipefail
ROOT=${1:-.}
OUT=${SECURITY_EVIDENCE_DIR:-security-evidence}
mkdir -p "$OUT"
python - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1])/'hotel_pms'; out=Path(sys.argv[2])/'secret-grep.txt'
pattern=re.compile(r'(api[_-]?secret|password|private[_-]?key)\s*=\s*["\'][^"\']{8,}',re.I)
hits=[]
for path in root.rglob('*.py'):
    for no,line in enumerate(path.read_text(errors='ignore').splitlines(),1):
        if pattern.search(line): hits.append(f'{path}:{no}:{line.strip()}')
out.write_text('\n'.join(hits))
if hits:
    print('\n'.join(hits)); raise SystemExit(1)
PY
python -m pip_audit --local --format json --output "$OUT/pip-audit.json"
command -v trivy >/dev/null || { echo "trivy is required"; exit 2; }
trivy fs --exit-code 1 --severity HIGH,CRITICAL --format json --output "$OUT/trivy-fs.json" "$ROOT"
printf '{"completed":true,"note":"Automated scans completed. A manual penetration test is still required."}\n' > "$OUT/security-gate-summary.json"
