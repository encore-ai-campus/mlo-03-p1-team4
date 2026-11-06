<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { refDebounced } from '@vueuse/core'
import { SlidersHorizontal } from '@lucide/vue'
import SidebarLayout from '@/components/layout/SidebarLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiDrawer from '@/components/ui/UiDrawer.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import DateStrip from '@/components/domain/DateStrip.vue'
import RoomArt from '@/components/domain/RoomArt.vue'
import SearchFilters from '@/components/domain/SearchFilters.vue'
import SlotGrid from '@/components/domain/SlotGrid.vue'
import { getCategories, getRegions } from '@/api/catalogApi'
import { getFacilities, getVenue, searchVenues } from '@/api/venuesApi'
import { useBooking } from '@/composables/useBooking'
import { useEventLogger } from '@/composables/useEventLogger'
import { dateLabel, nextDays, rangeLabel, todayISO, dayOffset, won } from '@/utils/date'

const route = useRoute()
const router = useRouter()
const { log } = useEventLogger()
const { book, booking } = useBooking()

// 필터는 주소에 그대로 남겨 공유·뒤로 가기가 되게 한다
const q0 = route.query
const filters = ref({
  category: q0.category ?? 'all',
  sido: q0.sido ?? '전국',
  sigungu: q0.sigungu ?? '전체',
  people: q0.people ?? '1',
  q: q0.q ?? '',
  facilities: q0.facilities ? String(q0.facilities).split(',') : [],
  now: q0.now === '1',
})
const offset = ref(Math.abs(dayOffset(q0.date)) <= 365 ? Math.max(-365, Math.min(352, dayOffset(q0.date))) : 0)
const days = computed(() => nextDays(Math.min(14, 366 - offset.value), offset.value))
const date = ref(Math.abs(dayOffset(q0.date)) <= 365 ? q0.date : todayISO())
function shiftDates(delta) { offset.value = Math.max(-365, Math.min(365, offset.value + delta)); date.value = days.value[0].iso }

const categories = ref([])
const regions = ref([])
const districts = ref([])
const facilities = ref([])
const loadError = ref('')
const items = ref([])
const loading = ref(true)
const drawerOpen = ref(false)
const minHours = ref(1)
const checkingSelection = ref(false)
const sel = ref({ venueId: null, hours: [] })

const debouncedQ = refDebounced(computed(() => filters.value.q), 300)
const params = computed(() => ({ ...filters.value, category: filters.value.category === 'all' ? undefined : filters.value.category, sido: filters.value.sido === '전국' ? undefined : filters.value.sido, sigungu: filters.value.sigungu === '전체' ? undefined : filters.value.sigungu, facilities: filters.value.facilities.join(','), q: debouncedQ.value, date: date.value }))

// 조건이 빠르게 바뀌면 늦게 도착한 예전 응답이 새 결과를 덮지 않도록, 마지막 요청의 응답만 반영한다
const PAGE_SIZE = 10
const page = ref(1)
const total = ref(0)
const loadingMore = ref(false)
let seq = 0
async function load() {
  const my = ++seq
  loading.value = true
  page.value = 1
  let res
  try { res = await searchVenues({ ...params.value, page: 1, size: PAGE_SIZE }); loadError.value = '' } catch (e) { if (my === seq) { loadError.value = e.message; loading.value = false }; return }
  if (my !== seq) return
  items.value = res.items
  total.value = res.total
  loading.value = false
}
async function loadMore() {
  const my = seq
  loadingMore.value = true
  let res
  try { res = await searchVenues({ ...params.value, page: page.value + 1, size: PAGE_SIZE }) } catch (e) { if (my === seq) { loadError.value = e.message; loadingMore.value = false }; return }
  loadingMore.value = false
  if (my !== seq) return
  page.value += 1
  items.value = [...items.value, ...res.items]
}
const isToday = computed(() => date.value === todayISO())
function showTomorrow() {
  filters.value = { ...filters.value, now: false }
  date.value = nextDays(2)[1].iso; offset.value = 0
}

watch(
  params,
  (p) => {
    router.replace({
      query: { category: p.category, sido: p.sido, sigungu: p.sigungu, people: p.people, date: p.date, q: p.q || undefined, facilities: p.facilities || undefined, now: p.now ? '1' : undefined },
    })
    log('search', { ...p })
    load()
  },
  { deep: true },
)
watch(date, () => (sel.value = { venueId: null, hours: [] }))
watch(() => filters.value.now, (enabled) => {
  if (enabled) { date.value = todayISO(); offset.value = 0 }
})

let districtRequest = 0
watch(() => filters.value.sido, async (sido) => {
  const current = ++districtRequest
  filters.value.sigungu = '전체'
  try {
    const response = sido !== '전국' ? await getRegions(sido) : []
    if (current === districtRequest) districts.value = response
  } catch (e) { loadError.value = e.message }
})
onMounted(async () => {
  try {
    const [types, provinces, amenities] = await Promise.all([getCategories(), getRegions(), getFacilities()])
    categories.value = types
    regions.value = provinces
    facilities.value = amenities
    districts.value = filters.value.sido !== '전국' ? await getRegions(filters.value.sido) : []
    await load()
  } catch (e) {
    loadError.value = e.message
    loading.value = false
  }
})

const activeCount = computed(() => {
  const f = filters.value
  return (f.category !== 'all') + (f.sigungu !== '전체') + (f.people !== '1') + f.facilities.length + Boolean(f.q) + f.now
})
const selectedRoom = computed(() => items.value.find((r) => r.venue_id === sel.value.venueId))
const summary = computed(() => {
  if (!selectedRoom.value || !sel.value.hours.length) return null
  const n = sel.value.hours.length
  const short = checkingSelection.value || n < minHours.value
  return { room: selectedRoom.value, time: rangeLabel(sel.value.hours), n, total: won(selectedRoom.value.price_per_hour * n), short }
})

function selectionFor(venueId) {
  return sel.value.venueId === venueId ? sel.value.hours : []
}
async function setSelection(venueId, hours) {
  const changed = venueId !== sel.value.venueId
  sel.value = { venueId: hours.length ? venueId : null, hours }
  if (!changed || !hours.length) return
  checkingSelection.value = true
  try { const detail = await getVenue(venueId); if (sel.value.venueId === venueId) minHours.value = detail.min_hours }
  catch (e) { loadError.value = e.message; sel.value = { venueId: null, hours: [] } }
  finally { checkingSelection.value = false }
}

function submit() {
  if (!summary.value || summary.value.short) return
  book({ venue_id: sel.value.venueId, date: date.value, hours: sel.value.hours, people: filters.value.people })
}
function resetFilters() {
  filters.value = { category: 'all', sido: '전국', sigungu: '전체', people: '1', q: '', facilities: [], now: false }
}
</script>

<template>
  <div class="container page">
    <header class="page__head">
      <h1 class="page__title">빈 시간 찾기</h1>
      <p class="page__lead">날짜를 고르고, 원하는 공간의 1시간 칸을 이어서 누르세요. 마감 칸은 고를 수 없어요.</p>
    </header>

    <DateStrip v-model="date" :days="days" :offset="offset" :min-offset="-365" :max-offset="365" label="이용 날짜" @shift="shiftDates" class="page__dates" />

    <SidebarLayout label="검색 조건">
      <template #sidebar>
        <SearchFilters v-if="categories.length" v-model="filters" :categories="categories" :regions="regions" :districts="districts" :facilities="facilities" />
      </template>
      <template #mobile-trigger>
        <UiDrawer v-model:open="drawerOpen" title="검색 조건" side="bottom">
          <template #trigger>
            <BaseButton variant="secondary" class="filter-btn">
              <SlidersHorizontal :size="18" aria-hidden="true" />조건 바꾸기<span v-if="activeCount" class="filter-btn__count num">{{ activeCount }}</span>
            </BaseButton>
          </template>
          <SearchFilters v-if="categories.length" v-model="filters" compact :categories="categories" :regions="regions" :districts="districts" :facilities="facilities" />
          <BaseButton class="drawer-done" @click="drawerOpen = false">{{ items.length }}곳 보기</BaseButton>
        </UiDrawer>
      </template>

      <div class="results-head">
        <h2 class="results-head__title">{{ dateLabel(date) }} <span class="results-head__count num">{{ loading ? '찾는 중…' : `${total}곳` }}</span></h2>
        <ul class="legend" aria-label="칸 표시">
          <li><span class="legend__box" />예약 가능</li>
          <li><span class="legend__box legend__box--on" />선택</li>
          <li><span class="legend__box legend__box--off" />마감</li>
        </ul>
      </div>

      <p v-if="loadError" role="alert">{{ loadError }} <BaseButton variant="secondary" @click="load">다시 시도</BaseButton></p>
      <div v-if="loading" class="results" aria-busy="true">
        <div v-for="i in 3" :key="i" class="result" aria-hidden="true">
          <div class="result__info"><UiSkeleton width="96px" height="62px" /><div class="sk-lines"><UiSkeleton width="80%" /><UiSkeleton width="60%" height="20px" /><UiSkeleton width="50%" /></div></div>
          <UiSkeleton height="48px" />
        </div>
      </div>

      <div v-else-if="items.length" class="results">
        <article v-for="r in items" :key="r.venue_id" class="result" :class="{ 'is-selected': sel.venueId === r.venue_id }">
          <div class="result__info">
            <span class="result__thumb"><RoomArt :image="r.image" :category="r.category" /></span>
            <div class="result__text">
              <h3 class="result__name"><RouterLink :to="`/venues/${r.venue_id}`">{{ r.name }}</RouterLink></h3>
              <span class="result__type">{{ r.category.name }} · {{ r.region.sido }} {{ r.region.sigungu }}</span>
              <span class="result__meta num">최대 {{ r.capacity_max }}명 · {{ won(r.price_per_hour) }}/시간<template v-if="r.min_hours > 1"> · 최소 {{ r.min_hours }}시간</template></span>
            </div>
          </div>
          <div class="result__slots">
            <SlotGrid
              :slots="r.slots"
              :model-value="selectionFor(r.venue_id)"
              :label="`${r.name} 시간 칸`"
              @update:model-value="(h) => setSelection(r.venue_id, h)"
              @select="(h) => log('select_slot', { venue_id: r.venue_id, hour: h })"
            />
          </div>
        </article>
        <div v-if="items.length < total" class="more">
          <BaseButton variant="secondary" :loading="loadingMore" @click="loadMore">더 보기 <span class="num">({{ items.length }}/{{ total }})</span></BaseButton>
        </div>
      </div>

      <div v-else class="empty">
        <p class="empty__title">이 조건에 맞는 공간이 없어요</p>
        <p v-if="isToday">오늘 남은 시간이 없을 수 있어요. 내일 칸을 보거나 조건을 넓혀 보세요.</p>
        <p v-else>지역이나 유형을 넓히거나 다른 날짜를 골라 보세요.</p>
        <div class="empty__actions">
          <BaseButton v-if="isToday" variant="secondary" @click="showTomorrow">내일 빈 시간 보기</BaseButton>
          <BaseButton variant="secondary" @click="resetFilters">조건 처음으로</BaseButton>
        </div>
      </div>
    </SidebarLayout>

    <!-- 하단 스티키 요약 바 -->
    <div class="sumbar" aria-live="polite">
      <template v-if="summary">
        <p class="sumbar__text">
          <strong>{{ summary.room.name }}</strong>
          <span class="num">{{ dateLabel(date) }} · {{ summary.time }} ({{ summary.n }}시간)</span>
          <span v-if="summary.short" class="sumbar__warn">이 공간은 최소 {{ minHours }}시간부터 예약할 수 있어요</span>
          <strong v-else class="sumbar__total num">{{ summary.total }}</strong>
        </p>
        <BaseButton size="lg" :loading="booking" :disabled="summary.short" @click="submit">예약 신청하기</BaseButton>
      </template>
      <template v-else>
        <p class="sumbar__hint">원하는 공간의 시간 칸을 눌러 고르세요.</p>
        <BaseButton size="lg" disabled>예약 신청하기</BaseButton>
      </template>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-top: var(--sp-32);
}
.page__title {
  font-size: var(--fs-32);
  font-weight: 900;
}
.page__lead {
  margin-top: 4px;
  color: var(--c-muted);
}
.page__dates {
  margin-block: var(--sp-24);
}
.filter-btn {
  width: 100%;
  margin-bottom: var(--sp-16);
}
.filter-btn__count {
  display: grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  border-radius: 999px;
  background: var(--c-brand);
  color: var(--c-on-dark);
  font-size: var(--fs-12);
}
.drawer-done {
  width: 100%;
  margin-top: var(--sp-16);
}
.results-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-8) var(--sp-16);
  margin-bottom: var(--sp-12);
}
.results-head__title {
  font-size: var(--fs-20);
  font-weight: 800;
}
.results-head__count {
  margin-left: 4px;
  font-size: var(--fs-15);
  font-weight: 500;
  color: var(--c-subtle);
}
.legend {
  display: flex;
  gap: var(--sp-16);
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--fs-13);
  color: var(--c-muted);
}
.legend li {
  display: flex;
  align-items: center;
  gap: 6px;
}
.legend__box {
  width: 16px;
  height: 16px;
  border: 1px solid var(--c-line-strong);
  border-radius: 4px;
  background: var(--c-surface);
}
.legend__box--on {
  background: var(--c-brand);
  border-color: var(--c-brand);
}
.legend__box--off {
  background: var(--c-slot-taken);
  border-color: var(--c-slot-taken);
}
.results {
  display: flex;
  flex-direction: column;
  gap: var(--sp-12);
}
.result {
  display: grid;
  gap: var(--sp-12);
  padding: var(--sp-16);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  transition: background-color var(--t-fast);
}
.result.is-selected {
  outline: 2px solid var(--c-brand);
  outline-offset: -2px;
}
.result__info {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
}
.result__thumb {
  flex: none;
  width: 96px;
  border-radius: var(--r-sm);
  overflow: hidden;
}
.result__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.result__type {
  font-size: var(--fs-13);
  color: var(--c-muted);
}
.result__name {
  font-size: var(--fs-16);
  font-weight: 800;
}
.result__name a {
  color: var(--c-ink);
  text-decoration: none;
}
.result__name a:hover {
  color: var(--c-brand-ink);
  text-decoration: underline;
}
.result__meta {
  font-size: var(--fs-13);
  color: var(--c-muted);
}
.result__slots {
  overflow-x: auto;
  padding-bottom: 4px;
}
.result__slots > * {
  min-width: 640px;
}
@media (min-width: 1280px) {
  .result {
    grid-template-columns: 250px minmax(0, 1fr);
    align-items: center;
  }
}
.sk-lines {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-8);
  padding: var(--sp-32) var(--sp-24);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-lg);
  color: var(--c-muted);
}
.empty__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-8);
  margin-top: var(--sp-4);
}
.more {
  display: flex;
  justify-content: center;
  padding-top: var(--sp-8);
}
.empty__title {
  font-size: var(--fs-20);
  font-weight: 800;
  color: var(--c-ink);
}
.sumbar {
  position: sticky;
  bottom: var(--sp-12);
  z-index: 30;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-12) var(--sp-16);
  margin-top: var(--sp-24);
  padding: var(--sp-12) var(--sp-16) var(--sp-12) var(--sp-24);
  border-radius: var(--r-lg);
  background: var(--c-ink);
  color: var(--c-on-dark);
  --btn-bg: var(--c-on-dark);
  --btn-ink: var(--c-brand);
  --btn-bg-hover: var(--c-surface);
  box-shadow: var(--shadow-pop); /* taste-skill-ignore 떠 있는 층·포커스 링 */
}
.sumbar__text {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px var(--sp-16);
  color: var(--c-on-dark-2);
}
.sumbar__text strong {
  color: var(--c-on-dark);
}
.sumbar__total {
  font-size: var(--fs-20);
  font-weight: 900;
}
.sumbar__warn {
  color: var(--c-danger-on-dark);
  font-size: var(--fs-13);
}
.sumbar__hint {
  color: var(--c-on-dark-2);
}
</style>
