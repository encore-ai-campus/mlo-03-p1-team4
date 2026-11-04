import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
let api, catalog;
beforeEach(async () => {
  vi.useFakeTimers({
    toFake: ['Date']
  });
  vi.setSystemTime(new Date('2026-11-03T23:30:00+09:00'));
  vi.resetModules();
  api = await import('../venuesApi');
  catalog = await import('../catalogApi');
});
afterEach(() => vi.useRealTimers());
describe('F-10~22 공간 계약', () => {
  it('공간 응답은 새 필드만 반환', async () => {
    const { items } = await api.searchVenues();
    expect(items[0]).toMatchObject({
      venue_id: 1, name: expect.any(String), category: {
        code: 'studyroom'
      }, region: {
        sido: '서울'
      }, capacity_max: 6, image: 'art:group-0'
    });
    expect(items[0].room_id).toBeUndefined();
    expect((await catalog.getCategories()).map(c => c.code)).toContain('lectureroom');
  });
  it('지역은 공간이 있는 시도·시군구만', async () => {
    expect(await catalog.getRegions()).toEqual(['서울', '경기']);
    expect(await catalog.getRegions('경기')).toEqual([{
        region_id: 1, sigungu: '성남시'
      }]);
  });
  it('지난 칸도 예약 가능 날짜 free/bookable에 포함', async () => {
    const res = await api.getAvailableDates(2, -14);
    expect(res).toMatchObject({
      venue_id: 2, offset: -14, days: 14, min_date: '2025-11-03', max_date: '2027-11-03'
    });
    expect(res.dates[0]).toMatchObject({
      free: 14, bookable: true
    });
    const slots = await api.getSlots(2, '2026-11-02');
    expect(slots.every(s => s.past)).toBe(true);
    expect(slots.map(s => s.hour)).toEqual(Array.from({
      length: 14
    }, (_, i) => i + 9));
  });
  it('밤 히어로는 내일을 보여 주고 날짜 최대 경계는 잘라낸다', async () => {
    expect(await catalog.getTodaySlots()).toMatchObject({
      date: '2026-11-04', day: '내일'
    });
    expect((await api.getAvailableDates(1, 365)).dates).toHaveLength(1);
    await expect(api.getSlots(1, '2027-11-04')).rejects.toMatchObject({
      code: 'OUT_OF_RANGE'
    });
  });
  it('시설 id·시각·정렬 필터', async () => {
    const result = await api.searchVenues({
      category: 'studio', start_hour: 9, hours: 2, facilities: [1], sort: 'price'
    });
    expect(result.items.map(v => v.category.code)).toEqual(['studio', 'studio']);
    await expect(api.searchVenues({
      sort: 'bad'
    })).rejects.toMatchObject({
      code: 'VALIDATION'
    });
  });
});
