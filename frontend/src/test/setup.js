// Vitest 공통 준비. 테스트마다 로그인 상태(sessionStorage)를 비운다.
import { afterEach } from 'vitest'

afterEach(() => {
  sessionStorage.clear()
})
