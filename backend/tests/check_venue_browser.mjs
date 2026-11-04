// F-20~22 실제 API를 Chrome의 네트워크 경로로 호출한다. 목업 화면 E2E와는 별도 시험이다.
import assert from 'node:assert/strict';
import { chromium } from '../../frontend/node_modules/@playwright/test/index.mjs';

const [baseUrl, venueId, today] = process.argv.slice(2);
assert.match(baseUrl, /^http:\/\/127\.0\.0\.1:\d+$/);
assert.match(venueId, /^\d+$/);
assert.match(today, /^\d{4}-\d{2}-\d{2}$/);

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
  const slotsUrl = `${baseUrl}/venues/${venueId}/slots`;
  const slots = await page.goto(`${slotsUrl}?date=${today}`);
  assert.equal(slots.status(), 200);
  assert.deepEqual(await slots.json(), detail.slots);

  const tomorrow = new Date(`${today}T00:00:00Z`);
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  const future = await page.goto(`${slotsUrl}?date=${tomorrow.toISOString().slice(0, 10)}`);
  assert.equal(future.status(), 200);
  assert.deepEqual(await future.json(), detail.slots.map(slot => ({ ...slot, past: false })));

  for (const query of ['', '?date=2026-02-30', '?date=20261105']) {
    const invalid = await page.goto(`${slotsUrl}${query}`);
    assert.equal(invalid.status(), 400);
    const error = await invalid.json();
    assert.equal(error.code, 'VALIDATION');
    assert.equal(error.detail.fields[0].field, 'date');
  }
  const outside = await page.goto(`${slotsUrl}?date=0001-01-01`);
  assert.equal(outside.status(), 400);
  const rangeError = await outside.json();
  assert.equal(rangeError.code, 'OUT_OF_RANGE');
  assert.equal(rangeError.detail.reason, 'date');
  assert.match(rangeError.detail.min_date, /^\d{4}-\d{2}-\d{2}$/);
  assert.match(rangeError.detail.max_date, /^\d{4}-\d{2}-\d{2}$/);

  const missingSlots = await page.goto(`${baseUrl}/venues/9223372036854775807/slots?date=${today}`);
  assert.equal(missingSlots.status(), 404);
  assert.deepEqual(await missingSlots.json(), {
    code: 'VENUE_NOT_FOUND', message: '공간을 찾을 수 없어요.', detail: null,
  });
  const datesUrl = `${baseUrl}/venues/${venueId}/available-dates`;
  const available = await page.goto(datesUrl);
  assert.equal(available.status(), 200);
  const calendar = await available.json();
  assert.deepEqual(Object.keys(calendar).sort(), ['venue_id', 'offset', 'days', 'min_date', 'max_date', 'dates'].sort());
  assert.equal(calendar.venue_id, Number(venueId));
  assert.equal(calendar.offset, 0);
  assert.equal(calendar.days, 14);
  assert.equal(calendar.dates.length, 14);
  assert.deepEqual(calendar.dates[0], {
    date: today, free: detail.slots.filter(slot => !slot.taken).length, bookable: true,
  });
  function addDays(day, offset) {
    const result = new Date(`${day}T00:00:00Z`);
    result.setUTCDate(result.getUTCDate() + offset);
    return result.toISOString().slice(0, 10);
  }
  assert.deepEqual(calendar.dates, Array.from({ length: 14 }, (_, i) => ({
    date: addDays(today, i), free: 14, bookable: true,
  })));
  const previous = await page.goto(`${datesUrl}?offset=-14&days=2`);
  assert.equal(previous.status(), 200);
  assert.deepEqual((await previous.json()).dates, [-14, -13].map(offset => ({
    date: addDays(today, offset), free: 14, bookable: true,
  })));
  const maxOffset = Math.round((Date.parse(calendar.max_date) - Date.parse(today)) / 86400000);
  const lastPage = await page.goto(`${datesUrl}?offset=${maxOffset}`);
  assert.equal(lastPage.status(), 200);
  const lastCalendar = await lastPage.json();
  assert.equal(lastCalendar.days, 14);
  assert.deepEqual(lastCalendar.dates, [{ date: calendar.max_date, free: 14, bookable: true }]);
  for (const [query, field] of [['days=0', 'days'], ['days=32', 'days'], ['offset=1.5', 'offset']]) {
    const invalid = await page.goto(`${datesUrl}?${query}`);
    assert.equal(invalid.status(), 400);
    const error = await invalid.json();
    assert.equal(error.code, 'VALIDATION');
    assert.equal(error.detail.fields[0].field, field);
  }
  const outsideDates = await page.goto(`${datesUrl}?offset=${maxOffset + 1}`);
  assert.equal(outsideDates.status(), 400);
  assert.deepEqual(await outsideDates.json(), {
    code: 'OUT_OF_RANGE', message: '예약할 수 없는 날짜나 시간이에요.',
    detail: { reason: 'date', min_date: calendar.min_date, max_date: calendar.max_date },
  });
  const missingDates = await page.goto(`${baseUrl}/venues/9223372036854775807/available-dates`);
  assert.equal(missingDates.status(), 404);
  assert.deepEqual(await missingDates.json(), {
    code: 'VENUE_NOT_FOUND', message: '공간을 찾을 수 없어요.', detail: null,
  });
  process.stdout.write('F-20~22 Chrome: 실제 상세·시간 칸·날짜 200, 과거·마지막 페이지, 검증·범위 400, 공간 404 통과\n');
} finally {
  await browser.close();
}
