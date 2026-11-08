// 2026-11-01 리뷰(docs/기록/리뷰_2026-11-01_프론트_QA.md)에서 고친 것이 다시 깨지지 않게
import { test, expect } from '@playwright/test'
import { fixClock, slot } from './helpers'

const NIGHT = new Date('2026-11-02T23:30:00+09:00')

test('QA-04: 밤에는 메인 패널이 내일 칸을 보여 주고, 카드는 지금 이용 가능이 없다', async ({ page }) => {
  await fixClock(page, NIGHT)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '내일 남은 칸' })).toBeVisible()
  await expect(page.getByText('지금 바로 들어갈 수 있는 곳')).toContainText('0곳')
  await expect(page.getByText('지금 이용 가능', { exact: true })).toHaveCount(0)
})

test('QA-04: 메인 패널에서 고른 칸을 들고 상세로 간다', async ({ page }) => {
  await fixClock(page)
  await page.goto('/')
  const strip = page.locator('section', { has: page.getByRole('heading', { name: '오늘 남은 칸' }) })
  const free = strip.getByRole('button', { name: /^\d{2}:00부터 1시간$/ })
  const first = (await free.first().getAttribute('aria-label')).slice(0, 2)
  await free.first().click()
  await strip.getByRole('button', { name: '이 시간으로 예약하기' }).click()
  await expect(page).toHaveURL(new RegExp(`/venues/1\\?date=2026-11-02&hours=${Number(first)}`))
  await expect(page.locator('#booking').getByRole('button', { name: `${first}:00부터 1시간` })).toHaveAttribute('aria-pressed', 'true')
})

test('QA-14: 밤에 지금 가능한 곳만 켜면 내일 보기로 이어 준다', async ({ page }) => {
  await fixClock(page, NIGHT)
  await page.goto('/search?now=1')
  await page.getByRole('button', { name: '내일 빈 시간 보기' }).click()
  await expect(page.getByRole('heading', { level: 2, name: /11월 3일/ })).toBeVisible()
  await expect(page.locator('#main article').first()).toBeVisible()
})

test('QA-08: 예약 카드로 바로 가기 → 포커스가 예약 카드 안으로', async ({ page }) => {
  await fixClock(page)
  await page.goto('/venues/2')
  await expect(page.locator('#booking')).toBeVisible()
  const skip = page.getByRole('button', { name: '예약 카드로 바로 가기' })
  await skip.focus()
  await expect(skip).toBeInViewport()
  await page.keyboard.press('Enter')
  await expect.poll(() => page.evaluate(() => document.getElementById('booking').contains(document.activeElement))).toBe(true)
})

test('QA-03: 폰에서는 토스트가 위쪽에 떠 하단 바를 가리지 않는다', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', '폰 화면 전용')
  await fixClock(page)
  await page.goto('/venues/1')
  // 토스트 띄우기: 이어진 빈 칸 5개를 차례로 누르면 '최대 4시간' 안내가 뜬다(찜은 API가 없어 11-06에 뺌)
  const free = page.locator('#booking').getByRole('button', { name: /^\d{2}:00부터 1시간$/ })
  await expect(free.first()).toBeVisible()
  const hours = (await free.evaluateAll((els) => els.map((el) => el.getAttribute('aria-label')))).map((t) => Number(t.slice(0, 2)))
  const h = hours.find((x) => [1, 2, 3, 4].every((d) => hours.includes(x + d)))
  expect(h, '이어진 빈 칸 5개').toBeDefined()
  for (const x of [h, h + 1, h + 2, h + 3, h + 4]) await slot(page, x).click()
  const toast = page.locator('[data-sonner-toast]').filter({ hasText: '최대 4시간' }).first()
  await expect(toast).toBeVisible()
  const t = await toast.boundingBox()
  const bar = await page.getByRole('button', { name: '시간 고르기' }).boundingBox()
  expect(t.y + t.height).toBeLessThan(bar.y)
})
