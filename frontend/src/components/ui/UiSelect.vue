<script setup>
import { SelectContent, SelectIcon, SelectItem, SelectItemIndicator, SelectItemText, SelectPortal, SelectRoot, SelectTrigger, SelectValue, SelectViewport } from 'reka-ui'
import { Check, ChevronDown } from '@lucide/vue'
import { useId } from 'vue'

// 값 하나 고르기 (시·도, 시·군·구, 인원, 정렬). 라벨은 항상 보이게 둔다.
const props = defineProps({
  label: { type: String, required: true },
  options: { type: Array, required: true }, // [{ value, label }] 또는 문자열 배열
  hideLabel: { type: Boolean, default: false },
})
const model = defineModel({ type: String })
const id = useId()
const items = () => props.options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o))
</script>

<template>
  <div class="field">
    <label :id="`${id}-label`" :for="`${id}-trigger`" class="field__label" :class="{ 'sr-only': hideLabel }">{{ label }}</label>
    <SelectRoot v-model="model">
      <SelectTrigger :id="`${id}-trigger`" class="select" :aria-labelledby="`${id}-label`">
        <SelectValue />
        <SelectIcon><ChevronDown :size="18" aria-hidden="true" /></SelectIcon>
      </SelectTrigger>
      <SelectPortal>
        <SelectContent class="select__menu" position="popper" :side-offset="6">
          <SelectViewport>
            <SelectItem v-for="o in items()" :key="o.value" :value="o.value" class="select__item">
              <SelectItemText>{{ o.label }}</SelectItemText>
              <SelectItemIndicator><Check :size="16" aria-hidden="true" /></SelectItemIndicator>
            </SelectItem>
          </SelectViewport>
        </SelectContent>
      </SelectPortal>
    </SelectRoot>
  </div>
</template>

<style>
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.field__label {
  font-size: var(--fs-13);
  font-weight: 700;
  color: var(--c-muted);
}
.select {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  min-height: 48px;
  padding: 0 10px 0 var(--sp-12);
  border: 1px solid var(--c-line-strong); /* taste-skill-ignore 입력 컨트롤 */
  border-radius: var(--r-md);
  background: var(--c-surface);
  font-size: var(--fs-16);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--t-fast);
}
.select > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.select:hover,
.select[data-state='open'] {
  border-color: var(--c-brand);
}
.select__menu {
  z-index: 60;
  min-width: var(--reka-select-trigger-width);
  max-height: 300px;
  overflow: auto;
  padding: var(--sp-4);
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
  box-shadow: var(--shadow-pop); /* taste-skill-ignore 떠 있는 층·포커스 링 */
}
.select__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-8);
  min-height: var(--tap);
  padding: 0 var(--sp-12);
  border-radius: var(--r-sm);
  outline: none;
  cursor: pointer;
}
.select__item[data-highlighted] {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
.select__item[data-state='checked'] {
  font-weight: 700;
}
</style>
