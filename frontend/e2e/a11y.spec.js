// WCAG 2 A·AA: 화면뿐 아니라 오류·창·가입 동의 상태도 검사한다.
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { animationsSettled, fixClock, loginFirst, toastSettled } from './helpers'

test.beforeEach(async ({ page }) => fixClock(page))

async function expectNoSerious(page, where) {
  await animationsSettled(page)
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
  expect(violations.filter((v) => ['serious', 'critical'].includes(v.impact)).map((v) => `${where} ${v.id}: ${v.nodes[0]?.target}`)).toEqual([])
}

test('로그인 직후 성공 토스트와 내 예약', async ({ page }) => {
  await loginFirst(page, '/me')
  await toastSettled(page)
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
  await expectNoSerious(page, '내 예약')
})

test('결제 충돌 안내와 다시 고르기', async ({ page }) => {
  await loginFirst(page, '/reserve?venue=1&date=2026-11-02&start=21&hours=1&people=2')
  await page.getByLabel('이용 규칙과 취소 · 환불 규정을 확인했어요').check()
  await page.getByRole('button', { name: /결제하고 확정/ }).click()
  await toastSettled(page, '먼저 결제')
  await expectNoSerious(page, '409')
})

test('결제 동의 입력 오류', async ({ page }) => {
  await loginFirst(page, '/reserve?venue=2&date=2026-11-02&start=13&hours=2&people=2')
  await page.getByRole('button', { name: /결제하고 확정/ }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expectNoSerious(page, '결제 동의')
})

test('후기 쓰기와 취소 확인 창', async ({ page }) => {
  await loginFirst(page, '/me?tab=completed')
  await page.getByRole('button', { name: '후기 쓰기' }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expectNoSerious(page, '후기 창')
  await page.keyboard.press('Escape')
  await page.getByRole('tab', { name: /이용 예정/ }).click()
  await page.getByRole('button', { name: '예약 취소' }).first().click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('button', { name: '취소하지 않기' })).toBeFocused()
  await expectNoSerious(page, '취소 창')
})

test('회원가입 필수 항목과 동의', async ({ page }) => {
  await page.goto('/login?tab=signup')
  await expect(page.getByRole('button', { name: /가입/ }).last()).toBeVisible()
  await expectNoSerious(page, '회원가입')
})

test('폰 검색 필터 드로어', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', '드로어는 폰 전용')
  await page.goto('/search')
  await page.getByRole('button', { name: /조건 바꾸기/ }).click()
  await expect(page.getByRole('dialog', { name: '검색 조건' })).toBeVisible()
  await expectNoSerious(page, '필터 드로어')
})
