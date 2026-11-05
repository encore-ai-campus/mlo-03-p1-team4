"""F-61: 출처별 공간·시설·그림을 같은 primary 트랜잭션에 저장한다."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import get_now
from app.core.errors import AppError
from app.repositories import catalog_repo, venue_repo
from app.schemas.internal import InternalVenueRead, InternalVenueUpsert


def upsert_venue(db: Session, body: InternalVenueUpsert) -> tuple[InternalVenueRead, int]:
    """신규는 201, 같은 출처의 재전송·갱신은 변경량과 관계없이 200이다."""
    try:
        category_id = catalog_repo.get_category_id(db, body.category_code)
        if category_id is None:
            raise AppError(
                "UNKNOWN_CATEGORY",
                "등록되지 않은 유형",
                400,
                {"category_code": body.category_code},
            )
        region_id = catalog_repo.get_region_id(db, body.sido, body.sigungu)
        if region_id is None:
            raise AppError(
                "UNKNOWN_REGION",
                "등록되지 않은 지역",
                400,
                {"sido": body.sido, "sigungu": body.sigungu},
            )

        facility_ids = set()
        ignored = []
        for name in dict.fromkeys(body.facilities):
            facility_id = catalog_repo.get_facility_id(db, name)
            if facility_id is None:
                ignored.append(name)
            else:
                facility_ids.add(facility_id)
        values = body.model_dump(
            exclude={"category_code", "sido", "sigungu", "facilities", "images"}
        )
        values.update(category_id=category_id, region_id=region_id, created_at=get_now())
        try:
            venue_id = venue_repo.insert_source(db, values)
            status = 201
        except IntegrityError as error:
            if not error.orig.args or error.orig.args[0] != 1062:
                raise
            db.rollback()
            # FOUND_ROWS 환경에서 무변경 갱신도 rowcount=1이다. 신규 판정을 rowcount에 맡기지 않는다.
            venue_id = venue_repo.upsert_source(db, values)
            status = 200

        venue_repo.replace_facilities_and_images(db, venue_id, sorted(facility_ids), body.images)
        db.commit()
        return InternalVenueRead(venue_id=venue_id, ignored_facilities=ignored), status
    except Exception:
        db.rollback()
        raise
