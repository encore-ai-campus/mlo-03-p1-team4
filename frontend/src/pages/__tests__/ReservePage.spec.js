// 회귀: http 배포 주소(randomUUID 없음)에서 이벤트 기록이 실패하면 결제 POST가 안 나가고 로딩이 남던 문제
import { expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'

const { createReservation, log } = vi.hoisted(() => ({
  createReservation: vi.fn(),
  log: vi.fn(() => { throw new TypeError('crypto.randomUUID is not a function') }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { venue: '1', date: '2026-11-20', start: '17', hours: '3', people: '2' } }),
  useRouter: () => ({ replace: vi.fn() }),
  RouterLink: { props: ['to'], template: '<a><slot /></a>' },
}))
vi.mock('vue-sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/composables/useAuth', () => ({ useAuth: () => ({ token: ref('test-token') }) }))
vi.mock('@/composables/useEventLogger', () => ({ useEventLogger: () => ({ log }) }))
vi.mock('@/api/reservationsApi', () => ({ createReservation }))
vi.mock('@/api/venuesApi', () => ({
  getVenue: vi.fn().mockResolvedValue({ venue_id: 1, name: '시험 공간', category: { code: 'partyroom', name: '파티룸' }, region: { sido: '서울', sigungu: '서대문구' }, capacity_max: 12, price_per_hour: 30000, min_hours: 3, open_hour: 9, close_hour: 23, images: [] }),
  getSlots: vi.fn().mockResolvedValue(Array.from({ length: 14 }, (_, i) => ({ hour: 9 + i, taken: false, past: false }))),
}))

it('이벤트 기록이 실패해도 예약 요청을 보내고 로딩을 해제한다', async () => {
  window.scrollTo = vi.fn()
  createReservation.mockResolvedValue({ reservation_id: 7, status: 'confirmed', venue_id: 1, date: '2026-11-20', start_hour: 17, end_hour: 20, headcount: 2, total_price: 90000 })
  const ReservePage = (await import('../ReservePage.vue')).default
  const wrapper = mount(ReservePage, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()

  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(log).toHaveBeenCalledWith('reservation_start', expect.objectContaining({ venue_id: 1, start_hour: 17, hours: 3 }))
  expect(createReservation).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ venue_id: 1, date: '2026-11-20', start_hour: 17, hours: 3, headcount: 2 }), 'test-token')
  expect(wrapper.find('[aria-busy="true"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('예약이 확정됐어요')
})

it('예약 요청이 실패해도 로딩을 해제한다', async () => {
  createReservation.mockRejectedValue(Object.assign(new Error('결제하지 못했어요.'), { code: 'INTERNAL' }))
  const ReservePage = (await import('../ReservePage.vue')).default
  const wrapper = mount(ReservePage, { global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()

  await wrapper.get('input[type="checkbox"]').setValue(true)
  await wrapper.get('form').trigger('submit')
  await flushPromises()

  expect(createReservation).toHaveBeenCalled()
  expect(wrapper.find('[aria-busy="true"]').exists()).toBe(false)
  expect(wrapper.find('form fieldset[disabled]').exists()).toBe(false)
})
