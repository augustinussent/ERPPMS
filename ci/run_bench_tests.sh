#!/usr/bin/env bash
set -euo pipefail
: "${BENCH_PATH:?Set BENCH_PATH to a prepared Frappe v16 bench}"
: "${SITE:?Set SITE to the disposable integration-test site}"
APP_SOURCE=${GITHUB_WORKSPACE:-$(pwd)}
EVIDENCE_DIR=${VALIDATION_EVIDENCE_DIR:-$APP_SOURCE/validation-evidence}
mkdir -p "$EVIDENCE_DIR"
EVIDENCE_FILE="$EVIDENCE_DIR/blank-install-$(date -u +%Y%m%dT%H%M%SZ).log"
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  cd "$BENCH_PATH"
  rm -rf apps/hotel_pms
  ln -s "$APP_SOURCE" apps/hotel_pms
  ./env/bin/pip install -e apps/hotel_pms
  if ! bench --site "$SITE" list-apps | grep -qx hotel_pms; then
    bench --site "$SITE" install-app hotel_pms
  fi
  bench --site "$SITE" migrate
  bench --site "$SITE" run-tests --app hotel_pms
  bench --site "$SITE" execute hotel_pms.platform.worker_heartbeat
  bench --site "$SITE" execute hotel_pms.platform.capture_health_snapshot
  bench --site "$SITE" backup --with-files
  bench --site "$SITE" execute hotel_pms.platform.verify_latest_backup
  bench --site "$SITE" execute hotel_pms.production_gate.restore_smoke_check
} 2>&1 | tee "$EVIDENCE_FILE"
COMPLETED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sha256sum "$EVIDENCE_FILE" > "$EVIDENCE_FILE.sha256"
if [[ "${RECORD_REHEARSAL:-0}" == "1" ]]; then
  CONTROL_SITE=${CONTROL_SITE:-$SITE} RUN_TYPE="Blank Install" ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-Staging} STATUS=Passed \
    STARTED_AT="$STARTED_AT" COMPLETED_AT="$COMPLETED_AT" EVIDENCE_PATH="$EVIDENCE_FILE" \
    RESULT_SUMMARY="Blank install, migrate, app tests, backup verification, and restore smoke check passed." \
    BENCH_PATH="$BENCH_PATH" "$APP_SOURCE/ci/record_rehearsal.sh"
fi
