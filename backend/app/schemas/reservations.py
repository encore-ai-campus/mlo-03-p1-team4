"""F-30~34 예약·모의 결제·취소와 F-40 내역 조회 요청·응답."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.schemas.catalog import CategoryRead
from app.schemas.venues import VenueRegionRead

type ReservationStatus = Literal["confirmed", "completed", "cancelled"]


class ReservationEventContext(BaseModel):
    """선택적 브라우저 문맥. 상품·인증 정보는 서버가 별도로 구성한다."""

    model_config = ConfigDict(extra="ignore")

    user: dict | None = None
    site: dict | None = None
    acquisition: dict | None = None
    page: dict | None = None
    navigation: dict | None = None


class ReservationCancel(BaseModel):
    """본문 없는 기존 취소 요청도 유지한다."""

    model_config = ConfigDict(extra="forbid")

    event_context: ReservationEventContext | None = None


class ReservationCreate(BaseModel):
    """결제 버튼 한 번에 예약할 공간과 이용 조건을 받는다."""

    model_config = ConfigDict(extra="forbid")

    venue_id: Annotated[StrictInt, Field(ge=1, le=9223372036854775807)]
    date: date
    start_hour: StrictInt
    hours: StrictInt
    headcount: Annotated[StrictInt, Field(ge=1)]
    # 잘못된 수단은 공통 VALIDATION 대신 명세의 INVALID_METHOD로 반환한다.
    method: str
    event_context: ReservationEventContext | None = None


class PaymentRead(BaseModel):
    method: Literal["transfer", "card", "phone"]
    status: Literal["paid", "refunded"]
    paid_at: datetime


class ReservationCreateRead(BaseModel):
    reservation_id: int
    status: Literal["confirmed", "completed", "cancelled"]
    venue_id: int
    date: date
    start_hour: int
    end_hour: int
    headcount: int
    total_price: int
    payment: PaymentRead


class ReservationPaymentRead(BaseModel):
    """내 예약에서 결제·환불 시각을 함께 표시한다."""

    method: Literal["transfer", "card", "phone"]
    status: Literal["paid", "refunded"]
    paid_at: datetime
    refunded_at: datetime | None


class ReservationVenueRead(BaseModel):
    """예약 공간과 마이페이지 카드에 필요한 이름을 반환한다."""

    venue_id: int
    name: str
    category: CategoryRead
    region: VenueRegionRead
    image: str


class ReservationRead(BaseModel):
    """내 예약 목록·상세의 공통 응답."""

    reservation_id: int
    status: ReservationStatus
    venue_id: int
    date: date
    start_hour: int
    end_hour: int
    headcount: int
    total_price: int
    created_at: datetime
    payment: ReservationPaymentRead
    venue: ReservationVenueRead
    can_cancel: bool
    # #45 확정: 삭제된 후기 ID도 유지하고, 작성한 적이 없을 때만 null이다.
    review_id: int | None


class ReservationCancelPaymentRead(BaseModel):
    method: Literal["transfer", "card", "phone"]
    status: Literal["refunded"]
    paid_at: datetime
    refunded_at: datetime


class ReservationCancelRead(BaseModel):
    reservation_id: int
    status: Literal["cancelled"]
    total_price: int
    payment: ReservationCancelPaymentRead
    can_cancel: Literal[False]
