"""F-60: 실제 HTTP 예약 결과 3종을 명시적으로 지정한 MongoDB에서 검증한다.

CHECK_MONGO_URL은 실행 환경에서만 지정한다. 기존 validator·인덱스는 변경하지
않고, 이 실행의 세션·가상 이벤트 ID만 조회·정리한다. 실행 진입점은
check_reservation_http.py이며 MariaDB는 로컬 spacecube_test로 제한된다.
"""

import os
import secrets
import time
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from pymongo import MongoClient
from pymongo.errors import BulkWriteError, WriteError


def check_mongo_events(*, client, engine, token, synthetic_key, venue_id, today):
    from check_reservation_http import clean_rows

    session_id = str(uuid4())
    email = f"{uuid4().hex}@example.invalid"
    password = secrets.token_urlsafe(24) + "aA1!"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Session-Id": session_id,
        "X-Synthetic": "1",
        "X-Synthetic-Key": synthetic_key,
    }
    url = "http://localhost/reserve"
    context = {
        "user": {"anonymous_id": str(uuid4()), "session_sequence": 1},
        "site": {"site_id": "main", "hostname": "localhost", "platform": "desktop_web"},
        "acquisition": {"landing_url": url},
        "page": {"page_view_id": str(uuid4()), "page_type": "checkout", "url": url},
        "navigation": {"from": None, "to": {"url": url}, "navigation_type": "direct"},
    }
    body = {
        "venue_id": venue_id,
        "date": (today + timedelta(days=2)).isoformat(),
        "start_hour": 13,
        "hours": 2,
        "headcount": 2,
        "method": "card",
        "event_context": context,
    }
    scope = {"user.session_id": session_id, "is_synthetic": True}
    with MongoClient(os.environ["CHECK_MONGO_URL"], serverSelectionTimeoutMS=5000) as mongo:
        collection = mongo["space_rental_analytics"]["events"]
        mongo.admin.command("ping")
        try:
            created = client.post("/reservations", headers=headers, json=body)
            assert created.status_code == 201
            assert client.post("/reservations", headers=headers, json=body).status_code == 200
            signup = client.post(
                "/auth/signup",
                headers=headers,
                json={
                    "email": email,
                    "password": password,
                    "name": "가상 충돌 회원",
                    "phone": "01000010002",
                    "birth": "000101",
                    "gender_digit": "3",
                    "terms_agreed": True,
                    "privacy_agreed": True,
                    "marketing_agreed": False,
                },
            )
            assert signup.status_code == 201
            login = client.post("/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200
            conflict_headers = {
                **headers,
                "Authorization": f"Bearer {login.json()['access_token']}",
            }
            assert (
                client.post("/reservations", headers=conflict_headers, json=body).status_code == 409
            )
            reservation_id = created.json()["reservation_id"]
            assert (
                client.post(
                    f"/reservations/{reservation_id}/cancel",
                    headers=headers,
                    json={"event_context": context},
                ).status_code
                == 200
            )
            deadline = time.monotonic() + 5
            docs = []
            while time.monotonic() < deadline:
                docs = list(collection.find(scope))
                if len(docs) == 3:
                    break
                time.sleep(0.1)
            assert sorted(d["event_name"] for d in docs) == [
                "reservation_cancel_complete",
                "reservation_complete",
                "reservation_conflict",
            ], "MongoDB 서버 결과 3종 저장 확인 실패"
            for doc in docs:
                product = doc["products"][0]
                assert product["product_id"] == str(venue_id)
                assert product["price"]["displayed_amount_minor"] == 10000
                assert product["rental_conditions"]["guest_count"] == 2
                assert isinstance(doc["user"]["user_id"], str)
            conflict = next(d for d in docs if d["event_name"] == "reservation_conflict")
            assert conflict["properties"]["reason"] == "SLOT_TAKEN"
            print(
                "MongoDB verified: 3 server result events from real HTTP, retry emits no duplicate"
            )
            repeated = [{k: v for k, v in d.items() if k != "_id"} for d in docs]
            try:
                collection.insert_many(repeated, ordered=False)
            except BulkWriteError as error:
                assert error.details["nInserted"] == 0
                assert len(error.details["writeErrors"]) == 3
                assert all(e["code"] == 11000 for e in error.details["writeErrors"])
            else:
                raise AssertionError("event_id 고유 인덱스가 중복 재적재를 차단하지 않았습니다.")
            print("MongoDB verified: replaying the same 3 event IDs adds zero documents")

            contextless = deepcopy(repeated[0])
            contextless["event_id"] = str(uuid4())
            contextless["user"].update(anonymous_id=None, session_sequence=None)
            for field in ("site", "acquisition", "page", "navigation"):
                contextless[field] = None
            try:
                collection.insert_one(contextless)
            except WriteError as error:
                assert error.code == 121
                print(
                    "MongoDB CONTRACT GAP: server null context rejected (121); DB update required"
                )
            else:
                print("MongoDB verified: server null context accepted")
        finally:
            # 같은 세션이라도 이번 조회에서 확인한 가상 이벤트 ID만 지운다.
            event_ids = [d["event_id"] for d in collection.find(scope, {"event_id": 1})]
            if event_ids:
                result = collection.delete_many({**scope, "event_id": {"$in": event_ids}})
                assert result.deleted_count == len(event_ids)
            assert collection.count_documents(scope) == 0
            clean_rows(engine, email, None, "")
            print("MongoDB temporary synthetic event IDs removed; validator unchanged")
