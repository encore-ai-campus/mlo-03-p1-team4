<script setup>
import { ref, watch } from 'vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import UiPagination from '@/components/ui/UiPagination.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiSkeleton from '@/components/ui/UiSkeleton.vue'
import ReviewCard from '@/components/domain/ReviewCard.vue'
import { getCategories } from '@/api/catalogApi'
import { getReviews } from '@/api/reviewsApi'

const categories = ref([])
const category = ref('')
const sort = ref('recent')
const page = ref(1)
const result = ref(null)
const loading = ref(false)
const error = ref('')
// 전체 후기 수. 0이면 유형 탭에서도 '전체 후기 보기'를 띄우지 않는다(전체 탭과 같게).
const allTotal = ref(null)
const sortOptions = [{ value: 'recent', label: '최신순' }, { value: 'high', label: '별점 높은 순' }, { value: 'low', label: '별점 낮은 순' }]
getCategories().then((items) => (categories.value = items)).catch((e) => (error.value = e.message))
let request = 0
// 탭을 바꿀 때 기존 카드를 지우지 않고 살짝 흐리게 둔 채 새 결과로 바꾼다. 빈 칸(스켈레톤)은 첫 로딩에만 보인다.
async function load() {
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const data = await getReviews({ category: category.value || undefined, sort: sort.value, page: page.value, size: 12 })
    if (current !== request) return
    result.value = data
    if (!category.value) allTotal.value = data.total
    else if (allTotal.value === null && !data.items.length) {
      const all = await getReviews({ page: 1, size: 1 })
      if (current === request) allTotal.value = all.total
    }
  } catch (e) {
    if (current === request) error.value = e.message
  } finally {
    if (current === request) loading.value = false
  }
}
watch([category, sort], () => { page.value = 1; load() })
watch(page, load)
load()
</script>

<template>
  <div class="container page">
    <header class="head"><h1>후기 모아보기</h1><p>공간을 이용한 사람들이 남긴 경험을 살펴보세요.</p></header>
    <section class="panel" aria-label="이용 후기">
      <ul class="stats" aria-label="공간 유형">
        <li><button type="button" class="stat" :aria-pressed="category === ''" @click="category = ''">전체</button></li>
        <li v-for="c in categories" :key="c.code"><button type="button" class="stat" :aria-pressed="category === c.code" @click="category = c.code">{{ c.name }}</button></li>
      </ul>
      <div class="toolbar">
        <p class="toolbar__count num" aria-live="polite">{{ result ? `후기 ${result.total}개` : '후기를 불러오는 중' }}</p>
        <div class="toolbar__sort"><UiSelect v-model="sort" label="후기 정렬" :options="sortOptions" /></div>
      </div>
      <div v-if="error" class="empty" role="alert"><p>{{ error }}</p><BaseButton variant="secondary" @click="load">다시 시도</BaseButton></div>
      <div v-else-if="!result" class="grid" aria-busy="true"><UiSkeleton v-for="i in 4" :key="i" height="180px" radius="var(--r-lg)" /></div>
      <div v-else class="results" :class="{ 'is-loading': loading }" :aria-busy="loading">
        <div v-if="!result.items.length" class="empty"><p>아직 등록된 후기가 없어요.</p><BaseButton v-if="category && allTotal > 0" variant="secondary" @click="category = ''">전체 후기 보기</BaseButton></div>
        <template v-else>
          <div class="grid"><ReviewCard v-for="review in result.items" :key="review.review_id" :review="review" show-room class="grid__card" /></div>
          <UiPagination v-model="page" :total="result.total" :size="12" />
        </template>
      </div>
      <p class="foot">후기는 이용 완료한 내 예약에서 작성할 수 있어요. <RouterLink to="/me?tab=completed">이용 완료 예약 보기</RouterLink></p>
    </section>
  </div>
</template>

<style scoped>
.page {
  padding-block: var(--sp-24) var(--sp-64);
}
.head {
  margin-bottom: var(--sp-16);
}
.head h1 {
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 900;
}
.head p {
  margin-top: 4px;
  color: var(--c-muted);
}
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-16);
  padding-top: var(--sp-24);
}
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: var(--sp-8);
  margin: 0;
  padding: 0;
  list-style: none;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  width: 100%;
  padding: var(--sp-12) var(--sp-16);
  border: 1.5px solid var(--c-line);
  border-radius: var(--r-md);
  background: var(--c-surface);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--t-fast);
}
.stat:hover {
  border-color: var(--c-brand);
}
.stat[aria-pressed='true'] {
  border-color: var(--c-brand);
  background: var(--c-brand-soft);
}
.stat span {
  font-weight: 700;
}
.stat strong {
  font-size: var(--fs-20);
  font-weight: 900;
}
.stat small {
  color: var(--c-subtle);
  font-size: var(--fs-12);
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--sp-12);
}
.toolbar__count {
  margin-right: auto;
  align-self: center;
  font-weight: 700;
}
.toolbar__sort {
  min-width: 160px;
}
.toolbar__search {
  flex: 1 1 260px;
  max-width: 420px;
}
/* 탭 전환: 이전 결과를 흐리게 유지했다가 새 결과로 바꾼다(빈 칸 반짝임 없음). */
.results {
  transition: opacity var(--t-fast) var(--ease-out);
}
.results.is-loading {
  opacity: 0.55;
  pointer-events: none;
}
@media (prefers-reduced-motion: reduce) {
  .results {
    transition: none;
  }
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--sp-16);
}
.grid__card {
  padding: var(--sp-16);
  border: 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-12);
  padding: var(--sp-48) var(--sp-16);
  border: 1px dashed var(--c-line-strong);
  border-radius: var(--r-lg);
  color: var(--c-muted);
}
.foot,
.muted {
  color: var(--c-subtle);
  font-size: var(--fs-13);
}

</style>
