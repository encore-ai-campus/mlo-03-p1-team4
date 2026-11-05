<script setup>
// 불러오는 동안 실제 내용과 같은 자리를 차지하는 회색 블록 (화면 밀림 방지)
defineProps({
  width: { type: String, default: '100%' },
  height: { type: String, default: '1em' },
  radius: { type: String, default: 'var(--r-sm)' },
})
</script>

<template>
  <span class="sk" :style="{ width, height, borderRadius: radius }" aria-hidden="true" />
</template>

<style scoped>
.sk {
  position: relative;
  display: block;
  overflow: hidden;
  background: var(--c-fill);
}
/* 그라데이션 빛 띠 대신 불투명도만 천천히 바꾼다 */
.sk {
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    opacity: 0.55;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sk {
    animation: none;
  }
}
</style>
