<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from 'vue-sonner'
import { Check, Clock, Heart, Star, Users, Wallet } from '@lucide/vue'
import SplitLayout from '@/components/layout/SplitLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiAccordion from '@/components/ui/UiAccordion.vue'
import UiCarousel from '@/components/ui/UiCarousel.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import UiTooltip from '@/components/ui/UiTooltip.vue'
import DateStrip from '@/components/domain/DateStrip.vue'
import ReviewCard from '@/components/domain/ReviewCard.vue'
import RoomArt from '@/components/domain/RoomArt.vue'
import SlotGrid from '@/components/domain/SlotGrid.vue'
import { getAvailableDates, getVenue, getSlots } from '@/api/venuesApi'
import { getVenueReviews } from '@/api/reviewsApi'
import { useBooking } from '@/composables/useBooking'
import { useEventLogger } from '@/composables/useEventLogger'
import { dateLabel, rangeLabel, won, nextDays, dayOffset, todayISO } from '@/utils/date'
import { scrollBehavior } from '@/utils/motion'
import { parseHours } from '@/utils/slots'


const route = useRoute()
const { log } = useEventLogger()
const { book, booking } = useBooking()

const room = ref(null)
const notFound = ref(false)
const roomError = ref('')
const reviews = ref([])
const reviewError = ref('')
const days = ref([])
const date = ref('')
const slots = ref([])
const slotsLoading = ref(false)
const hours = ref([])
const people = ref('2')
const saved = ref(false)
const offset = ref(0)
const minOffset = ref(-365)
const maxOffset = ref(365)
const slotError = ref('')
let initializing = false
async function loadDates() {
  const response = await getAvailableDates(room.value.venue_id, offset.value, 14)
  minOffset.value = dayOffset(response.min_date); maxOffset.value = dayOffset(response.max_date)
  days.value = response.dates.map((d) => ({ ...nextDays(1, dayOffset(d.date))[0], available: d.bookable, free: d.free }))
}
async function shiftDates(delta) {
  offset.value = Math.max(minOffset.value, Math.min(maxOffset.value, offset.value + delta))
  try { await loadDates(); date.value = days.value[0]?.iso ?? ''; } catch (e) { slotError.value = e.message }
}

async function loadRoom(id) {
  initializing = true
  room.value = null
  notFound.value = false
  roomError.value = ''
  reviews.value = []
  reviewError.value = ''
  try {
    room.value = await getVenue(id)
  } catch (e) {
    if (e.status === 404) notFound.value = true
    else roomError.value = e.message ?? '공간 정보를 불러오지 못했어요.'
    initializing = false
    return
  }
  log('view_venue', { venue_id: Number(id) })
  people.value = '2'
  if (room.value.capacity_max < 2) people.value = '1'
  offset.value = Math.abs(dayOffset(route.query.date)) <= 365 ? dayOffset(route.query.date) : 0
  try {
    await loadDates()
    date.value = route.query.date && days.value.some((d) => d.iso === route.query.date) ? route.query.date : (days.value.find((d) => d.available) ?? days.value[0])?.iso ?? todayISO()
    await loadSlots()
    const query = route.query
    const count = Number(query.hours)
    const restored = query.start !== undefined && Number.isInteger(count) ? Array.from({ length: Math.max(0, Math.min(count, 4)) }, (_, i) => Number(query.start) + i) : parseHours(query.hours)
    if (restored.length >= room.value.min_hours && restored.length <= 4 && restored.every((h, i) => (!i || h === restored[i - 1] + 1) && slots.value.some((slot) => slot.hour === h && !slot.taken))) hours.value = restored
    if (peopleOptions.value.some((option) => option.value === String(query.people))) people.value = String(query.people)
  } catch (e) { slotError.value = e.message }
  initializing = false
  loadReviews(id)
  log('view_dates', { venue_id: Number(id) })
}
async function loadReviews(id) {
  reviewError.value = ''
  try {
    const response = await getVenueReviews(id, { page: 1, size: 10 })
    if (String(route.params.venueId) === String(id)) reviews.value = response.items
  } catch (e) {
    if (String(route.params.venueId) === String(id)) reviewError.value = e.message ?? '후기를 불러오지 못했어요.'
  }
}
let slotRequest = 0
async function loadSlots() {
  if (!room.value || !date.value) return
  const request = ++slotRequest
  slotsLoading.value = true
  hours.value = []
  try {
    const response = await getSlots(room.value.venue_id, date.value)
    if (request === slotRequest) { slots.value = response; slotError.value = '' }
  } catch (e) { if (request === slotRequest) slotError.value = e.message }
  finally { if (request === slotRequest) slotsLoading.value = false }
}
watch(() => route.params.venueId, loadRoom, { immediate: true })
watch(date, () => { if (!initializing) loadSlots() })

// 이미지: 같은 그림의 색 두 가지 (실사 사진이 없으므로)
const gallery = computed(() => (room.value ? room.value.images : []))
const peopleOptions = computed(() => {
  if (!room.value) return []
  const list = []
  for (let n = 1; n <= room.value.capacity_max; n++) list.push({ value: String(n), label: `${n}명` })
  return list
})
const avg = computed(() => Number(room.value?.rating_avg ?? 0).toFixed(1))
const summary = computed(() => {
  if (!hours.value.length) return null
  const n = hours.value.length
  return { time: rangeLabel(hours.value), n, total: won(room.value.price_per_hour * n), short: n < room.value.min_hours }
})
const sections = [
  { id: 'intro', label: '소개' },
  { id: 'facilities', label: '시설' },
  { id: 'guide', label: '이용 안내' },
  { id: 'reviews', label: '후기' },
]
const guide = computed(() =>
  room.value
    ? [
        { value: 'use', title: '이용 안내', body: `${room.value.notice ?? ''} 1시간 단위로 예약하고, 최소 ${room.value.min_hours}시간부터 가능해요. 운영 ${room.value.open_hour}:00–${room.value.close_hour}:00, 최대 ${room.value.capacity_max}명까지 들어갈 수 있어요.` },
        { value: 'refund', title: '취소 · 환불 규정', body: '이용 시작 전까지 취소하면 전액 환불돼요. 지난 시간의 예약은 취소할 수 없어요.' },
        { value: 'pay', title: '결제', body: '지금은 모의 결제만 돼요. 실제 돈은 나가지 않아요.' },
      ]
    : [],
)

function toggleSave() {
  saved.value = !saved.value
  toast(saved.value ? '찜 목록에 담았어요' : '찜 목록에서 뺐어요')
}
function submit() {
  if (!summary.value || summary.value.short) return
  book({ venue_id: room.value.venue_id, date: date.value, hours: hours.value, people: people.value })
}
// 예약 카드로 이동하고 키보드 포커스도 옮긴다(선택된 날짜 → 없으면 카드 제목). 카드가 본문 뒤에 있어 Tab으로는 멀다
function scrollToBooking() {
  const card = document.getElementById('booking')
  if (!card) return
  card.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  const target = card.querySelector('[aria-checked="true"]') ?? card.querySelector('h2')
  target?.focus({ preventScroll: true })
}
</script>

<template>
  <div v-if="roomError" class="container missing" role="alert">
    <h1>공간 정보를 불러오지 못했어요</h1>
    <p>{{ roomError }}</p>
    <BaseButton variant="secondary" @click="loadRoom(route.params.venueId)">다시 시도</BaseButton>
  </div>
  <div v-else-if="notFound" class="container missing">
    <h1>찾는 공간이 없어요</h1>
    <p>문을 닫았거나 주소가 바뀌었을 수 있어요.</p>
    <BaseButton to="/search" variant="secondary">다른 공간 찾기</BaseButton>
  </div>

  <div v-else-if="!room && !roomError" class="container page" aria-busy="true">
    <UiSkeleton width="40%" height="36px" />
    <div class="sk-split"><UiSkeleton height="360px" radius="var(--r-lg)" /><UiSkeleton height="360px" radius="var(--r-lg)" /></div>
  </div>

  <div v-else-if="room" class="container page">
    <nav class="crumbs" aria-label="현재 위치">
      <RouterLink to="/search">공간 찾기</RouterLink><span aria-hidden="true">›</span>
      <RouterLink :to="{ path: '/search', query: { sido: room.region.sido, sigungu: room.region.sigungu } }">{{ room.region.sido }} {{ room.region.sigungu }}</RouterLink><span aria-hidden="true">›</span>
      <RouterLink :to="{ path: '/search', query: { category: room.category.code } }">{{ room.category.name }}</RouterLink>
    </nav>

    <button type="button" class="skip-booking" @click="scrollToBooking">예약 카드로 바로 가기</button>

    <header class="head">
      <div>
        <h1 class="head__title">{{ room.name }}</h1>
        <p class="head__meta">{{ room.category.name }} · 최대 {{ room.capacity_max }}명 · {{ room.region.sido }} {{ room.region.sigungu }}<template v-if="room.is_new"> · 새로 연 공간</template></p>
        <p class="head__meta"><Star :size="16" class="star" fill="currentColor" aria-hidden="true" /><strong class="num">{{ avg }}</strong> 후기 {{ room.review_count }}개</p>
      </div>
      <button type="button" class="save" :class="{ 'is-on': saved }" :aria-pressed="saved" :aria-label="saved ? '찜 해제' : '찜하기'" @click="toggleSave"><Heart :size="22" aria-hidden="true" /></button>
    </header>

    <SplitLayout ratio="3fr 2fr" sticky-end>
      <template #start>
        <UiCarousel label="공간 이미지">
          <div v-for="(g, i) in gallery" :key="i" class="shot"><RoomArt :image="g" /></div>
        </UiCarousel>

        <ul class="glance" aria-label="한눈에 보기">
          <li><Users :size="20" aria-hidden="true" /><span>인원</span><strong>최대 {{ room.capacity_max }}명</strong></li>
          <li><Wallet :size="20" aria-hidden="true" /><span>1시간</span><strong class="num">{{ won(room.price_per_hour) }}</strong></li>
          <li><Clock :size="20" aria-hidden="true" /><span>운영</span><strong class="num">{{ room.open_hour }}–{{ room.close_hour }}시</strong></li>
          <li><Star :size="20" aria-hidden="true" /><span>평점</span><strong class="num">{{ avg }}</strong></li>
        </ul>

        <nav class="subnav" aria-label="이 페이지 안에서 이동">
          <a v-for="s in sections" :key="s.id" :href="`#${s.id}`" class="subnav__link">{{ s.label }}</a>
        </nav>

        <section id="intro" class="block">
          <h2>공간 소개</h2>
          <p class="block__text">{{ room.description }}</p>
        </section>

        <section id="facilities" class="block">
          <h2>시설</h2>
          <ul class="facilities">
            <li v-for="f in room.facilities" :key="f.name">
              <UiTooltip :text="f.name">
                <button type="button" class="facility"><Check :size="18" aria-hidden="true" />{{ f.name }}</button>
              </UiTooltip>
            </li>
          </ul>
        </section>

        <section id="guide" class="block">
          <h2>이용 안내</h2>
          <UiAccordion :items="guide" :default-open="['use']" />
        </section>

        <section id="reviews" class="block">
          <h2>후기 <span class="num count">{{ reviews.length }}</span></h2>
          <p v-if="reviewError" role="alert">{{ reviewError }} <BaseButton variant="secondary" @click="loadReviews(room.venue_id)">후기 다시 불러오기</BaseButton></p>
          <div v-if="reviews.length" class="reviews">
            <ReviewCard v-for="v in reviews" :key="v.review_id" :review="v" />
          </div>
          <p v-else-if="!reviewError" class="muted">아직 후기가 없어요. 이용을 마치면 내 예약에서 첫 후기를 남길 수 있어요.</p>
          <RouterLink to="/reviews" class="more">후기 전체 보기</RouterLink>
        </section>
      </template>

      <template #end>
        <section id="booking" class="booking" aria-labelledby="booking-title">
          <h2 id="booking-title" class="booking__price" tabindex="-1"><strong class="num">{{ won(room.price_per_hour) }}</strong> / 1시간</h2>
          <div class="booking__group">
            <span class="booking__label">예약 가능 날짜 <span class="muted">· 과거·미래 365일</span></span>
            <DateStrip v-model="date" :days="days" :offset="offset" :min-offset="minOffset" :max-offset="maxOffset" label="예약 날짜" @shift="shiftDates" />
          </div>
          <div class="booking__group">
            <span class="booking__label">{{ dateLabel(date) }} 시간 <span class="muted">· 최소 {{ room.min_hours }}시간, 최대 4시간</span></span>
            <UiSkeleton v-if="slotsLoading" height="156px" />
            <SlotGrid v-else v-model="hours" :slots="slots" :columns="5" label="시간 칸" @select="(h) => log('select_slot', { venue_id: room.venue_id, hour: h })" />
          </div>
          <p v-if="slotError" role="alert">{{ slotError }} <BaseButton variant="secondary" @click="loadRoom(route.params.venueId)">다시 시도</BaseButton></p>
          <UiSelect v-model="people" label="인원" :options="peopleOptions" />
          <div class="booking__sum" aria-live="polite">
            <template v-if="summary">
              <p class="num"><span>{{ summary.time }}</span><span>{{ won(room.price_per_hour) }} × {{ summary.n }}시간</span></p>
              <p v-if="summary.short" class="warn">최소 {{ room.min_hours }}시간부터 예약할 수 있어요. 칸을 이어서 더 골라 주세요.</p>
              <p v-else class="booking__total num"><span>합계</span><strong>{{ summary.total }}</strong></p>
            </template>
            <p v-else class="muted">시간 칸을 골라 주세요.</p>
          </div>
          <BaseButton size="lg" class="booking__btn" :loading="booking" :disabled="!summary || summary.short" @click="submit">예약 신청하기</BaseButton>
          <p class="muted small">다음 화면에서 결제하면 예약이 확정돼요. 결제 전에는 시간이 확보되지 않아요.</p>
        </section>
      </template>
    </SplitLayout>

    <!-- 모바일 하단 스티키 바: 예약 카드로 이동 -->
    <div class="mbar">
      <p><strong class="num">{{ won(room.price_per_hour) }}</strong> / 1시간</p>
      <BaseButton variant="secondary" @click="scrollToBooking">시간 고르기</BaseButton>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-top: var(--sp-24);
}
.missing {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-12);
  padding-block: var(--sp-64);
}
.sk-split {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: var(--sp-32);
  margin-top: var(--sp-24);
}
.crumbs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-8);
  font-size: var(--fs-13);
  color: var(--c-subtle);
}
.crumbs a {
  color: var(--c-muted);
  text-decoration: none;
}
.crumbs a:hover {
  color: var(--c-brand-ink);
  text-decoration: underline;
}
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-16);
  margin-top: var(--sp-12);
}
.skip-booking {
  position: absolute;
  left: var(--sp-16);
  top: -100px;
  z-index: 50;
  padding: var(--sp-12) var(--sp-16);
  border: 0;
  border-radius: var(--r-md);
  background: var(--c-ink);
  color: var(--c-on-dark);
  font-weight: 700;
  cursor: pointer;
}
.skip-booking:focus {
  top: calc(var(--header-h) + var(--sp-8));
}
.nowrap {
  white-space: nowrap;
}
.head__title {
  text-wrap: balance;
  margin-top: var(--sp-8);
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 900;
}
.head__meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: var(--fs-15);
  color: var(--c-muted);
}
.star {
  color: var(--c-star);
}
.head__meta strong {
  color: var(--c-ink);
}
.save {
  flex: none;
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: 50%;
  background: var(--c-surface);
  color: var(--c-muted);
  cursor: pointer;
  transition: transform var(--t-fast);
}
.save:active {
  transform: scale(0.95);
}
.save.is-on {
  color: var(--c-heart);
  border-color: currentColor;
}
.save.is-on :deep(svg) {
  fill: currentColor;
}
.promo {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-8) var(--sp-16);
  margin-block: var(--sp-16) var(--sp-24);
  padding: var(--sp-16) var(--sp-24);
  border-radius: var(--r-lg);
  background: var(--c-brand-soft);
  border: 0;
  color: var(--c-brand-ink);
  font-weight: 700;
}
.promo__tag {
  padding: 3px 10px;
  border-radius: 6px;
  background: var(--c-ink);
  color: var(--c-on-dark);
  font-size: var(--fs-12);
}
.shot {
  border-radius: var(--r-lg);
  overflow: hidden;
}
.glance {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-8);
  margin: var(--sp-16) 0 0;
  padding: 0;
  list-style: none;
}
@media (min-width: 640px) {
  .glance {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.glance li {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  column-gap: var(--sp-8);
  align-items: center;
  padding: var(--sp-12) var(--sp-16);
  border: 0;
  border-radius: var(--r-md);
  background: var(--c-surface);
}
.glance li :first-child {
  grid-row: span 2;
  color: var(--c-brand-ink);
}
.glance span {
  font-size: var(--fs-12);
  color: var(--c-subtle);
}
.glance strong {
  font-size: var(--fs-15);
}
.subnav {
  position: sticky;
  top: var(--header-h);
  z-index: 5;
  display: flex;
  gap: var(--sp-4);
  margin-top: var(--sp-24);
  padding: var(--sp-4) 0;
  border: 0;
  background: var(--c-paper);
  overflow-x: auto;
}
.subnav__link {
  flex: none;
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
  padding: 0 var(--sp-16);
  border-radius: var(--r-sm);
  color: var(--c-muted);
  font-weight: 500;
  text-decoration: none;
}
.subnav__link:hover {
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
.block {
  margin-top: var(--sp-32);
  scroll-margin-top: calc(var(--header-h) + 64px);
}
.block h2 {
  margin-bottom: var(--sp-12);
  font-size: var(--fs-20);
  font-weight: 800;
}
.block__text {
  line-height: 1.8;
  color: var(--c-ink-2);
}
.count {
  color: var(--c-brand);
}
.facilities {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--sp-8);
  margin: 0;
  padding: 0;
  list-style: none;
}
.facility {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: var(--sp-8);
  width: 100%;
  min-height: 56px;
  padding: var(--sp-8) var(--sp-12);
  border: 0;
  border-radius: var(--r-md);
  background: var(--c-surface);
  font-weight: 700;
  text-align: left;
  cursor: help;
}
.facility :first-child {
  grid-row: span 2;
  align-self: center;
  color: var(--c-brand);
}
.facility__note {
  font-size: var(--fs-12);
  font-weight: 400;
  color: var(--c-subtle);
}
.reviews {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
}
.reviews > * + * {
  padding-top: var(--sp-16);

}
.more {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
  margin-top: var(--sp-8);
  font-weight: 500;
  text-decoration: none;
}
.muted {
  color: var(--c-subtle);
}
.small {
  font-size: var(--fs-13);
}
.booking {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
  padding: var(--sp-24);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
  scroll-margin-top: calc(var(--header-h) + 16px);
}
.booking__price {
  font-size: var(--fs-16);
  font-weight: 500;
  color: var(--c-subtle);
}
.booking__price strong {
  font-size: var(--fs-25);
  font-weight: 900;
  color: var(--c-ink);
}
.booking__group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-8);
}
.booking__label {
  font-size: var(--fs-13);
  font-weight: 700;
  color: var(--c-muted);
}
.booking__label .muted {
  font-weight: 400;
}
.booking__sum {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--sp-12);
  border-radius: var(--r-sm);
  background: var(--c-fill);
}
.booking__sum p {
  display: flex;
  justify-content: space-between;
  gap: var(--sp-8);
}
.booking__total {
  font-size: var(--fs-20);
}
.booking__total strong {
  font-weight: 900;
}
.warn {
  color: var(--c-danger);
  font-size: var(--fs-13);
}
.booking__btn {
  width: 100%;
}
.mbar {
  position: sticky;
  bottom: 0;
  z-index: 30;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-12);
  margin: var(--sp-24) calc(-1 * var(--sp-16)) 0;
  padding: var(--sp-12) var(--sp-16);
  border: 0;
  background: var(--c-surface);
}
.mbar strong {
  font-size: var(--fs-20);
  font-weight: 900;
}
@media (min-width: 768px) {
  .mbar {
    display: none;
  }
}
</style>
