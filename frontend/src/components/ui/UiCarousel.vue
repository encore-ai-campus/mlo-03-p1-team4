<script setup>
import { ref } from 'vue'
import { useScroll } from '@vueuse/core'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { scrollBehavior } from '@/utils/motion'

// 가로로 넘기는 목록. 자동 재생 없음, CSS 스크롤 스냅 + 이전·다음 버튼.
defineProps({ label: { type: String, required: true } })
const track = ref(null)
const { arrivedState } = useScroll(track)

function page(dir) {
  const el = track.value
  if (!el) return
  el.scrollBy({ left: dir * el.clientWidth * 0.85, behavior: scrollBehavior() })
}
</script>

<template>
  <section class="carousel" :aria-label="label" aria-roledescription="carousel">
    <div ref="track" class="carousel__track" tabindex="0">
      <slot />
    </div>
    <div class="carousel__nav">
      <button type="button" class="carousel__btn" aria-label="이전" :disabled="arrivedState.left" @click="page(-1)">
        <ChevronLeft :size="20" aria-hidden="true" />
      </button>
      <button type="button" class="carousel__btn" aria-label="다음" :disabled="arrivedState.right" @click="page(1)">
        <ChevronRight :size="20" aria-hidden="true" />
      </button>
    </div>
  </section>
</template>

<style scoped>
.carousel {
  position: relative;
}
.carousel__track {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(280px, 1fr);
  gap: var(--sp-16);
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-padding-inline: var(--sp-4);
  padding: var(--sp-4) var(--sp-4) var(--sp-12);
  scrollbar-width: thin;
}
@media (min-width: 1024px) {
  .carousel__track {
    grid-auto-columns: calc((100% - 2 * var(--sp-16)) / 3);
  }
}
.carousel__track > :deep(*) {
  scroll-snap-align: start;
}
.carousel__nav {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-8);
}
.carousel__btn {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: 50%;
  background: var(--c-fill);
  cursor: pointer;
  transition: background-color var(--t-fast);
}
.carousel__btn:hover:not(:disabled) {
  background: var(--c-line-strong);
}
.carousel__btn:disabled {
  opacity: 0.4;
  cursor: default;
}
</style>
