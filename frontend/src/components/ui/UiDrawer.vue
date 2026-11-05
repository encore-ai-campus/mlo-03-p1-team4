<script setup>
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, DialogRoot, DialogTitle, DialogTrigger } from 'reka-ui'
import { X } from '@lucide/vue'

// 화면 옆(또는 아래)에서 열리는 패널. 모바일 메뉴·모바일 필터에 쓴다.
defineProps({
  title: { type: String, required: true },
  side: { type: String, default: 'right' }, // right | left | bottom
})
const open = defineModel('open', { type: Boolean, default: false })
</script>

<template>
  <DialogRoot v-model:open="open">
    <DialogTrigger v-if="$slots.trigger" as-child>
      <slot name="trigger" />
    </DialogTrigger>
    <DialogPortal>
      <DialogOverlay class="overlay" />
      <DialogContent class="drawer" :class="`drawer--${side}`" :aria-describedby="undefined">
        <div class="drawer__head">
          <DialogTitle class="drawer__title">{{ title }}</DialogTitle>
          <DialogClose class="drawer__close" aria-label="닫기"><X :size="22" aria-hidden="true" /></DialogClose>
        </div>
        <div class="drawer__body"><slot /></div>
      </DialogContent>
    </DialogPortal>
  </DialogRoot>
</template>

<style>
.drawer {
  position: fixed;
  z-index: 51;
  display: flex;
  flex-direction: column;
  background: var(--c-surface);
  box-shadow: var(--shadow-pop); /* taste-skill-ignore 떠 있는 층·포커스 링 */
}
.drawer--right,
.drawer--left {
  top: 0;
  bottom: 0;
  width: min(86vw, 360px);
}
.drawer--right {
  right: 0;
  animation: drawer-right var(--t-base) var(--ease-drawer);
}
.drawer--left {
  left: 0;
  animation: drawer-left var(--t-base) var(--ease-drawer);
}
.drawer--bottom {
  left: 0;
  right: 0;
  bottom: 0;
  max-height: 85vh;
  border-radius: var(--r-lg) var(--r-lg) 0 0;
  animation: drawer-bottom var(--t-base) var(--ease-drawer);
}
.drawer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-12) var(--sp-12) var(--sp-12) var(--sp-24);
}
.drawer__title {
  font-size: var(--fs-20);
  font-weight: 800;
}
.drawer__close {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: var(--r-md);
  background: none;
  cursor: pointer;
}
.drawer__close:hover {
  background: var(--c-brand-soft);
}
.drawer__body {
  flex: 1;
  overflow: auto;
  overscroll-behavior: contain;
  padding: var(--sp-16) var(--sp-24) var(--sp-24);
}
/* 닫힘은 다른 이름의 키프레임이어야 reka가 끝날 때까지 기다린다(이름이 같으면 바로 사라짐) */
.drawer--right[data-state='closed'] {
  animation: drawer-right-out var(--t-fast) var(--ease-out);
}
.drawer--left[data-state='closed'] {
  animation: drawer-left-out var(--t-fast) var(--ease-out);
}
.drawer--bottom[data-state='closed'] {
  animation: drawer-bottom-out var(--t-fast) var(--ease-out);
}
@keyframes drawer-right {
  from {
    transform: translateX(100%);
  }
}
@keyframes drawer-left {
  from {
    transform: translateX(-100%);
  }
}
@keyframes drawer-bottom {
  from {
    transform: translateY(100%);
  }
}
@keyframes drawer-right-out {
  to {
    transform: translateX(100%);
  }
}
@keyframes drawer-left-out {
  to {
    transform: translateX(-100%);
  }
}
@keyframes drawer-bottom-out {
  to {
    transform: translateY(100%);
  }
}
@media (prefers-reduced-motion: reduce) {
  @keyframes drawer-right {
    from {
      opacity: 0;
    }
  }
  @keyframes drawer-left {
    from {
      opacity: 0;
    }
  }
  @keyframes drawer-bottom {
    from {
      opacity: 0;
    }
  }
  @keyframes drawer-right-out {
    to {
      opacity: 0;
    }
  }
  @keyframes drawer-left-out {
    to {
      opacity: 0;
    }
  }
  @keyframes drawer-bottom-out {
    to {
      opacity: 0;
    }
  }
}
</style>
