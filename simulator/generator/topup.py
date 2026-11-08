"""#99: 현재 활성 공간 수에 맞춰 검증된 등록 요청을 결정적으로 만든다."""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.internal import InternalVenueUpsert  # noqa: E402 -- backend 경로를 먼저 추가한다.

DEFAULT_PROFILES = Path(__file__).with_name("venue_profiles.json")

CATEGORIES = ("studyroom", "studio", "cafe", "lectureroom", "partyroom")
SOURCES = {"spacecloud", "shareit"}
NAMES = {
    "studyroom": ("스터디룸", "집중형", "art:group-0"),
    "studio": ("스튜디오", "촬영형", "art:studio-0"),
    "cafe": ("카페", "모임형", "art:lounge-0"),
    "lectureroom": ("강의실", "수업형", "art:seminar-0"),
    "partyroom": ("파티룸", "행사형", "art:partyroom-0"),
}
REQUIRED_ATTRIBUTES = (
    "sido",
    "sigungu",
    "capacity_max",
    "price_per_hour",
    "min_hours",
    "open_hour",
    "close_hour",
)


def valid_candidate(row, catalog=None):
    if (
        not row.get("is_active")
        or not row.get("verified")
        or row.get("source_site") not in SOURCES
    ):
        return False
    if any(row.get(key) is None for key in REQUIRED_ATTRIBUTES):
        return False
    try:
        validated = InternalVenueUpsert.model_validate(
            {
                "source_site": row["source_site"],
                "source_id": row["source_id"],
                "name": "검증 공간",
                "category_code": row["category_code"],
                **{key: row[key] for key in REQUIRED_ATTRIBUTES},
                "facilities": row.get("facilities", []),
                "images": [NAMES[row["category_code"]][2]],
            }
        )
    except (KeyError, TypeError, ValidationError):
        return False
    if validated.min_hours > validated.close_hour - validated.open_hour:
        return False
    if catalog is not None:
        if validated.category_code not in catalog["categories"]:
            return False
        if (validated.sido, validated.sigungu) not in catalog["regions"]:
            return False
        if set(validated.facilities) - catalog["facilities"]:
            return False
    return True


def _payload(*, category, number, seed, source, profile=None):
    title, feature, image = NAMES[category]
    attributes = source if source is not None else profile
    source_hash = hashlib.sha256(f"{seed}:{category}:{number}".encode()).hexdigest()[:24]
    sigungu = attributes["sigungu"]
    body = {
        "source_site": "synthetic",
        "source_id": f"gen-{source_hash}",
        "name": f"{sigungu} {feature} {title} {number:02d}",
        "category_code": category,
        "sido": attributes["sido"],
        "sigungu": sigungu,
        "capacity_max": attributes["capacity_max"],
        "price_per_hour": attributes["price_per_hour"],
        "min_hours": attributes["min_hours"],
        "open_hour": attributes["open_hour"],
        "close_hour": attributes["close_hour"],
        "description": f"{sigungu}의 {feature} {title} 시연용 공간입니다.",
        "notice": "실제 업체의 예약 상품이 아닌 시연용 공간입니다.",
        "facilities": sorted(set(attributes.get("facilities", []))),
        "images": [image],
    }
    return InternalVenueUpsert.model_validate(body).model_dump()


def prepare(
    snapshot, *, target=6, seed=99, profiles=None, catalog=None, profile_version="1"
):
    """활성 수를 세고 유효한 기존 공간 또는 기본 프로필로 요청을 만든다."""
    if target < 0:
        raise ValueError("목표 수는 0 이상이어야 합니다.")
    if seed < 0:
        raise ValueError("seed는 0 이상이어야 합니다.")

    venues = snapshot["venues"]
    counts = Counter(
        row["category_code"]
        for row in venues
        if row.get("is_active") and row.get("category_code") in CATEGORIES
    )
    existing_ids = {
        row.get("source_id") for row in venues if row.get("source_site") == "synthetic"
    }
    prepared = []
    references = {}
    reference_snapshots = {}
    failures = {}

    for category in CATEGORIES:
        missing = max(0, target - counts[category])
        if not missing:
            continue
        candidates = sorted(
            (
                row
                for row in venues
                if row.get("category_code") == category and valid_candidate(row, catalog)
            ),
            key=lambda row: (row["source_site"], row["source_id"]),
        )
        profile = (profiles or {}).get(category)
        if candidates:
            references[category] = {
                "kind": "venue",
                "source_ids": [row["source_id"] for row in candidates],
            }
        elif profile is not None:
            references[category] = {"kind": "profile", "profile_version": profile_version}
        else:
            failures[category] = "유효한 같은 유형의 참고 공간과 기본 프로필이 없습니다."
            continue

        index = 0
        made = 0
        while made < missing:
            index += 1
            source_hash = hashlib.sha256(f"{seed}:{category}:{index}".encode()).hexdigest()[:24]
            source_id = f"gen-{source_hash}"
            if source_id in existing_ids:
                continue
            source = candidates[(index - 1) % len(candidates)] if candidates else None
            try:
                body = _payload(
                    category=category,
                    number=index,
                    seed=seed,
                    source=source,
                    profile=profile,
                )
                if catalog is not None:
                    _validate_catalog(body, catalog)
            except (KeyError, TypeError, ValueError, ValidationError) as error:
                failures[category] = f"후보 속성 검증 실패 ({type(error).__name__})"
                break
            prepared.append(body)
            reference_snapshots[body["source_id"]] = (
                {
                    "kind": "venue",
                    "source_site": source["source_site"],
                    "source_id": source["source_id"],
                    "attributes": {key: source[key] for key in REQUIRED_ATTRIBUTES}
                    | {"facilities": list(source.get("facilities", []))},
                }
                if source is not None
                else {
                    "kind": "profile",
                    "profile_version": profile_version,
                    "attributes": {
                        key: profile[key]
                        for key in (
                            "sido",
                            "sigungu",
                            "capacity_max",
                            "price_per_hour",
                            "min_hours",
                            "open_hour",
                            "close_hour",
                            "facilities",
                        )
                    },
                }
            )
            existing_ids.add(body["source_id"])
            made += 1

    return {
        "active_counts": {category: counts[category] for category in CATEGORIES},
        "missing_by_category": {
            category: max(0, target - counts[category]) for category in CATEGORIES
        },
        "target_per_category": target,
        "references": references,
        "reference_snapshots": reference_snapshots,
        "failures": failures,
        "requests": prepared,
    }


def _validate_catalog(body, catalog):
    if body["category_code"] not in catalog["categories"]:
        raise ValueError("대상 DB에 유형이 없습니다.")
    if (body["sido"], body["sigungu"]) not in catalog["regions"]:
        raise ValueError("대상 DB에 지역이 없습니다.")
    unknown = set(body["facilities"]) - catalog["facilities"]
    if unknown:
        raise ValueError("대상 DB에 시설이 없습니다.")


def _load_profiles(path):
    source = json.loads(path.read_text(encoding="utf-8"))
    common = source["common"]
    profiles = source["profiles"]
    if set(profiles) != set(CATEGORIES):
        raise ValueError("기본 프로필은 5개 공간 유형을 모두 포함해야 합니다.")
    normalized = {}
    for category in CATEGORIES:
        row = {**common, **profiles[category]}
        row["facilities"] = sorted(
            set(common.get("facilities", [])) | set(profiles[category].get("facilities", []))
        )
        normalized[category] = row
    return normalized


def main(argv=None):
    command = argparse.ArgumentParser(description="#99 검증된 공간 속성으로 부족분을 계산")
    command.add_argument("--snapshot", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--seed", type=int, default=99)
    command.add_argument("--target", type=int, default=6)
    command.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    args = command.parse_args(argv)
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    profiles = _load_profiles(args.profiles)
    result = prepare(snapshot, target=args.target, seed=args.seed, profiles=profiles)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"등록 요청 {len(result['requests'])}건: {args.output}")
    return 0 if not result["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
