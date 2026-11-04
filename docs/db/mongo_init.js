// 공간큐브 MongoDB 초기화 수정안 (2026-11-03)
// 기준: docs/산출물_04_DB명세서.md · MongoDB 7.0
// 실행: mongosh "mongodb://<관리자>@<호스트>:27017/admin" mongo_init.js
// 상태: 11-04 로컬 MongoDB 7.0.45(Docker)에서 실행 검증(시험 13건 통과: db/tests/check_mongo_init.js). 다시 돌려도 오류 없음.
// 비밀번호는 이 파일에 적지 않는다(배포 때 passwordPrompt()로 넣음).

db = db.getSiblingDB('spacecube');  // mongosh 전역 db를 바꿈 (const로 다시 선언하면 오류)

// ── 1. user_events: 사용자 행동 이벤트 (원천 데이터) ──
db.createCollection('user_events', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['event_id', 'ts', 'session_id', 'event_type', 'is_synthetic', 'server'],
      properties: {
        event_id:     { bsonType: 'string', description: 'UUID v4. 같은 이벤트 두 번 저장 방지' },
        ts:           { bsonType: 'date',   description: '서버가 받은 실제 시각(UTC)' },
        client_ts:    { bsonType: ['date', 'null'], description: '브라우저 시각(참고용)' },
        session_id:   { bsonType: 'string' },
        user_id:      { bsonType: ['long', 'int', 'null'] },
        event_type:   { enum: ['search', 'view_venue', 'view_dates', 'select_slot', 'reserve_try',
                               'reserve_ok', 'reserve_conflict', 'reserve_cancel', 'reserve_cancel_ok',
                               'review_create', 'login', 'signup'] },
        venue_id:     { bsonType: ['long', 'int', 'null'] },
        category:     { bsonType: ['string', 'null'] },
        payload:      { bsonType: 'object', description: '종류별 값. 개인정보 넣지 않음' },
        is_synthetic: { bsonType: 'bool' },
        server:       { bsonType: 'string', description: 'api-1 / api-2 / generator / locust' }
      }
    }
  },
  validationLevel: 'moderate'
});
db.user_events.createIndex({ event_id: 1 }, { unique: true });
db.user_events.createIndex({ ts: 1 }, { expireAfterSeconds: 60 * 60 * 24 * 365 });  // 1년 보관
db.user_events.createIndex({ event_type: 1, ts: 1 });
db.user_events.createIndex({ user_id: 1, ts: -1 });
db.user_events.createIndex({ venue_id: 1, ts: -1 });
db.user_events.createIndex({ session_id: 1, ts: 1 });

// ── 2. event_daily: 하루 집계 (Grafana·발표용, 영구 보관) ──
db.createCollection('event_daily');
db.event_daily.createIndex({ date: 1, event_type: 1, venue_id: 1, is_synthetic: 1 }, { unique: true });

// ── 3. crawl_raw: 크롤링에서 추출한 속성 (원본 HTML 아님) ──
db.createCollection('crawl_raw', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['source_site', 'source_id', 'crawled_at', 'status'],
      properties: {
        source_site: { bsonType: 'string' },
        source_id:   { bsonType: 'string' },
        job_id:      { bsonType: ['long', 'int'] },
        crawled_at:  { bsonType: 'date' },
        status:      { enum: ['ok', 'no_detail', 'excluded', 'registered'] },
        space_types: { bsonType: 'array' },
        extracted:   { bsonType: 'object', description: '인원·가격·최소시간·영업시간·시설·시군구. 이름·사진·후기·연락처 없음' },
        mapped:      { bsonType: ['object', 'null'], description: '전처리 결과(우리 유형·지역·가격). 등록 후보' },
        exclude_reason: { bsonType: ['string', 'null'] },
        venue_id:    { bsonType: ['long', 'int', 'null'], description: '등록됐으면 MariaDB venues.venue_id' }
      }
    }
  }
});
db.crawl_raw.createIndex({ source_site: 1, source_id: 1 }, { unique: true });
db.crawl_raw.createIndex({ status: 1, 'mapped.category': 1 });   // 유형별 후보 꺼내기

// ── 계정 ──
// db.createUser({ user: 'app',     pwd: passwordPrompt(), roles: [{ role: 'readWrite', db: 'spacecube' }] });
// db.createUser({ user: 'analyst', pwd: passwordPrompt(), roles: [{ role: 'read',      db: 'spacecube' }] });
// db.createUser({ user: 'exporter', pwd: passwordPrompt(), roles: [{ role: 'clusterMonitor', db: 'admin' }, { role: 'read', db: 'local' }] });
