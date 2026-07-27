#!/usr/bin/env bash
set -euo pipefail
: "${BENCH_PATH:?Set BENCH_PATH}"
: "${SITE:?Set SITE to a disposable upgrade-rehearsal site}"
: "${V090_SOURCE:?Set V090_SOURCE to extracted v0.9.0 source}"
CURRENT_SOURCE=${CURRENT_SOURCE:-${GITHUB_WORKSPACE:-$(pwd)}}
[[ "$SITE" == *rehearsal* || "$SITE" == *upgrade* ]] || { echo "SITE must visibly be disposable"; exit 2; }
cd "$BENCH_PATH"
rm -rf apps/hotel_pms
ln -s "$V090_SOURCE" apps/hotel_pms
./env/bin/pip install -e apps/hotel_pms
bench --site "$SITE" install-app hotel_pms 2>/dev/null || true
bench --site "$SITE" migrate
bench --site "$SITE" execute hotel_pms.production_gate.restore_smoke_check 2>/dev/null || true
rm apps/hotel_pms
ln -s "$CURRENT_SOURCE" apps/hotel_pms
./env/bin/pip install -e apps/hotel_pms
bench --site "$SITE" migrate
bench --site "$SITE" run-tests --app hotel_pms
bench --site "$SITE" execute hotel_pms.production_gate.restore_smoke_check
