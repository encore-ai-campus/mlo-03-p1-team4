"""F-63: 백필 업무 시각과 이벤트 적재 시각의 분리."""

from datetime import UTC, date, datetime, timedelta
from secrets import token_urlsafe
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core import clock
from app.core.clock import KST, get_now, get_today, override_business_time
from app.core.errors import AppError
from app.core.event_document import build_document
from app.core.security import verify_password
from app.schemas.auth import SignupCreate
from app.services import auth_service, review_service
from simulator.generator.events import browser_context
from simulator.generator.events import documents as generator_documents
from simulator.generator.plan import Config
from simulator.generator.runtime import HistoricalRuntime

PAST = datetime.fromisoformat("2026-10-01T10:30:00")


def test_business_time_applies_to_signup_validation_and_service(monkeypatch):
    created = SimpleNamespace(user_id=77)
    create = Mock(return_value=created)
    monkeypatch.setattr(auth_service.user_repo, "create", create)
    db = Mock()

    with override_business_time(PAST):
        body = SignupCreate(
            email="gen-75-1@example.invalid",
            password=token_urlsafe(12),
            name="가상회원",
            phone="01000000000",
            birth="121001",
            gender_digit="3",
            marketing_agreed=False,
            terms_agreed=True,
            privacy_agreed=True,
        )
        assert auth_service.signup(db, body, is_synthetic=True) == {"user_id": 77}

    values = create.call_args.kwargs
    assert values["created_at"] == PAST
    assert values["terms_agreed_at"] == PAST
    assert values["privacy_agreed_at"] == PAST
    assert values["password_hash"] != body.password
    assert verify_password(body.password, values["password_hash"])
    assert values["is_synthetic"] is True
    db.commit.assert_called_once_with()
    assert get_now() != PAST


def test_business_time_applies_to_review_service(monkeypatch):
    db = Mock()
    monkeypatch.setattr(
        review_service.reservation_repo,
        "get_owned",
        Mock(return_value=(41, 7, PAST.date(), 9, 10, "completed", PAST)),
    )
    monkeypatch.setattr(review_service.review_repo, "get_by_reservation", Mock(return_value=None))
    monkeypatch.setattr(review_service.user_repo, "get_active", Mock(return_value=object()))
    create = Mock(return_value=81)
    monkeypatch.setattr(review_service.review_repo, "create", create)

    with override_business_time(PAST + timedelta(days=1)):
        result = review_service.create_review(
            db, user_id=77, reservation_id=41, body=SimpleNamespace(rating=5, content="좋아요")
        )

    assert result == {"review_id": 81}
    assert create.call_args.kwargs["created_at"] == PAST + timedelta(days=1)
    db.commit.assert_called_once_with()


def test_event_received_at_stays_real_during_business_time_override(monkeypatch):
    monkeypatch.setattr(
        "app.core.event_document.get_settings", lambda: SimpleNamespace(server_name="generator")
    )
    before = datetime.now(UTC)
    with override_business_time(PAST):
        document = build_document(
            event_id="00000000-0000-4000-8000-000000000075",
            session_id="00000000-0000-4000-8000-000000000076",
            user_id=77,
            event_name="reservation_conflict",
            occurred_at=PAST.replace(tzinfo=UTC),
            products=[
                {
                    "product_id": "7",
                    "product_name": "테스트 공간",
                    "price": {
                        "currency": "KRW",
                        "displayed_amount_minor": 10000,
                        "billing_unit": "hour",
                    },
                    "rental_conditions": {
                        "start_at": "2026-10-02T09:00:00+09:00",
                        "end_at": "2026-10-02T10:00:00+09:00",
                        "guest_count": 1,
                        "option_ids": [],
                    },
                }
            ],
            is_synthetic=True,
        )
    after = datetime.now(UTC)

    assert document["occurred_at"] == PAST.replace(tzinfo=UTC)
    assert before <= document["received_at"] <= after
    assert document["received_at"] > document["occurred_at"]
    assert document["server"] == "generator"
    assert document["is_synthetic"] is True


def test_business_time_override_restores_nested_and_after_error():
    with override_business_time(PAST):
        assert get_today() == PAST.date()
        with pytest.raises(RuntimeError), override_business_time(PAST + timedelta(days=1)):
            assert get_today() == (PAST + timedelta(days=1)).date()
            raise RuntimeError("stop")
        assert get_now() == PAST
    assert get_now() != PAST


def test_historical_runtime_matches_business_override_for_signup_and_review(monkeypatch):
    """생성기 패치와 A 업무 시각이 실제 가입·후기 서비스 결과에서 같다."""
    actual_today = datetime.now(KST).date()
    signup_at = datetime.combine(actual_today - timedelta(days=30), datetime.min.time()).replace(
        hour=10, minute=30
    )
    # 실제 현재 시점에는 만 14세지만 백필 시각에는 아직 생일 전인 가입 입력이다.
    try:
        birthday = date(signup_at.year - 14, signup_at.month, signup_at.day)
    except ValueError:  # 2월 29일은 생년월일 제약상 평년 3월 1일로 보정
        birthday = date(signup_at.year - 14, 3, 1)
    birthday += timedelta(days=1)
    birth = birthday.strftime("%y%m%d")

    modes = {
        "generator": HistoricalRuntime,
        "A override": override_business_time,
    }
    signup_password = token_urlsafe(12)
    signup_results = {}
    review_results = {}
    validation_results = {}

    for name, context_factory in modes.items():
        with context_factory(signup_at), pytest.raises(AppError) as error:
            SignupCreate(
                email="age-boundary@example.invalid",
                password=signup_password,
                name="가상회원",
                phone="01000000000",
                birth=birth,
                gender_digit="3",
                marketing_agreed=False,
                terms_agreed=True,
                privacy_agreed=True,
            )
        validation_results[name] = (error.value.code, error.value.detail)

        created_user = SimpleNamespace(user_id=77)
        create_user = Mock(return_value=created_user)
        monkeypatch.setattr(auth_service.user_repo, "create", create_user)
        signup_db = Mock()
        with context_factory(signup_at):
            signup_body = SignupCreate(
                email="gen-75-1@example.invalid",
                password=signup_password,
                name="가상회원",
                phone="01000000000",
                birth="900101",
                gender_digit="1",
                marketing_agreed=False,
                terms_agreed=True,
                privacy_agreed=True,
            )
            signup_result = auth_service.signup(signup_db, signup_body, is_synthetic=True)
        saved_user = create_user.call_args.kwargs
        assert verify_password(signup_body.password, saved_user["password_hash"])
        signup_db.commit.assert_called_once_with()
        signup_results[name] = (
            signup_result,
            saved_user["created_at"],
            saved_user["terms_agreed_at"],
            saved_user["privacy_agreed_at"],
            saved_user["is_synthetic"],
        )

        review_at = signup_at + timedelta(days=1)
        reservation_date = signup_at.date() - timedelta(days=1)
        monkeypatch.setattr(
            review_service.reservation_repo,
            "get_owned",
            Mock(
                return_value=(
                    41,
                    7,
                    reservation_date,
                    9,
                    10,
                    "completed",
                    datetime.combine(reservation_date, datetime.min.time()),
                )
            ),
        )
        monkeypatch.setattr(
            review_service.review_repo, "get_by_reservation", Mock(return_value=None)
        )
        monkeypatch.setattr(review_service.user_repo, "get_active", Mock(return_value=object()))
        create_review = Mock(return_value=81)
        monkeypatch.setattr(review_service.review_repo, "create", create_review)
        review_db = Mock()
        with context_factory(review_at):
            review_result = review_service.create_review(
                review_db,
                user_id=77,
                reservation_id=41,
                body=SimpleNamespace(rating=5, content="좋아요"),
            )
        review_db.commit.assert_called_once_with()
        review_results[name] = (review_result, create_review.call_args.kwargs["created_at"])

    assert validation_results["generator"] == validation_results["A override"]
    assert validation_results["generator"][0] == "VALIDATION"
    assert validation_results["generator"][1]["fields"][0]["field"] == "birth"
    assert signup_results["generator"] == signup_results["A override"]
    assert signup_results["generator"][1:4] == (signup_at, signup_at, signup_at)
    assert signup_results["generator"][4] is True
    assert review_results["generator"] == review_results["A override"]
    assert review_results["generator"][1] == signup_at + timedelta(days=1)


def test_historical_runtime_matches_business_override_for_event_time(monkeypatch):
    """생성기 이벤트와 A override 경로가 occurred_at은 같고 received_at은 실제다."""
    monkeypatch.setattr(
        "app.core.event_document.get_settings",
        lambda: SimpleNamespace(server_name="generator"),
    )
    event_at = PAST + timedelta(days=2)
    config = Config(seed=75, base_date=date(2026, 11, 7), users=1, days=1, sessions_per_day=1)
    session = {
        "index": 0,
        "person": 0,
        "session_id": config.identifier("session:0"),
    }
    event_id = config.identifier("event:0:1")
    anonymous_id = config.identifier("anonymous:0")

    before = datetime.now(UTC)
    with HistoricalRuntime(event_at):
        generator_now = clock.get_now()
        generator_document = next(
            generator_documents(
                config,
                [session],
                {0: 77},
                [
                    {
                        "session": 0,
                        "key": "home",
                        "at": generator_now.isoformat(),
                        "name": "page_view",
                        "page": "home",
                    }
                ],
            )
        )

    with override_business_time(event_at):
        a_now = clock.get_now()
        a_document = build_document(
            event_id=event_id,
            session_id=session["session_id"],
            user_id=77,
            anonymous_id=anonymous_id,
            session_sequence=1,
            event_name="page_view",
            occurred_at=a_now.replace(tzinfo=KST),
            context=browser_context(config, session, "home"),
            products=[],
            properties={},
            is_synthetic=True,
        )
    after = datetime.now(UTC)

    assert generator_document["occurred_at"] == a_document["occurred_at"]
    assert generator_document["occurred_at"] == event_at.replace(tzinfo=KST).astimezone(UTC)
    assert {key: value for key, value in generator_document.items() if key != "received_at"} == {
        key: value for key, value in a_document.items() if key != "received_at"
    }
    for document in (generator_document, a_document):
        assert before <= document["received_at"] <= after
        assert document["received_at"] > document["occurred_at"]
