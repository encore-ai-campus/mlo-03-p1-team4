<script setup>
import { computed } from 'vue'
import cafe from '@/assets/art/venue-cafe.jpg'
import lectureroom from '@/assets/art/venue-lectureroom.jpg'
import partyroom from '@/assets/art/venue-partyroom.jpg'
import studio from '@/assets/art/venue-studio.jpg'
import studyroom from '@/assets/art/venue-studyroom.jpg'

// 공간 이미지: 유형별 일러스트 5장(11-06, `assets/art/README.md`)을 돌려 쓴다. 크롤링한 사진은 쓰지 않는다.
// API 계약은 그대로 `art:<종류>-<색>`(예: art:group-1). 공간 유형(category)을 받으면 그 유형 그림을 먼저 쓴다.
// 크롤러는 스터디룸에도 인원에 따라 seminar·lounge 같은 종류를 주므로, 종류만으로는 유형을 알 수 없다.
// 유형이 없을 때만 종류 → 그림 대응표를 쓴다. 색 1은 그림을 좌우로 뒤집어 카드가 덜 겹쳐 보이게 한다.
const props = defineProps({
  image: { type: String, default: '' },
  kind: { type: String, default: 'group' }, // booth duo group seminar meeting lounge studio cafe partyroom
  tone: { type: Number, default: 0 },
  category: { type: [Object, String], default: null }, // { code } 또는 'studyroom' 같은 유형 코드
})

const PICTURES = {
  studyroom: { src: studyroom, label: '6인 테이블과 화이트보드가 있는 스터디룸 일러스트' },
  studio: { src: studio, label: '촬영 조명과 카메라가 있는 스튜디오 일러스트' },
  cafe: { src: cafe, label: '원형 테이블과 카운터가 있는 카페 일러스트' },
  lectureroom: { src: lectureroom, label: '책상과 화이트보드가 있는 강의실 일러스트' },
  partyroom: { src: partyroom, label: '긴 테이블과 장식이 있는 파티룸 일러스트' },
}
const KIND_TO_PICTURE = {
  booth: 'studyroom',
  duo: 'studyroom',
  group: 'studyroom',
  meeting: 'lectureroom',
  seminar: 'lectureroom',
  lounge: 'cafe',
  studio: 'studio',
  cafe: 'cafe',
  partyroom: 'partyroom',
}

const art = computed(() => {
  const match = /^art:([a-z]+)-([01])$/.exec(props.image)
  const kind = match?.[1] ?? props.kind
  const tone = match ? Number(match[2]) : props.tone
  const code = typeof props.category === 'string' ? props.category : props.category?.code
  const picture = PICTURES[code] ?? PICTURES[KIND_TO_PICTURE[kind]] ?? PICTURES.studyroom
  return { ...picture, flip: tone === 1 }
})
</script>

<template>
  <div class="art" role="img" :aria-label="art.label">
    <img :src="art.src" alt="" loading="lazy" decoding="async" :class="{ 'is-flip': art.flip }" />
  </div>
</template>

<style scoped>
.art {
  position: relative;
  width: 100%;
  aspect-ratio: 400 / 260;
  overflow: hidden;
  background: var(--c-fill);
}
.art img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.art img.is-flip {
  transform: scaleX(-1);
}
</style>
