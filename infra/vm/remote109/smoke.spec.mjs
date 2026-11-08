import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = process.env.SPACE_FRONTEND_DIR || resolve(dirname(fileURLToPath(import.meta.url)), '../../../frontend')
const { test: base, expect } = createRequire(resolve(frontend, 'package.json'))('@playwright/test')
const syntheticHeaders = () => ({ 'X-Synthetic': '1', 'X-Synthetic-Key': process.env.SPACE_SYNTHETIC_KEY })
const test = base.extend({
  context: async ({ context }, use) => {
    await context.setExtraHTTPHeaders(syntheticHeaders())
    await use(context)
  },
  request: async ({ playwright, baseURL }, use) => {
    const request = await playwright.request.newContext({ baseURL, extraHTTPHeaders: syntheticHeaders() })
    await use(request)
    await request.dispose()
  },
})

test('실제 홈 화면과 API 연결', async ({ page }) => {
  const categories = page.waitForResponse(r => new URL(r.url()).pathname === '/api/categories')
  await page.goto('/')
  await expect(page.getByRole('banner')).toBeVisible()
  await expect(page.locator('main')).toBeVisible()
  expect((await categories).status()).toBe(200)
  await expect(page.getByRole('link', { name: /다락큐브/ }).first()).toBeVisible()
})

test('실제 공간 목록과 데이터가 있는 공간의 상세', async ({ request }) => {
  const response = await request.get('/api/venues?page=1&size=5')
  expect(response.status()).toBe(200)
  const list = await response.json()
  expect(Array.isArray(list.items)).toBe(true)
  expect(list.page).toBe(1)
  expect(typeof list.total).toBe('number')
  // 실제 공간이 비어 있어도 목록 응답은 검증한다. 공간 데이터 수는 보고서에 별도 기록한다.
  if (list.items.length) {
    const detail = await request.get(`/api/venues/${list.items[0].venue_id}`)
    expect(detail.status()).toBe(200)
    expect((await detail.json()).venue_id).toBe(list.items[0].venue_id)
  }
})

test('DB 헬스와 내부 경로 차단', async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.status()).toBe(200)
  expect((await health.json()).replica).not.toBe('down')
  expect((await request.get('/api/metrics')).status()).toBe(403)
  expect((await request.get('/api/internal/venues')).status()).toBe(403)
  expect((await request.get('/api/reservations/me')).status()).toBe(401)
})
