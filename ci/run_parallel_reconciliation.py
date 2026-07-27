#!/usr/bin/env python3
from argparse import ArgumentParser
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hotel_pms.production_validation_rules import BASE_REQUIRED_PARALLEL_METRICS, classify_parallel_row, summarize_parallel_rows  # noqa: E402


def main():
    parser = ArgumentParser(description="Validate a Hotel PMS parallel-run CSV before uploading it to the Production Gate.")
    parser.add_argument("csv_file")
    parser.add_argument("--default-tolerance", type=float, default=0)
    parser.add_argument("--output")
    args = parser.parse_args()
    rows = []
    input_errors = []
    required_columns = {"metric_code", "department", "business_date", "unit", "legacy_value", "pms_value", "tolerance"}
    with Path(args.csv_file).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = sorted(required_columns - set(reader.fieldnames or []))
        if missing_columns:
            input_errors.append(f"Missing columns: {missing_columns}")
        for index, row in enumerate(reader, start=2):
            for field in required_columns:
                if str(row.get(field) or "").strip() == "":
                    input_errors.append(f"line {index}: {field} is required")
            try:
                tolerance = float(row.get("tolerance"))
                legacy = float(row.get("legacy_value"))
                pms = float(row.get("pms_value"))
            except (TypeError, ValueError):
                input_errors.append(f"line {index}: legacy_value, pms_value and tolerance must be numeric")
                continue
            status, variance = classify_parallel_row(legacy, pms, tolerance)
            rows.append({**row, "variance": float(variance), "tolerance": tolerance, "status": status, "csv_line": index})
    summary = summarize_parallel_rows(rows)
    missing=sorted(BASE_REQUIRED_PARALLEL_METRICS-{str(row.get("metric_code") or "").strip().upper() for row in rows})
    if missing or input_errors: summary["status"]="Failed"
    result = {"summary": summary, "missing_mandatory_metrics": missing, "input_errors": input_errors, "rows": rows}
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(text + "\n")
    print(text)
    raise SystemExit(0 if summary["status"] == "Passed" else 2)


if __name__ == "__main__":
    main()
