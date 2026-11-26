import process from 'node:process'
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { personas, requiredFacilities, searchDepth } from './personas.mjs'
import { allowedMutation, futureDate } from './policy.mjs'

const mode = process.env.PERSONA_MODE || 'read'
const selected = process.env.PERSONA_FILTER || 'all'
const confirmed = (process.env.E2E_CONFIRMED_PERSONAS || '').split(',')
for (const persona of personas.filter((p) => selected === 'all' || p.id === selected)) {
  test(`${persona.id} · ${persona.name} · ${mode}`, async ({ page, baseURL }, info) => {
    test.skip(process.env.PERSONA_RUN !== '1', '준비 모드: 서버 접속 없음')
    test.skip(mode === 'write' && persona.browseOnly, '검색 전용: 예약 시험 제외')
    if (mode === 'write') expect(confirmed, '문서의 시설·외부 조건을 먼저 확인하세요').toContain(persona.id)
    const source = new URL(`../../simulator/locust/personas/${persona.source}`, import.meta.url)
    const markdown = readFileSync(source, 'utf8')
    const firstDate = futureDate(persona.weekdays)
    let date = firstDate
    const origin = new URL(baseURL).origin
    const synthetic = { 'X-Synthetic': '1', 'X-Synthetic-Key': process.env.E2E_SYNTHETIC_KEY }
    const result = {
      persona: persona.id, source: persona.source,
      source_sha256: createHash('sha256').update(markdown).digest('hex'),
      mode, date, prerequisites: persona.prerequisites, requests: [], errors: [],
      reservation_id: null, cleanup: 'not-needed',
    }
    let attempted = false
    let ownId = null
    const pending = []
    await page.route('**/*', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.origin !== origin) {
        const headers = { ...request.headers() }
        for (const key of Object.keys(headers)) {
          if (['x-synthetic', 'x-synthetic-key', 'authorization'].includes(key.toLowerCase())) delete headers[key]
        }
        return route.continue({ headers })
      }
      if (!allowedMutation(mode, url.pathname, request.method(), ownId, attempted)) {
        result.errors.push(`blocked:${request.method()}:${url.pathname}`)
        return route.abort('blockedbyclient')
      }
      if (request.method() === 'POST' && url.pathname === '/api/reservations') attempted = true
      if (!url.pathname.startsWith('/api/')) return route.continue()
      // fetch의 자동 리다이렉트를 금지해 키를 외부 Location으로 전달하지 않는다.
      const response = await route.fetch({ headers: { ...request.headers(), ...synthetic }, maxRedirects: 0, maxRetries: 0 })
      if (response.status() >= 300 && response.status() < 400) {
        result.errors.push(`api-redirect-blocked:${url.pathname}`)
        return route.abort('blockedbyclient')
      }
      return route.fulfill({ response })
    })
    if (process.env.PERSONA_RECORD === '1') {
      // 녹화 영상에서 누구 화면인지 알 수 있게 오른쪽 아래에 이름표를 띄운다(클릭·접근성 트리에 영향 없음).
      await page.addInitScript((label) => {
        const show = () => {
          if (document.getElementById('persona-badge')) return
          const badge = document.createElement('div')
          badge.id = 'persona-badge'
          badge.textContent = label
          badge.setAttribute('aria-hidden', 'true')
          badge.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:2147483647;padding:6px 12px;border-radius:6px;background:#111827;color:#fff;font:600 14px/1.4 sans-serif;pointer-events:none;opacity:.85'
          document.body.appendChild(badge)
        }
        if (document.body) show()
        else document.addEventListener('DOMContentLoaded', show)
      }, `${persona.name} · ${persona.id} · ${mode}`)
    }
    page.on('pageerror', () => result.errors.push('browser-javascript-error'))
    page.on('response', (response) => {
      const url = new URL(response.url())
      if (url.origin !== origin || !url.pathname.startsWith('/api/')) return
      const request = response.request()
      const timing = request.timing()
      result.requests.push({ path: url.pathname, method: request.method(), status: response.status(), ttfb_ms: timing.responseStart })
      if (response.status() >= 400) result.errors.push(`http:${response.status()}:${url.pathname}`)
      if (request.method() === 'POST' && url.pathname === '/api/reservations' && response.status() === 201) {
        pending.push(response.json().then((body) => {
          if (Number.isInteger(body.reservation_id)) {
            ownId = body.reservation_id
            result.reservation_id = ownId
            result.cleanup = 'pending'
          }
        }).catch(() => result.errors.push('invalid-create-response')))
      }
    })
    const apiResponse = (response, path) => new URL(response.url()).origin === origin && new URL(response.url()).pathname === path
    try {
      if (mode === 'write') {
        await page.goto('/login')
        await page.getByLabel('이메일', { exact: true }).fill(process.env.E2E_EMAIL)
        await page.getByLabel('비밀번호', { exact: true }).fill(process.env.E2E_PASSWORD)
        const login = page.waitForResponse((r) => apiResponse(r, '/api/auth/login'))
        await page.getByRole('button', { name: '로그인', exact: true }).click()
        expect((await login).status()).toBe(200)
        await expect(page).not.toHaveURL(/\/login/)
      }
      // 인원·예산·시간 길이는 완화하지 않는다. 첫 페이지에서 조건에 맞는 후보를 최대 searchDepth.candidates곳 비교하고,
      // 빈 시간이 없으면 같은 요일로 다음 주(최대 searchDepth.weeks주)까지 다시 찾는다.
      let candidate = null
      let category = null
      const recording = process.env.PERSONA_RECORD === '1'
      // 녹화 때만 사람이 보는 속도로 멈춘다. PERSONA_PACE로 배율 조정(기본 1).
      const pace = recording ? Number(process.env.PERSONA_PACE || 1) : 0
      const beat = async (ms) => { if (pace) await page.waitForTimeout(ms * pace) }
      const tour = async () => {
        // 상세 화면을 천천히 내려 보며 사진·시설·시간표를 영상에 담는다.
        if (!pace) return
        await beat(2000)
        for (let i = 0; i < 3; i++) { await page.mouse.wheel(0, 400); await beat(1500) }
        await page.mouse.wheel(0, -1200)
        await beat(1500)
      }
      const checked = []
      for (let week = 0; week < searchDepth.weeks && !candidate; week++) {
      const shifted = new Date(`${firstDate}T00:00:00Z`)
      shifted.setUTCDate(shifted.getUTCDate() + 7 * week)
      date = shifted.toISOString().slice(0, 10)
      for (const code of persona.categories) {
        const query = new URLSearchParams({ category: code, sido: persona.sido, people: String(persona.people), date, sort: 'price' })
        const loaded = page.waitForResponse((r) => apiResponse(r, '/api/venues'))
        await page.goto(`/search?${query}`)
        const response = await loaded
        expect(response.status()).toBe(200)
        const body = await response.json()
        expect(Array.isArray(body.items)).toBe(true)
        const candidates = body.items.filter((v) => v.category.code === code && v.capacity_max >= persona.people && v.price_per_hour * persona.hours <= persona.budget)
        // 검색 결과 목록을 보여 준다.
        await beat(2500)
        if (pace) { await page.mouse.wheel(0, 500); await beat(1800); await page.mouse.wheel(0, -500); await beat(800) }
        for (const venue of candidates.slice(0, searchDepth.candidates)) {
          const details = page.waitForResponse((r) => apiResponse(r, `/api/venues/${venue.venue_id}`))
          const slots = page.waitForResponse((r) => apiResponse(r, `/api/venues/${venue.venue_id}/slots`) && new URL(r.url()).searchParams.get('date') === date)
          const selection = new URLSearchParams({ date, people: String(persona.people) })
          if (!persona.browseOnly) {
            selection.set('start', String(persona.start))
            selection.set('hours', String(persona.hours))
          }
          await page.goto(`/venues/${venue.venue_id}?${selection}`)
          const detailResponse = await details
          const slotResponse = await slots
          expect(detailResponse.status()).toBe(200)
          expect(slotResponse.status()).toBe(200)
          const detail = await detailResponse.json()
          const available = await slotResponse.json()
          const hours = Array.from({ length: persona.hours }, (_, i) => persona.start + i)
          await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
          const amenities = (detail.facilities || []).map((f) => f.name)
          const required = requiredFacilities[persona.id]
          const facilitiesMatch = required.every((name) => amenities.includes(name))
          await tour()
          const reasons = []
          if (!facilitiesMatch) reasons.push('facilities')
          if (detail.min_hours > persona.hours) reasons.push('min_hours')
          if (detail.open_hour > persona.start || detail.close_hour < persona.start + persona.hours) reasons.push('open_hours')
          if (!hours.every((h) => available.some((s) => s.hour === h && !s.taken && !s.past))) reasons.push('slots_taken')
          checked.push({ date, venue_id: venue.venue_id, fit: persona.browseOnly || reasons.length === 0, reasons })
          if (persona.browseOnly || reasons.length === 0) {
            candidate = detail
            category = code
            break
          }
        }
        if (candidate) break
      }
      }
      result.checked = checked
      result.date = date
      expect(result.errors, 'HTTP/브라우저/쓰기 정책 오류').toEqual([])
      test.skip(!candidate, '비교한 후보(최대 주·곳 수는 searchDepth)에서 문서 조건·연속 빈 시간 충족 못함: 재고 미충족, 통과 아님. summary.checked의 reasons 확인')
      result.venue_id = candidate.venue_id
      result.category = category
      if (mode === 'write') {
        // 마지막 비교 후보와 실제 예약 후보를 같게 맞춘다.
        const selection = new URLSearchParams({ date, start: String(persona.start), hours: String(persona.hours), people: String(persona.people) })
        await page.goto(`/venues/${candidate.venue_id}?${selection}`)
        const book = page.getByRole('button', { name: '예약 신청하기', exact: true })
        await expect(book).toBeEnabled()
        await book.click()
        await expect(page).toHaveURL(/\/reserve\?/)
        await page.getByRole('radio', { name: { card: '카드결제', phone: '휴대폰', transfer: '계좌이체' }[persona.method], exact: false }).check()
        await page.getByLabel('이용 규칙과 취소 · 환불 규정을 확인했어요').check()
        const created = page.waitForResponse((r) => apiResponse(r, '/api/reservations') && r.request().method() === 'POST')
        await page.getByRole('button', { name: /결제하고 확정/ }).click()
        const response = await created
        expect(response.status()).toBe(201)
        await Promise.all(pending)
        expect(ownId, '생성 예약 ID').not.toBeNull()
        await expect(page.getByRole('heading', { name: '예약이 확정됐어요' })).toBeVisible()
        await page.goto('/me')
        const row = page.getByRole('listitem').filter({ hasText: new RegExp(`예약 ${ownId}(?!\\d)`) })
        await row.getByRole('button', { name: '예약 취소', exact: true }).click()
        const cancelled = page.waitForResponse((r) => apiResponse(r, `/api/reservations/${ownId}/cancel`))
        await page.getByRole('dialog').getByRole('button', { name: '예약 취소', exact: true }).click()
        expect((await cancelled).status()).toBe(200)
        await page.goto('/me?tab=cancelled')
        await expect(page.getByRole('listitem').filter({ hasText: new RegExp(`예약 ${ownId}(?!\\d)`) })).toContainText('환불 완료')
        result.cleanup = 'ui-cancelled'
      }
      expect(result.errors, 'HTTP/브라우저/쓰기 정책 오류').toEqual([])
    } finally {
      await Promise.allSettled(pending)
      // UI 실패 때도 이 시험이 생성한 예약만 취소한다. 토큰·응답 본문은 기록하지 않는다.
      if (ownId != null && result.cleanup === 'pending') {
        try {
          const status = await page.evaluate(async ({ id, headers }) => {
            const token = JSON.parse(sessionStorage.getItem('spacecube.session') || '{}').token
            if (!token) return 0
            const response = await fetch(`/api/reservations/${id}/cancel`, { method: 'POST', headers: { ...headers, Authorization: `Bearer ${token}` } })
            return response.status
          }, { id: ownId, headers: synthetic })
          result.cleanup = status === 200 ? 'api-fallback-cancelled' : `manual-check-required:${status}`
        } catch { result.cleanup = 'manual-check-required' }
      }
      if (attempted && ownId == null) result.cleanup = 'create-result-unknown:check-server-before-retry'
      await info.attach('persona-summary', { body: JSON.stringify(result, null, 2), contentType: 'application/json' })
    }
  })
}
