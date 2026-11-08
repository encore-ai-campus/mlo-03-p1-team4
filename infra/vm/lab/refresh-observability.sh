#!/bin/bash
# 이미 설치한 시험 VM의 관측 설정만 갱신한다. 앱·DB 설정은 변경하지 않는다.
set -euo pipefail
role=${1:?gw/api1/api2/mon}
sed -i 's/^CUSTOM_ARGS=.*/CUSTOM_ARGS="--server.http.listen-addr=0.0.0.0:12345"/' /etc/default/alloy
ufw allow from 192.168.0.217 to any port 12345 proto tcp
systemctl restart alloy
if test "$role" = mon; then
  promtool check config /tmp/observability/prometheus.yml
  install -m 644 /tmp/observability/prometheus.yml /etc/prometheus/prometheus.yml
  cp /tmp/observability/dashboard-*.json /var/lib/grafana/dashboards/
  chown grafana:grafana /var/lib/grafana/dashboards/dashboard-*.json
  systemctl restart prometheus
fi
echo "OBSERVABILITY_READY=$role"
