"""#75 수동 실행 진입점. 기본 동작은 미리보기이며 --apply만 업무 데이터를 쓴다."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from pymongo.uri_parser import parse_uri

from app.core.clock import get_now, get_today
from app.core.config import get_settings
from app.core.db import close_databases, get_engine
from app.core.mongo import close_mongo, get_event_collection

from .events import MongoSink
from .gateway import Gateway, load_venues, seed_lock
from .plan import CATEGORIES, Config, GeneratorError, digest, make_sessions, members
from .runner import Runner
from .runtime import HistoricalRuntime
from .storage import Journal

ROOT = Path(__file__).resolve().parents[2]


def code_identity():
    directory = Path(__file__).parent
    hasher = hashlib.sha256()
    # 서비스 코드가 달라진 재실행도 막는다. 배포 시 backend와 생성기는 같은 checkout이어야 한다.
    files = sorted(directory.glob("*.py")) + sorted((ROOT / "backend" / "app").rglob("*.py"))
    for path in files:
        hasher.update(path.relative_to(ROOT).as_posix().encode())
        hasher.update(path.read_bytes())
    git = shutil.which("git")
    commit = "unavailable"
    if git:
        result = subprocess.run(  # noqa: S603 -- 고정 git 인자, shell 없이 실행
            [git, "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
    return {"commit": commit, "code_sha256": hasher.hexdigest()}


def target_identity(collection):
    url = get_engine().url
    raw = get_settings().mongo_url
    if raw is None:
        raise GeneratorError("MONGO_URL 설정이 필요합니다.")
    mongo = parse_uri(raw.get_secret_value(), validate=True)
    return digest(
        {
            "sql": [url.host, url.port, url.database],
            "mongo": [sorted(mongo["nodelist"]), collection.full_name],
        }
    )


def validate_venues(venues, *, apply):
    if not venues or len({venue["venue_id"] for venue in venues}) != len(venues):
        raise GeneratorError("공간이 없거나 공간 ID가 중복입니다.")
    for venue in venues:
        if (
            venue["category_code"] not in CATEGORIES
            or not 9 <= venue["open_hour"] < venue["close_hour"] <= 23
            or not 1 <= venue["min_hours"] <= min(4, venue["close_hour"] - venue["open_hour"])
            or venue["capacity_max"] < 1
            or venue["price_per_hour"] <= 0
        ):
            raise GeneratorError("공간 스냅샷의 예약 속성이 잘못되었습니다.")
    counts = Counter(venue["category_code"] for venue in venues)
    if apply and any(counts[category] < 6 for category in CATEGORIES):
        raise GeneratorError("DB 담당의 공간 보충(유형별 최소 6개)을 먼저 완료해야 합니다.")
    return dict(counts)


def parser():
    command = argparse.ArgumentParser(description="#75 과거 행동 데이터 생성기")
    command.add_argument("--seed", type=int, required=True)
    command.add_argument("--base-date", type=date.fromisoformat, default=get_today())
    command.add_argument("--users", type=int, default=100)
    command.add_argument("--days", type=int, default=30)
    command.add_argument("--sessions-per-day", type=int, default=42)
    mode = command.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="api1에서 서비스 호출과 MongoDB 적재")
    mode.add_argument(
        "--dry-run", action="store_true", help="DB 쓰기 없이 입력·세션 계획 확인(기본)"
    )
    command.add_argument("--resume", action="store_true", help="원래 manifest와 작업 기록으로 재개")
    command.add_argument(
        "--snapshot", type=Path, help="미리보기용 공간 JSON. --apply와 함께 사용 불가"
    )
    command.add_argument("--output-root", type=Path, default=ROOT / "logs")
    return command


def execute(args):
    config = Config(args.seed, args.base_date, args.users, args.days, args.sessions_per_day)
    if config.base_date > get_today():
        raise GeneratorError("기준일은 실행일 KST 또는 그 이전이어야 합니다.")
    if args.snapshot and args.apply:
        raise GeneratorError("실제 적재는 primary 공간 정보만 사용합니다.")
    if args.resume and not args.apply:
        raise GeneratorError("--resume은 --apply와 함께 사용합니다.")
    directory = args.output_root / f"generator-{config.run_id}"

    if not args.apply:
        venues = (
            json.loads(args.snapshot.read_text(encoding="utf-8"))
            if args.snapshot
            else load_venues()
        )
        counts = validate_venues(venues, apply=False)
        sessions = make_sessions(config)
        return {
            "mode": "dry-run",
            "config": config.document(),
            "run_id": config.run_id,
            "venues": counts,
            "members": dict(Counter(members(config))),
            "sessions": len(sessions),
            "session_plan_sha256": digest(sessions),
            "ready_venues": all(counts.get(category, 0) >= 6 for category in CATEGORIES),
        }

    with seed_lock(config.seed):
        # 같은 seed의 잠금을 확보한 뒤에만 manifest·state를 읽고 쓴다.
        if args.resume:
            original = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            venues = original["venues"]
            if venues != load_venues():
                raise GeneratorError(
                    "공간 스냅샷이 달라졌습니다. 기존 실행 입력을 먼저 확인하세요."
                )
        else:
            venues = load_venues()
        validate_venues(venues, apply=True)
        collection = get_event_collection()
        sink = MongoSink(collection)
        sink.preflight()
        manifest = {
            "run_id": config.run_id,
            "config": config.document(),
            "venues": venues,
            "generator": code_identity(),
            "target_sha256": target_identity(collection),
            "session_plan_sha256": digest(make_sessions(config)),
        }
        journal = Journal(directory, manifest, resume=args.resume)
        with HistoricalRuntime(get_now()) as runtime:
            gateway = Gateway(journal, runtime, config)
            return Runner(config, venues, gateway, journal, sink).run()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        report = execute(args)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except GeneratorError as error:
        print(f"생성 중단: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(
            f"생성 중단 ({type(error).__name__}). 대상 연결·권한을 확인한 뒤 같은 입력으로 --resume 하세요.",
            file=sys.stderr,
        )
        return 1
    finally:
        close_databases()
        close_mongo()
