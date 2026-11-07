"""승인한 시험 구간의 DB/앱 지표를 Prometheus에서 집계해 보존한다."""

import argparse
import json
import math
from pathlib import Path

import requests

PROM = "http://192.168.219.217:9090"
QUERIES = {
    "db_max_used_connections": 'mysql_global_status_max_used_connections{job="mariadb"}',
    "db_connections": 'mysql_global_status_threads_connected{job="mariadb"}',
    "db_running": 'mysql_global_status_threads_running{job="mariadb"}',
    "db_connection_errors": 'mysql_global_status_connection_errors_total{job="mariadb"}',
    "db_aborted_connects": 'mysql_global_status_aborted_connects{job="mariadb"}',
    "db_deadlocks": 'mysql_global_status_innodb_deadlocks{job="mariadb"}',
    "db_lock_waits": 'mysql_info_schema_innodb_metrics_lock_lock_row_lock_waits_total{job="mariadb"}',
    "db_replication_lag": 'mysql_slave_status_seconds_behind_master{job="mariadb"}',
    "db_replication_io": 'mysql_slave_status_slave_io_running{job="mariadb"}',
    "db_replication_sql": 'mysql_slave_status_slave_sql_running{job="mariadb"}',
    "db_table_sizes": 'mysql_info_schema_table_size{job="mariadb",schema="spacecube",component=~"data_length|index_length"}',
    "app_connections": "spacecube_db_app_connections",
    "app_state_age": "spacecube_db_app_state_age_seconds_max",
    "app_lock_waits": "spacecube_db_app_lock_waits",
    "app_lock_seconds": "spacecube_db_app_lock_wait_seconds_max",
    "cpu": '100*(1-avg by(server)(rate(node_cpu_seconds_total{job="nodes",mode="idle"}[1m])))',
    "memory": '100*(1-node_memory_MemAvailable_bytes{job="nodes"}/node_memory_MemTotal_bytes{job="nodes"})',
    "disk_free": 'node_filesystem_avail_bytes{job="nodes",mountpoint="/"}',
    "replica_fallbacks": "db_read_fallback_total",
    "mongo_write_failures": "mongo_event_write_failures_total",
}


QUERIES.update(
    {
        "db_write_commands_rate": 'rate(mysql_global_status_commands_total{job="mariadb",command=~"insert|update|delete|commit|rollback"}[1m])',
        "haproxy_sessions": 'haproxy_server_current_sessions{proxy="apps"}',
        "haproxy_queue": 'haproxy_server_current_queue{proxy="apps"}',
        "haproxy_check_failures": 'haproxy_server_check_failures_total{proxy="apps"}',
        "haproxy_up_down": 'haproxy_server_check_up_down_total{proxy="apps"}',
        "haproxy_downtime": 'haproxy_server_downtime_seconds_total{proxy="apps"}',
        "db_questions_rate": 'rate(mysql_global_status_questions{job="mariadb"}[1m])',
        "cpu_iowait": '100*avg by(server)(rate(node_cpu_seconds_total{job="nodes",mode="iowait"}[1m]))',
        "disk_busy": '100*rate(node_disk_io_time_seconds_total{job="nodes",device=~"sd[a-z]|nvme[0-9]+n[0-9]+"}[1m])',
        "disk_read_bytes": 'rate(node_disk_read_bytes_total{job="nodes",device=~"sd[a-z]|nvme[0-9]+n[0-9]+"}[1m])',
        "disk_write_bytes": 'rate(node_disk_written_bytes_total{job="nodes",device=~"sd[a-z]|nvme[0-9]+n[0-9]+"}[1m])',
        "disk_read_iops": 'rate(node_disk_reads_completed_total{job="nodes",device=~"sd[a-z]|nvme[0-9]+n[0-9]+"}[1m])',
        "disk_write_iops": 'rate(node_disk_writes_completed_total{job="nodes",device=~"sd[a-z]|nvme[0-9]+n[0-9]+"}[1m])',
        "disk_average_read_seconds": 'rate(node_disk_read_time_seconds_total{job="nodes"}[1m])/rate(node_disk_reads_completed_total{job="nodes"}[1m])',
        "disk_average_write_seconds": 'rate(node_disk_write_time_seconds_total{job="nodes"}[1m])/rate(node_disk_writes_completed_total{job="nodes"}[1m])',
        "swap_free": 'node_memory_SwapFree_bytes{job="nodes"}',
        "swap_total": 'node_memory_SwapTotal_bytes{job="nodes"}',
        "load1": 'node_load1{job="nodes"}',
        "backend_up": 'haproxy_server_status{proxy="apps",state="UP"}',
        "http_status_rate": 'sum by(server,method,status)(rate(http_requests_total{job="api"}[1m]))',
    }
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    suite = json.loads((args.report / "suite.json").read_text())
    rows = suite["results"]
    # 예열에서 중단한 단계도 보존한다. 측정 구간별 집계는 보고서에서 따로 자른다.
    observations = [
        json.loads(line)
        for line in (args.report / "resources.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    start = min([r["start"] for r in rows] + [r["time"] for r in observations])
    end = max([r["end"] for r in rows] + [r["time"] for r in observations])
    raw, summary = {}, {}
    for name, query in QUERIES.items():
        response = requests.get(
            PROM + "/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": 15},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("status") != "success":
            raise RuntimeError("query_failed_" + name)
        raw[name] = result["data"]["result"]
        summary[name] = []
        for series in raw[name]:
            values = [
                (stamp, float(value))
                for stamp, value in series["values"]
                if math.isfinite(float(value))
            ]
            if not values:
                continue
            peak = max(values, key=lambda point: point[1])
            summary[name].append(
                {
                    "labels": series["metric"],
                    "samples": len(values),
                    "first": values[0][1],
                    "last": values[-1][1],
                    "min": min(v for _, v in values),
                    "max": peak[1],
                    "peak_time": peak[0],
                    "last_minus_first": values[-1][1] - values[0][1],
                }
            )
    for name, data in [
        ("prometheus-range.json", raw),
        ("db-resource-summary.json", {"start": start, "end": end, "series": summary}),
    ]:
        (args.report / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "queries": len(raw),
                "empty": [name for name, series in raw.items() if not series],
                "start": start,
                "end": end,
            }
        )
    )


if __name__ == "__main__":
    main()
