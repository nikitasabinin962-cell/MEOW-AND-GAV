// Общие помощники браузерных проверок (Playwright, Chromium).
// overlaps(page, rootSelector) — пары видимых текстовых элементов с пересечением > minArea px²
// в реальных экранных координатах (после загрузки шрифтов). SVG <text>/<tspan> и HTML-текст.
const path = require('path');
const { chromium } = require('playwright');
const CHROME_ARGS = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
async function launch(){ return chromium.launch({ args: CHROME_ARGS }); }
async function openPage(browser, file, { theme = 'light', width = 1440, height = 900, dpr = 1, reduced = false, hash = '', offline = true } = {}){
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dpr, colorScheme: theme, reducedMotion: reduced ? 'reduce' : 'no-preference' });
  if (offline) await ctx.route(/^https?:/, r => r.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await page.goto('file://' + path.resolve(file) + hash, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForTimeout(500);
  return { ctx, page, errors };
}
async function overlaps(page, root, { minArea = 4, ignore = null, selector = 'text, tspan, .lab, label, span, b, small, button, a, h1, h2, h3, h4, h5, li, td, th' } = {}){
  return page.evaluate(([root, minArea, selector, ignore]) => {
    const R = document.querySelector(root); if (!R) return { error: 'no root ' + root };
    const vis = el => { const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false;
      if (el.checkVisibility && !el.checkVisibility({ contentVisibilityAuto: true, opacityProperty: true, visibilityProperty: true })) return false;   // закрытые <details>, content-visibility
      for (let a = el; a; a = a.parentElement) if (a.tagName === 'DETAILS' && !a.open && !(el.closest('summary') && el.closest('summary').parentElement === a)) return false;
      for (let a = el; a; a = a.parentElement) { const s = getComputedStyle(a); if (s.display === 'none' || +s.opacity === 0) return false; } return true; };
    const leafs = [...R.querySelectorAll(selector)].filter(el => {
      if (!vis(el)) return false;
      if (ignore && el.closest(ignore)) return false;
      const t = (el.textContent || '').trim(); if (!t) return false;
      // только элементы с собственным текстом (не контейнеры текстов-потомков)
      return [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    });
    // видимая часть: каждый строковый фрагмент текста (getClientRects — у перенесённого inline-элемента это отдельные строки,
    // а не общий прямоугольник обеих строк) пересекается с прямоугольниками предков, обрезающих содержимое (локальный scroll/overflow)
    const clips = el => { const out = []; for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) { const cs = getComputedStyle(a); if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') out.push(a.getBoundingClientRect()); } return out; };
    const rectsOf = el => { const C = clips(el); return [...el.getClientRects()].map(q => { let r = { left: q.left, top: q.top, right: q.right, bottom: q.bottom };
      C.forEach(c => { r = { left: Math.max(r.left, c.left), top: Math.max(r.top, c.top), right: Math.min(r.right, c.right), bottom: Math.min(r.bottom, c.bottom) }; });
      return r; }).filter(r => r.right - r.left > 0 && r.bottom - r.top > 0); };
    const boxes = leafs.map(el => ({ el, rs: rectsOf(el), t: el.textContent.trim().slice(0, 40) })).filter(b => b.rs.length);
    // перекрытие непрозрачным липким/плавающим слоем — не столкновение подписей: видна только одна из них
    // точка вне окна (elementFromPoint там возвращает null): страница на мгновение прокручивается так, чтобы точка
    // оказалась в середине окна (не под липкой панелью вкладок), проверка выполняется там и прокрутка возвращается
    const hitAt = (x, y) => { if (x >= 0 && y >= 0 && x < innerWidth && y < innerHeight) return document.elementFromPoint(x, y);
      const sx = scrollX, sy = scrollY; window.scrollTo({ left: sx + (x < 0 || x >= innerWidth ? x - innerWidth / 2 : 0), top: sy + (y < 0 || y >= innerHeight ? y - innerHeight / 2 : 0), behavior: 'instant' });
      const hx = x - (scrollX - sx), hy = y - (scrollY - sy), hit = hx >= 0 && hy >= 0 && hx < innerWidth && hy < innerHeight ? document.elementFromPoint(hx, hy) : null;
      window.scrollTo({ left: sx, top: sy, behavior: 'instant' }); return hit; };
    const covered = (a, b, x, y) => { const hit = hitAt(x, y); if (!hit) return false;
      const inA = a.el.contains(hit) || hit.contains(a.el), inB = b.el.contains(hit) || hit.contains(b.el);
      if (inA === inB && (inA || inB)) return false;
      for (let p = inA ? a.el : inB ? b.el : hit; p && p !== document.body; p = p.parentElement) { const ps = getComputedStyle(p).position; if (ps === 'sticky' || ps === 'fixed') return true; }
      return false; };
    const out = [];
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j]; if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      let area = 0;
      for (const ra of a.rs) { for (const rb of b.rs) {
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (!(w > 0 && h > 0 && w * h > minArea)) continue;
        if (covered(a, b, (Math.max(ra.left, rb.left) + Math.min(ra.right, rb.right)) / 2, (Math.max(ra.top, rb.top) + Math.min(ra.bottom, rb.bottom)) / 2)) continue;
        area = Math.max(area, w * h); } }
      if (area) out.push({ a: a.t, b: b.t, area: Math.round(area) });
    }
    return { count: boxes.length, overlaps: out };
  }, [root, minArea, selector, ignore]);
}
// минимальный экранный размер шрифта видимого текста внутри root (CSS px, с учётом масштабирования SVG)
async function minFontPx(page, root){
  return page.evaluate(root => {
    const R = document.querySelector(root); if (!R) return null; let min = 1e9, who = '';
    R.querySelectorAll('text, tspan, span, td, th, b, small, label, button').forEach(el => {
      if (!(el.textContent || '').trim()) return; const r = el.getBoundingClientRect(); if (!r.width) return;
      let px = parseFloat(getComputedStyle(el).fontSize);
      const svg = el.ownerSVGElement; if (svg && svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width) px *= svg.getBoundingClientRect().width / svg.viewBox.baseVal.width;
      if (px < min) { min = px; who = el.textContent.trim().slice(0, 30); } });
    return { min: Math.round(min * 10) / 10, who };
  }, root);
}
module.exports = { launch, openPage, overlaps, minFontPx, CHROME_ARGS };
