<script setup>
// 오늘부터 14일 날짜 띠. 좁은 화면에서는 가로로 넘기고(스크롤 스냅), 빈 칸 없는 날은 회색으로 막는다.
defineProps({
  days: { type: Array, required: true }, // [{ iso, month, day, weekday, dow, isToday, available? }]
  label: { type: String, default: '날짜' },
  offset: { type: Number, default: 0 },
  minOffset: { type: Number, default: -365 },
  maxOffset: { type: Number, default: 365 },
})
defineEmits(['shift'])
const model = defineModel({ type: String })
</script>

<template>
  <div class="date-strip">
  <div class="date-nav">
    <button type="button" :disabled="offset <= minOffset" @click="$emit('shift', -14)">이전 14일</button>
    <span>{{ days[0]?.month }}월 {{ days[0]?.day }}일 – {{ days.at(-1)?.month }}월 {{ days.at(-1)?.day }}일</span>
    <button type="button" :disabled="offset + days.length > maxOffset" @click="$emit('shift', 14)">다음 14일</button>
  </div>
  <div class="dates" role="radiogroup" :aria-label="label">
    <button
      v-for="d in days"
      :key="d.iso"
      type="button"
      role="radio"
      class="date"
      :class="{ 'is-on': model === d.iso, 'is-full': d.available === false, 'is-sun': d.dow === 0, 'is-sat': d.dow === 6 }"
      :aria-checked="model === d.iso"
      :aria-disabled="d.available === false || undefined"
      :aria-label="`${d.month}월 ${d.day}일 ${d.weekday}요일${d.available === false ? ' 빈 칸 없음' : ''}`"
      @click="d.available !== false && (model = d.iso)"
    >
      <span class="date__wd">{{ d.isToday ? '오늘' : d.weekday }}</span>
      <span class="date__d num">{{ d.day === 1 || d.isToday ? `${d.month}.${d.day}` : d.day }}</span>
    </button>
  </div>
  </div>
</template>

<style scoped>
.date-strip { min-width: 0; }
.date-nav { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-8); font-size: var(--fs-13); }
.date-nav button { min-height: var(--tap); padding: 0 var(--sp-8); border: 0; background: transparent; color: var(--c-brand-ink); cursor: pointer; }
.date-nav button:disabled { color: var(--c-muted); cursor: not-allowed; }
.dates {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(52px, 1fr);
  gap: 6px;
  overflow-x: auto;
  scroll-snap-type: x proximity;
  padding-bottom: 4px;
  scrollbar-width: thin;
}
.date {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 56px;
  border: 1px solid var(--c-line-strong);
  border-radius: var(--r-md);
  background: var(--c-surface);
  scroll-snap-align: start;
  cursor: pointer;
  transition: border-color var(--t-fast), background-color var(--t-fast);
}
.date:hover:not(.is-full) {
  border-color: var(--c-brand);
}
.date__wd {
  font-size: var(--fs-12);
  color: var(--c-muted);
}
.date__d {
  font-size: var(--fs-16);
  font-weight: 700;
}
.is-sun .date__wd {
  color: var(--c-danger);
}
.is-sat .date__wd {
  color: var(--c-saturday);
}
.date.is-on {
  background: var(--c-brand);
  border-color: var(--c-brand);
  color: var(--c-on-dark);
}
.date.is-on .date__wd {
  color: var(--c-on-brand-2);
}
.date.is-full {
  background: var(--c-slot-taken);
  border-color: var(--c-slot-taken);
  color: var(--c-disabled-ink);
  cursor: not-allowed;
}
</style>
