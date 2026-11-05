import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
let auth, users;
const body = {
  name: '새회원', email: 'new@example.com', password: 'abcd1234', phone: '010-1111-2222', birth: '990315', gender_digit: '1', terms_agreed: true, privacy_agreed: true, marketing_agreed: false
};
beforeEach(async () => {
  vi.useFakeTimers({
    toFake: ['Date']
  });
  vi.setSystemTime(new Date('2026-11-03T14:00:00+09:00'));
  vi.resetModules();
  auth = await import('../authApi');
  users = await import('../usersApi');
});
afterEach(() => vi.useRealTimers());
describe('F-01~04 회원 계약', () => {
  it('로그인 실패는 폼 오류 코드', async () => {
    await expect(auth.login({
      email: 'none@example.com', password: 'abcd1234'
    })).rejects.toMatchObject({
      status: 401, code: 'INVALID_CREDENTIALS'
    });
  });
  it.each([
    {
      terms_agreed: false
    }, {
      privacy_agreed: false
    }, {
      birth: '990230'
    }, {
      birth: '200101', gender_digit: '3'
    }, {
      gender_digit: '5'
    }, {
      password: '가'.repeat(25)
    }, {
      password: 'short'
    }
  ])('가입 필수 값 검사 %j', async (patch) => {
    await expect(auth.signup({
      ...body, ...patch
    })).rejects.toMatchObject({
      status: 400, code: 'VALIDATION', detail: {
        fields: expect.any(Array)
      }
    });
  });
  it('만 14세 경계와 사유', async () => {
    await expect(auth.signup({
      ...body, birth: '121104', gender_digit: '3'
    })).rejects.toMatchObject({
      detail: {
        fields: [{
            field: 'birth', reason: 'under_14'
          }]
      }
    });
    expect(await auth.signup({
      ...body, birth: '121103', gender_digit: '3'
    })).toMatchObject({
      user_id: 2
    });
  });
  it('가입·중복·탈퇴·이메일 재사용, 옛 토큰 거부', async () => {
    expect(await auth.signup(body)).toEqual({
      user_id: 2
    });
    await expect(auth.signup(body)).rejects.toMatchObject({
      code: 'EMAIL_TAKEN', status: 409
    });
    const { access_token } = await auth.login(body);
    await users.withdraw(access_token);
    expect(await auth.checkEmail(body.email)).toEqual({
      available: true
    });
    await expect(users.getMe(access_token)).rejects.toMatchObject({
      code: 'UNAUTHORIZED', status: 401
    });
    await expect(auth.login(body)).rejects.toMatchObject({
      code: 'INVALID_CREDENTIALS'
    });
    expect(await auth.signup(body)).toEqual({
      user_id: 3
    });
  });
  it('F-03 내 정보 수정·비밀번호 변경', async () => {
    await auth.signup(body);
    const { access_token } = await auth.login(body);
    expect(await users.updateMe({
      name: '바뀐이름', phone: '010-3333-4444', marketing_agreed: true
    }, access_token)).toMatchObject({
      name: '바뀐이름', phone: '010-3333-4444', marketing_agreed: true, email: body.email
    });
    await expect(users.updateMe({
      name: '  '
    }, access_token)).rejects.toMatchObject({
      code: 'VALIDATION', detail: {
        fields: [{
          field: 'name', reason: '이름을 입력해 주세요.'
        }]
      }
    });
    await expect(users.changePassword({
      current_password: '틀린비번1234', new_password: 'newpass1234'
    }, access_token)).rejects.toMatchObject({
      code: 'WRONG_PASSWORD', status: 400
    });
    await expect(users.changePassword({
      current_password: body.password, new_password: 'short'
    }, access_token)).rejects.toMatchObject({
      code: 'VALIDATION'
    });
    await users.changePassword({
      current_password: body.password, new_password: 'newpass1234'
    }, access_token);
    await expect(auth.login(body)).rejects.toMatchObject({
      code: 'INVALID_CREDENTIALS'
    });
    expect(await auth.login({
      ...body, password: 'newpass1234'
    })).toHaveProperty('access_token');
  });
  it('새 회원 비밀번호는 정확히 비교한다', async () => {
    await auth.signup(body);
    await expect(auth.login({
      ...body, password: 'wrong1234'
    })).rejects.toMatchObject({
      code: 'INVALID_CREDENTIALS'
    });
  });
});
