"""F-60: events.log를 재생한다. event_id UNIQUE로 중복은 무시한다.

사용: 운영자가 MongoDB 장애 후 이벤트 로그 파일을 다시 적재할 때 실행한다.
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.clock import as_korean_time
from app.core.config import get_settings
from app.core.events import EVENT_DOCUMENT_FIELDS, insert_event_documents
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
                # 옛 v4 로그의 추가 필드를 제외하되 중복 판정용 event_id는 유지한다.
                document = {
                    key: value for key, value in document.items() if key in EVENT_DOCUMENT_FIELDS
                }
                document["ts"] = parse_time(document["ts"])
                if document.get("client_ts"):
                    document["client_ts"] = parse_time(document["client_ts"])
                if not document.get("event_id"):
                    raise ValueError("event_id 없음")
            except (ValueError, KeyError, TypeError, AttributeError):
                invalid += 1
                continue
            if since and document["ts"] < since:
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
