#!/usr/bin/env bash
set -euo pipefail
: "${BENCH_PATH:?Set BENCH_PATH}"
: "${CONTROL_SITE:?Set CONTROL_SITE to the site that stores Production Gate evidence}"
: "${RUN_TYPE:?Set RUN_TYPE}"
: "${STARTED_AT:?Set STARTED_AT as an ISO timestamp}"
: "${COMPLETED_AT:?Set COMPLETED_AT as an ISO timestamp}"
STATUS=${STATUS:-Passed}
ENVIRONMENT_NAME=${ENVIRONMENT_NAME:-Staging}
EVIDENCE_PATH=${EVIDENCE_PATH:-}
EVIDENCE_SHA256=${EVIDENCE_SHA256:-}
if [[ -n "$EVIDENCE_PATH" ]]; then
  [[ -f "$EVIDENCE_PATH" ]] || { echo "Evidence file not found: $EVIDENCE_PATH"; exit 2; }
  EVIDENCE_SHA256=$(sha256sum "$EVIDENCE_PATH" | awk '{print $1}')
fi
KWARGS=$(python - <<'PY'
import json,os
payload={
 "run_type":os.environ["RUN_TYPE"],
 "environment_name":os.environ.get("ENVIRONMENT_NAME","Staging"),
 "status":os.environ.get("STATUS","Passed"),
 "started_at":os.environ["STARTED_AT"],
 "completed_at":os.environ["COMPLETED_AT"],
 "property":os.environ.get("PROPERTY") or None,
 "source_version":os.environ.get("SOURCE_VERSION") or None,
 "result_summary":os.environ.get("RESULT_SUMMARY") or None,
 "evidence_sha256":os.environ.get("EVIDENCE_SHA256") or None,
 "measured_rto_minutes":os.environ.get("MEASURED_RTO_MINUTES") or None,
 "metadata_json":{"evidence_path":os.environ.get("EVIDENCE_PATH") or None,"ci_run":os.environ.get("CI_RUN_URL") or None},
}
print(json.dumps(payload,separators=(",",":")))
PY
)
cd "$BENCH_PATH"
bench --site "$CONTROL_SITE" execute hotel_pms.production_validation.record_rehearsal --kwargs "$KWARGS"
