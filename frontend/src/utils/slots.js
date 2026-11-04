// 시간 칸 계산 도우미. slots = [{ hour, taken, past }]

// 이어진 빈 칸(마감만 제외)의 가장 긴 길이. '예약 가능한 날' = 이 값이 공간의 min_hours 이상
export function longestFreeRun(slots) {
  let best = 0
  let run = 0
  for (const s of slots) {
    run = !s.taken ? run + 1 : 0
    best = Math.max(best, run)
  }
  return best
}

// 주소 query의 hours('13,14') ↔ 배열
export const parseHours = (v) => (v ? String(v).split(',').map(Number).filter((h) => Number.isInteger(h)) : [])
export const formatHours = (hours) => [...hours].sort((a, b) => a - b).join(',')
