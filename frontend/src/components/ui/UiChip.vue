<script setup>
// 켜고 끄는 필터 칩. v-model로 선택 여부를 받는다.
const pressed = defineModel({ type: Boolean, default: false })
</script>

<template>
  <button type="button" class="chip" :aria-pressed="pressed" @click="pressed = !pressed">
    <slot />
  </button>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 var(--sp-12);
  border: 0;
  border-radius: var(--r-sm);
  background: var(--c-fill);
  color: var(--c-ink-2);
  font-size: var(--fs-15);
  font-weight: 500;
  cursor: pointer;
  transition: border-color var(--t-fast), background-color var(--t-fast), color var(--t-fast);
}
.chip:hover {
  background: var(--c-line-strong);
}
.chip[aria-pressed='true'] {
  background: var(--c-ink);
  color: var(--c-on-dark);
}
</style>
