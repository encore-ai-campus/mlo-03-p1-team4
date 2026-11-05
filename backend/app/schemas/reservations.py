"""F-30~32 예약·모의 결제 요청과 응답."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt


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
