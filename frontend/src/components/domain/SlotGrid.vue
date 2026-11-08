<script setup>
import { toast } from 'vue-sonner'
import UiTooltip from '@/components/ui/UiTooltip.vue'
import { hourLabel } from '@/utils/date'

// 1시간 칸 표. 이어진 최대 4칸. 지난 칸도 예약 가능하고 마감만 막는다.
// v-model = 고른 시 배열 (예: [13, 14])
// 11-07 팀 피드백: 최소 이용시간(min)이 있으면 처음 고를 때 min칸을 한 번에 잡고, 그다음부터 1칸씩 늘린다.
// 줄여서 min 미만이 되면 막고 안내한다. 마우스로 누른 채 좌우로 끌면 칸을 이어서 고른다.
const props = defineProps({
  slots: { type: Array, required: true }, // [{ hour, taken, past }]
  columns: { type: Number, default: 14 },
  label: { type: String, required: true },
  max: { type: Number, default: 4 },
  min: { type: Number, default: 1 },
  disabled: { type: Boolean, default: false },
})
const selected = defineModel({ type: Array, default: () => [] })
const emit = defineEmits(['select'])

const minCount = () => Math.min(Math.max(props.min, 1), props.max)
const isFree = (h) => props.slots.some((s) => s.hour === h && !s.taken)
const range = (from, to) => Array.from({ length: to - from + 1 }, (_, i) => from + i)
const minMessage = () => `이 공간은 최소 이용시간이 ${minCount()}시간이라 ${minCount()}시간 미만은 예약할 수 없어요`

// h를 포함하는 최소 길이 묶음: h에서 시작하는 것을 먼저, 안 되면 한 칸씩 앞으로 당겨 찾는다.
function startBlock(h) {
  const n = minCount()
  for (let offset = 0; offset < n; offset += 1) {
    const block = range(h - offset, h - offset + n - 1)
    if (block.every(isFree)) return block
  }
  return null
}

function commit(next, h) {
  selected.value = next
  emit('select', h)
}

function toggle(h) {
  if (props.disabled) return
  const s = selected.value
  const lo = Math.min(...s)
  const hi = Math.max(...s)
  if (s.includes(h)) {
    if (h === lo || h === hi) {
      const next = s.filter((x) => x !== h)
      if (next.length && next.length < minCount()) {
        toast(minMessage())
        return
      }
      return commit(next, h)
    }
    const block = startBlock(h)
    return block ? commit(block, h) : toast(minMessage())
  }
  if (s.length && (h === hi + 1 || h === lo - 1)) {
    if (s.length >= props.max) {
      toast(`한 번에 최대 ${props.max}시간까지 예약할 수 있어요`)
      return
    }
    return commit([...s, h].sort((a, b) => a - b), h)
  }
  const block = startBlock(h)
  if (!block) {
    toast(minMessage())
    return
  }
  commit(block, h)
}

// 마우스 끌어서 고르기: 누른 칸을 기준으로 지나간 칸까지 이어서 고른다(마감 칸을 만나면 그 앞에서 멈춤).
let drag = null
function hourAt(event) {
  const el = document.elementFromPoint?.(event.clientX, event.clientY)?.closest?.('[data-hour]')
  return el ? Number(el.dataset.hour) : null
}
function onPointerDown(event, h) {
  if (props.disabled || event.pointerType !== 'mouse' || event.button !== 0) return
  drag = { anchor: h, moved: false, scroller: event.currentTarget.closest('.slots')?.parentElement }
}
function onPointerMove(event) {
  if (!drag) return
  const h = hourAt(event)
  if (h === null || (h === drag.anchor && !drag.moved)) return
  drag.moved = true
  const dir = h >= drag.anchor ? 1 : -1
  const n = Math.min(Math.max(Math.abs(h - drag.anchor) + 1, minCount()), props.max)
  const hours = []
  for (let i = 0; i < n; i += 1) {
    const x = drag.anchor + dir * i
    if (!isFree(x)) break
    hours.push(x)
  }
  if (hours.length < minCount()) return
  const next = hours.sort((a, b) => a - b)
  if (next.join() !== selected.value.join()) commit(next, h)
  // 가로로 넘치는 칸 줄은 끝에 닿으면 그쪽으로 조금씩 넘긴다.
  const box = drag.scroller?.getBoundingClientRect?.()
  if (box && drag.scroller.scrollWidth > drag.scroller.clientWidth) {
    if (event.clientX > box.right - 32) drag.scroller.scrollLeft += 16
    else if (event.clientX < box.left + 32) drag.scroller.scrollLeft -= 16
  }
}
function onPointerUp() {
  if (!drag) return
  const moved = drag.moved
  drag = null
  if (!moved) return
  // 끌기가 끝난 칸에서 이어지는 click 한 번만 무시한다(다른 칸에서 끝나 click이 안 오면 바로 풀림).
  suppressClick = true
  setTimeout(() => (suppressClick = false), 0)
}
let suppressClick = false
function onClick(h) {
  if (suppressClick) {
    suppressClick = false
    return
  }
  toggle(h)
}
</script>

<template>
  <ul class="slots" :style="{ '--cols': columns }" :aria-label="label" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointerleave="onPointerUp">
    <li v-for="s in slots" :key="s.hour" :data-hour="s.hour">
      <UiTooltip v-if="s.taken" :text="`${hourLabel(s.hour)} 칸은 이미 예약됐어요`">
        <button type="button" class="slot is-off" aria-disabled="true" :aria-label="`${hourLabel(s.hour)} 마감`">
          <span class="slot__h num">{{ s.hour }}시</span>
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
        @pointerdown="onPointerDown($event, s.hour)"
        @click="onClick(s.hour)"
      >
        <span class="slot__h num">{{ s.hour }}시</span>
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
  user-select: none; /* 끌어서 고를 때 글자가 선택되지 않게 */
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
  white-space: nowrap; /* '10시'가 좁은 칸에서 두 줄로 나뉘지 않게 */
}
.slot__s {
  font-size: 11px;
  line-height: 1.2;
}
</style>
