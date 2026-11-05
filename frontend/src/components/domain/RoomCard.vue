<script setup>
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import { Heart, Star } from '@lucide/vue'
import RoomArt from './RoomArt.vue'
import { nowInSeoul } from '@/utils/date'
import { useEventLogger } from '@/composables/useEventLogger'

// 공간 카드. 카드 전체가 상세로 가는 링크이고(제목 링크를 카드 크기로 늘림), 찜 버튼은 따로 누를 수 있다.
const props = defineProps({
  room: { type: Object, required: true },
  rank: { type: Number, default: 0 }, // 1~3이면 '인기 n위'를 글자로
  index: { type: Number, default: 0 }, // 스태거 순서
})

const available = computed(() => props.room.slots?.some((s) => !s.taken && s.hour > nowInSeoul().hour))
const next = computed(() => props.room.slots?.find((s) => !s.taken && s.hour > nowInSeoul().hour)?.hour)
const saved = ref(false)
const { log } = useEventLogger()

function toggleSave() {
  saved.value = !saved.value
  toast(saved.value ? '찜 목록에 담았어요' : '찜 목록에서 뺐어요')
}
const won = (n) => n.toLocaleString('ko-KR')
</script>

<template>
  <article class="card" :style="{ '--i': Math.min(index, 7) }">
    <div class="card__media">
      <RoomArt :image="room.image" />
      <button type="button" class="save" :class="{ 'is-on': saved }" :aria-pressed="saved" :aria-label="saved ? '찜 해제' : '찜하기'" @click="toggleSave">
        <Heart :size="20" aria-hidden="true" />
      </button>
    </div>

    <div class="card__body">
      <div class="card__title-row">
        <h3 class="card__title">
          <RouterLink :to="`/venues/${room.venue_id}`" class="card__link" @click="log('view_venue', { venue_id: room.venue_id })">{{ room.name }}</RouterLink>
        </h3>
        <span class="rating num"><Star :size="15" class="star" fill="currentColor" aria-hidden="true" />{{ Number(room.rating_avg ?? 0).toFixed(1) }} <span class="rating__count">({{ room.review_count }})</span></span>
      </div>
      <p class="card__meta"><strong v-if="rank && rank <= 3" class="card__rank">인기 {{ rank }}위 · </strong>{{ room.category.name }} · {{ room.region.sido }} {{ room.region.sigungu }} · 최대 {{ room.capacity_max }}인</p>
      <p class="card__now" :class="{ 'is-now': available }">{{ available ? '지금 이용 가능' : next ? `다음 빈 시간 ${next}:00` : '오늘 예약 마감' }}</p>
      <p class="card__desc">{{ room.facilities?.map((f) => typeof f === 'string' ? f : f.name).join(' · ') }}</p>
      <p class="price num"><strong>{{ won(room.price_per_hour) }}원</strong> / 1시간</p>
    </div>
  </article>
</template>

<style scoped>
.card {
  position: relative;
  display: flex;
  flex-direction: column;
  border-radius: var(--r-lg);
  background: var(--c-surface);
  transition: transform var(--t-fast) var(--ease-out), background-color var(--t-fast);
  animation: rise var(--t-enter) var(--ease-out) both;
  animation-delay: calc(var(--i) * 50ms);
}
/* 호버: 바탕 한 단계 + 3px 들림. 마우스에서만(폰은 탭 뒤 호버가 남는다) */
@media (hover: hover) and (pointer: fine) {
  .card:hover {
    background: var(--c-fill);
  }
}
@media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference) {
  .card:hover {
    transform: translateY(-3px);
  }
}
.card:focus-within {
  background: var(--c-fill);
}
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
}
@media (prefers-reduced-motion: reduce) {
  @keyframes rise {
    from {
      opacity: 0;
    }
  }
}
.card__media {
  position: relative;
  border-radius: var(--r-lg) var(--r-lg) 0 0;
  overflow: hidden;
}
/* 찜: 카드 링크 위로 올라와 따로 눌린다 */
.save {
  position: absolute;
  right: var(--sp-8);
  top: var(--sp-8);
  z-index: 2;
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: 50%;
  background: var(--c-surface);
  color: var(--c-muted);
  cursor: pointer;
  transition:
    transform var(--t-fast) var(--ease-out),
    color var(--t-fast);
}
.save:active {
  transform: scale(0.95);
}
.save :deep(svg) {
  fill: transparent;
  transition: fill var(--t-fast);
}
.save.is-on {
  color: var(--c-heart);
}
.save.is-on :deep(svg) {
  fill: currentColor;
}
.card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--sp-16);
}
.card__title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-8);
}
.card__title {
  font-size: var(--fs-20);
  font-weight: 800;
}
.card__link {
  color: inherit;
  text-decoration: none;
}
/* 제목 링크를 카드 전체로 늘린다 */
.card__link::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  border-radius: var(--r-lg);
}
.card__link:focus-visible {
  outline: none;
}
.card__link:focus-visible::after {
  outline: 3px solid var(--c-brand-light);
  outline-offset: 2px;
}
.card:hover .card__title {
  color: var(--c-brand-ink);
}
.rating {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex: none;
  font-size: var(--fs-15);
  font-weight: 700;
}
.rating .star {
  color: var(--c-star);
}
.rating__count {
  color: var(--c-subtle);
  font-weight: 400;
}
.card__meta {
  font-size: var(--fs-15);
  color: var(--c-muted);
}
.card__rank {
  color: var(--c-brand-ink);
  font-weight: 800;
}
.card__now {
  font-size: var(--fs-15);
  color: var(--c-muted);
}
.card__now.is-now {
  color: var(--c-brand-ink);
  font-weight: 700;
}
.card__desc {
  font-size: var(--fs-15);
  color: var(--c-ink-2);
  line-height: 1.55;
}
.pop {
  display: flex;
  align-items: center;
  gap: var(--sp-8);
  font-size: var(--fs-13);
  color: var(--c-subtle);
}
.pop__label {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.pop__info {
  position: relative;
  z-index: 2;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  margin: -7px 0;
  border: 0;
  border-radius: 50%;
  background: none;
  color: var(--c-subtle);
  cursor: help;
}
.pop__bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--c-fill);
  overflow: hidden;
}
.pop__bar > span {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: var(--c-brand);
}
.pop__value {
  color: var(--c-muted);
}
.price {
  margin-top: 2px;
  color: var(--c-subtle);
}
.price strong {
  color: var(--c-ink);
  font-size: var(--fs-20);
  font-weight: 900;
}
</style>
