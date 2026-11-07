"""행정안전부 법정동코드 전체자료에서 크롤러 주소 매핑 CSV를 만든다.

공식 ZIP의 KIKcd_B 텍스트 파일을 입력으로 받는다. 원본 파일은 저장소에
넣지 않고, 필요한 현행 읍·면·동·리 이름과 다락큐브 지역만 CSV로 보관한다.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "db" / "seed"
OUTPUT = SEED / "legal_dong.csv"


def _read_csv(name: str) -> list[dict[str, str]]:
    with (SEED / name).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _source_rows(path: Path):
    """공식 KIKcd_B 고정폭 텍스트를 시도·시군구·읍면동·리 단위로 읽는다."""
    source = path.read_bytes()
    try:
        text = source.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = source.decode("cp949")
    for line in text.splitlines():
        match = re.match(r"^(\d{10})\s+(.*)$", line)
        if not match:
            continue
        fields = re.split(r"\s{2,}", match.group(2).strip())
        if len(fields) < 4:
            continue
        date_field = fields[-1]
        dates = re.findall(r"\d{8}", date_field)
        if not dates or len(dates) > 1:  # 말소일자가 있는 옛 코드는 제외한다.
            continue
        names = fields[:-1]
        if len(names) < 3:
            continue
        province, sigungu, eupmyeondong = names[:3]
        ri = names[3] if len(names) > 3 else ""
        if not province or not sigungu or not eupmyeondong:
            continue
        yield province, sigungu, eupmyeondong, ri


def _target_region(
    province: str,
    sigungu_name: str,
    sido_alias: dict[str, str],
    sigungu_alias: dict[tuple[str, str], str],
    regions: set[tuple[str, str]],
) -> tuple[str, str] | None:
    sido = sido_alias.get(province)
    if sido is None:
        return None
    sigungu = sigungu_alias.get((sido, sigungu_name), sigungu_name)
    if not sigungu:
        return None
    if (sido, sigungu) in regions:
        return sido, sigungu

    # 수원시 팔달구처럼 일반구까지 포함된 법정동 코드는 기존 regions의
    # 기초자치단체(수원시)로 접는다. 가장 구체적으로 일치하는 지역을 쓴다.
    candidates = [
        name
        for region_sido, name in regions
        if region_sido == sido and sigungu.startswith(f"{name} ")
    ]
    return (sido, max(candidates, key=len)) if candidates else None


def build(source: Path, output: Path = OUTPUT) -> tuple[int, int]:
    sido_alias = {row["alias"]: row["sido"] for row in _read_csv("sido_alias.csv")}
    sigungu_alias = {
        (row["sido"], row["alias"]): row["sigungu"] for row in _read_csv("sigungu_alias.csv")
    }
    regions = {(row["sido"], row["sigungu"]) for row in _read_csv("regions.csv")}
    candidates: dict[tuple[str, str, str], set[tuple[str, str, str]]] = defaultdict(set)

    for province, raw_sigungu, eupmyeondong, ri in _source_rows(source):
        target = _target_region(province, raw_sigungu, sido_alias, sigungu_alias, regions)
        if target is None:
            continue
        target_sido, target_sigungu = target
        localities = {eupmyeondong}
        if ri:
            localities.add(ri)
        for locality in localities:
            candidate = (target_sido, target_sigungu, raw_sigungu)
            candidates[("sido", target_sido, locality)].add(candidate)

            # addressRegion은 천안·파주·고양처럼 시도 올 수 있다.
            if target_sigungu.endswith("시"):
                city_aliases = {target_sigungu, target_sigungu[:-1]}
                for city in city_aliases:
                    candidates[("city", city, locality)].add(candidate)

    rows = []
    ambiguous = 0
    for (scope, alias, locality), targets in sorted(candidates.items()):
        if len(targets) == 1:
            target_sido, target_sigungu, _ = next(iter(targets))
            status = "unique"
        else:
            target_sido = target_sigungu = ""
            status = "ambiguous"
            ambiguous += 1
        rows.append(
            {
                "scope": scope,
                "alias": alias,
                "locality": locality,
                "sido": target_sido,
                "sigungu": target_sigungu,
                "status": status,
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["scope", "alias", "locality", "sido", "sigungu", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows), ambiguous


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="KIKcd_B.20260701 텍스트 파일 경로")
    args = parser.parse_args()
    count, ambiguous = build(args.source)
    print(f"{OUTPUT.relative_to(ROOT)}: {count} keys · {ambiguous} ambiguous")


if __name__ == "__main__":
    main()
