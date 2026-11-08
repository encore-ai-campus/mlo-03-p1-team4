"""#99 공간 보충의 primary 조회를 모은 저장소."""

from sqlalchemy import select

from app.models.catalog import Category, Facility, Region
from app.models.venue import Venue, VenueFacility, VenueImage


def load_snapshot(db):
    """활성 수 집계와 참고 속성에 필요한 공간만 primary에서 읽는다."""
    rows = db.execute(
        select(
            Venue.venue_id,
            Venue.source_site,
            Venue.source_id,
            Venue.is_active,
            Venue.capacity_max,
            Venue.price_per_hour,
            Venue.min_hours,
            Venue.open_hour,
            Venue.close_hour,
            Category.code.label("category_code"),
            Region.sido,
            Region.sigungu,
        )
        .join(Category, Category.category_id == Venue.category_id)
        .join(Region, Region.region_id == Venue.region_id)
        .order_by(Venue.venue_id)
    ).mappings()
    venues = [dict(row) for row in rows]
    if not venues:
        return {"venues": []}

    venue_ids = [row["venue_id"] for row in venues]
    facilities = db.execute(
        select(VenueFacility.venue_id, Facility.name)
        .join(Facility, Facility.facility_id == VenueFacility.facility_id)
        .where(VenueFacility.venue_id.in_(venue_ids))
        .order_by(VenueFacility.venue_id, Facility.name)
    )
    facility_map = {}
    for venue_id, name in facilities:
        facility_map.setdefault(venue_id, []).append(name)

    for row in venues:
        row["verified"] = row["source_site"] in {"spacecloud", "shareit"}
        row["facilities"] = facility_map.get(row["venue_id"], [])
    return {"venues": venues}


def load_catalog(db):
    """내부 API가 사용하는 유형·지역·시설 이름을 primary에서 읽는다."""
    return {
        "categories": set(db.scalars(select(Category.code))),
        "regions": set(db.execute(select(Region.sido, Region.sigungu)).tuples()),
        "facilities": set(db.scalars(select(Facility.name))),
    }


def get_synthetic_source(db, source_id):
    """재개 시 같은 출처 공간의 상태·속성을 대조한다."""
    row = (
        db.execute(
            select(
                Venue.venue_id,
                Venue.source_id,
                Venue.is_active,
                Venue.name,
                Venue.description,
                Venue.notice,
                Venue.capacity_max,
                Venue.price_per_hour,
                Venue.min_hours,
                Venue.open_hour,
                Venue.close_hour,
                Category.code.label("category_code"),
                Region.sido,
                Region.sigungu,
            )
            .join(Category, Category.category_id == Venue.category_id)
            .join(Region, Region.region_id == Venue.region_id)
            .where(Venue.source_site == "synthetic", Venue.source_id == source_id)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    result = dict(row)
    venue_id = result["venue_id"]
    result["facilities"] = list(
        db.scalars(
            select(Facility.name)
            .join(VenueFacility, VenueFacility.facility_id == Facility.facility_id)
            .where(VenueFacility.venue_id == venue_id)
            .order_by(Facility.name)
        )
    )
    result["images"] = list(
        db.scalars(
            select(VenueImage.url)
            .where(VenueImage.venue_id == venue_id)
            .order_by(VenueImage.sort_order, VenueImage.image_id)
        )
    )
    return result
