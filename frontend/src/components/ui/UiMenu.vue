<script setup>
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuTrigger } from 'reka-ui'

// 동작 메뉴 (헤더 사용자 메뉴 등). items: [{ label, onSelect }]
defineProps({ items: { type: Array, required: true } })
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger as-child>
      <slot />
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent class="menu" align="end" :side-offset="6">
        <DropdownMenuItem v-for="item in items" :key="item.label" class="menu__item" @select="item.onSelect">
          {{ item.label }}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>

<style>
.menu {
  z-index: 60;
  min-width: 180px;
  padding: var(--sp-4);
  border: 1px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
  box-shadow: var(--shadow-pop); /* taste-skill-ignore 떠 있는 층·포커스 링 */
}
.menu__item {
  display: flex;
  align-items: center;
  min-height: var(--tap);
  padding: 0 var(--sp-12);
  border-radius: var(--r-sm);
  outline: none;
  cursor: pointer;
}
.menu__item[data-highlighted] {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
</style>
