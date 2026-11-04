# AGENTS.md — db

루트 `AGENTS.md`에 더해 이 폴더에서 지킨다.

- 표 정의의 기준은 `docs/산출물_04_DB명세서.md`와 `migrations/*.sql`이다(11-04 실행 검증 뒤 `0001_init.sql`로 옮김, 표 12개 + 뷰). MongoDB는 `docs/db/mongo_init.js`(컬렉션 3개, 검증 끝). 마이그레이션을 바꾸면 `tests/check_ddl.py`를 다시 돌린다.
- `docs/지난설계/공간대여_02_DB정규화.md`(16개 표, rooms·posts·user_events 표)는 지난 설계다. 거기서 표를 가져오지 않는다.
- 이미 누군가의 DB에 적용된 마이그레이션 파일은 고치지 않는다. 바꿀 것은 새 번호 파일로 만든다(`0002_…`).
- 표·컬럼 이름을 바꾸거나 지우는 변경은 FastAPI A·B 코드를 깨뜨린다. 하기 전에 사람에게 묻는다.
- 일부러 정규화를 어긴 곳(`reservation_slots`의 `venue_id`·`slot_date`와 복합 외래키, `reservations.total_price`)은 명세 5-5절의 이유가 있으니 '정리'하지 않는다.
- 크롤링 공간은 B의 `POST /internal/venues`로만 넣는다(`venues (source_site, source_id)` upsert). DB에 바로 넣는 로더를 따로 만들지 않는다. 유형 매핑은 `seed/category_map.csv` 한 곳만 쓴다.
- 크롤링 원본 추출값은 MongoDB `crawl_raw`에 둔다. 업체 실명·사진·후기·연락처·상세 주소·원본 HTML은 어디에도 저장하지 않는다.
- 가상 데이터는 모든 행에 `is_synthetic = true`. 가상 예약도 `reservation_slots`를 거쳐 넣어 중복이 생기지 않게 한다.
- `DROP`·`TRUNCATE`·대량 `DELETE`는 `spacecube_test` 스키마에서만.
- 계정 비밀번호는 `.env`에만. SQL·JS 파일에는 계정 이름과 권한만 적는다.

## 명령

로컬 MariaDB 11.4·MongoDB 7은 `infra/local`의 docker compose로 띄운다(11-04). Docker Desktop을 켜는 것은 사람이 한다(에이전트는 사람이 허락했을 때만). 첫 실행 때 `0001_init` → `seed.sql` → `mongo_init.js`가 자동으로 들어간다.

```bash
docker compose -f infra/local/docker-compose.yml up -d
```

seed를 고쳤으면 `python db/loaders/load_seed.py --check`로 `seed.sql`을 다시 만든다.

제약 검증: `tests/README.md`의 항목을 `spacecube_test`에서 돌리고, 기대한 오류가 나는지 결과를 보고한다.
