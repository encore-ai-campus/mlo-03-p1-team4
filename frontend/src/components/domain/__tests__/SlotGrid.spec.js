import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SlotGrid from '../SlotGrid.vue'

vi.mock('vue-sonner', () => ({ toast: vi.fn() }))
const { toast } = await import('vue-sonner')

// 9~14시 6칸. 12시는 마감, 9시는 이미 지남
const slots = [
  { hour: 9, taken: false, past: true },
  { hour: 10, taken: false, past: false },
  { hour: 11, taken: false, past: false },
  { hour: 12, taken: true, past: false },
  { hour: 13, taken: false, past: false },
  { hour: 14, taken: false, past: false },
  { hour: 15, taken: false, past: false },
  { hour: 16, taken: false, past: false },
  { hour: 17, taken: false, past: false },
]

function setup(modelValue = [], max = 4, min = 1) {
  const wrapper = mount(SlotGrid, {
    attachTo: document.body,
    props: { slots, label: '시간 칸', max, min, modelValue, 'onUpdate:modelValue': (v) => wrapper.setProps({ modelValue: v }) },
    global: { stubs: { UiTooltip: { template: '<slot />' } } },
  })
  // 화면 글자(9, 10…)가 아니라 접근성 이름(09:00부터 1시간)으로 칸을 찾는다
  const btn = (h) => wrapper.findAll('button').find((b) => (b.attributes('aria-label') ?? '').startsWith(`${String(h).padStart(2, '0')}:00`))
  return { wrapper, btn, value: () => wrapper.props('modelValue') }
}

describe('SlotGrid (F-22 시간 칸 선택 규칙)', () => {
  it('마감 칸만 막고 지난 칸은 표시와 함께 선택할 수 있다', async () => {
    const { btn, value } = setup()
    expect(btn(12).text()).toContain('마감')
    expect(btn(9).text()).toContain('지남')
    expect(btn(12).attributes('aria-disabled')).toBe('true')
    await btn(12).trigger('click')
    expect(value()).toEqual([])
    await btn(9).trigger('click')
    expect(value()).toEqual([9])
  })

  it('이어진 칸만 늘어나고, 떨어진 칸을 누르면 새로 시작한다', async () => {
    const { btn, value } = setup()
    await btn(13).trigger('click')
    await btn(14).trigger('click')
    expect(value()).toEqual([13, 14])
    expect(btn(13).attributes('aria-pressed')).toBe('true')
    await btn(10).trigger('click')
    expect(value()).toEqual([10])
  })

  it('최대 4칸을 넘기면 늘어나지 않고 안내한다', async () => {
    const { btn, value } = setup([13, 14, 15, 16])
    await btn(17).trigger('click')
    expect(value()).toEqual([13, 14, 15, 16])
    expect(toast).toHaveBeenCalledWith('한 번에 최대 4시간까지 예약할 수 있어요')
  })

  it('양 끝 칸을 다시 누르면 그 칸만 빠진다', async () => {
    const { btn, value } = setup([13, 14, 15])
    await btn(15).trigger('click')
    expect(value()).toEqual([13, 14])
    await btn(13).trigger('click')
    expect(value()).toEqual([14])
  })

  it('가운데 칸을 누르면 그 칸만 남는다 (중간이 비는 예약 방지)', async () => {
    const { btn, value } = setup([13, 14, 15])
    await btn(14).trigger('click')
    expect(value()).toEqual([14])
  })
})

describe('SlotGrid 최소 이용시간 (11-07 팀 피드백)', () => {
  const minMsg = '이 공간은 최소 이용시간이 2시간이라 2시간 미만은 예약할 수 없어요'

  it('처음 누르면 최소 시간만큼 한 번에 잡고, 그다음부터 1칸씩 늘린다', async () => {
    const { btn, value } = setup([], 4, 2)
    await btn(13).trigger('click')
    expect(value()).toEqual([13, 14])
    await btn(15).trigger('click')
    expect(value()).toEqual([13, 14, 15])
  })

  it('뒤가 마감이면 앞쪽으로 최소 묶음을 잡고, 둘 다 안 되면 안내만 한다', async () => {
    const { btn, value } = setup([], 4, 2)
    await btn(11).trigger('click') // 12시 마감 → 10~11시
    expect(value()).toEqual([10, 11])
    toast.mockClear()
    const only = setup([], 4, 3)
    await only.btn(13).trigger('click')
    expect(only.value()).toEqual([13, 14, 15])
    await only.btn(10).trigger('click') // 10~12는 12시 마감 → 한 칸 당겨 9~11(지난 칸도 예약 가능)
    expect(only.value()).toEqual([9, 10, 11])
  })

  it('줄여서 최소 시간보다 짧아지면 빼지 않고 안내한다', async () => {
    const { btn, value } = setup([13, 14], 4, 2)
    toast.mockClear()
    await btn(14).trigger('click')
    expect(value()).toEqual([13, 14])
    expect(toast).toHaveBeenCalledWith(minMsg)
    const longer = setup([13, 14, 15], 4, 2)
    await longer.btn(15).trigger('click')
    expect(longer.value()).toEqual([13, 14])
  })

  it('마우스로 끌면 지나간 칸까지 이어서 고르고, 마감 칸 앞에서 멈춘다', async () => {
    const { wrapper, btn, value } = setup([], 4, 2)
    const li = (h) => wrapper.find(`li[data-hour="${h}"]`).element
    const original = document.elementFromPoint
    let over = 13
    document.elementFromPoint = () => li(over)
    try {
      await btn(13).trigger('pointerdown', { pointerType: 'mouse' })
      over = 15
      await wrapper.find('ul').trigger('pointermove', { pointerType: 'mouse' })
      expect(value()).toEqual([13, 14, 15])
      over = 17
      await wrapper.find('ul').trigger('pointermove', { pointerType: 'mouse' })
      expect(value()).toEqual([13, 14, 15, 16]) // 최대 4칸
      await wrapper.find('ul').trigger('pointerup')
      // 왼쪽으로 끌면 12시 마감 앞에서 멈춰 최소 2칸을 채우지 못하므로 바꾸지 않는다
      await btn(11).trigger('pointerdown', { pointerType: 'mouse' })
      over = 10
      await wrapper.find('ul').trigger('pointermove', { pointerType: 'mouse' })
      expect(value()).toEqual([10, 11])
    } finally {
      document.elementFromPoint = original
    }
  })
})
