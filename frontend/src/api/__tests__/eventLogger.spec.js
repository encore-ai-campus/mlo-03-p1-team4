import { afterEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { send } = vi.hoisted(() => ({ send: vi.fn().mockResolvedValue({ accepted: 1 }) }))
vi.mock('../client', () => ({ USE_MOCK: false, getSessionId: () => 'test-session', request: send }))
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers() })

it('허용된 프론트 이벤트만 보내고 공간·세션을 맞추며 개인정보를 제외한다', async () => {
  vi.useFakeTimers()
  setActivePinia(createPinia())
  const { useEventLogger, FRONTEND_EVENTS } = await import('@/composables/useEventLogger')
  const logger = useEventLogger()
  expect(FRONTEND_EVENTS).toEqual(['search', 'view_venue', 'view_dates', 'select_slot', 'reserve_try', 'reserve_cancel', 'review_create', 'login', 'signup'])
  logger.log('unknown_event', { email: 'private@example.com' })
  logger.log('select_slot', { venue_id: 2, hour: 13, email: 'private@example.com', name: '개인정보', q: '자유 입력' })
  await logger.flush()
  expect(send).toHaveBeenCalledExactlyOnceWith('/events', expect.objectContaining({
    reportErrors: false,
    body: { session_id: 'test-session', events: [{ event_type: 'select_slot', venue_id: 2, payload: { hour: 13 }, occurred_at: expect.any(String) }] },
  }))
})
