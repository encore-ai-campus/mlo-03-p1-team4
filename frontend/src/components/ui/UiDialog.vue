<script setup>
import { DialogClose, DialogContent, DialogDescription, DialogOverlay, DialogPortal, DialogRoot, DialogTitle, DialogTrigger } from 'reka-ui'
import { X } from '@lucide/vue'

// 확인·입력용 가운데 창. 포커스는 창 안에 갇히고 Esc로 닫힌다.
// #trigger: 여는 버튼(as-child), 기본 슬롯: 내용, #actions: 아래 버튼들
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
const open = defineModel('open', { type: Boolean, default: false })
defineEmits(['open-auto-focus'])
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogTrigger v-if="$slots.trigger" as-child>
      <slot name="trigger" />
    </DialogTrigger>
    <DialogPortal>
      <DialogOverlay class="overlay" />
      <DialogContent class="dialog" @open-auto-focus="$emit('open-auto-focus', $event)">
        <DialogTitle class="dialog__title">{{ title }}</DialogTitle>
        <DialogDescription v-if="description" class="dialog__desc">{{ description }}</DialogDescription>
        <div class="dialog__body"><slot /></div>
        <div v-if="$slots.actions" class="dialog__actions"><slot name="actions" /></div>
        <DialogClose class="dialog__close" aria-label="닫기"><X :size="20" aria-hidden="true" /></DialogClose>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

<style>
/* 포털로 body에 붙으므로 scoped가 아닌 고유 클래스로 둔다. 배경 .overlay는 base.css */
.dialog {
  position: fixed;
  left: 50%;
  top: 50%;
  z-index: 51;
  width: min(92vw, 480px);
  max-height: 85vh;
  overflow: auto;
  overscroll-behavior: contain;
  transform: translate(-50%, -50%);
  padding: var(--sp-24);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  box-shadow: var(--shadow-pop); /* taste-skill-ignore 떠 있는 층·포커스 링 */
  animation: dialog-in var(--t-base) var(--ease-out);
}
.dialog[data-state='closed'] {
  animation: dialog-out var(--t-fast) var(--ease-out);
}
.dialog__title {
  padding-right: var(--sp-32);
  font-size: var(--fs-20);
  font-weight: 800;
}
.dialog__desc {
  margin-top: var(--sp-8);
  color: var(--c-muted);
}
.dialog__body {
  margin-top: var(--sp-16);
}
.dialog__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--sp-8);
  margin-top: var(--sp-24);
}
.dialog__close {
  position: absolute;
  right: var(--sp-12);
  top: var(--sp-12);
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: var(--r-md);
  background: none;
  color: var(--c-muted);
  cursor: pointer;
}
.dialog__close:hover {
  background: var(--c-brand-soft);
}
@keyframes dialog-in {
  from {
    opacity: 0;
    transform: translate(-50%, calc(-50% + 8px)) scale(0.98);
  }
}
@keyframes dialog-out {
  to {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.98);
  }
}
@media (prefers-reduced-motion: reduce) {
  @keyframes dialog-in {
    from {
      opacity: 0;
    }
  }
  @keyframes dialog-out {
    to {
      opacity: 0;
    }
  }
}
</style>
