# Grafana 대시보드 JSON · DASH-003

11-07 쓰기 시험 종료 후 저장한 provisioning 원본 11개입니다. 예약 통계는 워커 표본이며 정확한 실험 건수는 별도 집계 문서를 봅니다.

## dashboard-alloy.json

```json
{
  "uid": "spacecube-alloy",
  "title": "Spacecube / Alloy · 로그 수집·전송",
  "schemaVersion": 39,
  "version": 101,
  "refresh": "15s",
  "panels": [
    {
      "id": 1,
      "title": "Alloy 수집 상태",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "up{job=\"alloy\"}",
          "legendFormat": "{{server}}",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN",
                  "color": "red"
                },
                "1": {
                  "text": "UP",
                  "color": "green"
                }
              }
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 12,
        "h": 3
      }
    },
    {
      "id": 2,
      "title": "설정 로드 성공",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "alloy_config_last_load_successful{job=\"alloy\"}",
          "legendFormat": "{{server}}",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN",
                  "color": "red"
                },
                "1": {
                  "text": "UP",
                  "color": "green"
                }
              }
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 12,
        "y": 0,
        "w": 12,
        "h": 3
      }
    },
    {
      "id": 3,
      "title": "Loki 전달 로그 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(loki_write_sent_entries_total{job=\"alloy\"}[2m]))",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ops",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 4,
      "title": "전송 재시도 누계",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(loki_write_batch_retries_total{job=\"alloy\"})",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 5,
      "title": "전송 유실 누계",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(loki_write_dropped_entries_total{job=\"alloy\"})",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 6,
      "title": "활성 파일 수 (gw·mon은 journal만 수집)",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "loki_source_file_files_active_total{job=\"alloy\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 7,
      "title": "journal 수집 누계",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "loki_source_journal_target_lines_total{job=\"alloy\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 8,
      "title": "Alloy 메모리",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "process_resident_memory_bytes{job=\"alloy\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 100,
      "title": "관련 로그 · Loki",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"journal\"} |= \"alloy\""
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 24,
        "w": 24,
        "h": 9
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "tags": [
    "spacecube",
    "lab"
  ],
  "description": "109 최소 사양 시험. MariaDB primary·replica exporter가 수집 중이며 MongoDB는 제외했습니다. FastAPI 지표는 현재 수집 워커 기준. 빈 구간은 0을 뜻하지 않습니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-api.json

```json
{
  "uid": "spacecube-api",
  "title": "Spacecube / FastAPI",
  "schemaVersion": 39,
  "version": 103,
  "refresh": "15s",
  "panels": [
    {
      "id": 1,
      "title": "FastAPI 프로세스 수집 상태 (DB 상태와 별개)",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "up{job=\"api\"}",
          "legendFormat": "{{server}}",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN",
                  "color": "red"
                },
                "1": {
                  "text": "UP",
                  "color": "green"
                }
              }
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 24,
        "h": 3
      }
    },
    {
      "id": 2,
      "title": "초당 API 요청",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(http_requests_total{job=\"api\"}[$__rate_interval]))"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 12,
        "h": 7
      },
      "description": ""
    },
    {
      "id": 3,
      "title": "HTTP 상태코드별 API 요청률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server,status)(rate(http_requests_total{job=\"api\"}[$__rate_interval]))"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 12,
        "h": 7
      },
      "description": ""
    },
    {
      "id": 4,
      "title": "API 응답 지연 p50 / p95 / p99",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "1000 * histogram_quantile(0.50, sum by(le,server)(rate(http_request_duration_seconds_bucket{job=\"api\"}[$__rate_interval])))",
          "legendFormat": "{{server}} · p50"
        },
        {
          "refId": "B",
          "expr": "1000 * histogram_quantile(0.95, sum by(le,server)(rate(http_request_duration_seconds_bucket{job=\"api\"}[$__rate_interval])))",
          "legendFormat": "{{server}} · p95"
        },
        {
          "refId": "C",
          "expr": "1000 * histogram_quantile(0.99, sum by(le,server)(rate(http_request_duration_seconds_bucket{job=\"api\"}[$__rate_interval])))",
          "legendFormat": "{{server}} · p99"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ms",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 10,
        "w": 12,
        "h": 7
      },
      "description": "FastAPI 히스토그램 버킷에서 계산한 서버별 백분위입니다. 단위는 ms."
    },
    {
      "id": 5,
      "title": "워커 프로세스 메모리 (수집된 워커)",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "process_resident_memory_bytes{job=\"api\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 6,
      "title": "MongoDB 이벤트 전달 실패",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mongo_event_write_failures_total",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 17,
        "w": 12,
        "h": 7
      },
      "description": "MongoDB는 현재 온라인입니다. 응답 뒤 저장 실패 누계이며 문서 수나 저장 완료 건수가 아닙니다."
    },
    {
      "id": 7,
      "title": "API 5xx 요청률 · 상태코드별",
      "description": "503 등 서버 오류를 발생 서버와 상태코드별로 비교합니다.",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server,status)(rate(http_requests_total{job=\"api\",status=~\"5..\"}[$__rate_interval]))",
          "legendFormat": "{{server}} · {{status}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "custom": {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 8,
      "title": "API 응답 지연 분포 · 시간별",
      "description": "각 시점의 요청 지연시간 분포입니다. 밝은 구간은 요청이 몰린 지연 버킷입니다.",
      "type": "heatmap",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(le)(rate(http_request_duration_seconds_bucket{job=\"api\"}[$__rate_interval]))",
          "legendFormat": "{{le}}",
          "format": "heatmap"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {},
      "gridPos": {
        "x": 0,
        "y": 24,
        "w": 24,
        "h": 8
      }
    },
    {
      "id": 9,
      "title": "5xx 발생 경로 · 선택 기간 상위 10개",
      "description": "선택 기간에 5xx가 많이 발생한 API 경로와 코드입니다.",
      "type": "table",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "topk(10,sum by(handler,status)(increase(http_requests_total{job=\"api\",status=~\"5..\"}[$__range])))",
          "instant": true,
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "showHeader": true,
        "cellHeight": "sm",
        "sortBy": []
      },
      "gridPos": {
        "x": 0,
        "y": 32,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 100,
      "title": "관련 로그 · Loki",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"api\"}"
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 39,
        "w": 24,
        "h": 9
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "tags": [
    "spacecube",
    "lab"
  ],
  "description": "API RED 상세: 요청률·상태코드·지연 백분위와 히스토그램, 5xx 경로를 살펴봅니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-db-connections.json

```json
{
  "uid": "spacecube-db-connections",
  "title": "Spacecube / DB 연결·대기",
  "schemaVersion": 39,
  "version": 1,
  "timezone": "Asia/Seoul",
  "refresh": "15s",
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "tags": [
    "spacecube",
    "db",
    "loadtest"
  ],
  "panels": [
    {
      "id": 1,
      "type": "timeseries",
      "title": "API 서버별 Sleep / Query 연결 수",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "targets": [
        {
          "expr": "spacecube_db_app_connections{job=\"nodes\"}",
          "refId": "A",
          "legendFormat": "{{server}} / {{app}} / {{command}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 2,
      "type": "timeseries",
      "title": "API 서버별 InnoDB 행 잠금 대기 연결",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "targets": [
        {
          "expr": "spacecube_db_app_lock_waits{job=\"nodes\"}",
          "refId": "A",
          "legendFormat": "{{server}} / {{app}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 3,
      "type": "timeseries",
      "title": "Query 상태 체류 시간 최대",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 0,
        "y": 7
      },
      "targets": [
        {
          "expr": "spacecube_db_app_state_age_seconds_max{job=\"nodes\",command=\"Query\"}",
          "refId": "A",
          "legendFormat": "{{server}} / {{app}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 4,
      "type": "timeseries",
      "title": "Sleep 유휴 상태 시간 최대",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 12,
        "y": 7
      },
      "targets": [
        {
          "expr": "spacecube_db_app_state_age_seconds_max{job=\"nodes\",command=\"Sleep\"}",
          "refId": "A",
          "legendFormat": "{{server}} / {{app}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 5,
      "type": "timeseries",
      "title": "현재 행 잠금 대기 시간 최대",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 0,
        "y": 14
      },
      "targets": [
        {
          "expr": "spacecube_db_app_lock_wait_seconds_max{job=\"nodes\"}",
          "refId": "A",
          "legendFormat": "{{server}} / {{app}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 6,
      "type": "timeseries",
      "title": "DB 전체 연결 수 / 실행 쿼리",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 12,
        "y": 14
      },
      "targets": [
        {
          "expr": "mysql_global_status_threads_running{job=\"mariadb\"}",
          "refId": "A",
          "legendFormat": "{{server}} / running"
        },
        {
          "expr": "mysql_global_status_threads_connected{job=\"mariadb\"}",
          "refId": "B",
          "legendFormat": "{{server}} / connected"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 7,
      "type": "timeseries",
      "title": "연결 집계 수집 오류 (정상 0)",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 0,
        "y": 21
      },
      "targets": [
        {
          "expr": "spacecube_db_app_metrics_error{job=\"nodes\"}",
          "refId": "A",
          "legendFormat": "{{server}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    },
    {
      "id": 8,
      "type": "timeseries",
      "title": "연결 집계 마지막 갱신 후 경과",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "h": 7,
        "w": 12,
        "x": 12,
        "y": 21
      },
      "targets": [
        {
          "expr": "time() - spacecube_db_app_observed_timestamp_seconds{job=\"nodes\"}",
          "refId": "A",
          "legendFormat": "{{server}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 8,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "tooltip": {
          "mode": "multi"
        },
        "legend": {
          "displayMode": "table",
          "placement": "bottom",
          "calcs": [
            "lastNotNull",
            "max"
          ]
        }
      }
    }
  ],
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "description": "원본 IP별 집계만 표시. Query 상태 체류 시간은 전체 요청 지연과 다르고 Sleep 시간은 대기 중인 유휴 연결의 나이다. 행 잠금 대기는 INNODB_TRX의 현재 대기 시간이다. 15초 집계/스크랩이므로 짧은 피크는 놓칠 수 있다."
}

```

## dashboard-haproxy.json

```json
{
  "uid": "spacecube-haproxy",
  "title": "Spacecube / HAProxy",
  "schemaVersion": 39,
  "version": 102,
  "refresh": "15s",
  "panels": [
    {
      "id": 1,
      "title": "앱 서버 UP",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "haproxy_server_status{proxy=\"apps\",state=\"UP\"}",
          "legendFormat": "{{server}}",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN",
                  "color": "red"
                },
                "1": {
                  "text": "UP",
                  "color": "green"
                }
              }
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 24,
        "h": 3
      }
    },
    {
      "id": 2,
      "title": "서버별 분산 요청 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "rate(haproxy_server_loadbalanced_total{proxy=\"apps\"}[2m])",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 3,
      "title": "서버별 누적 분산 요청",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "haproxy_server_loadbalanced_total{proxy=\"apps\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 4,
      "title": "서버별 활성 세션",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "haproxy_server_current_sessions{proxy=\"apps\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 5,
      "title": "헬스체크 실패 누계",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "haproxy_server_check_failures_total{proxy=\"apps\"}",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 6,
      "title": "서버별 평균 응답 시간",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "1000 * (haproxy_server_response_time_average_seconds{proxy=\"apps\"})",
          "legendFormat": "{{server}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ms",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 200,
      "title": "기간별 서버 분산 요청",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "increase(haproxy_server_loadbalanced_total{proxy=\"apps\"}[$__range])",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 201,
      "title": "분산 비율 % · 최근 속도 기준",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * rate(haproxy_server_loadbalanced_total{proxy=\"apps\"}[$__rate_interval]) / ignoring(server) group_left sum without(server)(rate(haproxy_server_loadbalanced_total{proxy=\"apps\"}[$__rate_interval]))",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 24,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 202,
      "title": "서버별 HTTP 5xx / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(haproxy_server_http_responses_total{proxy=\"apps\",code=\"5xx\"}[$__rate_interval]))",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 24,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 203,
      "title": "HAProxy→앱 활성 세션 · 워커 연결 수와 다름",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "haproxy_server_current_sessions{proxy=\"apps\"}",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 31,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 204,
      "title": "헬스체크 UP/DOWN 전환 · 기간 증가량",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "increase(haproxy_server_check_up_down_total{proxy=\"apps\"}[$__range])",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 31,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 205,
      "title": "서버별 평균 응답 시간 · HAProxy",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "1000 * (haproxy_server_response_time_average_seconds{proxy=\"apps\"})",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ms",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 38,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 206,
      "title": "동시성 제한 경고 · 서버별 분당 기록",
      "type": "timeseries",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(count_over_time({job=\"journal\",server=~\"api1|api2\"} |= \"Exceeded concurrency limit\" [1m]))",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 38,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 207,
      "title": "헬스 실패 누계 · 기간 증가량",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "increase(haproxy_server_check_failures_total{proxy=\"apps\"}[$__range])",
          "legendFormat": "{{server}}",
          "queryType": "range",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 45,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 221,
      "title": "지표 해석·미수집 항목",
      "type": "text",
      "options": {
        "mode": "markdown",
        "content": "요청 수·세션·경고 건수는 서로 다른 지표입니다. 경고 270:66 또는 8:0은 부하 비율이 아닙니다. 워커별 연결·실행 작업·DB 풀 대기는 아직 미수집입니다. Loki 빈 구간은 0건을 보장하지 않으며 수집 상태를 함께 보세요. 서버 제외 전후를 비교하세요."
      },
      "gridPos": {
        "x": 0,
        "y": 52,
        "w": 24,
        "h": 4
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    },
    {
      "id": 100,
      "title": "관련 로그 · Loki",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{server=\"gw\",job=\"journal\"}"
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 56,
        "w": 24,
        "h": 9
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    },
    {
      "id": 220,
      "title": "FastAPI 동시성 제한·HAProxy 제외 근거 로그",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"journal\",server=~\"api1|api2|gw\"} |~ \"Exceeded concurrency limit|Server apps/.*(DOWN|UP)|no server available\""
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 65,
        "w": 24,
        "h": 9
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "tags": [
    "spacecube",
    "lab"
  ],
  "description": "109 최소 사양 시험. MariaDB primary·replica exporter가 수집 중이며 MongoDB는 제외했습니다. FastAPI 지표는 현재 수집 워커 기준. 빈 구간은 0을 뜻하지 않습니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-logs.json

```json
{
  "uid": "spacecube-logs",
  "title": "Spacecube / 로그 탐색",
  "schemaVersion": 39,
  "version": 103,
  "refresh": "15s",
  "tags": [
    "spacecube",
    "lab"
  ],
  "panels": [
    {
      "id": 1,
      "title": "전체 로그",
      "description": "",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{server=~\"gw|api1|api2|mon\"}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 24,
        "h": 9
      }
    },
    {
      "id": 2,
      "title": "FastAPI 오류·503·동시성 제한",
      "description": "",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"api\",server=~\"api1|api2\"} |~ \"(?i)(ERROR|Exception|Traceback|503|Exceeded concurrency limit)\""
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 9,
        "w": 24,
        "h": 9
      }
    },
    {
      "id": 3,
      "title": "Nginx API 5xx 접근 로그",
      "description": "",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"nginx\",server=~\"api1|api2\"} | json | __error__=\"\" | path=~\"/api/.*\" | path!~\"/api/(health|metrics).*\" | status=~\"5..\""
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 18,
        "w": 24,
        "h": 9
      }
    },
    {
      "id": 4,
      "title": "서버·수집기 오류 로그",
      "description": "",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"journal\",server=~\"gw|api1|api2|mon\"} |~ \"(?i)(error|failed|down|retry|drop)\""
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 27,
        "w": 24,
        "h": 9
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "description": "같은 시간 범위에서 API 오류, Nginx 5xx, 시스템·수집기 로그를 확인합니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-loki.json

```json
{
  "uid": "spacecube-loki",
  "title": "Spacecube / Loki · 로그 저장·조회",
  "schemaVersion": 39,
  "version": 101,
  "refresh": "15s",
  "panels": [
    {
      "id": 1,
      "title": "Loki 수집 상태",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "up{job=\"loki\"}",
          "legendFormat": "{{instance}}",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN",
                  "color": "red"
                },
                "1": {
                  "text": "UP",
                  "color": "green"
                }
              }
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 24,
        "h": 3
      }
    },
    {
      "id": 2,
      "title": "수신 로그 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(loki_distributor_lines_received_total[2m]))",
          "legendFormat": "수신 로그",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ops",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 3,
      "title": "수신 바이트 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(loki_distributor_bytes_received_total[2m]))",
          "legendFormat": "수신량",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "Bps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 4,
      "title": "메모리 내 스트림",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(loki_ingester_memory_streams)",
          "legendFormat": "스트림",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 5,
      "title": "Loki 메모리",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "process_resident_memory_bytes{job=\"loki\"}",
          "legendFormat": "Loki",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 6,
      "title": "조회·수신 요청 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(route,status_code)(rate(loki_request_duration_seconds_count[2m]))",
          "legendFormat": "{{route}} · {{status_code}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 100,
      "title": "관련 로그 · Loki",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{server=~\"gw|api1|api2|mon\"}"
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 24,
        "w": 24,
        "h": 9
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "tags": [
    "spacecube",
    "lab"
  ],
  "description": "109 최소 사양 시험. MariaDB primary·replica exporter가 수집 중이며 MongoDB는 제외했습니다. FastAPI 지표는 현재 수집 워커 기준. 빈 구간은 0을 뜻하지 않습니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-mariadb.json

```json
{
  "uid": "spacecube-mariadb",
  "title": "Spacecube / MariaDB primary · replica",
  "schemaVersion": 39,
  "version": 101,
  "refresh": "15s",
  "tags": [
    "spacecube"
  ],
  "panels": [
    {
      "id": 1,
      "title": "DB exporter 정상 대수",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(mysql_up{job=\"mariadb\"})",
          "legendFormat": "",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "noValue": "수집 없음",
          "decimals": 0,
          "color": {
            "mode": "fixed",
            "fixedColor": "blue"
          }
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value",
        "justifyMode": "center",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 2
      }
    },
    {
      "id": 2,
      "title": "Replica I/O 스레드",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_slave_status_slave_io_running{job=\"mariadb\",server=\"db-replica\"}",
          "legendFormat": "",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "noValue": "수집 없음",
          "decimals": 0,
          "color": {
            "mode": "fixed",
            "fixedColor": "blue"
          }
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value",
        "justifyMode": "center",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 6,
        "y": 0,
        "w": 6,
        "h": 2
      }
    },
    {
      "id": 3,
      "title": "Replica SQL 스레드",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_slave_status_slave_sql_running{job=\"mariadb\",server=\"db-replica\"}",
          "legendFormat": "",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "noValue": "수집 없음",
          "decimals": 0,
          "color": {
            "mode": "fixed",
            "fixedColor": "blue"
          }
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value",
        "justifyMode": "center",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 12,
        "y": 0,
        "w": 6,
        "h": 2
      }
    },
    {
      "id": 4,
      "title": "Replica 복제 지연",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_slave_status_seconds_behind_master{job=\"mariadb\",server=\"db-replica\"}",
          "legendFormat": "",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "noValue": "수집 없음",
          "decimals": 0,
          "color": {
            "mode": "fixed",
            "fixedColor": "blue"
          }
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value",
        "justifyMode": "center",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 18,
        "y": 0,
        "w": 6,
        "h": 2
      }
    },
    {
      "id": 5,
      "title": "CPU 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - avg by(server) (rate(node_cpu_seconds_total{job=\"nodes\",server=~\"db-.*\",mode=\"idle\"}[$__rate_interval])))",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 2,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 6,
      "title": "메모리 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - node_memory_MemAvailable_bytes{job=\"nodes\",server=~\"db-.*\"} / node_memory_MemTotal_bytes{job=\"nodes\",server=~\"db-.*\"})",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 2,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 7,
      "title": "루트 디스크 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - node_filesystem_avail_bytes{job=\"nodes\",server=~\"db-.*\",mountpoint=\"/\"} / node_filesystem_size_bytes{job=\"nodes\",server=~\"db-.*\",mountpoint=\"/\"})",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 9,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 8,
      "title": "루트 디스크 남은 공간",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "node_filesystem_avail_bytes{job=\"nodes\",server=~\"db-.*\",mountpoint=\"/\"}",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 9,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 9,
      "title": "spacecube 데이터 · 인덱스 용량",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server,component) (mysql_info_schema_table_size{job=\"mariadb\",schema=\"spacecube\",component=~\"data_length|index_length\"})",
          "legendFormat": "{{server}} · {{component}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 16,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 10,
      "title": "현재 · 최고 · 허용 연결 수",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_global_status_threads_connected{job=\"mariadb\"}",
          "legendFormat": "{{server}} · 현재",
          "instant": false,
          "interval": "15s"
        },
        {
          "refId": "B",
          "expr": "mysql_global_status_max_used_connections{job=\"mariadb\"}",
          "legendFormat": "{{server}} · 최고",
          "instant": false,
          "interval": "15s"
        },
        {
          "refId": "C",
          "expr": "mysql_global_variables_max_connections{job=\"mariadb\"}",
          "legendFormat": "{{server}} · 허용",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 16,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 11,
      "title": "실행 중 쿼리 수",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_global_status_threads_running{job=\"mariadb\"}",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 23,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 12,
      "title": "연결 오류 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server) (rate(mysql_global_status_connection_errors_total{job=\"mariadb\"}[$__rate_interval]))",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 3
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 23,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 13,
      "title": "InnoDB 잠금 대기 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "rate(mysql_info_schema_innodb_metrics_lock_lock_row_lock_waits_total{job=\"mariadb\"}[$__rate_interval])",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 3
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 30,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 14,
      "title": "InnoDB 데드락 누적",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_info_schema_innodb_metrics_lock_lock_deadlocks{job=\"mariadb\"}",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 30,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 15,
      "title": "spacecube 테이블별 데이터 · 인덱스 용량",
      "type": "table",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_info_schema_table_size{job=\"mariadb\",schema=\"spacecube\",component=~\"data_length|index_length\"}",
          "format": "table",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "showHeader": true,
        "cellHeight": "sm"
      },
      "gridPos": {
        "x": 0,
        "y": 37,
        "w": 12,
        "h": 7
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "description": "MariaDB primary(.212)와 replica(.213)의 시스템 자원, 공간큐브 용량, 연결, InnoDB 잠금 및 복제 상태.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-nginx.json

```json
{
  "uid": "spacecube-nginx",
  "title": "Spacecube / Nginx",
  "schemaVersion": 39,
  "version": 102,
  "refresh": "15s",
  "panels": [
    {
      "id": 1,
      "title": "Nginx 수집 상태",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "nginx_up",
          "legendFormat": "{{instance}}",
          "instant": true,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN",
                  "color": "red"
                },
                "1": {
                  "text": "UP",
                  "color": "green"
                }
              }
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 24,
        "h": 3
      }
    },
    {
      "id": 2,
      "title": "활성 연결",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "nginx_connections_active",
          "legendFormat": "{{instance}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 3,
      "title": "초당 요청",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "rate(nginx_http_requests_total[2m])",
          "legendFormat": "{{instance}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 4,
      "title": "처리 중 연결",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "nginx_connections_writing",
          "legendFormat": "{{instance}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 5,
      "title": "대기 연결",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "nginx_connections_waiting",
          "legendFormat": "{{instance}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 0
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 10,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 6,
      "title": "수락한 연결 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "rate(nginx_connections_accepted[2m])",
          "legendFormat": "{{instance}}",
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "cps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 17,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 100,
      "title": "관련 로그 · Loki",
      "type": "logs",
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "{job=\"nginx\"}"
        }
      ],
      "options": {
        "showTime": true,
        "showLabels": false,
        "wrapLogMessage": false,
        "sortOrder": "Descending",
        "enableLogDetails": true
      },
      "gridPos": {
        "x": 0,
        "y": 24,
        "w": 24,
        "h": 9
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "tags": [
    "spacecube",
    "lab"
  ],
  "description": "109 최소 사양 시험. MariaDB primary·replica exporter가 수집 중이며 MongoDB는 제외했습니다. FastAPI 지표는 현재 수집 워커 기준. 빈 구간은 0을 뜻하지 않습니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-overview.json

```json
{
  "uid": "spacecube-overview",
  "title": "Spacecube / 전체 현황",
  "schemaVersion": 39,
  "version": 103,
  "refresh": "15s",
  "tags": [
    "spacecube"
  ],
  "panels": [
    {
      "id": 7001,
      "title": "기간 총 요청 · 정적 포함",
      "type": "stat",
      "description": "두 Nginx 전체 요청 증가 추정값. 정적·health·상태 요청 포함.",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(nginx_http_requests_total[$__range]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "blue",
                "value": null
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7002,
      "title": "전체 RPS · 정적 포함",
      "type": "stat",
      "description": "",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 6,
        "y": 0,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(nginx_http_requests_total[$__rate_interval]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "decimals": 1,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "blue",
                "value": null
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7003,
      "title": "앱 정상 (2대 중)",
      "type": "stat",
      "description": "HAProxy health 기준 정상 앱 서버 수",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 12,
        "y": 0,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(haproxy_server_status{proxy=\"apps\",state=\"UP\"})",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "orange",
                "value": 1
              },
              {
                "color": "green",
                "value": 2
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7004,
      "title": "수집 대상 정상 비율",
      "type": "stat",
      "description": "전체 19개 scrape 대상 응답 비율. DB 연결 성공률과는 다릅니다.",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 18,
        "y": 0,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100*sum(up)/count(up)",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "decimals": 0,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "orange",
                "value": 90
              },
              {
                "color": "green",
                "value": 100
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7005,
      "title": "replica 복제 지연",
      "type": "stat",
      "description": "",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "max(mysql_slave_status_seconds_behind_master{job=\"mariadb\"})",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "decimals": 0,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "orange",
                "value": 5
              },
              {
                "color": "red",
                "value": 30
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7006,
      "title": "예약 생성 · 워커 표본",
      "type": "stat",
      "description": "수집 워커 기준이며 다중 프로세스 합산이 미구성돼 과소/과대 집계될 수 있습니다. DB 실제 건수와 구분합니다.",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 6,
        "y": 3,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(reservation_total{job=\"api\",result=\"ok\"}[$__range]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "blue",
                "value": null
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7007,
      "title": "예약 충돌 · 워커 표본",
      "type": "stat",
      "description": "동일 칸 경합의 정상 409 차단. 수집 워커 기준이며 다중 프로세스 합산이 미구성돼 과소/과대 집계될 수 있습니다. DB 실제 건수와 구분합니다.",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(reservation_total{job=\"api\",result=\"conflict\"}[$__range]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "blue",
                "value": null
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 7008,
      "title": "API 응답 p95",
      "type": "stat",
      "description": "현재 수집 워커의 전체 API 지연. 조회 300ms 가이드이며 업무별 실험 p95와 구분합니다.",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "gridPos": {
        "x": 18,
        "y": 3,
        "w": 6,
        "h": 3
      },
      "targets": [
        {
          "refId": "A",
          "expr": "histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket{job=\"api\"}[$__rate_interval])))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "decimals": 2,
          "min": 0,
          "noValue": "수집 없음",
          "color": {
            "mode": "thresholds"
          },
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "orange",
                "value": 0.3
              },
              {
                "color": "red",
                "value": 1
              }
            ]
          }
        },
        "overrides": []
      },
      "options": {
        "textMode": "value",
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "center",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "titleSize": 11,
          "valueSize": 24
        }
      }
    },
    {
      "id": 5,
      "title": "서버별 CPU 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - avg by(server)(rate(node_cpu_seconds_total{job=\"nodes\",mode=\"idle\"}[$__rate_interval])))",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 6,
        "w": 12,
        "h": 7
      },
      "description": "node exporter 6대 지표입니다. MongoDB는 실험 SSH 표본에서 확인합니다."
    },
    {
      "id": 6,
      "title": "서버별 메모리 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - node_memory_MemAvailable_bytes{job=\"nodes\"}/node_memory_MemTotal_bytes{job=\"nodes\"})",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 6,
        "w": 12,
        "h": 7
      },
      "description": "node exporter 6대 지표입니다. MongoDB는 실험 SSH 표본에서 확인합니다."
    },
    {
      "id": 600,
      "title": "서비스·백엔드 상태 이력",
      "description": "1=정상, 0=비정상. Prometheus 수집 상태와 HAProxy의 앱 서버 헬스체크를 함께 봅니다.",
      "type": "state-timeline",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "max by(server,job)(up{job=~\"alloy|api|haproxy|loki|mariadb|nginx|nodes|prometheus\"})",
          "legendFormat": "{{server}} · {{job}}"
        },
        {
          "refId": "B",
          "expr": "haproxy_server_status{proxy=\"apps\",state=\"UP\"}",
          "legendFormat": "{{server}} · HAProxy backend"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "mappings": [
            {
              "type": "value",
              "options": {
                "0": {
                  "text": "DOWN / STOPPED",
                  "color": "red"
                },
                "1": {
                  "text": "UP / RUNNING",
                  "color": "green"
                }
              }
            }
          ]
        },
        "overrides": []
      },
      "options": {
        "showValue": "auto",
        "mergeValues": true,
        "rowHeight": 0.8,
        "tooltip": {
          "mode": "single"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 13,
        "w": 24,
        "h": 6
      }
    },
    {
      "id": 7,
      "title": "서버별 가용 메모리",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "node_memory_MemAvailable_bytes{job=\"nodes\"}",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 19,
        "w": 12,
        "h": 7
      },
      "description": "node exporter 6대 지표입니다. MongoDB는 실험 SSH 표본에서 확인합니다."
    },
    {
      "id": 8,
      "title": "루트 디스크 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1-node_filesystem_avail_bytes{job=\"nodes\",mountpoint=\"/\",fstype!=\"rootfs\"}/node_filesystem_size_bytes{job=\"nodes\",mountpoint=\"/\",fstype!=\"rootfs\"})",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1,
          "max": 100
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 19,
        "w": 12,
        "h": 7
      },
      "description": "node exporter 6대 지표입니다. MongoDB는 실험 SSH 표본에서 확인합니다."
    },
    {
      "id": 9,
      "title": "서버별 분산 RPS",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "rate(haproxy_server_loadbalanced_total{proxy=\"apps\"}[$__rate_interval])",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 26,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 10,
      "title": "Alloy 로그 전송 / 초",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(loki_write_sent_entries_total{job=\"alloy\"}[$__rate_interval]))",
          "legendFormat": "{{server}}",
          "instant": false,
          "interval": "15s"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ops",
          "min": 0,
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "decimals": 1
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 26,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 500,
      "title": "HTTP 응답 비율 · HAProxy 정문",
      "description": "선택 기간의 정문 전체 응답 비율입니다. 시간별 오류 추이는 FastAPI 대시보드에서 확인하세요.",
      "type": "piechart",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(code)(increase(haproxy_frontend_http_responses_total{proxy=\"web\"}[$__range])) > 0",
          "legendFormat": "{{code}}",
          "instant": true,
          "queryType": "instant"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "decimals": 0,
          "color": {
            "mode": "palette-classic"
          },
          "noValue": "수집 없음"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "2xx"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "green"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "200"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "green"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "201"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "blue"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "4xx"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "orange"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "401"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "orange"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "409"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "yellow"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "5xx"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "red"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "503"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "mode": "fixed",
                  "fixedColor": "red"
                }
              }
            ]
          }
        ]
      },
      "options": {
        "pieType": "donut",
        "displayLabels": [
          "name",
          "percent"
        ],
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "legend": {
          "displayMode": "table",
          "placement": "right",
          "values": [
            "value",
            "percent"
          ]
        },
        "tooltip": {
          "mode": "single",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 33,
        "w": 12,
        "h": 7
      }
    },
    {
      "datasource": {
        "type": "loki",
        "uid": "loki"
      },
      "description": "Nginx API 접근 로그의 200·201·401·409·503 등 개별 코드. health/metrics 제외. HAProxy가 앱 전달 전에 반환한 오류는 포함하지 않으므로 정문 차트와 함께 봅니다.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "decimals": 0,
          "noValue": "수집 없음",
          "unit": "short"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "2xx"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "green",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "200"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "green",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "201"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "blue",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "4xx"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "orange",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "401"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "orange",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "409"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "yellow",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "5xx"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "503"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "x": 12,
        "y": 33,
        "w": 12,
        "h": 7
      },
      "id": 501,
      "options": {
        "displayLabels": [
          "name",
          "percent"
        ],
        "legend": {
          "displayMode": "table",
          "placement": "right",
          "values": [
            "value",
            "percent"
          ]
        },
        "pieType": "donut",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "desc"
        }
      },
      "targets": [
        {
          "expr": "sum by(status)(count_over_time({job=\"nginx\",server=~\"api1|api2\"} | json | __error__=\"\" | path=~\"/api/.*\" | path!~\"/api/(health|metrics).*\" [$__range]))",
          "instant": true,
          "legendFormat": "{{status}}",
          "queryType": "instant",
          "refId": "A"
        }
      ],
      "title": "API 상태코드 · 선택 기간",
      "type": "piechart"
    },
    {
      "id": 20,
      "title": "API 5xx 비율",
      "description": "FastAPI 전체 응답 중 5xx 비율입니다.",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * sum(rate(http_requests_total{job=\"api\",status=~\"5..\"}[$__rate_interval])) / clamp_min(sum(rate(http_requests_total{job=\"api\"}[$__rate_interval])), 0.001)",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 0,
        "y": 40,
        "w": 12,
        "h": 2
      }
    },
    {
      "id": 23,
      "title": "이벤트 API 수락 · 선택 기간",
      "description": "HTTP 202로 수락된 요청 수이며 MongoDB 저장 건수는 아닙니다.",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(http_requests_total{job=\"api\",handler=\"/events\",status=\"202\"}[$__range]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 12,
        "y": 40,
        "w": 12,
        "h": 2
      }
    },
    {
      "id": 90,
      "type": "text",
      "title": "구성과 읽는 법",
      "options": {
        "mode": "markdown",
        "content": "**구성과 관측 범위**\n- 219망 VM 7대: 정문 .218 · API .214/.215 · mon .217 · MariaDB .212/.213 · MongoDB .216.\n- node exporter는 6대입니다. MongoDB는 전용 exporter 없이 API health 및 실험 SSH 표본으로 확인합니다. 수집 대상 정상 비율은 19개 scrape 대상의 응답 비율입니다.\n- api1 타이머: 이용 완료 매시 :05 · event_daily 매시 :20 · 크롤러 월요일 04:00.\n\n**지표를 읽는 법**\n- 총 요청·RPS는 두 Nginx 합계로 정적 파일·health·상태 요청을 포함합니다. 실험 요청 수와는 다릅니다.\n- 예약 생성·충돌·API 지연은 현재 수집 워커 통계입니다. 워커 합산이 미구성돼 기간 증가량이 과소/과대 집계될 수 있습니다. 실제 업무 건수는 DB/실험 기록으로 확인합니다.\n- API p95의 300ms는 조회 가이드입니다. 모의 결제 예약 생성의 500ms 기준은 Locust 기록에서 따로 확인합니다.\n- 생성기 파일럿 과거 이벤트 10,368건은 실시간 API 요청 카운터가 아닌 원천 events/event_daily에 있습니다."
      },
      "gridPos": {
        "x": 0,
        "y": 42,
        "w": 24,
        "h": 8
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "description": "219망 VM 7대: 앱·수집 상태, 트래픽, 예약 워커 표본, 복제 지연과 OS 자원.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-servers.json

```json
{
  "uid": "spacecube-servers",
  "title": "Spacecube / 서버·프록시",
  "schemaVersion": 39,
  "version": 103,
  "refresh": "15s",
  "tags": [
    "spacecube",
    "lab"
  ],
  "panels": [
    {
      "id": 1,
      "title": "정상 수집 대상 수",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(up)",
          "instant": true,
          "interval": "15s",
          "legendFormat": "{{server}} · {{instance}}"
        }
      ],
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 12,
        "h": 3
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "min": 0,
          "decimals": 0,
          "unit": "short"
        }
      }
    },
    {
      "id": 5,
      "title": "HAProxy 백엔드 상태",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "haproxy_server_status{proxy=\"apps\",state=\"UP\"}",
          "instant": true,
          "interval": "15s",
          "legendFormat": "{{server}} · {{instance}}"
        }
      ],
      "gridPos": {
        "x": 12,
        "y": 0,
        "w": 12,
        "h": 3
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "text": {
          "valueSize": 16,
          "titleSize": 11
        },
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        }
      },
      "fieldConfig": {
        "defaults": {
          "noValue": "수집 없음",
          "min": 0,
          "decimals": 0,
          "unit": "short"
        }
      }
    },
    {
      "id": 2,
      "title": "CPU 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - avg by(server)(rate(node_cpu_seconds_total{mode=\"idle\"}[2m])))",
          "interval": "15s",
          "legendFormat": "{{server}} · {{instance}}"
        }
      ],
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 12,
        "h": 7
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "min": 0,
          "decimals": 1,
          "unit": "percent",
          "max": 100
        }
      }
    },
    {
      "id": 3,
      "title": "메모리 사용률",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "100 * (1 - node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)",
          "interval": "15s",
          "legendFormat": "{{server}} · {{instance}}"
        }
      ],
      "gridPos": {
        "x": 12,
        "y": 3,
        "w": 12,
        "h": 7
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "min": 0,
          "decimals": 1,
          "unit": "percent",
          "max": 100
        }
      }
    },
    {
      "id": 4,
      "title": "루트 디스크 여유",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "node_filesystem_avail_bytes{mountpoint=\"/\"}",
          "interval": "15s",
          "legendFormat": "{{server}} · {{instance}}"
        }
      ],
      "gridPos": {
        "x": 0,
        "y": 10,
        "w": 12,
        "h": 7
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "min": 0,
          "decimals": 1,
          "unit": "bytes"
        }
      }
    },
    {
      "id": 6,
      "title": "Nginx 접속",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "nginx_connections_active",
          "interval": "15s",
          "legendFormat": "{{server}} · {{instance}}"
        }
      ],
      "gridPos": {
        "x": 12,
        "y": 10,
        "w": 12,
        "h": 7
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "drawStyle": "line",
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never",
            "spanNulls": false,
            "axisBorderShow": false
          },
          "noValue": "수집 없음",
          "min": 0,
          "decimals": 0,
          "unit": "short"
        }
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "description": "109 최소 사양 시험. MariaDB primary·replica exporter가 수집 중이며 MongoDB는 제외했습니다. FastAPI 지표는 현재 수집 워커 기준. 빈 구간은 0을 뜻하지 않습니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

## dashboard-storage.json

```json
{
  "uid": "spacecube-storage",
  "title": "Spacecube / 이벤트·저장소 요약",
  "schemaVersion": 39,
  "version": 103,
  "refresh": "15s",
  "tags": [
    "spacecube",
    "lab"
  ],
  "panels": [
    {
      "id": 10,
      "title": "MariaDB exporter 정상 대수",
      "description": "",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(mysql_up{job=\"mariadb\"})",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 3
      }
    },
    {
      "id": 11,
      "title": "spacecube 데이터 + 인덱스",
      "description": "테이블 데이터·인덱스 크기 합계입니다. DB 서버 루트 디스크 사용량과 다릅니다.",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server,role)(mysql_info_schema_table_size{job=\"mariadb\",schema=\"spacecube\",component=~\"data_length|index_length\"})",
          "legendFormat": "{{server}}",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "bytes",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 6,
        "y": 0,
        "w": 6,
        "h": 3
      }
    },
    {
      "id": 12,
      "title": "Replica 복제 지연",
      "description": "",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "mysql_slave_status_seconds_behind_master{job=\"mariadb\"}",
          "legendFormat": "{{server}}",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 12,
        "y": 0,
        "w": 6,
        "h": 3
      }
    },
    {
      "id": 14,
      "title": "이벤트 API 수락 수 · 선택 기간",
      "description": "HTTP 202 응답 수이며 MongoDB 저장 건수는 아닙니다.",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(http_requests_total{job=\"api\",handler=\"/events\",status=\"202\"}[$__range]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 18,
        "y": 0,
        "w": 6,
        "h": 3
      }
    },
    {
      "id": 15,
      "title": "읽기 대체 횟수 · 선택 기간",
      "description": "",
      "type": "stat",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(increase(db_read_fallback_total{job=\"api\"}[$__range]))",
          "instant": true
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "value_and_name",
        "justifyMode": "auto",
        "orientation": "horizontal",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "values": false
        },
        "text": {
          "valueSize": 16,
          "titleSize": 11
        }
      },
      "gridPos": {
        "x": 0,
        "y": 3,
        "w": 6,
        "h": 3
      }
    },
    {
      "id": 20,
      "title": "이벤트 API 수락률 · HTTP 202",
      "description": "",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(http_requests_total{job=\"api\",handler=\"/events\",status=\"202\"}[$__rate_interval]))",
          "legendFormat": "{{server}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "custom": {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 6,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 21,
      "title": "Replica 읽기 대체 증가율",
      "description": "",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(db_read_fallback_total{job=\"api\"}[$__rate_interval]))",
          "legendFormat": "{{server}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ops",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "custom": {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 6,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 22,
      "title": "MongoDB 전달 실패 누계",
      "description": "MongoDB는 현재 온라인입니다. 응답 뒤 백그라운드 저장 실패 누계이며 현재 문서 수나 저장 완료 건수가 아닙니다.",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(mongo_event_write_failures_total{job=\"api\"})",
          "legendFormat": "{{server}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "custom": {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 13,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 23,
      "title": "Alloy → Loki 전송률",
      "description": "",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum by(server)(rate(loki_write_sent_entries_total{job=\"alloy\"}[$__rate_interval]))",
          "legendFormat": "{{server}}"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ops",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "custom": {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 12,
        "y": 13,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 24,
      "title": "Loki 로그 수신률",
      "description": "",
      "type": "timeseries",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [
        {
          "refId": "A",
          "expr": "sum(rate(loki_distributor_lines_received_total[$__rate_interval]))"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "ops",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음",
          "custom": {
            "drawStyle": "line",
            "lineWidth": 1,
            "fillOpacity": 6,
            "showPoints": "never"
          }
        },
        "overrides": []
      },
      "options": {
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "calcs": []
        },
        "tooltip": {
          "mode": "multi",
          "sort": "desc"
        }
      },
      "gridPos": {
        "x": 0,
        "y": 20,
        "w": 12,
        "h": 7
      }
    },
    {
      "id": 900,
      "title": "저장·집계 범위",
      "description": "",
      "type": "text",
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "targets": [],
      "fieldConfig": {
        "defaults": {
          "unit": "short",
          "min": 0,
          "decimals": 1,
          "noValue": "수집 없음"
        },
        "overrides": []
      },
      "options": {
        "mode": "markdown",
        "content": "**저장·집계 범위**\nMariaDB 10.11.14 primary·replica exporter는 정상 수집 중입니다. MongoDB 8.0.34는 온라인이며 전용 exporter는 미설치입니다.\n\n이벤트 API 202는 batch 접수 수로, 이벤트 수나 MongoDB 저장 완료 건수가 아닙니다. 예약·취소의 서버 이벤트는 /events 요청 없이도 생성됩니다.\n\n원천 space_rental_analytics.events는 api1이 매시 :20에 event_daily로 집계합니다. 생성기 파일럿(100명·30일, 10-08~11-06)의 10,368건과 이후 부하 시험 이벤트를 구분합니다. Mongo user.user_id는 문자열입니다. 업무별 정확한 건수는 실험 SQL/Mongo 집계 문서를 따릅니다."
      },
      "gridPos": {
        "x": 0,
        "y": 27,
        "w": 24,
        "h": 8
      }
    }
  ],
  "time": {
    "from": "now-30m",
    "to": "now"
  },
  "description": "이벤트 API 수락, replica 읽기 대체, 로그 전달과 DB 용량 요약을 봅니다. DB 세부 패널은 MariaDB 대시보드에서 확인합니다.",
  "links": [
    {
      "title": "전체 현황",
      "type": "link",
      "url": "/d/spacecube-overview",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "서버",
      "type": "link",
      "url": "/d/spacecube-servers",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "HAProxy",
      "type": "link",
      "url": "/d/spacecube-haproxy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Nginx",
      "type": "link",
      "url": "/d/spacecube-nginx",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "FastAPI",
      "type": "link",
      "url": "/d/spacecube-api",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "MariaDB",
      "type": "link",
      "url": "/d/spacecube-mariadb",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "DB 연결·대기",
      "type": "link",
      "url": "/d/spacecube-db-connections",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "이벤트·저장소",
      "type": "link",
      "url": "/d/spacecube-storage",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "로그 탐색",
      "type": "link",
      "url": "/d/spacecube-logs",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Alloy",
      "type": "link",
      "url": "/d/spacecube-alloy",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    },
    {
      "title": "Loki",
      "type": "link",
      "url": "/d/spacecube-loki",
      "keepTime": true,
      "includeVars": true,
      "targetBlank": false
    }
  ],
  "timepicker": {
    "refresh_intervals": [
      "15s",
      "30s",
      "1m",
      "5m"
    ]
  },
  "timezone": "Asia/Seoul"
}

```

