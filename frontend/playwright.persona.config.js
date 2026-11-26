import process from 'node:process'
import { defineConfig } from '@playwright/test'

const running = process.env.PERSONA_RUN === '1'
const mode = process.env.PERSONA_MODE || 'read'
if (!['read', 'write'].includes(mode)) throw new Error('PERSONA_MODE는 read/write만 허용합니다.')
if (running && !process.env.E2E_SYNTHETIC_KEY) throw new Error('합성 키 E2E_SYNTHETIC_KEY가 필요합니다.')
if (running && mode === 'write' && (!process.env.E2E_EMAIL || !process.env.E2E_PASSWORD || !process.env.E2E_CONFIRMED_PERSONAS)) {
  throw new Error('쓰기에는 합성 계정과 E2E_CONFIRMED_PERSONAS 사전 조건 확인이 필요합니다.')
}
const baseURL = process.env.E2E_BASE_URL || 'http://192.168.0.218'
const url = new URL(baseURL)
if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('정문 origin 주소만 지정하세요.')
const output = process.env.PERSONA_REPORT_DIR || '../logs/playwright-personas/prepare'
// 녹화: 사용자(페르소나)마다 브라우저 화면을 영상 하나로 남긴다. 동시: 6명이 한꺼번에 접속한다.
const record = process.env.PERSONA_RECORD === '1'
const parallel = process.env.PERSONA_PARALLEL === '1'
const slowMo = Number(process.env.PERSONA_SLOWMO || (record ? 800 : 0))
// PERSONA_SET=500: 페르소나 500명 읽기 시험(persona500.spec.mjs). 동시 브라우저 수는 PERSONA_WORKERS(기본 8).
const set500 = process.env.PERSONA_SET === '500'
const workers = set500 ? Number(process.env.PERSONA_WORKERS || 8) : (parallel ? 6 : 1)
export default defineConfig({
  testDir: './e2e-personas', testMatch: set500 ? 'persona500.spec.mjs' : 'persona.spec.mjs',
  timeout: record ? 600000 : (set500 ? 60000 : 90000),
  // 동시 실행에서는 한 명이 실패해도 나머지 화면은 끝까지 진행·녹화한다.
  workers, retries: 0, maxFailures: set500 || parallel ? 0 : 1, fullyParallel: set500 || parallel,
  outputDir: `${output}/test-results`,
  reporter: [['./e2e-personas/reporter.mjs']],
  use: {
    baseURL, browserName: 'chromium', viewport: { width: 1280, height: 800 },
    locale: 'ko-KR', timezoneId: 'Asia/Seoul', actionTimeout: 10000,
    trace: 'off', screenshot: 'off', serviceWorkers: 'block',
    video: record ? { mode: 'on', size: { width: 1280, height: 800 } } : 'off',
    launchOptions: slowMo ? { slowMo } : {},
    // 합성 헤더는 시험의 동일 출처 요청에만 붙인다. 외부 글꼴 등에 키를 보내지 않는다.
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  },
})
