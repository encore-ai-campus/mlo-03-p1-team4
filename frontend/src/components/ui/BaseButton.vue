<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

// variant: primary(주 행동, 화면에 하나) · secondary · quiet
const props = defineProps({
  variant: { type: String, default: 'primary' },
  size: { type: String, default: 'md' },
  to: { type: [String, Object], default: null },
  href: { type: String, default: null },
  type: { type: String, default: 'button' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const tag = computed(() => (props.to ? RouterLink : props.href ? 'a' : 'button'))
const attrs = computed(() => {
  if (props.to) return { to: props.to }
  if (props.href) return { href: props.href }
  return { type: props.type, disabled: props.disabled || props.loading }
})
</script>

<template>
  <component
    :is="tag"
    v-bind="attrs"
    class="btn"
    :class="[`btn--${variant}`, `btn--${size}`, { 'is-loading': loading }]"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="spinner" aria-hidden="true" />
    <slot />
  </component>
</template>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-8);
  min-height: var(--tap);
  padding: 0 var(--sp-16);
  border: 1px solid transparent;
  border-radius: var(--r-md);
  font-weight: 700;
  font-size: var(--fs-15);
  text-decoration: none;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color var(--t-fast), border-color var(--t-fast), color var(--t-fast), transform var(--t-fast) var(--ease-out);
}
.btn:active:not(:disabled) {
  transform: scale(0.97);
}
.btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.btn--lg {
  min-height: 52px;
  padding: 0 var(--sp-24);
  font-size: var(--fs-16);
}
.btn--primary {
  background: var(--c-brand);
  color: var(--c-on-dark);
}
.btn--primary:hover:not(:disabled) {
  background: var(--c-brand-hover);
}
.btn--secondary {
  background: var(--c-surface);
  border-color: var(--c-line-strong);
  color: var(--c-ink);
}
.btn--secondary:hover:not(:disabled) {
  border-color: var(--c-brand);
  color: var(--c-brand-ink);
}
.btn--quiet {
  background: transparent;
  color: var(--c-muted);
  font-weight: 500;
}
.btn--quiet:hover:not(:disabled) {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
