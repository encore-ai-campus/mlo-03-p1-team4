<script setup>
import { BookOpen, Camera, Presentation, Coffee, PartyPopper } from '@lucide/vue'
import RoomArt from './RoomArt.vue'

// 유형 바로가기 (벤토). 개수가 정해진 입구 5개에만 쓴다. 큰 칸(스터디룸)은 그림 + 글자, 작은 칸은 아이콘 + 글자 한 줄.
// 메인 첫 화면에 히어로와 함께 들어오도록 높이를 낮게 둔다 (2줄 × 108px).
defineProps({
  categories: { type: Array, required: true }, // [{ code, name, use }]
})
const uses = { studyroom: '팀 과제 · 면접 연습', studio: '프로필 · 제품 촬영', cafe: '북토크 · 소모임', lectureroom: '강의 · 워크숍', partyroom: '생일 · 모임' }
const icons = { studyroom: BookOpen, studio: Camera, cafe: Coffee, lectureroom: Presentation, partyroom: PartyPopper }
</script>

<template>
  <ul class="bento">
    <li v-for="c in categories" :key="c.code" class="bento__cell" :class="`bento__cell--${c.code}`">
      <RouterLink :to="{ path: '/search', query: { category: c.code } }" class="tile">
        <RoomArt v-if="c.code === 'studyroom'" kind="group" class="tile__art" />
        <span class="tile__icon" aria-hidden="true"><component :is="icons[c.code]" :size="22" /></span>
        <span class="tile__text">
          <span class="tile__name">{{ c.name }}</span>
          <span class="tile__use">{{ uses[c.code] }}</span>
        </span>
      </RouterLink>
    </li>
  </ul>
</template>

<style scoped>
.bento {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-12);
  margin: 0;
  padding: 0;
  list-style: none;
}
.bento__cell--studyroom {
  grid-column: span 2;
}
@media (min-width: 768px) {
  .bento {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    grid-template-rows: repeat(2, 108px);
  }
  .bento__cell--studyroom {
    grid-row: span 2;
  }
}
/* 작은 칸: 아이콘 왼쪽, 글자 오른쪽 */
.tile {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
  height: 100%;
  min-height: 88px;
  padding: var(--sp-16);
  border: 1px solid var(--c-line);
  border-radius: var(--r-lg);
  background: var(--c-surface);
  color: var(--c-ink);
  text-decoration: none;
  overflow: hidden;
  transition: border-color var(--t-fast), transform var(--t-fast) var(--ease-out);
}
.tile:hover {
  border-color: var(--c-brand);
}
@media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference) {
  .tile:hover {
    transform: translateY(-2px);
  }
}
.tile__icon {
  flex: none;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--c-brand-soft);
  color: var(--c-brand-ink);
}
.tile__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.tile__name {
  font-size: var(--fs-20);
  font-weight: 800;
  letter-spacing: -0.02em;
}
.tile__use {
  font-size: var(--fs-13);
  color: var(--c-muted);
}
/* 큰 칸(스터디룸): 위는 그림, 아래는 글자 */
.bento__cell--studyroom .tile {
  position: relative;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  padding: 0;
}
.bento__cell--studyroom .tile__art {
  flex: 1;
  min-height: 120px;
  aspect-ratio: auto;
}
.bento__cell--studyroom .tile__icon {
  position: absolute;
  top: var(--sp-12);
  left: var(--sp-12);
  background: var(--c-surface);
}
.bento__cell--studyroom .tile__text {
  padding: var(--sp-8) var(--sp-16) var(--sp-12);
}
</style>
