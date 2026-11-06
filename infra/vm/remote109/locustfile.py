"""F-12·20·22: 실제 DB에 쓰지 않는 원격 시스템 읽기 부하 시험."""

import os

from locust import HttpUser, between, task
from locust.exception import StopUser

from app.core.clock import get_today


class ReadOnlyBrowser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        key = os.environ.get("SPACE_SYNTHETIC_KEY")
        if not key:
            raise StopUser("합성 데이터 키가 없어 시험을 시작하지 않습니다.")
        self.client.headers.update({"X-Synthetic": "1", "X-Synthetic-Key": key})
        self.venue_id = None

    @task(5)
    def search(self):
        with self.client.get(
            "/api/venues",
            params={"page": 1, "size": 10},
            name="F-12 공간 검색",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            items = response.json().get("items", [])
            if items:
                self.venue_id = items[0]["venue_id"]

    @task(2)
    def catalog(self):
        self.client.get("/api/categories", name="F-10 유형 조회")

    @task(2)
    def detail(self):
        if self.venue_id:
            self.client.get(f"/api/venues/{self.venue_id}", name="F-20 공간 상세")

    @task(1)
    def slots(self):
        if self.venue_id:
            self.client.get(
                f"/api/venues/{self.venue_id}/slots",
                params={"date": get_today().isoformat()},
                name="F-22 시간 칸",
            )
