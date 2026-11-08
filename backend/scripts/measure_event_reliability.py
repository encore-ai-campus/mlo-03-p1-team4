"""F-60: 한 시험 세션의 API 접수·파일·MongoDB 이벤트 수를 대조한다."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.core.mongo import close_mongo, get_event_collection


def measure(path: Path, session_id: str, accepted: int | None, expected_unique: int | None) -> dict:
    log_ids = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                document = json.loads(line)
            except json.JSONDecodeError:
                continue
            user = document.get("user")
            if not isinstance(user, dict) or user.get("session_id") != session_id:
                continue
            if document.get("server") == "generator":
                continue
            event_id = document.get("event_id")
            if isinstance(event_id, str):
                log_ids.append(event_id)

    documents = get_event_collection().find(
        {"user.session_id": session_id, "server": {"$ne": "generator"}},
        {"_id": 0, "event_id": 1},
    )
    mongo_ids = [item["event_id"] for item in documents if isinstance(item.get("event_id"), str)]
    unique_log = set(log_ids)
    unique_mongo = set(mongo_ids)
    missing = sorted(unique_log - unique_mongo)
    stored = len(unique_log & unique_mongo)
    return {
        "session_id": session_id,
        "api_accepted_attempts": accepted,
        "expected_unique_events": expected_unique,
        "log_lines": len(log_ids),
        "log_unique": len(unique_log),
        "mongo_documents": len(mongo_ids),
        "mongo_unique": len(unique_mongo),
        "log_duplicate_ids": len(log_ids) - len(unique_log),
        "mongo_duplicate_ids": len(mongo_ids) - len(unique_mongo),
        "fallback_only_in_log": len(missing),
        "missing_mongo_event_ids": missing,
        "missing_log_count": (
            max(0, expected_unique - len(unique_log)) if expected_unique is not None else None
        ),
        "excess_stored_count": (
            max(0, stored - expected_unique) if expected_unique is not None else None
        ),
        "loss_rate": (
            max(0, expected_unique - stored) / expected_unique if expected_unique else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="한 시험 세션의 이벤트 수집 신뢰성을 읽기 전용으로 측정"
    )
    parser.add_argument("--session-id", type=UUID, required=True)
    parser.add_argument("--accepted", type=int, help="API 202 응답의 accepted 합계(재전송 포함)")
    parser.add_argument("--expected-unique", type=int, help="재전송을 제외한 고유 사용자 이벤트 수")
    parser.add_argument("--file", type=Path, default=get_settings().log_path / "events.log")
    args = parser.parse_args()
    if args.accepted is not None and args.accepted < 0:
        parser.error("--accepted는 0 이상이어야 합니다")
    if args.expected_unique is not None and args.expected_unique < 0:
        parser.error("--expected-unique는 0 이상이어야 합니다")
    try:
        print(
            json.dumps(
                measure(args.file, str(args.session_id), args.accepted, args.expected_unique),
                ensure_ascii=False,
            )
        )
    finally:
        close_mongo()


if __name__ == "__main__":
    main()
