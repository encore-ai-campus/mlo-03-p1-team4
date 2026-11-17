// 페르소나 500명 읽기 시험: 문서에서 뽑은 유형·지역·인원으로 검색 → 첫 후보 상세·시간표 확인.
// 예약·가입은 하지 않는다. 이벤트 전송 결과는 따로 세고, 공개 조회 API 오류만 실패로 본다.
import process from 'node:process'
import { test, expect } from '@playwright/test'
import { loadPersonas500 } from './personas500.mjs'
import { futureDate } from './policy.mjs'

const all = loadPersonas500()
const limit = Number(process.env.PERSONA500_LIMIT || all.length)
for (const persona of all.slice(0, limit)) {
  test(`${persona.id} · ${persona.category} · ${persona.sido} · ${persona.people}명`, async ({ page, baseURL }, info) => {
    test.skip(process.env.PERSONA_RUN !== '1', '준비 모드: 서버 접속 없음')
    const origin = new URL(baseURL).origin
    const synthetic = { 'X-Synthetic': '1', 'X-Synthetic-Key': process.env.E2E_SYNTHETIC_KEY }
    const date = futureDate([1, 2, 3, 4, 5, 6, 0])
    const result = { persona: persona.id, sha256: persona.sha256, category: persona.category, sido: persona.sido,
      source_sido: persona.sourceSido, people: persona.people, browse_only: persona.browseOnly, date,
      found: 0, venue_id: null, api: [], events: [], errors: [] }
    await page.route('**/*', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.origin !== origin) return route.continue()
      if (!['GET', 'HEAD'].includes(request.method()) && url.pathname !== '/api/events') {
        result.errors.push(`blocked:${request.method()}:${url.pathname}`)
        return route.abort('blockedbyclient')
      }
      if (!url.pathname.startsWith('/api/')) return route.continue()
      try {
        const response = await route.fetch({ headers: { ...request.headers(), ...synthetic }, maxRedirects: 0, maxRetries: 0 })
        await route.fulfill({ response })
      } catch {
        // 시험이 끝나 페이지가 닫히는 중에 남은 이벤트 전송은 버린다.
        await route.abort('aborted').catch(() => {})
      }
    })
    page.on('pageerror', () => result.errors.push('browser-javascript-error'))
    page.on('response', (response) => {
      const url = new URL(response.url())
      if (url.origin !== origin || !url.pathname.startsWith('/api/')) return
      if (url.pathname === '/api/events') { result.events.push(response.status()); return }
      result.api.push(response.status())
      if (response.status() >= 400) result.errors.push(`http:${response.status()}:${url.pathname.replace(/\/\d+/g, '/{id}')}`)
    })
    const isApi = (r, path) => new URL(r.url()).origin === origin && new URL(r.url()).pathname === path
    try {
      const query = new URLSearchParams({ category: persona.category, sido: persona.sido, people: String(persona.people), date, sort: 'price' })
      const loaded = page.waitForResponse((r) => isApi(r, '/api/venues'))
      await page.goto(`/search?${query}`)
      const response = await loaded
      expect(response.status()).toBe(200)
      const body = await response.json()
      const candidates = body.items.filter((v) => v.category.code === persona.category && v.capacity_max >= persona.people)
      result.found = candidates.length
      if (candidates.length) {
        const venue = candidates[0]
        const details = page.waitForResponse((r) => isApi(r, `/api/venues/${venue.venue_id}`))
        const slots = page.waitForResponse((r) => isApi(r, `/api/venues/${venue.venue_id}/slots`))
        await page.goto(`/venues/${venue.venue_id}?${new URLSearchParams({ date, people: String(persona.people) })}`)
        expect((await details).status()).toBe(200)
        expect((await slots).status()).toBe(200)
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
        result.venue_id = venue.venue_id
      }
      expect(result.errors, '공개 조회 API·브라우저 오류').toEqual([])
    } finally {
      await info.attach('persona-summary', { body: JSON.stringify(result), contentType: 'application/json' })
    }
  })
}
