// .mmd 파일들을 공식 mermaid(브라우저 렌더)로 PNG·SVG로 만든다.
// node docs/figures/tools/render_mermaid.cjs docs/figures docs/figures/src/*.mmd
const fs = require('fs');
const path = require('path');
const { chromium } = require(path.join(__dirname, '../../../frontend/node_modules/playwright'));
const MERMAID = 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js';
const [, , outDir, ...files] = process.argv;

const page = (src) => `<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:0;background:#fff;font-family:'Noto Sans KR','Malgun Gothic',sans-serif}#out{display:inline-block;padding:24px}</style>
<script src="${MERMAID}"></script></head><body><div id="out"></div>
<script>
mermaid.initialize({ startOnLoad: false, theme: 'base', securityLevel: 'loose',
  themeVariables: { fontFamily: "'Noto Sans KR','Malgun Gothic',sans-serif", fontSize: '15px',
    primaryColor: '#eef4ff', primaryBorderColor: '#5b7bd5', primaryTextColor: '#1f2430',
    lineColor: '#4b5563', secondaryColor: '#fff4ec', tertiaryColor: '#f6f7f9',
    actorBkg: '#eef4ff', actorBorder: '#5b7bd5', noteBkgColor: '#fff8d6', noteBorderColor: '#d4b106' },
  flowchart: { curve: 'basis', nodeSpacing: 40, rankSpacing: 50 },
  er: { fontSize: 13, layoutDirection: 'LR' },
  sequence: { mirrorActors: false, actorMargin: 60 } });
mermaid.render('g', ${JSON.stringify(src)}).then(({ svg }) => { const o = document.getElementById('out'); o.innerHTML = svg; const s = o.querySelector('svg'); const vb = s.viewBox.baseVal; s.style.maxWidth = 'none'; s.setAttribute('width', vb.width); s.setAttribute('height', vb.height); window.__svg = o.innerHTML; window.__done = true; })
  .catch((e) => { window.__err = String(e); window.__done = true; });
</script></body></html>`;

(async () => {
  const b = await chromium.launch();
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    const tmp = path.join(require('os').tmpdir(), 'spacecube_mmd_render.html');
    fs.writeFileSync(tmp, page(src));
    const p = await b.newPage({ viewport: { width: 2400, height: 1200 }, deviceScaleFactor: 2 });
    await p.goto('file:///' + tmp.replace(/\\/g, '/'));
    await p.waitForFunction(() => window.__done, null, { timeout: 30000 });
    const err = await p.evaluate(() => window.__err);
    const name = path.basename(f, '.mmd');
    if (err) { console.log('FAIL', name, err.slice(0, 200)); await p.close(); continue; }
    await p.evaluate(() => document.fonts.ready);
    fs.writeFileSync(path.join(outDir, name + '.svg'), await p.evaluate(() => window.__svg));
    await p.locator('#out').screenshot({ path: path.join(outDir, name + '.png') });
    console.log('ok', name);
    await p.close();
  }
  await b.close();
})();
