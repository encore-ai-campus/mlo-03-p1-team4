"""events → event_daily 일별 집계와 CSV 내보내기 (F-60 후속, 11-07).

실행 (MONGO_URL·MONGO_DB 환경변수, 기본 DB space_rental_analytics):
  python db/aggregate/event_daily.py                     # 어제·오늘(한국 날짜) 다시 집계
  python db/aggregate/event_daily.py --days 30           # 오늘 포함 최근 30일
  python db/aggregate/event_daily.py --date 2026-11-06   # 하루만
  python db/aggregate/event_daily.py --days 30 --csv out/event_daily.csv

정책 (docs/db/events_event_daily_컬렉션_속성정리_v1.md 4·5절에서 미정으로 둔 부분을 여기서 정한다)
- 날짜: occurred_at을 Asia/Seoul 날짜(YYYY-MM-DD)로 바꿔 묶는다.
- 상품: products 배열을 펼쳐 공간마다 한 건. 상품이 없는 이벤트(page_view·search_submit·login·signup)는 venue_id=null.
- 재집계: 대상 날짜의 결과를 원천에서 다시 세어 같은 키 문서를 덮어쓴다(count는 $set, 더하지 않음).
  원천에서 사라진 조합(TTL 만료 등)은 그 날짜를 다시 집계할 때 지운다.
- 개인정보: 날짜·행동·공간 ID·테스트 여부·건수만 남긴다.
- CSV: date,event_type,is_synthetic,count. 공간별 집계의 count를 합치되 실제·합성은 분리한다.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
CSV_FIELDS = ["date", "event_type", "is_synthetic", "count"]


def day_range(day: date) -> tuple[datetime, datetime]:
    """한국 날짜 하루의 [시작, 끝) 경계(시간대 포함)."""
    start = datetime.combine(day, time.min, tzinfo=KST)
    return start, start + timedelta(days=1)


def target_days(*, on: date | None, days: int, today: date) -> list[date]:
    if on is not None:
        return [on]
    if days < 1:
        raise ValueError("days는 1 이상")
    return [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


def pipeline(start: datetime, end: datetime) -> list[dict]:
    return [
        {"$match": {"occurred_at": {"$gte": start, "$lt": end}}},
        {"$unwind": {"path": "$products", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id": {
                    "date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$occurred_at",
                            "timezone": "Asia/Seoul",
                        }
                    },
                    "event_type": "$event_name",
                    "venue_id": {"$ifNull": ["$products.product_id", None]},
                    "is_synthetic": {"$ifNull": ["$is_synthetic", False]},
                },
                "count": {"$sum": 1},
            }
        },
    ]


def to_rows(groups) -> list[dict]:
    rows = []
    for item in groups:
        key = item["_id"]
        venue = key.get("venue_id")
        rows.append(
            {
                "date": key["date"],
                "event_type": key["event_type"],
                "venue_id": str(venue) if venue is not None else None,
                "is_synthetic": bool(key.get("is_synthetic")),
                "count": int(item["count"]),
            }
        )
    rows.sort(key=lambda r: (r["date"], r["event_type"], r["venue_id"] or "", r["is_synthetic"]))
    return rows


def aggregate_day(db, day: date) -> dict:
    """하루를 다시 집계해 event_daily에 반영한다. 반환: 반영·삭제 건수."""
    from pymongo import UpdateOne

    start, end = day_range(day)
    rows = to_rows(db.events.aggregate(pipeline(start, end), allowDiskUse=True))
    label = day.isoformat()
    keys = []
    ops = []
    for row in rows:
        key = {k: row[k] for k in ("date", "event_type", "venue_id", "is_synthetic")}
        keys.append(key)
        ops.append(UpdateOne(key, {"$set": {"count": row["count"]}}, upsert=True))
    written = db.event_daily.bulk_write(ops, ordered=False).upserted_count if ops else 0
    stale = {"date": label, "$nor": keys} if keys else {"date": label}
    removed = db.event_daily.delete_many(stale).deleted_count
    return {"date": label, "groups": len(rows), "new": written, "removed": removed}


def export_csv(db, days: list[date], path: Path) -> int:
    labels = [d.isoformat() for d in days]
    cursor = db.event_daily.find(
        {"date": {"$in": labels}}, {"_id": 0, **dict.fromkeys(CSV_FIELDS, 1)}
    )
    totals: dict[tuple[str, str, bool], int] = {}
    for row in cursor:
        key = (row["date"], row["event_type"], row["is_synthetic"])
        totals[key] = totals.get(key, 0) + row["count"]
    rows = [
        {"date": day, "event_type": event_type, "is_synthetic": synthetic, "count": count}
        for (day, event_type, synthetic), count in sorted(totals.items())
    ]
    write_csv(rows, path)
    return len(rows)


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{k: row.get(k) for k in CSV_FIELDS},
                    "is_synthetic": "true" if row.get("is_synthetic") else "false",
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="events → event_daily 일별 집계")
    parser.add_argument("--date", type=date.fromisoformat, help="한국 날짜 하루(YYYY-MM-DD)")
    parser.add_argument(
        "--days", type=int, default=2, help="오늘 포함 최근 N일 (기본 2: 어제·오늘)"
    )
    parser.add_argument("--csv", type=Path, help="집계 결과를 CSV로 저장할 경로")
    args = parser.parse_args(argv)

    url = os.environ.get("MONGO_URL")
    if not url:
        print("MONGO_URL 환경변수가 필요합니다.", file=sys.stderr)
        return 2
    name = os.environ.get("MONGO_DB") or "space_rental_analytics"
    if name == "spacecube":  # 앱 설정과 같은 옛 이름 보정
        name = "space_rental_analytics"

    from pymongo import MongoClient

    days = target_days(on=args.date, days=args.days, today=datetime.now(KST).date())
    client = MongoClient(url, serverSelectionTimeoutMS=5000, tz_aware=True)
    try:
        db = client[name]
        for day in days:
            result = aggregate_day(db, day)
            print(
                f"{result['date']}: 조합 {result['groups']} (신규 {result['new']}, 삭제 {result['removed']})"
            )
        if args.csv:
            count = export_csv(db, days, args.csv)
            print(f"CSV {count}행 → {args.csv}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
