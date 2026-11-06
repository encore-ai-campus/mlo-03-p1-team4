"""Collect 15 spaces from a selected source and save crawl results."""

import argparse
import sys
from datetime import datetime
from typing import Any

from playwright.sync_api import sync_playwright

from config import load_env_file, required_env
from internal_api import post_internal_venue
from mapping import make_venue_payload
from scraper import MAX_DETAIL_PER_RUN, PoliteClient, USER_AGENT, crawl_space_detail, search_spaces
from spacecloud_scraper import crawl_spacecloud_detail, search_spacecloud_spaces
from storage import (
    SEOUL,
    count_new_source_ids,
    crawl_raw_namespace,
    finish_crawl_job,
    mark_crawl_record_registered,
    save_crawl_raw_records,
    start_crawl_job,
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    load_env_file()
    parser = argparse.ArgumentParser(description="Crawl Shareit or Spacecloud spaces")
    parser.add_argument("--source", choices=("shareit", "spacecloud"), default="shareit")
    parser.add_argument("--page", type=int, default=1, help="Sitemap/search page (15 spaces)")
    parser.add_argument("--register", action="store_true", help="Register eligible venues through /internal/venues")
    args = parser.parse_args()
    if args.page < 1:
        parser.error("--page must be 1 or greater")
    if args.register:
        required_env("INTERNAL_API_KEY")

    source_site = args.source

    job_id: int | None = None
    crawl_finished_at: datetime | None = None
    records: list[dict[str, Any]] = []
    payloads: list[tuple[dict[str, Any], dict[str, Any]]] = []
    new_ids = fetched = registered = api_errors = 0
    try:
        with sync_playwright() as playwright:
            headers = {"User-Agent": USER_AGENT}
            if source_site == "shareit":
                headers.update({
                    "Content-Type": "application/json",
                    "Origin": "https://shareit.kr",
                    "Referer": "https://shareit.kr/search/venue",
                })
            request = playwright.request.new_context(extra_http_headers=headers)
            try:
                client = PoliteClient(request)
                crawl_started_at = datetime.now(SEOUL)
                job_id = start_crawl_job(source_site, started_at=crawl_started_at)
                search = search_spaces if source_site == "shareit" else search_spacecloud_spaces
                crawl_detail = crawl_space_detail if source_site == "shareit" else crawl_spacecloud_detail
                source_ids = search(client, args.page)[:MAX_DETAIL_PER_RUN]
                for source_id in source_ids:
                    try:
                        record = crawl_detail(client, source_id)
                        fetched += 1
                    except (RuntimeError, PermissionError, ValueError, KeyError):
                        record = {
                            "source_id": source_id,
                            "status": "no_detail",
                            "space_types": [],
                            "extracted": {},
                            "exclude_reason": "detail_fetch_failed",
                        }
                    payload, reason = make_venue_payload(record, source_site)
                    if reason and record["status"] == "ok":
                        record["status"] = "excluded"
                        record["exclude_reason"] = reason
                    records.append(record)
                    if payload is not None:
                        payloads.append((record, payload))
                crawl_finished_at = datetime.now(SEOUL)
            finally:
                request.dispose()

        new_ids = count_new_source_ids(source_site, source_ids)
        mongo_saved = save_crawl_raw_records(job_id, source_site, records)
        for record, payload in (payloads if args.register else []):
            try:
                result = post_internal_venue(payload)
            except RuntimeError as exc:
                record["status"] = "excluded"
                record["exclude_reason"] = "registration_failed"
                save_crawl_raw_records(job_id, source_site, [record])
                print(f"{record['source_id']}: API registration failed: {exc}", file=sys.stderr)
                api_errors += 1
                continue
            mark_crawl_record_registered(source_site, record["source_id"], result["venue_id"])
            registered += 1

        status = "failed" if api_errors else "done"
        total_demo = finish_crawl_job(
            job_id, new_ids=new_ids, fetched=fetched, registered=registered,
            status=status, finished_at=crawl_finished_at,
        )
    except Exception as exc:
        if job_id is not None:
            try:
                finish_crawl_job(
                    job_id, new_ids=new_ids, fetched=fetched, registered=registered,
                    status="failed", finished_at=crawl_finished_at or datetime.now(SEOUL),
                )
            except Exception:
                pass
        raise SystemExit(f"{source_site} crawl or registration failed: {exc}") from exc

    print(
        f"조회 {len(records)}개 · 상세 {fetched}개 · 등록 {registered}개 · "
        f"MongoDB {crawl_raw_namespace()} 적재 {mongo_saved}개 · "
        f"총 시연 공간 {total_demo}개 · API 오류 {api_errors}개 (crawl_jobs #{job_id})"
    )


if __name__ == "__main__":
    main()
