"""잠금 회귀 검증에서만 띄우는 하위 프로세스. 접속정보를 출력하지 않는다."""

import argparse
import os
from threading import Event

from tests.db_lock import DatabaseTestLock, DatabaseTestLockError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--hold", type=float, default=0)
    args = parser.parse_args()
    try:
        with DatabaseTestLock(
            os.environ["CHECK_DB_URL"],
            name=args.name,
            timeout=args.timeout,
            on_wait=lambda: print("waiting", flush=True),
        ):
            print("acquired", flush=True)
            Event().wait(args.hold)
        print("released", flush=True)
        return 0
    except DatabaseTestLockError:
        print("lock-error", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
