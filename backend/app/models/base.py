"""A·B 모델이 공유하는 선언 기반.

사용: A·B SQLAlchemy 모델이 같은 선언 기반을 상속한다.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
