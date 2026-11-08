#!/usr/bin/env bash
# 읽기 전용 수집: 109에서 각 VM의 사양·디스크·주요 설정을 출력한다. 아무것도 바꾸지 않는다.
K=~/.config/spacecube109
run() { ssh -o BatchMode=yes -o ConnectTimeout=6 -o UserKnownHostsFile=$K/known_hosts -i $K/id_ed25519 "$1@192.168.219.$2" "$3" 2>&1; }
COMMON='echo "cpu=$(nproc) mem_MiB=$(free -m | awk "/Mem:/{print \$2}") avail_MiB=$(free -m | awk "/Mem:/{print \$7}") swap_MiB=$(free -m | awk "/Swap:/{print \$2}") up=$(uptime -p)"; lsblk -dno NAME,SIZE,TYPE | grep disk; df -h / | tail -1; echo "loadavg $(cat /proc/loadavg)"; awk "\$3 ~ /^(sda|nvme0n1)$/ {print \"diskstats\",\$3,\"reads\",\$4,\"writes\",\$8,\"io_ms\",\$13}" /proc/diskstats; cat /sys/block/sda/queue/scheduler 2>/dev/null'
for t in "ubuntu 218 gw" "ubuntu 214 api1" "ubuntu 215 api2" "ubuntu 217 mon" "ubuntu 212 db1" "ubuntu 213 db2" "test 216 mongo"; do
  set -- $t; echo "################ $3 (.${2})"; run $1 $2 "$COMMON"
  case $3 in
    gw) run $1 $2 'sudo -n grep -vE "^\s*(#|$)" /etc/haproxy/haproxy.cfg; haproxy -v | head -1';;
    api1|api2) run $1 $2 'systemctl cat spacecube | grep -E "ExecStart|LimitNOFILE"; grep -E "worker_processes|worker_connections|keepalive_timeout|multi_accept" /etc/nginx/nginx.conf; grep -nE "pool_size|max_overflow|pool_timeout|pool_recycle|pool_pre_ping" /opt/spacecube/backend/app/core/db.py; grep -nE "ThreadPool|max_workers|thread" /opt/spacecube/backend/app/core/events.py | head -5; ulimit -n; ps -o pid,rss,cmd -C uvicorn,python3 --no-headers | cut -c1-140 | head -6';;
    mon) run $1 $2 'grep -nE "retention|compactor|delete|period|max_query|chunk" /etc/loki/config.yml 2>/dev/null | head -20; systemctl cat prometheus 2>/dev/null | grep -E "ExecStart|ARGS"; grep -E "^ARGS" /etc/default/prometheus 2>/dev/null; sudo -n du -sh /var/lib/prometheus /var/lib/loki /var/lib/grafana 2>/dev/null';;
    db1|db2) run $1 $2 'sudo -n mariadb -N -e "SELECT @@innodb_buffer_pool_size/1048576 bp_MiB, @@max_connections, @@thread_cache_size, @@innodb_log_file_size/1048576 log_MiB, @@innodb_flush_log_at_trx_commit, @@sync_binlog, @@innodb_io_capacity, @@table_open_cache, @@tmp_table_size/1048576, @@performance_schema, @@thread_handling, @@innodb_flush_method, @@binlog_format; SHOW GLOBAL STATUS WHERE Variable_name IN (\"Max_used_connections\",\"Threads_created\",\"Innodb_buffer_pool_reads\",\"Innodb_buffer_pool_read_requests\",\"Innodb_row_lock_waits\",\"Innodb_row_lock_time_max\",\"Created_tmp_disk_tables\",\"Aborted_connects\",\"Connection_errors_max_connections\"); SELECT ROUND(SUM(data_length+index_length)/1048576,1) FROM information_schema.tables WHERE table_schema=\"spacecube\";" 2>&1; sudo -n du -sh /var/lib/mysql';;
    mongo) run $1 $2 'grep -vE "^\s*(#|$)" /etc/mongod.conf; mongod --version | head -1; sudo -n du -sh /var/lib/mongodb 2>&1 | tail -1; ps -o rss,cmd -C mongod --no-headers | cut -c1-80; sudo -n ufw status 2>&1 | head -1';;
  esac
done
