"""앱의 서비스·리포지토리 계약을 사용하는 백필 연결부. HTTP는 호출하지 않는다."""

import secrets
from contextlib import contextmanager
from datetime import date, datetime

from sqlalchemy import text

from app.core.db import get_engine, new_write_session
from app.core.errors import AppError
from app.repositories import reservation_repo, review_repo, user_repo, venue_repo
from app.schemas.auth import SignupCreate
from app.schemas.reservations import ReservationCreate
from app.schemas.reviews import ReviewCreate
from app.services import auth_service, reservation_service, review_service

from .plan import GeneratorError, digest


@contextmanager
def seed_lock(seed):
    """같은 seed의 다른 폴더·프로세스 실행도 DB 연결 단위 잠금으로 직렬화한다."""
    name = "generator-" + digest(seed)[:40]
    with get_engine().connect() as connection:
        acquired = connection.scalar(text("SELECT GET_LOCK(:name, 0)"), {"name": name})
        if acquired != 1:
            raise GeneratorError("같은 seed의 생성기가 이미 실행 중입니다.")
        try:
            yield
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})


class Gateway:
    def __init__(self, journal, runtime, config, session_factory=new_write_session):
        self.journal = journal
        self.runtime = runtime
        self.config = config
        self.session_factory = session_factory

    def signup(self, person, at):
        self.runtime.now = at
        email = f"gen-{self.config.seed}-{person}@example.invalid"
        with self.session_factory() as db:

            def recover():
                user = user_repo.get_by_email(db, email)
                if user is None:
                    return None
                if not user.is_synthetic or user.created_at != at:
                    raise GeneratorError(
                        "같은 seed 회원이 다른 실행에 속합니다. 원래 실행을 재개하세요."
                    )
                return {"user_id": user.user_id}

            def execute():
                body = SignupCreate(
                    email=email,
                    password=secrets.token_urlsafe(24),
                    name=f"가상회원{person + 1:03}",
                    phone="01000000000",
                    birth="900101",
                    gender_digit="1",
                    marketing_agreed=False,
                    terms_agreed=True,
                    privacy_agreed=True,
                )
                return auth_service.signup(db, body, is_synthetic=True)

            return self.journal.perform(f"member:{person}", recover, execute)["user_id"]

    def book(self, key, user_id, session_id, values, at, price_per_hour):
        self.runtime.now = at
        body = ReservationCreate(**values)
        with self.session_factory() as db:

            def recover():
                row = reservation_repo.find_generator_booking(
                    db, user_id=user_id, body=body, created_at=at
                )
                if row is not None:
                    if (
                        row["method"] != body.method
                        or row["paid_at"] != at
                        or row["total_price"] != price_per_hour * body.hours
                    ):
                        raise GeneratorError("복구할 예약의 결제 정보가 실행 계획과 다릅니다.")
                    return {"outcome": "created", "reservation_id": row["reservation_id"]}
                saved = self.journal.operations.get(key)
                if saved and saved["outcome"] == "conflict":
                    return saved
                if saved and saved["outcome"] == "duplicate":
                    existing = reservation_repo.get_owned_detail(
                        db, user_id=user_id, reservation_id=saved["reservation_id"]
                    )
                    if existing is not None:
                        return saved
                return None

            def execute():
                try:
                    result, status = reservation_service.create_reservation(
                        db, body, user_id=user_id, session_id=session_id, is_synthetic=True
                    )
                    return {
                        "outcome": "created" if status == 201 else "duplicate",
                        "reservation_id": result.reservation_id,
                    }
                except AppError as error:
                    if error.code != "SLOT_TAKEN":
                        raise
                    return {"outcome": "conflict", "slots": (error.detail or {}).get("slots", [])}

            return self.journal.perform(key, recover, execute)

    def cancel(self, reservation_id, user_id, session_id, at):
        self.runtime.now = at
        with self.session_factory() as db:

            def recover():
                row = reservation_repo.get_owned_detail(
                    db, user_id=user_id, reservation_id=reservation_id
                )
                if row and row["status"] == "cancelled":
                    if row["payment_status"] != "refunded" or row["refunded_at"] != at:
                        raise GeneratorError("복구할 취소의 환불 시각이 다릅니다.")
                    return {"reservation_id": reservation_id}
                return None

            def execute():
                reservation_service.cancel_reservation(
                    db, user_id=user_id, reservation_id=reservation_id, session_id=session_id
                )
                return {"reservation_id": reservation_id}

            return self.journal.perform(f"cancel:{reservation_id}", recover, execute)

    def complete(self, reservation_id, user_id, at):
        self.runtime.now = at
        with self.session_factory() as db:

            def recover():
                owned = reservation_repo.get_owned(db, user_id, reservation_id)
                if owned and owned[5] == "completed":
                    return {"reservation_id": reservation_id}
                return None

            def execute():
                reservation_service.complete_generator_reservation(
                    db, user_id=user_id, reservation_id=reservation_id
                )
                return {"reservation_id": reservation_id}

            return self.journal.perform(f"complete:{reservation_id}", recover, execute)

    def review(self, reservation_id, user_id, rating, content, at):
        self.runtime.now = at
        with self.session_factory() as db:

            def recover():
                review = review_repo.get_by_reservation(db, reservation_id)
                if review is None:
                    return None
                if (
                    review.user_id != user_id
                    or review.rating != rating
                    or review.content != content
                    or review.created_at != at
                    or review.deleted_at is not None
                ):
                    raise GeneratorError("복구할 후기의 내용·작성자가 실행 계획과 다릅니다.")
                return {"review_id": review.review_id}

            def execute():
                return review_service.create_review(
                    db, user_id, reservation_id, ReviewCreate(rating=rating, content=content)
                )

            return self.journal.perform(f"review:{reservation_id}", recover, execute)


def load_venues():
    with new_write_session() as db:
        return venue_repo.list_generator_venues(db)


def booking_end(body):
    return datetime.combine(date.fromisoformat(body["date"]), datetime.min.time()).replace(
        hour=body["start_hour"] + body["hours"]
    )
