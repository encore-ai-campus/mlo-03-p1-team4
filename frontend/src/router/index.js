import { createRouter, createWebHistory } from 'vue-router'
import MainPage from '@/pages/MainPage.vue'
import { useAuthStore } from '@/stores/auth'
import { setUnauthorizedHandler } from '@/api/client'

const routes = [
  { path: '/', name: 'main', component: MainPage, meta: { title: '다락큐브' } },
  { path: '/search', name: 'search', component: () => import('@/pages/SearchPage.vue'), meta: { title: '빈 시간 찾기' } },
  { path: '/rooms/:roomId', redirect: (to) => ({ name: 'venue', params: { venueId: to.params.roomId }, query: to.query }) },
  { path: '/venues/:venueId', name: 'venue', component: () => import('@/pages/RoomPage.vue'), meta: { title: '공간 상세' } },
  { path: '/reservations/:id', redirect: '/me' },
  { path: '/reserve', name: 'reserve', component: () => import('@/pages/ReservePage.vue'), meta: { title: '예약 확인 · 결제', requiresAuth: true } },
  { path: '/login', name: 'login', component: () => import('@/pages/AuthPage.vue'), meta: { title: '로그인 · 회원가입' } },
  { path: '/me', name: 'me', component: () => import('@/pages/MyPage.vue'), meta: { title: '예약 내역', requiresAuth: true } },
  { path: '/board', redirect: (to) => ({ path: '/reviews', query: to.query }) },
  { path: '/reviews', name: 'reviews', component: () => import('@/pages/BoardPage.vue'), meta: { title: '후기 모아보기' } },
  { path: '/ui', name: 'ui', component: () => import('@/pages/UiShowcasePage.vue'), meta: { title: '컴포넌트 모음' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/PlaceholderPage.vue'), meta: { title: '찾는 페이지가 없어요' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash }
    if (to.path === from.path) return false // 같은 화면에서 필터·탭(query)만 바뀌면 스크롤 유지
    return { top: 0 }
  },
})

// 로그인이 필요한 화면은 로그인 후 돌아오게
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !useAuthStore().isLoggedIn) {
    return { name: 'login', query: { next: to.fullPath } }
  }
})

router.afterEach((to) => {
  document.title = to.meta.title === '다락큐브' ? '다락큐브 · 1시간 단위 공간 예약' : `${to.meta.title} · 다락큐브`
})

setUnauthorizedHandler(() => {
  const current = router.currentRoute.value
  useAuthStore().logout()
  if (current.name !== 'login') router.replace({ name: 'login', query: { next: current.fullPath } })
})

export default router
