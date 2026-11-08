import { getSessionId, request, USE_MOCK } from '@/api/client';
import { useAuthStore } from '@/stores/auth';
import { uuid } from '@/utils/uuid';

// 사용자 행동 이벤트. 구조는 docs/db/events_event_daily_컬렉션_속성정리_v1.md(11-06 PM 채택, 대응표는 PR #58 코멘트).
// 서버가 확인하는 reservation_complete·reservation_conflict·reservation_cancel_complete는 B가 보내고, 여기서는 보내지 않는다.
export const FRONTEND_EVENTS = Object.freeze([
  'page_view', 'product_impression', 'product_view', 'product_section_click', 'search_submit', 'availability_view',
  'rental_slot_select', 'reservation_start', 'reservation_cancel_attempt', 'review_create', 'login', 'signup'
]);
const allowedProperties = new Set([
  'category', 'sido', 'sigungu', 'date', 'people', 'headcount', 'hour', 'hours', 'start_hour', 'reservation_id', 'rating', 'sort', 'facilities'
]);
const PAGE_TYPES = [
  [/^\/venues\//, 'product_detail'], [/^\/search/, 'search_results'], [/^\/reserve/, 'checkout'],
  [/^\/me/, 'my_page'], [/^\/login/, 'auth'], [/^\/reviews/, 'reviews'], [/^\/$/, 'home']
];
const ACQ_KEY = 'spacecube.event-acquisition';
const ANON_KEY = 'spacecube.anonymous-id';

function stored(storage, key, make) {
  try {
    const hit = storage.getItem(key);
    if (hit) return JSON.parse(hit);
    const value = make();
    storage.setItem(key, JSON.stringify(value));
    return value;
  }
  catch { return make(); } /* 저장소 없이 동작 */
}
// 주소에는 검색어 등이 섞일 수 있어 쿼리·해시를 뺀다(#48 개인정보)
const bare = (href) => { try { const u = new URL(href); return u.origin + u.pathname; } catch { return null; } };

let sequence = 0;
let current = null; // 지금 페이지 { page_view_id, site_id, url, path }
let previous = null;
let navigationType = null;

function pageContext() {
  const { origin, pathname } = window.location;
  if (!current || current.path !== pathname) {
    previous = current;
    current = { page_view_id: uuid(), site_id: 'main', url: origin + pathname, path: pathname };
    const ref = document.referrer && bare(document.referrer);
    navigationType = previous ? 'internal' : ref && !ref.startsWith(origin) ? 'external' : 'direct';
  }
  return {
    page: { page_view_id: current.page_view_id, page_type: PAGE_TYPES.find(([re]) => re.test(pathname))?.[1] ?? 'other', url: current.url, path: current.path, title: document.title || '다락큐브' },
    navigation: { from: previous, to: current, navigation_type: navigationType },
  };
}

export function buildEvent(event_name, payload = {}) {
  const { venue_id, ...rest } = payload;
  const properties = Object.fromEntries(Object.entries(rest).filter(([key]) => allowedProperties.has(key)));
  const { page, navigation } = pageContext();
  const params = new URLSearchParams(window.location.search);
  const acquisition = stored(sessionStorage, ACQ_KEY, () => ({
    landing_url: window.location.origin + window.location.pathname,
    referrer_url: (document.referrer && bare(document.referrer)) || null,
    utm_source: params.get('utm_source'), utm_medium: params.get('utm_medium'), utm_campaign: params.get('utm_campaign'),
  }));
  return {
    event_id: uuid(),
    schema_version: 1,
    event_name,
    occurred_at: new Date().toISOString(),
    user: { anonymous_id: stored(localStorage, ANON_KEY, () => uuid()), session_id: getSessionId(), session_sequence: ++sequence },
    site: { site_id: 'main', hostname: window.location.hostname, platform: window.matchMedia?.('(max-width: 767px)').matches ? 'mobile_web' : 'desktop_web' },
    acquisition,
    page,
    navigation,
    // 공간 이름·가격·대여 조건은 서버가 공간 ID로 채운다(PR #58 코멘트 5-1)
    products: venue_id !== undefined ? [{ product_id: String(venue_id) }] : [],
    properties,
  };
}

const queue = [];
let started = false;
async function flush(keepalive = false) {
  if (!queue.length)
    return;
  const events = queue.splice(0, 50), body = {
    session_id: getSessionId(), events
  };
  if (USE_MOCK)
    return;
  try {
    await request('/events', {
      method: 'POST', body, token: useAuthStore().token, keepalive, reportErrors: false
    });
  }
  catch { /* 관측 오류로 사용자 흐름을 막지 않음 */
  }
}
export function useEventLogger() {
  if (!started && typeof window !== 'undefined') {
    started = true;
    const timer = setInterval(() => void flush(), 10000);
    timer.unref?.();
    window.addEventListener('pagehide', () => void flush(true));
  }
  return {
    log(event_name, payload = {}) {
      if (!FRONTEND_EVENTS.includes(event_name))
        return;
      // 기록 실패가 화면 흐름(날짜·시간 칸 불러오기 등)을 막지 않게 한다.
      try {
        queue.push(buildEvent(event_name, payload));
      }
      catch {
        return;
      }
      if (queue.length >= 20)
        void flush();
    }, flush
  };
}
