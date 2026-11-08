import { USE_MOCK, mockDelay, request, query } from './client';
import { categories } from './mock/catalog';
import { VENUES, venueItem, pageOf } from './mock/db';
import { searchVenues, getVenue, getSlots } from './venuesApi';
import { getReviews } from './reviewsApi';
import { addDays, dateLabel, todayISO } from '@/utils/date';
export { searchVenues };
export function getCategories() {
  return USE_MOCK ? mockDelay(categories) : request('/categories');
}
export function getRegions(sido) {
  if (!USE_MOCK)
    return request(`/regions?${query({
      sido
    })}`);
  const list = [...new Set(VENUES.map(v => v.region.sido))];
  return mockDelay(sido ? [...new Set(VENUES.filter(v => v.region.sido === sido).map(v => v.region.sigungu))].map((sigungu, i) => ({
    region_id: i + 1, sigungu
  })) : list);
}
export function getNewVenues(params = {}) {
  if (!USE_MOCK)
    return request(`/venues/new?${query(params)}`);
  return mockDelay(pageOf(VENUES.filter(v => v.is_new).map(v => ({
    ...venueItem(v), registered_on: v.registered_on, new_days_left: 11
  })), params));
}
export async function getTodaySlots(id = 1) {
  const v = await getVenue(id);
  let date = todayISO(), slots = await getSlots(id, date);
  if (!slots.some(s => !s.taken && !s.past)) {
    date = addDays(date, 1);
    slots = await getSlots(id, date);
  }
  const day = date === todayISO() ? '오늘' : '내일';
  return {
    venue_id: Number(id), name: v.name, price_per_hour: v.price_per_hour, date, day, date_label: `${day} ${dateLabel(date)}`, slots
  };
}
export function getRecentReviews() {
  return getReviews({
    size: 3
  });
}
