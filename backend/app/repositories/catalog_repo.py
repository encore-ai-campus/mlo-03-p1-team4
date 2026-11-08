"""F-10·11 기준 정보 조회. 읽기 세션은 호출하는 쪽이 넘긴다."""

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.catalog import Category, Facility, Region


def list_categories(db: Session) -> list[Category]:
    """유형을 기본키 순으로 읽어 응답 순서를 일정하게 유지한다."""
    return list(db.scalars(select(Category).order_by(Category.category_id)))


def list_active_regions(db: Session) -> list[Region]:
    """공간 모델 없이 기존 표를 참조하며 공간 수와 관계없이 지역당 한 행만 읽는다."""
    return list(
        db.scalars(
            select(Region)
            .where(
                text(
                    "EXISTS (SELECT 1 FROM venues "
                    "WHERE venues.region_id = regions.region_id AND venues.is_active = TRUE)"
                )
            )
            .order_by(Region.region_id)
        )
    )


def list_facilities(db: Session) -> list[Facility]:
    """시설을 기본키 순으로 읽는다. 공간 연결 여부로 시설을 숨기지 않는다."""
    return list(db.scalars(select(Facility).order_by(Facility.facility_id)))


def get_category_id(db: Session, code: str) -> int | None:
    """내부 등록에서는 활성 공간 유무와 관계없이 seed 유형을 찾는다."""
    return db.scalar(select(Category.category_id).where(Category.code == code))


def get_region_id(db: Session, sido: str, sigungu: str) -> int | None:
    """시·도와 시·군·구를 함께 비교해 등록된 지역만 사용한다."""
    return db.scalar(select(Region.region_id).where(Region.sido == sido, Region.sigungu == sigungu))


def get_facility_id(db: Session, name: str) -> int | None:
    """대소문자 비교 등은 실제 MariaDB 컬럼 collation을 따른다."""
    return db.scalar(select(Facility.facility_id).where(Facility.name == name))
