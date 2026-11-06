import { categories, facilities } from './catalog';
import { ApiError, reportApiError } from '../client';
import { addDays, todayISO } from '@/utils/date';
export const stamp = (at = Date.now()) => new Date(at + 9 * 3600000).toISOString().replace('Z', '+09:00');
export function seoulHour() {
  return Number(new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Seoul', hour: '2-digit', hourCycle: 'h23'
  }).format(new Date()));
}
export const VENUES = Array.from({
  length: 10
}, (_, i) => {
  const category = categories[i % 5];
  return {
    venue_id: i + 1, name: `${[
      '관악구', '성동구', '마포구', '마포구', '마포구', '강남구', '중구', '종로구', '서대문구', '성남시'
    ][i]} ${category.name} ${i + 1}호`, category, region: {
      sido: i === 9 ? '경기' : '서울', sigungu: [
        '관악구', '성동구', '마포구', '마포구', '마포구', '강남구', '중구', '종로구', '서대문구', '성남시'
      ][i]
    }, capacity_max: [
      6, 10, 25, 20, 15, 1, 8, 20, 6, 10
    ][i], price_per_hour: [
      10000, 25000, 30000, 20000, 35000, 3000, 22000, 28000, 6000, 15000
    ][i], open_hour: 9, close_hour: 23, min_hours: i % 5 === 1 || i % 5 === 4 ? 2 : 1, rating_avg: 4.5 + (i % 5) / 10, review_count: 10 + i, image: `art:${[
      'group', 'studio', 'cafe', 'seminar', 'partyroom'
    ][i % 5]}-${i > 4 ? 1 : 0}`, is_new: i > 5, registered_on: addDays(todayISO(), i > 5 ? -3 : -30), facilities: [
      1, 2, 3, 7
    ].map(id => facilities.find(f => f.facility_id === id)), description: '모임과 작업에 편안하게 이용할 수 있는 독립 공간입니다.', notice: '이용 후 물품을 제자리에 정리해 주세요.'
  };
});
export const venueById = id => VENUES.find(v => v.venue_id === Number(id));
export const users = [{
    user_id: 1, email: 'study@example.com', name: '김스터디', phone: '010-1234-5678', birth: '990315', gender_digit: '1', marketing_agreed: false, deleted: false, password: null
  }];
export const tokens = new Map();
export function fail(code, status, message, detail = null) {
  throw reportApiError(new ApiError({
    code, status, message, detail
  }));
}
export function currentUser(token) {
  const record = tokens.get(token);
  if (!record)
    fail('UNAUTHORIZED', 401, '로그인이 필요해요.');
  if (Date.now() >= record.expires)
    fail('TOKEN_EXPIRED', 401, '로그인 시간이 끝났어요. 다시 로그인해 주세요.');
  const user = users.find(u => u.user_id === record.user_id && !u.deleted);
  if (!user)
    fail('UNAUTHORIZED', 401, '로그인이 필요해요.');
  return user;
}
export function validateDate(date) {
  const min_date = addDays(todayISO(), -365), max_date = addDays(todayISO(), 365);
  const parsed = new Date(`${date}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date ?? '') || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date || date < min_date || date > max_date)
    fail('OUT_OF_RANGE', 400, '예약할 수 없는 날짜나 시간이에요.', {
      reason: 'date', min_date, max_date
    });
}
export function pageOf(items, { page = 1, size = 10 } = {}) {
  page = Number(page);
  size = Number(size);
  if (!Number.isInteger(page) || page < 1 || !Number.isInteger(size) || size < 1 || size > 50)
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.');
  return {
    items: items.slice((page - 1) * size, page * size), page, size, total: items.length
  };
}
export const reservations = [];
let nextId = 1006;
export const newReservationId = () => nextId++;
for (const [id, venue_id, offset, status] of [
  [
    1001, 1, 1, 'confirmed'
  ], [
    1002, 4, 3, 'confirmed'
  ], [
    1003, 2, -2, 'completed'
  ], [
    1004, 1, -11, 'completed'
  ], [
    1005, 5, -13, 'cancelled'
  ]
])
  reservations.push({
    reservation_id: id, user_id: 1, venue_id, date: addDays(todayISO(), offset), start_hour: 13, end_hour: 15, headcount: 2, total_price: venueById(venue_id).price_per_hour * 2, status, created_at: stamp(Date.now() - (id === 1003 ? 864e5 : 12 * 864e5)), payment: {
      method: 'card', status: status === 'cancelled' ? 'refunded' : 'paid', paid_at: stamp(), refunded_at: status === 'cancelled' ? stamp() : null
    }
  });
export const reviews = Array.from({
  length: 8
}, (_, i) => ({
  review_id: i + 1, user_id: i === 0 ? 1 : 90 + i, venue_id: i % 5 + 1, reservation_id: i === 0 ? 1004 : 900 + i, rating: i % 3 === 0 ? 4 : 5, content: '조용하고 편안해서 모임에 집중하기 좋았어요.', author: i === 0 ? '김**' : '이**', created_at: stamp(Date.now() - i * 864e5)
}));
export const externalSlots = new Set();
export function isTaken(venue_id, date, hour) {
  return externalSlots.has(`${venue_id}|${date}|${hour}`) || reservations.some(r => r.venue_id === Number(venue_id) && r.date === date && r.status !== 'cancelled' && hour >= r.start_hour && hour < r.end_hour);
}
export function slotsFor(id, date) {
  const v = venueById(id);
  return Array.from({
    length: v.close_hour - v.open_hour
  }, (_, i) => {
    const hour = v.open_hour + i;
    return {
      hour, taken: isTaken(id, date, hour), past: date < todayISO() || (date === todayISO() && hour <= seoulHour())
    };
  });
}
export function freeRun(slots) {
  let best = 0, run = 0;
  for (const s of slots) {
    run = s.taken ? 0 : run + 1;
    best = Math.max(best, run);
  }
  return best;
}
export function venueRequired(id) {
  const v = venueById(id);
  if (!v)
    fail('VENUE_NOT_FOUND', 404, '공간을 찾을 수 없어요.');
  return v;
}
export function venueItem(v, date = todayISO()) {
  const { description: _d, notice: _n, registered_on: _r, ...base } = v;
  return {
    ...base, facilities: v.facilities.map(f => f.name), slots: slotsFor(v.venue_id, date)
  };
}
export function reservationItem(r) {
  const v = venueById(r.venue_id);
  if (r.status === 'confirmed' && (r.date < todayISO() || (r.date === todayISO() && r.end_hour <= seoulHour())))
    r.status = 'completed';
  const { user_id: _u, ...base } = r;
  return {
    ...base, venue: {
      venue_id: v.venue_id, name: v.name, category: v.category, region: v.region, image: v.image
    }, can_cancel: r.status === 'confirmed' && (r.date > todayISO() || (r.date === todayISO() && r.start_hour > seoulHour())), review_id: reviews.find(x => x.reservation_id === r.reservation_id)?.review_id ?? null // 지운 후기도 포함(#45): 예약당 한 번만 쓸 수 있다
  };
}
