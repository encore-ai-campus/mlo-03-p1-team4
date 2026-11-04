export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';
const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api';
let unauthorizedHandler = null;
let sessionId;
export function getSessionId() {
  if (!sessionId) {
    try {
      sessionId = sessionStorage.getItem('spacecube.event-session');
    }
    catch { /* 저장소 없이 동작 */
    }
    sessionId ||= crypto.randomUUID();
    try {
      sessionStorage.setItem('spacecube.event-session', sessionId);
    }
    catch { /* 저장소 없이 동작 */
    }
  }
  return sessionId;
}
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}
export class ApiError extends Error {
  constructor({ code = 'UNKNOWN', message = '요청을 처리하지 못했어요.', detail = null, status = 0 } = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.detail = detail;
    this.status = status;
  }
}
export function reportApiError(error) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('spacecube:api-error', { detail: error }));
  }
  if (error.status === 401 && error.code !== 'INVALID_CREDENTIALS')
    unauthorizedHandler?.(error);
  return error;
}
export async function request(path, { method = 'GET', body, token, headers = {}, keepalive = false, reportErrors = true } = {}) {
  const handle = (error) => reportErrors ? reportApiError(error) : error;
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method, keepalive, headers: {
        'Content-Type': 'application/json', ...headers, 'X-Session-Id': getSessionId(), ...(token && {
          Authorization: `Bearer ${token}`
        })
      }, ...(body !== undefined && {
        body: JSON.stringify(body)
      })
    });
  }
  catch {
    throw handle(new ApiError({
      code: 'NETWORK_ERROR', message: '인터넷 연결을 확인해 주세요.'
    }));
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok)
    throw handle(new ApiError({
      ...data, status: res.status
    }));
  return data;
}
export function mockDelay(value, ms = 350) {
  return new Promise(resolve => setTimeout(() => resolve(structuredClone(value)), import.meta.env.MODE === 'test' ? 0 : ms));
}
export function query(params = {}) {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params))
    if (value !== undefined && value !== null && value !== '' && value !== 'all' && value !== '전체' && value !== '전국')
      q.set(key, Array.isArray(value) ? value.join(',') : value);
  return q.toString();
}
