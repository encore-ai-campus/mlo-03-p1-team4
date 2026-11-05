"""목록 응답의 공통 모양.

사용: A·B 목록 라우터가 페이지 입력을 검증하고 목록 응답을 만든다.
"""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    page: int
    size: int
    total: int


class Pagination(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=50)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def get_pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> Pagination:
    return Pagination(page=page, size=size)


def paginate(items, page: int, size: int, total: int) -> dict:
    return {"items": items, "page": page, "size": size, "total": total}
