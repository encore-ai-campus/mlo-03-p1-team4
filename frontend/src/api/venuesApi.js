import { USE_MOCK, mockDelay, request, query } from './client';
import { VENUES, reservations, venueRequired, venueItem, slotsFor, validateDate, freeRun, pageOf, fail, seoulHour } from './mock/db';
import { facilities } from './mock/catalog';
import { addDays, todayISO } from '@/utils/date';
export async function searchVenues(params = {}) {
  if (!USE_MOCK)
    return request(`/venues?${query(params)}`);
  const { category, sido, sigungu, people, q, sort = 'default', now } = params;
  const date = now === true || now === 'true' ? todayISO() : (params.date || todayISO());
  validateDate(date);
  if (![
    'default', 'popular', 'price', 'rating'
  ].includes(sort) || category && category !== 'all' && !VENUES.some(v => v.category.code === category))
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.');
  let list = VENUES.filter(v => (!category || category === 'all' || v.category.code === category) && (!sido || sido === '전국' || v.region.sido === sido) && (!sigungu || sigungu === '전체' || v.region.sigungu === sigungu) && (!people || v.capacity_max >= Number(people)) && (!q || `${v.name} ${v.region.sigungu} ${v.facilities.map(f => f.name).join(' ')}`.includes(q)));
  const filterFacilities = Array.isArray(params.facilities) ? params.facilities : String(params.facilities ?? '').split(',').filter(Boolean);
  list = list.filter(v => filterFacilities.every(id => v.facilities.some(f => f.facility_id === Number(id)))).map(v => venueItem(v, date));
  if (params.start_hour !== undefined && params.hours !== undefined)
    list = list.filter(v => {
      const start = Number(params.start_hour), hours = Number(params.hours);
      return Number.isInteger(start) && Number.isInteger(hours) && hours >= v.min_hours && hours <= 4 && start >= v.open_hour && start + hours <= v.close_hour && v.slots.filter(s => s.hour >= start && s.hour < start + hours).every(s => !s.taken);
    });
  if (now === true || now === 'true')
    list = list.filter(v => v.slots.some(s => !s.taken && s.hour > seoulHour()));
  if (sort === 'price')
    list.sort((a, b) => a.price_per_hour - b.price_per_hour);
  if (sort === 'rating')
    list.sort((a, b) => b.rating_avg - a.rating_avg);
  if (sort === 'popular') {
    const weekAgo = Date.now() - 7 * 864e5;
    const counts = new Map();
    for (const reservation of reservations) {
      const paidDay = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'
      }).format(new Date(reservation.created_at));
      if (reservation.status === 'cancelled' || Date.parse(reservation.created_at) < weekAgo || reservation.date < paidDay) continue;
      counts.set(reservation.venue_id, (counts.get(reservation.venue_id) ?? 0) + 1);
    }
    list.sort((a, b) => (counts.get(b.venue_id) ?? 0) - (counts.get(a.venue_id) ?? 0));
  }
  return mockDelay(pageOf(list, params));
}
export async function getVenue(id) {
  if (!USE_MOCK)
    return request(`/venues/${id}`);
  const v = venueRequired(id);
  return mockDelay({
    ...venueItem(v), min_hours: v.min_hours, description: v.description, notice: v.notice, images: [v.image], facilities: v.facilities
  });
}
export async function getSlots(id, date = todayISO()) {
  if (!USE_MOCK)
    return request(`/venues/${id}/slots?${query({
      date
    })}`);
  venueRequired(id);
  validateDate(date);
  return mockDelay(slotsFor(id, date));
}
export async function getAvailableDates(id, offset = 0, days = 14) {
  if (!USE_MOCK)
    return request(`/venues/${id}/available-dates?${query({
      offset, days
    })}`);
  const v = venueRequired(id);
  offset = Number(offset);
  days = Number(days);
  if (!Number.isInteger(offset) || !Number.isInteger(days) || days < 1 || days > 31)
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.');
  validateDate(addDays(todayISO(), offset));
  const min_date = addDays(todayISO(), -365), max_date = addDays(todayISO(), 365);
  const dates = Array.from({
    length: days
  }, (_, i) => addDays(todayISO(), offset + i)).filter(date => date <= max_date && date >= min_date).map(date => {
    const slots = slotsFor(id, date);
    return {
      date, free: slots.filter(s => !s.taken).length, bookable: freeRun(slots) >= v.min_hours
    };
  });
  return mockDelay({
    venue_id: Number(id), offset, days, min_date, max_date, dates
  });
}
export function getFacilities() {
  return USE_MOCK ? mockDelay(facilities) : request('/facilities');
}
