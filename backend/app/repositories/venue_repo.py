"""F-12~13 공간 검색·정렬과 F-20~22 상세·영업시간 SQL."""

from datetime import date, datetime

from sqlalchemy import and_, column, exists, false, func, literal, or_, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.models.catalog import Category, Facility, Region
from app.models.reservation import Reservation, ReservationSlot
from app.models.venue import Venue, VenueFacility, VenueImage

# 기존 DB 뷰를 조회식으로만 참조한다. ORM 모델이나 새 표를 만들지 않는다.
_rating_view = table(
    "v_venue_rating", column("venue_id"), column("rating_avg"), column("review_count")
)


def category_exists(db: Session, category_code: str) -> bool:
    """검색 유형이 기준 정보에 있는지 확인한다."""
    return bool(db.scalar(select(exists().where(Category.code == category_code))))


def _search_conditions(
    *,
    q: str | None,
    category: str | None,
    sido: str | None,
    sigungu: str | None,
    people: int | None,
    facility_ids: list[int],
    slot_date: date,
    start_hour: int | None,
    hours: int | None,
    now_only: bool,
    current_hour: int,
):
    conditions = [Venue.is_active.is_(True)]
    if q:
        facility_name_matches = exists(
            select(literal(1))
            .select_from(VenueFacility)
            .join(Facility, Facility.facility_id == VenueFacility.facility_id)
            .where(
                VenueFacility.venue_id == Venue.venue_id, Facility.name.contains(q, autoescape=True)
            )
        )
        conditions.append(
            or_(
                Venue.name.contains(q, autoescape=True),
                Region.sido.contains(q, autoescape=True),
                Region.sigungu.contains(q, autoescape=True),
                facility_name_matches,
            )
        )
    if category:
        conditions.append(Category.code == category)
    if sido and sido != "전국":
        conditions.append(Region.sido == sido)
    if sigungu and sigungu != "전체":
        conditions.append(Region.sigungu == sigungu)
    if people is not None:
        conditions.append(Venue.capacity_max >= people)
    if facility_ids:
        all_facilities_match = (
            select(VenueFacility.venue_id)
            .where(
                VenueFacility.venue_id == Venue.venue_id,
                VenueFacility.facility_id.in_(facility_ids),
            )
            .group_by(VenueFacility.venue_id)
            .having(func.count(func.distinct(VenueFacility.facility_id)) == len(facility_ids))
        )
        conditions.append(exists(all_facilities_match))
    if start_hour is not None and hours is not None:
        requested_slots_taken = exists(
            select(literal(1)).where(
                ReservationSlot.venue_id == Venue.venue_id,
                ReservationSlot.slot_date == slot_date,
                ReservationSlot.slot_hour >= start_hour,
                ReservationSlot.slot_hour < start_hour + hours,
            )
        )
        conditions.extend(
            (
                Venue.open_hour <= start_hour,
                Venue.close_hour >= start_hour + hours,
                Venue.min_hours <= hours,
                ~requested_slots_taken,
            )
        )
    if now_only:
        available_future_hours = []
        for hour in range(max(9, current_hour + 1), 23):
            slot_is_taken = exists(
                select(literal(1)).where(
                    ReservationSlot.venue_id == Venue.venue_id,
                    ReservationSlot.slot_date == slot_date,
                    ReservationSlot.slot_hour == hour,
                )
            )
            available_future_hours.append(
                and_(Venue.open_hour <= hour, Venue.close_hour > hour, ~slot_is_taken)
            )
        conditions.append(or_(*available_future_hours) if available_future_hours else false())
    return conditions


def _search_from():
    return (
        select(Venue.venue_id)
        .select_from(Venue)
        .join(Category, Category.category_id == Venue.category_id)
        .join(Region, Region.region_id == Venue.region_id)
    )


def count_search_venues(
    db: Session,
    *,
    q: str | None,
    category: str | None,
    sido: str | None,
    sigungu: str | None,
    people: int | None,
    facility_ids: list[int],
    slot_date: date,
    start_hour: int | None,
    hours: int | None,
    now_only: bool,
    current_hour: int,
) -> int:
    """모든 검색 조건을 적용한 뒤 페이지를 자르기 전 전체 건수를 센다."""
    conditions = _search_conditions(
        q=q,
        category=category,
        sido=sido,
        sigungu=sigungu,
        people=people,
        facility_ids=facility_ids,
        slot_date=slot_date,
        start_hour=start_hour,
        hours=hours,
        now_only=now_only,
        current_hour=current_hour,
    )
    return (
        db.scalar(_search_from().with_only_columns(func.count(Venue.venue_id)).where(*conditions))
        or 0
    )


def list_search_venues(
    db: Session,
    *,
    q: str | None,
    category: str | None,
    sido: str | None,
    sigungu: str | None,
    people: int | None,
    facility_ids: list[int],
    slot_date: date,
    start_hour: int | None,
    hours: int | None,
    now_only: bool,
    current_hour: int,
    sort: str,
    page: int,
    size: int,
    popular_since: datetime,
) -> list[RowMapping]:
    """정렬·페이지를 SQL에 적용한 검색 항목을 읽는다."""
    conditions = _search_conditions(
        q=q,
        category=category,
        sido=sido,
        sigungu=sigungu,
        people=people,
        facility_ids=facility_ids,
        slot_date=slot_date,
        start_hour=start_hour,
        hours=hours,
        now_only=now_only,
        current_hour=current_hour,
    )
    popularity = None
    if sort == "popular":
        popularity = (
            select(Reservation.venue_id, func.count(Reservation.reservation_id).label("count"))
            .where(
                Reservation.created_at >= popular_since,
                Reservation.status != "cancelled",
                Reservation.reserve_date >= func.date(Reservation.created_at),
            )
            .group_by(Reservation.venue_id)
            .subquery()
        )

    query = (
        select(
            Venue.venue_id,
            Venue.name,
            Venue.capacity_max,
            Venue.price_per_hour,
            Venue.open_hour,
            Venue.close_hour,
            Venue.created_at,
            Category.code.label("category_code"),
            Category.name.label("category_name"),
            Region.sido,
            Region.sigungu,
            func.coalesce(_rating_view.c.rating_avg, 0).label("rating_avg"),
            func.coalesce(_rating_view.c.review_count, 0).label("review_count"),
        )
        .select_from(Venue)
        .join(Category, Category.category_id == Venue.category_id)
        .join(Region, Region.region_id == Venue.region_id)
        .outerjoin(_rating_view, _rating_view.c.venue_id == Venue.venue_id)
        .where(*conditions)
    )
    if popularity is not None:
        query = query.outerjoin(popularity, popularity.c.venue_id == Venue.venue_id)
        popularity_count = func.coalesce(popularity.c.count, 0)
        query = query.order_by(popularity_count.desc(), Venue.venue_id.asc())
    elif sort == "price":
        query = query.order_by(Venue.price_per_hour.asc(), Venue.venue_id.asc())
    elif sort == "rating":
        query = query.order_by(_rating_view.c.rating_avg.desc(), Venue.venue_id.asc())
    else:
        query = query.order_by(Venue.venue_id.asc())

    return list(db.execute(query.offset((page - 1) * size).limit(size)).mappings())


def list_facilities_by_venues(db: Session, venue_ids: list[int]) -> dict[int, list[str]]:
    """검색 결과 공간들의 시설 이름을 공간 ID 순서로 한 번에 읽는다."""
    if not venue_ids:
        return {}
    query = (
        select(VenueFacility.venue_id, Facility.name)
        .join(Facility, Facility.facility_id == VenueFacility.facility_id)
        .where(VenueFacility.venue_id.in_(venue_ids))
        .order_by(VenueFacility.venue_id, Facility.facility_id)
    )
    result: dict[int, list[str]] = {}
    for venue_id, name in db.execute(query):
        result.setdefault(venue_id, []).append(name)
    return result


def list_images_by_venues(db: Session, venue_ids: list[int]) -> dict[int, list[str]]:
    """검색 결과 공간들의 정렬된 그림을 한 번에 읽는다."""
    if not venue_ids:
        return {}
    query = (
        select(VenueImage.venue_id, VenueImage.url)
        .where(VenueImage.venue_id.in_(venue_ids))
        .order_by(VenueImage.venue_id, VenueImage.sort_order, VenueImage.image_id)
    )
    result: dict[int, list[str]] = {}
    for venue_id, url in db.execute(query):
        result.setdefault(venue_id, []).append(url)
    return result


def get_detail(db: Session, venue_id: int) -> RowMapping | None:
    """활성 공간과 유형·지역·평점을 읽는다. 후기 본문은 A API가 담당한다."""
    query = (
        select(
            Venue.venue_id,
            Venue.name,
            Venue.description,
            Venue.notice,
            Venue.capacity_max,
            Venue.price_per_hour,
            Venue.min_hours,
            Venue.open_hour,
            Venue.close_hour,
            Venue.created_at,
            Category.code.label("category_code"),
            Category.name.label("category_name"),
            Region.sido,
            Region.sigungu,
            func.coalesce(_rating_view.c.rating_avg, 0).label("rating_avg"),
            func.coalesce(_rating_view.c.review_count, 0).label("review_count"),
        )
        .select_from(Venue)
        .join(Category, Category.category_id == Venue.category_id)
        .join(Region, Region.region_id == Venue.region_id)
        .outerjoin(_rating_view, _rating_view.c.venue_id == Venue.venue_id)
        .where(Venue.venue_id == venue_id, Venue.is_active.is_(True))
    )
    return db.execute(query).mappings().one_or_none()


def get_slot_context(db: Session, venue_id: int) -> RowMapping | None:
    """날짜·시간 칸 조회에 필요한 활성 공간의 영업시간·최소 이용시간만 읽는다."""
    query = select(Venue.venue_id, Venue.open_hour, Venue.close_hour, Venue.min_hours).where(
        Venue.venue_id == venue_id, Venue.is_active.is_(True)
    )
    return db.execute(query).mappings().one_or_none()


def list_facilities(db: Session, venue_id: int) -> list[RowMapping]:
    """이미지와 따로 조회해 시설 수만큼 갤러리 행이 중복되지 않게 한다."""
    query = (
        select(Facility.facility_id, Facility.name)
        .select_from(VenueFacility)
        .join(Facility, Facility.facility_id == VenueFacility.facility_id)
        .where(VenueFacility.venue_id == venue_id)
        .order_by(Facility.facility_id)
    )
    return list(db.execute(query).mappings())


def list_images(db: Session, venue_id: int) -> list[str]:
    """정렬 값이 같으면 이미지 ID로 순서를 고정한다."""
    query = (
        select(VenueImage.url)
        .where(VenueImage.venue_id == venue_id)
        .order_by(VenueImage.sort_order, VenueImage.image_id)
    )
    return list(db.scalars(query))
