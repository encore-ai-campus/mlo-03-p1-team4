"""크롤러 JSON 로그. 백엔드(`app.core.logging`)와 같은 한 줄 JSON 모양으로 stderr에 남긴다.

개인정보·원문 HTML·예외 원문은 넣지 않는다. 단계(stage)·원인 종류(kind)·출처 ID 같은 안전한 값만 쓴다.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime

# 로그 줄에 그대로 옮기는 안전한 추가 필드
FIELDS = (
    "stage",
    "kind",
    "source_site",
    "source_id",
    "error_type",
    "status_code",
    "attempt",
    "wait_sec",
    "count",
    "path",
    "result",
)


class CrawlerJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "server": os.environ.get("SERVER_NAME") or "crawler",
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        value.update({key: getattr(record, key) for key in FIELDS if hasattr(record, key)})
        return json.dumps(value, ensure_ascii=False, default=str)


def get_logger(name: str = "spacecube.crawler") -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(h.formatter, CrawlerJsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(CrawlerJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
