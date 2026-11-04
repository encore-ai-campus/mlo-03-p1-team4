import { describe, expect, it } from 'vitest'
import { formatHours, longestFreeRun, parseHours } from '../slots'

const S = (hour, taken = false, past = false) => ({ hour, taken, past })

describe('slots utils', () => {
  it('F-22 longestFreeRun: 마감에서만 끊기고 지난 칸도 포함한다', () => {
    expect(longestFreeRun([S(9), S(10), S(11, true), S(12), S(13), S(14)])).toBe(3)
    expect(longestFreeRun([S(9, false, true), S(10, false, true), S(11)])).toBe(3)
    expect(longestFreeRun([S(21, true), S(22, true)])).toBe(0)
    expect(longestFreeRun([])).toBe(0)
  })

  it('hours 주소 값 왕복', () => {
    expect(formatHours([14, 13])).toBe('13,14')
    expect(parseHours('13,14')).toEqual([13, 14])
    expect(parseHours(undefined)).toEqual([])
    expect(parseHours('13,x,15')).toEqual([13, 15])
  })
})
