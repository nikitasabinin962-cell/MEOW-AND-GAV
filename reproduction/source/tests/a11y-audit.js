// Сквозной аудит доступности по всем вкладкам (WCAG 2.2 AA, автоматическая часть; не заменяет ручную проверку).
// Контраст значимого текста на фактическом (скомпозированном) фоне, видимость фокуса при обходе Tab,
// размер целей < 24 px, горизонтальная прокрутка страницы на 320 px.
// Запуск: NODE_PATH=<node_modules с playwright> node tests/a11y-audit.js [html]  → docs/a11y-audit.json
const path = require('path');
const fs = require('fs');
const { launch, openPage, overlaps } = require('./lib/qa.js');
const ROOT = path.resolve(__dirname, '..');
const FILE = path.resolve(process.argv[2] || path.join(ROOT, 'econtypes.html'));
const TABS = ['out', 'map', 'cmp', 'corr', 'types', 'quality', 'how'];
const sleep = ms => new Promise(r => setTimeout(r, ms));
/* «Сравнение» проверяется заполненным: пять районов (худший случай плотности дорожек), а не пустым состоянием */
const FILL_CMP = () => { clearComparison(); ['Кумертау', 'Салават', 'Бакалинский', 'Бирский', 'Благовещенский'].forEach(s => addToComparison(findMO(s))); const ss = document.querySelector('#cxSs'); if (ss) ss.open = true; };   // + раскрытая полоса сезонности

/* контраст: цвет текста × непрозрачность предков поверх фона, сложенного из полупрозрачных слоёв предков */
const CONTRAST = () => {
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const over = (top, bot) => { const a = top[3]; return [top[0] * a + bot[0] * (1 - a), top[1] * a + bot[1] * (1 - a), top[2] * a + bot[2] * (1 - a), 1]; };
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const bgOf = el => { const layers = []; let complex = false;
    for (let a = el; a; a = a.parentElement) { const cs = getComputedStyle(a); if (cs.backgroundImage && cs.backgroundImage !== 'none') complex = true;
      const c = parse(cs.backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] >= .999) break; } }
    let bg = [255, 255, 255, 1]; const root = parse(getComputedStyle(document.body).backgroundColor); if (root && root[3] > 0) bg = root;
    for (let k = layers.length - 1; k >= 0; k--) bg = over(layers[k], bg);
    return { bg, complex }; };
  const out = []; let n = 0;
  const vis = el => el.checkVisibility ? el.checkVisibility({ contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true }) : true;
  document.querySelectorAll('section[role=tabpanel]:not([hidden]) *, header *, nav *, footer *').forEach(el => {
    if (!vis(el) || el.closest('[aria-hidden=true]') || el.closest('canvas')) return;
    if (![...el.childNodes].some(t => t.nodeType === 3 && t.textContent.trim())) return;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return;
    if (el.closest('button[disabled], input[disabled], select[disabled], [aria-disabled=true], .off')) return;   // неактивные элементы — исключение WCAG 1.4.3
    if (el.closest('.mlabels, .scene, .leaflet-container')) return;                                              // подписи поверх WebGL/карты — проверяются кадрами
    const cs = getComputedStyle(el), isSvg = el instanceof SVGElement;
    let fg = parse(isSvg ? (cs.fill && cs.fill !== 'none' ? cs.fill : cs.color) : cs.color); if (!fg) return;
    let op = 1; for (let a = el; a; a = a.parentElement) op *= +getComputedStyle(a).opacity; fg = [fg[0], fg[1], fg[2], fg[3] * op];
    const { bg, complex } = bgOf(isSvg ? (el.closest('svg') || el).parentElement : el); const fgc = over(fg, bg);
    const px = parseFloat(cs.fontSize) * (isSvg && el.ownerSVGElement && el.ownerSVGElement.viewBox.baseVal.width ? el.ownerSVGElement.getBoundingClientRect().width / el.ownerSVGElement.viewBox.baseVal.width : 1);
    const large = px >= 24 || (px >= 18.66 && +cs.fontWeight >= 700), need = large ? 3 : 4.5, cr = ratio(fgc, bg); n++;
    if (cr < need - .005) out.push({ t: el.textContent.trim().replace(/\s+/g, ' ').slice(0, 50), cr: Math.round(cr * 100) / 100, need, px: Math.round(px * 10) / 10, fg: fgc.slice(0, 3).map(Math.round).join(','), bg: bg.slice(0, 3).map(Math.round).join(','), complex, sel: el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '') });
  });
  return { checked: n, fails: out };
};
const TARGETS = () => {
  const small = [];
  document.querySelectorAll('section[role=tabpanel]:not([hidden]) :is(button, a[href], input, select, summary, [role=button], [role=tab], [role=treeitem], [tabindex="0"])').forEach(el => {
    if (el.closest('[aria-hidden=true]') || (el.checkVisibility && !el.checkVisibility({ visibilityProperty: true }))) return;
    let r = el.getBoundingClientRect(); if (!r.width || !r.height) return; let via = '';
    /* поле с подписью: щелчок по <label> тоже переключает поле — цель = поле ∪ подпись */
    if (el.labels && el.labels.length) { const l = el.labels[0].getBoundingClientRect(); r = { width: Math.max(r.right, l.right) - Math.min(r.left, l.left), height: Math.max(r.bottom, l.bottom) - Math.min(r.top, l.top) }; via = 'label'; }
    if (r.width >= 24 && r.height >= 24) return;
    const inline = el.tagName === 'A' && getComputedStyle(el).display === 'inline';          // ссылка внутри текста — исключение 2.5.8
    const eq = el.matches('.cx-dot, .cx-na') && (b => b && b.getBoundingClientRect().height >= 24 && b.getBoundingClientRect().width >= 24)(el.closest('.cx-pr') && el.closest('.cx-pr').querySelector('.cx-ixb'));
    small.push({ el: el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : ''), t: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30), w: Math.round(r.width), h: Math.round(r.height), inline, via, eq });
  });
  return small;
};

(async () => {
  const browser = await launch(); const report = { file: path.relative(ROOT, FILE), at: new Date().toISOString(), contrast: {}, focus: {}, targets: {}, reflow320: {} };
  for (const theme of ['light', 'dark']) {
    const { page, ctx } = await openPage(browser, FILE, { theme, width: 1440, height: 1000 });
    for (const t of TABS) {
      await page.evaluate(t => activate(t), t); if (t === 'cmp') await page.evaluate(FILL_CMP); await sleep(t === 'map' ? 2600 : t === 'cmp' ? 1800 : 1200);
      const c = await page.evaluate(CONTRAST); report.contrast[`${theme}/${t}`] = c;
      if (theme === 'light') report.targets[t] = await page.evaluate(TARGETS);
      console.log(`contrast ${theme}/${t}: ${c.checked} текстов, ниже порога ${c.fails.length}` + (c.fails.length ? ' — ' + c.fails.slice(0, 4).map(f => `«${f.t}» ${f.cr}:1 (${f.fg} на ${f.bg})`).join('; ') : ''));
    }
    await ctx.close();
  }
  /* фокус: обход Tab с начала страницы на каждой вкладке, видимый индикатор (outline или box-shadow) */
  { const { page, ctx } = await openPage(browser, FILE, { theme: 'light', width: 1440, height: 1000 });
    for (const t of TABS) {
      await page.evaluate(t => { activate(t); scrollTo(0, 0); document.activeElement && document.activeElement.blur && document.activeElement.blur(); }, t); if (t === 'cmp') await page.evaluate(FILL_CMP); await sleep(t === 'map' ? 2600 : t === 'cmp' ? 1800 : 1000);
      await page.focus(`nav.tabs [data-t="${t}"]`);
      const seen = [], bad = [];
      /* стили элемента и его потомков, которыми рисуют индикатор фокуса (обводка, тень, контур SVG, фон, цвет) */
      const SNAP = e => [e, ...e.querySelectorAll('*')].slice(0, 80).map(x => { const c = getComputedStyle(x); return [c.outlineStyle, c.outlineWidth, c.boxShadow, c.stroke, c.strokeWidth, c.strokeOpacity, c.backgroundColor, c.color, c.textDecorationLine].join('|'); });
      for (let k = 0; k < 45; k++) { await page.keyboard.press('Tab'); await sleep(40);
        const f = await page.evaluate(() => { const e = document.activeElement; if (!e || e === document.body) return null; const cs = getComputedStyle(e), r = e.getBoundingClientRect();
          const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== 'none');
          /* закрыт: видимая часть вне окна или её центр перекрыт липкой панелью вкладок (WCAG 2.4.11) */
          const nav = document.querySelector('nav.tabs'), v = { l: Math.max(r.left, 0), t: Math.max(r.top, 0), r: Math.min(r.right, innerWidth), b: Math.min(r.bottom, innerHeight) };
          let hidden = false;
          if (v.r <= v.l || v.b <= v.t) hidden = 'вне окна';
          else if (!nav.contains(e)) { const hit = document.elementFromPoint((v.l + v.r) / 2, (v.t + v.b) / 2); if (hit && nav.contains(hit)) hidden = 'под панелью'; }
          return { d: e.tagName.toLowerCase() + (e.id ? '#' + e.id : e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.getAttribute('class') ? '.' + e.getAttribute('class').split(' ')[0] : ''), ring, hidden }; });
        if (!f) continue; seen.push(f.d);
        if (!f.ring) { /* индикатор на потомке (например, контур фона узла SVG): сравнить стили в фокусе и без него */
          const a = await page.evaluate(`(${SNAP})(document.activeElement)`);
          await page.evaluate(() => { window.__fe = document.activeElement; window.__fe.blur(); }); await sleep(30);
          const b = await page.evaluate(`(${SNAP})(window.__fe)`);
          await page.evaluate(() => window.__fe.focus({ preventScroll: true })); await sleep(30);
          if (a.some((x, j) => x !== b[j])) f.ring = 'стиль потомка'; }
        if (!f.ring || f.hidden) bad.push(f); }
      report.focus[t] = { steps: seen.length, unique: new Set(seen).size, noIndicator: bad };
      console.log(`focus ${t}: ${seen.length} шагов, без видимого индикатора или под панелью: ${bad.length}` + (bad.length ? ' — ' + bad.slice(0, 4).map(b => b.d + (b.hidden ? ` (${b.hidden})` : '') + (b.ring ? '' : ' (нет индикатора)')).join(', ') : ''));
    }
    await ctx.close(); }
  /* reflow 320 px: горизонтальная прокрутка страницы и наложения */
  { const { page, ctx } = await openPage(browser, FILE, { theme: 'light', width: 320, height: 720 });
    for (const t of TABS) { await page.evaluate(t => activate(t), t); if (t === 'cmp') await page.evaluate(FILL_CMP); await sleep(t === 'map' ? 2600 : t === 'cmp' ? 1800 : 1000);
      const sw = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth); const o = await overlaps(page, '#t-' + t);
      report.reflow320[t] = { hscroll: sw, overlaps: o.overlaps.slice(0, 5), n: o.overlaps.length };
      console.log(`320px ${t}: горизонтальная прокрутка ${sw}px, наложений ${o.overlaps.length}`); }
    await ctx.close(); }
  for (const t of TABS) console.log(`targets <24px ${t}: ${report.targets[t].length}` + (report.targets[t].length ? ' — ' + report.targets[t].slice(0, 5).map(x => `${x.el} «${x.t}» ${x.w}×${x.h}${x.inline ? ' (ссылка в тексте)' : ''}${x.via ? ' (с подписью)' : ''}${x.eq ? ' (есть эквивалент ≥ 24 px)' : ''}`).join('; ') : '') + (report.targets[t].length ? ` · без исключения: ${report.targets[t].filter(x => !x.inline && !x.eq).length}` : ''));
  await browser.close();
  fs.writeFileSync(path.join(ROOT, 'docs', 'a11y-audit.json'), JSON.stringify(report, null, 1));
})();
