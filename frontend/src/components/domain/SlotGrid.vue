<script setup>
import { toast } from 'vue-sonner'
import UiTooltip from '@/components/ui/UiTooltip.vue'
import { hourLabel } from '@/utils/date'

// 1시간 칸 표. 이어진 최대 4칸. 지난 칸도 예약 가능하고 마감만 막는다.
// v-model = 고른 시 배열 (예: [13, 14])
const props = defineProps({
  slots: { type: Array, required: true }, // [{ hour, taken, past }]
  columns: { type: Number, default: 14 },
  label: { type: String, required: true },
  max: { type: Number, default: 4 },
  disabled: { type: Boolean, default: false },
})
const selected = defineModel({ type: Array, default: () => [] })
const emit = defineEmits(['select'])

function toggle(h) {
  if (props.disabled) return
  const s = selected.value
  const min = Math.min(...s)
  const max = Math.max(...s)
  let next
  if (s.includes(h)) next = h === min || h === max ? s.filter((x) => x !== h) : [h]
  else if (s.length && (h === max + 1 || h === min - 1)) {
    if (s.length >= props.max) {
      toast(`한 번에 최대 ${props.max}시간까지 예약할 수 있어요`)
      return
    }
    next = [...s, h].sort((a, b) => a - b)
  } else next = [h]
  selected.value = next
  emit('select', h)
}
</script>

<template>
  <ul class="slots" :style="{ '--cols': columns }" :aria-label="label">
    <li v-for="s in slots" :key="s.hour">
      <UiTooltip v-if="s.taken" :text="`${hourLabel(s.hour)} 칸은 이미 예약됐어요`">
        <button type="button" class="slot is-off" aria-disabled="true" :aria-label="`${hourLabel(s.hour)} 마감`">
          <span class="slot__h num">{{ s.hour }}</span>
          <span class="slot__s">마감</span>
        </button>
      </UiTooltip>
      <button
        v-else
        type="button"
        class="slot"
        :class="{ 'is-on': selected.includes(s.hour), 'is-past': s.past }"
        :aria-pressed="selected.includes(s.hour)"
        :disabled="disabled"
        :aria-label="`${hourLabel(s.hour)}부터 1시간`"
        @click="toggle(s.hour)"
      >
        <span class="slot__h num">{{ s.hour }}</span>
        <span class="slot__s">{{ selected.includes(s.hour) ? '선택' : s.past ? '지남' : '가능' }}</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.slots {
  display: grid;
  grid-template-columns: repeat(var(--cols), minmax(44px, 1fr));
  gap: var(--sp-8);
  margin: 0;
  padding: 0;
  list-style: none;
}
.slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 48px;
  border: 1px solid var(--c-line-strong); /* taste-skill-ignore 입력 컨트롤 */
  border-radius: var(--r-sm);
  background: var(--c-surface);
  cursor: pointer;
  transition: background-color var(--t-fast), border-color var(--t-fast), transform var(--t-fast) var(--ease-out);
}
.slot:hover:not(.is-off) {
  border-color: var(--c-brand);
  background: var(--c-brand-soft);
}
.slot:active:not(.is-off) {
  transform: scale(0.97); /* 한 번 예약에 여러 번 누르는 칸이라 약하게 */
}
.slot.is-on {
  background: var(--c-brand);
  border-color: var(--c-brand);
  color: var(--c-on-dark);
}
.slot.is-past:not(.is-on) {
  background: var(--c-paper);
}
.slot.is-on:hover {
  background: var(--c-brand-hover);
}
.slot.is-off {
  background: var(--c-slot-taken);
  border-color: var(--c-slot-taken);
  color: var(--c-subtle);
  cursor: not-allowed;
}
.slot__h {
  font-size: var(--fs-15);
  font-weight: 700;
  line-height: 1.15;
}
.slot__s {
  font-size: 11px;
  line-height: 1.2;
}
</style>
