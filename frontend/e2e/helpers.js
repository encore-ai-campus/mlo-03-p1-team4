// E2E 공통 도우미. 버튼·입력은 화면에 보이는 이름(역할·라벨)으로 찾는다.
import { expect } from '@playwright/test'

export const DEMO_USER = { email: 'study@example.com', password: 'abcd1234' } // 목업 시연 계정 (frontend/src/pages/README.md)

// 테스트 시계. 목업의 '이미 찬 칸'은 날짜로 정해지는 가짜 값이라, 실제 시각에 기대면 밤에는 빈 칸이 없어 테스트가 달라진다.
// 모든 E2E는 2026-11-02(월) 오전 10시(서울)에 연다. 이 날짜·시각에서 아래 시나리오가 성립하는지는 테스트가 직접 확인한다.
export const FIXED_NOW = new Date('2026-11-02T10:00:00+09:00')
export const FIXED_DAY = '2026-11-02'

export async function fixClock(page, at = FIXED_NOW) {
  await page.clock.setFixedTime(at)
}

// 예약 카드(#booking)에서 비어 있는 이어진 두 칸을 골라 누른다. 고른 시를 돌려준다.
export async function pickTwoFreeSlots(page) {
  const card = page.locator('#booking')
  const free = card.getByRole('button', { name: /^\d{2}:00부터 1시간$/ })
  await expect(free.first()).toBeVisible()
  const hours = (await free.allTextContents()).map((t) => Number(t.slice(0, 2)))
  const h = hours.find((x) => hours.includes(x + 1))
  if (h === undefined) return null
  for (const x of [h, h + 1]) await slot(page, x).click()
  return [h, h + 1]
}

export const slot = (page, h) => page.locator('#booking').getByRole('button', { name: `${String(h).padStart(2, '0')}:00부터 1시간` })

export async function login(page) {
  const form = page.locator('form')
  await form.getByLabel('이메일').fill(DEMO_USER.email)
  await form.getByLabel('비밀번호', { exact: true }).fill(DEMO_USER.password)
  await form.getByRole('button', { name: '로그인' }).click()
}

export async function loginFirst(page, next = '/') {
  await page.goto(`/login?next=${encodeURIComponent(next)}`)
  await login(page)
  await expect(page).not.toHaveURL(/\/login/)
}

// 토스트가 다 나타난 뒤(투명도 1)에 검사해야 대비가 정확하다
export async function toastSettled(page, text) {
  const t = page.locator('[data-sonner-toast]').filter(text ? { hasText: text } : {}).first()
  await expect(t).toBeVisible()
  await expect(t).toHaveCSS('opacity', '1')
  return t
}

// 창·드로어가 열리는 움직임이 끝난 뒤에 검사한다. 움직이는 중에는 반투명이라 axe가 대비를 낮게 잰다.
export async function animationsSettled(page) {
  // 무한 반복(스켈레톤 등)은 끝나지 않으니 뺀다
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getComputedTiming().endTime !== Infinity)
        .map((a) => a.finished.catch(() => {})),
    ),
  )
}
