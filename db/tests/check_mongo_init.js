// mongo_init.js 실행 뒤 검증 (11-04). 실행: mongosh 연결주소 docs/db/mongo_init.js db/tests/check_mongo_init.js
db = db.getSiblingDB('spacecube');
let fails = 0;
function t(name, fn, wantErr) {
  try { fn(); if (wantErr) { fails++; print('FAIL ' + name + ': 막혀야 하는데 들어감'); } else print('OK   ' + name); }
  catch (e) { if (wantErr && (e.code === wantErr || String(e).includes(String(wantErr)))) print('OK   ' + name + ' (' + e.code + ')'); else { fails++; print('FAIL ' + name + ': ' + e.code + ' ' + e.message); } }
}
const ok = { event_id: 'e-1', ts: new Date(), session_id: 's-1', user_id: NumberLong('1'), event_type: 'select_slot', venue_id: 3, category: 'studyroom', payload: { date: '2026-11-10', hour: 14 }, is_synthetic: false, server: 'api-1' };
t('정상 이벤트', () => db.user_events.insertOne(ok));
t('같은 event_id 다시', () => db.user_events.insertOne(Object.assign({}, ok)), 11000);
t('모르는 event_type', () => db.user_events.insertOne(Object.assign({}, ok, { event_id: 'e-2', event_type: 'abandon' })), 121);
t('server 없음', () => { const d = Object.assign({}, ok, { event_id: 'e-3' }); delete d.server; db.user_events.insertOne(d); }, 121);
t('ts가 문자열', () => db.user_events.insertOne(Object.assign({}, ok, { event_id: 'e-4', ts: '2026-11-04' })), 121);
t('비회원(user_id null)', () => db.user_events.insertOne(Object.assign({}, ok, { event_id: 'e-5', user_id: null })));
t('서버 이벤트 reserve_ok', () => db.user_events.insertOne(Object.assign({}, ok, { event_id: 'e-6', event_type: 'reserve_ok' })));
t('하루 집계 upsert', () => { db.event_daily.updateOne({ date: '2026-11-04', event_type: 'select_slot', venue_id: 3, is_synthetic: false }, { $inc: { count: 1 } }, { upsert: true }); });
t('하루 집계 같은 키 두 번 insert', () => db.event_daily.insertOne({ date: '2026-11-04', event_type: 'select_slot', venue_id: 3, is_synthetic: false, count: 1 }), 11000);
const raw = { source_site: 'spacecloud', source_id: '53074', crawled_at: new Date(), status: 'ok', space_types: ['스터디룸'], extracted: { capacity_max: 6 }, mapped: null };
t('크롤링 원본', () => db.crawl_raw.insertOne(raw));
t('크롤링 같은 사이트·id', () => db.crawl_raw.insertOne(Object.assign({}, raw)), 11000);
t('크롤링 status 이상값', () => db.crawl_raw.insertOne(Object.assign({}, raw, { source_id: '1', status: 'done' })), 121);
const ttl = db.user_events.getIndexes().find(i => i.expireAfterSeconds !== undefined);
if (ttl && ttl.expireAfterSeconds === 31536000 && ttl.key.ts === 1) print('OK   TTL 365일 (ts)'); else { fails++; print('FAIL TTL ' + JSON.stringify(ttl)); }
print('인덱스 user_events ' + db.user_events.getIndexes().length + ' / event_daily ' + db.event_daily.getIndexes().length + ' / crawl_raw ' + db.crawl_raw.getIndexes().length);
print('실패 ' + fails);
