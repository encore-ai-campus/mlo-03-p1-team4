import { USE_MOCK, mockDelay, request, query } from './client';
import { currentUser, reservations, newReservationId, reservationItem, venueRequired, validateDate, fail, pageOf, stamp, externalSlots } from './mock/db';
import { todayISO } from '@/utils/date';
export async function createReservation(body, token) {
  if (!USE_MOCK)
    return request('/reservations', {
      method: 'POST', body, token
    });
  await mockDelay(null);
  const user = currentUser(token), v = venueRequired(body.venue_id);
  const { date, start_hour, hours, headcount, method } = body;
  validateDate(date);
  if (!Number.isInteger(hours) || hours < v.min_hours || hours > 4 || !Number.isInteger(start_hour) || start_hour < v.open_hour || start_hour + hours > v.close_hour)
    fail('OUT_OF_RANGE', 400, '예약할 수 없는 날짜나 시간이에요.', {
      reason: hours < v.min_hours ? 'min_hours' : hours > 4 ? 'max_hours' : 'hours', min_hours: v.min_hours
    });
  if (!Number.isInteger(headcount) || headcount < 1)
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.', {
      fields: [{
          field: 'headcount', reason: '1명 이상 입력해 주세요.'
        }]
    });
  if (headcount > v.capacity_max)
    fail('TOO_MANY_PEOPLE', 400, `이 공간은 최대 ${v.capacity_max}명까지예요.`, {
      capacity_max: v.capacity_max
    });
  if (!['transfer', 'card', 'phone'].includes(method))
    fail('INVALID_METHOD', 400, '결제 수단을 다시 골라 주세요.');
  const same = reservations.find(r => r.user_id === user.user_id && r.status !== 'cancelled' && r.venue_id === v.venue_id && r.date === date && r.start_hour === start_hour && r.end_hour === start_hour + hours && Date.now() - Date.parse(r.created_at) <= 600000);
  if (same)
    return reservationItem(same);
  const range = Array.from({
    length: hours
  }, (_, i) => start_hour + i);
  if (v.venue_id === 1 && range.includes(21))
    externalSlots.add(`1|${date}|21`);
  const collisions = reservations.filter(r => r.venue_id === v.venue_id && r.date === date && r.status !== 'cancelled' && range.some(h => h >= r.start_hour && h < r.end_hour));
  const slots = range.filter(h => externalSlots.has(`${v.venue_id}|${date}|${h}`) || collisions.some(r => h >= r.start_hour && h < r.end_hour));
  if (slots.length) {
    const mine = collisions.length && collisions.every(r => r.user_id === user.user_id) && !slots.some(h => externalSlots.has(`${v.venue_id}|${date}|${h}`));
    fail('SLOT_TAKEN', 409, mine ? '이미 내 예약과 겹치는 시간이에요.' : '다른 분이 먼저 결제한 시간이 있어요.', {
      slots, ...(mine && {
        mine: true, reservation_id: collisions[0].reservation_id
      })
    });
  }
  const r = {
    reservation_id: newReservationId(), user_id: user.user_id, venue_id: v.venue_id, date, start_hour, end_hour: start_hour + hours, headcount, total_price: v.price_per_hour * hours, status: date < todayISO() || Date.parse(`${date}T${String(start_hour + hours).padStart(2, '0')}:00:00+09:00`) <= Date.now() ? 'completed' : 'confirmed', created_at: stamp(), payment: {
      method, status: 'paid', paid_at: stamp(), refunded_at: null
    }
  };
  reservations.push(r);
  return reservationItem(r);
}
function owned(id, token) {
  const user = currentUser(token);
  const r = reservations.find(r => r.reservation_id === Number(id) && r.user_id === user.user_id);
  if (!r)
    fail('RESERVATION_NOT_FOUND', 404, '예약을 찾을 수 없어요.');
  return r;
}
export async function getReservation(id, token) {
  if (!USE_MOCK)
    return request(`/reservations/${id}`, {
      token
    });
  return mockDelay(reservationItem(owned(id, token)));
}
export async function getMyReservations(token, params = {}) {
  if (!USE_MOCK)
    return request(`/reservations/me?${query(params)}`, {
      token
    });
  const user = currentUser(token);
  if (params.status && !['confirmed', 'completed', 'cancelled'].includes(params.status))
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.');
  return mockDelay(pageOf(reservations.filter(r => r.user_id === user.user_id).map(reservationItem).filter(r => !params.status || r.status === params.status).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)), params));
}
export async function cancelReservation(id, token) {
  if (!USE_MOCK)
    return request(`/reservations/${id}/cancel`, {
      method: 'POST', token
    });
  const r = owned(id, token);
  const item = reservationItem(r);
  if (r.status === 'cancelled')
    fail('ALREADY_CANCELLED', 409, '이미 취소된 예약이에요.');
  if (!item.can_cancel)
    fail('NOT_CANCELLABLE', 409, '이용이 시작된 예약은 취소할 수 없어요.');
  r.status = 'cancelled';
  r.payment.status = 'refunded';
  r.payment.refunded_at = stamp();
  return mockDelay(reservationItem(r));
}
