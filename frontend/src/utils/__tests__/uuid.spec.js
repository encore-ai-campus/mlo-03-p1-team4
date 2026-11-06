import { afterEach, describe, expect, it, vi } from 'vitest'
import { uuid } from '../uuid'

const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

describe('uuid', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('보안 컨텍스트에서는 crypto.randomUUID를 쓴다', () => {
    expect(uuid()).toMatch(V4)
  })

  it('http 배포 주소처럼 randomUUID가 없어도 v4 UUID를 만든다', () => {
    const real = globalThis.crypto
    vi.stubGlobal('crypto', { getRandomValues: (b) => real.getRandomValues(b) })
    const a = uuid()
    expect(a).toMatch(V4)
    expect(uuid()).not.toBe(a)
  })
})
