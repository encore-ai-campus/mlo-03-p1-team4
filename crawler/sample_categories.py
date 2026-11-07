"""스페이스클라우드 공간유형 표본(실행당 상세 20건 이하).

예전 200건 표본은 이력을 위한 결과이며 이 명령으로 다시 수집하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import httpx

from crawler.spacecloud_crawler import (
    MAX_DETAIL_PER_RUN,
    SPACE_BASE_URL,
    PoliteClient,
    fetch_sitemap_ids,
    parse_space,
    sanitized_dict,
)

DATA_DIR = Path(__file__).parent / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261030)
    args = parser.parse_args()
    if not 1 <= args.n <= MAX_DETAIL_PER_RUN:
        parser.error("--n은 1~20이어야 합니다.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with PoliteClient() as client:
        ids = fetch_sitemap_ids(client, "spacecloud")
        chosen = random.Random(args.seed).sample(ids, args.n)  # noqa: S311 재현 가능한 표본 추출
        path = DATA_DIR / f"sample_{args.seed}_{args.n}.jsonl"
        with path.open("x", encoding="utf-8") as output:
            for source_id in chosen:
                try:
                    space = parse_space(
                        source_id, client.get(f"{SPACE_BASE_URL}/space/{source_id}")
                    )
                    row = sanitized_dict(space)
                    row["status"] = "ok" if row["space_types"] else "no_detail"
                except httpx.HTTPStatusError as error:
                    row = {"source_id": source_id, "status": f"http_{error.response.status_code}"}
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"저장: {path}")


if __name__ == "__main__":
    main()
