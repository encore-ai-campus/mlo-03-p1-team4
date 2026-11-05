"""MongoDB 연결 하나를 공유하고 작업 전체 시간 제한을 둔다.

사용: 이벤트 작성기·재적재 스크립트·헬스체크가 MongoDB 연결을 공유한다.
"""

import logging
from functools import lru_cache

import pymongo
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import get_settings


@lru_cache
def get_mongo_client() -> MongoClient | None:
    value = get_settings().mongo_url
    if value is None:
        return None
    try:
        return MongoClient(
            value.get_secret_value(),
            serverSelectionTimeoutMS=1000,
            connectTimeoutMS=1000,
            socketTimeoutMS=1000,
            timeoutMS=1000,
            tz_aware=True,
            connect=False,
        )
    except (PyMongoError, ValueError):
        # 주소 오류도 MongoDB만 degraded로 둔다. 원문에는 인증 정보가 있을 수 있다.
        logging.getLogger("spacecube.app").error("MongoDB 연결 설정을 확인하세요.")
        return None


def get_event_collection():
    client = get_mongo_client()
    if client is None:
        raise RuntimeError("MONGO_URL이 설정되지 않았습니다.")
    return client[get_settings().mongo_db]["user_events"]


def check_mongo() -> bool:
    client = get_mongo_client()
    if client is None:
        return False
    try:
        with pymongo.timeout(0.5):
            client.admin.command("ping")
        return True
    except PyMongoError:
        return False


def close_mongo() -> None:
    client = get_mongo_client()
    if client is not None:
        client.close()
    get_mongo_client.cache_clear()
