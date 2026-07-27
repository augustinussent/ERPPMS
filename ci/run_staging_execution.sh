#!/usr/bin/env bash
set -euo pipefail

: "${BENCH_ROOT:?Set BENCH_ROOT to the Frappe bench directory}"
: "${SITE:?Set SITE to the staging site name}"
: "${GATE_RUN:?Set GATE_RUN to the Hotel Production Gate Run name}"

EVIDENCE_DIR="${EVIDENCE_DIR:-${BENCH_ROOT}/sites/${SITE}/private/hotel-pms-evidence/${GATE_RUN}}"
mkdir -p "$EVIDENCE_DIR"
cd "$BENCH_ROOT"

run_execute() {
  local method="$1"
  local output="$2"
  bench --site "$SITE" execute "$method" \
    --kwargs "{\"gate_run\":\"${GATE_RUN}\"}" | tee "$EVIDENCE_DIR/$output"
}

{
  printf 'site=%s\n' "$SITE"
  printf 'gate_run=%s\n' "$GATE_RUN"
  printf 'bench_root=%s\n' "$BENCH_ROOT"
  printf 'started_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'git_commit=%s\n' "$(git -C apps/hotel_pms rev-parse HEAD 2>/dev/null || true)"
  printf 'python=%s\n' "$(python --version 2>&1)"
  printf 'node=%s\n' "$(node --version 2>/dev/null || true)"
} > "$EVIDENCE_DIR/00-environment.txt"

{
  bench --site "$SITE" backup --with-files
  bench --site "$SITE" migrate
  bench build --app hotel_pms
  bench --site "$SITE" clear-cache
} 2>&1 | tee "$EVIDENCE_DIR/10-migrate.log"

run_execute hotel_pms.staging_execution.capture_staging_preflight 20-preflight.json
run_execute hotel_pms.staging_execution.run_smoke_suite 30-smoke.json
run_execute hotel_pms.staging_execution.capture_reconciliation_snapshot 40-reconciliation.json
run_execute hotel_pms.staging_execution.build_cutover_bundle 50-cutover-bundle.json
bench --site "$SITE" execute hotel_pms.production_gate.execute_automated_checks --kwargs "{\"run_name\":\"${GATE_RUN}\"}" | tee "$EVIDENCE_DIR/60-gate-checks.json"

python apps/hotel_pms/ci/build_evidence_manifest.py "$EVIDENCE_DIR"
python apps/hotel_pms/ci/verify_staging_bundle.py "$EVIDENCE_DIR"
printf 'Evidence bundle: %s\n' "$EVIDENCE_DIR"
