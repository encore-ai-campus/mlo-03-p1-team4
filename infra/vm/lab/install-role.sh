#!/bin/bash
# 새 시험 VM 전용. 기존 DB 주소에는 접속하지 않는다.
set -euo pipefail
ROLE=${1:?gw/api1/api2/mon}
export DEBIAN_FRONTEND=noninteractive
# 제공 OVA는 20GB 디스크 중 10GB만 루트에 할당한다. 새 시험 VM 안의 남은 VG 공간만 사용한다.
if test "$(findmnt -no SOURCE /)" = /dev/mapper/ubuntu--vg-ubuntu--lv; then
  free_extents=$(vgs --noheadings -o vg_free_count ubuntu-vg | tr -d ' ')
  if test "$free_extents" -gt 0; then
    lvextend --resizefs -l +100%FREE /dev/ubuntu-vg/ubuntu-lv
  fi
fi
systemctl restart systemd-journald
install -d /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=128M\nRuntimeMaxUse=64M\n' > /etc/systemd/journald.conf.d/spacecube-lab.conf
hostnamectl set-hostname "spacecube-$ROLE"
cat >> /etc/hosts <<'EOF'
192.168.0.211 gw
192.168.0.212 db1
192.168.0.213 db2
192.168.0.214 api1
192.168.0.215 api2
192.168.0.216 mongo
192.168.0.217 mon
EOF
cat > /etc/alloy/config.alloy <<EOF
# 로그는 Alloy -> Loki, 메트릭은 Prometheus pull 경로로 수집한다.
# Alloy remote_write로 바꾸려면 Prometheus receiver·방화벽·중복 scrape 전환을 별도로 검증한다.
logging { level = "info" }
loki.source.journal "system" {
  max_age = "1h"
  labels = { job = "journal", server = "$ROLE" }
  forward_to = [loki.write.local.receiver]
}
local.file_match "logs" {
  path_targets = [
    {__path__ = "/var/log/nginx/spacecube-access.log", job = "nginx", server = "$ROLE"},
    {__path__ = "/opt/spacecube/backend/logs/*.log", job = "api", server = "$ROLE"},
  ]
}
loki.source.file "logs" {
  targets = local.file_match.logs.targets
  forward_to = [loki.write.local.receiver]
}
loki.write "local" {
  endpoint { url = "http://192.168.0.217:3100/loki/api/v1/push" }
}
EOF
usermod -aG adm,systemd-journal alloy
case "$ROLE" in
gw)
  apt-get -o DPkg::Lock::Timeout=180 install -y haproxy
  install -m 644 /tmp/lab/haproxy.cfg /etc/haproxy/haproxy.cfg
  haproxy -c -f /etc/haproxy/haproxy.cfg
  systemctl enable --now haproxy
  systemctl restart haproxy
  ;;
api1|api2)
  apt-get -o DPkg::Lock::Timeout=180 install -y nginx prometheus-nginx-exporter
  id spacecube >/dev/null 2>&1 || useradd --system --home-dir /opt/spacecube --shell /usr/sbin/nologin spacecube
  install -d /opt/spacecube /var/www/spacecube
  tar -xzf /tmp/payload.tar.gz -C /opt/spacecube
  cp -a /opt/spacecube/frontend/dist/. /var/www/spacecube/
  python3 -m venv /opt/spacecube/venv
  /opt/spacecube/venv/bin/pip install -r /tmp/lab/backend-requirements.txt
  install -d -m 750 -o spacecube -g adm /opt/spacecube/backend/logs
  cat > /etc/systemd/system/spacecube.service <<EOF
[Unit]
Description=Spacecube FastAPI ($ROLE)
After=network-online.target
Wants=network-online.target
[Service]
User=spacecube
Group=adm
WorkingDirectory=/opt/spacecube/backend
EnvironmentFile=/etc/spacecube/.env
Environment=SERVER_NAME=$ROLE
Environment=LOG_DIR=/opt/spacecube/backend/logs
ExecStart=/opt/spacecube/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --limit-concurrency 200 --timeout-keep-alive 5
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
  install -m 644 /tmp/lab/nginx.conf /etc/nginx/conf.d/spacecube.conf
  test ! -f /etc/nginx/sites-enabled/default || unlink /etc/nginx/sites-enabled/default
  nginx -t
  printf 'ARGS="-nginx.scrape-uri=http://127.0.0.1:8080/nginx_status"\n' > /etc/default/prometheus-nginx-exporter
  systemctl daemon-reload
  systemctl enable --now spacecube nginx prometheus-nginx-exporter
  systemctl restart spacecube nginx prometheus-nginx-exporter
  cat > /etc/logrotate.d/spacecube <<'EOF'
/opt/spacecube/backend/logs/*.log {
    daily
    maxsize 10M
    rotate 3
    missingok
    notifempty
    compress
    delaycompress
    create 0640 spacecube adm
    su spacecube adm
}
EOF
  ;;
mon)
  apt-get -o DPkg::Lock::Timeout=180 install -y prometheus grafana loki
  install -m 644 /tmp/lab/prometheus.yml /etc/prometheus/prometheus.yml
  printf 'ARGS="--config.file=/etc/prometheus/prometheus.yml --storage.tsdb.path=/var/lib/prometheus/metrics2/ --storage.tsdb.retention.time=2d --storage.tsdb.retention.size=2GB"\n' > /etc/default/prometheus
  install -d -o loki -g "$(id -gn loki)" /var/lib/loki
  install -m 644 /tmp/lab/loki.yml /etc/loki/config.yml
  install -d /etc/systemd/system/loki.service.d
  cat > /etc/systemd/system/loki.service.d/override.conf <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/loki -config.file=/etc/loki/config.yml
EOF
  install -d /etc/grafana/provisioning/datasources /etc/grafana/provisioning/dashboards /var/lib/grafana/dashboards
  cat > /etc/grafana/provisioning/datasources/spacecube.yml <<'EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://localhost:9090
    isDefault: true
  - name: Loki
    uid: loki
    type: loki
    access: proxy
    url: http://localhost:3100
EOF
  cat > /etc/grafana/provisioning/dashboards/spacecube.yml <<'EOF'
apiVersion: 1
providers:
  - name: Spacecube
    folder: Spacecube Lab
    type: file
    allowUiUpdates: true
    disableDeletion: true
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
EOF
  cp /tmp/lab/dashboard-*.json /var/lib/grafana/dashboards/
  chown -R grafana:grafana /var/lib/grafana/dashboards
  install -d /etc/systemd/system/grafana-server.service.d
  if test ! -f /etc/grafana/.env; then
    umask 077
    printf 'GF_SECURITY_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 20)" > /etc/grafana/.env
  fi
  cat > /etc/systemd/system/grafana-server.service.d/lab.conf <<'EOF'
[Service]
Environment=GF_SECURITY_ADMIN_USER=admin
EnvironmentFile=/etc/grafana/.env
Environment=GF_USERS_ALLOW_SIGN_UP=false
Environment=GF_ANALYTICS_REPORTING_ENABLED=false
EOF
  promtool check config /etc/prometheus/prometheus.yml
  systemctl daemon-reload
  systemctl enable --now prometheus loki grafana-server
  systemctl restart prometheus loki grafana-server
  ;;
*) exit 2 ;;
esac
systemctl enable --now alloy
sed -i 's/^CUSTOM_ARGS=.*/CUSTOM_ARGS="--server.http.listen-addr=0.0.0.0:12345"/' /etc/default/alloy
systemctl restart alloy
# 시험 PC와 서비스 사이에 필요한 포트만 허용한다.
ufw default deny incoming
ufw default allow outgoing
ufw allow from 192.168.0.19 to any port 22 proto tcp
ufw allow from 192.168.0.109 to any port 22 proto tcp
ufw allow from 192.168.0.217 to any port 9100 proto tcp
ufw allow from 192.168.0.217 to any port 12345 proto tcp
case "$ROLE" in
gw)
  ufw allow from 192.168.0.0/24 to any port 80 proto tcp
  ufw allow from 192.168.0.217 to any port 8404 proto tcp
  ufw allow from 192.168.0.19 to any port 8404 proto tcp
  ;;
api1|api2)
  ufw allow from 192.168.0.211 to any port 80 proto tcp
  ufw allow from 192.168.0.19 to any port 80 proto tcp
  ufw allow from 192.168.0.217 to any port 8000 proto tcp
  ufw allow from 192.168.0.217 to any port 9113 proto tcp
  ;;
mon)
  ufw allow from 192.168.0.0/24 to any port 3000 proto tcp
  ufw allow from 192.168.0.19 to any port 9090 proto tcp
  for ip in 192.168.0.211 192.168.0.214 192.168.0.215 192.168.0.217; do
    ufw allow from "$ip" to any port 3100 proto tcp
  done
  ;;
esac
ufw --force enable
dpkg-query -W -f='${Package}=${Version}\n' > /var/log/spacecube-package-versions.txt
echo "ROLE_READY=$ROLE"
