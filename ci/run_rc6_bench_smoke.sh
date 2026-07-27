#!/usr/bin/env bash
set -euo pipefail
: "${BENCH_PATH:?Set BENCH_PATH to a prepared Frappe v16 bench}"
: "${SITE:?Set SITE to a disposable integration-test site}"
: "${RC6_TEST_PROPERTY:?Set RC6_TEST_PROPERTY to an existing Hotel Property on the disposable site}"
APP_SOURCE=${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd)}
EVIDENCE_DIR=${VALIDATION_EVIDENCE_DIR:-$APP_SOURCE/validation-evidence}
mkdir -p "$EVIDENCE_DIR"
EVIDENCE_FILE="$EVIDENCE_DIR/rc6-intelligence-smoke-$(date -u +%Y%m%dT%H%M%SZ).log"
{
  cd "$BENCH_PATH"
  rm -rf apps/hotel_pms
  ln -s "$APP_SOURCE" apps/hotel_pms
  ./env/bin/pip install -e apps/hotel_pms
  if ! bench --site "$SITE" list-apps | grep -qx hotel_pms; then
    bench --site "$SITE" install-app hotel_pms
  fi
  bench --site "$SITE" migrate
  bench --site "$SITE" run-tests --module hotel_pms.tests.test_intelligence_rc6_integration
  bench --site "$SITE" execute hotel_pms.intelligence_ci.run_rc6_smoke --kwargs "{\"property_name\":\"$RC6_TEST_PROPERTY\"}"
  if [[ -n "${GATE_RUN:-}" ]]; then
    bench --site "$SITE" execute hotel_pms.staging_execution.run_smoke_suite --kwargs "{\"gate_run\":\"$GATE_RUN\"}"
  else
    echo "Gate run not supplied; core RC6 smoke completed without Production Gate attachment."
  fi
} 2>&1 | tee "$EVIDENCE_FILE"
sha256sum "$EVIDENCE_FILE" > "$EVIDENCE_FILE.sha256"
