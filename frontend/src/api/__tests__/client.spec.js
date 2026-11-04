import { afterEach, beforeEach, expect, it, vi } from 'vitest';
let client;
beforeEach(async () => {
  vi.resetModules();
  client = await import('../client');
});
afterEach(() => vi.unstubAllGlobals());
it('전체 요청은 같은 세션 헤더, 200 재전송 성공', async () => {
  const fetch = vi.fn().mockResolvedValue({
    ok: true, status: 200, json: () => Promise.resolve({
      reservation_id: 12
    })
  });
  vi.stubGlobal('fetch', fetch);
  expect(await client.request('/reservations', {
    token: 'abc'
  })).toEqual({
    reservation_id: 12
  });
  await client.request('/venues');
  expect(fetch.mock.calls[0][1].headers).toMatchObject({
    'X-Session-Id': client.getSessionId(), Authorization: 'Bearer abc'
  });
  expect(fetch.mock.calls[1][1].headers['X-Session-Id']).toBe(client.getSessionId());
});
it('401 중앙 처리와 로그인 폼 예외', async () => {
  const handler = vi.fn();
  client.setUnauthorizedHandler(handler);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false, status: 401, json: () => Promise.resolve({
      code: 'TOKEN_EXPIRED', message: '만료'
    })
  }));
  await expect(client.request('/users/me')).rejects.toMatchObject({
    code: 'TOKEN_EXPIRED'
  });
  expect(handler).toHaveBeenCalledOnce();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false, status: 401, json: () => Promise.resolve({
      code: 'INVALID_CREDENTIALS'
    })
  }));
  await expect(client.request('/auth/login')).rejects.toMatchObject({
    code: 'INVALID_CREDENTIALS'
  });
  expect(handler).toHaveBeenCalledOnce();
});
it('네트워크·HTML 오류와 204 처리', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
  await expect(client.request('/venues')).rejects.toMatchObject({
    code: 'NETWORK_ERROR'
  });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false, status: 502, json: () => Promise.reject(new SyntaxError())
  }));
  await expect(client.request('/venues')).rejects.toMatchObject({
    code: 'UNKNOWN', status: 502
  });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, status: 204
  }));
  expect(await client.request('/users/me', {
    method: 'DELETE'
  })).toBeNull();
});

it('관측 전송 실패는 전체 안내나 로그아웃을 일으키지 않는다', async () => {
  const handler = vi.fn();
  client.setUnauthorizedHandler(handler);
  const listener = vi.fn();
  window.addEventListener('spacecube:api-error', listener);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 401, json: () => Promise.resolve({ code: 'TOKEN_EXPIRED' }) }));
  await expect(client.request('/events', { method: 'POST', reportErrors: false })).rejects.toMatchObject({ code: 'TOKEN_EXPIRED' });
  expect(handler).not.toHaveBeenCalled();
  expect(listener).not.toHaveBeenCalled();
  window.removeEventListener('spacecube:api-error', listener);
});
