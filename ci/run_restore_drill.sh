#!/usr/bin/env bash
set -euo pipefail
: "${CONFIRM_ISOLATED_RESTORE:?Set CONFIRM_ISOLATED_RESTORE=YES}"
[[ "$CONFIRM_ISOLATED_RESTORE" == "YES" ]] || { echo "Refusing non-confirmed restore drill"; exit 2; }
: "${BENCH_PATH:?}" "${RESTORE_SITE:?}" "${DB_ROOT_PASSWORD:?}" "${BACKUP_SQL:?}"
[[ "$RESTORE_SITE" == *restore* || "$RESTORE_SITE" == *drill* ]] || { echo "RESTORE_SITE must visibly be an isolated drill site"; exit 2; }
cd "$BENCH_PATH"
bench drop-site "$RESTORE_SITE" --force --no-backup 2>/dev/null || true
bench new-site "$RESTORE_SITE" --mariadb-root-password "$DB_ROOT_PASSWORD" --admin-password "${RESTORE_ADMIN_PASSWORD:-restore-drill-only}"
ARGS=(--with-public-files "${PUBLIC_FILES:-}" --with-private-files "${PRIVATE_FILES:-}")
bench --site "$RESTORE_SITE" restore "$BACKUP_SQL" "${ARGS[@]}"
bench --site "$RESTORE_SITE" migrate
bench --site "$RESTORE_SITE" execute hotel_pms.production_gate.restore_smoke_check
bench --site "$RESTORE_SITE" backup --with-files
