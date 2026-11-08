  # 정기 실행(11-07 Claude): api1 한 대에서만. 이용 완료 배치(F-35) 매시 5분, event_daily 집계 매시 20분.
  if [ "$ROLE" = api1 ]; then
    cat > /etc/systemd/system/spacecube-complete.service <<EOF
[Unit]
Description=Spacecube 이용 완료 배치 (F-35)
[Service]
Type=oneshot
User=spacecube
Group=adm
WorkingDirectory=/opt/spacecube/backend
EnvironmentFile=/etc/spacecube/.env
Environment=SERVER_NAME=api1-job
Environment=LOG_DIR=/opt/spacecube/backend/logs
ExecStart=/opt/spacecube/venv/bin/python -m app.jobs.complete_reservations
EOF
    cat > /etc/systemd/system/spacecube-complete.timer <<EOF
[Unit]
Description=Spacecube 이용 완료 배치 매시 5분
[Timer]
OnCalendar=*-*-* *:05:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
    cat > /etc/systemd/system/spacecube-event-daily.service <<EOF
[Unit]
Description=Spacecube event_daily 집계 (어제·오늘)
[Service]
Type=oneshot
User=spacecube
Group=adm
WorkingDirectory=/opt/spacecube
EnvironmentFile=/etc/spacecube/.env
ExecStart=/opt/spacecube/venv/bin/python /opt/spacecube/db/aggregate/event_daily.py --days 2
EOF
    cat > /etc/systemd/system/spacecube-event-daily.timer <<EOF
[Unit]
Description=Spacecube event_daily 집계 매시 20분
[Timer]
OnCalendar=*-*-* *:20:00
Persistent=true
[Install]
WantedBy=timers.target
EOF
    cat > /etc/systemd/system/spacecube-crawler.service <<EOF
[Unit]
Description=Spacecube 크롤러 주간 신규 등록 (F-61, 상세 20건 이하)
[Service]
Type=oneshot
WorkingDirectory=/opt/spacecube
EnvironmentFile=/etc/spacecube/.env
Environment=PYTHONPATH=/opt/spacecube:/opt/spacecube/backend
ExecStart=/opt/spacecube/venv/bin/python -m crawler.crawl_venues run --site spacecloud --mode weekly --max-detail 20
NoNewPrivileges=true
EOF
    cat > /etc/systemd/system/spacecube-crawler.timer <<EOF
[Unit]
Description=Spacecube 크롤러 매주 월요일 04:00
[Timer]
OnCalendar=Mon *-*-* 04:00:00
[Install]
WantedBy=timers.target
EOF
    /opt/spacecube/venv/bin/pip install -q httpx==0.28.1 beautifulsoup4==4.15.0
    systemctl daemon-reload
    systemctl enable --now spacecube-complete.timer spacecube-event-daily.timer spacecube-crawler.timer
  fi
