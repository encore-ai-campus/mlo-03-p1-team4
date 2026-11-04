import { afterEach, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { toast } from 'vue-sonner'
import App from '../../../App.vue'

vi.mock('vue-sonner', () => ({ toast: { error: vi.fn() } }))
let wrapper
afterEach(() => { wrapper?.unmount(); vi.useRealTimers(); vi.clearAllMocks() })
const stubs = { TooltipProvider: { template: '<slot />' }, AppHeader: true, AppFooter: true, AppToaster: true, RouterView: true, BaseButton: { template: '<button><slot /></button>' } }
const emit = (detail) => window.dispatchEvent(new CustomEvent('spacecube:api-error', { detail }))

it('500이면 토스트에 오류 번호(request_id)를 같이 보여 준다', () => {
  wrapper = mount(App, { global: { stubs } })
  emit({ code: 'INTERNAL_ERROR', message: '잠시 후 다시 시도해 주세요.', detail: { request_id: 'req-7f3a' } })
  expect(toast.error).toHaveBeenCalledWith('잠시 후 다시 시도해 주세요.', expect.objectContaining({ description: '오류 번호 req-7f3a' }))
})

it('405는 토스트로 알린다', () => {
  wrapper = mount(App, { global: { stubs } })
  emit({ code: 'METHOD_NOT_ALLOWED', message: '요청을 처리하지 못했어요.' })
  expect(toast.error).toHaveBeenCalledWith('요청을 처리하지 못했어요.')
})

it('503이면 30초 동안 전체 안내 후 현재 화면 조회를 다시 시도한다', async () => {
  vi.useFakeTimers()
  wrapper = mount(App, { global: { stubs: { TooltipProvider: { template: '<slot />' }, AppHeader: true, AppFooter: true, AppToaster: true, RouterView: true, BaseButton: { template: '<button><slot /></button>' } } } })
  window.dispatchEvent(new CustomEvent('spacecube:api-error', { detail: { code: 'SERVICE_UNAVAILABLE', message: '서비스 점검 중이에요.' } }))
  await nextTick()
  expect(wrapper.get('[role="alert"]').text()).toContain('서비스 점검 중')
  await vi.advanceTimersByTimeAsync(30000)
  expect(wrapper.find('[role="alert"]').exists()).toBe(false)
})
