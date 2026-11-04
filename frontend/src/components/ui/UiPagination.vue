<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'

// 페이지 버튼. 백엔드 목록 응답 {page, size, total}을 그대로 받는다.
const props = defineProps({
  total: { type: Number, required: true },
  size: { type: Number, default: 10 },
})
const page = defineModel({ type: Number, default: 1 })
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.size)))
</script>

<template>
  <nav v-if="pages > 1" class="pager" aria-label="페이지">
    <button type="button" class="pager__btn" aria-label="이전 페이지" :disabled="page <= 1" @click="page--"><ChevronLeft :size="18" aria-hidden="true" /></button>
    <button
      v-for="p in pages"
      :key="p"
      type="button"
      class="pager__btn num"
      :class="{ 'is-on': p === page }"
      :aria-current="p === page ? 'page' : undefined"
      @click="page = p"
    >
      {{ p }}
    </button>
    <button type="button" class="pager__btn" aria-label="다음 페이지" :disabled="page >= pages" @click="page++"><ChevronRight :size="18" aria-hidden="true" /></button>
  </nav>
</template>

<style scoped>
.pager {
  display: flex;
  justify-content: center;
  gap: 4px;
}
.pager__btn {
  display: grid;
  place-items: center;
  min-width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: var(--r-md);
  background: none;
  color: var(--c-ink-2);
  cursor: pointer;
}
.pager__btn:hover:not(:disabled) {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
.pager__btn.is-on {
  background: var(--c-ink);
  color: var(--c-on-dark);
  font-weight: 700;
}
.pager__btn:disabled {
  opacity: 0.35;
  cursor: default;
}
</style>
