"""고정 방문량의 세션·예약·취소·완료·후기를 서비스 계층으로 실행한다."""

import random
from collections import Counter
from datetime import datetime, time, timedelta

from .events import documents, product
from .gateway import booking_end
from .plan import GeneratorError, allocations, candidates, make_sessions
from .storage import atomic_json

REVIEW_TEMPLATES = {
    "studyroom": "집중해서 공부하기 좋은 구성의 공간이었습니다.",
    "studio": "촬영과 작업에 필요한 공간 구성이 편리했습니다.",
    "cafe": "대화와 모임을 진행하기에 편리한 공간이었습니다.",
    "lectureroom": "여럿이 함께 학습하기 좋은 공간이었습니다.",
    "partyroom": "모임을 진행하기에 알맞은 공간 구성이었습니다.",
}


class Runner:
    def __init__(self, config, venues, gateway, journal, sink):
        self.config = config
        self.venues = venues
        self.by_id = {venue["venue_id"]: venue for venue in venues}
        self.gateway = gateway
        self.journal = journal
        self.sink = sink
        self.sessions = make_sessions(config)
        self.records = []
        self.created = []
        self.counts = Counter()

    def emit(self, session, name, at, page, *, body=None, venue=None, properties=None):
        record = {
            "key": f"{session['index']}:{len(self.records)}",
            "session": session["index"],
            "name": name,
            "at": at.isoformat(),
            "page": page,
            "properties": properties or {},
        }
        if venue is not None:
            record.update(venue_id=venue["venue_id"], products=[product(venue, body)])
        self.records.append(record)

    def visit(self, session, user_id):
        at = datetime.fromisoformat(session["at"])
        choices = candidates(self.config, session, self.venues)
        venue = (
            self.by_id[choices[0]["venue_id"]]
            if choices
            else self.venues[session["choice_seed"] % len(self.venues)]
        )
        self.emit(session, "page_view", at, "home")
        self.emit(session, "search_submit", at + timedelta(seconds=1), "search_results")
        for offset, name in enumerate(
            ("product_impression", "product_view", "availability_view"), 2
        ):
            self.emit(session, name, at + timedelta(seconds=offset), "product_detail", venue=venue)
        for attempt, body in enumerate(choices):
            venue = self.by_id[body["venue_id"]]
            booked_at = at + timedelta(seconds=60 + 120 * attempt)
            self.emit(
                session,
                "rental_slot_select",
                booked_at - timedelta(seconds=2),
                "product_detail",
                body=body,
                venue=venue,
            )
            self.emit(
                session,
                "reservation_start",
                booked_at - timedelta(seconds=1),
                "checkout",
                body=body,
                venue=venue,
            )
            result = self.gateway.book(
                f"booking:{session['index']}:{attempt}",
                user_id,
                session["session_id"],
                body,
                booked_at,
                venue["price_per_hour"],
            )
            self.counts["booking_attempts"] += 1
            outcome = result["outcome"]
            if outcome == "conflict":
                self.counts["conflicts"] += 1
                self.emit(
                    session,
                    "reservation_conflict",
                    booked_at,
                    "checkout",
                    body=body,
                    venue=venue,
                    properties={"reason": "SLOT_TAKEN", "slots": result["slots"]},
                )
                continue
            if outcome == "duplicate":
                self.counts["existing_responses"] += 1
                break
            self.emit(
                session, "reservation_complete", booked_at, "checkout", body=body, venue=venue
            )
            reservation_id = result["reservation_id"]
            # 성공 예약 열 건마다 한 건: 정수 나머지는 버려 floor(N*0.1)을 지킨다.
            cancel = (len(self.created) + 1) % 10 == 0
            self.created.append(
                {
                    "reservation_id": reservation_id,
                    "user_id": user_id,
                    "person": session["person"],
                    "body": body,
                    "venue": venue,
                    "cancelled": cancel,
                    "booked_at": booked_at,
                }
            )
            if cancel:
                cancelled_at = booked_at + timedelta(seconds=60)
                self.gateway.cancel(reservation_id, user_id, session["session_id"], cancelled_at)
                self.emit(
                    session,
                    "reservation_cancel_attempt",
                    cancelled_at - timedelta(seconds=1),
                    "my_page",
                    body=body,
                    venue=venue,
                )
                self.emit(
                    session,
                    "reservation_cancel_complete",
                    cancelled_at,
                    "my_page",
                    body=body,
                    venue=venue,
                    properties={"reservation_id": reservation_id},
                )
                self.counts["cancelled"] += 1
            break

    def finish_reviews(self):
        completed = [booking for booking in self.created if not booking["cancelled"]]
        for booking in completed:
            self.gateway.complete(
                booking["reservation_id"], booking["user_id"], booking_end(booking["body"])
            )
        self.counts["completed"] = len(completed)
        eligible = []
        for booking in completed:
            end = booking_end(booking["body"])
            deadline = max(end.date(), booking["booked_at"].date()) + timedelta(days=7)
            # 이미 배정된 같은 회원의 후속 방문에 후기를 넣어 세션 총량을 유지한다.
            followup = next(
                (
                    session
                    for session in self.sessions
                    if session["person"] == booking["person"]
                    and end < datetime.fromisoformat(session["at"])
                    and datetime.fromisoformat(session["at"]).date() <= deadline
                ),
                None,
            )
            if followup is not None:
                eligible.append((booking, followup))
        target = len(completed) // 4
        if len(eligible) < target:
            raise GeneratorError(
                "후기 25%를 채울 후속 세션이 부족합니다. manifest를 보존해 확인하세요."
            )
        rng = random.Random(self.config.seed)  # noqa: S311 -- 후기 분포 재현용
        rng.shuffle(eligible)
        ratings = []
        for rating, count in zip(
            (5, 4, 3, 2, 1), allocations(target, (40, 30, 15, 10, 5)), strict=True
        ):
            ratings.extend([rating] * count)
        rng.shuffle(ratings)
        for (booking, session), rating in zip(eligible[:target], ratings, strict=True):
            at = datetime.fromisoformat(session["at"]) + timedelta(seconds=300)
            self.gateway.review(
                booking["reservation_id"],
                booking["user_id"],
                rating,
                REVIEW_TEMPLATES[booking["venue"]["category_code"]],
                at,
            )
            self.emit(
                session,
                "review_create",
                at,
                "reviews",
                body=booking["body"],
                venue=booking["venue"],
                properties={
                    "reservation_id": booking["reservation_id"],
                    "rating": rating,
                },
            )
            self.counts[f"rating_{rating}"] += 1
        self.counts["reviews"] = target

    def run(self):
        start = datetime.combine(self.config.base_date - timedelta(days=self.config.days), time())
        user_ids = [
            self.gateway.signup(person, start + timedelta(seconds=person))
            for person in range(self.config.users)
        ]
        for session in self.sessions:
            self.visit(session, user_ids[session["person"]])
        self.finish_reviews()
        inserted = duplicates = event_count = 0
        batch = []
        for document in documents(self.config, self.sessions, user_ids, self.records):
            batch.append(document)
            event_count += 1
            if len(batch) >= 100:
                added, repeated = self.sink.write(batch)
                inserted += added
                duplicates += repeated
                batch = []
        if batch:
            added, repeated = self.sink.write(batch)
            inserted += added
            duplicates += repeated
        report = {
            "run_id": self.config.run_id,
            "period_start": start.date().isoformat(),
            "period_end": (self.config.base_date - timedelta(days=1)).isoformat(),
            "users": len(user_ids),
            "sessions": len(self.sessions),
            "personas": dict(Counter(session["persona"] for session in self.sessions)),
            "reservations": len(self.created),
            **self.counts,
            "events": event_count,
            "mongo_inserted": inserted,
            "mongo_duplicates": duplicates,
            "downstream": {"event_daily": "DB 담당 후속 실행", "csv": "DB 담당 후속 실행"},
        }
        atomic_json(self.journal.directory / "report.json", report)
        return report
