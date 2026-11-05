"""F-12·13·20~22 브라우저 별도 실행기. 기본 pytest 수집에는 포함하지 않는다."""

import os
import shutil
import socket
import subprocess
from datetime import datetime, time
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn
from sqlalchemy.orm import Session
from test_venues import synthetic_venue as synthetic_venue

from app.core.db import get_db_read
from app.main import app
from app.services import venue_service


def test_venue_availability_in_real_browser(synthetic_venue, monkeypatch):
    """임시 Uvicorn에 실제 앱을 띄우고 Chrome으로 확인한 뒤 서버·DB를 정리한다."""
    connection, venue_id, today = synthetic_venue
    monkeypatch.setattr(venue_service, "get_today", lambda: today)
    monkeypatch.setattr(venue_service, "get_now", lambda: datetime.combine(today, time(12, 30)))
    node = shutil.which("node")
    if node is None:
        pytest.fail("설치된 Node 실행 경로를 PATH에 지정해 주세요.")

    def test_read_db():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            yield db

    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_read] = test_read_db
    server = None
    thread = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            listener.listen(128)
            server = uvicorn.Server(
                uvicorn.Config(
                    app,
                    host="127.0.0.1",
                    port=port,
                    lifespan="off",
                    log_level="error",
                    access_log=False,
                )
            )
            thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            deadline = monotonic() + 5
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.02)
            assert server.started, "테스트 API 서버가 시작되지 않았습니다."

            environment = os.environ.copy()
            for key in (
                "CHECK_DB_URL",
                "DB_WRITE_URL",
                "DB_READ_URL",
                "MYSQL_PWD",
                "JWT_SECRET",
                "INTERNAL_API_KEY",
            ):
                environment.pop(key, None)
            result = subprocess.run(  # noqa: S603 로컬 Node와 프로젝트의 브라우저 검사 스크립트만 실행한다.
                [
                    node,
                    str(Path(__file__).with_suffix(".mjs")),
                    f"http://127.0.0.1:{port}",
                    str(venue_id),
                    today.isoformat(),
                ],
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=45,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            print(result.stdout.strip())
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5)
            assert not thread.is_alive(), "테스트 API 서버가 종료되지 않았습니다."
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
