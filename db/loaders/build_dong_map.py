"""법정동 원본 CSV → db/seed/dong_sigungu.csv (11-07).

원본: 공공데이터포털 '국토교통부_전국 법정동'(15063424, 이용허락범위 제한 없음).
  컬럼: 법정동코드,시도명,시군구명,읍면동명,리명,순번,생성일자 (현재 유효한 행만 들어 있음)
실행: python db/loaders/build_dong_map.py <원본.csv>

- 스페이스클라우드 상세는 시·군·구 없이 '시·도(또는 시 이름) + 법정동'만 준다(#10).
  그래서 (시·도, 동) → 시·군·구 대응표를 만든다. 크롤러는 시 이름(천안·파주)도 이 표로 푼다.
- regions.csv 기준에 맞춘다: 일반구가 있는 시(천안시서북구)는 시(천안시)로 줄인다.
- regions에 없는 시·군·구 행은 버린다. 리(里) 행은 리 이름으로 넣는다. 같은 (시·도, 동)이 여러 시·군·구에 있어도
  모두 남긴다. 고르는 일은 크롤러가 하고, 겹치면 제외한다.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "db" / "seed"
OUT = SEED / "dong_sigungu.csv"


def _rows(name: str) -> list[dict[str, str]]:
    with (SEED / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_sigungu(sido: str, name: str, regions: set[tuple[str, str]]) -> str | None:
    if sido == "세종":
        return "세종시"
    if (sido, name) in regions:
        return name
    city = re.match(r"^(.+?시)(.+구)$", name)
    if city and (sido, city.group(1)) in regions:
        return city.group(1)
    return None


def build(source: Path) -> int:
    sido_alias = {r["alias"]: r["sido"] for r in _rows("sido_alias.csv")}
    regions = {(r["sido"], r["sigungu"]) for r in _rows("regions.csv")}
    out: set[tuple[str, str, str]] = set()
    with source.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            dong, ri = (row.get("읍면동명") or "").strip(), (row.get("리명") or "").strip()
            if not dong:
                continue
            sido = sido_alias.get((row.get("시도명") or "").strip())
            if not sido:
                continue
            sigungu = normalize_sigungu(sido, (row.get("시군구명") or "").strip(), regions)
            if sigungu:
                # 리(里) 행은 읍·면 대신 리 이름으로 넣는다(김포 석모리처럼 사이트가 리만 줄 때).
                out.add((sido, sigungu, ri or dong))
    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["sido", "sigungu", "dong"])
        writer.writerows(sorted(out))
    return len(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "사용법: python db/loaders/build_dong_map.py <국토교통부_전국 법정동.csv>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    count = build(Path(sys.argv[1]))
    print(f"{OUT.relative_to(ROOT)}: {count}행")
