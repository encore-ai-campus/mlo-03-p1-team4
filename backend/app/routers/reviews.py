"""F-41·50·51: 공개 목록만 replica, 내 후기와 쓰기는 primary.

사용: 후기 작성자와 공간 상세·후기 목록 화면이 후기 API를 호출한다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.orm import Session

from app.core.db import get_db_read
from app.core.deps import CurrentUser, WriteDB, get_current_user
from app.core.pagination import Page, Pagination, get_pagination
from app.schemas.reviews import (
    Category,
    ReviewCreate,
    ReviewListItem,
    ReviewRead,
    ReviewSort,
    ReviewUpdate,
)
from app.services import review_service

router = APIRouter()
Member = Annotated[CurrentUser, Depends(get_current_user)]
ReadDB = Annotated[Session, Depends(get_db_read)]
Pages = Annotated[Pagination, Depends(get_pagination)]
PositiveId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("/reservations/{reservation_id}/review", status_code=201)
def create_review(
    reservation_id: PositiveId, body: ReviewCreate, user: Member, db: WriteDB
) -> ReviewRead:
    return review_service.create_review(db, user.user_id, reservation_id, body)


@router.patch("/reviews/{review_id}")
def update_review(
    review_id: PositiveId, body: ReviewUpdate, user: Member, db: WriteDB
) -> ReviewRead:
    return review_service.update_review(db, user.user_id, review_id, body)


@router.delete("/reviews/{review_id}", status_code=204)
def delete_review(review_id: PositiveId, user: Member, db: WriteDB) -> Response:
    review_service.delete_review(db, user.user_id, review_id)
    return Response(status_code=204)


@router.get("/venues/{venue_id}/reviews")
def venue_reviews(venue_id: PositiveId, db: ReadDB, pagination: Pages) -> Page[ReviewListItem]:
    return review_service.list_reviews(db, pagination, venue_id=venue_id)


@router.get("/reviews")
def reviews(
    db: ReadDB,
    pagination: Pages,
    category: Category | None = None,
    sort: ReviewSort = "recent",
) -> Page[ReviewListItem]:
    return review_service.list_reviews(db, pagination, category=category, sort=sort)


@router.get("/users/me/reviews")
def my_reviews(user: Member, db: WriteDB, pagination: Pages) -> Page[ReviewListItem]:
    return review_service.list_reviews(db, pagination, user_id=user.user_id)
