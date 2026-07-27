#!/usr/bin/env bash
set -euo pipefail
: "${CONFIRM_ISOLATED_RESTORE:?Set CONFIRM_ISOLATED_RESTORE=YES}"
[[ "$CONFIRM_ISOLATED_RESTORE" == "YES" ]] || { echo "Refusing non-confirmed restore drill"; exit 2; }
: "${BENCH_PATH:?}" "${RESTORE_SITE:?}" "${DB_ROOT_PASSWORD:?}" "${BACKUP_SQL:?}"
[[ "$RESTORE_SITE" == *restore* || "$RESTORE_SITE" == *drill* ]] || { echo "RESTORE_SITE must visibly be an isolated drill site"; exit 2; }
APP_SOURCE=${GITHUB_WORKSPACE:-$(pwd)}
EVIDENCE_DIR=${VALIDATION_EVIDENCE_DIR:-$APP_SOURCE/validation-evidence}
mkdir -p "$EVIDENCE_DIR"
EVIDENCE_FILE="$EVIDENCE_DIR/restore-$(date -u +%Y%m%dT%H%M%SZ).log"
START_EPOCH=$(date +%s)
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  cd "$BENCH_PATH"
  bench drop-site "$RESTORE_SITE" --force --no-backup 2>/dev/null || true
  bench new-site "$RESTORE_SITE" --mariadb-root-password "$DB_ROOT_PASSWORD" --admin-password "${RESTORE_ADMIN_PASSWORD:-restore-drill-only}"
  ARGS=()
  [[ -n "${PUBLIC_FILES:-}" ]] && ARGS+=(--with-public-files "$PUBLIC_FILES")
  [[ -n "${PRIVATE_FILES:-}" ]] && ARGS+=(--with-private-files "$PRIVATE_FILES")
  bench --site "$RESTORE_SITE" restore "$BACKUP_SQL" "${ARGS[@]}"
  bench --site "$RESTORE_SITE" migrate
  bench --site "$RESTORE_SITE" execute hotel_pms.production_gate.restore_smoke_check
  bench --site "$RESTORE_SITE" backup --with-files
} 2>&1 | tee "$EVIDENCE_FILE"
END_EPOCH=$(date +%s)
COMPLETED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RTO_MINUTES=$(python - <<PY
print(round(($END_EPOCH-$START_EPOCH)/60,2))
PY
)
sha256sum "$EVIDENCE_FILE" > "$EVIDENCE_FILE.sha256"
if [[ "${RECORD_REHEARSAL:-0}" == "1" ]]; then
  : "${CONTROL_SITE:?Set CONTROL_SITE to the non-disposable site that stores gate evidence}"
  RUN_TYPE="Restore" ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-Staging} STATUS=Passed \
    STARTED_AT="$STARTED_AT" COMPLETED_AT="$COMPLETED_AT" EVIDENCE_PATH="$EVIDENCE_FILE" MEASURED_RTO_MINUTES="$RTO_MINUTES" \
    RESULT_SUMMARY="Isolated database and file restore passed smoke checks in ${RTO_MINUTES} minutes." \
    BENCH_PATH="$BENCH_PATH" "$APP_SOURCE/ci/record_rehearsal.sh"
fi
