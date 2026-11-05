// 화면 흐름 테스트 (Playwright). 개발 서버를 띄워 실제 브라우저로 누른다. 백엔드 없이 목업 데이터로 돈다.
// 데스크톱(1280)과 폰(375) 두 폭에서 같은 시나리오를 돌린다. 브라우저는 Chromium 하나만 쓴다.
import process from 'node:process'
import { defineConfig, devices } from '@playwright/test'

// 실제 서버로 돌릴 때(11-05 4-1): E2E_BASE_URL=http://gw 이면 개발 서버를 띄우지 않고 그 주소로 간다.
// E2E_SYNTHETIC_KEY가 있으면 모든 요청에 X-Synthetic: 1 + X-Synthetic-Key를 붙여 가상 데이터로 저장되게 한다(값은 저장소에 넣지 않는다).
const REMOTE = process.env.E2E_BASE_URL
const SYNTHETIC_KEY = process.env.E2E_SYNTHETIC_KEY

export default defineConfig({
  testDir: './e2e',
  timeout: 30 * 1000,
  expect: { timeout: 5000 },
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'line' : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: REMOTE || (process.env.CI ? 'http://localhost:4173' : 'http://localhost:5173'),
    extraHTTPHeaders: SYNTHETIC_KEY ? { 'X-Synthetic': '1', 'X-Synthetic-Key': SYNTHETIC_KEY } : undefined,
    trace: 'on-first-retry',
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    // 번들 브라우저가 없는 PC는 설치된 Chrome 등으로 검증할 수 있다.
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'], viewport: { width: 375, height: 812 } } },
  ],
  webServer: REMOTE
    ? undefined
    : {
        command: process.env.CI ? 'npm run build && npm run preview' : 'npm run dev',
        port: process.env.CI ? 4173 : 5173,
        reuseExistingServer: !process.env.CI,
      },
})
