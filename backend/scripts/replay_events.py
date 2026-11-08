"""F-60: events.log를 재생한다. event_id UNIQUE로 중복은 무시한다.

사용: 운영자가 MongoDB 장애 후 이벤트 로그 파일을 다시 적재할 때 실행한다.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.clock import as_korean_time
from app.core.config import get_settings
from app.core.event_document import EVENT_DOCUMENT_FIELDS
from app.core.events import insert_event_documents
from app.core.mongo import close_mongo


def parse_time(value: str) -> datetime:
    return as_korean_time(datetime.fromisoformat(value.replace("Z", "+00:00"))).astimezone(UTC)


def replay(path: Path, since: datetime | None) -> dict:
    inserted = duplicates = invalid = 0
    batch = []

    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                document = json.loads(line)
                # 이전 형식에는 필수 화면·상품 문맥이 없으므로 변환하지 않는다.
                if set(document) != EVENT_DOCUMENT_FIELDS or document.get("schema_version") != 1:
                    raise ValueError("새 events 형식 아님")
                if not document.get("event_id"):
                    raise ValueError("event_id 없음")
                document["occurred_at"] = parse_time(document["occurred_at"])
                document["received_at"] = parse_time(document["received_at"])
                for product in document["products"]:
                    rental = product["rental_conditions"]
                    for key in ("start_at", "end_at"):
                        if rental[key] is not None:
                            rental[key] = parse_time(rental[key])
            except (ValueError, KeyError, TypeError, AttributeError):
                invalid += 1
                continue
            if since and document["received_at"] < since:
                continue
            batch.append(document)
            if len(batch) == 50:
                count, repeated = insert_event_documents(batch)
                inserted += count
                duplicates += repeated
                batch = []
        if batch:
            count, repeated = insert_event_documents(batch)
            inserted += count
            duplicates += repeated
    return {"inserted": inserted, "duplicates": duplicates, "invalid": invalid}


def main() -> None:
    parser = argparse.ArgumentParser(description="이벤트 로그를 MongoDB에 다시 적재합니다.")
    parser.add_argument("--since", type=parse_time)
    parser.add_argument("--file", type=Path, default=get_settings().log_path / "events.log")
    arguments = parser.parse_args()
    try:
        print(json.dumps(replay(arguments.file, arguments.since), ensure_ascii=False))
    finally:
        close_mongo()


if __name__ == "__main__":
    main()
