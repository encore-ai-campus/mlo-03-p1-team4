"""F-20·22 공간 상세·영업시간 SQL. 공개 읽기 세션은 호출자가 전달한다."""

from sqlalchemy import column, func, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.models.catalog import Category, Facility, Region
from app.models.venue import Venue, VenueFacility, VenueImage

# 기존 DB 뷰를 조회식으로만 참조한다. ORM 모델이나 새 표를 만들지 않는다.
_rating_view = table(
    "v_venue_rating", column("venue_id"), column("rating_avg"), column("review_count")
)


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
    """시간 칸 조회에 필요한 활성 공간의 ID·영업시간만 읽는다."""
    query = select(Venue.venue_id, Venue.open_hour, Venue.close_hour).where(
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
