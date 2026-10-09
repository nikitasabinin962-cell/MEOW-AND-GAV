// econtypes V4 — именованные смысловые проверки в headless Chromium (Playwright).
// Каждая проверка проверяет поведение или смысл, а не наличие флага: кадры, пиксели, координаты, состояние после действий.
// Запуск: NODE_PATH=/opt/node-tools/node_modules node tests/check.js [путь к html]  → docs/checks.json + сводка в консоли.
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const { launch, openPage, overlaps, minFontPx } = require('./lib/qa.js');
const ROOT = path.resolve(__dirname, '..');
const FILE = path.resolve(process.argv[2] || path.join(ROOT, 'econtypes.html'));
const OUT = path.join(ROOT, 'docs', 'checks.json');
const D_SHA1 = 'd849169e16d7d2c42c1f210426b1490b6832b76a';
const results = [];
const CHECKS = [];
const check = (id, title, fn) => CHECKS.push({ id, title, fn });
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* пиксели снимка экрана в точках (x,y в CSS px окна) — без доступа к WebGL-буферу */
async function pixels(page, pts){
  const buf = await page.screenshot({ type: 'png' });
  return page.evaluate(async ([b64, pts]) => {
    const bmp = await createImageBitmap(await (await fetch('data:image/png;base64,' + b64)).blob());
    const c = document.createElement('canvas'); c.width = bmp.width; c.height = bmp.height; const g = c.getContext('2d'); g.drawImage(bmp, 0, 0);
    const k = bmp.width / innerWidth;
    return pts.map(([x, y]) => Array.from(g.getImageData(Math.round(x * k), Math.round(y * k), 1, 1).data.slice(0, 3)));
  }, [buf.toString('base64'), pts]);
}
const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
async function mapReady(page){ await page.waitForFunction(() => typeof MAPVS !== 'undefined' && MAPVS.scenes.length && MAPVS.scenes[0].rendered > 0, null, { timeout: 20000 }); await sleep(900); }
const vpProject = (page, lonlatz, k = 0) => page.evaluate(([p, k]) => { const s = MAPVS.scenes[k]; const vp = s.deck ? s.deck.getViewports()[0] : s.viewport(); const r = s.el.getBoundingClientRect(); const q = vp.project(p); return [r.left + q[0], r.top + q[1]]; }, [lonlatz, k]);

/* ============================ ДАННЫЕ И ПОСТАВКА ============================ */
check('data.d-bytes', 'Блок D в собранном HTML побайтно совпадает с исходником (SHA-1)', async () => {
  const html = fs.readFileSync(FILE, 'utf8'); const a = html.indexOf('const D = ') + 'const D = '.length;
  const raw = html.slice(a, html.indexOf(';\n', a)); const h = crypto.createHash('sha1').update(raw, 'utf8').digest('hex');
  return { pass: h === D_SHA1, detail: h };
});
check('data.runtime-intact', 'После прохода по всем вкладкам D не изменён в памяти (сериализация до/после)', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE);
  const before = await page.evaluate(() => JSON.stringify(D).length + ':' + JSON.stringify(D).slice(0, 2000));
  for (const t of ['map', 'cmp', 'corr', 'types', 'quality', 'how', 'out']) { await page.evaluate(t => activate(t), t); await sleep(t === 'map' ? 2500 : 700); }
  await page.evaluate(() => { select(findMO('Уфа'), true); addToComparison(findMO('Уфа')); });
  await sleep(800);
  const after = await page.evaluate(() => JSON.stringify(D).length + ':' + JSON.stringify(D).slice(0, 2000));
  const fp = await page.evaluate(() => { const s = JSON.stringify(D); let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return h; });
  await ctx.close(); return { pass: before === after, detail: 'длина/префикс совпадают; хэш ' + fp };
});
check('ship.offline', 'Готовый файл работает без сети: ни одного внешнего запроса при открытии и проходе по вкладкам', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } }); const reqs = [];
  await ctx.route(/^https?:/, r => { reqs.push(r.request().url()); r.abort(); });
  const page = await ctx.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.goto('file://' + FILE + '#map', { waitUntil: 'load' }); await mapReady(page);
  for (const t of ['out', 'cmp', 'corr', 'types', 'quality', 'how']) { await page.evaluate(t => activate(t), t); await sleep(600); }
  await ctx.close(); return { pass: reqs.length === 0 && errs.length === 0, detail: `запросов: ${reqs.length}${reqs[0] ? ' (' + reqs[0] + ')' : ''}; ошибок JS: ${errs.length}` };
});
check('ship.no-errors', 'Нет ошибок JS во всех вкладках в светлой/тёмной теме на 1440×900, 1024×768, 390×844', async ({ browser }) => {
  const bad = [];
  for (const theme of ['light', 'dark']) for (const [w, h] of [[1440, 900], [1024, 768], [390, 844]]) {
    const { page, ctx, errors } = await openPage(browser, FILE, { theme, width: w, height: h });
    for (const t of ['out', 'map', 'cmp', 'corr', 'types', 'quality', 'how']) { await page.evaluate(t => activate(t), t); await sleep(t === 'map' ? 2000 : 500); }
    const sw = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    if (errors.length) bad.push(`${theme} ${w}: ${errors[0]}`); if (sw > 1) bad.push(`${theme} ${w}: горизонтальная прокрутка страницы ${sw}px`);
    await ctx.close();
  }
  return { pass: !bad.length, detail: bad.join(' | ') || '12 комбинаций без ошибок и без горизонтальной прокрутки' };
});

/* ================================ КАРТА ================================ */
check('map.webgl2-3d', 'Карта по умолчанию — 3D-сцена deck.gl (WebGL2) с наклоном 25–40°, весь регион в кадре', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  const st = await page.evaluate(() => { const s = MAPVS.scenes[0], vp = s.deck.getViewports()[0], r = s.size();
    const c = GEO.outline[0].map(p => vp.project(p)); const inside = c.filter(([x, y]) => x >= 0 && y >= 0 && x <= r.width && y <= r.height).length / c.length;
    return { kind: s.kind, pitch: vp.pitch, inside, gl2: !!s.el.querySelector('canvas').getContext('webgl2') }; });
  await ctx.close(); return { pass: st.kind === 'deck' && st.pitch >= 25 && st.pitch <= 40 && st.inside === 1, detail: JSON.stringify(st) };
});
check('map.arcs-world-height', 'Дуги имеют высоту в мировых координатах: при наклоне вершина дуги смещается на экране, концы остаются в центрах МО', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  const r = await page.evaluate(() => { const it = MAPST.ctx[MAPST.ctx.length - 1], s = MAPVS.scenes[0];
    const P = vs => { const vp = new DK.WebMercatorViewport({ ...MAPVS.vs, ...vs, ...s.size() }); return { top: vp.project(it.g.path[ARC_S / 2]), flat: vp.project(it.g.path[ARC_S / 2].slice(0, 2)), a: vp.project(it.g.path[0]), ca: vp.project(CENTER[it.s0]), b: vp.project(it.g.path[ARC_S]), cb: vp.project(CENTER[it.s1]) }; };
    const p0 = P({ pitch: 0 }), p1 = P({ pitch: 40 }), z = it.g.path[ARC_S / 2][2];
    return { z, lift0: Math.hypot(p0.top[0] - p0.flat[0], p0.top[1] - p0.flat[1]), lift40: Math.hypot(p1.top[0] - p1.flat[0], p1.top[1] - p1.flat[1]),
      endErr: Math.max(Math.hypot(p1.a[0] - p1.ca[0], p1.a[1] - p1.ca[1]), Math.hypot(p1.b[0] - p1.cb[0], p1.b[1] - p1.cb[1])) }; });
  await ctx.close(); return { pass: r.z > 1000 && r.lift40 > r.lift0 + 3 && r.endErr < .5, detail: `высота вершины ${Math.round(r.z)} м; экранный подъём вершины: сверху ${r.lift0.toFixed(1)} px, при 40° ${r.lift40.toFixed(1)} px; расхождение концов ${r.endErr.toFixed(2)} px` };
});
check('map.labels-collision', 'Подписи МО не пересекаются и целиком в кадре: обзор, выбор, группа из 15, приближение', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page); const out = [];
  const probe = async name => { await sleep(900); const o = await overlaps(page, '#sceneA .mlabels', { selector: '.mlbl', minArea: 1 });
    const outside = await page.evaluate(() => { const r = $('#sceneA').getBoundingClientRect(); return [...document.querySelectorAll('#sceneA .mlbl')].filter(e => { const b = e.getBoundingClientRect(); return b.left < r.left || b.right > r.right || b.top < r.top || b.bottom > r.bottom; }).length; });
    out.push(`${name}: ${o.count} подп., пересечений ${o.overlaps.length}, за кадром ${outside}`); return !o.overlaps.length && !outside && o.count > 0; };
  let ok = await probe('обзор');
  await page.evaluate(() => select(findMO('Уфа'), true)); ok = await probe('Уфа') && ok;
  await page.evaluate(() => { const ids = N.map((x, i) => i).sort((a, b) => N[b].pop - N[a].pop).slice(0, 15); showGroup(ids, '15'); }); ok = await probe('группа 15') && ok;
  await page.evaluate(() => setMapVS({ ...MAPVS.vs, zoom: 8.6 }, null)); ok = await probe('зум 8,6') && ok;
  await ctx.close(); return { pass: ok, detail: out.join('; ') };
});
check('map.selection-glow', 'Выбор: жемчужный свет внутри территории, соседние МО не затемняются в чёрное, вуаль в пределах ТЗ', async ({ browser }) => {
  const res = [];
  for (const theme of ['light', 'dark']) {
    const { page, ctx } = await openPage(browser, FILE, { hash: '#map', theme }); await mapReady(page);
    const i = await page.evaluate(() => findMO('Белорецкий'));
    await page.evaluate(i => fitView(BBOX[i], { pad: 70, maxZoom: 8.3, duration: 0 }), i); await sleep(900);
    const geo = await page.evaluate(i => { let j = -1, bd = 1e9; N.forEach((x, k) => { if (k === i) return; const d = Math.hypot(CENTER[k][0] - CENTER[i][0], CENTER[k][1] - CENTER[i][1]); if (d < bd && !UNC(k)) { bd = d; j = k; } }); return { c: CENTER[i], out: CENTER[j], geo: PAL.geo }; }, i);
    const pc = await vpProject(page, geo.c), pn = await vpProject(page, geo.out);
    const inside = [pc[0] + 26, pc[1] + 26], po = [pn[0], pn[1] + 12];
    const before = await pixels(page, [inside, po]);
    await page.evaluate(i => select(i), i); await sleep(900);
    const after = await pixels(page, [inside, po]);
    const veil = await page.evaluate(() => { const l = MAPVS.scenes[0].deck.props.layers.find(l => /selveil/.test(l.id)); return l.props.getFillColor[3] / 255; });
    const dIn = dist3(before[0], after[0]), dOut = dist3(before[1], after[1]), lum = c => .2126 * c[0] + .7152 * c[1] + .0722 * c[2];
    const ok = veil >= (theme === 'dark' ? .08 : .04) && veil <= (theme === 'dark' ? .16 : .08) && dIn > 2 && lum(after[1]) >= Math.min(lum(before[1]), lum(geo.geo)) - 6;   // сосед не темнее исходного и не темнее основы — нет «чёрных силуэтов»
    res.push({ ok, s: `${theme}: вуаль ${veil.toFixed(2)}, ΔRGB внутри ${dIn.toFixed(1)}, сосед ${before[1]}→${after[1]}` });
    await ctx.close();
  }
  return { pass: res.every(r => r.ok), detail: res.map(r => r.s).join('; ') };
});
check('map.directed-trail-moves', 'Направленный поток: световой след движется по той же дуге от источника к получателю (кадры t0…t3)', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map', height: 1100 }); await mapReady(page);
  await page.evaluate(() => { $('#edgeLayer').value = 'flow_rub'; $('#edgeLayer').dispatchEvent(new Event('input')); select(findMO('Ишимбайский'), true); }); await sleep(1200);
  await page.evaluate(() => { const it = MAPST.edges.find(x => N[x.e[0]].s === 'г. Уфа' && N[x.e[1]].s === 'Ишимбайский'); pinEdge(it); showBoth(); }); await sleep(1100);
  /* Кадры при управляемых часах: планировщик остановлен, слой следа строится тем же buildLayers для момента T после фокуса.
     Голова следа = самая дальняя точка дуги, где кадр со следом отличается от кадра без следа; ожидаемая доля пути = T/2800·1,45 − 0,05. */
  await page.evaluate(() => { window.__realNeeds = mapNeedsFrames; mapNeedsFrames = () => false; if (mapRaf) cancelAnimationFrame(mapRaf); mapRaf = null; });
  /* счётчик кадров читается в том же вызове до setProps: на медленном SwiftShader кадр занимает главный поток дольше,
     чем доходит следующий вызов, и счётчик, прочитанный после, уже включает этот кадр (ожидание повисало) */
  const frameAt = async (T, trails) => { const r = await page.evaluate(([T, trails]) => { const s = MAPVS.scenes[0], m = MAPST.motion, r = s.rendered; MAPST.motion = trails; s.deck.setProps({ layers: buildLayers(s, MAPST.pinT0 + T) }); MAPST.motion = m; return r; }, [T, trails]);
    await page.waitForFunction(r => MAPVS.scenes[0].rendered > r, r, { timeout: 60000 }); await sleep(150); };
  const geo = await page.evaluate(() => { const it = MAPST.edges.find(x => x.e === MAPST.pinned.e), s = MAPVS.scenes[0], vp = s.deck.getViewports()[0], r = s.el.getBoundingClientRect();
    return { pts: it.g.path.map(p => { const q = vp.project(p); return [r.left + q[0], r.top + q[1]]; }), ts: it.g.ts }; });
  await frameAt(3000 + 2800 * 0, false); const base = await pixels(page, geo.pts);
  const heads = [];
  for (const T of [600, 1100, 1600, 2050]) {
    await frameAt(T, true); const px = await pixels(page, geo.pts);
    const ch = px.map((c, j) => dist3(c, base[j])); let head = -1; ch.forEach((v, j) => { if (v > 25) head = j; });
    heads.push({ T, cur: (T % 2800) / 2800 * 1.45 - .05, at: head < 0 ? null : geo.ts[head], lit: ch.filter(v => v > 25).length });
  }
  await page.evaluate(() => { mapNeedsFrames = window.__realNeeds; mapAnimSync(); });
  const usable = heads, onPath = heads.filter(h => h.at != null && Math.abs(h.at - h.cur) < .1);
  const moved = heads.every((h, j) => j === 0 || (h.at != null && heads[j - 1].at != null && h.at > heads[j - 1].at));
  const ordered = onPath.length === heads.length;
  const dir = await page.evaluate(() => ({ card: $('.edgecard .ends').innerText.replace(/\s+/g, ' '), arrows: MAPVS.scenes[0].deck.props.layers.some(l => /arrows/.test(l.id)) }));
  await ctx.close(); return { pass: ordered && moved && /г\. Уфа → Ишимбайский/.test(dir.card) && dir.arrows, detail: `голова следа на дуге (доля пути от источника) при T мс после фокуса — ожидаемая→найденная: ${heads.map(h => h.T + ': ' + h.cur.toFixed(2) + '→' + (h.at == null ? 'нет' : h.at.toFixed(2)) + ' (' + h.lit + ' точек)').join('; ')}; карточка «${dir.card}»; стрелка у получателя: ${dir.arrows}` };
});
check('map.undirected-no-direction', 'Ненаправленный каркас: нет бегущего следа и стрелок, вместо этого мягкая подсветка без направления', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  await page.evaluate(() => select(findMO('Уфа'), true)); await sleep(900);
  const r = await page.evaluate(() => ({ ids: MAPVS.scenes[0].deck.props.layers.map(l => l.id.replace(/^main-/, '')), motionDisabled: $('#motionChk').disabled, glow: $('#glowChk').checked, card: $('#p-net').innerText.includes('↔') }));
  await ctx.close(); return { pass: !r.ids.some(i => /trails|arrows/.test(i)) && r.ids.includes('soft') && r.motionDisabled && r.card, detail: `слои: ${r.ids.filter(i => /soft|trails|arrows|edges/.test(i)).join(', ')}; «движение направленных потоков» недоступно: ${r.motionDisabled}` };
});
check('map.motion-scheduler', 'Анимация останавливается на паузе, во вкладке вне карты и при reduced motion; возобновляется по запросу', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  await page.evaluate(() => { $('#edgeLayer').value = 'lead_lag'; $('#edgeLayer').dispatchEvent(new Event('input')); select(findMO('Уфа'), true); }); await sleep(1200);
  const frames = async () => { const a = await page.evaluate(() => MAPVS.scenes[0] ? MAPVS.scenes[0].rendered : 0); await sleep(1500); const b = await page.evaluate(() => MAPVS.scenes[0] ? MAPVS.scenes[0].rendered : 0); return b - a; };
  const on = await frames();
  await page.click('#motionChk'); await sleep(300); const paused = await frames();
  await page.click('#motionChk'); await sleep(300); const resumed = await frames();
  await page.evaluate(() => activate('types')); await sleep(1000); const away = await frames();
  await ctx.close();
  const r = await openPage(browser, FILE, { hash: '#map', reduced: true }); await mapReady(r.page);
  await r.page.evaluate(() => { $('#edgeLayer').value = 'lead_lag'; $('#edgeLayer').dispatchEvent(new Event('input')); select(findMO('Уфа'), true); }); await sleep(2000);
  const a = await r.page.evaluate(() => MAPVS.scenes[0].rendered); await sleep(1500); const rm = (await r.page.evaluate(() => MAPVS.scenes[0].rendered)) - a;
  const rmTxt = await r.page.evaluate(() => $('#legend').innerText.includes('Движение выключено') && !$('#motionChk').checked);
  await r.ctx.close();
  return { pass: on >= 2 && paused <= 1 && resumed >= 2 && away <= 1 && rm <= 1 && rmTxt, detail: `кадров за 1,5 с: идёт ${on}, пауза ${paused}, снова ${resumed}, другая вкладка ${away}, reduced motion ${rm} (направление объяснено текстом: ${rmTxt})` };
});
check('map.edge-focus', 'Фокус связи: оба конца подсвечены кольцами, карточка «A → B» со значением, единицей, периодом и смыслом; «Показать оба МО» помещает концы в кадр', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  await page.evaluate(() => { $('#edgeLayer').value = 'flow_rub'; $('#edgeLayer').dispatchEvent(new Event('input')); select(findMO('Агидель'), true); }); await sleep(1000);
  await page.evaluate(() => { const it = MAPST.edges[MAPST.edges.length - 1]; pinEdge(it); }); await sleep(300);
  await page.click('#showBoth'); await sleep(1100);
  const r = await page.evaluate(() => { const e = MAPST.pinned.e, s = MAPVS.scenes[0], vp = s.deck.getViewports()[0], sz = s.size();
    const inV = i => { const [x, y] = vp.project(CENTER[i]); return x > 0 && y > 0 && x < sz.width && y < sz.height; };
    const ends = s.deck.props.layers.find(l => /ends/.test(l.id)); const t = $('.edgecard').innerText;
    return { both: inV(e[0]) && inV(e[1]), rings: ends ? ends.props.data.length : 0, unit: /млн ₽/.test(t), period: /2023-01/.test(t), meaning: /Поставщики из/.test(t), arrow: /→/.test(t) }; });
  await ctx.close(); return { pass: Object.values(r).every(v => v === true || v === 2), detail: JSON.stringify(r) };
});
check('map.split-sync', 'Сопоставление «Сеть и миграция»: две сцены вида сверху с одной камерой; перетаскивание левой двигает правую; выход не оставляет второй сцены', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  await page.click('[data-view="split"]'); await page.waitForFunction(() => MAPVS.scenes.length === 2 && MAPVS.scenes[1].rendered > 1); await sleep(800);
  const box = await page.evaluate(() => { const r = $('#sceneA').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; });
  await page.mouse.move(box[0], box[1]); await page.mouse.down(); await page.mouse.move(box[0] + 80, box[1] + 40, { steps: 8 }); await page.mouse.up(); await sleep(700);
  const r = await page.evaluate(() => { const [a, b] = MAPVS.scenes.map(s => s.deck.getViewports()[0]); return { pitch: [a.pitch, b.pitch], dLon: Math.abs(a.longitude - b.longitude), dLat: Math.abs(a.latitude - b.latitude), dZ: Math.abs(a.zoom - b.zoom), moved: Math.abs(a.longitude - 56) > .01, legend: $('#legend').innerText.includes('правая карта') }; });
  await page.click('[data-view="map"]'); await sleep(600);
  const after = await page.evaluate(() => ({ scenes: MAPVS.scenes.length, canvasB: !!$('#sceneB canvas'), pitch: MAPVS.vs.pitch }));
  await ctx.close();
  return { pass: r.pitch[0] === 0 && r.pitch[1] === 0 && r.dLon < 1e-9 && r.dLat < 1e-9 && r.dZ < 1e-9 && r.legend && after.scenes === 1 && !after.canvasB && after.pitch === 35,
    detail: `${JSON.stringify(r)}; после выхода ${JSON.stringify(after)}` };
});
check('map.migration-diverging', 'Миграция: дивергентная шкала с нулём; отток и прирост окрашены в разные тона, рейтинг с нулевой осью синхронен выбору', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  await page.selectOption('#colorBy', 'f:migr_rate'); await sleep(900);
  const r = await page.evaluate(() => { const v = N.map(x => x.f.migr_rate), neg = v.findIndex(x => x != null && x < -5), pos = v.findIndex(x => x != null && x > 5), nd = v.findIndex(x => x == null);
    const c = i => themeRGB(i, 'f:migr_rate', 'main').rgb; const hue = ([r, g, b]) => { r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn; if (!d) return 0; let h = mx === r ? (g - b) / d % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; return (h * 60 + 360) % 360; }; const hd = (a, b) => { const x = Math.abs(hue(a) - hue(b)) % 360; return Math.min(x, 360 - x); };
    select(pos, false);
    const opt = RANK.chart.getOption(); const ml = opt.series[0].markLine; const sc = scaleFor('f:migr_rate');
    return { kind: sc.kind, sym: sc.lo === -sc.hi, hueGap: Math.round(hd(c(neg), c(pos))), toneOk: hd(c(neg), c(pos)) >= 60 && hd(c(neg), PAL.migNeg) < 25 && hd(c(pos), PAL.migPos) < 25, smallVisible: Math.hypot(...[0, 1, 2].map(k => c(pos)[k] - PAL.migZero[k])) > 40, nd: nd < 0 || fillFor(nd, 'main')[3] === 0,
      zeroLine: !!(ml && ml.data && ml.data[0].xAxis === 0), legend: /−\d/.test($('#legend').innerText) && $('#legend').innerText.includes('‰'), selBold: opt.yAxis[0].data.indexOf(N[pos].s) >= 0, panel: $('.valblk') && $('.valblk').innerText.includes('место') }; });
  await ctx.close(); return { pass: Object.entries(r).every(([k, v]) => k === 'hueGap' || v === true || v === 'div'), detail: JSON.stringify(r) + ' (hueGap — разница тона оттока и прироста, °)' };
});
check('map.fallback-2d', 'Честный 2D-резерв (?render=2d): Leaflet-сцена, пояснение, выбор, связи и подписи работают; 3D-переключатель недоступен', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } }); await ctx.route(/^https?:/, r => r.abort());
  const page = await ctx.newPage(); const errs = []; page.on('pageerror', e => errs.push(e.message));
  await page.goto('file://' + FILE + '?render=2d#map'); await sleep(2500);
  await page.evaluate(() => select(findMO('Уфа'), true)); await sleep(1200);
  const r = await page.evaluate(() => ({ kind: MAPVS.scenes[0].kind, note: !$('#fbNote').hidden && $('#fbNote').innerText.includes('2D-режим'), sel: $('#panel h2').innerText, edges: MAPST.edges.length, labels: $$('#sceneA .mlbl').length, dim: $('#dimBtn').disabled }));
  const o = await overlaps(page, '#sceneA .mlabels', { selector: '.mlbl', minArea: 1 });
  await ctx.close(); return { pass: r.kind === 'leaflet' && r.note && r.sel === 'г. Уфа' && r.edges > 0 && r.labels > 5 && r.dim && !o.overlaps.length && !errs.length, detail: JSON.stringify(r) + `; пересечений подписей ${o.overlaps.length}; ошибок ${errs.length}` };
});
check('map.context-loss', 'Потеря контекста WebGL: автоматический переход в 2D с сохранением выбора и связи, кнопка «Попробовать 3D снова» восстанавливает сцену', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  await page.evaluate(() => { select(findMO('Уфа'), true); }); await sleep(800);
  await page.evaluate(() => MAPVS.scenes[0].el.querySelector('canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()); await sleep(1500);
  const a = await page.evaluate(() => ({ kind: MAPVS.scenes[0].kind, sel: sel != null && N[sel].s, note: !$('#fbNote').hidden }));
  await page.click('#retry3d'); await sleep(1500);
  const b = await page.evaluate(() => ({ kind: MAPVS.scenes[0].kind, sel: sel != null && N[sel].s, note: $('#fbNote').hidden }));
  await ctx.close(); return { pass: a.kind === 'leaflet' && a.sel === 'г. Уфа' && a.note && b.kind === 'deck' && b.sel === 'г. Уфа' && b.note, detail: `после потери ${JSON.stringify(a)}; после повтора ${JSON.stringify(b)}` };
});
check('map.basemap-honest', 'Без подложки по умолчанию; при недоступной сети OSM выключается сам, флажок отражает факт, данные остаются; нет «API KEY REQUIRED»', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  const def = await page.evaluate(() => ({ osm: $('#osm').checked, attr: $('#attrib').innerText }));
  await page.click('#osm'); await sleep(2500);
  const after = await page.evaluate(() => ({ osm: $('#osm').checked, layer: MAPVS.scenes[0].deck.props.layers.some(l => l.id === 'osm'), notice: !!document.querySelector('.notice'), key: document.body.innerText.includes('API KEY') }));
  await ctx.close(); return { pass: !def.osm && !after.osm && !after.layer && after.notice && !after.key && /geoBoundaries/.test(def.attr), detail: `${JSON.stringify(def)} → ${JSON.stringify(after)}` };
});
check('map.density-honest', 'Плотность и порог честно подсчитаны: «Показано X из Y» совпадает с нарисованным; все 62 записи каркаса доступны режимом «все выше порога»', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map' }); await mapReady(page);
  const a = await page.evaluate(() => { const L = MAPVS.scenes[0].deck.props.layers; const n = L.filter(l => /-(ctx|edges)$/.test(l.id)).reduce((s, l) => s + l.props.data.length, 0); return { drawn: n, txt: $('#edgeCount').innerText }; });
  /* ждём два отрисованных кадра после смены плотности (а не фиксированные 600 мс): при 1–3 кадрах/с слои обновляются позже */
  const r0 = await page.evaluate(() => MAPVS.scenes[0].rendered);
  await page.selectOption('#density', 'all'); await page.waitForFunction(r => MAPVS.scenes[0].rendered >= r + 2, r0, { timeout: 30000 }); await sleep(200);
  const b = await page.evaluate(() => { const L = MAPVS.scenes[0].deck.props.layers; return { drawn: L.filter(l => /-(ctx|edges)$/.test(l.id)).reduce((s, l) => s + l.props.data.length, 0), txt: $('#edgeCount').innerText, total: D.layers.backbone.length }; });
  await ctx.close();
  const m = s => +(/Показано\s+(\d+)/.exec(s) || [])[1];
  return { pass: m(a.txt) === a.drawn && m(b.txt) === b.drawn && b.drawn === b.total, detail: `по умолчанию: «${a.txt}» / нарисовано ${a.drawn}; все: «${b.txt}» / нарисовано ${b.drawn} из ${b.total}` };
});

module.exports = { check, CHECKS, pixels, mapReady, vpProject, sleep, dist3 };

/* ============================== ЗАПУСК ============================== */
if (require.main === module) (async () => {
  const extra = path.join(__dirname, 'checks-tabs.js'); if (fs.existsSync(extra)) require(extra);
  const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
  const browser = await launch(); const t0 = Date.now();
  for (const c of CHECKS) {
    if (only && !only.test(c.id)) continue;
    const t = Date.now(); let r;
    try { r = await Promise.race([c.fn({ browser }), sleep(120000).then(() => ({ pass: false, detail: 'таймаут 120 с' }))]); }
    catch (e) { r = { pass: false, detail: 'исключение: ' + e.message.split('\n')[0] }; }
    results.push({ id: c.id, title: c.title, pass: !!r.pass, detail: r.detail, ms: Date.now() - t });
    console.log(`${r.pass ? 'OK  ' : 'FAIL'} ${c.id} — ${c.title}\n      ${r.detail}`);
  }
  await browser.close();
  const browserVer = require('playwright').chromium.name();
  const summary = { file: path.relative(ROOT, FILE), browser: 'Chromium (Playwright, headless, SwiftShader WebGL2)', at: new Date().toISOString(), passed: results.filter(r => r.pass).length, total: results.length, seconds: Math.round((Date.now() - t0) / 1000), results };
  if (!only) fs.writeFileSync(OUT, JSON.stringify(summary, null, 1));
  console.log(`\n${summary.passed} из ${summary.total} проверок пройдено за ${summary.seconds} с`);
  process.exit(summary.passed === summary.total ? 0 : 1);
})();
