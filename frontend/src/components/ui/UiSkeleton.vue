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
/* 빛 띠는 transform으로만 움직인다(GPU). 계속 도는 움직임이라 linear */
.sk::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--c-fill-shine), transparent);
  transform: translateX(-100%);
  animation: shimmer 1.4s linear infinite;
}
@keyframes shimmer {
  to {
    transform: translateX(100%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .sk::after {
    animation: none;
    opacity: 0;
  }
}
</style>
