"""F-40·50: B 내 예약 응답에 제공할 A 후기 ID 일괄 조회 계약."""

from sqlalchemy import event, text
from sqlalchemy.orm import Session
from test_reservation_dependencies import NOW

from app.repositories import review_repo

pytest_plugins = ("test_reservation_dependencies",)


def test_get_review_ids_empty_skips_sql():
    class NoQuerySession:
        def execute(self, *_args, **_kwargs):
            raise AssertionError("빈 예약 목록은 SQL을 실행하면 안 됩니다.")

    assert review_repo.get_review_ids(NoQuerySession(), []) == {}
    assert review_repo.get_review_ids(NoQuerySession(), ()) == {}


def test_get_review_ids_includes_active_and_deleted_once(connection, sample):
    user_id, _, create_reservation = sample
    no_review = create_reservation()
    active = create_reservation()
    deleted = create_reservation()
    another_active = create_reservation()

    def add_review(reservation_id, *, deleted_at=None):
        return connection.execute(
            text(
                "INSERT INTO reviews (reservation_id,user_id,rating,content,created_at,deleted_at) "
                "VALUES (:reservation,:user,5,'일괄 조회 검증',:created,:deleted)"
            ),
            {
                "reservation": reservation_id,
                "user": user_id,
                "created": NOW,
                "deleted": deleted_at,
            },
        ).lastrowid

    active_review_id = add_review(active)
    deleted_review_id = add_review(deleted, deleted_at=NOW)
    another_review_id = add_review(another_active)

    statements = []

    def count_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
        transaction = db.begin()
        commits = []
        rollbacks = []
        event.listen(db, "after_commit", lambda _session: commits.append(True))
        event.listen(db, "after_rollback", lambda _session: rollbacks.append(True))
        event.listen(connection, "before_cursor_execute", count_sql)
        try:
            result = review_repo.get_review_ids(
                db, [no_review, active, deleted, another_active, active, deleted]
            )
        finally:
            event.remove(connection, "before_cursor_execute", count_sql)

        assert result == {
            active: active_review_id,
            deleted: deleted_review_id,
            another_active: another_review_id,
        }
        assert len([sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]) == 1
        assert db.get_transaction() is transaction and transaction.is_active
        assert commits == rollbacks == []
