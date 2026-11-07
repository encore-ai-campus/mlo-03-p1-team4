"""시드와 고정 공간 스냅샷에서 사용자·세션·예약 후보를 만든다."""

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5

CATEGORIES = ("studyroom", "studio", "cafe", "lectureroom", "partyroom")
PERSONAS = (("Student", 35), ("Worker", 25), ("Gathering", 20), ("Explorer", 20))
VERSION = 1


class GeneratorError(Exception):
    """접속정보·입력 비밀값을 포함하지 않는 생성기 운영 메시지."""


@dataclass(frozen=True)
class Config:
    seed: int
    base_date: date
    users: int = 100
    days: int = 30
    sessions_per_day: int = 42

    def __post_init__(self):
        if not 0 <= self.seed <= 2**63 - 1 or self.users < 1 or not 1 <= self.days <= 365:
            raise GeneratorError("seed는 0~2^63-1, users는 1 이상, days는 1~365여야 합니다.")
        if not 1 <= self.sessions_per_day <= 120:
            raise GeneratorError("sessions-per-day는 1~120이어야 합니다.")

    def document(self):
        return {**asdict(self), "base_date": self.base_date.isoformat(), "version": VERSION}

    @property
    def namespace(self):
        return uuid5(NAMESPACE_URL, f"spacecube-generator:{self.seed}:{self.base_date}")

    def identifier(self, key):
        return str(uuid5(self.namespace, key))

    @property
    def run_id(self):
        return self.identifier("run")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def allocations(total, weights):
    """정수 수량은 최대 나머지 방식으로 배분해 합계를 보존한다."""
    denominator = sum(weights)
    counts = [total * weight // denominator for weight in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(total * weights[i] % denominator), i))
    for index in order[: total - sum(counts)]:
        counts[index] += 1
    return counts


def members(config):
    people = []
    for (persona, _), count in zip(
        PERSONAS, allocations(config.users, [weight for _, weight in PERSONAS]), strict=True
    ):
        people.extend([persona] * count)
    random.Random(config.seed).shuffle(people)  # noqa: S311 -- 비밀값이 아닌 재현용 난수
    return people


def make_sessions(config):
    """하루 수량을 고정하고 회원을 순환 배정해 후속 후기 세션도 확보한다."""
    rng = random.Random(config.seed)  # noqa: S311 -- 행동 재현용
    people = members(config)
    groups = {
        persona: [i for i, value in enumerate(people) if value == persona]
        for persona, _ in PERSONAS
    }
    personas = []
    for (persona, _), count in zip(
        PERSONAS,
        allocations(
            config.days * config.sessions_per_day, [len(group) for group in groups.values()]
        ),
        strict=True,
    ):
        personas.extend([persona] * count)
    rng.shuffle(personas)
    assigned = dict.fromkeys(groups, 0)
    sessions = []
    for day_index in range(config.days):
        day = config.base_date - timedelta(days=config.days - day_index)
        for index in range(config.sessions_per_day):
            ordinal = len(sessions)
            persona = personas[ordinal]
            group = groups[persona]
            person = group[assigned[persona] % len(group)]
            assigned[persona] += 1
            # 08~20시를 고르게 방문한다. 각 방문은 초 단위로 서로 다른 시각이다.
            seconds = 8 * 3600 + index * 12 * 3600 // config.sessions_per_day
            at = datetime.combine(day, time()) + timedelta(seconds=seconds)
            sessions.append(
                {
                    "index": ordinal,
                    "person": person,
                    "persona": people[person],
                    "session_id": config.identifier(f"session:{ordinal}"),
                    "at": at.isoformat(),
                    "choice_seed": rng.getrandbits(64),
                }
            )
    return sessions


def candidates(config, session, venues):
    """점유 여부를 미리 검사해 성공을 강제하지 않고, 선호에 맞는 후보 두 개만 고른다."""
    if session["persona"] == "Explorer":
        return []
    rng = random.Random(session["choice_seed"])  # noqa: S311 -- 행동 재현용
    at = datetime.fromisoformat(session["at"])
    choices = []
    for offset in range(7):
        day = at.date() + timedelta(days=offset)
        if day >= config.base_date:
            break
        for venue in venues:
            persona = session["persona"]
            if persona == "Student" and venue["category_code"] != "studyroom":
                continue
            if persona == "Gathering" and (
                day.weekday() < 5
                or venue["category_code"] not in {"partyroom", "cafe", "lectureroom"}
                or venue["capacity_max"] < 4
            ):
                continue
            hours = venue["min_hours"]
            for start in range(venue["open_hour"], venue["close_hour"] - hours + 1):
                begins = datetime.combine(day, time(start))
                if begins <= at + timedelta(minutes=10):
                    continue
                if persona == "Student" and (day.weekday() >= 5 or not 13 <= start < 19):
                    continue
                if persona == "Worker" and not (
                    (day.weekday() < 5 and start >= 19) or (day.weekday() >= 5 and start < 12)
                ):
                    continue
                if persona == "Gathering" and not 12 <= start < 19:
                    continue
                choices.append(
                    {
                        "venue_id": venue["venue_id"],
                        "date": day.isoformat(),
                        "start_hour": start,
                        "hours": hours,
                        "headcount": min(venue["capacity_max"], 4 if persona == "Gathering" else 2),
                        "method": rng.choice(("transfer", "card", "phone")),
                    }
                )
    rng.shuffle(choices)
    return choices[:2]
