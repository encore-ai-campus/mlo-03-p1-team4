"""표본 결과로 공간유형·묶음별 전체 공간 수를 추정한다 (95% Wilson 구간).

uv run python analyze_sample.py data/sample_20261030_200.jsonl
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter

TOTAL_SPACES = 14137

GROUPS = {
    "A 학습·회의": {"스터디룸", "회의실", "세미나실", "강의실"},
    "B 모임·행사": {"파티룸", "다목적홀", "공유주방", "카페", "레저시설"},
    "C 연습·촬영": {
        "연습실",
        "댄스연습실",
        "보컬연습실",
        "악기연습실",
        "촬영스튜디오",
        "렌탈스튜디오",
        "운동시설",
    },
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def estimate(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k:>3}/{n} ({k / n:5.1%}) → 약 {round(k / n * TOTAL_SPACES):>6,}개 (95% {round(lo * TOTAL_SPACES):,}~{round(hi * TOTAL_SPACES):,})"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with open(sys.argv[1], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    status = Counter(r["status"] for r in rows)
    ok = [r for r in rows if r["status"] == "ok"]
    n = len(rows)
    print("응답 상태:", dict(status))

    types = Counter(t for r in ok for t in set(r["space_types"]))
    print("\n[공간유형별 (한 공간이 여러 유형 가능)]")
    for t, k in types.most_common():
        print(f"  {t:<10} {estimate(k, n)}")

    seoul = [r for r in ok if (r.get("address_region") or "").startswith("서울")]
    print(f"\n[지역] 서울 {estimate(len(seoul), n)}")
    regions = Counter((r.get("address_region") or "미상").split()[0] for r in ok)
    print("  ", dict(regions.most_common(8)))

    print("\n[묶음별 (유형 중 하나라도 해당하면 1개로 셈)]")
    for name, members in GROUPS.items():
        hit = [r for r in ok if members & set(r["space_types"])]
        hit_seoul = [r for r in hit if (r.get("address_region") or "").startswith("서울")]
        small = [r for r in hit_seoul if (r.get("max_capacity") or 999) <= 10]
        print(f"  {name}")
        print(f"    전국        {estimate(len(hit), n)}")
        print(f"    서울        {estimate(len(hit_seoul), n)}")
        print(f"    서울·10명↓  {estimate(len(small), n)}")


if __name__ == "__main__":
    main()
