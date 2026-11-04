"""사이트맵 공간 id에서 무작위 표본을 뽑아 공간유형·지역 분포를 추정한다.

전체 14,137개를 다 열면 3초 간격으로 약 12시간이 걸리므로, 표본으로 카테고리별 공간 수를 어림한다.

    uv run --with httpx --with beautifulsoup4 python sample_categories.py --n 200
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict

import httpx
from spacecloud_crawler import (
    BASE_URL,
    DATA_DIR,
    SITEMAP_IDS_FILE,
    PoliteClient,
    load_json,
    parse_space,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261030)
    args = parser.parse_args()

    ids = load_json(SITEMAP_IDS_FILE, [])
    if not ids:
        sys.exit("먼저 spacecloud_crawler.py baseline을 실행하세요.")
    sample = random.Random(args.seed).sample(ids, args.n)  # noqa: S311 표본 뽑기용(보안 무관), 시드로 재현

    client = PoliteClient()
    out_path = DATA_DIR / f"sample_{args.seed}_{args.n}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for i, source_id in enumerate(sample, 1):
            try:
                row = asdict(parse_space(source_id, client.get(f"{BASE_URL}/space/{source_id}")))
                row["status"] = "ok" if row["space_types"] else "no_detail"
            except httpx.HTTPStatusError as exc:
                row = {"source_id": source_id, "status": f"http_{exc.response.status_code}"}
            except (httpx.HTTPError, PermissionError) as exc:
                row = {"source_id": source_id, "status": f"error: {exc}"}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"{i}/{args.n}")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
