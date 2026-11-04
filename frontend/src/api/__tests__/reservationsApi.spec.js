import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
let api, db, token, other, reviews;
const body = {
  venue_id: 1, date: '2026-11-05', start_hour: 9, hours: 2, headcount: 2, method: 'card'
};
beforeEach(async () => {
  vi.useFakeTimers({
    toFake: ['Date']
  });
  vi.setSystemTime(new Date('2026-11-03T14:00:00+09:00'));
  vi.resetModules();
  api = await import('../reservationsApi');
  db = await import('../mock/db');
  reviews = await import('../reviewsApi');
  const auth = await import('../authApi');
  token = (await auth.login({
    email: 'study@example.com', password: 'abcd1234'
  })).access_token;
  await auth.signup({
    name: '다른회원', email: 'other@example.com', password: 'abcd1234', phone: '010-1111-2222', birth: '990315', gender_digit: '1', terms_agreed: true, privacy_agreed: true, marketing_agreed: false
  });
  other = (await auth.login({
    email: 'other@example.com', password: 'abcd1234'
  })).access_token;
});
afterEach(() => vi.useRealTimers());
describe('F-30~41 결제와 후기', () => {
  it('한 번 확정·200 재전송·10분 뒤 내 충돌', async () => {
    const a = await api.createReservation(body, token);
    expect(a).toMatchObject({
      status: 'confirmed', payment: {
        status: 'paid', method: 'card'
      }, total_price: 20000
    });
    expect((await api.createReservation(body, token)).reservation_id).toBe(a.reservation_id);
    vi.setSystemTime(Date.now() + 600001);
    await expect(api.createReservation(body, token)).rejects.toMatchObject({
      status: 409, detail: {
        slots: [9, 10], mine: true
      }
    });
  });
  it('일부 내 겹침·남의 겹침 구분', async () => {
    await api.createReservation(body, token);
    await expect(api.createReservation({
      ...body, start_hour: 10
    }, token)).rejects.toMatchObject({
      code: 'SLOT_TAKEN', detail: {
        slots: [10], mine: true
      }
    });
    const error = await api.createReservation(body, other).catch((e) => e);
    expect(error).toMatchObject({ status: 409, code: 'SLOT_TAKEN', detail: { slots: [9, 10] } });
    expect(error.detail.mine).toBeUndefined();
  });
  it('남의 예약 404·취소 전액 환불·반납·반복취소', async () => {
    const a = await api.createReservation(body, token);
    await expect(api.getReservation(a.reservation_id, other)).rejects.toMatchObject({
      status: 404, code: 'RESERVATION_NOT_FOUND'
    });
    expect(await api.cancelReservation(a.reservation_id, token)).toMatchObject({
      status: 'cancelled', payment: {
        status: 'refunded'
      }
    });
    expect(db.isTaken(1, body.date, 9)).toBe(false);
    await expect(api.cancelReservation(a.reservation_id, token)).rejects.toMatchObject({
      code: 'ALREADY_CANCELLED'
    });
  });
  it('내 예약은 회원만·목록 계약·방금 예약 포함', async () => {
    await expect(api.getMyReservations()).rejects.toMatchObject({
      status: 401
    });
    const a = await api.createReservation(body, token);
    const list = await api.getMyReservations(token, {
      status: 'confirmed', page: 1, size: 20
    });
    expect(list).toMatchObject({
      page: 1, size: 20, total: 3
    });
    expect(list.items).toContainEqual(expect.objectContaining({
      reservation_id: a.reservation_id, can_cancel: true
    }));
  });
  it.each([
    [{
        date: '2028-01-01'
      }, 'OUT_OF_RANGE'], [{
        hours: 5
      }, 'OUT_OF_RANGE'], [{
        venue_id: 2, hours: 1
      }, 'OUT_OF_RANGE'], [{
        start_hour: 22, hours: 2
      }, 'OUT_OF_RANGE'], [{
        headcount: 99
      }, 'TOO_MANY_PEOPLE'], [{
        method: 'cash'
      }, 'INVALID_METHOD']
  ])('범위·인원·수단 %j', async (patch, code) => {
    await expect(api.createReservation({
      ...body, ...patch
    }, token)).rejects.toMatchObject({
      code, status: 400
    });
  });
  it('지난 예약 작성 당일부터 7일 후기 허용·중복·기간', async () => {
    const a = await api.createReservation({
      ...body, date: '2026-10-01'
    }, token);
    expect(a.status).toBe('completed');
    await expect(api.cancelReservation(a.reservation_id, token)).rejects.toMatchObject({
      code: 'NOT_CANCELLABLE'
    });
    const review = await reviews.createReview(a.reservation_id, {
      rating: 5, content: '잘 이용했습니다'
    }, token);
    await expect(reviews.createReview(a.reservation_id, {
      rating: 4, content: '중복'
    }, token)).rejects.toMatchObject({
      code: 'REVIEW_EXISTS', detail: {
        review_id: review.review_id
      }
    });
    expect((await api.getReservation(a.reservation_id, token)).review_id).toBe(review.review_id);
    const old = db.reservations.find(r => r.reservation_id === 1004);
    await expect(reviews.createReview(old.reservation_id, {
      rating: 5, content: '늦은 후기'
    }, token)).rejects.toMatchObject({
      code: 'REVIEW_PERIOD_OVER'
    });
  });
  it('후기 수정·삭제 작성자만, 탈퇴 후 익명 표기', async () => {
    const a = await api.createReservation({
      ...body, date: '2026-11-02'
    }, token);
    const r = await reviews.createReview(a.reservation_id, {
      rating: 5, content: '좋습니다'
    }, token);
    await expect(reviews.updateReview(r.review_id, {
      content: '변경'
    }, other)).rejects.toMatchObject({
      code: 'FORBIDDEN'
    });
    expect(await reviews.updateReview(r.review_id, {
      rating: 4
    }, token)).toMatchObject({
      rating: 4
    });
    const users = await import('../usersApi');
    await users.withdraw(token);
    expect((await reviews.getReviews()).items.find(x => x.review_id === r.review_id).author).toBe('탈퇴한 회원');
  });
});
