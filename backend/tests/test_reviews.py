"""F-50 후기 작성 자격 판정과 트랜잭션 단위 테스트."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.core.pagination import Pagination
from app.services import review_service

TODAY = date(2026, 11, 5)
NOW = datetime.fromisoformat("2026-11-05T12:00:00")
BODY = SimpleNamespace(rating=5, content="테스트 후기")


@pytest.fixture
def review_flow(monkeypatch):
    db = Mock()
    reservation = (41, 7, TODAY, 9, 10, "completed", NOW)
    monkeypatch.setattr(review_service, "get_today", lambda: TODAY)
    monkeypatch.setattr(review_service, "get_now", lambda: NOW)
    monkeypatch.setattr(
        review_service.reservation_repo, "get_owned", Mock(return_value=reservation)
    )
    monkeypatch.setattr(review_service.user_repo, "get_active", Mock(return_value=object()))
    monkeypatch.setattr(review_service.review_repo, "get_by_reservation", Mock(return_value=None))
    monkeypatch.setattr(review_service.review_repo, "create", Mock(return_value=81))
    return db


def assert_app_error(call, code: str, status: int):
    with pytest.raises(AppError) as caught:
        call()
    assert (caught.value.code, caught.value.status) == (code, status)
    return caught.value


def test_create_review_uses_b_owned_contract_and_commits(review_flow):
    db = review_flow

    assert review_service.create_review(db, 12, 41, BODY) == {"review_id": 81}

    review_service.reservation_repo.get_owned.assert_called_once_with(db, 12, 41)
    review_service.review_repo.create.assert_called_once_with(
        db,
        reservation_id=41,
        user_id=12,
        rating=5,
        content="테스트 후기",
        created_at=NOW,
    )
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("reservation", "existing", "today", "expected_code", "status"),
    [
        (None, None, TODAY, "RESERVATION_NOT_FOUND", 404),
        ((41, 7, TODAY, 9, 10, "confirmed", NOW), None, TODAY, "NOT_COMPLETED", 403),
        (
            (41, 7, TODAY - timedelta(days=8), 9, 10, "completed", NOW - timedelta(days=8)),
            None,
            TODAY,
            "REVIEW_PERIOD_OVER",
            403,
        ),
        (
            (41, 7, TODAY, 9, 10, "completed", NOW),
            SimpleNamespace(review_id=72),
            TODAY,
            "REVIEW_EXISTS",
            409,
        ),
    ],
)
def test_create_review_rejects_in_eligibility_order(
    review_flow, monkeypatch, reservation, existing, today, expected_code, status
):
    db = review_flow
    monkeypatch.setattr(
        review_service.reservation_repo, "get_owned", Mock(return_value=reservation)
    )
    monkeypatch.setattr(
        review_service.review_repo,
        "get_by_reservation",
        Mock(return_value=existing),
    )
    monkeypatch.setattr(review_service, "get_today", lambda: today)

    error = assert_app_error(
        lambda: review_service.create_review(db, 12, 41, BODY), expected_code, status
    )

    if expected_code == "REVIEW_PERIOD_OVER":
        assert error.detail == {"deadline": (TODAY - timedelta(days=1)).isoformat()}
    if expected_code == "REVIEW_EXISTS":
        assert error.detail == {"review_id": 72}
    else:
        review_service.review_repo.get_by_reservation.assert_not_called()
    review_service.review_repo.create.assert_not_called()
    review_service.user_repo.get_active.assert_not_called()
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_review_deadline_includes_seventh_day(review_flow, monkeypatch):
    db = review_flow
    monkeypatch.setattr(
        review_service.reservation_repo,
        "get_owned",
        Mock(
            return_value=(
                41,
                7,
                TODAY - timedelta(days=7),
                9,
                10,
                "completed",
                NOW - timedelta(days=7),
            )
        ),
    )

    assert review_service.create_review(db, 12, 41, BODY) == {"review_id": 81}
    db.commit.assert_called_once_with()


def test_review_database_failure_rolls_back(review_flow, monkeypatch):
    db = review_flow
    monkeypatch.setattr(
        review_service.review_repo,
        "create",
        Mock(side_effect=RuntimeError("database write failed")),
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        review_service.create_review(db, 12, 41, BODY)

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_review_non_duplicate_integrity_error_is_not_mapped_to_conflict(review_flow, monkeypatch):
    db = review_flow
    error = IntegrityError("INSERT", {}, Exception(1452, "foreign key"))
    monkeypatch.setattr(review_service.review_repo, "create", Mock(side_effect=error))

    with pytest.raises(IntegrityError) as caught:
        review_service.create_review(db, 12, 41, BODY)

    assert caught.value is error
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_review_unique_race_rolls_back_and_reports_existing(review_flow, monkeypatch):
    db = review_flow
    error = IntegrityError("INSERT", {}, Exception(1062, "duplicate"))
    monkeypatch.setattr(review_service.review_repo, "create", Mock(side_effect=error))
    monkeypatch.setattr(
        review_service.review_repo,
        "get_by_reservation",
        Mock(side_effect=[None, SimpleNamespace(review_id=72)]),
    )

    caught = assert_app_error(
        lambda: review_service.create_review(db, 12, 41, BODY), "REVIEW_EXISTS", 409
    )

    assert caught.detail == {"review_id": 72}
    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


def test_list_reviews_masks_active_author_and_labels_withdrawn_author(monkeypatch):
    rows = [
        {
            "review_id": 1,
            "author_name": "김민수",
            "author_deleted_at": None,
            "venue_id": 7,
            "venue_name": "검증 공간",
            "category": "studyroom",
            "rating": 5,
            "content": "좋아요",
            "created_at": NOW,
        },
        {
            "review_id": 2,
            "author_name": "탈퇴회원",
            "author_deleted_at": NOW,
            "venue_id": 8,
            "venue_name": "다른 공간",
            "category": "studio",
            "rating": 4,
            "content": "좋았어요",
            "created_at": NOW,
        },
    ]
    monkeypatch.setattr(
        review_service.review_repo,
        "list_items",
        Mock(return_value=(rows, 2)),
    )

    result = review_service.list_reviews(Mock(), Pagination(page=1, size=20))

    assert result["total"] == 2
    assert result["items"][0]["author"] == "김**"
    assert result["items"][1]["author"] == "탈퇴한 회원"
