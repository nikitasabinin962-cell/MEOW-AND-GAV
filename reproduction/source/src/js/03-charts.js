/* ==========================================================================
   ECharts: тема из CSS-токенов, создание графиков с учётом видимости,
   ResizeObserver, смены темы и reduced motion. Один реестр на страницу.
   ========================================================================== */
const ECH = window.echarts;
function chartTheme(){
  const t = n => css(n);
  return {
    color: [t('--c0'), t('--c1'), t('--c2'), t('--c3'), t('--c4'), t('--c5'), t('--c6')],
    backgroundColor: 'transparent',
    textStyle: {fontFamily: 'Golos Text, system-ui, sans-serif', color: t('--ink2'), fontSize: 12},
    title: {textStyle: {color: t('--ink'), fontWeight: 600}},
    axisPointer: {lineStyle: {color: t('--line-strong')}, label: {backgroundColor: t('--surface-3'), color: t('--ink')}},
    tooltip: {backgroundColor: t('--surface'), borderColor: t('--line-strong'), textStyle: {color: t('--ink'), fontSize: 12.5}, extraCssText: 'box-shadow:' + t('--shadow-float') + ';border-radius:8px;'},
    categoryAxis: {axisLine: {lineStyle: {color: t('--line-strong')}}, axisTick: {lineStyle: {color: t('--line-strong')}}, axisLabel: {color: t('--ink2')}, splitLine: {lineStyle: {color: t('--line-soft')}}},
    valueAxis: {axisLine: {lineStyle: {color: t('--line-strong')}}, axisTick: {lineStyle: {color: t('--line-strong')}}, axisLabel: {color: t('--ink2')}, splitLine: {lineStyle: {color: t('--line-soft')}}, nameTextStyle: {color: t('--ink2')}},
    logAxis: {axisLabel: {color: t('--ink2')}, splitLine: {lineStyle: {color: t('--line-soft')}}},
    legend: {textStyle: {color: t('--ink2')}},
  };
}
const CHARTS = new Set();
/* makeChart(el, build) — build(chart) возвращает option; перерисовка при смене темы/размера */
function makeChart(el, build, opts = {}){
  const rec = {el, build, chart: null, ro: null, opts};
  const init = () => {
    if (rec.chart) rec.chart.dispose();
    ECH.registerTheme('econ', chartTheme());
    rec.chart = ECH.init(el, 'econ', {renderer: opts.renderer || 'svg'});
    rec.chart.setOption(withMotion(build(rec.chart)), true);
    if (opts.onInit) opts.onInit(rec.chart);
  };
  rec.refresh = (notMerge = false) => { if (rec.chart) rec.chart.setOption(withMotion(build(rec.chart)), notMerge); };
  rec.rethemed = () => init();
  rec.dispose = () => { if (rec.chart) rec.chart.dispose(); if (rec.ro) rec.ro.disconnect(); CHARTS.delete(rec); };
  FONTS_READY.then(() => whenSized(el, () => { init(); rec.ro = onResize(el, () => rec.chart && rec.chart.resize()); }));
  CHARTS.add(rec);
  return rec;
}
function withMotion(o){ if (RM.matches) { o.animation = false; o.animationDurationUpdate = 0; } return o; }
THEME_HOOKS.push(() => CHARTS.forEach(r => { if (!r.el.isConnected) { r.dispose(); return; } if (r.chart) r.rethemed(); }));
