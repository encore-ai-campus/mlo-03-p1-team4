<script setup>
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
// RoomCard와 같은 크기의 자리 (그림 비율 400:260, 본문 줄 수 동일)
</script>

<template>
  <div class="sk-card" aria-hidden="true">
    <UiSkeleton height="auto" radius="var(--r-lg) var(--r-lg) 0 0" class="sk-card__media" />
    <div class="sk-card__body">
      <UiSkeleton width="60%" height="26px" />
      <UiSkeleton width="80%" height="18px" />
      <UiSkeleton height="18px" />
      <UiSkeleton width="90%" height="18px" />
      <UiSkeleton height="14px" />
      <UiSkeleton width="40%" height="26px" />
    </div>
  </div>
</template>

<style scoped>
.sk-card {
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.sk-card__media {
  aspect-ratio: 400 / 260;
}
.sk-card__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: var(--sp-16);
}
</style>
