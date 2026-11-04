<script setup>
import { AccordionContent, AccordionHeader, AccordionItem, AccordionRoot, AccordionTrigger } from 'reka-ui'
import { ChevronDown } from '@lucide/vue'

// items: [{ value, title, body }]. 여러 개를 함께 열 수 있다. 내용은 item.value 이름의 슬롯으로도 넣을 수 있다.
defineProps({
  items: { type: Array, required: true },
  defaultOpen: { type: Array, default: () => [] }, // 처음부터 열어 둘 item.value
})
</script>

<template>
  <AccordionRoot type="multiple" class="acc" :default-value="defaultOpen">
    <AccordionItem v-for="item in items" :key="item.value" :value="item.value" class="acc__item">
      <AccordionHeader as="h3" class="acc__header">
        <AccordionTrigger class="acc__trigger">
          {{ item.title }}
          <ChevronDown class="acc__chev" :size="20" aria-hidden="true" />
        </AccordionTrigger>
      </AccordionHeader>
      <AccordionContent class="acc__content">
        <div class="acc__body">
          <slot :name="item.value">{{ item.body }}</slot>
        </div>
      </AccordionContent>
    </AccordionItem>
  </AccordionRoot>
</template>

<style scoped>
.acc {
  border-top: 1px solid var(--c-line);
}
.acc__item {
  border-bottom: 1px solid var(--c-line);
}
.acc__header {
  font-size: var(--fs-16);
}
.acc__trigger {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-12);
  min-height: 56px;
  padding: 0 var(--sp-4);
  border: 0;
  background: none;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}
.acc__chev {
  flex: none;
  color: var(--c-subtle);
  transition: transform var(--t-base) var(--ease-out);
}
.acc__trigger[data-state='open'] .acc__chev {
  transform: rotate(180deg);
}
.acc__content {
  overflow: hidden;
}
.acc__content[data-state='open'] {
  animation: open var(--t-base) var(--ease-out);
}
.acc__content[data-state='closed'] {
  animation: close var(--t-fast) var(--ease-out);
}
.acc__body {
  padding: 0 var(--sp-4) var(--sp-16);
  color: var(--c-ink-2);
  line-height: 1.7;
}
@keyframes open {
  from {
    height: 0;
  }
  to {
    height: var(--reka-accordion-content-height);
  }
}
@keyframes close {
  from {
    height: var(--reka-accordion-content-height);
  }
  to {
    height: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .acc__content[data-state] {
    animation: none;
  }
  .acc__chev {
    transition: none;
  }
}
</style>
