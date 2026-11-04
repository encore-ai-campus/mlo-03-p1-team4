// F-20 실제 API를 Chrome의 네트워크 경로로 호출한다. 목업 화면 E2E와는 별도 시험이다.
import assert from 'node:assert/strict';
import { chromium } from '../../frontend/node_modules/@playwright/test/index.mjs';

const [baseUrl, venueId] = process.argv.slice(2);
assert.match(baseUrl, /^http:\/\/127\.0\.0\.1:\d+$/);
assert.match(venueId, /^\d+$/);

const browser = await chromium.launch({
  headless: true,
  channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
});
try {
  const page = await browser.newPage({ locale: 'ko-KR', timezoneId: 'Asia/Seoul' });
  const response = await page.goto(`${baseUrl}/venues/${venueId}`);
  assert.equal(response.status(), 200);
  const detail = await response.json();
  assert.equal(detail.venue_id, Number(venueId));
  assert.equal(detail.name, '정책 검증용 가상 공간');
  assert.equal(detail.price_per_hour, 10000);
  assert.equal(detail.min_hours, 1);
  assert.equal(detail.image, 'art:group-0');
  assert.deepEqual(detail.images, ['art:group-0']);
  assert.equal(detail.is_new, true);
  assert.equal(detail.slots.length, 14);
  assert.deepEqual(detail.slots[0], { hour: 9, taken: false, past: true });
  assert.deepEqual(detail.slots.at(-1), { hour: 22, taken: false, past: false });
  assert.equal(Object.hasOwn(detail, 'source_id'), false);
  assert.equal(Object.hasOwn(detail, 'created_at'), false);
  assert.match(await page.locator('body').innerText(), /정책 검증용 가상 공간/);

  const missing = await page.goto(`${baseUrl}/venues/9223372036854775807`);
  assert.equal(missing.status(), 404);
  assert.deepEqual(await missing.json(), {
    code: 'VENUE_NOT_FOUND', message: '공간을 찾을 수 없어요.', detail: null,
  });
  process.stdout.write('F-20 Chrome: 실제 상세 200·응답 계약·없는 공간 404 통과\n');
} finally {
  await browser.close();
}
