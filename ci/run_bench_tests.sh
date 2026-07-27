#!/usr/bin/env bash
set -euo pipefail
: "${BENCH_PATH:?Set BENCH_PATH to a prepared Frappe v16 bench}"
: "${SITE:?Set SITE to the disposable integration-test site}"
APP_SOURCE=${GITHUB_WORKSPACE:-$(pwd)}
cd "$BENCH_PATH"
rm -rf apps/hotel_pms
ln -s "$APP_SOURCE" apps/hotel_pms
./env/bin/pip install -e apps/hotel_pms
bench --site "$SITE" install-app hotel_pms 2>/dev/null || true
bench --site "$SITE" migrate
bench --site "$SITE" run-tests --app hotel_pms
bench --site "$SITE" execute hotel_pms.platform.worker_heartbeat
bench --site "$SITE" execute hotel_pms.platform.capture_health_snapshot
bench --site "$SITE" backup --with-files
bench --site "$SITE" execute hotel_pms.platform.verify_latest_backup
bench --site "$SITE" execute hotel_pms.production_gate.restore_smoke_check
