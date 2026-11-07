"""별도 생성기 프로세스에서만 과거 업무 시각과 관측 호출을 치환한다."""

import sys
from contextlib import ExitStack
from unittest.mock import patch

from app.core import clock
from app.services import auth_service, reservation_service, review_service  # noqa: F401 -- 별칭 치환 전 로드


class SilentCounter:
    def labels(self, **labels):
        return self

    def inc(self, amount=1):
        pass


class HistoricalRuntime:
    def __init__(self, now):
        self.now = now
        self.stack = ExitStack()

    def __enter__(self):
        original_now, original_today = clock.get_now, clock.get_today
        try:
            # from app.core.clock import get_now인 사용처도 함께 바꾼다.
            for name, module in list(sys.modules.items()):
                if module is None or not name.startswith("app."):
                    continue
                for attribute, value in list(vars(module).items()):
                    if value is original_now:
                        self.stack.enter_context(patch.object(module, attribute, lambda: self.now))
                    elif value is original_today:
                        self.stack.enter_context(
                            patch.object(module, attribute, lambda: self.now.date())
                        )
            self.stack.enter_context(
                patch.object(reservation_service, "_log_reservation_event", lambda *a, **kw: None)
            )
            self.stack.enter_context(
                patch.object(reservation_service, "reservation_counter", SilentCounter())
            )
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        self.stack.close()
        # get_event_time은 실제 수신 시각/TTL용이므로 치환하지 않는다.
