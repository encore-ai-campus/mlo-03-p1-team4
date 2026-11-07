import { createRequire } from 'node:module'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = process.env.SPACE_FRONTEND_DIR || resolve(here, '../../../frontend')
const { defineConfig } = createRequire(resolve(frontend, 'package.json'))('@playwright/test')
if (!process.env.SPACE_SYNTHETIC_KEY) throw new Error('합성 데이터 키가 필요합니다.')

export default defineConfig({
  testDir: here,
  testMatch: 'smoke.spec.mjs',
  workers: 1,
  retries: 0,
  timeout: 30000,
  outputDir: process.env.SPACE_REPORT_DIR + '/playwright-artifacts',
  reporter: [['list'], ['json', { outputFile: process.env.SPACE_REPORT_DIR + '/playwright.json' }]],
  use: {
    baseURL: process.env.SPACE_GATEWAY || 'http://192.168.0.218',
    channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome',
    headless: true,
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    trace: 'off', // 네트워크 trace에 합성 요청 키가 저장되지 않게 한다.
    screenshot: 'only-on-failure',
  },
})
