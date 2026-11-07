"""쓰기 결과를 이전 읽기와 나란히 비교하되 배포 차이를 명시한다."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from runner import percentile
from summarize_read import fmt, values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--read-report", type=Path, default=Path("logs/read-high-20261107-183052"))
    args = parser.parse_args()
    report = args.report
    suite = json.loads((report / "suite.json").read_text())
    read = json.loads((args.read_report / "suite.json").read_text())
    raw = json.loads((report / "prometheus-range.json").read_text())
    resources = [json.loads(line) for line in (report / "resources.jsonl").read_text().splitlines()]
    lines = [
        "# 재배포 후 쓰기 100·200·400명 — 읽기 비교",
        "",
        "run_id: " + suite["run_id"],
        "",
        "이번 실행 중 VM/앱/DB 설정을 바꾸지 않았다. 독립 합성 계정과 미래 시간 칸을 사용자별로 할당했고, 모의 카드결제 예약 생성·조회·취소/환불을 반복했다. spawn 5명/초·목표 도달 후 warmup 60초/measure 180초/recovery 120초·생각 시간 1~5초다. 준비/로그인과 종료 정리는 본 측정에서 분리했다. 어느 구간이든 오류가 있으면 다음 단계에 진입하지 않는다.",
        "",
        "## 비교 조건",
        "",
        "이전 읽기는 1583778 인계 배포·공간19·구 Nginx였고, 현재 쓰기는 local/server-e2e-1107(f0b14c3 기반+로컬 변경) 인계·공간31·생성기 적재·Nginx keepalive16/4초·신규 타이머가 적용된 상태다. 따라서 업무·코드·설정·데이터 차이가 함께 포함된다. 최적화 효과의 인과적 A/B 비교나 서비스 최대치 판정으로 해석하지 않는다. 실제 OpenAPI와 deployment-snapshot.json 지문을 함께 보존했다.",
        "",
        "|종류|VU|HTTP 요청|HTTP RPS|전체 p95 ms|전체 p99 ms|실패|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for phase in read["results"]:
        rows = [
            json.loads(line)
            for line in (args.read_report / phase["phase"] / "requests.jsonl")
            .read_text()
            .splitlines()
        ]
        rows = [r for r in rows if r["phase"] == "measure"]
        lines.append(
            f"|읽기(이전 배포)|{phase['users']}|{len(rows)}|{phase['rps']:.2f}|{fmt(percentile([r['ms'] for r in rows], 95))}|{fmt(percentile([r['ms'] for r in rows], 99))}|{sum(r['failed'] for r in rows)}|"
        )
    for phase in suite["results"]:
        rows = [
            json.loads(line)
            for line in (report / phase["phase"] / "requests.jsonl").read_text().splitlines()
        ]
        rows = [r for r in rows if r["phase"] == "measure"]
        lines.append(
            f"|쓰기 여정|{phase['users']}|{len(rows)}|{phase['rps']:.2f}|{fmt(percentile([r['ms'] for r in rows], 95))}|{fmt(percentile([r['ms'] for r in rows], 99))}|{sum(r['failed'] for r in rows)}|"
        )
    lines += [
        "",
        "HTTP RPS는 조회와 생성/취소가 섞인 전체 호출 수다. 아래 예약 201 처리량과 구분한다. 실패를 빼서 지연이 좋아 보이지 않도록 전체 지연도 함께 제시한다.",
        "",
        "|VU|KST 본 측정|예약 201|예약 생성/초|예약 POST 전체 p95/p99 ms|정상 201 p95 ms|취소 성공|예약 여정 완료|",
        "|---:|---|---:|---:|---|---:|---:|---:|",
    ]
    for phase in suite["results"]:
        folder = report / phase["phase"]
        rows = [json.loads(line) for line in (folder / "requests.jsonl").read_text().splitlines()]
        rows = [r for r in rows if r["phase"] == "measure"]
        booked = [r for r in rows if r["method"] == "POST" and r["name"] == "/reservations"]
        success = [r for r in booked if r["status"] == 201 and not r["failed"]]
        cancelled = [
            r
            for r in rows
            if r["method"] == "POST"
            and r["name"] == "/reservations/{id}/cancel"
            and not r["failed"]
        ]
        transactions = [
            json.loads(line) for line in (folder / "transactions.jsonl").read_text().splitlines()
        ]
        complete = [
            r
            for r in transactions
            if r["kind"] == "booking_ok"
            and r.get("started", 0) >= phase["start"]
            and r["time"] <= phase["end"]
        ]
        start = datetime.fromtimestamp(phase["start"], ZoneInfo("Asia/Seoul")).strftime("%H:%M:%S")
        end = datetime.fromtimestamp(phase["end"], ZoneInfo("Asia/Seoul")).strftime("%H:%M:%S")
        lines.append(
            f"|{phase['users']}|{start}–{end}|{len(success)}|{len(success) / (phase['end'] - phase['start']):.2f}|{fmt(percentile([r['ms'] for r in booked], 95))} / {fmt(percentile([r['ms'] for r in booked], 99))}|{fmt(percentile([r['ms'] for r in success], 95))}|{len(cancelled)}|{len(complete)}|"
        )
    for phase in suite["results"]:
        lines += [
            "",
            f"## {phase['users']}명 VM 자원",
            "",
            "|VM|CPU 평균/최고 % (1분 평균 표본)|RAM 최고 %|디스크 busy 최고 %|루트 여유 최소 GiB|",
            "|---|---:|---:|---:|---:|",
        ]
        for server in ["gw", "api1", "api2", "mon", "db-primary", "db-replica"]:
            cpu = values(raw, "cpu", server, phase["start"], phase["end"])
            ram = values(raw, "memory", server, phase["start"], phase["end"])
            busy = values(raw, "disk_busy", server, phase["start"], phase["end"])
            free = values(raw, "disk_free", server, phase["start"], phase["end"])
            lines.append(
                f"|{server}|{fmt(sum(cpu) / len(cpu) if cpu else None)} / {fmt(max(cpu) if cpu else None)}|{fmt(max(ram) if ram else None)}|{fmt(max(busy) if busy else None)}|{fmt(min(free) / 2**30 if free else None)}|"
            )
        mongo = [
            n
            for record in resources
            if phase["start"] <= record["time"] <= phase["end"]
            for n in record.get("direct_7node_sample", {}).get("nodes", [])
            if n["server"] == "mongo" and "error" not in n
        ]
        if mongo:
            busy = [d["busy_percent"] for n in mongo for d in n.get("disk_io", {}).values()]
            lines.append(
                f"|mongo (1초 SSH 표본)|{sum(n['cpu_percent'] for n in mongo) / len(mongo):.2f} / {max(n['cpu_percent'] for n in mongo):.2f}|{max(n['memory_percent'] for n in mongo):.2f}|{fmt(max(busy) if busy else None)}|{min(n['disk_free'] for n in mongo) / 2**30:.2f}|"
            )
        lines += [
            "",
            "|DB|전체 연결 최고|실행 쿼리 최고(수집 포함)|앱 행 잠금 대기 표본 최고|복제 지연 최고 초|",
            "|---|---:|---:|---:|---:|",
        ]
        for server in ["db-primary", "db-replica"]:
            cells = []
            for key in ["db_connections", "db_running", "app_lock_waits", "db_replication_lag"]:
                v = values(raw, key, server, phase["start"], phase["end"])
                cells.append(fmt(max(v) if v else None))
            lines.append("|" + server + "|" + "|".join(cells) + "|")
    reached = {r["users"] for r in suite["results"]}
    lines += [
        "",
        "## 중단·관측 한계",
        "",
        "실행하지 않은 단계: " + ", ".join(str(v) for v in [100, 200, 400] if v not in reached),
        "",
        "실행기 중단 사유: " + str(suite.get("error")),
        "",
        "CPU는 Prometheus 1분 평균 표본이며 1초 SSH 표본도 따로 보존했다. 15/30초 관측 사이의 순간 포화·잠금은 놓칠 수 있다. Mongo는 exporter 없이 SSH 표본이다. 앱 DB 풀 획득 대기는 미계측이며 전체 연결 한도 미도달이 풀 대기 부재를 증명하지 않는다. FastAPI Prometheus는 수집 워커 기준이므로 전체 요청은 Locust·Nginx 로그를 우선한다.",
        "",
        "신규 event_daily 타이머·완료/크롤러 타이머를 끄지 않았다. timer 기록에서 본 측정과 겹친 실행이 있는지 확인한다. 계정 준비/로그인·cleanup은 본 측정 밖이며 DB 최종 행 수는 준비/워밍업/본 측정/정리를 모두 포함한다.",
        "",
        "## 기록",
        "",
        "단계별 requests.jsonl/transactions.jsonl/CSV/HTML, resources.jsonl, prometheus-range.json, generator-host-resources.jsonl, server-evidence-before/after, deployment-snapshot.json, 안전 필드 app 로그·HAProxy 이력·SQL 정합성 집계. 인증정보와 SQL 원문/개인정보는 공유하지 않는다.",
        "",
    ]
    (report / "WRITE_READ_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(report / "WRITE_READ_REVIEW.md")


if __name__ == "__main__":
    main()
