// 날짜 도우미. 오늘·현재 시는 브라우저 설정과 무관하게 한국 시각을 쓴다.
const WD = ['일', '월', '화', '수', '목', '금', '토']

export function nowInSeoul() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).formatToParts(new Date())
  const p = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
  return { date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour) }
}

export function dayOffset(iso) {
  const parsed = new Date(`${iso}T00:00:00Z`)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso ?? '') || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== iso) return NaN
  return Math.round((parsed.getTime() - Date.parse(`${todayISO()}T00:00:00Z`)) / 86400000)
}

export function toISO(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function fromISO(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function todayISO() {
  return nowInSeoul().date
}

export function addDays(iso, n) {
  const d = fromISO(iso)
  d.setDate(d.getDate() + n)
  return toISO(d)
}

// 오늘부터 n일 [{ iso, month, day, weekday, isToday }]
export function nextDays(n = 14, offset = 0) {
  const today = todayISO()
  const start = Math.max(-365, Math.min(365, offset))
  return Array.from({ length: Math.max(0, Math.min(n, 366 - start)) }, (_, i) => {
    const iso = addDays(today, start + i)
    const d = fromISO(iso)
    return { iso, month: d.getMonth() + 1, day: d.getDate(), weekday: WD[d.getDay()], dow: d.getDay(), isToday: iso === today }
  })
}

export function dateLabel(iso) {
  const d = fromISO(iso)
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${WD[d.getDay()]})`
}

export const hourLabel = (h) => `${String(h).padStart(2, '0')}:00`

export function rangeLabel(hours) {
  if (!hours?.length) return ''
  const min = Math.min(...hours)
  const max = Math.max(...hours)
  return `${hourLabel(min)}–${hourLabel(max + 1)}`
}

export const won = (n) => `${n.toLocaleString('ko-KR')}원`
