// 색 코드(#fff, #5638e8 …)를 tokens.css 밖에 직접 쓰지 않았는지 검사한다. ESLint는 <style> 안을 보지 않아서 따로 둔다.
// 예외: tokens.css(색을 정하는 곳), RoomArt.vue(일러스트 자체 팔레트), 테스트 파일.
// 실행: npm run lint:colors (npm run lint에 포함)
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, sep } from 'node:path'
import process from 'node:process'

const ROOT = new URL('../src', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const ALLOW = ['styles/tokens.css', 'components/domain/RoomArt.vue']
const HEX = /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return name === '__tests__' ? [] : walk(path)
    return /\.(vue|css|js)$/.test(name) ? [path] : []
  })
}

const problems = []
for (const file of walk(ROOT)) {
  const rel = relative(ROOT, file).split(sep).join('/')
  if (ALLOW.includes(rel)) continue
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((line, i) => {
      // 템플릿 id 참조(href="#intro")나 URL 조각은 색이 아니므로 건너뜀
      for (const m of line.matchAll(HEX)) {
        const before = line.slice(0, m.index)
        if (/(href|to)=["'`][^"'`]*$/.test(before) || /`#\$\{/.test(line.slice(m.index - 1))) continue
        problems.push(`src/${rel}:${i + 1}  ${m[0]}  → tokens.css 변수를 쓰세요`)
      }
    })
}

if (problems.length) {
  console.error(problems.join('\n'))
  console.error(`\n색 코드 ${problems.length}곳. 새 색이 필요하면 src/styles/tokens.css에 이름을 붙여 추가하세요.`)
  process.exit(1)
}
console.log('색 코드 검사 통과 (tokens.css 밖 0곳)')
