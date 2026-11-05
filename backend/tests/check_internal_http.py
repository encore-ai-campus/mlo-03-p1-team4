"""F-61 별도 HTTP 검증: 공식 앱·Postman·로컬 MariaDB를 연결한다.

CHECK_DB_URL은 로컬 spacecube_test만 허용한다. 임시 내부 키는 자식 프로세스와
자동 삭제하는 Postman 환경에만 두고, 이번 실행의 synthetic 공간만 정리한다.
"""

import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
from check_reservation_http import postman_command
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[2]


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
    source_id = uuid4().hex
    key = secrets.token_urlsafe(32)
    process = None
    try:
        with engine.connect() as db:
            assert db.scalar(text("SELECT DATABASE()")) == "spacecube_test"
            version = db.scalar(text("SELECT VERSION()"))
            assert "MariaDB" in version
            region = db.execute(
                text("SELECT sido,sigungu FROM regions ORDER BY region_id LIMIT 1")
            ).one()
            category = db.scalar(text("SELECT code FROM categories ORDER BY category_id LIMIT 1"))
            facility = db.scalar(text("SELECT name FROM facilities ORDER BY facility_id LIMIT 1"))
            assert category and facility, "기존 0001·seed 적용이 필요합니다."
            print(f"Local test DB: {version}")
        ignored_facility = "HTTP 검증용 미등록 시설"
        body = {
            "source_site": "synthetic",
            "source_id": source_id,
            "name": "내부 HTTP 검증 공간",
            "category_code": category,
            "sido": region.sido,
            "sigungu": region.sigungu,
            "capacity_max": 4,
            "price_per_hour": 10000,
            "facilities": [facility, ignored_facility],
            "images": ["art:group-0"],
        }
        changed = {
            **body,
            "name": "내부 HTTP 변경 공간",
            "price_per_hour": 15000,
            "facilities": [],
            "images": ["art:cafe-1"],
        }
        with tempfile.TemporaryDirectory(prefix="spacecube-internal-http-") as temp:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            base_url = f"http://127.0.0.1:{port}"
            env = dict(os.environ)
            env.update(
                DB_WRITE_URL=os.environ["CHECK_DB_URL"],
                DB_READ_URL=os.environ["CHECK_DB_URL"],
                MONGO_URL="",
                INTERNAL_API_KEY=key,
                LOG_DIR=str(Path(temp) / "logs"),
            )
            process = subprocess.Popen(  # noqa: S603 -- pro_1의 고정 Uvicorn 모듈을 loopback에서 실행한다.
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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
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
                values = {
                    "base_url": base_url,
                    "allow_internal_write": "1",
                    "internal_api_key": key,
                    "venue_json": json.dumps(body),
                    "updated_venue_json": json.dumps(changed),
                    "invalid_venue_json": json.dumps({**body, "source_site": "roovook"}),
                    "ignored_facility": ignored_facility,
                }
                environment = Path(temp) / "Internal.private.environment.yaml"
                lines = ["name: Temporary internal HTTP", "values:"]
                for name, value in values.items():
                    lines += [
                        f"  - key: {name}",
                        f"    value: {json.dumps(value)}",
                        "    enabled: true",
                    ]
                    if name == "internal_api_key":
                        lines.append("    type: secret")
                environment.write_text("\n".join(lines) + "\n", encoding="utf-8")
                result = subprocess.run(  # noqa: S603 -- 설치된 CLI의 고정 로컬 컬렉션을 실행한다.
                    [
                        *command,
                        "collection",
                        "run",
                        str(ROOT / "postman/collections/Internal venues API"),
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
                for sensitive in (key, url.password):
                    if sensitive:
                        output = output.replace(sensitive, "[redacted]")
                print(output)
                assert result.returncode == 0, "Postman 계약 검증 실패"
                with engine.connect() as db:
                    rows = db.execute(
                        text(
                            "SELECT venue_id,name,price_per_hour FROM venues "
                            "WHERE source_site='synthetic' AND source_id=:source"
                        ),
                        {"source": source_id},
                    ).all()
                    assert len(rows) == 1
                    venue_id, name, price = rows[0]
                    assert (name, price) == (changed["name"], 15000)
                    assert (
                        db.scalar(
                            text("SELECT COUNT(*) FROM venue_facilities WHERE venue_id=:id"),
                            {"id": venue_id},
                        )
                        == 0
                    )
                    assert db.execute(
                        text("SELECT url,sort_order FROM venue_images WHERE venue_id=:id"),
                        {"id": venue_id},
                    ).all() == [("art:cafe-1", 0)]
                print("HTTP/DB verified: one source, stable venue ID, replaced facilities/images")
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
        with engine.begin() as db:
            db.execute(
                text("DELETE FROM venues WHERE source_site='synthetic' AND source_id=:source"),
                {"source": source_id},
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
        engine.dispose()
        print("Temporary internal test rows removed")


if __name__ == "__main__":
    main()
