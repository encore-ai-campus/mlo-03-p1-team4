<script setup>
import { computed, ref, watch } from 'vue'
import cafe from '@/assets/art/venue-cafe.jpg'
import lectureroom from '@/assets/art/venue-lectureroom.jpg'
import partyroom from '@/assets/art/venue-partyroom.jpg'
import studio from '@/assets/art/venue-studio.jpg'
import studyroom from '@/assets/art/venue-studyroom.jpg'
import { getVenuePhoto } from '@/utils/venuePhoto'

// 공간 유형별 CCL 분위기 참고 사진을 venue ID로 안정적으로 선택한다. 이미지 API 계약은 그대로 `art:<종류>-<색>`이다.
// 로딩 실패·유형 정보 없음·로그인 화면은 일러스트를 사용한다.
// 크롤러는 스터디룸에도 인원에 따라 seminar·lounge 같은 종류를 주므로, 종류만으로는 유형을 알 수 없다.
// 유형이 없을 때는 종류 → 일러스트 대응표를 쓴다. 색 1은 그림을 좌우로 뒤집는다.
const props = defineProps({
  image: { type: String, default: '' },
  kind: { type: String, default: 'group' }, // booth duo group seminar meeting lounge studio cafe partyroom
  tone: { type: Number, default: 0 },
  category: { type: [Object, String], default: null }, // { code } 또는 'studyroom' 같은 유형 코드
  seed: { type: [Number, String], default: '' }, // 공간 ID, 상세 갤러리는 공간 ID + 칸 번호
})
const photoFailed = ref(false)
watch(() => [typeof props.category === 'string' ? props.category : props.category?.code, props.seed], () => { photoFailed.value = false })

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
  const photo = photoFailed.value ? null : getVenuePhoto(code, props.seed)
  const picture = PICTURES[code] ?? PICTURES[KIND_TO_PICTURE[kind]] ?? PICTURES.studyroom
  return {
    src: photo ?? picture.src,
    label: photo ? `${code} 유형 분위기 참고 사진입니다. 실제 등록 공간의 사진이 아닙니다.` : picture.label,
    isPhoto: Boolean(photo),
    flip: !photo && tone === 1,
  }
})

function onImageError() {
  if (art.value.isPhoto) photoFailed.value = true
}
</script>

<template>
  <div class="art" role="img" :aria-label="art.label">
    <img :key="art.src" :src="art.src" alt="" loading="lazy" decoding="async" :class="{ 'is-flip': art.flip }" @error="onImageError" />
    <span v-if="art.isPhoto" class="art__note">분위기 참고</span>
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
.art__note {
  position: absolute;
  inset: auto var(--sp-8) var(--sp-8) auto;
  padding: var(--sp-4) var(--sp-8);
  border-radius: var(--r-sm);
  background: var(--c-ink);
  color: var(--c-on-dark);
  font-size: var(--fs-12);
  line-height: 1.4;
}
</style>
