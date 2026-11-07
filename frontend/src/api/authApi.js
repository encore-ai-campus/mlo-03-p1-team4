import { USE_MOCK, mockDelay, request } from './client';
import { users, tokens, fail } from './mock/db';
import { todayISO } from '@/utils/date';
import { uuid } from '@/utils/uuid';
export function validation(fields) {
  if (fields.length)
    fail('VALIDATION', 400, '입력한 내용을 다시 확인해 주세요.', {
      fields
    });
}
export function validateSignup(b) {
  const fields = [];
  const bad = (field, reason) => fields.push({
    field, reason
  });
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(b.email ?? '') || b.email.length > 100)
    bad('email', '이메일 형식을 확인해 주세요.');
  if (typeof b.password !== 'string' || b.password.length < 8 || new TextEncoder().encode(b.password).length > 72)
    bad('password', '8자 이상으로 입력해 주세요. 너무 길면(영문 72자·한글 24자 초과) 쓸 수 없어요.');
  if (!b.name?.trim())
    bad('name', '이름을 입력해 주세요.');
  if (!/^01\d-?\d{3,4}-?\d{4}$/.test(b.phone ?? ''))
    bad('phone', '휴대폰 번호를 확인해 주세요.');
  if (!/^[1-4]$/.test(b.gender_digit ?? ''))
    bad('gender_digit', '1~4 중에서 골라 주세요.');
  const birth = `${['1', '2'].includes(b.gender_digit) ? '19' : '20'}${b.birth?.slice(0, 2)}-${b.birth?.slice(2, 4)}-${b.birth?.slice(4, 6)}`;
  const d = new Date(`${birth}T00:00:00Z`);
  if (!/^\d{6}$/.test(b.birth ?? '') || Number.isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== birth)
    bad('birth', '실제 생년월일 6자리를 입력해 주세요.');
  else {
    const today = todayISO();
    const age = Number(today.slice(0, 4)) - Number(birth.slice(0, 4)) - (today.slice(5) < birth.slice(5) ? 1 : 0);
    if (age < 14)
      bad('birth', 'under_14');
  }
  for (const key of ['terms_agreed', 'privacy_agreed'])
    if (b[key] !== true)
      bad(key, '필수 동의가 필요해요.');
  if (typeof b.marketing_agreed !== 'boolean')
    bad('marketing_agreed', '선택 동의를 확인해 주세요.');
  validation(fields);
}
export async function checkEmail(email) {
  if (!USE_MOCK)
    return request(`/auth/email-check?email=${encodeURIComponent(email)}`);
  validation(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? [] : [{
      field: 'email', reason: '이메일 형식을 확인해 주세요.'
    }]);
  return mockDelay({
    available: !users.some(u => !u.deleted && u.email === email)
  });
}
export async function signup(body) {
  if (!USE_MOCK)
    return request('/auth/signup', {
      method: 'POST', body
    });
  await mockDelay(null);
  validateSignup(body);
  if (users.some(u => !u.deleted && u.email === body.email))
    fail('EMAIL_TAKEN', 409, '이미 가입된 이메일이에요.');
  const user_id = Math.max(...users.map(u => u.user_id)) + 1;
  users.push({
    ...body, user_id, deleted: false
  });
  return {
    user_id
  };
}
export async function login(body) {
  if (!USE_MOCK)
    return request('/auth/login', {
      method: 'POST', body
    });
  await mockDelay(null);
  const u = users.find(u => !u.deleted && u.email === body.email);
  if (!u || typeof body.password !== 'string' || body.password.length < 8 || (u.password !== null && u.password !== body.password))
    fail('INVALID_CREDENTIALS', 401, '이메일 또는 비밀번호가 맞지 않아요.');
  const access_token = `mock-${uuid()}`;
  tokens.set(access_token, {
    user_id: u.user_id, expires: Date.now() + 3600000
  });
  return {
    access_token, token_type: 'bearer', expires_in: 3600
  };
}
