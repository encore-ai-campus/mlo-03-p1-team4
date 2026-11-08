"""읽기 전용 시험의 측정 구간과 VM 자원을 연결해 검토 문서를 만든다."""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from runner import percentile


def values(raw, name, server, start, end):
    return [
        float(v)
        for row in raw.get(name, [])
        if row["metric"].get("server") == server
        for t, v in row["values"]
        if start <= t <= end and math.isfinite(float(v))
    ]


def fmt(value):
    return "N/A" if value is None else f"{value:.2f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = args.report
    suite = json.loads((report / "suite.json").read_text())
    raw = json.loads((report / "prometheus-range.json").read_text())
    resources = [json.loads(line) for line in (report / "resources.jsonl").read_text().splitlines()]
    lines = [
        "# 공개 읽기 100·200·400명 시험 검토",
        "",
        f"run_id: {suite['run_id']}",
        "",
        "쓰기 부하는 수행하지 않았다. 서비스·VM·DB 한도는 고정했고 Grafana 파일 저장만 사전 수행했다. 기준 사양은 gw 1vCPU/768MiB, api1·api2 각각 1vCPU/1536MiB, mon 2vCPU/3072MiB, db1·db2·mongo 각각 1vCPU/2048MiB다. 일반 6대 루트 파일시스템 약 19.68GB, Mongo 약 10.46GB이며 가상 디스크 설정 용량과 구분한다. 각 단계 목표 도달 뒤 워밍업 60초·측정 180초·회복 120초다.",
        "",
        "|VU|측정 시각 KST|요청|RPS|오류|성공 GET p95 ms|성공 GET p99 ms|전체 p95 ms|전체 p99 ms|",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for phase in suite["results"]:
        folder = report / phase["phase"]
        rows = [json.loads(line) for line in (folder / "requests.jsonl").read_text().splitlines()]
        rows = [r for r in rows if r["phase"] == "measure"]
        times = [r["ms"] for r in rows if not r["failed"]]
        start = datetime.fromtimestamp(phase["start"], ZoneInfo("Asia/Seoul")).strftime("%H:%M:%S")
        end = datetime.fromtimestamp(phase["end"], ZoneInfo("Asia/Seoul")).strftime("%H:%M:%S")
        lines.append(
            f"|{phase['users']}|{start}–{end}|{phase['requests']}|{phase['rps']:.2f}|{phase['availability_errors']}|{fmt(phase['get_p95_ms'])}|{fmt(percentile(times, 99))}|{fmt(percentile([r['ms'] for r in rows], 95))}|{fmt(percentile([r['ms'] for r in rows], 99))}|"
        )
    lines += [
        "",
        "생각 시간 1~5초의 API 10종 시나리오다. 브라우저 자산 다운로드/렌더링이나 무대기 최대 처리량 시험이 아니다. 이전 11-06의 4종/1~3초 및 다른 DB 배치·데이터 규모와는 VU만으로 개선을 단정하지 않는다. 최고 시험 인원은 실제 결과의 마지막 VU이며 시스템 최대 인원이 아니다.",
        "",
    ]
    for phase in suite["results"]:
        lines += [
            f"## {phase['users']}명 VM 자원",
            "",
            "|VM|CPU 최고 % (1분 평균)|RAM 최고 %|루트 여유 최소 GiB|디스크 busy 최고 %|",
            "|---|---:|---:|---:|---:|",
        ]
        for server in ["gw", "api1", "api2", "mon", "db-primary", "db-replica"]:
            cpu = values(raw, "cpu", server, phase["start"], phase["end"])
            memory = values(raw, "memory", server, phase["start"], phase["end"])
            free = values(raw, "disk_free", server, phase["start"], phase["end"])
            busy = values(raw, "disk_busy", server, phase["start"], phase["end"])
            lines.append(
                f"|{server}|{fmt(max(cpu) if cpu else None)}|{fmt(max(memory) if memory else None)}|{fmt(min(free) / 2**30 if free else None)}|{fmt(max(busy) if busy else None)}|"
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
                f"|mongo (1초 SSH 표본)|{max(n['cpu_percent'] for n in mongo):.2f}|{max(n['memory_percent'] for n in mongo):.2f}|{min(n['disk_free'] for n in mongo) / 2**30:.2f}|{fmt(max(busy) if busy else None)}|"
            )
        lines += [
            "",
            "|DB|연결 최고|실행 쿼리 최고|앱 행 잠금 대기 표본 최고|복제 지연 최고 초|",
            "|---|---:|---:|---:|---:|",
        ]
        for server in ["db-primary", "db-replica"]:
            cells = []
            for name in ["db_connections", "db_running", "app_lock_waits", "db_replication_lag"]:
                v = values(raw, name, server, phase["start"], phase["end"])
                cells.append(fmt(max(v) if v else None))
            lines.append("|" + server + "|" + "|".join(cells) + "|")
        endpoints = json.loads((report / phase["phase"] / "endpoints.json").read_text())
        worst = sorted(
            (r for r in endpoints if r["p95_ms"] is not None),
            key=lambda r: r["p95_ms"],
            reverse=True,
        )[:3]
        lines += [
            "",
            "느린 경로 p95: "
            + ", ".join(f"{r['name']} {r['p95_ms']:.2f}ms (n={r['count']})" for r in worst)
            + ".",
            "",
        ]
    lines += [
        "## 해석과 다음 검토",
        "",
        "보조 발생기/물리 호스트 표본은 수집기 수정 후 18:41 KST부터 보존됐으므로 100명 구간 전체를 포함하지 않는다. VM 7대 기본 자원 기록은 시험 시작부터 유지했다. CPU는 Prometheus 1분 평균의 최고값이고, Mongo는 약 30초마다 얻은 1초 SSH 표본이다. 순간 피크·짧은 잠금은 놓칠 수 있다. Mongo 디스크 I/O는 100명 종료 뒤부터 추가했으므로 100명 표본은 N/A다. 디스크 상세 IOPS·처리량·평균 I/O 시간·iowait·스왑은 prometheus-range.json에 보관했다.",
        "",
        "- 소프트웨어/하드웨어를 이번에 조정하지 않았다. CPU·RAM·디스크 여유와 지연이 모두 양호하면 증설이나 동시성 제한 상향을 먼저 할 근거가 약하다. 읽기 결과만으로 쓰기 여유를 보장하지 않는다.",
        "- 앱 DB 풀 획득 대기는 현재 계측하지 않았다. DB 연결/행 잠금 표본이 낮다고 풀 대기가 전혀 없었다고 단정하지 않는다.",
        "- FastAPI 지표는 현재 scrape에 잡힌 워커 기준이다. 전체 요청 판정은 Locust 원본과 두 Nginx 요청 로그를 우선한다.",
        "- 쓰기 확장은 사용자 검토 뒤 진행한다. 계정 공유로 병목을 만들지 않도록 VU당 합성 계정과 독립 시간 칸을 확보하며, 새 설정 적용 전후는 동일 프로토콜로 비교한다.",
        "- 다음 소프트웨어 비교 후보는 대기 중인 #67 Nginx keepalive·request_id/상류 지연 로그다. 먼저 현재 설정의 쓰기 기준선을 확보하고 한 항목씩 A/B 비교한다.\n- Claude의 대기 중 Nginx 변경이 적용됐다면 다음 쓰기/설정 비교 전에 지문을 다시 확인하고 변경점을 별도 기록한다.",
        "",
        "## 기록 위치",
        "",
        "requests.jsonl/Locust CSV·HTML: 단계별 원본. resources.jsonl: 7대 CPU·RAM·디스크/DB 집계. prometheus-range.json 및 db-resource-summary.json: 33종 구간 지표. generator-host-resources.jsonl: 발생기/VMware 호스트. server-evidence-*.json: 두 Nginx 정규화 요청·7대 서비스 오류 패턴 집계·설정 지문. Grafana 원본/폴링 검증도 같은 폴더에 보존했다. 인증정보·사용자 글·SQL 원문은 저장하지 않았다.",
        "",
    ]
    if suite.get("error"):
        lines += ["중단 원인: " + suite["error"], ""]
    (report / "READ_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(str(report / "READ_REVIEW.md"))


if __name__ == "__main__":
    main()
