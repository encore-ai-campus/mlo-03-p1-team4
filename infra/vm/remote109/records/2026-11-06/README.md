# 2026-11-06 선별 실험 기록

- limit100-summary.csv: Uvicorn 제한 100, 실제 400명 시험의 실패 요약.
- limit200-summary.csv: 제한 200으로 올린 50/100/200/400명 재시험.
- limit200-resources.csv: VM별 CPU·메모리 평균/관측 최고·epoch 시각. CPU는 1분 rate를 15초 간격으로 수집했으므로 순간 피크가 아니다.
- *-evidence.txt: 관련 시각의 Uvicorn 동시성 경고와 HAProxy DOWN/UP만 선별했다.

단계 간 시점과 램프업 조건이 다르다. 원본 logs 경로는 실행 PC 로컬 위치이며 Git에 포함되지 않는다. 실제 800명 도달 시험·DB 쓰기·정식 A7 판정은 하지 않았다.
