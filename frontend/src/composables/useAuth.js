import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 로그인 상태를 화면에서 쓰는 창구. 로그인이 필요한 동작 앞에서 requireLogin()을 부른다.
export function useAuth() {
  const store = useAuthStore()
  const { user, token, isLoggedIn } = storeToRefs(store)
  const router = useRouter()
  const route = useRoute()

  function requireLogin(next = route.fullPath) {
    if (isLoggedIn.value) return true
    router.push({ name: 'login', query: { next } })
    return false
  }

  return { user, token, isLoggedIn, requireLogin, setSession: store.setSession, logout: store.logout }
}
