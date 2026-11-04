# models — SQLAlchemy 모델 (DDL과 같게)

표를 파이썬 클래스로 옮긴 것입니다. **표를 만드는 곳이 아닙니다.** 표는 `db/migrations/*.sql`(지금 `0001_init.sql`)이 만들고, 모델은 그 DDL과 이름·타입·NULL 여부를 똑같이 맞춥니다. `Base.metadata.create_all()`은 쓰지 않습니다.

| 파일 (예정) | 담당 | 표 |
| --- | --- | --- |
| `base.py` | A | `class Base(DeclarativeBase)` 하나 |
| `user.py` | A | users |
| `review.py` | A | reviews |
| `catalog.py` | B | regions, categories, facilities |
| `venue.py` | B | venues, venue_facilities, venue_images |
| `reservation.py` | B | reservations, reservation_slots, payments |

- 크롤러가 쓰는 `crawl_jobs`, 뷰 `v_venue_rating`은 모델을 두지 않고 리포지토리에서 SQL로 읽습니다.
- SQLAlchemy 2.0 방식: `Mapped[int] = mapped_column(primary_key=True)`. ENUM은 DDL 값 그대로(`Enum("confirmed", "completed", "cancelled", native_enum=True)`).
- 복합 외래키(`reservation_slots` → `reservations`)도 `ForeignKeyConstraint`로 적어 둡니다. 실제 제약은 DB가 지킵니다.
- 마이그레이션이 바뀌면 같은 커밋에서 모델도 고칩니다. `backend/tests/test_models_match_db.py`가 어긋남을 잡습니다.
