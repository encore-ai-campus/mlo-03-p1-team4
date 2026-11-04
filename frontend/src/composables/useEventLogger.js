import { getSessionId, request, USE_MOCK } from '@/api/client';
import { useAuthStore } from '@/stores/auth';
export const FRONTEND_EVENTS = Object.freeze([
  'search', 'view_venue', 'view_dates', 'select_slot', 'reserve_try', 'reserve_cancel', 'review_create', 'login', 'signup'
]);
const allowedPayload = new Set([
  'category', 'sido', 'sigungu', 'date', 'people', 'headcount', 'hour', 'hours', 'start_hour', 'reservation_id', 'rating', 'sort', 'facilities'
]);
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
    log(event_type, payload = {}) {
      if (!FRONTEND_EVENTS.includes(event_type))
        return;
      const { venue_id, ...rest } = payload;
      const clean = Object.fromEntries(Object.entries(rest).filter(([key]) => allowedPayload.has(key)));
      queue.push({
        event_type, ...(venue_id !== undefined && {
          venue_id: Number(venue_id)
        }), payload: clean, occurred_at: new Date().toISOString()
      });
      if (queue.length >= 20)
        void flush();
    }, flush
  };
}
