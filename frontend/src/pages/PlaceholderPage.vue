<script setup>
import BaseButton from '@/components/ui/BaseButton.vue'
</script>

<template>
  <section class="container soon">
    <h1 class="soon__title">찾는 페이지가 없어요</h1>
    <p class="soon__text">주소를 다시 확인하거나 메인에서 공간을 찾아보세요.</p>
    <BaseButton to="/" variant="secondary">메인으로 가기</BaseButton>
  </section>
</template>

<style scoped>
.soon {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-16);
  padding-block: var(--sp-64);
}
.soon__title {
  font-size: var(--fs-32);
  font-weight: 900;
}
.soon__text {
  color: var(--c-muted);
}
</style>
