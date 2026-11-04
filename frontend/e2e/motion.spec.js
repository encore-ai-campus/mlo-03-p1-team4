// 움직임 규칙(2026-11-02 애니메이션 점검, emilkowalski/skills review-animations 기준)이 다시 깨지지 않게
import { test, expect } from '@playwright/test'
import { animationsSettled, fixClock, loginFirst } from './helpers'

test.beforeEach(async ({ page }) => fixClock(page))

// 요소에 걸린 CSS 애니메이션들의 키프레임 속성 이름 (offset 등 제외)
const animatedProps = (locator) =>
  locator.evaluate((el) =>
    el.getAnimations().flatMap((a) =>
      a.effect.getKeyframes().flatMap((k) => Object.keys(k).filter((p) => !['offset', 'computedOffset', 'easing', 'composite'].includes(p))),
    ),
  )

test('창은 닫힐 때 짧게 흐려진 뒤 사라진다', async ({ page }) => {
  await loginFirst(page, '/me?tab=completed')
  await page.getByRole('button', { name: '후기 쓰기' }).first().click()
  const dialog = page.getByRole('dialog', { name: '후기 쓰기' })
  await expect(dialog).toBeVisible()
  await animationsSettled(page)
  await page.keyboard.press('Escape')
  const closing = await page.locator('.dialog').evaluate((el) => el.getAnimations().map((a) => [a.animationName, a.effect.getTiming().duration]))
  expect(closing).toEqual([['dialog-out', 150]])
  await expect(dialog).toBeHidden()
})

test('폰 드로어도 닫힐 때 내려가며 사라진다', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', '드로어는 폰 화면에서만')
  await page.goto('/search')
  await page.getByRole('button', { name: /조건 바꾸기/ }).click()
  const drawer = page.getByRole('dialog', { name: '검색 조건' })
  await expect(drawer).toBeVisible()
  await animationsSettled(page)
  await page.keyboard.press('Escape')
  // 열림과 같은 키프레임 이름이면 reka가 움직임 없이 바로 지운다
  expect(await page.locator('.drawer').evaluate((el) => el.getAnimations().map((a) => a.animationName))).toEqual(['drawer-bottom-out'])
  await expect(drawer).toBeHidden({ timeout: 1000 })
  await expect(page.locator('.overlay')).toHaveCount(0)
})

// 카드에 호버(폰은 탭과 같은 효과)한 뒤 세로로 들린 px
async function hoverLift(page) {
  await page.goto('/')
  const card = page.locator('article.card').first()
  await expect(card).toBeVisible()
  await animationsSettled(page)
  await card.hover()
  await animationsSettled(page)
  return card.evaluate((el) => new DOMMatrix(getComputedStyle(el).transform).m42)
}

test('마우스 호버하면 카드가 3px 들린다', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', '마우스 화면')
  expect(await hoverLift(page)).toBe(-3)
})

test('폰에서는 탭해도 카드가 들린 채 남지 않는다', async ({ page }, info) => {
  test.skip(info.project.name !== 'mobile', '터치 화면')
  expect(await hoverLift(page)).toBe(0)
})

test.describe('움직임 줄이기', () => {
  test.use({ reducedMotion: 'reduce' })

  test('카드 등장은 흐려짐만, 기다림 없음', async ({ page }) => {
    await page.goto('/')
    const card = page.locator('article.card').nth(5)
    await expect(card).toBeVisible()
    expect(await card.evaluate((el) => getComputedStyle(el).animationDelay)).toBe('0s')
    expect(await animatedProps(card)).not.toContain('transform')
  })

  test('창 열림도 흐려짐만', async ({ page }) => {
    await loginFirst(page, '/me?tab=completed')
    await page.getByRole('button', { name: '후기 쓰기' }).first().click()
    await expect(page.getByRole('dialog')).toBeVisible()
    const props = await animatedProps(page.locator('.dialog'))
    expect(props).toContain('opacity')
    expect(props).not.toContain('transform')
  })
})
