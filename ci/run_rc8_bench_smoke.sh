#!/usr/bin/env bash
set -euo pipefail
: "${SITE:?SITE is required}"
BENCH_ROOT="${BENCH_ROOT:-$(pwd)}"
cd "$BENCH_ROOT"
bench --site "$SITE" migrate
bench --site "$SITE" execute hotel_pms.distribution_ci.run_rc8_bench_smoke
bench --site "$SITE" run-tests --app hotel_pms --module hotel_pms.tests.test_distribution_rc8_rules
