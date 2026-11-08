"""db/seed/*.csv → db/seed/seed.sql (11-04).

실행: conda run -n pro_1 --no-capture-output python db/loaders/load_seed.py
- CSV를 읽어 INSERT IGNORE 문을 만든다. 여러 번 넣어도 같은 결과(UNIQUE 키 기준).
- 만든 seed.sql은 저장소에 같이 둔다. 로컬 compose가 첫 실행 때 자동으로 넣고,
  RDS에는 `mariadb … spacecube < db/seed/seed.sql`로 넣는다.
- --check: 크롤링 표본(crawler/data/sample_*.jsonl)의 주소가 regions·별칭으로 모두 풀리는지 본다.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "db" / "seed"
OUT = SEED / "seed.sql"


def rows(name):
    with (SEED / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def q(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def insert(table, cols, data):
    values = ",\n  ".join("(" + ",".join(q(r[c]) for c in cols) + ")" for r in data)
    return f"INSERT IGNORE INTO {table} ({','.join(cols)}) VALUES\n  {values};\n"


def build():
    parts = [
        "-- 자동 생성: db/loaders/load_seed.py (원본은 db/seed/*.csv, 이 파일을 손으로 고치지 않는다)\n",
        "-- 0001_init.sql을 적용한 스키마에서 실행. 여러 번 실행해도 같은 결과.\n\n",
        insert("categories", ["code", "name"], rows("categories.csv")),
        insert("facilities", ["name"], rows("facilities.csv")),
        insert("regions", ["sido", "sigungu"], rows("regions.csv")),
    ]
    OUT.write_text("".join(parts), encoding="utf-8")
    print(
        f"{OUT.relative_to(ROOT)}: 유형 {len(rows('categories.csv'))} · 시설 {len(rows('facilities.csv'))} · 지역 {len(rows('regions.csv'))}"
    )


def resolve(address, sido_alias, sigungu_alias, regions, legal_dong=None, city_aliases=None):
    """'서울특별시 마포구' → ('서울', '마포구'). 못 풀면 (None, 이유)."""
    parts = address.split()
    if len(parts) < 2:
        return None, "주소가 시·도 하나뿐"
    sido = sido_alias.get(parts[0])
    locality = parts[1]
    legal_dong = legal_dong or {}
    city_aliases = city_aliases or set()

    if sido is not None:
        if sido == "세종":  # 시·군·구가 없는 세종은 지역 한 곳으로 둔다.
            target = (sido, "세종시")
        else:
            mapped = legal_dong.get(("sido", sido, locality), "missing")
            if mapped != "missing":
                if mapped is None:
                    return None, "동 이름 겹침"
                if mapped not in regions:
                    return None, f"regions에 없음 {mapped[0]} {mapped[1]}"
                return mapped, ""

            sigungu = sigungu_alias.get((sido, locality), locality)
            if not sigungu:
                return None, f"나뉜 옛 구 {parts[0]} {locality}"
            target = (sido, sigungu)

        if target not in regions:
            if locality.endswith(("동", "가", "읍", "면", "리")):
                return None, "동 대응 없음"
            return None, f"regions에 없음 {target[0]} {target[1]}"
        return target, ""

    # 스페이스클라우드 addressRegion에는 천안·고양처럼 시 이름만 올 수 있다.
    mapped = legal_dong.get(("city", parts[0], locality), "missing")
    if mapped != "missing":
        if mapped is None:
            return None, "동 이름 겹침"
        if mapped not in regions:
            return None, f"regions에 없음 {mapped[0]} {mapped[1]}"
        return mapped, ""
    if parts[0] in city_aliases or locality.endswith(("동", "가", "읍", "면", "리")):
        return None, "동 대응 없음"
    return None, f"모르는 시·도 {parts[0]}"


def check():
    sido_alias = {r["alias"]: r["sido"] for r in rows("sido_alias.csv")}
    sigungu_alias = {(r["sido"], r["alias"]): r["sigungu"] for r in rows("sigungu_alias.csv")}
    regions = {(r["sido"], r["sigungu"]) for r in rows("regions.csv")}
    legal_dong, city_aliases = {}, set()
    for row in rows("legal_dong.csv"):
        target = (row["sido"], row["sigungu"]) if row["status"] == "unique" else None
        legal_dong[(row["scope"], row["alias"], row["locality"])] = target
        if row["scope"] == "city":
            city_aliases.add(row["alias"])
    ok, bad = 0, []
    for path in sorted((ROOT / "crawler" / "data").glob("sample_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            address = json.loads(line).get("address_region") or ""
            found, reason = resolve(
                address, sido_alias, sigungu_alias, regions, legal_dong, city_aliases
            )
            if found:
                ok += 1
            else:
                bad.append(reason)
    print(f"표본 주소 {ok + len(bad)}건 중 풀림 {ok}, 못 풂 {len(bad)}")
    for reason in sorted(set(bad)):
        print(f"  - {reason} ({bad.count(reason)}건)")


if __name__ == "__main__":
    build()
    if "--check" in sys.argv:
        check()
