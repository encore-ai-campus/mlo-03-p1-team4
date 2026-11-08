"""#19 파일럿 report.json과 분석 CSV의 수량을 오프라인 대조한다."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def inspect(report, events_path, daily_path):
    with events_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with daily_path.open(encoding="utf-8-sig", newline="") as stream:
        daily = list(csv.DictReader(stream))
    unique_events = {row["event_id"] for row in rows}
    sessions = {row["session_id"] for row in rows if row["session_id"]}
    dates = Counter(row["occurred_at(KST)"][:10] for row in rows)
    daily_synthetic = sum(
        int(row["count"]) for row in daily if row["is_synthetic"].lower() == "true"
    )
    checks = {
        "event_ids_match_report": len(unique_events) == report["events"],
        "sessions_match_report": len(sessions) == report["sessions"],
        "synthetic_daily_matches_csv_rows": daily_synthetic == len(rows),
        "period_matches_report": all(
            report["period_start"] <= day <= report["period_end"] for day in dates
        ),
        "synthetic_only_csv": all(row["is_synthetic"] == "True" for row in rows),
    }
    return {
        "checks": checks,
        "report_events": report["events"],
        "csv_event_ids": len(unique_events),
        "csv_rows": len(rows),
        "daily_synthetic_count": daily_synthetic,
        "csv_sessions": len(sessions),
        "daily_event_types": dict(
            sorted(
                {
                    event_type: sum(
                        int(row["count"])
                        for row in daily
                        if row["event_type"] == event_type
                        and row["is_synthetic"].lower() == "true"
                    )
                    for event_type in {
                        row["event_type"]
                        for row in daily
                        if row["is_synthetic"].lower() == "true"
                    }
                }.items()
            )
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="#19 파일럿 보고서·CSV 수량 대조")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--events-csv", type=Path, required=True)
    parser.add_argument("--daily-csv", type=Path, required=True)
    args = parser.parse_args(argv)
    result = inspect(
        json.loads(args.report.read_text(encoding="utf-8")), args.events_csv, args.daily_csv
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
