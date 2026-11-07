"""F-63: 백필 업무 시각과 이벤트 적재 시각의 분리."""

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.clock import get_now, get_today, override_business_time
from app.core.event_document import build_document
from app.core.security import verify_password
from app.schemas.auth import SignupCreate
from app.services import auth_service, review_service

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
