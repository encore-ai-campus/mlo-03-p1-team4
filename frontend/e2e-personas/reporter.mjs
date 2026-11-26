import process from 'node:process'
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve, relative, isAbsolute } from 'node:path'
import { safeResult } from './policy.mjs'

export default class PersonaReporter {
  constructor() { this.rows = [] }
  onBegin(config, suite) {
    this.resultsDir = resolve(config.projects[0].outputDir)
    for (const test of suite.allTests()) process.stdout.write(`준비: ${test.title}\n`)
  }
  onTestEnd(test, result) {
    // Playwright의 실패 화면 텍스트에는 입력값이 남을 수 있어 원시 문맥을 비저장 처리한다.
    for (const attachment of result.attachments) {
      if (!attachment.path || !this.resultsDir) continue
      const child = relative(this.resultsDir, resolve(attachment.path))
      if (child && !child.startsWith('..') && !isAbsolute(child) && attachment.name === 'error-context') {
        writeFileSync(attachment.path, '개인정보 보호: 실패 화면 원문 비저장. persona-summary의 단계·상태를 확인하세요.\n')
      }
    }
    const row = safeResult(test.title, result)
    const summary = result.attachments.find((a) => a.name === 'persona-summary')
    if (summary?.body) row.summary = JSON.parse(summary.body.toString())
    // 녹화 영상은 페르소나 이름으로 videos/에 모은다(예: videos/study-read.webm).
    const video = result.attachments.find((a) => a.name === 'video' && a.path && existsSync(a.path))
    const output = process.env.PERSONA_REPORT_DIR
    if (video && output) {
      const dir = join(output, 'videos')
      mkdirSync(dir, { recursive: true })
      const name = `${row.summary?.persona || test.title.split(' · ')[0]}-${row.summary?.mode || 'run'}.webm`
      copyFileSync(video.path, join(dir, name))
      row.video = `videos/${name}`
    }
    this.rows.push(row)
    process.stdout.write(`${row.status}: ${row.title}\n`)
  }
  onError() { process.stderr.write('설정 또는 실행 오류: 키·계정 환경변수와 준비 문서를 확인하세요. 원시 오류 비저장.\n') }
  onEnd(result) {
    const output = process.env.PERSONA_REPORT_DIR
    if (!output) return
    mkdirSync(output, { recursive: true })
    const json = JSON.stringify({ status: result.status, tests: this.rows }, null, 2)
    const escape = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    writeFileSync(join(output, 'report.json'), json)
    writeFileSync(join(output, 'report.html'), `<!doctype html><html lang="ko"><meta charset="utf-8"><title>대표 페르소나 시험</title><h1>대표 페르소나 시험 · ${escape(result.status)}</h1><p>skip은 조건·재고 미충족이며 통과가 아닙니다. 원시 오류와 입력값은 기록하지 않습니다.</p><pre>${escape(json)}</pre></html>`)
  }
}
