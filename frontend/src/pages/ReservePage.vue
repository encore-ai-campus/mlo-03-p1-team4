<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { CircleCheck } from '@lucide/vue'
import SplitLayout from '@/components/layout/SplitLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import RoomArt from '@/components/domain/RoomArt.vue'
import SlotGrid from '@/components/domain/SlotGrid.vue'
import { createReservation } from '@/api/reservationsApi'
import { getVenue, getSlots } from '@/api/venuesApi'
import { useAuth } from '@/composables/useAuth'
import { useEventLogger } from '@/composables/useEventLogger'
import { dateLabel, rangeLabel, won, dayOffset, nowInSeoul } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const { token } = useAuth()
const { log } = useEventLogger()
const venue = ref(null)
const result = ref(null)
const slots = ref([])
const selected = ref([])
const loadError = ref('')
const conflict = ref('')
const mine = ref(false)
const paying = ref(false)
const people = ref(String(route.query.people ?? 1))
const form = reactive({ method: 'card', agree: false })
const errors = reactive({})
const date = computed(() => String(route.query.date ?? ''))
const total = computed(() => (venue.value?.price_per_hour ?? 0) * selected.value.length)
const peopleOptions = computed(() => Array.from({ length: venue.value?.capacity_max ?? 0 }, (_, n) => ({ value: String(n + 1), label: `${n + 1}명` })))
const validSelection = computed(() => selected.value.length >= (venue.value?.min_hours ?? 1) && selected.value.length <= 4 && selected.value.every((h, i) => (!i || h === selected.value[i - 1] + 1) && slots.value.some((s) => s.hour === h && !s.taken)))
const isPast = computed(() => { const now = nowInSeoul(); return date.value < now.date || (date.value === now.date && selected.value.length && selected.value.at(-1) + 1 <= now.hour) })
const payMethods = [{ value: 'card', label: '카드결제' }, { value: 'transfer', label: '계좌이체' }, { value: 'phone', label: '휴대폰' }]
let request = 0
async function load() {
  const current = ++request
  venue.value = null; result.value = null; loadError.value = ''; conflict.value = ''; mine.value = false
  const id = Number(route.query.venue), start = Number(route.query.start), count = Number(route.query.hours), headcount = Number(route.query.people)
  if (!Number.isInteger(id) || id < 1 || !Number.isFinite(dayOffset(date.value)) || Math.abs(dayOffset(date.value)) > 365 || !Number.isInteger(start) || start < 9 || !Number.isInteger(count) || count < 1 || count > 4 || start + count > 23 || !Number.isInteger(headcount) || headcount < 1) {
    loadError.value = '날짜·시간·인원 선택을 다시 확인해 주세요.'; return
  }
  try {
    const [detail, available] = await Promise.all([getVenue(id), getSlots(id, date.value)])
    if (current !== request) return
    venue.value = detail; slots.value = available; people.value = String(headcount)
    if (count < detail.min_hours || headcount > detail.capacity_max || start < detail.open_hour || start + count > detail.close_hour) { loadError.value = '공간의 최소 이용시간·영업시간·인원을 확인해 주세요.'; return }
    selected.value = Array.from({ length: count }, (_, i) => start + i)
    if (!validSelection.value) { selected.value = []; conflict.value = '선택한 시간 중 마감된 칸이 있어요. 시간을 다시 골라 주세요.' }
  } catch (e) { if (current === request) loadError.value = e.message }
}
watch([() => route.query.venue, () => route.query.date], load, { immediate: true })
watch(people, (value) => { if (venue.value && !result.value) router.replace({ query: { ...route.query, people: value } }) })
watch(() => form.agree, () => delete errors.agree)
function updateSelection(hours) {
  selected.value = hours
  if (hours.length) router.replace({ query: { ...route.query, start: hours[0], hours: hours.length, people: people.value } })
}
async function pay() {
  if (paying.value || !validSelection.value) return
  if (!form.agree) { errors.agree = '이용 규칙과 환불 규정에 동의해야 결제할 수 있어요.'; return }
  paying.value = true
  log('reservation_start', { venue_id: venue.value.venue_id, date: date.value, start_hour: selected.value[0], hours: selected.value.length })
  try {
    result.value = await createReservation({ venue_id: venue.value.venue_id, date: date.value, start_hour: selected.value[0], hours: selected.value.length, headcount: Number(people.value), method: form.method }, token.value)
    toast.success('모의 결제를 마쳤어요.')
    window.scrollTo({ top: 0 })
  } catch (e) {
    if (e.code === 'SLOT_TAKEN') {
      const closed = new Set(e.detail?.slots ?? [])
      slots.value = slots.value.map((s) => ({ ...s, taken: s.taken || closed.has(s.hour) }))
      selected.value = []; mine.value = Boolean(e.detail?.mine)
      conflict.value = mine.value ? '이미 내 예약과 겹치는 시간이에요. 내 예약을 확인해 주세요.' : '다른 분이 먼저 결제한 시간이 있어요.'
      toast.error(conflict.value)
    } else { toast.error(e.message ?? '결제하지 못했어요. 다시 시도해 주세요.') }
  } finally { paying.value = false }
}
</script>

<template>
  <div class="container page">
    <section v-if="loadError" class="state">
      <h1>예약 정보를 확인해 주세요</h1><p role="alert">{{ loadError }}</p>
      <BaseButton to="/search" variant="secondary">시간 다시 고르기</BaseButton>
    </section>
    <div v-else-if="!venue" aria-busy="true">
      <UiSkeleton width="30%" height="36px" /><div class="sk"><UiSkeleton height="420px" /><UiSkeleton height="320px" /></div>
    </div>
    <section v-else-if="result" class="state state--done" aria-labelledby="done-title">
      <CircleCheck :size="56" class="state__icon" aria-hidden="true" />
      <h1 id="done-title">{{ result.status === 'completed' ? '이용 완료로 저장됐어요' : '예약이 확정됐어요' }}</h1>
      <p>{{ venue.name }}<br /><span class="num">{{ dateLabel(result.date) }} {{ result.start_hour }}:00–{{ result.end_hour }}:00</span></p>
      <p v-if="result.status === 'completed'">지난 시간의 예약이라 이용 완료로 저장했어요. 바로 후기를 쓸 수 있어요.</p>
      <dl class="receipt">
        <div><dt>예약 번호</dt><dd class="num">{{ result.reservation_id }}</dd></div>
        <div><dt>인원</dt><dd class="num">{{ result.headcount }}명</dd></div>
        <div><dt>결제 금액</dt><dd class="num">{{ won(result.total_price) }}</dd></div>
      </dl>
      <div class="state__actions">
        <BaseButton v-if="result.status === 'completed'" :to="`/me?tab=completed&review=${result.reservation_id}`">바로 후기 쓰기</BaseButton>
        <BaseButton to="/me" :variant="result.status === 'completed' ? 'secondary' : 'primary'">내 예약 보기</BaseButton>
        <BaseButton to="/search" variant="secondary">다른 공간 찾기</BaseButton>
      </div>
    </section>
    <template v-else>
      <header class="head"><h1>예약 확인 · 결제</h1><p>결제 전에는 시간이 확보되지 않아요.</p></header>
      <SplitLayout ratio="3fr 2fr" sticky-end>
        <template #start>
          <form class="form" @submit.prevent="pay">
            <fieldset class="group" :disabled="paying">
              <legend>이용 정보</legend>
              <p class="num">{{ dateLabel(date) }} · 최소 {{ venue.min_hours }}시간, 최대 4시간</p>
              <p v-if="conflict" role="alert">{{ conflict }}</p>
              <RouterLink v-if="mine" to="/me">내 예약 확인하기</RouterLink>
              <SlotGrid :model-value="selected" :slots="slots" :columns="5" label="결제할 시간 칸" @update:model-value="updateSelection" />
              <p v-if="!validSelection" class="err">최소 {{ venue.min_hours }}시간의 빈 칸을 이어서 골라 주세요.</p>
              <UiSelect v-model="people" label="인원" :options="peopleOptions" />
              <p v-if="isPast" class="note">지난 시간이에요. 결제하면 이용 완료로 저장되어 바로 후기를 쓸 수 있어요.</p>
            </fieldset>
            <fieldset class="group" :disabled="paying">
              <legend>결제 수단</legend>
              <div class="pays" role="radiogroup" aria-label="결제 수단">
                <label v-for="m in payMethods" :key="m.value" class="pay" :class="{ 'is-on': form.method === m.value }">
                  <input v-model="form.method" type="radio" name="method" :value="m.value" /><span>{{ m.label }}</span><small>모의 결제</small>
                </label>
              </div>
              <p class="note">실제 돈은 나가지 않아요. 결제 버튼을 누르면 예약과 결제가 함께 완료돼요.</p>
            </fieldset>
            <div class="agree">
              <label><input v-model="form.agree" type="checkbox" :aria-invalid="Boolean(errors.agree)" /><span>이용 규칙과 취소 · 환불 규정을 확인했어요</span></label>
              <p class="note">이용 시작 전 취소 시 전액 환불돼요. 지난 시간의 예약은 취소할 수 없어요.</p>
              <p v-if="errors.agree" class="err" role="alert">{{ errors.agree }}</p>
            </div>
            <p class="sum__total num"><span>결제 금액</span><strong>{{ won(total) }}</strong></p>
            <BaseButton type="submit" size="lg" class="submit" :loading="paying" :disabled="!validSelection">{{ won(total) }} 결제하고 확정</BaseButton>
          </form>
        </template>
        <template #end>
          <aside class="sum" aria-label="예약 요약">
            <div class="sum__room"><span class="sum__thumb"><RoomArt :image="venue.image" :category="venue.category" /></span><div><span class="sum__type">{{ venue.category.name }}</span><strong>{{ venue.name }}</strong><span>{{ venue.region.sido }} {{ venue.region.sigungu }}</span></div></div>
            <dl class="sum__list">
              <div><dt>날짜</dt><dd class="num">{{ dateLabel(date) }}</dd></div>
              <div><dt>시간</dt><dd class="num">{{ selected.length ? rangeLabel(selected) : '다시 선택해 주세요' }}</dd></div>
              <div><dt>인원</dt><dd class="num">{{ people }}명</dd></div>
              <div><dt>금액</dt><dd class="num">{{ won(venue.price_per_hour) }} × {{ selected.length }}시간</dd></div>
            </dl>
            <RouterLink :to="`/venues/${venue.venue_id}`" class="sum__back">날짜 바꾸기</RouterLink>
          </aside>
        </template>
      </SplitLayout>
    </template>
  </div>
</template>

<style scoped>
.page {
  padding-block: var(--sp-24) var(--sp-64);
}
.sk {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: var(--sp-32);
  margin-top: var(--sp-24);
}
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-12);
  margin-bottom: var(--sp-24);
}
.head h1 {
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 900;
}
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-24);
}
.group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
  margin: 0;
  padding: var(--sp-24);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.group legend {
  float: left;
  width: 100%;
  margin-bottom: var(--sp-4);
  font-size: var(--fs-20);
  font-weight: 800;
}
.err {
  margin-top: 6px;
  color: var(--c-danger);
  font-size: var(--fs-13);
}
.pays {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-8);
}
.pay {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: var(--sp-8);
  align-items: center;
  min-height: 64px;
  padding: var(--sp-12) var(--sp-16);
  border: 1.5px solid var(--c-line-strong);
  border-radius: var(--r-md);
  cursor: pointer;
  transition: border-color var(--t-fast);
}
.pay input {
  grid-row: span 2;
  width: 20px;
  height: 20px;
  accent-color: var(--c-brand);
}
.pay span {
  font-weight: 700;
}
.pay small {
  color: var(--c-subtle);
  font-size: var(--fs-12);
}
.pay.is-on {
  border-color: var(--c-brand);
  background: var(--c-brand-soft);
}
.pay:has(:focus-visible) {
  outline: 2px solid var(--c-brand);
  outline-offset: 2px;
}
.note {
  color: var(--c-subtle);
  font-size: var(--fs-13);
}
.agree label {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
  min-height: var(--tap);
  font-weight: 700;
  cursor: pointer;
}
.agree input {
  flex: none;
  width: 22px;
  height: 22px;
  accent-color: var(--c-brand);
}
.submit {
  width: 100%;
}
.sum {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
  padding: var(--sp-24);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.sum__room {
  display: flex;
  gap: var(--sp-12);
  align-items: center;
}
.sum__room > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sum__thumb {
  flex: none;
  width: 96px;
  border-radius: var(--r-md);
  overflow: hidden;
}
.sum__type {
  font-size: var(--fs-12);
  font-weight: 700;
  color: var(--c-brand-ink);
}
.sum__room span:last-child {
  color: var(--c-muted);
  font-size: var(--fs-15);
}
.sum__list,
.receipt {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
  margin: 0;
}
.sum__list div,
.receipt div {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-12);
}
.sum__list dt,
.receipt dt {
  color: var(--c-subtle);
}
.sum__list dd,
.receipt dd {
  margin: 0;
  font-weight: 700;
}
.sum__total {
  display: flex;
  justify-content: space-between;
  margin-top: var(--sp-8);
  padding: var(--sp-12);
  border-radius: var(--r-sm);
  background: var(--c-fill);
  font-size: var(--fs-20);
}
.sum__total strong {
  font-weight: 900;
}
.sum__back {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
  font-weight: 500;
}
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-16);
  max-width: 480px;
  margin: var(--sp-48) auto;
  text-align: center;
}
.state h1 {
  font-size: var(--fs-25);
  font-weight: 900;
}
.state p {
  color: var(--c-muted);
  line-height: 1.7;
}
.state__icon {
  color: var(--c-success);
  animation: pop var(--t-enter) var(--ease-out);
}
.state__icon--off {
  color: var(--c-subtle);
}
.receipt {
  width: 100%;
  padding: var(--sp-16) var(--sp-24);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.state__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--sp-8);
}
/* 결제 완료: 드문 순간이라 조금 크게 튀어도 된다 */
@keyframes pop {
  from {
    transform: scale(0.97);
    opacity: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  @keyframes pop {
    from {
      opacity: 0;
    }
  }
}
</style>

<style scoped>
@media (max-width: 767px) {
  .submit { position: static; }
  .sk { grid-template-columns: 1fr; }
}
</style>
