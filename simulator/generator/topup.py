"""#19: 검증된 공간 속성으로 부족한 유형의 내부 등록 요청을 준비한다."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.internal import InternalVenueUpsert  # noqa: E402 -- backend 경로를 먼저 추가한다.

NAMES = {
    "studyroom": ("스터디룸", "집중형"),
    "studio": ("스튜디오", "촬영형"),
    "cafe": ("카페", "모임형"),
    "lectureroom": ("강의실", "수업형"),
    "partyroom": ("파티룸", "행사형"),
}


def prepare(snapshot, *, target=6, seed=19):
    """활성 공간을 세고 같은 유형의 검증된 원천 속성만 복제한다."""
    venues = snapshot["venues"]
    counts = Counter(row["category_code"] for row in venues if row.get("is_active"))
    prepared = []
    for category, (title, feature) in NAMES.items():
        candidates = sorted(
            (
                row
                for row in venues
                if row.get("verified")
                and row.get("source_site") in {"spacecloud", "shareit"}
                and row["category_code"] == category
            ),
            key=lambda row: (row["source_site"], row["source_id"]),
        )
        missing = max(0, target - counts[category])
        if missing and not candidates:
            raise ValueError(f"{category}: 검증된 같은 유형의 원천 공간이 없습니다.")
        existing_ids = {
            row.get("source_id") for row in venues if row.get("source_site") == "synthetic"
        }
        index = 0
        made = 0
        while made < missing:
            index += 1
            source = candidates[(index - 1) % len(candidates)]
            source_id = hashlib.sha256(f"{seed}:{category}:{index}".encode()).hexdigest()[:24]
            if f"gen-{source_id}" in existing_ids:
                continue
            body = {
                "source_site": "synthetic",
                "source_id": f"gen-{source_id}",
                "name": f"{source['sigungu']} {feature} {title} {index:02d}",
                "category_code": category,
                "sido": source["sido"],
                "sigungu": source["sigungu"],
                "capacity_max": source["capacity_max"],
                "price_per_hour": source["price_per_hour"],
                "min_hours": source["min_hours"],
                "open_hour": source["open_hour"],
                "close_hour": source["close_hour"],
                "description": f"{source['sigungu']}의 {feature} {title} 시연용 공간입니다.",
                "notice": "실제 업체의 예약 상품이 아닌 시연용 공간입니다.",
                "facilities": source.get("facilities", []),
                "images": [f"art:{category}-0"],
            }
            prepared.append(InternalVenueUpsert.model_validate(body).model_dump())
            made += 1
    return {"active_counts": dict(counts), "target_per_category": target, "requests": prepared}


def main(argv=None):
    parser = argparse.ArgumentParser(description="#19 부족 공간 등록 요청 준비")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=19)
    args = parser.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    result = prepare(snapshot, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"등록 요청 {len(result['requests'])}건: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
