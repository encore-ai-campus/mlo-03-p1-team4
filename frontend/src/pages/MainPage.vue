<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@lucide/vue'
import SplitLayout from '@/components/layout/SplitLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import UiCarousel from '@/components/ui/UiCarousel.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import RoomArt from '@/components/domain/RoomArt.vue'
import RoomCard from '@/components/domain/RoomCard.vue'
import RoomCardSkeleton from '@/components/domain/RoomCardSkeleton.vue'
import CategoryBento from '@/components/domain/CategoryBento.vue'
import SlotStrip from '@/components/domain/SlotStrip.vue'
import { useReveal } from '@/composables/useReveal'
import { useEventLogger } from '@/composables/useEventLogger'
import { nextDays, nowInSeoul } from '@/utils/date'
import * as api from '@/api/catalogApi'

const router = useRouter()
const { log } = useEventLogger()
const categories = ref([])
const regions = ref([])
const allRooms = ref([])
const newRooms = ref([])
const newLoading = ref(true)
const newError = ref('')
const todaySlots = ref(null)
const reviews = ref([])
const loadingRooms = ref(true)
const error = ref('')
const tab = ref('all')
const sort = ref('default')
let sequence = 0
async function loadRooms() {
  const id = ++sequence
  loadingRooms.value = true
  error.value = ''
  try {
    const res = await api.searchVenues({ category: tab.value, sort: sort.value, size: 12 })
    if (id === sequence) allRooms.value = res.items
  } catch (e) { if (id === sequence) error.value = e.message }
  finally { if (id === sequence) loadingRooms.value = false }
}
async function loadNewRooms() {
  newLoading.value = true
  newError.value = ''
  try { newRooms.value = (await api.getNewVenues()).items }
  catch (e) { newError.value = e.message ?? '새 공간을 불러오지 못했어요.' }
  finally { newLoading.value = false }
}
onMounted(async () => {
  await Promise.allSettled([
    api.getCategories().then((r) => { categories.value = r }),
    api.getRegions().then((r) => { regions.value = r }),
    api.getTodaySlots().then((r) => { todaySlots.value = r }),
    loadNewRooms(),
    api.getRecentReviews().then((r) => { reviews.value = r.items }),
    loadRooms(),
  ])
})
watch([tab, sort], loadRooms)
const dateOptions = nextDays(7).map((d) => ({ value: d.iso, label: `${d.isToday ? '오늘 ' : ''}${d.month}.${d.day} (${d.weekday})` }))
const form = ref({ category: 'all', region: '전국', date: dateOptions[0].value, people: '4' })
const categoryOptions = computed(() => [{ value: 'all', label: '전체 유형' }, ...categories.value.map((c) => ({ value: c.code, label: c.name }))])
const regionOptions = computed(() => ['전국', ...regions.value])
const peopleOptions = ['1', '2', '4', '6', '8', '10', '15'].map((n) => ({ value: n, label: `${n}명` }))
function submitSearch() {
  const query = { category: form.value.category, sido: form.value.region === '전국' ? undefined : form.value.region, date: form.value.date, people: form.value.people }
  log('search', query)
  router.push({ path: '/search', query })
}
const sortOptions = [{ value: 'default', label: '추천순' }, { value: 'popular', label: '인기순' }, { value: 'price', label: '낮은 가격순' }, { value: 'rating', label: '평점순' }]
const tabs = computed(() => [{ value: 'all', label: '전체' }, ...categories.value.map((c) => ({ value: c.code, label: c.name }))])
const shown = computed(() => allRooms.value)
const availableNow = computed(() => allRooms.value.filter((r) => r.slots?.some((s) => !s.taken && s.hour > nowInSeoul().hour)).length)
const emptyCategory = computed(() => categories.value.find((c) => c.code === tab.value)?.name ?? '')
const { target: reviewsTarget, visible: reviewsVisible } = useReveal()
const won = (n) => n.toLocaleString('ko-KR')
</script>

<template>
  <!-- 히어로: 정적, 주 행동 하나(빈 공간 찾기) + 이 서비스의 단위인 '1시간 칸'을 바로 눌러 보게 -->
  <section class="hero">
    <div class="container">
      <SplitLayout ratio="3fr 2fr">
        <template #start>
          <h1 class="hero__title">필요한 공간을<br />한 시간씩 빌려 쓰세요</h1>
          <p class="hero__lead">스터디룸부터 파티룸까지, 전국의 빈 시간을 유형과 지역으로 찾아요.</p>

          <form class="search" @submit.prevent="submitSearch">
            <UiSelect v-model="form.category" label="유형" :options="categoryOptions" />
            <UiSelect v-model="form.region" label="지역" :options="regionOptions" />
            <UiSelect v-model="form.date" label="날짜" :options="dateOptions" />
            <UiSelect v-model="form.people" label="인원" :options="peopleOptions" />
            <BaseButton type="submit" class="search__submit"><Search :size="18" aria-hidden="true" />빈 공간 찾기</BaseButton>
          </form>
        </template>
        <template #end>
          <SlotStrip v-if="todaySlots" :slots="todaySlots" />
        </template>
      </SplitLayout>
    </div>
  </section>

  <!-- 첫 화면(1280×650)에 히어로와 이 벤토까지 잘리지 않고 들어오게 높이를 맞춘다 -->
  <section class="section section--first container" aria-labelledby="bento-title">
    <div class="section__head section__head--row section__head--tight">
      <h2 id="bento-title" class="section__title">어떤 공간이 필요하세요?</h2>
      <RouterLink :to="{ path: '/search', query: { now: 1 } }" class="now-link">
        지금 바로 들어갈 수 있는 곳 <strong class="num">{{ availableNow }}곳</strong>
      </RouterLink>
    </div>
    <CategoryBento v-if="categories.length" :categories="categories" />
  </section>

  <section class="section container" aria-labelledby="new-title">
    <div class="section__head">
      <h2 id="new-title" class="section__title">새로 문을 연 공간</h2>
      <p class="section__sub">등록 후 14일 동안 여기에 보여요</p>
    </div>
    <UiCarousel label="새로 문을 연 공간">
      <template v-if="newRooms.length">
        <RouterLink v-for="n in newRooms" :key="n.venue_id" :to="`/venues/${n.venue_id}`" class="new-card">
          <span class="new-card__art"><RoomArt :image="n.image" :category="n.category" /></span>
          <span class="new-card__body">
            <span class="new-card__open num">{{ n.registered_on }} 오픈 · {{ n.new_days_left }}일 남음</span>
            <span class="new-card__name">{{ n.name }}</span>
            <span class="new-card__meta">{{ n.category.name }} · {{ n.region.sido }} {{ n.region.sigungu }}</span>
            <span class="new-card__price num"><strong>{{ won(n.price_per_hour) }}원</strong> / 1시간</span>
          </span>
        </RouterLink>
      </template>
      <template v-else-if="newLoading">
        <div v-for="i in 3" :key="i" class="new-card new-card--sk" aria-hidden="true">
          <UiSkeleton height="auto" radius="0" class="new-card__art-sk" />
          <span class="new-card__body"><UiSkeleton width="50%" /><UiSkeleton width="70%" height="22px" /><UiSkeleton width="40%" /></span>
        </div>
      </template>
      <p v-else-if="newError" role="alert" class="empty">{{ newError }} <BaseButton variant="secondary" @click="loadNewRooms">다시 시도</BaseButton></p>
      <p v-else class="empty">최근 14일에 등록된 새 공간이 없어요. 아래에서 다른 공간을 둘러보세요.</p>
    </UiCarousel>
  </section>

  <section class="section container" aria-labelledby="list-title">
    <div class="section__head section__head--row">
      <div>
        <h2 id="list-title" class="section__title">둘러볼 공간</h2>
        <p class="section__sub">유형과 정렬을 골라 원하는 공간을 찾아보세요</p>
      </div>
      <UiSelect v-model="sort" label="정렬" :options="sortOptions" class="sort" />
    </div>

    <UiTabs v-model="tab" :tabs="tabs" label="공간 유형">
      <template #panel>
        <div v-if="loadingRooms" class="grid" aria-busy="true">
          <RoomCardSkeleton v-for="i in 6" :key="i" />
        </div>
        <div v-else-if="error" class="empty" role="alert"><p>{{ error }}</p><BaseButton variant="secondary" @click="loadRooms">다시 시도</BaseButton></div>
        <div v-else-if="shown.length" :key="`${tab}-${sort}`" class="grid">
          <RoomCard
            v-for="(r, i) in shown"
            :key="r.venue_id"
            :room="r"
            :index="i"
            :rank="sort === 'popular' ? i + 1 : 0"
            
          />
        </div>
        <div v-else class="empty">
          <p>등록된 {{ emptyCategory }} 공간이 아직 없어요.</p>
          <BaseButton variant="secondary" @click="tab = 'all'">전체 유형 보기</BaseButton>
        </div>
      </template>
    </UiTabs>
  </section>

  <section class="section container insights">
    <div ref="reviewsTarget" class="panel reveal" :class="{ 'is-visible': reviewsVisible }" aria-labelledby="reviews-title">
      <div class="panel__head">
        <h2 id="reviews-title" class="panel__title">최근 후기</h2>
        <RouterLink to="/reviews" class="panel__more">후기 전체 보기</RouterLink>
      </div>
      <ul class="reviews">
        <li v-for="v in reviews" :key="v.review_id" class="review">
          <div class="review__meta">
            <span class="review__type">{{ categories.find((c) => c.code === v.category)?.name }}</span>
            <span class="review__stars">별점 {{ v.rating }}</span>
            <span class="review__by num">{{ v.author }} · {{ v.created_at.slice(0, 10) }}</span>
          </div>
          <p class="review__text">{{ v.content }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.hero {
  padding-block: var(--sp-32) var(--sp-32);
  background: var(--c-surface);
}
.hero__title {
  font-size: clamp(2rem, 3.6vw, 3.25rem);
  font-weight: 900;
  line-height: 1.22;
  letter-spacing: -0.03em;
}
.hero__lead {
  margin-top: var(--sp-8);
  font-size: var(--fs-15);
  color: var(--c-muted);
}
.search {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-12);
  margin-top: var(--sp-16);
  padding: var(--sp-12);
  border-radius: var(--r-lg);
  background: var(--c-paper);
}
.search__submit {
  grid-column: 1 / -1;
  min-height: 48px;
}
/* 넓은 화면: 검색칸 한 줄 */
@media (min-width: 1024px) {
  .search {
    grid-template-columns: 0.95fr 1fr 1.35fr 0.65fr auto;
  }
  .search__submit {
    grid-column: auto;
    align-self: end;
  }
}
.section {
  margin-top: var(--sp-64);
}
.section--first {
  margin-top: var(--sp-24);
}
.section__head {
  margin-bottom: var(--sp-16);
}
.section__head--tight {
  margin-bottom: var(--sp-12);
}
.now-link {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-8);
  min-height: var(--tap);
  color: var(--c-brand-ink);
  font-size: var(--fs-16);
  text-underline-offset: 4px;
  text-decoration: none;
  transition: background-color var(--t-fast);
}
.now-link:hover {
  text-decoration: underline;
}
.section__head--row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--sp-12);
}
.section__title {
  font-size: var(--fs-25);
  font-weight: 800;
}
.section > .section__title {
  margin-bottom: var(--sp-16);
}
.section__sub {
  margin-top: 4px;
  font-size: var(--fs-15);
  color: var(--c-subtle);
}
.sort {
  width: 160px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--sp-24);
  padding-top: var(--sp-24);
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-12);
  padding: var(--sp-32) 0;
  color: var(--c-muted);
}
/* NEW 카드 */
.new-card {
  display: flex;
  flex-direction: column;
  border-radius: var(--r-lg);
  background: var(--c-surface);
  color: var(--c-ink);
  text-decoration: none;
  overflow: hidden;
  transition: background-color var(--t-fast);
}
.new-card:hover {
  background: var(--c-fill);
}
.new-card__art {
  position: relative;
  display: block;
}
.new-card__art-sk {
  aspect-ratio: 400 / 260;
}
.new-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--sp-12) var(--sp-16) var(--sp-16);
}
.new-card__open {
  font-size: var(--fs-15);
  color: var(--c-muted);
}
.new-card__name {
  font-size: var(--fs-20);
  font-weight: 800;
}
.new-card__meta {
  font-size: var(--fs-13);
  color: var(--c-muted);
}
.new-card__price {
  color: var(--c-subtle);
}
.new-card__price strong {
  color: var(--c-ink);
  font-size: var(--fs-16);
  font-weight: 900;
}
/* 하단 두 패널 */
.insights {
  display: grid;
  gap: var(--sp-24);
}
.panel {
  padding: var(--sp-24);
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.panel__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-12);
}
.panel__title {
  font-size: var(--fs-20);
  font-weight: 800;
}
.panel__more {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap);
  font-size: var(--fs-15);
  font-weight: 500;
  text-decoration: none;
}
/* 스크롤 리빌: 한 번만 */
.reveal {
  opacity: 0;
  transform: translateY(16px);
  transition: opacity var(--t-enter) var(--ease-out), transform var(--t-enter) var(--ease-out);
}
.reveal.is-visible {
  opacity: 1;
  transform: none;
}
.reviews {
  margin: var(--sp-8) 0 0;
  padding: 0;
  list-style: none;
}
.review {
  padding-block: var(--sp-12);
}
.review__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-8);
  font-size: var(--fs-13);
}
.review__type {
  color: var(--c-ink);
  font-weight: 700;
}
.review__stars {
  color: var(--c-muted);
}
.review__by {
  margin-left: auto;
  color: var(--c-subtle);
}
.review__text {
  margin-top: 6px;
  font-size: var(--fs-15);
  line-height: 1.65;
  color: var(--c-ink-2);
}
</style>
