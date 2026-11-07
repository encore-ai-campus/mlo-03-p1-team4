<script setup>
import { computed, ref } from 'vue'
import { useWindowScroll } from '@vueuse/core'
import { Menu, User } from '@lucide/vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiMenu from '@/components/ui/UiMenu.vue'
import { useAuth } from '@/composables/useAuth'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'

const { y } = useWindowScroll()
const compact = computed(() => y.value > 8)
const menuOpen = ref(false)
const { user, isLoggedIn, logout } = useAuth()
const router = useRouter()

const links = [
  { to: '/search', label: '공간 찾기' },
  { to: '/me', label: '예약 내역' },
  { to: '/reviews', label: '후기 모아보기' },
]
const userMenu = [
  { label: '예약 내역', onSelect: () => router.push('/me') },
  {
    label: '로그아웃',
    onSelect: () => {
      logout()
      toast('로그아웃했어요')
      router.push('/')
    },
  },
]
</script>

<template>
  <header class="header" :class="{ 'is-compact': compact }">
    <div class="container header__inner">
      <RouterLink to="/" class="logo" aria-label="다락큐브 홈">
        <span class="logo__mark" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z" /><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5" /></svg>
        </span>
        <span class="logo__name">다락큐브</span>
      </RouterLink>

      <nav class="nav" aria-label="주 메뉴">
        <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="nav__link">{{ l.label }}</RouterLink>
      </nav>

      <div class="header__actions">
        <template v-if="isLoggedIn">
          <UiMenu :items="userMenu">
            <button type="button" class="user-btn"><User :size="18" aria-hidden="true" />{{ user.name }} 님</button>
          </UiMenu>
        </template>
        <template v-else>
          <BaseButton variant="quiet" :to="{ path: '/login' }" class="hide-sm">로그인</BaseButton>
          <BaseButton :to="{ path: '/login', query: { tab: 'signup' } }">회원가입</BaseButton>
        </template>

        <UiDrawer v-model:open="menuOpen" title="메뉴" side="right">
          <template #trigger>
            <button type="button" class="menu-btn" aria-label="메뉴 열기"><Menu :size="22" aria-hidden="true" /></button>
          </template>
          <nav class="drawer-nav" aria-label="모바일 메뉴">
            <RouterLink v-for="l in links" :key="l.to" :to="l.to" class="drawer-nav__link" @click="menuOpen = false">{{ l.label }}</RouterLink>
            <RouterLink v-if="!isLoggedIn" to="/login" class="drawer-nav__link" @click="menuOpen = false">로그인</RouterLink>
          </nav>
        </UiDrawer>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* 스티키 헤더: 반투명·흐림·그림자 없이 평평한 바탕 (높이는 움직이지 않음)
   스크롤하면 하단에 주 색 선을 그어 '고정된 상단바'임을 보여 준다(11-07 팀 피드백). 선은 높이를 바꾸지 않게 그림자로 그린다. */
.header {
  position: sticky;
  top: 0;
  z-index: 40;
  background: var(--c-paper);
  box-shadow: inset 0 -1px 0 var(--c-line);
  transition: box-shadow var(--t-fast) var(--ease-out);
}
.header.is-compact {
  box-shadow: inset 0 -2px 0 var(--c-brand);
}
@media (prefers-reduced-motion: reduce) {
  .header {
    transition: none;
  }
}
.header__inner {
  display: flex;
  align-items: center;
  gap: var(--sp-24);
  height: var(--header-h);
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--c-ink);
  text-decoration: none;
}
.logo__mark {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: var(--c-brand);
  color: var(--c-on-dark);
}
.logo__name {
  font-size: 19px;
  font-weight: 900;
  letter-spacing: -0.03em;
}
.nav {
  display: none;
  gap: 2px;
  flex: 1;
}
.nav__link {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
  padding: 0 var(--sp-12);
  border-radius: var(--r-sm);
  color: var(--c-muted);
  font-weight: 500;
  text-decoration: none;
}
.nav__link:hover {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
.nav__link.router-link-active {
  color: var(--c-brand-ink);
  font-weight: 700;
}
.header__actions {
  display: flex;
  align-items: center;
  gap: var(--sp-8);
  margin-left: auto;
}
.user-btn,
.menu-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: var(--tap);
  min-width: var(--tap);
  justify-content: center;
  padding: 0 var(--sp-12);
  border: 0;
  border-radius: var(--r-md);
  background: var(--c-fill);
  font-weight: 500;
  cursor: pointer;
}
.user-btn:hover,
.menu-btn:hover {
  background: var(--c-line-strong);
}
.menu-btn {
  padding: 0;
}
.drawer-nav {
  display: flex;
  flex-direction: column;
}
.drawer-nav__link {
  display: flex;
  align-items: center;
  min-height: 52px;
  color: var(--c-ink);
  font-size: var(--fs-16);
  font-weight: 700;
  text-decoration: none;
}
@media (max-width: 479px) {
  .hide-sm {
    display: none;
  }
}
@media (min-width: 900px) {
  .nav {
    display: flex;
  }
  .header__actions {
    margin-left: 0;
  }
  .menu-btn {
    display: none;
  }
}
</style>
