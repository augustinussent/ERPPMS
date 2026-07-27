#!/usr/bin/env bash
set -euo pipefail
: "${CONFIRM_ISOLATED_ROLLBACK:?Set CONFIRM_ISOLATED_ROLLBACK=YES}"
[[ "$CONFIRM_ISOLATED_ROLLBACK" == "YES" ]] || { echo "Refusing non-confirmed rollback drill"; exit 2; }
: "${BENCH_PATH:?}" "${ROLLBACK_SITE:?}" "${DB_ROOT_PASSWORD:?}" "${PRE_UPGRADE_SQL:?}" "${PREVIOUS_SOURCE:?}"
[[ "$ROLLBACK_SITE" == *rollback* || "$ROLLBACK_SITE" == *drill* ]] || { echo "ROLLBACK_SITE must visibly be isolated"; exit 2; }
CURRENT_SOURCE=${CURRENT_SOURCE:-${GITHUB_WORKSPACE:-$(pwd)}}
EVIDENCE_DIR=${VALIDATION_EVIDENCE_DIR:-$CURRENT_SOURCE/validation-evidence}
mkdir -p "$EVIDENCE_DIR"
EVIDENCE_FILE="$EVIDENCE_DIR/rollback-$(date -u +%Y%m%dT%H%M%SZ).log"
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
restore_current_source() {
  cd "$BENCH_PATH"
  rm -rf apps/hotel_pms
  ln -s "$CURRENT_SOURCE" apps/hotel_pms
  ./env/bin/pip install -e apps/hotel_pms >/dev/null 2>&1 || true
}
trap restore_current_source EXIT
{
  cd "$BENCH_PATH"
  bench drop-site "$ROLLBACK_SITE" --force --no-backup 2>/dev/null || true
  rm -rf apps/hotel_pms
  ln -s "$PREVIOUS_SOURCE" apps/hotel_pms
  ./env/bin/pip install -e apps/hotel_pms
  bench new-site "$ROLLBACK_SITE" --mariadb-root-password "$DB_ROOT_PASSWORD" --admin-password "${ROLLBACK_ADMIN_PASSWORD:-rollback-drill-only}"
  ARGS=()
  [[ -n "${PUBLIC_FILES:-}" ]] && ARGS+=(--with-public-files "$PUBLIC_FILES")
  [[ -n "${PRIVATE_FILES:-}" ]] && ARGS+=(--with-private-files "$PRIVATE_FILES")
  bench --site "$ROLLBACK_SITE" restore "$PRE_UPGRADE_SQL" "${ARGS[@]}"
  bench --site "$ROLLBACK_SITE" migrate
  bench --site "$ROLLBACK_SITE" execute hotel_pms.production_gate.restore_smoke_check
} 2>&1 | tee "$EVIDENCE_FILE"
COMPLETED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sha256sum "$EVIDENCE_FILE" > "$EVIDENCE_FILE.sha256"
if [[ "${RECORD_REHEARSAL:-0}" == "1" ]]; then
  : "${CONTROL_SITE:?Set CONTROL_SITE to the site that stores gate evidence}"
  RUN_TYPE="Rollback" ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-Staging} STATUS=Passed \
    STARTED_AT="$STARTED_AT" COMPLETED_AT="$COMPLETED_AT" EVIDENCE_PATH="$EVIDENCE_FILE" SOURCE_VERSION=${SOURCE_VERSION:-0.9.0} \
    RESULT_SUMMARY="Pre-upgrade database and files were restored with the previous application source and passed smoke checks." \
    BENCH_PATH="$BENCH_PATH" "$CURRENT_SOURCE/ci/record_rehearsal.sh"
fi
