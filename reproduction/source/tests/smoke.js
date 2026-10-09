// Быстрый прогон: открыть каждую вкладку в обеих темах, собрать ошибки консоли.
const { chromium } = require('playwright');
const path = require('path');
const URL = 'file://' + path.resolve(__dirname, '..', 'econtypes.html');
(async () => {
  const browser = await chromium.launch();
  const errs = [];
  for (const theme of ['light', 'dark']) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: theme });
    const page = await ctx.newPage();
    page.on('pageerror', e => errs.push(`[${theme}] pageerror: ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') errs.push(`[${theme}] console: ${m.text()}`); });
    await page.goto(URL, { waitUntil: 'load' });
    await page.waitForTimeout(800);
    for (const t of ['out', 'map', 'cmp', 'corr', 'types', 'quality', 'how']) {
      await page.click(`nav.tabs [data-t="${t}"]`);
      await page.waitForTimeout(t === 'map' ? 900 : 300);
      await page.screenshot({ path: path.resolve(__dirname, `../docs/screenshots/../../../tmp/claude-0/-home-user--/972836d2-b90f-5895-8c88-e1464352fb4b/scratchpad/smoke-${theme}-${t}.png`), fullPage: false });
    }
    await ctx.close();
  }
  await browser.close();
  console.log(errs.length ? errs.join('\n') : 'no errors');
})();
