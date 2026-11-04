import { afterEach, describe, expect, it, vi } from 'vitest'
import { addDays, dateLabel, dayOffset, hourLabel, nextDays, nowInSeoul, rangeLabel, todayISO, won } from '../date'

describe('date utils', () => {
  afterEach(() => vi.useRealTimers())

  it('F-21 한국 자정 경계와 과거 날짜 띠를 처리한다', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-11-02T15:30:00Z'))
    expect(nowInSeoul()).toEqual({ date: '2026-11-03', hour: 0 })
    expect(todayISO()).toBe('2026-11-03')
    expect(nextDays(14, -14)[0].iso).toBe('2026-10-20')
    expect(dayOffset('2026-10-20')).toBe(-14)
    expect(dayOffset('2026-02-31')).toBeNaN()
    expect(nextDays(14, 360)).toHaveLength(6)
  })

  it('addDays는 월·연도 경계를 넘긴다', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
  })

  it('nextDays(14)는 오늘부터 14일, 첫날만 isToday', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 10, 1, 10)) // 2026-11-01 (일)
    const days = nextDays(14)
    expect(days).toHaveLength(14)
    expect(days[0]).toMatchObject({ iso: '2026-11-01', weekday: '일', isToday: true })
    expect(days[13].iso).toBe('2026-11-14')
    expect(days.filter((d) => d.isToday)).toHaveLength(1)
    expect(todayISO()).toBe('2026-11-01')
  })

  it('rangeLabel은 끝 칸의 다음 시각까지 표시', () => {
    expect(rangeLabel([13, 14])).toBe('13:00–15:00')
    expect(rangeLabel([9])).toBe('09:00–10:00')
    expect(rangeLabel([22, 21])).toBe('21:00–23:00')
    expect(rangeLabel([])).toBe('')
  })

  it('표시 형식', () => {
    expect(hourLabel(9)).toBe('09:00')
    expect(dateLabel('2026-11-02')).toBe('11월 2일 (월)')
    expect(won(20000)).toBe('20,000원')
  })
})
