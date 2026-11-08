"""#19/#75: KST 일별 이벤트 집계와 파일럿 CSV 내보내기."""

import argparse
import csv
import json
import os
import sys
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.clock import get_today  # noqa: E402 -- backend 경로를 먼저 추가한다.
from app.core.config import get_settings  # noqa: E402 -- backend 경로를 먼저 추가한다.
from db.aggregate.event_daily import aggregate_day, export_csv  # noqa: E402 -- DB 집계기를 재사용한다.

KST = ZoneInfo("Asia/Seoul")
EVENT_FIELDS = (
    "event_id",
    "occurred_at(KST)",
    "event_name",
    "session_id",
    "user_id",
    "anonymous_id",
    "session_sequence",
    "product_id",
    "page_type",
    "properties(JSON)",
    "is_synthetic",
)


@contextmanager
def run_lock(path):
    """api1에서 집계·CSV 실행이 겹치지 않게 파일 잠금을 유지한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("같은 경로의 집계가 이미 실행 중입니다.") from error
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("같은 경로의 집계가 이미 실행 중입니다.") from error
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def atomic_csv(path, fields, rows):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def export_event_rows(events, start_utc, end_utc):
    query = {
        "occurred_at": {"$gte": start_utc, "$lt": end_utc},
        "is_synthetic": True,
    }
    projection = {
        "_id": 0,
        "event_id": 1,
        "occurred_at": 1,
        "event_name": 1,
        "user.session_id": 1,
        "user.user_id": 1,
        "user.anonymous_id": 1,
        "user.session_sequence": 1,
        "products.product_id": 1,
        "page.page_type": 1,
        "properties": 1,
        "is_synthetic": 1,
    }
    rows = []
    for event in events.find(query, projection).sort([("occurred_at", 1), ("event_id", 1)]):
        product_ids = sorted({item.get("product_id", "") for item in event.get("products") or [{}]})
        for product_id in product_ids:
            rows.append(
                {
                    "event_id": event["event_id"],
                    "occurred_at(KST)": event["occurred_at"].astimezone(KST).isoformat(),
                    "event_name": event["event_name"],
                    "session_id": event["user"].get("session_id", ""),
                    "user_id": event["user"].get("user_id") or "",
                    "anonymous_id": event["user"].get("anonymous_id", ""),
                    "session_sequence": event["user"].get("session_sequence", ""),
                    "product_id": product_id,
                    "page_type": event.get("page", {}).get("page_type", ""),
                    "properties(JSON)": json.dumps(
                        event.get("properties", {}), ensure_ascii=False, sort_keys=True
                    ),
                    "is_synthetic": event["is_synthetic"],
                }
            )
    return rows


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="#19/#75 일별 이벤트 집계와 분석 CSV")
    parser.add_argument("--base-date", type=date.fromisoformat, default=get_today())
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output-root", type=Path, default=ROOT / "logs" / "analytics")
    return parser.parse_args(argv)


def period_bounds(base_date, days):
    start_date = base_date - timedelta(days=days)
    start_utc = datetime.combine(start_date, time.min, tzinfo=KST).astimezone(UTC)
    end_utc = datetime.combine(base_date, time.min, tzinfo=KST).astimezone(UTC)
    return start_date, start_utc, end_utc


def main(argv=None):
    args = parse_args(argv)
    if args.days < 1 or args.base_date > get_today():
        print("--days는 1 이상이고 --base-date는 오늘 또는 과거여야 합니다.", file=sys.stderr)
        return 2

    start_date, start_utc, end_utc = period_bounds(args.base_date, args.days)
    settings = get_settings()
    if settings.mongo_url is None:
        print("MONGO_URL 설정이 필요합니다.", file=sys.stderr)
        return 2

    args.output_root.mkdir(parents=True, exist_ok=True)
    prefix = f"events-{start_date.isoformat()}-{args.base_date.isoformat()}"
    client = MongoClient(
        settings.mongo_url.get_secret_value(),
        tz_aware=True,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=120000,
    )
    try:
        client.admin.command("ping")
        database = client[settings.mongo_db]
        events = database["events"]
        daily = database["event_daily"]
        indexes = daily.index_information()
        if not any(
            tuple(index.get("key", []))
            == (("date", 1), ("event_type", 1), ("venue_id", 1), ("is_synthetic", 1))
            and index.get("unique")
            for index in indexes.values()
        ):
            raise RuntimeError("event_daily 복합 UNIQUE 인덱스를 먼저 적용하세요.")

        with run_lock(args.output_root / ".event_daily.lock"):
            days = [start_date + timedelta(days=offset) for offset in range(args.days)]
            results = [aggregate_day(database, day) for day in days]
            rows = export_event_rows(events, start_utc, end_utc)
            atomic_csv(args.output_root / f"{prefix}-synthetic.csv", EVENT_FIELDS, rows)
            daily_path = args.output_root / f"{prefix}-event-daily.csv"
            temporary = daily_path.with_suffix(".csv.tmp")
            daily_count = export_csv(database, days, temporary)
            temporary.replace(daily_path)

        print(
            json.dumps(
                {
                    "start_date": start_date.isoformat(),
                    "end_date_exclusive": args.base_date.isoformat(),
                    "daily_groups": daily_count,
                    "days_rebuilt": len(results),
                    "synthetic_csv_rows": len(rows),
                    "output_root": str(args.output_root.resolve()),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
