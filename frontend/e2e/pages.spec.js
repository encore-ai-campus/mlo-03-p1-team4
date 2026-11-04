// 화면 7개가 열리고, 가로 스크롤이 없고, 자동 접근성 검사(axe)에서 심각한 문제가 없는지.
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { animationsSettled, fixClock } from './helpers'

test.beforeEach(async ({ page }) => fixClock(page))

const PAGES = [
  { path: '/', heading: /필요한 공간을/ },
  { path: '/search', heading: /공간|빈 시간/ },
  { path: '/venues/1', heading: /관악구 스터디룸 1호/ },
  { path: '/login', heading: /필요한 시간만큼만/ },
  { path: '/reviews', heading: '후기 모아보기' },
]

for (const p of PAGES) {
  test(`${p.path} 열림 · 가로 스크롤 없음 · axe 심각 0건`, async ({ page }) => {
    await page.goto(p.path)
    await expect(page.getByRole('heading', { level: 1 }).first()).toContainText(p.heading)
    // 스켈레톤이 사라질 때까지 (목업 응답 대기)
    await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow, '가로로 넘치는 요소').toBeLessThanOrEqual(0)

    await animationsSettled(page) // 카드 스태거가 끝난 최종 상태로 잰다
    const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    const serious = violations.filter((v) => ['serious', 'critical'].includes(v.impact))
    expect(serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length}곳) ${v.nodes[0]?.target}`)).toEqual([])
  })
}

test('메인 첫 화면에 유형 바로가기까지 들어온다 (1280×650)', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', '데스크톱 기준 요구사항')
  await page.setViewportSize({ width: 1280, height: 650 })
  await page.goto('/')
  const bento = page.getByRole('heading', { name: '어떤 공간이 필요하세요?' })
  await expect(bento).toBeInViewport()
  const box = await page.locator('section', { has: bento }).boundingBox()
  expect(box.y + box.height).toBeLessThanOrEqual(650)
})
