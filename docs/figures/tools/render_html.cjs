// HTML 그림(아키텍처)을 PNG로 만든다. 프론트에 설치된 Playwright(Chromium)를 쓴다.
// node docs/figures/tools/render_html.cjs docs/figures/src/architecture.html docs/figures/architecture.png 1800 1180
const path = require('path');
const { chromium } = require(path.join(__dirname, '../../../frontend/node_modules/playwright'));
const [, , html, png, w, h] = process.argv;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 2 });
  await p.goto('file:///' + path.resolve(html).replace(/\\/g, '/'));
  await p.waitForLoadState('networkidle');
  await p.evaluate(() => document.fonts.ready);
  const broken = await p.evaluate(() => [...document.images].filter((i) => !i.complete || !i.naturalWidth).map((i) => i.src));
  await p.screenshot({ path: png });
  await b.close();
  console.log('saved', png, broken.length ? `깨진 이미지: ${broken.join(', ')}` : '이미지 모두 정상');
})();
