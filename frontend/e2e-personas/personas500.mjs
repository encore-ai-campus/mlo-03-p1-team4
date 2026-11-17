// 페르소나 500명 Markdown에서 검색 조건(유형·지역·인원·검색 전용 여부)만 규칙으로 뽑는다.
// 자유문 전체를 해석하지 않는다. 뽑지 못한 값은 유형 폴더의 기본값을 쓰고 inferred에 표시한다.
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createHash } from 'node:crypto'

const ROOT = new URL('../../simulator/locust/personas/', import.meta.url)
const FOLDERS = {
  '학습·스터디형': { category: 'studyroom', people: 2 },
  '업무·협업형': { category: 'studyroom', people: 2 },
  '촬영·창작형': { category: 'studio', people: 3 },
  '강의·워크숍형': { category: 'lectureroom', people: 8 },
  '친목·기념일형': { category: 'partyroom', people: 6 },
  '검색전용': { category: 'studyroom', people: 2, browseOnly: true },
}
const CATEGORY_WORDS = [['스터디룸', 'studyroom'], ['스튜디오', 'studio'], ['강의실', 'lectureroom'], ['파티룸', 'partyroom'], ['카페', 'cafe']]
// 서비스에 공간이 있는 시·도(11-09 실서버: 서울·인천·부산·충남·경기)와, 없는 시·도를 옮길 가까운 지역.
export const SERVICE_SIDO = ['서울', '인천', '부산', '충남', '경기']
const SIDO_NAMES = [
  ['서울', '서울'], ['부산', '부산'], ['대구', '부산'], ['인천', '인천'], ['광주', '서울'], ['대전', '충남'],
  ['울산', '부산'], ['세종', '충남'], ['경기', '경기'], ['강원', '경기'], ['충북', '충남'], ['충청북', '충남'],
  ['충남', '충남'], ['충청남', '충남'], ['전북', '서울'], ['전라북', '서울'], ['전남', '서울'], ['전라남', '서울'],
  ['경북', '부산'], ['경상북', '부산'], ['경남', '부산'], ['경상남', '부산'], ['제주', '서울'],
]

function firstIndexOf(text, words) {
  let best = null
  for (const [word, value] of words) {
    const at = text.indexOf(word)
    if (at >= 0 && (best == null || at < best.at)) best = { at, word, value }
  }
  return best
}

export function parsePersona(folder, file, markdown) {
  const base = FOLDERS[folder]
  const inferred = []
  const title = (markdown.match(/^#\s*(.+)$/m) || [])[1] || file
  // 지역: 본문에서 처음 나오는 시·도 이름. 서비스에 없으면 가까운 서비스 지역으로 옮긴다.
  const sidoHit = firstIndexOf(markdown, SIDO_NAMES.map(([name, mapped]) => [name, { name, mapped }]))
  let sourceSido = sidoHit?.value.name ?? null
  let sido = sidoHit?.value.mapped ?? '서울'
  if (!sidoHit) inferred.push('sido')
  // 유형: '주요 공간' 줄이 있으면 그 값, 없으면 본문 첫 유형 단어, 그래도 없으면 폴더 기본값.
  const spaceLine = (markdown.match(/주요 공간[^\n]*/) || [])[0]
  const categoryHit = firstIndexOf(spaceLine || markdown, CATEGORY_WORDS)
  const category = categoryHit?.value ?? base.category
  if (!categoryHit) inferred.push('category')
  // 인원: '인원' 뒤 숫자 또는 'N명과/N명이' 같은 첫 인원 표현. 1~30명만 인정한다.
  const peopleMatch = markdown.match(/인원[^0-9\n]{0,12}(\d{1,2})\s*명/) || markdown.match(/(\d{1,2})\s*명(?:과|이|의|이서|으로|,| )/)
  let people = peopleMatch ? Number(peopleMatch[1]) : base.people
  if (!peopleMatch || people < 1 || people > 30) { people = base.people; inferred.push('people') }
  const browseOnly = Boolean(base.browseOnly) || /검색 전용|탐색만 하고/.test(markdown.split('\n').slice(0, 12).join('\n'))
  return {
    id: `${folder}/${file}`.replace(/\.md$/, ''), title: title.trim(), folder, file,
    sha256: createHash('sha256').update(markdown).digest('hex').slice(0, 16),
    category, sido, sourceSido, people, browseOnly, inferred,
  }
}

export function loadPersonas500() {
  const list = []
  for (const folder of Object.keys(FOLDERS)) {
    const dir = join(ROOT.pathname.replace(/^\/([A-Za-z]:)/, '$1'), folder)
    for (const file of readdirSync(decodeURIComponent(dir)).filter((f) => f.endsWith('.md') && f !== 'README.md').sort()) {
      list.push(parsePersona(folder, file, readFileSync(join(decodeURIComponent(dir), file), 'utf8')))
    }
  }
  return list
}
