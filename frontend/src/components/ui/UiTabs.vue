<script setup>
import { TabsContent, TabsIndicator, TabsList, TabsRoot, TabsTrigger } from 'reka-ui'

// tabs: [{ value, label, count? }]. 선택된 탭의 내용은 #panel 슬롯으로 그린다.
defineProps({
  tabs: { type: Array, required: true },
  label: { type: String, required: true },
})
const model = defineModel({ type: String })
</script>

<template>
  <TabsRoot v-model="model" class="tabs" activation-mode="automatic">
    <TabsList class="tabs__list" :aria-label="label">
      <TabsIndicator class="tabs__indicator" />
      <TabsTrigger v-for="t in tabs" :key="t.value" :value="t.value" class="tabs__trigger">
        {{ t.label }}
        <span v-if="t.count != null" class="tabs__count num">{{ t.count }}</span>
      </TabsTrigger>
    </TabsList>
    <TabsContent v-for="t in tabs" :key="t.value" :value="t.value" class="tabs__panel">
      <slot name="panel" :tab="t" />
    </TabsContent>
  </TabsRoot>
</template>

<style scoped>
.tabs__list {
  position: relative;
  display: flex;
  gap: var(--sp-4);
  overflow-x: auto;
  scroll-snap-type: x proximity;
  scrollbar-width: none;
  border-bottom: 1px solid var(--c-line);
}
.tabs__trigger {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 48px;
  padding: 0 var(--sp-16);
  border: 0;
  background: none;
  color: var(--c-muted);
  font-size: var(--fs-16);
  font-weight: 500;
  scroll-snap-align: start;
  cursor: pointer;
  transition: color var(--t-fast);
}
.tabs__trigger:hover {
  color: var(--c-brand-ink);
}
.tabs__trigger[data-state='active'] {
  color: var(--c-ink);
  font-weight: 700;
}
.tabs__count {
  font-size: var(--fs-13);
  color: var(--c-subtle);
}
/* 선택 탭으로 미끄러지는 밑줄 (마이크로 인터랙션) */
.tabs__indicator {
  position: absolute;
  bottom: -1px;
  left: 0;
  height: 3px;
  width: var(--reka-tabs-indicator-size);
  transform: translateX(var(--reka-tabs-indicator-position));
  border-radius: 3px 3px 0 0;
  background: var(--c-brand);
  transition: transform var(--t-base) var(--ease-out);
}
.tabs__panel:focus-visible {
  outline-offset: 6px;
}
@media (prefers-reduced-motion: reduce) {
  .tabs__indicator {
    transition: none;
  }
}
</style>
