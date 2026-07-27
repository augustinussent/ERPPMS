#!/usr/bin/env bash
set -euo pipefail
: "${BENCH_PATH:?Set BENCH_PATH}"
: "${SITE:?Set SITE to a disposable upgrade-rehearsal site}"
: "${V090_SOURCE:?Set V090_SOURCE to extracted v0.9.0 source}"
CURRENT_SOURCE=${CURRENT_SOURCE:-${GITHUB_WORKSPACE:-$(pwd)}}
EVIDENCE_DIR=${VALIDATION_EVIDENCE_DIR:-$CURRENT_SOURCE/validation-evidence}
mkdir -p "$EVIDENCE_DIR"
EVIDENCE_FILE="$EVIDENCE_DIR/upgrade-$(date -u +%Y%m%dT%H%M%SZ).log"
[[ "$SITE" == *rehearsal* || "$SITE" == *upgrade* ]] || { echo "SITE must visibly be disposable"; exit 2; }
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  cd "$BENCH_PATH"
  rm -rf apps/hotel_pms
  ln -s "$V090_SOURCE" apps/hotel_pms
  ./env/bin/pip install -e apps/hotel_pms
  if ! bench --site "$SITE" list-apps | grep -qx hotel_pms; then
    bench --site "$SITE" install-app hotel_pms
  fi
  bench --site "$SITE" migrate
  bench --site "$SITE" execute hotel_pms.production_gate.restore_smoke_check 2>/dev/null || true
  rm apps/hotel_pms
  ln -s "$CURRENT_SOURCE" apps/hotel_pms
  ./env/bin/pip install -e apps/hotel_pms
  bench --site "$SITE" migrate
  bench --site "$SITE" run-tests --app hotel_pms
  bench --site "$SITE" execute hotel_pms.production_gate.restore_smoke_check
} 2>&1 | tee "$EVIDENCE_FILE"
COMPLETED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sha256sum "$EVIDENCE_FILE" > "$EVIDENCE_FILE.sha256"
if [[ "${RECORD_REHEARSAL:-0}" == "1" ]]; then
  CONTROL_SITE=${CONTROL_SITE:-$SITE} RUN_TYPE="Upgrade" ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-Staging} STATUS=Passed \
    STARTED_AT="$STARTED_AT" COMPLETED_AT="$COMPLETED_AT" EVIDENCE_PATH="$EVIDENCE_FILE" SOURCE_VERSION="0.9.0" \
    RESULT_SUMMARY="Upgrade from v0.9.0 to the installed release passed migrate, app tests, and restore smoke checks." \
    BENCH_PATH="$BENCH_PATH" "$CURRENT_SOURCE/ci/record_rehearsal.sh"
fi
