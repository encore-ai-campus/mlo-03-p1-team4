"""db/migrations/0001_init.sql로 spacecube_test를 새로 만들고 제약을 시험한다 (11-04).

실행: conda run -n pro_1 --no-capture-output python db/tests/check_ddl.py
- 접속 정보는 backend/.env의 DB_WRITE_URL에서 읽고, 비밀번호는 환경 변수로만 클라이언트에 넘긴다.
  다른 DB를 보려면 CHECK_DB_URL(예: 로컬 compose 127.0.0.1:3308, RDS)을 준다. DB 이름은 spacecube_test.
- spacecube_test만 지우고 다시 만든다. 다른 스키마는 건드리지 않는다.
- MariaDB 클라이언트 경로는 MARIADB_BIN(없으면 기본 설치 경로).
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "db" / "migrations" / "0001_init.sql"
ENV_FILE = ROOT / "backend" / ".env"
TEST_DB = "spacecube_test"
BIN = os.environ.get("MARIADB_BIN", r"C:\Program Files\MariaDB 11.8\bin\mariadb.exe")
STRICT = "STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION"


def load_url():
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            env[key] = value
    raw = os.environ.get("CHECK_DB_URL") or env["DB_WRITE_URL"]  # 다른 DB(로컬 compose·RDS)를 볼 때
    url = urlparse(raw.replace("mysql+pymysql", "mysql"))
    assert url.path.strip("/") == TEST_DB, "DB_WRITE_URL은 spacecube_test를 가리켜야 함"
    return url


URL = load_url()
CHILD_ENV = dict(os.environ, MYSQL_PWD=unquote(URL.password or ""))


def client(db=TEST_DB):
    args = [BIN, "--protocol=TCP", "-h", URL.hostname, "-P", str(URL.port or 3306)]
    args += ["-u", unquote(URL.username), "--default-character-set=utf8mb4", "-N", "-B"]
    return args + ([db] if db else [])


def run(sql, db=TEST_DB):
    """(오류 코드, 출력, 오류 줄). 세션은 STRICT로 시작한다(앱 연결과 같게)."""
    full = f"SET SESSION sql_mode='{STRICT}'; {sql}"
    r = subprocess.run(  # noqa: S603 로컬 MariaDB 클라이언트, 인자는 이 파일의 고정 SQL
        [*client(db), "-e", full], env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8"
    )
    m = re.search(r"ERROR (\d+)[^\n]*", r.stderr)
    return (int(m.group(1)) if m else 0), r.stdout.strip(), (m.group(0) if m else "")


def build_schema():
    ddl = DDL.read_text(encoding="utf-8")
    code, _, err = run(
        f"DROP DATABASE IF EXISTS {TEST_DB};"
        f" CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        db=None,
    )
    assert code == 0, err
    r = subprocess.run(  # noqa: S603 로컬 MariaDB 클라이언트에 저장소의 마이그레이션 파일을 넣음
        client(TEST_DB), input=ddl, env=CHILD_ENV, capture_output=True, text=True, encoding="utf-8"
    )
    assert r.returncode == 0, r.stderr
    _, tables, _ = run(
        "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'"
    )
    _, views, _ = run("SELECT COUNT(*) FROM information_schema.VIEWS WHERE TABLE_SCHEMA=DATABASE()")
    _, checks, _ = run(
        "SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE()"
    )
    print(f"스키마: 표 {tables} · 뷰 {views} · CHECK {checks}")


U = "INSERT INTO users (email,password_hash,name,phone,birth,gender_digit,terms_agreed_at,privacy_agreed_at) VALUES "
V = "INSERT INTO venues (region_id,category_id,name,capacity_max,price_per_hour,min_hours,open_hour,close_hour) VALUES "
R = "INSERT INTO reservations (user_id,venue_id,reserve_date,start_hour,end_hour,headcount,total_price) VALUES "

SEED = f"""
INSERT INTO regions (sido,sigungu) VALUES ('서울','관악구');
INSERT INTO categories (code,name) VALUES ('studyroom','스터디룸'),('lectureroom','강의실');
INSERT INTO facilities (name) VALUES ('와이파이');
{U}('a@example.com','x','김스터디','010-0000-0000','990315','1',NOW(),NOW()),
   ('b@example.com','x','이스터디',NULL,'050101','3',NOW(),NOW());
{V}(1,1,'관악구 스터디룸 1',6,10000,1,9,23);
INSERT INTO venue_facilities VALUES (1,1);
INSERT INTO venue_images (venue_id,url) VALUES (1,'art:group-0');
"""  # noqa: S608 시험용 고정 데이터


def book(user_id, day, start, hours, method="card", sleep=0):
    """결제 버튼 한 번 = 예약·칸·결제를 한 트랜잭션으로."""
    slots = ",".join(f"(1,'{day}',{h},@r)" for h in range(start, start + hours))
    return (
        f"START TRANSACTION; {R}({user_id},1,'{day}',{start},{start + hours},2,{10000 * hours});"  # noqa: S608 값은 이 파일의 정수·고정 문자열
        f" SET @r=LAST_INSERT_ID(); INSERT INTO reservation_slots VALUES {slots};"
        f" INSERT INTO payments (reservation_id,method) VALUES (@r,'{method}');"
        + (f" SELECT SLEEP({sleep});" if sleep else "")
        + " COMMIT;"
    )


CASES = [
    (
        "생년월일 형식(6자리 숫자)",
        f"{U}('c@example.com','x','가','010','99031','1',NOW(),NOW())",
        4025,
    ),
    ("성별 구분 1~4", f"{U}('c@example.com','x','가','010','990315','5',NOW(),NOW())", 4025),
    (
        "필수 동의 시각 없음",
        "INSERT INTO users (email,password_hash,name,birth,gender_digit) VALUES ('c@example.com','x','가','990315','1')",
        1364,
    ),
    ("이메일 중복", f"{U}('a@example.com','x','가','010','990315','1',NOW(),NOW())", 1062),
    ("영업 시작 8시", f"{V}(1,1,'v',6,10000,1,8,23)", 4025),
    ("영업 끝 24시", f"{V}(1,1,'v',6,10000,1,9,24)", 4025),
    ("최소 이용 5시간", f"{V}(1,1,'v',6,10000,5,9,23)", 4025),
    ("없는 지역(외래키)", f"{V}(99,1,'v',6,10000,1,9,23)", 1452),
    ("정상 예약 13~15시(예약·칸·결제 한 트랜잭션)", book(1, "2026-11-10", 13, 2), 0),
    ("예약 시작 8시", f"{R}(1,1,'2026-11-10',8,10,1,1)", 4025),
    ("예약 끝 24시", f"{R}(1,1,'2026-11-10',21,24,1,1)", 4025),
    ("예약 5시간", f"{R}(1,1,'2026-11-10',9,14,1,1)", 4025),
    ("같은 칸 두 번째 예약", book(2, "2026-11-10", 14, 2), 1062),
    (
        "칸 날짜가 예약 날짜와 다름(복합 외래키)",
        "INSERT INTO reservation_slots VALUES (1,'2026-11-11',16,1)",
        1452,
    ),
    ("칸 23시", "INSERT INTO reservation_slots VALUES (1,'2026-11-10',23,1)", 4025),
    ("결제수단 cash", "INSERT INTO payments (reservation_id,method) VALUES (1,'cash')", 1265),
    ("예약당 결제 1건", "INSERT INTO payments (reservation_id,method) VALUES (1,'phone')", 1062),
    (
        "환불인데 refunded_at 없음",
        "UPDATE payments SET status='refunded' WHERE reservation_id=1",
        4025,
    ),
    (
        "별점 6",
        "INSERT INTO reviews (reservation_id,user_id,rating,content) VALUES (1,1,6,'x')",
        4025,
    ),
    (
        "정상 후기",
        "INSERT INTO reviews (reservation_id,user_id,rating,content) VALUES (1,1,5,'화이트보드가 넓어요')",
        0,
    ),
    (
        "예약당 후기 1개",
        "INSERT INTO reviews (reservation_id,user_id,rating,content) VALUES (1,1,4,'x')",
        1062,
    ),
    (
        "예약 상태 pending 없음",
        "UPDATE reservations SET status='pending' WHERE reservation_id=1",
        1265,
    ),
]

CHECKS = [
    ("1062 뒤 남은 예약 수", "SELECT COUNT(*) FROM reservations", "1"),
    (
        "남은 칸",
        "SELECT GROUP_CONCAT(slot_hour ORDER BY slot_hour) FROM reservation_slots",
        "13,14",
    ),
    (
        "평점 뷰",
        "SELECT CONCAT(venue_id,' ',rating_avg,' ',review_count) FROM v_venue_rating",
        "1 5.0 1",
    ),
    ("한글 저장", "SELECT name FROM venues WHERE venue_id=1", "관악구 스터디룸 1"),
]

CANCEL = (
    "START TRANSACTION; UPDATE reservations SET status='cancelled' WHERE reservation_id=1;"
    " DELETE FROM reservation_slots WHERE reservation_id=1;"
    " UPDATE payments SET status='refunded', refunded_at=NOW() WHERE reservation_id=1; COMMIT;"
)


def race():
    """A가 칸을 잡고 3초 뒤 커밋, B는 1초 뒤 같은 칸 → B는 A 커밋까지 기다렸다가 1062."""
    t0 = time.time()
    full = f"SET SESSION sql_mode='{STRICT}'; " + book(1, "2026-11-20", 18, 2, sleep=3)
    a = subprocess.Popen(  # noqa: S603 로컬 MariaDB 클라이언트, 고정 SQL
        [*client(), "-e", full],
        env=CHILD_ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(1)
    b_code, _, _ = run(book(2, "2026-11-20", 18, 2))
    b_done = time.time() - t0
    a.communicate()
    _, left, _ = run("SELECT COUNT(*) FROM reservations WHERE reserve_date='2026-11-20'")
    ok = a.returncode == 0 and b_code == 1062 and b_done >= 2.5 and left == "1"
    print(
        f"{'OK  ' if ok else 'FAIL'} 동시 결제: A 성공, B {b_code}({b_done:.1f}s에 끝남), 남은 예약 {left}"
    )
    return ok


def main():
    build_schema()
    code, _, err = run(SEED)
    assert code == 0, err
    fails = 0
    for title, sql, want in CASES:
        code, _, err = run(sql)
        fails += code != want
        print(
            f"{'OK  ' if code == want else 'FAIL'} {title}: 기대 {want} / 실제 {code} {'' if code == want else err[:100]}"
        )
    for title, sql, want in CHECKS:
        code, out, _ = run(sql)
        ok = code == 0 and out == want
        fails += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {title}: {out}")
    for title, sql in [
        ("취소(칸 삭제 + 환불)", CANCEL),
        ("취소한 칸을 다른 사람이 다시 예약", book(2, "2026-11-10", 14, 2, "transfer")),
    ]:
        code, _, err = run(sql)
        fails += code != 0
        print(f"{'OK  ' if code == 0 else 'FAIL'} {title} {err}")
    fails += not race()
    print(f"실패 {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
