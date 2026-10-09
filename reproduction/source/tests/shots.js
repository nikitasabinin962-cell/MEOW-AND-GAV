// Кадры-доказательства для REPORT_V4: обзоры 7 вкладок × 2 темы, исправленные состояния 11 скринов,
// дополнительные состояния и серии кадров движения. Запуск:
//   NODE_PATH=/opt/node-tools/node_modules node tests/shots.js [html] [фильтр-регэксп]
const path = require('path');
const fs = require('fs');
const { launch, openPage } = require('./lib/qa.js');
const ROOT = path.resolve(__dirname, '..');
const FILE = path.resolve(process.argv[2] || path.join(ROOT, 'econtypes.html'));
const ONLY = process.argv[3] ? new RegExp(process.argv[3]) : null;
const DIR = path.join(ROOT, 'docs', 'shots'), MDIR = path.join(ROOT, 'docs', 'motion');
fs.mkdirSync(DIR, { recursive: true }); fs.mkdirSync(MDIR, { recursive: true });
/* метка сборки у каждого кадра: SHA-1 снятого HTML-файла (первые 12 знаков) */
const BUILD = require('crypto').createHash('sha1').update(fs.readFileSync(FILE)).digest('hex').slice(0, 12);
const MINDEX = [];
const sleep = ms => new Promise(r => setTimeout(r, ms));
const TABS = [['out', 'Выводы и рекомендации'], ['map', 'Карта и сеть'], ['cmp', 'Сравнение районов'], ['corr', 'Корреляции'], ['types', 'Типы МО'], ['quality', 'Качество модели'], ['how', 'Как это работает']];
const INDEX = [];
const SHOTS = [];
const shot = (id, title, fn) => SHOTS.push({ id, title, fn });

async function save(page, id, title, { clip = null, el = null, full = false } = {}){
  const file = id + '.jpg';
  if (el) { const r = await page.evaluate(sel => { const e = document.querySelector(sel); e.scrollIntoView({ block: 'start' }); const nav = document.querySelector('nav.tabs').getBoundingClientRect().height; scrollBy(0, -nav - 6); const a = e.getBoundingClientRect(); return { x: a.left, y: Math.max(0, a.top), width: a.width, height: Math.min(a.height, innerHeight - Math.max(0, a.top)) }; }, el); await sleep(200); clip = r; }
  await page.screenshot({ path: path.join(DIR, file), type: 'jpeg', quality: 86, clip: clip || undefined, fullPage: full });
  INDEX.push({ id, file, title, build: BUILD }); console.log('  ✓', id);
}
/* лента кадров движения: кадры рядом (до 3 в ряд) с подписью времени после действия → docs/motion/<id>.jpg */
async function strip(page, id, title, bufs, labels){
  const b64 = await page.evaluate(async ([imgs, labels]) => {
    const bm = await Promise.all(imgs.map(async s => createImageBitmap(await (await fetch('data:image/png;base64,' + s)).blob())));
    const sc = Math.min(1, 560 / bm[0].width), w = Math.round(bm[0].width * sc), h = Math.round(bm[0].height * sc), pad = 10, lh = 24, cols = Math.min(bm.length, 3), rows = Math.ceil(bm.length / cols);
    const c = document.createElement('canvas'); c.width = cols * (w + pad) + pad; c.height = rows * (h + lh + pad) + pad; const g = c.getContext('2d');
    g.fillStyle = '#eef0f3'; g.fillRect(0, 0, c.width, c.height); g.font = '600 13px ' + getComputedStyle(document.body).fontFamily; g.fillStyle = '#1d232b';
    bm.forEach((b, k) => { const x = pad + (k % cols) * (w + pad), y = pad + Math.floor(k / cols) * (h + lh + pad); g.fillText(labels[k], x, y + 16); g.drawImage(b, x, y + lh, w, h); g.strokeStyle = '#c5cbd3'; g.strokeRect(x + .5, y + lh + .5, w - 1, h - 1); });
    return c.toDataURL('image/jpeg', .86).split(',')[1]; }, [bufs.map(b => b.toString('base64')), labels]);
  fs.writeFileSync(path.join(MDIR, id + '.jpg'), Buffer.from(b64, 'base64'));
  MINDEX.push({ id, file: id + '.jpg', title, frames: labels, build: BUILD }); console.log('  ✓ лента', id, '(' + bufs.length + ' кадров)');
}
async function mapReady(page){ await page.waitForFunction(() => typeof MAPVS !== 'undefined' && MAPVS.scenes.length && MAPVS.scenes[0].rendered > 2, null, { timeout: 20000 }); await sleep(700); }
const mapClip = page => page.evaluate(() => { const c = document.querySelector('.mapcard'); c.scrollIntoView({ block: 'start' }); scrollBy(0, -document.querySelector('nav.tabs').getBoundingClientRect().height - 6);
  const a = c.getBoundingClientRect(); return { x: a.left, y: Math.max(0, a.top), width: a.width, height: Math.min(a.height, innerHeight - Math.max(0, a.top)) }; });
const layer = (page, k) => page.evaluate(k => { $('#edgeLayer').value = k; $('#edgeLayer').dispatchEvent(new Event('input')); }, k);

/* ---------------- обзорные кадры: каждая вкладка в светлой и тёмной теме ---------------- */
for (const theme of ['light', 'dark']) TABS.forEach(([t, name], k) => shot(`o${k + 1}-${t}-${theme}`, `${k + 1}. ${name} — обзор, ${theme === 'light' ? 'светлая' : 'тёмная'} тема`, async b => {
  const { page, ctx } = await openPage(b, FILE, { theme, width: 1440, height: 1000, hash: '#' + t });
  if (t === 'map') await mapReady(page); else await sleep(1200);
  await page.evaluate(() => { const nav = document.querySelector('nav.tabs'); scrollTo(0, 0); });
  await save(page, `o${k + 1}-${t}-${theme}`, `${k + 1}. ${name} — обзор, ${theme === 'light' ? 'светлая' : 'тёмная'} тема`);
  await ctx.close();
}));

/* ---------------- карта: исправленные состояния скринов 1–4, 9–11 и фокус ---------------- */
shot('s01-split-region', 'Скрин 1: «Сеть и миграция» — две сцены, общий вид сверху, весь регион', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await page.click('[data-view="split"]'); await page.waitForFunction(() => MAPVS.scenes.length === 2 && MAPVS.scenes[1].rendered > 1); await sleep(1200);
  await save(page, 's01-split-region', 'Скрин 1: сопоставление «Сеть и миграция», общая камера', { clip: await mapClip(page) }); await ctx.close();
});
shot('s02-split-zoom-seams', 'Скрин 2: сильное приближение в сопоставлении — тонкие швы, контур объединения, без клиньев', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await page.click('[data-view="split"]'); await page.waitForFunction(() => MAPVS.scenes.length === 2 && MAPVS.scenes[1].rendered > 1);
  await page.evaluate(() => { select(findMO('Уфа')); setMapVS({ ...MAPVS.vs, longitude: 55.95, latitude: 54.75, zoom: 9.2 }, null); }); await sleep(1500);
  await save(page, 's02-split-zoom-seams', 'Скрин 2: приближение ×9 в сопоставлении', { clip: await mapClip(page) }); await ctx.close();
});
shot('s03-dark-split-nokey', 'Скрин 3: тёмная тема, две сцены одного языка, без подложки и без «API KEY REQUIRED»', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'dark', height: 1300, hash: '#map' }); await mapReady(page);
  await page.click('[data-view="split"]'); await page.waitForFunction(() => MAPVS.scenes.length === 2 && MAPVS.scenes[1].rendered > 1);
  await page.evaluate(() => select(findMO('Белорецкий'), true)); await sleep(1500);
  await save(page, 's03-dark-split-nokey', 'Скрин 3: тёмная тема, выбор одинаков в обеих сценах', { clip: await mapClip(page) }); await ctx.close();
});
shot('s04-migration', 'Скрин 4: миграционный прирост — дивергентная шкала вокруг нуля, легенда в ‰, связанный рейтинг', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await page.selectOption('#colorBy', 'f:migr_rate'); await page.evaluate(() => { setDim('2d', true); select(findMO('Иглинский')); fitView(REGION_BOUNDS, { pad: 24, duration: 0 }); }); await sleep(1500);
  await save(page, 's04-migration-map', 'Скрин 4: миграция на карте (вид сверху), выбран Иглинский', { clip: await mapClip(page) });
  await save(page, 's04-migration-rank', 'Скрин 4: связанный рейтинг с нулевой осью', { el: '#rankSec' }); await ctx.close();
});
shot('s09-light-3d-focus', 'Скрин 9: светлая 3D-карта — тонкие дуги, мягкий выбор, аккуратные маркеры, фокус связи A → B', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await layer(page, 'flow_rub'); await page.evaluate(() => select(findMO('Ишимбайский'), true)); await sleep(1200);
  await page.evaluate(() => { const it = MAPST.edges.find(x => N[x.e[0]].s === 'г. Уфа' && N[x.e[1]].s === 'Ишимбайский'); pinEdge(it); showBoth(); }); await sleep(2100);
  await save(page, 's09-light-3d-focus', 'Скрин 9: светлая 3D, связь г. Уфа → Ишимбайский', { clip: await mapClip(page) }); await ctx.close();
});
shot('s10-start-backbone', 'Скрин 10: стартовый каркас до клика — спокойная география, сильнейшие 30 из 62 с подписью правила', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await save(page, 's10-start-backbone', 'Скрин 10: стартовое состояние «Каркас сети»', { clip: await mapClip(page) }); await ctx.close();
});
shot('s11-leadlag-light', 'Скрин 11: lead_lag в светлой теме — световой след семейства, лаг выбранной связи в карточке', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await layer(page, 'lead_lag'); await page.evaluate(() => select(findMO('г. Стерлитамак'), true)); await sleep(1200);
  await page.evaluate(() => { const it = MAPST.edges[MAPST.edges.length - 1]; pinEdge(it); showBoth(); }); await sleep(2100);   // оба конца выбранной связи в кадре
  await save(page, 's11-leadlag-light', 'Скрин 11: опережение трат, выбранная связь — оба конца в кадре', { clip: await mapClip(page) }); await ctx.close();
});
shot('x-map-selections', 'Выбор: Уфа, Агидель, Межгорье, длинное имя, группа из 15 — светлая и тёмная', async b => {
  for (const theme of ['light', 'dark']) {
    const { page, ctx } = await openPage(b, FILE, { theme, height: 1300, hash: '#map' }); await mapReady(page);
    for (const [k, nm] of [['ufa', 'Уфа'], ['agidel', 'Агидель'], ['mezh', 'Межгорье']]) { await page.evaluate(nm => select(findMO(nm), true), nm); await sleep(1500); await save(page, `x-sel-${k}-${theme}`, `Выбор ${nm} (${theme})`, { clip: await mapClip(page) }); }
    const nm = await page.evaluate(() => { let j = 0; N.forEach((x, i) => { if (x.s.length > N[j].s.length) j = i; }); select(j, true); return N[j].s; }); await sleep(1500);
    await save(page, `x-sel-long-${theme}`, `Выбор: самое длинное имя — ${nm} (${theme})`, { clip: await mapClip(page) });
    await page.evaluate(() => { select(null); const ids = N.map((x, i) => i).sort((a, c) => N[c].pop - N[a].pop).slice(0, 15); showGroup(ids, '15 крупнейших по населению'); }); await sleep(1500);
    await save(page, `x-group15-${theme}`, `Группа из 15 МО без тяжёлых рамок (${theme})`, { clip: await mapClip(page) });
    await ctx.close();
  }
});
shot('x-map-fallback', '2D-резерв (?render=2d) и потеря контекста WebGL', async b => {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1300 } }); await ctx.route(/^https?:/, r => r.abort()); const page = await ctx.newPage();
  await page.goto('file://' + FILE + '?render=2d#map'); await sleep(2600); await page.evaluate(() => select(findMO('Уфа'), true)); await sleep(1300);
  await save(page, 'x-fallback-2d', 'Честный 2D-резерв на Leaflet: та же геометрия, выбор и связи', { clip: await mapClip(page) }); await ctx.close();
});
shot('x-map-matrix', 'Матрица связей и таблица всех записей слоя', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await layer(page, 'flow_rub'); await page.click('[data-view="matrix"]'); await sleep(1800);
  await save(page, 'x-matrix-flow', 'Матрица связей: потоки госзаказа (строки — поставщики, столбцы — заказчики)', { clip: await mapClip(page) });
  await page.click('[data-view="map"]'); await page.evaluate(() => { select(findMO('Агидель'), true); $('#etSec').open = true; }); await sleep(900);
  await save(page, 'x-edge-table', 'Таблица всех записей слоя для выбранного МО', { el: '#etSec' }); await ctx.close();
});
shot('x-map-mobile', 'Карта на 390 px: сцена, затем карточка МО', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', width: 390, height: 844, dpr: 2, hash: '#map' }); await mapReady(page);
  await page.evaluate(() => select(findMO('Уфа'), true)); await sleep(1500);
  await page.evaluate(() => { const c = document.querySelector('.mapcard'); c.scrollIntoView({ block: 'start' }); scrollBy(0, -document.querySelector('nav.tabs').getBoundingClientRect().height - 4); }); await sleep(900);   // в кадре — сама карта, а не шапка страницы
  await save(page, 'x-map-mobile', 'Карта, 390 px: сцена с выбранной Уфой');
  await page.evaluate(() => { MAPST.glow = false; MAPST.motion = false; mapAnimSync(); $('#panel').scrollIntoView(); }); await sleep(800);   // статичный кадр карточки: анимация на телефоне с DPR 2 мешала снимку
  await save(page, 'x-map-mobile-card', 'Карточка МО под картой, 390 px'); await ctx.close();
});

/* ---------------- серии кадров движения ---------------- */
shot('m-trail', 'Серия: световой след г. Уфа → Ишимбайский при неподвижной камере, пауза и возобновление', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'dark', height: 1300, hash: '#map' }); await mapReady(page);
  await layer(page, 'flow_rub'); await page.evaluate(() => select(findMO('Ишимбайский'), true)); await sleep(1200);
  await page.evaluate(() => { const it = MAPST.edges.find(x => N[x.e[0]].s === 'г. Уфа' && N[x.e[1]].s === 'Ишимбайский'); pinEdge(it); showBoth(); }); await sleep(900);
  const clip = await page.evaluate(() => { const a = $('#mapwrap').getBoundingClientRect(); return { x: a.left, y: a.top, width: a.width, height: a.height }; });
  const bufs = [], labels = [], t0 = Date.now();
  for (let k = 0; k < 6; k++) { bufs.push(await page.screenshot({ clip })); labels.push(`${k + 1}. ≈${((Date.now() - t0) / 1000).toFixed(1)} с`); await sleep(250); }
  await page.click('#motionChk'); await sleep(400);
  bufs.push(await page.screenshot({ clip })); labels.push('пауза: кадр A'); await sleep(700); bufs.push(await page.screenshot({ clip })); labels.push('пауза: кадр B (= A)');
  await strip(page, 'm-trail', 'Световой след г. Уфа → Ишимбайский при неподвижной камере; пауза — кадры A и B совпадают', bufs, labels);
  await ctx.close();
});

/* ---------------- серии кадров переходов вкладок (реальное время; снимок в SwiftShader занимает ~0,15–0,3 с) ---------------- */
const series = (id, title, hash, prep, act, sel, n = 4, theme = 'light') => shot(id, title, async b => {
  const { page, ctx } = await openPage(b, FILE, { theme, width: 1440, height: 1100, hash }); await sleep(2000);
  if (prep) await prep(page); await sleep(900);
  const clip = await page.evaluate(sel => { const e = document.querySelector(sel); e.scrollIntoView({ block: 'center' }); const a = e.getBoundingClientRect(); return { x: a.left, y: Math.max(0, a.top), width: a.width, height: Math.min(a.height, innerHeight - Math.max(0, a.top)) }; }, sel);
  const bufs = [await page.screenshot({ clip })], labels = ['до действия']; await sleep(300); const t0 = Date.now(); await act(page);
  for (let k = 0; k < n; k++) { const ms = Date.now() - t0; bufs.push(await page.screenshot({ clip })); labels.push(`≈${ms} мс после действия`); }
  await sleep(900); bufs.push(await page.screenshot({ clip })); labels.push('итог');
  await strip(page, id, title, bufs, labels); await ctx.close(); });
series('m-corr-bub2med', 'Корреляции: пузыри → медианы по типам', '#corr', null, p => p.click('#bMode [data-bm=med]'), '#bStage');
series('m-corr-med2dist', 'Корреляции: медианы → распределение по типам', '#corr', p => p.click('#bMode [data-bm=med]'), p => p.click('#bMode [data-bm=dist]'), '#bStage');
series('m-corr-dist2bub', 'Корреляции: распределение → пузыри', '#corr', p => p.click('#bMode [data-bm=dist]'), p => p.click('#bMode [data-bm=bub]'), '#bStage');
series('m-corr-lagsel', 'Лаги: выбор лага +2 мес', '#corr', p => p.evaluate(() => $('.cr-lagsec').scrollIntoView({ block: 'center' })), p => p.click('#lagCtl [data-k="5"]'), '.cr-lagmain', 3);
series('m-corr-lagintro', 'Лаги: вступительная анимация профиля (кнопка «показать заново»)', '#corr', p => p.evaluate(() => $('.cr-lagsec').scrollIntoView({ block: 'center' })), p => p.click('#lagReplay'), '.cr-lagmain', 4);
series('m-corr-bub2med-dark', 'Корреляции: пузыри → медианы по типам, тёмная тема', '#corr', null, p => p.click('#bMode [data-bm=med]'), '#bStage', 4, 'dark');
series('m-tree-expand-dark', 'Дерево: раскрытие ветви, тёмная тема', '#types', null, p => p.evaluate(() => { const t = TY.find(x => /Города/.test(x.name)); tyToggle(t.c, true); }), '#tree', 4, 'dark');
series('m-tree-expand', 'Дерево: раскрытие ветви «Города и промышленные центры»', '#types', null, p => p.evaluate(() => { const t = TY.find(x => /Города/.test(x.name)); tyToggle(t.c, true); }), '#tree');
series('m-tree-collapse', 'Дерево: свернуть все', '#types', p => p.click('#treeAll'), p => p.click('#treeNone'), '#tree');
series('m-quality-sort', 'Важность признаков: пересортировка по перестановочной важности', '#quality', null, p => p.click('#qlISeg [data-is=perm]'), '#q-imp', 4);


/* ---------------- вкладки: скрины 5–8, сравнение, дерево, агрегаты ---------------- */
const secShot = (id, title, hash, sel, prep, opts = {}) => shot(id, title, async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: opts.theme || 'light', width: opts.width || 1440, height: opts.height || 1100, hash }); await sleep(1800);
  if (prep) await prep(page); await sleep(opts.wait || 1500); await save(page, id, title, { el: sel }); await ctx.close(); });
secShot('s05-bubble-pop', 'Скрин 5: Bubble по умолчанию — площадь ∝ населению', '#corr', '#bubble', null);
secShot('s05-medians', 'Переход МО → медианы по типам (итог), длинные названия типов', '#corr', '#bubble', p => p.click('[data-bm="med"]'));
secShot('s05-distribution', 'Распределение по типам: точки МО, медиана и IQR', '#corr', '#bubble', p => p.click('[data-bm="dist"]'));
secShot('s06-lag', 'Скрин 6: профиль семи лагов с карточкой', '#corr', '.cr-lagsec', null);
secShot('s07-importance', 'Скрин 7: важность признаков — две выровненные dot/interval-диаграммы', '#quality', '#q-imp', null);
secShot('s08-tree-all', 'Скрин 8: дерево, всё раскрыто, подписи не пересекаются', '#types', '#typesTreeSec', p => p.click('#treeAll'), { height: 1400, wait: 2000 });
secShot('x-tree-dark', 'Дерево в тёмной теме, одна ветвь в фокусе', '#types', '#typesTreeSec', p => p.evaluate(() => { const g = document.querySelector('#tree [role=treeitem][aria-level="2"]'); g && g.dispatchEvent(new MouseEvent('click', { bubbles: true })); }), { theme: 'dark' });
secShot('x-cmp-ties', 'Сравнение: Кумертау, Салават, Бакалинский, Бирский, Благовещенский — совпавшие процентили разведены дорожками', '#cmp', '#cxProfSec', p => p.evaluate(() => { clearComparison(); ['Кумертау', 'Салават', 'Бакалинский', 'Бирский', 'Благовещенский'].forEach(n => addToComparison(findMO(n))); }), { height: 1300 });
secShot('x-cmp-missing', 'Сравнение: Межгорье и Куюргазинский — пропуски «н/д», ряд не соединяется через пропуски', '#cmp', '#cmpBody', p => p.evaluate(() => { clearComparison(); addToComparison(findMO('Межгорье')); addToComparison(findMO('Куюргазинский')); }), { height: 1500 });
secShot('x-types-flows', 'Типы МО: переходы между типами по кварталам (ТЗ 12.3), выбран Куюргазинский', '#types', '#typesFlowSec', p => p.evaluate(() => setSel(findMO('Куюргазинский'))), { height: 1300 });
shot('x-map-typechord', 'Матрица связей → «Типы × типы» (ТЗ 12.2): суммы госзаказа между типами', async b => {
  const { page, ctx } = await openPage(b, FILE, { theme: 'light', height: 1300, hash: '#map' }); await mapReady(page);
  await layer(page, 'flow_rub'); await page.click('[data-view="matrix"]'); await sleep(900); await page.click('[data-fm="types"]'); await sleep(1500);
  await page.click('.tch-tab td[data-a="4"][data-b="6"]'); await sleep(500);
  await save(page, 'x-map-typechord', 'Хорд-диаграмма сумм госзаказа между типами; выбрана пара 5 → 7', { clip: await mapClip(page) }); await ctx.close(); });
secShot('x-cmp-seasonality', 'Сравнение → «Сезонность 2 × 12» (ТЗ 12.4): Кумертау, Куюргазинский (пропуски), Межгорье (ряда нет), Салават; выбран март 2024', '#cmp', '#cxSpendSec', async p => { await p.evaluate(() => { clearComparison(); ['Кумертау', 'Куюргазинский', 'Межгорье', 'Салават'].forEach(s => addToComparison(findMO(s))); }); await sleep(1500); await p.evaluate(() => { $('#cxSs').open = true; }); await sleep(800); await p.click('#cxSs td[data-k="14"]'); }, { height: 1500 });
secShot('x-cmp-seasonality-dark', 'Сезонность 2 × 12 в тёмной теме', '#cmp', '#cxSpendSec', async p => { await p.evaluate(() => { clearComparison(); ['Кумертау', 'Куюргазинский', 'Салават', 'Бирский'].forEach(s => addToComparison(findMO(s))); }); await sleep(1500); await p.evaluate(() => { $('#cxSs').open = true; }); await sleep(800); }, { height: 1500, theme: 'dark' });
shot('x-cmp-mobile', 'Сравнение на 390 px', async b => { const { page, ctx } = await openPage(b, FILE, { width: 390, height: 844, dpr: 2, hash: '#cmp' }); await sleep(1200);
  await page.evaluate(() => { clearComparison(); ['Кумертау', 'Салават', 'Бирский'].forEach(n => addToComparison(findMO(n))); }); await sleep(1500);
  await page.evaluate(() => { const e = document.querySelector('#cmpSlots'); e.scrollIntoView({ block: 'start' }); scrollBy(0, -document.querySelector('nav.tabs').getBoundingClientRect().height - 8); }); await sleep(700);   // в кадре — районы и профиль, а не шапка страницы
  await save(page, 'x-cmp-mobile', 'Сравнение на 390 px: три района и начало профиля'); await ctx.close(); });

(async () => {
  const b = await launch(); const t0 = Date.now();
  for (const s of SHOTS) { if (ONLY && !ONLY.test(s.id)) continue; console.log(s.id, '—', s.title); try { await s.fn(b); } catch (e) { console.log('  ✗', e.message.split('\n')[0]); } }
  await b.close();
  const merge = (idx, add) => { let old = []; try { old = JSON.parse(fs.readFileSync(idx, 'utf8')); } catch (e) {}
    fs.writeFileSync(idx, JSON.stringify(old.filter(o => !add.some(n => n.id === o.id)).concat(add).sort((a, c) => a.id.localeCompare(c.id)), null, 1)); };
  merge(path.join(DIR, 'index.json'), INDEX); merge(path.join(MDIR, 'index.json'), MINDEX);
  console.log(`${INDEX.length} кадров → docs/shots/, ${MINDEX.length} лент движения → docs/motion/ за ${Math.round((Date.now() - t0) / 1000)} с; сборка ${BUILD}`);
})();
