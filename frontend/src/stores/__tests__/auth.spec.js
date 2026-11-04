import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../auth'

describe('auth store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('로그인하면 sessionStorage에 남고, 로그아웃하면 비워진다', async () => {
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(false)
    store.setSession('mock-token', { user_id: 1, name: '김스터디' })
    await nextTick()
    expect(store.isLoggedIn).toBe(true)
    expect(JSON.parse(sessionStorage.getItem('spacecube.session'))).toMatchObject({ token: 'mock-token' })

    store.logout()
    await nextTick()
    expect(store.isLoggedIn).toBe(false)
    expect(JSON.parse(sessionStorage.getItem('spacecube.session')).token).toBeNull()
  })

  it('새로고침(새 스토어)해도 같은 탭이면 로그인이 유지된다', () => {
    sessionStorage.setItem('spacecube.session', JSON.stringify({ token: 't', user: { name: 'a' } }))
    const store = useAuthStore()
    expect(store.isLoggedIn).toBe(true)
    expect(store.user.name).toBe('a')
  })

  it('저장 값이 깨져 있어도 화면이 죽지 않는다', () => {
    sessionStorage.setItem('spacecube.session', '{broken')
    expect(useAuthStore().isLoggedIn).toBe(false)
  })
})
