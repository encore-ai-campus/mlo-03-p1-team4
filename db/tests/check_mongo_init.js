// mongo_init.js 실행 뒤 검증 (11-06 F-60 새 구조). 실행: mongosh 연결주소 docs/db/mongo_init.js db/tests/check_mongo_init.js
// 기준: docs/db/events_event_daily_컬렉션_속성정리_v1.md, #60 결정(서버 결과 3종만 화면 문맥 null 허용)
// 운영 이름(space_rental_analytics·crawl)으로 초기화한 일회용 DB(CI·로컬 compose)에서만 돌린다.
const analytics = db.getSiblingDB('space_rental_analytics');
const crawl = db.getSiblingDB('crawl');
let fails = 0;
function t(name, fn, wantErr) {
  try { fn(); if (wantErr) { fails++; print('FAIL ' + name + ': 막혀야 하는데 들어감'); } else print('OK   ' + name); }
  catch (e) { if (wantErr && (e.code === wantErr || String(e).includes(String(wantErr)))) print('OK   ' + name + ' (' + e.code + ')'); else { fails++; print('FAIL ' + name + ': ' + e.code + ' ' + e.message); } }
}
// mongosh의 숫자는 double이므로 int 칸은 NumberInt로 넣는다.
const product = {
  product_id: '1',
  product_name: '서대문구 쿠킹 파티룸 82345',
  price: { currency: 'KRW', displayed_amount_minor: NumberInt(30000), displayed_text: '30,000원', billing_unit: 'hour' },
  rental_conditions: { start_at: null, end_at: null, timezone: 'Asia/Seoul', guest_count: null, option_ids: [] },
};
const page = { page_view_id: 'p-1', page_type: 'product_detail', url: 'http://gw/venues/1', path: '/venues/1', title: '공간 상세' };
const fe = () => ({
  event_id: 'e-1', schema_version: NumberInt(1), event_name: 'product_view', occurred_at: new Date(), received_at: new Date(),
  user: { user_id: null, anonymous_id: 'a-1', session_id: 's-1', session_sequence: NumberInt(1) },
  site: { site_id: 'main', hostname: 'gw', platform: 'desktop_web' },
  acquisition: { landing_url: 'http://gw/', referrer_url: null, utm_source: null, utm_medium: null, utm_campaign: null },
  page,
  navigation: { from: null, to: { page_view_id: 'p-1', site_id: 'main', url: page.url, path: page.path }, navigation_type: 'direct' },
  products: [product], properties: {}, is_synthetic: false, server: 'api1',
});
const ins = (doc) => analytics.events.insertOne(doc);
const withId = (id, patch) => { const d = fe(); d.event_id = id; return Object.assign(d, patch); };

t('정상 FE 이벤트(product_view)', () => ins(fe()));
t('같은 event_id 다시', () => ins(fe()), 11000);
t('모르는 event_name', () => ins(withId('e-2', { event_name: 'abandon' })), 121);
t('received_at 없음', () => { const d = withId('e-3'); delete d.received_at; ins(d); }, 121);
t('occurred_at이 문자열', () => ins(withId('e-4', { occurred_at: '2026-11-06' })), 121);
t('schema_version이 double', () => ins(withId('e-5', { schema_version: 1.5 })), 121);
t('정의 안 된 최상위 칸', () => ins(withId('e-6', { payload: {} })), 121);
t('user_id가 숫자', () => ins(withId('e-7', { user: { user_id: 1, anonymous_id: 'a-1', session_id: 's-1', session_sequence: NumberInt(1) } })), 121);
t('로그인 회원(user_id 문자열)', () => ins(withId('e-8', { user: { user_id: '1', anonymous_id: 'a-1', session_id: 's-1', session_sequence: NumberInt(2) } })));
t('FE 이벤트의 page null', () => ins(withId('e-9', { page: null })), 121);
t('FE 이벤트의 anonymous_id null', () => ins(withId('e-10', { user: { user_id: null, anonymous_id: null, session_id: 's-1', session_sequence: NumberInt(3) } })), 121);
t('상품 필요한 이벤트의 빈 products', () => ins(withId('e-11', { products: [] })), 121);
t('page_view는 빈 products 허용', () => ins(withId('e-12', { event_name: 'page_view', products: [] })));
t('product에 이름·가격 없음(product_id만)', () => ins(withId('e-13', { products: [{ product_id: '1' }] })), 121);
const server = (id, patch) => withId(id, Object.assign({
  event_name: 'reservation_complete', site: null, acquisition: null, page: null, navigation: null,
  user: { user_id: '1', anonymous_id: null, session_id: 's-1', session_sequence: null },
  properties: { reservation_id: 7 },
}, patch));
t('서버 결과 이벤트는 화면 문맥 null 허용', () => ins(server('e-14')));
t('서버 결과 이벤트도 빈 products는 거부', () => ins(server('e-15', { products: [] })), 121);

const opts = analytics.getCollectionInfos({ name: 'events' })[0]?.options ?? {};
if (opts.validationLevel === 'strict' && opts.validationAction === 'error') print('OK   events validator strict/error'); else { fails++; print('FAIL validator 설정 ' + JSON.stringify(opts)); }
const ttl = analytics.events.getIndexes().find(i => i.expireAfterSeconds !== undefined);
if (ttl && ttl.expireAfterSeconds === 31536000 && ttl.key.received_at === 1) print('OK   TTL 365일 (received_at)'); else { fails++; print('FAIL TTL ' + JSON.stringify(ttl)); }
const uq = analytics.events.getIndexes().find(i => i.name === 'uq_event_id');
if (uq && uq.unique) print('OK   uq_event_id unique'); else { fails++; print('FAIL uq_event_id ' + JSON.stringify(uq)); }

const day = { date: '2026-11-06', event_type: 'product_view', venue_id: '1', is_synthetic: false };
t('하루 집계 upsert', () => analytics.event_daily.updateOne(day, { $inc: { count: 1 } }, { upsert: true }));
t('하루 집계 같은 키 두 번 insert', () => analytics.event_daily.insertOne(Object.assign({ count: 1 }, day)), 11000);

const raw = (patch) => Object.assign({ source_site: 'spacecloud', source_id: '53074', crawled_at: new Date(), status: 'ok', space_types: ['파티룸'], extracted: { capacity_max: 12 }, mapped: null }, patch);
t('크롤링 원본', () => crawl.crawl_raw.insertOne(raw()));
t('크롤링 같은 사이트·id', () => crawl.crawl_raw.insertOne(raw()), 11000);
t('크롤링 status 이상값', () => crawl.crawl_raw.insertOne(raw({ source_id: '1', status: 'done' })), 121);

print('인덱스 events ' + analytics.events.getIndexes().length + ' / event_daily ' + analytics.event_daily.getIndexes().length + ' / crawl_raw ' + crawl.crawl_raw.getIndexes().length);
print('실패 ' + fails);
