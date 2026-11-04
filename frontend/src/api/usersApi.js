import { USE_MOCK, mockDelay, request } from './client';
import { currentUser, fail, stamp } from './mock/db';
import { validation } from './authApi';
const publicUser = u => ({
  user_id: u.user_id, email: u.email, name: u.name, phone: u.phone, birth: u.birth, gender_digit: u.gender_digit, marketing_agreed: u.marketing_agreed
});
export async function getMe(token) {
  if (!USE_MOCK)
    return request('/users/me', {
      token
    });
  return mockDelay(publicUser(currentUser(token)));
}
export async function updateMe(body, token) {
  if (!USE_MOCK)
    return request('/users/me', {
      method: 'PATCH', body, token
    });
  const u = currentUser(token);
  validation(body.name !== undefined && !body.name.trim() ? [{
      field: 'name', reason: '이름을 입력해 주세요.'
    }] : []);
  for (const key of ['name', 'phone', 'marketing_agreed'])
    if (body[key] !== undefined)
      u[key] = body[key];
  return mockDelay(publicUser(u));
}
export async function changePassword(body, token) {
  if (!USE_MOCK)
    return request('/users/me/password', {
      method: 'PATCH', body, token
    });
  const u = currentUser(token);
  if ((u.password !== null && body.current_password !== u.password) || (u.password === null && body.current_password?.length < 8))
    fail('WRONG_PASSWORD', 400, '현재 비밀번호가 맞지 않아요.');
  validation(typeof body.new_password !== 'string' || body.new_password.length < 8 || new TextEncoder().encode(body.new_password).length > 72 ? [{
      field: 'new_password', reason: '8자 이상, 72바이트 이하로 입력해 주세요.'
    }] : []);
  u.password = body.new_password;
  return mockDelay(null);
}
export async function withdraw(token) {
  if (!USE_MOCK)
    return request('/users/me', {
      method: 'DELETE', token
    });
  const u = currentUser(token);
  Object.assign(u, {
    deleted: true, deleted_at: stamp(), name: '탈퇴회원', phone: null, birth: '000000', email: `deleted+${u.user_id}@invalid`, password: crypto.randomUUID(), marketing_agreed: false
  });
  return mockDelay(null);
}
