<script setup>
// 왼쪽 사이드바 + 본문 (조회 필터, 마이페이지 메뉴). 1024px 아래에서는 사이드바를 숨기고,
// 쓰는 화면이 같은 내용을 UiDrawer로 열 수 있게 #mobile-trigger 자리를 둔다.
defineProps({ label: { type: String, required: true } })
</script>

<template>
  <div class="sidebar-layout">
    <aside class="sidebar" :aria-label="label"><slot name="sidebar" /></aside>
    <div class="sidebar-layout__main">
      <div class="mobile-trigger"><slot name="mobile-trigger" /></div>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.sidebar-layout {
  display: grid;
  gap: var(--sp-24);
}
.sidebar {
  display: none;
}
.sidebar-layout__main {
  min-width: 0;
}
@media (min-width: 1024px) {
  .sidebar-layout {
    grid-template-columns: 280px minmax(0, 1fr);
    align-items: start;
  }
  .sidebar {
    display: block;
    position: sticky;
    top: calc(var(--header-h) + var(--sp-16));
  }
  .mobile-trigger {
    display: none;
  }
}
</style>
