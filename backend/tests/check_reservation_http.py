"""F-30~32 별도 HTTP 검증: 공식 앱·실제 인증·Postman 컬렉션·MariaDB를 연결한다.

pro_1에서 실행하며 CHECK_DB_URL은 로컬 spacecube_test만 허용한다.
임시 가상 회원·공간과 예약은 생성한 ID로만 정리한다. 비밀값은 출력하지 않는다.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.clock import get_today  # noqa: E402 -- 저장소 앱 경로를 먼저 추가한다.


def postman_command() -> list[str]:
    """WindowsApps 별칭 대신 설치된 Node·Postman CLI 실행 파일을 찾는다."""
    roots = [Path(os.environ.get("NVM_HOME", "")) / "installs"]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "Author Software/nvm/installs")
    for root in roots:
        for version in sorted(root.glob("v*"), reverse=True):
            node = version / "node.exe"
            entry = version / "node_modules/postman-cli/bin/postman.js"
            if node.is_file() and entry.is_file():
                return [str(node), str(entry)]
    raise RuntimeError("Postman CLI가 설치된 NVM Node 실행 경로를 찾지 못했습니다.")


def clean_rows(engine, email: str, venue_id: int | None, source_id: str) -> None:
    """이 실행의 가상 회원·공간·예약만 지우고 모두 정리됐는지 확인한다."""
    with engine.begin() as db:
        user_id = db.scalar(
            text("SELECT user_id FROM users WHERE email=:email AND is_synthetic=TRUE"),
            {"email": email},
        )
        if user_id is not None and venue_id is not None:
            ids = db.scalars(
                text(
                    "SELECT reservation_id FROM reservations "
                    "WHERE user_id=:user AND venue_id=:venue AND is_synthetic=TRUE"
                ),
                {"user": user_id, "venue": venue_id},
            ).all()
            for reservation_id in ids:
                for statement in (
                    "DELETE FROM reservation_slots WHERE reservation_id=:id",
                    "DELETE FROM payments WHERE reservation_id=:id",
                    "DELETE FROM reservations WHERE reservation_id=:id",
                ):
                    db.execute(text(statement), {"id": reservation_id})
        if user_id is not None:
            db.execute(
                text("DELETE FROM users WHERE user_id=:id AND email=:email AND is_synthetic=TRUE"),
                {"id": user_id, "email": email},
            )
        if venue_id is not None:
            db.execute(
                text(
                    "DELETE FROM venues WHERE venue_id=:id "
                    "AND source_site='synthetic' AND source_id=:source"
                ),
                {"id": venue_id, "source": source_id},
            )
        assert (
            db.scalar(text("SELECT COUNT(*) FROM users WHERE email=:email"), {"email": email}) == 0
        )
        assert (
            db.scalar(
                text(
                    "SELECT COUNT(*) FROM venues WHERE source_site='synthetic' AND source_id=:source"
                ),
                {"source": source_id},
            )
            == 0
        )


def main() -> None:
    url = make_url(os.environ["CHECK_DB_URL"])
    if (
        url.drivername != "mysql+pymysql"
        or url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise RuntimeError("로컬 MariaDB spacecube_test에서만 실행합니다.")
    command = postman_command()
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    email = f"{uuid4().hex}@example.invalid"
    source_id = uuid4().hex
    password = secrets.token_urlsafe(24) + "aA1!"
    synthetic_key = secrets.token_urlsafe(32)
    jwt_secret = secrets.token_urlsafe(48)
    venue_id = None
    process = None
    today = get_today()
    try:
        with engine.begin() as db:
            assert db.scalar(text("SELECT DATABASE()")) == "spacecube_test"
            version = db.scalar(text("SELECT VERSION()"))
            assert "MariaDB" in version
            print(f"Local test DB: {version}")
            category = db.scalar(text("SELECT MIN(category_id) FROM categories"))
            region = db.scalar(text("SELECT MIN(region_id) FROM regions"))
            assert category is not None and region is not None, "기존 seed.sql 적용이 필요합니다."
            venue_id = db.execute(
                text(
                    "INSERT INTO venues "
                    "(region_id,category_id,name,capacity_max,price_per_hour,min_hours,"
                    "open_hour,close_hour,source_site,source_id) "
                    "VALUES (:region,:category,'예약 HTTP 검증 공간',4,10000,1,9,23,'synthetic',:source)"
                ),
                {"region": region, "category": category, "source": source_id},
            ).lastrowid
        with tempfile.TemporaryDirectory(prefix="spacecube-booking-http-") as temp:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            base_url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            env.update(
                DB_WRITE_URL=os.environ["CHECK_DB_URL"],
                DB_READ_URL=os.environ["CHECK_DB_URL"],
                MONGO_URL="",
                JWT_SECRET=jwt_secret,
                SYNTHETIC_API_KEY=synthetic_key,
                TODAY_OVERRIDE=today.isoformat(),
                BOOKING_FUTURE_DAYS="365",
                LOG_DIR=str(Path(temp) / "logs"),
            )
            process = subprocess.Popen(  # noqa: S603 -- 현재 pro_1 실행기·고정 Uvicorn 인자를 사용한다.
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=ROOT / "backend",
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                with httpx.Client(base_url=base_url, timeout=10, trust_env=False) as client:
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError("임시 API 서버가 기동 중 종료됐습니다.")
                        try:
                            if client.get("/openapi.json").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("임시 API 서버 기동 시간이 초과됐습니다.")
                    signup = client.post(
                        "/auth/signup",
                        headers={"X-Synthetic": "1", "X-Synthetic-Key": synthetic_key},
                        json={
                            "email": email,
                            "password": password,
                            "name": "예약HTTP검증",
                            "phone": "01000010001",
                            "birth": "000101",
                            "gender_digit": "3",
                            "terms_agreed": True,
                            "privacy_agreed": True,
                            "marketing_agreed": False,
                        },
                    )
                    assert signup.status_code == 201, f"Signup status: {signup.status_code}"
                    user_id = signup.json()["user_id"]
                    login = client.post("/auth/login", json={"email": email, "password": password})
                    assert login.status_code == 200, f"Login status: {login.status_code}"
                    token = login.json()["access_token"]
                    values = {
                        "base_url": base_url,
                        "access_token": token,
                        "synthetic_api_key": synthetic_key,
                        "venue_id": str(venue_id),
                        "booking_date": (today + timedelta(days=1)).isoformat(),
                        "start_hour": "13",
                        "hours": "2",
                        "headcount": "2",
                        "method": "card",
                    }
                    environment = Path(temp) / "Local.private.environment.yaml"
                    lines = ["name: Temporary reservation HTTP", "values:"]
                    for key, value in values.items():
                        lines += [
                            f"  - key: {key}",
                            f"    value: {json.dumps(value)}",
                            "    enabled: true",
                        ]
                    environment.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    result = subprocess.run(  # noqa: S603 -- 로컬 설치된 Node·CLI와 고정 컬렉션을 실행한다.
                        [
                            *command,
                            "collection",
                            "run",
                            str(ROOT / "postman/collections/Reservations API"),
                            "--environment",
                            str(environment),
                            "--no-report-events",
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=90,
                    )
                    output = result.stdout + result.stderr
                    for sensitive in (
                        token,
                        password,
                        synthetic_key,
                        jwt_secret,
                        email,
                        url.password,
                    ):
                        if sensitive:
                            output = output.replace(sensitive, "[redacted]")
                    print(output)
                    assert result.returncode == 0, "Postman assertions failed"
                    with engine.connect() as db:
                        rows = db.execute(
                            text(
                                "SELECT reservation_id,status,is_synthetic FROM reservations "
                                "WHERE user_id=:user AND venue_id=:venue"
                            ),
                            {"user": user_id, "venue": venue_id},
                        ).all()
                        assert len(rows) == 1 and rows[0][1:] == ("confirmed", 1)
                        reservation_id = rows[0][0]
                        assert db.scalars(
                            text(
                                "SELECT slot_hour FROM reservation_slots WHERE reservation_id=:id ORDER BY slot_hour"
                            ),
                            {"id": reservation_id},
                        ).all() == [13, 14]
                        assert db.execute(
                            text("SELECT method,status FROM payments WHERE reservation_id=:id"),
                            {"id": reservation_id},
                        ).all() == [("card", "paid")]
                    metrics = client.get("/metrics").text
                    assert 'reservation_total{result="ok"} 1.0' in metrics
                    print(
                        "HTTP/DB verified: one synthetic reservation, two slots, one payment, one success counter"
                    )
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process = None
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        try:
            clean_rows(engine, email, venue_id, source_id)
            print("Temporary test rows removed")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
