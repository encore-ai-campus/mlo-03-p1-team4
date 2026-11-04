<script setup>
// 두 칸 나란히 (로그인·회원가입, 예약 폼/요약, 상세 본문/예약 카드). 768px 아래는 위아래로 쌓인다.
// stickyEnd: 오른쪽 칸을 스크롤해도 따라오게 (상세 예약 카드)
defineProps({
  ratio: { type: String, default: '3fr 2fr' },
  stickyEnd: { type: Boolean, default: false },
})
</script>

<template>
  <div class="split" :style="{ '--split-cols': ratio }">
    <div class="split__start"><slot name="start" /></div>
    <div class="split__end" :class="{ 'is-sticky': stickyEnd }"><slot name="end" /></div>
  </div>
</template>

<style scoped>
.split {
  display: grid;
  gap: var(--sp-24);
}
@media (min-width: 768px) {
  .split {
    grid-template-columns: var(--split-cols);
    align-items: start;
    gap: var(--sp-32);
  }
  .split__end.is-sticky {
    position: sticky;
    top: calc(var(--header-h) + var(--sp-16));
  }
}
.split__start,
.split__end {
  min-width: 0;
}
</style>
