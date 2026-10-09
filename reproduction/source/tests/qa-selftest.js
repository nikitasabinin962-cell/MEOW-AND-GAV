// Запуск: NODE_PATH=<node_modules с playwright> node tests/qa-selftest.js
// самопроверка помощника overlaps: настоящие столкновения ловятся, ложные (перенос строки, закрытый details, обрезка, липкая шапка) — нет
const {launch, overlaps} = require('./lib/qa.js');
(async () => { const b = await launch(); const page = await b.newPage();
  await page.setContent(`<div id="r" style="font:14px sans-serif;width:600px">
    <div style="position:relative;height:40px"><span style="position:absolute;left:0;top:0">Столкновение один</span><span style="position:absolute;left:40px;top:4px">Столкновение два</span></div>
    <p style="width:200px"><span>Длинная подпись, которая переносится на вторую строку текста</span> <b>жирное</b></p>
    <details><summary>свёрнуто</summary><span style="position:absolute;left:0;top:0">скрытое в details</span></details>
    <div style="height:30px;overflow:hidden;position:relative"><span style="position:absolute;top:40px">обрезано прокруткой</span></div><span style="position:relative;top:-12px">под обрезанным</span>
    <div class="sc" style="height:60px;overflow:auto"><table><thead><tr><th style="position:sticky;top:0;background:#fff">Липкая шапка</th></tr></thead><tbody><tr><td>строка 1</td></tr><tr><td>строка 2</td></tr><tr><td>строка 3</td></tr></tbody></table></div>
    <div style="height:1200px"></div>
    <!-- ниже края окна: липкая шапка над строкой — не столкновение; настоящее столкновение — ловится -->
    <div class="sc" style="height:60px;overflow:auto"><table><thead><tr><th style="position:sticky;top:0;background:#fff">Нижняя липкая шапка</th></tr></thead><tbody><tr><td>нижняя строка 1</td></tr><tr><td>нижняя строка 2</td></tr><tr><td>нижняя строка 3</td></tr></tbody></table></div>
    <div style="position:relative;height:40px"><span style="position:absolute;left:0;top:0">Нижнее столкновение один</span><span style="position:absolute;left:40px;top:4px">Нижнее столкновение два</span></div>
  </div>`);
  await page.setViewportSize({ width: 800, height: 600 });
  await page.evaluate(() => document.querySelectorAll('.sc').forEach(d => d.scrollTop = 18));
  const o = await overlaps(page, '#r'); console.log(JSON.stringify(o.overlaps));
  const y0 = await page.evaluate(() => scrollY);
  const ok = o.overlaps.length === 2 && o.overlaps.every(x => /Столкновение|столкновение/.test(x.a + x.b)) && o.overlaps.some(x => /Нижнее/.test(x.a)) && y0 === 0;
  console.log(ok ? 'SELFTEST OK' : 'SELFTEST FAIL'); await b.close(); process.exit(ok ? 0 : 1); })();
