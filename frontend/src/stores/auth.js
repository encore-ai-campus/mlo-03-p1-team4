import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

// 로그인 상태. 탭을 닫기 전까지 유지(sessionStorage). 저장소를 못 쓰는 환경이면 메모리에만 둔다.
const KEY = 'spacecube.session'
function load() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY)) ?? {}
  } catch {
    return {}
  }
}

export const useAuthStore = defineStore('auth', () => {
  const saved = load()
  const token = ref(saved.token ?? null)
  const user = ref(saved.user ?? null)
  const isLoggedIn = computed(() => Boolean(token.value))

  watch([token, user], () => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ token: token.value, user: user.value }))
    } catch {
      /* 저장 못 해도 화면은 동작 */
    }
  })

  function setSession(accessToken, u) {
    token.value = accessToken
    user.value = u
  }

  function logout() {
    token.value = null
    user.value = null
  }

  return { token, user, isLoggedIn, setSession, logout }
})
