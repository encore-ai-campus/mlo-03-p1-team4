<script setup>
import { computed } from 'vue'

// 공간 일러스트 9종 × 색 2가지. 디자인 캔버스 RoomArt.dc.html의 그림 로직을 그대로 옮겼다.
// 크롤링한 사진을 쓰지 않으므로 모든 공간 이미지는 이 그림을 유형·인원별로 돌려 쓴다.
const props = defineProps({
  image: { type: String, default: '' },
  kind: { type: String, default: 'group' }, // booth duo group seminar meeting lounge studio cafe partyroom
  tone: { type: Number, default: 0 },
})

const ALT_WALLS = { booth: '#DCEBF3', duo: '#F3E1E1', group: '#E1ECF7', seminar: '#EDE6DA', meeting: '#E6EDE4', lounge: '#E3E9F5', studio: '#E3E7EE', cafe: '#E6E9DA', partyroom: '#E3E1FA' }

function build(kind) {
  const s = []
  const R = (l, t, w, h, bg, x = '') => s.push(`position:absolute;left:${l}%;top:${t}%;width:${w}%;height:${h}%;background:${bg};${x}`)
  const floor = (c) => {
    R(0, 70, 100, 30, c)
    R(0, 69, 100, 1.6, 'rgba(0,0,0,.10)')
    for (let i = 1; i < 6; i++) R(0, 70 + i * 5.5, 100, 0.5, 'rgba(0,0,0,.06)')
  }
  const backChair = (cx, c) => R(cx - 4.5, 48, 9, 14, c, 'border-radius:7px 7px 2px 2px')
  const frontChair = (cx, c) => {
    R(cx - 0.6, 84, 1.2, 9, '#2B2A33')
    R(cx - 6, 66, 12, 20, c, 'border-radius:10px 10px 4px 4px;box-shadow:inset 0 -6px 0 rgba(0,0,0,.14)')
  }
  const table = (cx, w, c) => {
    R(cx - w / 2 + 2, 63, 1.4, 24, '#3B3A44')
    R(cx + w / 2 - 3.4, 63, 1.4, 24, '#3B3A44')
    R(cx - w / 2 + 1, 63, w - 2, 2.2, 'rgba(0,0,0,.18)')
    R(cx - w / 2, 59.5, w, 3.8, c, 'border-radius:3px')
  }
  const whiteboard = (l, t, w, h) => {
    R(l, t, w, h, '#FFFFFF', 'box-shadow:0 0 0 2px #B8B6C4;border-radius:2px')
    R(l + w * 0.1, t + h * 0.22, w * 0.45, 1.2, '#5638E8')
    R(l + w * 0.1, t + h * 0.42, w * 0.32, 1, '#9A98A8')
    R(l + w * 0.1, t + h * 0.6, w * 0.55, 1, '#9A98A8')
    R(l + w * 0.68, t + h * 0.3, w * 0.18, h * 0.42, 'transparent', 'border:2px solid #E0794A;border-radius:50%;box-sizing:border-box')
    R(l + w * 0.25, t + h, w * 0.5, 1.6, '#B8B6C4')
  }
  const tv = (l, t, w, h) => {
    R(l, t, w, h, '#1D1C24', 'border-radius:4px')
    R(l + 1, t + 2, w - 2, h - 4, '#2F2A5C', 'border-radius:2px')
    R(l + 4, t + h * 0.3, w * 0.4, 1.4, '#FFFFFF')
    R(l + 4, t + h * 0.5, w * 0.25, 1, '#B9AEF5')
    R(l + w * 0.6, t + h * 0.3, w * 0.25, h * 0.4, '#5638E8', 'border-radius:2px')
  }
  const screen = (l, t, w, h) => {
    R(l - 1, t, w + 2, 2.4, '#3B3A44', 'border-radius:2px')
    R(l, t + 2.4, w, h, '#F6F6F8', 'box-shadow:0 2px 0 rgba(0,0,0,.08)')
    ;[0.35, 0.6, 0.45, 0.8].forEach((v, i) => R(l + w * (0.18 + i * 0.12), t + 2.4 + h * (0.85 - v * 0.7), w * 0.07, h * v * 0.7, i === 3 ? '#5638E8' : '#C9C0F7'))
  }
  const windowPane = (l, t, w, h) => {
    R(l, t, w, h, '#CFE3F2', 'box-shadow:0 0 0 4px #FFFFFF')
    R(l, t + h * 0.62, w, h * 0.38, '#B7D3B4')
    R(l + w * 0.08, t + h * 0.38, w * 0.16, h * 0.4, '#7FB07E', 'border-radius:50% 50% 40% 40%')
    R(l + w * 0.62, t + h * 0.3, w * 0.2, h * 0.5, '#6FA16F', 'border-radius:50% 50% 40% 40%')
    R(l + w / 3, t, 0.8, h, '#FFFFFF')
    R(l + (w * 2) / 3, t, 0.8, h, '#FFFFFF')
    R(l, t + h / 2, w, 1.2, '#FFFFFF')
  }
  const plant = (x) => {
    R(x + 1, 40, 7, 12, '#78B585', 'border-radius:50%')
    R(x - 3, 46, 13, 18, '#5E9B6C', 'border-radius:50% 50% 45% 45%')
    R(x, 62, 7, 9, '#E9E3D8', 'border-radius:2px 2px 6px 6px')
  }
  const lamp = (x) => {
    R(x, 0, 0.4, 12, '#3B3A44')
    R(x - 4, 12, 8.4, 5, '#2B2A33', 'border-radius:50% 50% 0 0 / 100% 100% 0 0')
    R(x - 2.5, 16.6, 5, 1.6, '#FFE7A3', 'border-radius:50%')
  }
  const clock = (x, y) => {
    R(x, y, 5, 7.7, '#FFFFFF', 'border-radius:50%;box-shadow:0 0 0 2px #3B3A44')
    R(x + 2.3, y + 1.6, 0.5, 3, '#3B3A44')
  }
  const shelf = (l, t, w, h) => {
    R(l, t, w, h, '#E9E1D3', 'border-radius:2px')
    const cols = ['#5638E8', '#E0794A', '#2F7D5B', '#E8B44C', '#3F5BA9']
    for (let row = 0; row < 3; row++) {
      R(l, t + ((row + 1) * h) / 3 - 1, w, 1, '#C9BEA9')
      for (let i = 0; i < 4; i++) R(l + 1.5 + (i * (w - 3)) / 4, t + (row * h) / 3 + 3, (w - 3) / 4 - 1, h / 3 - 4.5, cols[(row + i) % 5], 'border-radius:1px')
    }
  }

  const scenes = {
    booth: { wall: '#E6E1F6', label: '칸막이 책상과 개별 조명이 있는 1인 부스', draw() {
      floor('#CDBB98')
      R(22, 24, 40, 38, '#D3CAF0', 'border-radius:4px 4px 0 0')
      R(19, 20, 4, 50, '#B9AEDF', 'border-radius:3px 3px 0 0')
      R(61, 20, 4, 50, '#B9AEDF', 'border-radius:3px 3px 0 0')
      R(86, 20, 4, 50, '#B9AEDF', 'border-radius:3px 3px 0 0')
      R(90, 24, 12, 38, '#D3CAF0')
      R(40, 36, 20, 22, 'rgba(255,224,140,.45)', 'border-radius:50%')
      R(52, 40, 0.9, 18, '#2B2A33')
      R(47.5, 37, 9, 4, '#2B2A33', 'border-radius:4px')
      R(29, 52, 14, 7, '#3B3A44', 'border-radius:2px 2px 0 0')
      table(42, 42, '#F6F1E7')
      frontChair(42, '#5638E8')
      plant(72)
      clock(70, 16)
    } },
    duo: { wall: '#DCEAE2', label: '마주 앉는 2인 테이블과 미니 화이트보드', draw() {
      floor('#CBB590')
      shelf(6, 22, 14, 46)
      whiteboard(56, 16, 26, 22)
      lamp(40)
      backChair(40, '#2F7D5B')
      table(40, 34, '#F6F1E7')
      frontChair(40, '#24684B')
      plant(86)
    } },
    group: { wall: '#F2E5D3', label: '벽면 화이트보드와 6인 테이블이 있는 그룹룸', draw() {
      floor('#B99B70')
      whiteboard(18, 12, 64, 30)
      ;[32, 44, 56, 68].forEach((x) => backChair(x, '#E0794A'))
      table(50, 56, '#F6F1E7')
      ;[36, 64].forEach((x) => frontChair(x, '#C9643A'))
      plant(88)
    } },
    seminar: { wall: '#DCE5F1', label: '대형 TV와 8인 테이블이 있는 세미나룸', draw() {
      floor('#A8A39B')
      tv(36, 12, 28, 26)
      clock(12, 16)
      whiteboard(72, 16, 18, 22)
      ;[26, 38, 50, 62, 74].forEach((x) => backChair(x, '#3F5BA9'))
      table(50, 64, '#F6F1E7')
      ;[32, 50, 68].forEach((x) => frontChair(x, '#33498A'))
    } },
    meeting: { wall: '#E4E3E6', label: '빔프로젝터 스크린과 장테이블이 있는 회의실', draw() {
      floor('#8C877F')
      screen(20, 6, 60, 32)
      ;[18, 30, 42, 58, 70, 82].forEach((x) => backChair(x, '#4A4858'))
      table(50, 76, '#3A3845')
      ;[26, 42, 58, 74].forEach((x) => frontChair(x, '#4A4858'))
    } },
    lounge: { wall: '#F5E8D8', label: '통창과 소파석이 있는 라운지', draw() {
      floor('#C7A77A')
      windowPane(6, 8, 58, 50)
      lamp(74)
      lamp(86)
      R(10, 47, 36, 14, '#B0563A', 'border-radius:10px 10px 4px 4px')
      R(7, 56, 42, 15, '#C0603F', 'border-radius:8px')
      R(7, 52, 5, 19, '#A64E33', 'border-radius:6px')
      R(44, 52, 5, 19, '#A64E33', 'border-radius:6px')
      R(10, 70, 1.2, 5, '#2B2A33')
      R(45, 70, 1.2, 5, '#2B2A33')
      R(63.5, 66, 1.2, 12, '#3B3A44')
      R(54, 63, 20, 4, '#F6F1E7', 'border-radius:50%')
      R(76, 55, 15, 22, '#E8B44C', 'border-radius:14px 14px 6px 6px')
      R(78, 63, 11, 8, '#F2C766', 'border-radius:6px')
    } },
    studio: { wall: '#E9E9EE', label: '흰 호리존 벽과 조명, 카메라가 있는 촬영 스튜디오', draw() {
      R(8, 6, 84, 70, '#FAFAFA', 'border-radius:0 0 30% 30% / 0 0 14% 14%')
      R(0, 72, 100, 28, '#F1F1F4')
      ;[[8, 14], [79, 82]].forEach(([bx, sx]) => {
        R(sx, 30, 0.8, 52, '#2B2A33')
        R(sx - 3.5, 82, 8, 0.8, '#2B2A33')
        R(bx, 16, 13, 16, '#FFFFFF', 'box-shadow:0 0 0 2px #2B2A33;border-radius:3px')
        R(bx + 2, 18, 9, 12, '#FFF6D8')
      })
      R(49.6, 58, 0.8, 30, '#2B2A33')
      R(45.5, 87, 9, 0.8, '#2B2A33')
      R(44, 49, 12, 9, '#2B2A33', 'border-radius:2px')
      R(47.5, 51, 5, 6.5, '#5638E8', 'border-radius:50%')
      R(30, 60, 8, 14, '#E8B44C', 'border-radius:6px 6px 2px 2px')
    } },
    cafe: { wall: '#F1E3CF', label: '카운터와 메뉴판, 원형 테이블이 있는 카페', draw() {
      floor('#A8825A')
      R(10, 12, 26, 24, '#2E3B33', 'border-radius:3px;box-shadow:0 0 0 3px #7A5638')
      ;[0.25, 0.45, 0.65].forEach((v) => R(13, 12 + 24 * v, 14 + v * 6, 1, '#E9E3D8'))
      R(14, 40, 9, 12, '#3B3A44', 'border-radius:2px')
      R(26, 45, 4, 7, '#F6F1E7', 'border-radius:1px 1px 3px 3px')
      R(6, 51, 44, 3, '#5A3E28', 'border-radius:2px')
      R(8, 54, 40, 18, '#7A5638')
      ;[60, 72, 84].forEach((x) => lamp(x))
      R(64.5, 64, 1.2, 16, '#3B3A44')
      R(58, 61.5, 14, 2.6, '#F6F1E7', 'border-radius:3px')
      R(53, 64, 5, 16, '#C9643A', 'border-radius:4px 4px 2px 2px')
      R(73, 64, 5, 16, '#C9643A', 'border-radius:4px 4px 2px 2px')
      plant(88)
    } },
    partyroom: { wall: '#FBE3E8', label: '풍선과 가랜드, 긴 테이블이 있는 파티룸', draw() {
      floor('#C7A77A')
      const flags = ['#E5484D', '#FFC23D', '#5638E8', '#2F7D5B', '#E0794A']
      for (let i = 0; i < 9; i++) R(22 + i * 6.5, 8 + (i % 2) * 1.5, 3.4, 5.2, flags[i % 5], 'transform:rotate(45deg)')
      R(20, 9, 60, 0.5, '#8A8896')
      ;[[6, 14, '#E5484D'], [12, 20, '#FFC23D'], [86, 12, '#5638E8'], [91, 19, '#2F7D5B']].forEach(([bx, by, c]) => {
        R(bx + 3.3, by + 10, 0.4, 16, '#8A8896')
        R(bx, by, 7, 10.8, c, 'border-radius:50%')
      })
      R(0, 32, 100, 1, '#FF7AB6', 'box-shadow:0 0 8px #FF7AB6')
      ;[32, 44, 56, 68].forEach((x) => backChair(x, '#F2A0B6'))
      table(50, 56, '#F6F1E7')
      R(46, 52.5, 8, 7, '#FFFFFF', 'border-radius:2px 2px 0 0')
      R(46, 52.5, 8, 2, '#E5484D', 'border-radius:2px 2px 0 0')
      ;[36, 64].forEach((x) => frontChair(x, '#E0794A'))
    } },
  }

  const sc = scenes[kind] ?? scenes.group
  sc.draw()
  return { shapes: s, wall: sc.wall, label: sc.label }
}

const art = computed(() => {
  const match = /^art:([a-z]+)-([01])$/.exec(props.image)
  const kind = match?.[1] ?? props.kind
  const tone = match ? Number(match[2]) : props.tone
  const a = build(kind)
  return { ...a, wall: tone ? ALT_WALLS[kind] ?? a.wall : a.wall }
})
</script>

<template>
  <div class="art" role="img" :aria-label="art.label" :style="{ background: art.wall }">
    <div v-for="(style, i) in art.shapes" :key="i" :style="style" />
  </div>
</template>

<style scoped>
.art {
  position: relative;
  width: 100%;
  aspect-ratio: 400 / 260;
  overflow: hidden;
}
</style>
