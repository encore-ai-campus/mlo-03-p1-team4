<script setup>
import RoomArt from './RoomArt.vue'

// 유형 바로가기 (벤토). 개수가 정해진 입구 5개에만 쓴다. 큰 칸(스터디룸)은 위 그림 + 글자, 작은 칸은 왼쪽 그림 + 글자.
// 메인 첫 화면에 히어로와 함께 들어오도록 높이를 낮게 둔다 (2줄 × 108px).
defineProps({
  categories: { type: Array, required: true }, // [{ code, name, use }]
})
const uses = { studyroom: '팀 과제 · 면접 연습', studio: '프로필 · 제품 촬영', cafe: '북토크 · 소모임', lectureroom: '강의 · 워크숍', partyroom: '생일 · 모임' }
const arts = { studyroom: 'group', studio: 'studio', cafe: 'cafe', lectureroom: 'seminar', partyroom: 'partyroom' }
</script>

<template>
  <ul class="bento">
    <li v-for="c in categories" :key="c.code" class="bento__cell" :class="`bento__cell--${c.code}`">
      <RouterLink :to="{ path: '/search', query: { category: c.code } }" class="tile">
        <RoomArt :kind="arts[c.code]" class="tile__art" aria-hidden="true" />
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
/* 작은 칸: 그림 왼쪽, 글자 오른쪽 */
.tile {
  display: flex;
  align-items: center;
  gap: var(--sp-12);
  height: 100%;
  min-height: 88px;
  padding: 0 var(--sp-16) 0 0;
  border-radius: var(--r-lg);
  background: var(--c-surface);
  color: var(--c-ink);
  text-decoration: none;
  overflow: hidden;
  transition: background-color var(--t-fast), transform var(--t-fast) var(--ease-out);
}
.tile:hover {
  background: var(--c-fill);
}
.tile__art {
  flex: none;
  align-self: stretch;
  width: 112px;
  aspect-ratio: auto;
}
@media (hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference) {
  .tile:hover {
    transform: translateY(-2px);
  }
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
  font-size: var(--fs-15);
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
  width: auto;
  min-height: 120px;
}
.bento__cell--studyroom .tile__text {
  padding: var(--sp-8) var(--sp-16) var(--sp-12);
}
</style>
