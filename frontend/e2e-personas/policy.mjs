// 날짜는 서울 기준 다음 주부터 고른다. 실제 업무 날짜를 가상으로 바꾸지 않는다.
export function futureDate(weekdays, now = new Date()) {
  const day = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)
  const date = new Date(`${day}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 7)
  while (!weekdays.includes(date.getUTCDay())) date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}

export function allowedMutation(mode, path, method, ownId, attempted) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(method)) return true
  if (method !== 'POST') return false
  if (path === '/api/events') return true
  if (mode !== 'write') return false
  return path === '/api/auth/login'
    || (path === '/api/reservations' && !attempted)
    || (ownId != null && path === `/api/reservations/${ownId}/cancel`)
}

// 보고서에 Playwright 원시 오류·입력값·헤더·실행 단계를 복사하지 않는다.
export function safeResult(title, result) {
  return { title, status: result.status, expectedStatus: result.expectedStatus, duration_ms: result.duration,
    errors: (result.errors || []).map(() => '시험 오류: 원시 오류·입력값 비저장') }
}
