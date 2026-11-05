<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiTooltip from '@/components/ui/UiTooltip.vue'
import { useEventLogger } from '@/composables/useEventLogger'
import { formatHours } from '@/utils/slots'

// 히어로의 '오늘 남은 칸' 패널: 이 서비스의 핵심 단위인 1시간 칸을 첫 화면에서 바로 눌러 보게 한다.
// 연속 최대 4칸, 마감만 막고 지난 칸도 선택 가능. 오늘이 끝났으면 내일 칸을 받는다(catalogApi.getTodaySlots).
// slots = { venue_id, name, price_per_hour, date, day: '오늘'|'내일', slots: [{ hour, taken, past }] }
const props = defineProps({ slots: { type: Object, required: true } })
const selected = ref([])
const router = useRouter()
const { log } = useEventLogger()
const pad = (h) => `${String(h).padStart(2, '0')}:00`

function toggle(h) {
  const s = selected.value
  if (s.includes(h)) {
    const min = Math.min(...s)
    const max = Math.max(...s)
    selected.value = h === min || h === max ? s.filter((x) => x !== h) : [h]
  } else if (s.length && (h === Math.max(...s) + 1 || h === Math.min(...s) - 1)) {
    if (s.length >= 4) {
      toast('한 번에 최대 4시간까지 예약할 수 있어요')
      return
    }
    selected.value = [...s, h]
  } else {
    selected.value = [h]
  }
  log('select_slot', { venue_id: props.slots.venue_id, hour: h })
}

const summary = computed(() => {
  if (!selected.value.length) return null
  const min = Math.min(...selected.value)
  const max = Math.max(...selected.value)
  const hours = selected.value.length
  return { time: `${pad(min)}–${pad(max + 1)}`, hours, total: (props.slots.price_per_hour * hours).toLocaleString('ko-KR') }
})

// 고른 날짜·칸을 들고 상세로 간다 (상세가 주소의 date·hours로 선택을 되살림)
function goReserve() {
  router.push({ name: 'venue', params: { venueId: props.slots.venue_id }, query: { date: props.slots.date, hours: formatHours(selected.value) } })
}
</script>

<template>
  <section class="strip" aria-labelledby="strip-title">
    <div class="strip__head">
      <h2 id="strip-title" class="strip__title">{{ slots.day }} 남은 칸</h2>
      <p class="strip__room">{{ slots.name }}</p>
    </div>

    <ul class="grid" :aria-label="`${slots.date_label} 1시간 단위 시간 칸`">
      <li v-for="{ hour: h, taken, past } in slots.slots" :key="h">
        <UiTooltip v-if="taken" :text="`${pad(h)} 칸은 이미 예약됐어요`">
          <button type="button" class="slot is-taken" aria-disabled="true" :aria-label="`${pad(h)} 마감`">
            <span class="slot__h num">{{ h }}시</span>
            <span class="slot__s">마감</span>
          </button>
        </UiTooltip>
        <button
          v-else
          type="button"
          class="slot"
          :class="{ 'is-on': selected.includes(h), 'is-past': past }"
          :aria-pressed="selected.includes(h)"
          :aria-label="`${pad(h)}부터 1시간`"
          @click="toggle(h)"
        >
          <span class="slot__h num">{{ h }}시</span>
          <span class="slot__s">{{ selected.includes(h) ? '선택' : past ? '지남' : '가능' }}</span>
        </button>
      </li>
    </ul>

    <div class="strip__foot" aria-live="polite">
      <p v-if="summary" class="strip__sum num"><strong>{{ summary.time }}</strong> · {{ summary.hours }}시간 · {{ summary.total }}원</p>
      <p v-else class="strip__hint">칸을 눌러 고르세요 · 최대 4시간</p>
      <BaseButton :disabled="!summary" @click="goReserve">이 시간으로 예약하기</BaseButton>
    </div>
  </section>
</template>

<style scoped>
.slot.is-past:not(.is-on) { background: var(--c-dark-taken); color: var(--c-on-dark-faint); }
.strip {
  display: flex;
  flex-direction: column;
  gap: var(--sp-12);
  padding: var(--sp-16) 20px;
  border-radius: var(--r-lg);
  background: var(--c-ink);
  color: var(--c-on-dark);
  --btn-bg: var(--c-on-dark);
  --btn-ink: var(--c-brand);
  --btn-bg-hover: var(--c-surface);
}
/* 제목과 공간 이름을 한 줄에 */
.strip__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 2px var(--sp-12);
}
.strip__title {
  font-size: var(--fs-20);
  font-weight: 800;
}
.strip__room {
  font-size: var(--fs-13);
  color: var(--c-on-dark-2);
}
.grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 6px;
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
  min-height: 46px;
  border: 0;
  border-radius: var(--r-sm);
  background: var(--c-dark-2);
  color: var(--c-on-dark);
  cursor: pointer;
  transition: background-color var(--t-fast), border-color var(--t-fast), transform var(--t-fast) var(--ease-out);
}
.slot:hover:not(.is-taken) {
  background: var(--c-dark-line);
}
.slot:active:not(.is-taken) {
  transform: scale(0.97); /* 한 번 예약에 여러 번 누르는 칸이라 약하게 */
}
.slot.is-on,
.slot.is-on:hover {
  background: var(--c-on-dark);
  color: var(--c-brand);
}
.slot.is-taken {
  background: var(--c-dark-taken);
  color: var(--c-on-dark-faint);
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
  color: inherit;
  opacity: 0.85;
}
.strip__foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-12);
}
.strip__sum {
  font-size: var(--fs-16);
}
.strip__hint {
  font-size: var(--fs-13);
  color: var(--c-on-dark-3);
}
</style>
