import { beforeEach, afterEach, expect, it, vi } from 'vitest';
let auth, api, token;
beforeEach(async () => {
  vi.useFakeTimers({
    toFake: ['Date']
  });
  vi.setSystemTime(new Date('2026-11-03T14:00:00+09:00'));
  vi.resetModules();
  auth = await import('../authApi');
  api = await import('../reservationsApi');
  token = (await auth.login({
    email: 'study@example.com', password: 'abcd1234'
  })).access_token;
});
afterEach(() => vi.useRealTimers());
it('F-02 로그인 토큰만 반환하며 60분 만료', async () => {
  const res = await auth.login({
    email: 'study@example.com', password: 'abcd1234'
  });
  expect(res.user).toBeUndefined();
  const users = await import('../usersApi');
  expect(await users.getMe(res.access_token)).toMatchObject({
    user_id: 1
  });
  vi.setSystemTime(Date.now() + 3600001);
  await expect(users.getMe(res.access_token)).rejects.toMatchObject({
    code: 'TOKEN_EXPIRED', status: 401
  });
});
it('F-30 한 번 확정·10분 재전송·내 부분충돌·환불', async () => {
  const body = {
    venue_id: 1, date: '2026-11-05', start_hour: 9, hours: 2, headcount: 2, method: 'card'
  };
  const r = await api.createReservation(body, token);
  expect(r).toMatchObject({
    status: 'confirmed', payment: {
      status: 'paid'
    }
  });
  expect((await api.createReservation(body, token)).reservation_id).toBe(r.reservation_id);
  await expect(api.createReservation({
    ...body, start_hour: 10
  }, token)).rejects.toMatchObject({
    status: 409, detail: {
      slots: [10], mine: true
    }
  });
  expect(await api.cancelReservation(r.reservation_id, token)).toMatchObject({
    status: 'cancelled', payment: {
      status: 'refunded'
    }
  });
});
it('F-30 지난 시간 완료·취소 불가·후기 작성', async () => {
  const r = await api.createReservation({
    venue_id: 1, date: '2026-11-02', start_hour: 9, hours: 2, headcount: 2, method: 'phone'
  }, token);
  expect(r.status).toBe('completed');
  await expect(api.cancelReservation(r.reservation_id, token)).rejects.toMatchObject({
    code: 'NOT_CANCELLABLE'
  });
  const reviews = await import('../reviewsApi');
  expect(await reviews.createReview(r.reservation_id, {
    rating: 5, content: '잘 이용했습니다'
  }, token)).toMatchObject({
    venue_id: 1, rating: 5
  });
});
