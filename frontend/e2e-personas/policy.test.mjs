import { test } from 'node:test'
import assert from 'node:assert/strict'
import { futureDate, allowedMutation, safeResult } from './policy.mjs'
import { personas, requiredFacilities } from './personas.mjs'
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import process from 'node:process'

test('서울 날짜 이후 다음 주의 지정 요일을 선택한다', () => {
  assert.equal(futureDate([1, 2, 3, 4, 5], new Date('2026-11-08T16:00:00Z')), '2026-11-16')
  assert.equal(futureDate([0], new Date('2026-11-08T16:00:00Z')), '2026-11-22')
})
test('대표 6명의 원본·조건·결제수단을 연결한다', () => {
  assert.equal(personas.length, 6)
  assert.equal(new Set(personas.map((p) => p.id)).size, 6)
  assert.equal(personas.filter((p) => p.browseOnly).length, 1)
  const names = { phone: '휴대폰 모의 결제', card: '카드 모의 결제', transfer: '계좌이체 모의 결제' }
  for (const p of personas) {
    const source = readFileSync(new URL(`../../simulator/locust/personas/${p.source}`, import.meta.url), 'utf8')
    assert.ok(source.includes(p.name))
    assert.ok(p.hours >= 1 && p.hours <= 4 && p.start + p.hours <= 23)
    if (!p.browseOnly) assert.ok(source.includes(names[p.method]), `${p.id}의 결제수단이 원본과 다름`)
  }
})
test('읽기는 이벤트만, 쓰기는 로그인과 자신의 예약 한 건만 허용한다', () => {
  assert.equal(allowedMutation('read', '/api/events', 'POST', null, false), true)
  assert.equal(allowedMutation('read', '/api/reservations', 'POST', null, false), false)
  assert.equal(allowedMutation('write', '/api/auth/login', 'POST', null, false), true)
  assert.equal(allowedMutation('write', '/api/reservations', 'POST', null, false), true)
  assert.equal(allowedMutation('write', '/api/reservations', 'POST', 42, true), false)
  assert.equal(allowedMutation('write', '/api/reservations/42/cancel', 'POST', 42, true), true)
  assert.equal(allowedMutation('write', '/api/reservations/43/cancel', 'POST', 42, true), false)
  assert.equal(allowedMutation('write', '/api/users', 'POST', null, false), false)
})
test('실패 보고서에 원시 오류와 입력값을 복사하지 않는다', () => {
  const result = safeResult('study', { status: 'failed', duration: 1, errors: [{ message: 'fill("private-password")', stack: 'private-token' }] })
  assert.ok(!JSON.stringify(result).includes('private-'))
})
test('실행 플래그가 있어도 합성 키가 없으면 브라우저 시작 전에 거절한다', () => {
  const config = new URL('../playwright.persona.config.js', import.meta.url).href
  const child = spawnSync(process.execPath, ['--input-type=module', '-e', `await import(${JSON.stringify(config)})`], {
    env: { ...process.env, PERSONA_RUN: '1', PERSONA_MODE: 'read', E2E_SYNTHETIC_KEY: '' }, encoding: 'utf8',
  })
  assert.notEqual(child.status, 0)
  assert.ok(child.stderr.includes('E2E_SYNTHETIC_KEY'))
})
test('쓰기 모드는 합성 계정 없이 시작할 수 없다', () => {
  const config = new URL('../playwright.persona.config.js', import.meta.url).href
  const child = spawnSync(process.execPath, ['--input-type=module', '-e', `await import(${JSON.stringify(config)})`], {
    env: { ...process.env, PERSONA_RUN: '1', PERSONA_MODE: 'write', E2E_SYNTHETIC_KEY: 'test-key', E2E_EMAIL: '', E2E_PASSWORD: '', E2E_CONFIRMED_PERSONAS: '' }, encoding: 'utf8',
  })
  assert.notEqual(child.status, 0)
  assert.ok(child.stderr.includes('합성 계정'))
})
test('필수 시설은 실제 DB 시드 명칭과 일치한다', () => {
  const seed = readFileSync(new URL('../../db/seed/facilities.csv', import.meta.url), 'utf8')
  for (const names of Object.values(requiredFacilities)) {
    for (const name of names) assert.ok(seed.includes(name), `${name} 시드 불일치`)
  }
  assert.ok(requiredFacilities.study.includes('의자/테이블'))
  assert.ok(requiredFacilities.work.includes('인터넷/WIFI'))
})
