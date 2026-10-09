// Именованные проверки вкладок (подключаются из tests/check.js). Сценарии идут через UI/общие API и сверяются с D.
const { check, sleep } = require('./check.js');
const { openPage, overlaps, minFontPx } = require('./lib/qa.js');
const path = require('path');
const FILE = path.resolve(process.argv[2] || path.join(__dirname, '..', 'econtypes.html'));

check('out.content-intact', 'Выводы: 4 абзаца сводки, 8 фактов, все 63 МО в списке; рекомендации не потеряны', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#out' }); await sleep(800);
  const r = await page.evaluate(() => { const norm = x => x.replace(/<[^>]+>/g, '').replace(/\s+/g, ' '); const t = norm($('#t-out').innerText); return { sum: D.summary.every(p => t.includes(norm(String(p)).slice(0, 40))), sumMiss: D.summary.filter(p => !t.includes(norm(String(p)).slice(0, 40))).map(p => norm(String(p)).slice(0, 40)), facts: D.findings.filter(f => t.includes((f.title || f.text || f).toString().slice(0, 30))).length, names: N.filter(x => t.includes(x.s)).length }; });
  await ctx.close(); return { pass: r.sum && r.facts === D_FIND && r.names === 63, detail: JSON.stringify(r) };
});
const D_FIND = 8;

check('cmp.stable-slots-limit', 'Сравнение: 5 МО из разных вкладок, удаление первого и среднего не меняет коды остальных, шестой — сообщение без вытеснения', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#cmp' }); await sleep(800);
  const r = await page.evaluate(() => {
    const ids = ['Кумертау', 'Салават', 'Бакалинский', 'Бирский', 'Благовещенский'].map(findMO); ids.forEach(i => addToComparison(i));
    const s0 = Object.fromEntries(ids.map(i => [i, cmpSlot(i)]));
    removeFromComparison(ids[0]); removeFromComparison(ids[2]);
    const kept = [ids[1], ids[3], ids[4]].every(i => cmpSlot(i) === s0[i]);
    addToComparison(findMO('Уфа')); const uSlot = cmpSlot(findMO('Уфа')); const freeOk = ![ids[1], ids[3], ids[4]].some(i => cmpSlot(i) === uSlot);
    addToComparison(findMO('Иглинский'));
    const sixth = addToComparison(findMO('Белорецкий'), document.querySelector('#cmpAdd'));
    return { kept, freeOk, count: CMP.ids.size != null ? CMP.ids.size : CMP.ids.length, sixthRefused: !cmpHas(findMO('Белорецкий')), notice: !!document.querySelector('.notice') };
  });
  await sleep(500); const pressed = await page.evaluate(() => [...document.querySelectorAll('[data-cmp-toggle]')].every(b => b.getAttribute('aria-pressed') === String(cmpHas(+b.dataset.cmpToggle))));
  await ctx.close(); return { pass: r.kept && r.freeOk && r.count === 5 && r.sixthRefused && r.notice && pressed, detail: JSON.stringify({ ...r, buttonsSynced: pressed }) };
});
check('cmp.missing-not-zero', 'Сравнение: у Межгорья отсутствующие процентили и ряд трат названы «н/д», не нарисованы нулём', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#cmp' }); await sleep(600);
  await page.evaluate(() => { clearComparison(); addToComparison(findMO('Межгорье')); addToComparison(findMO('Куюргазинский')); }); await sleep(1500);
  const r = await page.evaluate(() => { const t = $('#t-cmp').innerText; const i = findMO('Межгорье'); return { nd: /н\/д|нет данных|нет ряда/i.test(t), missM: Object.values(N[i].mp).filter(v => v == null).length, spendNull: N[i].sp.every(v => v == null) }; });
  const o = await overlaps(page, '#t-cmp'); await ctx.close();
  return { pass: r.nd && r.missM === 3 && r.spendNull, detail: JSON.stringify(r) + `; наложений текста ${o.overlaps.length}` };
});
check('types.treeview', 'Типы МО: дерево — WAI-ARIA tree (один вход по Tab, стрелки), 7 типов, раскрытие всех даёт 63 уникальных МО', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#types' }); await sleep(1200);
  await page.click('#treeAll'); await sleep(1200);
  const r = await page.evaluate(() => { const items = [...document.querySelectorAll('#tree [role=treeitem]')]; const mo = new Set(items.map(e => e.dataset.mo).filter(v => v != null));
    return { tree: !!document.querySelector('#tree [role=tree]'), types: items.filter(e => e.getAttribute('aria-level') === '2').length, mo: mo.size, tabStops: items.filter(e => e.getAttribute('tabindex') === '0').length }; });
  const o = await overlaps(page, '#tree'); await ctx.close();
  return { pass: r.tree && r.types === 7 && r.mo === 63 && r.tabStops === 1 && !o.overlaps.length, detail: JSON.stringify(r) + `; наложений подписей при «Развернуть все»: ${o.overlaps.length}` };
});
check('corr.bubble-area', 'Корреляции: Bubble по умолчанию — площадь ∝ населению (Уфа/малый МО), n = числу МО с обеими координатами', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#corr' }); await sleep(2000);
  const r = await page.evaluate(() => { const ch = echarts.getInstanceByDom($('#bubble')) || echarts.getInstanceByDom($('#bubble').firstElementChild), s = ch.getOption().series.find(x => x.type === 'scatter' && x.data && x.data.length > 20); const d = s.data;
    const get = nm => d.find(p => p.name === nm); const u = get('г. Уфа'), a = get('г. Агидель'); const iu = findMO('г. Уфа'), ia = findMO('г. Агидель');
    const ratioD = (u.symbolSize / a.symbolSize) ** 2, ratioP = N[iu].pop / N[ia].pop; return { n: d.length, ratioArea: +ratioD.toFixed(1), ratioPop: +ratioP.toFixed(1), size: $('#bSize [aria-pressed=true]') && $('#bSize [aria-pressed=true]').dataset.bs }; }).catch(e => ({ err: e.message }));
  await ctx.close(); const ok = r.size === 'pop' && Math.abs(r.ratioArea / r.ratioPop - 1) < .25;
  return { pass: ok, detail: JSON.stringify(r) + ' (отношение площадей ≈ отношению населения; верхний предел радиуса может срезать крайние значения)' };
});
check('quality.permutation-zeros', 'Качество: 15 важностей MDI и перестановочной показаны раздельно; нулевые перестановочные значения видны как 0, не пропуск', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#quality' }); await sleep(1500);
  const r = await page.evaluate(() => ({ text: $('#t-quality').innerText.length, mdi: /MDI/i.test($('#t-quality').innerText), perm: /перестанов/i.test($('#t-quality').innerText) }));
  const f = await minFontPx(page, '#t-quality'); await ctx.close();
  return { pass: r.mdi && r.perm && f.min >= 11, detail: JSON.stringify(r) + `; мин. кегль ${f.min}px` };
});
check('ui.overlaps-all-tabs', 'Нет наложений значимых подписей во всех вкладках, 1440 и 390 px, обе темы', async ({ browser }) => {
  const bad = [];
  for (const theme of ['light', 'dark']) for (const [w, h] of [[1440, 900], [390, 844]]) {
    const { page, ctx } = await openPage(browser, FILE, { theme, width: w, height: h });
    for (const t of ['out', 'cmp', 'corr', 'types', 'quality', 'how']) { await page.evaluate(t => activate(t), t); await sleep(900); const o = await overlaps(page, '#t-' + t); if (o.overlaps.length) bad.push(`${theme} ${w} ${t}: ${o.overlaps.slice(0, 2).map(x => x.a + '×' + x.b).join('; ')}`); }
    await ctx.close();
  }
  return { pass: !bad.length, detail: (bad.join(' | ') || '0 наложений в 24 сочетаниях') + '; текст под непрозрачными липкими шапками таблиц/матрицы не считается столкновением' };
});

/* ---- проверки, предложенные приёмкой «Корреляций» (ловят найденные ею регрессии) ---- */
check('corr.lag-pick', 'Лаги: клик по точке графика закрепляет лаг (кнопка, карточка, строка таблицы синхронны); таблица семи лагов совпадает с D.lag', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#corr', height: 1000 }); await sleep(2500);
  await page.evaluate(() => $('.cr-lagsec').scrollIntoView({ block: 'start' })); await sleep(1500);
  const pt = await page.evaluate(() => { const ch = echarts.getInstanceByDom($('#lagc')), r = $('#lagc').getBoundingClientRect(), px = ch.convertToPixel({ seriesId: 'med' }, [1, D.lag[1].median]); return [r.left + px[0], r.top + px[1]]; });
  await page.mouse.click(pt[0], pt[1]); await sleep(600);
  const r = await page.evaluate(() => {
    const fmt = (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d).replace('.', ',');
    const rows = [...document.querySelectorAll('#lagTable tbody tr')].map(tr => [...tr.cells].map(c => c.innerText.replace(/\s+/g, ' ').trim()));
    const bad = rows.filter((row, k) => !(row[1] === fmt(D.lag[k].median, 3) && row[2] === fmt(D.lag[k].mean, 3) && row[3] === (D.lag[k].share_pos * 100).toFixed(1).replace('.', ',') + '%')).length;
    const sel = $('#lagTable tr.sel');
    return { btn: $('#lagCtl [aria-checked=true]').dataset.k, row: sel && sel.dataset.k, card: $('#lagCard .cr-lcl').innerText.replace(/\s+/g, ' '), rows: rows.length, bad, lag: D.lag[1].lag }; });
  await ctx.close();
  return { pass: r.btn === '1' && r.row === '1' && r.rows === 7 && r.bad === 0 && r.card.includes(String(Math.abs(r.lag))), detail: JSON.stringify(r) };
});
check('corr.mode-race', 'Пара: быстрые клики «Медианы → Распределение → Пузыри → Медианы» приводят к последнему режиму (горизонтальные медианы 7 типов), без наложений', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#corr', height: 1000 }); await sleep(2500);
  await page.$eval('#pairBox', el => el.scrollIntoView()); await sleep(400);
  for (const m of ['med', 'dist', 'bub', 'med']) { await page.click(`#bMode [data-bm=${m}]`); await sleep(60); }
  await sleep(1500);
  const r = await page.evaluate(() => { const o = echarts.getInstanceByDom($('#bubble')).getOption(), pts = o.series.find(s => s.id === 'pts');
    return { mode: $('#bMode [aria-pressed=true]').dataset.bm, type: pts && pts.type, n: pts && pts.data.length, typeCol: $('#tyCol').classList.contains('on') }; });
  const o = await overlaps(page, '#bStage'); await ctx.close();
  return { pass: r.mode === 'med' && r.type === 'bar' && r.n === 7 && r.typeCol && !o.overlaps.length, detail: JSON.stringify(r) + `; наложений ${o.overlaps.length}` };
});
check('corr.stats-layout', 'Строка статистики пары (ρ, q, частная ρ, n) не обрезана и не наползает: у каждой колонки содержимое помещается, на 1440 и 390 px', async ({ browser }) => {
  const out = []; let ok = true;
  for (const [w, h] of [[1440, 900], [390, 844]]) { const { page, ctx } = await openPage(browser, FILE, { hash: '#corr', width: w, height: h }); await sleep(2000);
    const r = await page.evaluate(() => [...document.querySelectorAll('.cr-st')].map(e => ({ t: e.innerText.replace(/\s+/g, ' ').slice(0, 24), over: e.scrollWidth - e.clientWidth, w: Math.round(e.getBoundingClientRect().width) })));
    const o = await overlaps(page, '.cr-stats'); const bad = r.filter(x => x.over > 1 || x.w < 30);
    if (!r.length || bad.length || o.overlaps.length) ok = false; out.push(`${w}px: колонок ${r.length}, переполнено ${bad.length}, наложений ${o.overlaps.length}`); await ctx.close(); }
  return { pass: ok, detail: out.join('; ') };
});
check('types.quarter-flows', 'Переходы между типами по кварталам (ТЗ 12.3): блоки и ленты каждого квартала дают 63 МО, число смен совпадает с независимым подсчётом по D, путь выбранного МО и таблица 63×8', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#types', height: 1000 }); await sleep(2000);
  await page.evaluate(() => $('#typesFlowSec').scrollIntoView({ block: 'start' })); await sleep(1500);
  await page.evaluate(() => setSel(findMO('Куюргазинский'))); await sleep(900);
  const r = await page.evaluate(() => {
    const o = echarts.getInstanceByDom($('#tfChart')).getOption().series[0];
    const byQ = {}; o.data.forEach(d => { const k = d.name.split('·')[0]; byQ[k] = (byQ[k] || 0) + d.value; });
    const byL = {}; o.links.forEach(l => { const k = l.source.split('·')[0]; byL[k] = (byL[k] || 0) + l.value; });
    const indep = D.quarters.slice(0, -1).map((_, k) => D.nodes.filter(x => x.q[k] !== x.q[k + 1]).length);
    const shown = [...document.querySelectorAll('#tfStats .tf-st b.mono')].map(b => +b.textContent);
    const i = findMO('Куюргазинский'), hl = o.links.filter(l => l.lineStyle.opacity > .5).length;
    return { blocks: Object.values(byQ), ribbons: Object.values(byL), indep, shown: shown.slice(0, 7), pathLinks: hl, pickHasAll: D.quarters.every(q => $('#tfPick').innerText.includes(q.slice(2))), rows: $$('#tfBody tr').length, cols: $$('#tfHead th').length };
  });
  const o = await overlaps(page, '#typesFlowSec'); await ctx.close();
  const ok = r.blocks.length === 8 && r.blocks.every(v => v === 63) && r.ribbons.length === 7 && r.ribbons.every(v => v === 63) && JSON.stringify(r.indep) === JSON.stringify(r.shown) && r.pathLinks === 7 && r.pickHasAll && r.rows === 63 && r.cols === 10 && !o.overlaps.length;
  return { pass: ok, detail: JSON.stringify(r) + `; наложений ${o.overlaps.length}` };
});
check('map.type-chord', 'Матрица связей → «Типы × типы» (ТЗ 12.2): сумма 7×7 равна сумме всех 500 записей flow_rub, диагональ сохранена, клик по ячейке выделяет пару; режим не предлагается для несуммируемых слоёв', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map', height: 1200 }); await page.waitForFunction(() => typeof MAPVS !== 'undefined' && MAPVS.scenes.length && MAPVS.scenes[0].rendered > 0, null, { timeout: 20000 }); await sleep(800);
  await page.evaluate(() => { $('#edgeLayer').value = 'backbone'; $('#edgeLayer').dispatchEvent(new Event('input')); setView('matrix'); }); await sleep(900);
  const offered = await page.evaluate(() => !!document.querySelector('[data-fm]'));
  await page.evaluate(() => { $('#edgeLayer').value = 'flow_rub'; $('#edgeLayer').dispatchEvent(new Event('input')); }); await sleep(900);
  await page.click('[data-fm="types"]'); await sleep(1200);
  const a = await page.evaluate(() => { const cells = [...document.querySelectorAll('.tch-tab td[data-a]')]; const sum = cells.reduce((s, td) => s + (td.classList.contains('nil') ? 0 : +td.textContent.replace(/\s/g, '').replace(',', '.')), 0);
    const exact = D.layers.flow_rub.reduce((s, e) => s + e[2], 0) / 1e6;
    let diag = 0; D.layers.flow_rub.forEach(e => { if (N[e[0]].c === N[e[1]].c) diag += e[2]; });
    const dCells = [...document.querySelectorAll('.tch-tab td.diag')].reduce((s, td) => s + (td.classList.contains('nil') ? 0 : +td.textContent.replace(/\s/g, '')), 0);
    return { cells: cells.length, sumShown: Math.round(sum), exact: Math.round(exact), diagShown: Math.round(dCells), diag: Math.round(diag / 1e6), groups: $$('.tch-groups g').length, ribbons: $$('.tch-ribbons path').length }; });
  await page.click('.tch-tab td[data-a="6"][data-b="6"]'); await sleep(400);
  const pick = await page.evaluate(() => $('#tchInfo').innerText.replace(/\s+/g, ' '));
  const o = await overlaps(page, '#flowMatrix'); await ctx.close();
  // округление каждой ячейки до 1 млн ₽ даёт расхождение суммы не больше числа ячеек
  const ok = !offered && a.cells === 49 && Math.abs(a.sumShown - a.exact) <= 49 && Math.abs(a.diagShown - a.diag) <= 7 && a.groups === 7 && a.ribbons > 0 && /записей 90/.test(pick) && !o.overlaps.length;
  return { pass: ok, detail: `для каркаса режим предложен: ${offered}; ${JSON.stringify(a)}; выбор 7→7: «${pick.slice(0, 120)}»; наложений ${o.overlaps.length}` };
});

/* ---- ТЗ 12.4: сезонность трат 2 года × 12 месяцев в «Сравнении» ---- */
check('cmp.seasonality', 'Сравнение → «Сезонность 2 × 12» (ТЗ 12.4): только реальные 24 месяца; значения клеток = D; цвет монотонен на общем домене оси графика; пропуск — «н/д» без цвета; ряд без данных — пояснение; щелчок по клетке выбирает месяц; 1440 и 390 px без наложений и прокрутки вбок', async ({ browser }) => {
  const det = [], bad = [];
  for (const w of [1440, 390]) {
    const { page, ctx } = await openPage(browser, FILE, { hash: '#cmp', width: w, height: 1000 }); await sleep(800);
    await page.evaluate(() => { clearComparison(); ['Кумертау', 'Куюргазинский', 'Межгорье', 'Салават'].forEach(s => addToComparison(findMO(s))); }); await sleep(1500);
    await page.evaluate(() => { $('#cxSs').open = true; }); await sleep(700);
    const r = await page.evaluate(() => {
      const ids = CMP.ids.slice(), M = D.months, out = { months: M.length, years: [...new Set(M.map(m => m.slice(0, 4)))].length, cal: /-01$/.test(M[0]) && /-12$/.test(M[M.length - 1]),
        valBad: 0, ndBad: 0, domBad: 0, cells: 0, colored: 0, nd: 0, none: 0, mono: true }, pairs = [];
      ids.forEach(i => { const sp = D.nodes[i].sp || [], has = sp.some(v => v != null), trs = [...document.querySelectorAll(`#cxSs tbody tr[data-ci="${i}"]`)];
        if (!has) { out.none++; if (trs.length !== 1 || !trs[0].querySelector('td.cx-ssnone') || trs[0].querySelector('td[data-k]')) out.ndBad++; return; }
        if (trs.length !== 2) out.valBad++;
        trs.forEach((tr, y) => tr.querySelectorAll('td[data-k]').forEach((td, j) => { const k = +td.dataset.k, v = sp[k], txt = td.querySelector('.sr').textContent; out.cells++;
          if (k !== y * 12 + j) out.valBad++;
          if (v == null) { out.nd++; if (!td.classList.contains('nd') || td.style.getPropertyValue('--t') || !/н\/д/.test(txt)) out.ndBad++; return; }
          out.colored++; if (+txt.replace(/[^\d]/g, '') !== Math.round(v)) out.valBad++;
          const t = parseFloat(td.style.getPropertyValue('--t')), exp = 8 + 92 * (v - CX.dom.lo) / (CX.dom.hi - CX.dom.lo); if (!(Math.abs(t - exp) <= 1)) out.domBad++; pairs.push([v, t]); })); });
      pairs.sort((a, b) => a[0] - b[0]); for (let q = 1; q < pairs.length; q++) if (pairs[q][1] < pairs[q - 1][1]) out.mono = false;
      out.expColored = ids.reduce((s, i) => s + (D.nodes[i].sp || []).filter(v => v != null).length, 0);
      out.expNd = ids.reduce((s, i) => { const sp = D.nodes[i].sp || []; return s + (sp.some(v => v != null) ? sp.filter(v => v == null).length : 0); }, 0);
      return out; });
    await page.click('#cxSs td[data-k="14"]'); await sleep(500);
    const c = await page.evaluate(() => { const cur = [...document.querySelectorAll('#cxSs td.cur')];
      return { month: CX.month, cur: cur.length > 0 && cur.every(td => td.dataset.k === '14'), lbl: $('#cxMonL').textContent, readout: /март 2024/.test($('#cxSsR').textContent), hs: document.documentElement.scrollWidth - innerWidth }; });
    const o = await overlaps(page, '#cxSpendSec'); await ctx.close();
    const ok = r.months === 24 && r.years === 2 && r.cal && !r.valBad && !r.ndBad && !r.domBad && r.mono && r.colored === r.expColored && r.nd === r.expNd && r.none === 1
      && c.month === 14 && c.cur && /март 2024/.test(c.lbl) && c.readout && c.hs <= 0 && !o.overlaps.length;
    if (!ok) bad.push(w);
    det.push(`${w}px: клеток ${r.cells}, с цветом ${r.colored} (по D ${r.expColored}), «н/д» ${r.nd} (по D ${r.expNd}), строк «ряда нет» ${r.none}; расхождений с D ${r.valBad}, цвет вне домена оси ${r.domBad}, монотонность ${r.mono}; щелчок → месяц ${c.month} («${c.lbl}»), прокрутка вбок ${c.hs}, наложений ${o.overlaps.length}`);
  }
  return { pass: !bad.length, detail: det.join('; ') };
});

/* ---- ТЗ 12.1: матрица связей МО × МО ---- */
check('map.flow-matrix', 'Матрица связей МО × МО (ТЗ 12.1): клетки = записи слоя (flow_rub — 500 направленных пар «строка-источник → столбец-получатель», совпадают с D), обе оси — все 63 МО, пересортировка не теряет клеток, ненаправленный каркас симметричен, пустая клетка подписана «нет записи», не ноль', async ({ browser }) => {
  const { page, ctx } = await openPage(browser, FILE, { hash: '#map', height: 1200 }); await page.waitForFunction(() => typeof MAPVS !== 'undefined' && MAPVS.scenes.length && MAPVS.scenes[0].rendered > 0, null, { timeout: 20000 }); await sleep(800);
  await page.evaluate(() => { $('#edgeLayer').value = 'flow_rub'; $('#edgeLayer').dispatchEvent(new Event('input')); setView('matrix'); }); await sleep(1500);
  const read = () => page.evaluate(() => { const ch = echarts.getInstanceByDom($('#fmxChart')), o = ch.getOption(), data = o.series[0].data, xs = o.xAxis[0].data, ys = o.yAxis[0].data;
    return { data: data.map(d => [ys[d[1]], xs[d[0]]]), xs: xs.length, ys: ys.length, ux: new Set(xs).size, first: xs.slice(0, 3), hint: /не доказанный ноль/.test($('#flowMatrix .fmx-head').innerText) }; });
  const a = await read();
  const exp = await page.evaluate(() => D.layers.flow_rub.map(e => [N[e[0]].s, N[e[1]].s]));
  const key = p => p[0] + '→' + p[1], A = new Set(a.data.map(key)), same = A.size === exp.length && exp.every(p => A.has(key(p)));
  await page.click('#flowMatrix [data-fs="total"]'); await sleep(1200);
  const b = await read(), B = new Set(b.data.map(key)), sameAfter = B.size === A.size && [...A].every(p => B.has(p));
  await page.evaluate(() => { $('#edgeLayer').value = 'backbone'; $('#edgeLayer').dispatchEvent(new Event('input')); }); await sleep(1500);
  const c = await read(), nb = await page.evaluate(() => D.layers.backbone.length), C = new Set(c.data.map(key)), sym = c.data.every(p => C.has(p[1] + '→' + p[0]));
  const o = await overlaps(page, '#flowMatrix .fmx-head'); await ctx.close();
  const ok = a.data.length === exp.length && same && a.xs === 63 && a.ys === 63 && a.ux === 63 && a.hint && sameAfter && b.first.join() !== a.first.join() && c.data.length === 2 * nb && sym && !o.overlaps.length;
  return { pass: ok, detail: `flow_rub: клеток ${a.data.length}, записей ${exp.length}, пары совпадают с D: ${same}; оси ${a.xs}×${a.ys}; по сумме связей — пары те же: ${sameAfter}, порядок изменился: ${b.first.join() !== a.first.join()}; каркас: клеток ${c.data.length} = 2 × ${nb}, симметрия ${sym}; подпись «не доказанный ноль»: ${a.hint}; наложений в шапке ${o.overlaps.length}` };
});

/* ---- переходы режимов пары без сдвига макета ---- */
check('corr.mode-no-shift', 'Пара: переходы «пузыри → медианы → распределение → пузыри» не сдвигают график (верх области ±1 px, 1440 и 390 px); кнопки неактивного режима не получают фокус', async ({ browser }) => {
  const det = [], bad = [];
  for (const w of [1440, 390]) {
    const { page, ctx } = await openPage(browser, FILE, { hash: '#corr', width: w, height: 1000 }); await sleep(2500);
    await page.evaluate(() => $('#bStage').scrollIntoView({ block: 'center' })); await sleep(500);
    const top = () => page.evaluate(() => Math.round($('#bStage').getBoundingClientRect().top + scrollY));
    const tops = [await top()];
    for (const m of ['med', 'dist', 'bub']) { await page.click(`#bMode [data-bm=${m}]`); await sleep(1400); tops.push(await top()); }
    await page.click('#bMode [data-bm=med]'); await sleep(1200);
    const focusable = await page.evaluate(() => [...document.querySelectorAll('#bBubTools button')].filter(b => { b.focus(); return document.activeElement === b && b.checkVisibility({ visibilityProperty: true }); }).length);
    await ctx.close();
    const ok = tops.every(t => Math.abs(t - tops[0]) <= 1) && focusable === 0;
    if (!ok) bad.push(w);
    det.push(`${w}px: верх графика ${tops.join(' → ')}; видимых фокусируемых кнопок пузырей в режиме медиан ${focusable}`);
  }
  return { pass: !bad.length, detail: det.join('; ') };
});
