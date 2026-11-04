<script setup>
import { TooltipArrow, TooltipContent, TooltipPortal, TooltipRoot, TooltipTrigger } from 'reka-ui'

// 보조 설명만. 터치에서는 보이지 않으니 꼭 필요한 정보는 화면 글자로도 둔다.
defineProps({ text: { type: String, required: true } })
</script>

<template>
  <TooltipRoot>
    <TooltipTrigger as-child>
      <slot />
    </TooltipTrigger>
    <TooltipPortal>
      <TooltipContent class="tip" :side-offset="6">
        {{ text }}
        <TooltipArrow class="tip__arrow" :width="10" :height="5" />
      </TooltipContent>
    </TooltipPortal>
  </TooltipRoot>
</template>

<style>
.tip {
  z-index: 70;
  max-width: 260px;
  padding: var(--sp-8) var(--sp-12);
  border-radius: var(--r-sm);
  background: var(--c-ink);
  color: var(--c-on-dark);
  font-size: var(--fs-13);
  line-height: 1.5;
  transform-origin: var(--reka-tooltip-content-transform-origin);
}
.tip[data-state='delayed-open'] {
  animation: tip-in var(--t-tip) var(--ease-out);
}
@keyframes tip-in {
  from {
    opacity: 0;
    transform: scale(0.97);
  }
}
@media (prefers-reduced-motion: reduce) {
  @keyframes tip-in {
    from {
      opacity: 0;
    }
  }
}
.tip__arrow {
  fill: var(--c-ink);
}
</style>
