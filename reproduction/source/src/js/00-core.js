/* ==========================================================================
   econtypes · ядро: утилиты, тема, шапка, вкладки, общее состояние
   Данные D не изменяются: весь код только читает их.
   ========================================================================== */
const $ = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const N = D.nodes, n = N.length;
const SVGNS = 'http://www.w3.org/2000/svg';
const RM = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : {matches: false, addEventListener(){}};

/* постоянное соответствие «название типа → цвет» (как в исходной сборке) */
const TYPEIDX = {'Западные промышленные районы':0,'Северная аграрная периферия':1,'Горный юго-восток, связанный с соседними регионами':2,
  'Бюджетная сельская периферия с молодым населением':3,'Пригородный пояс Уфы':4,'Стареющие аграрные районы центра и юго-запада':5,'Города и промышленные центры':6};
const tslot = c => (TYPEIDX[(D.names || {})[c]] ?? c) % 7;
const COLV = c => 'var(--c' + tslot(c) + ')';           // для HTML/SVG: меняется с темой без перерисовки
const COL = c => css('--c' + tslot(c));                  // вычисленный цвет: canvas, Leaflet
const MACROV = ['--c6', '--c3', '--c2'];
const typeName = c => (D.names || {})[c] ?? ('тип ' + c);

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtN = (v, d = 0) => v == null || Number.isNaN(v) ? 'н/д' : Number(v).toLocaleString('ru-RU', {maximumFractionDigits: d, minimumFractionDigits: d}).replace(/^-/, '−');   // единый знак минуса U+2212
const fmtSigned = (v, d = 2) => v == null ? 'н/д' : (v > 0 ? '+' : v < 0 ? '−' : '') + fmtN(Math.abs(v), d);
function fmtF(k, v){ if (v == null) return 'н/д'; const u = (D.feats[k] || ['', ''])[1];
  if (u === '%') return fmtN(v * 100, 1) + '%'; return fmtN(v, Math.abs(v) >= 100 ? 0 : 2) + (u ? ' ' + u : ''); }
const featLabel = k => k.startsWith('m_') ? D.metrics[k.slice(2)].label : (D.feats[k] ? D.feats[k][0] : k);
const featUnit = k => k.startsWith('m_') ? '' : (D.feats[k] ? D.feats[k][1] : '');
const FL = k => (D.feats[k] || [k])[0];
const NA = '<span class="na" title="значение отсутствует в данных">н/д</span>';

function hex2rgb(h){ h = String(h).trim();
  if (h.startsWith('rgb')) return h.replace(/[^\d.,]/g, '').split(',').slice(0, 3).map(Number);
  h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join('');
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); }
const cv = x => x.startsWith('--') ? css(x) : x;
function mix(a, b, t){ const A = hex2rgb(cv(a)), B = hex2rgb(cv(b)); t = Math.max(0, Math.min(1, t));
  return 'rgb(' + A.map((x, i) => Math.round(x + (B[i] - x) * t)).join(',') + ')'; }
const ramp = (t, a, b) => mix(a, b, t);
const rgba = (c, a) => { const [r, g, b] = hex2rgb(cv(c)); return `rgba(${r},${g},${b},${a})`; };
const isDark = () => getComputedStyle(document.documentElement).colorScheme.includes('dark');

function niceTicks(lo, hi, k){ const span = hi - lo || 1, step0 = span / k, mag = 10 ** Math.floor(Math.log10(step0)), err = step0 / mag;
  const step = (err >= 5 ? 10 : err >= 2 ? 5 : err >= 1.5 ? 2 : 1) * mag, t = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-12; v += step) t.push(+v.toFixed(12)); return t; }
const median = a => { const v = a.filter(x => x != null).sort((p, q) => p - q); if (!v.length) return null; const m = v.length >> 1; return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2; };
const ICON = {
  close: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
  map: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/></svg>',
  plus: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
  check: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>',
  chev: '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>',
  copy: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>',
  reset: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v5h5"/></svg>',
  arrow: '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
};

/* ---------- всплывающая подсказка ---------- */
const tt = $('#tt');
function showTip(e, html){ tt.innerHTML = html; tt.hidden = false;
  const w = tt.offsetWidth, h = tt.offsetHeight; let x = e.clientX + 14, y = e.clientY + 14;
  if (x + w > innerWidth - 8) x = e.clientX - w - 14; if (y + h > innerHeight - 8) y = e.clientY - h - 14;
  tt.style.left = Math.max(8, x) + 'px'; tt.style.top = Math.max(8, y) + 'px'; }
const hideTip = () => { tt.hidden = true; };

/* ---------- темы рекомендаций: риск / возможность / ориентир ---------- */
const RISK = new Set(['Локализация госзаказа','Конкуренция в закупках','Бюджетная зависимость','Утечка потребительского спроса','Демография','Рост без людей']);
const OPP = new Set(['Опорный центр снабжения','Связующее звено сети','Опережающий индикатор']);
const kind = t => RISK.has(t) ? 'risk' : OPP.has(t) ? 'opp' : 'info';
const KIND_LABEL = {risk: 'риск', opp: 'возможность', info: 'ориентир'};
const mk = k => `<span class="mk ${k}" aria-hidden="true"></span>`;

/* ---------- общее состояние ---------- */
let sel = null;          // выбранный МО (общий для карты, корреляций, дерева типов)
let cmpSet = [];         // районы в сравнении (до 5)
let group = null;        // подсвеченная группа МО на карте
let groupLabel = '';
const SEL_HOOKS = [];    // кто реагирует на смену выбранного МО
const THEME_HOOKS = [];  // кто перерисовывается при смене темы
const TAB_HOOKS = {};    // вход на вкладку
let activeTab = 'out';

/* ---------- шапка ---------- */
document.title = D.title;
$('#ttl').textContent = D.title;
$('#regionLine').innerHTML = `<span>${esc(D.region)}</span><span>${n} муниципалитета</span><span>${D.k} экономических типов</span>`;
$('#metaLine').innerHTML = `<span>Период данных: <b>${esc(D.period)}</b></span><span>Сборка: <b>${esc(D.generated)}</b></span>`
  + (D.authors ? `<span>Авторы: ${esc(D.authors)}</span>` : '')
  + `<span><a href="https://elena30r.github.io/econtypes/">О проекте</a> · <a href="https://elena30r.github.io/econtypes/report.pdf" title="PDF-отчёт проекта; в рамках редизайна не пересоздавался">Отчёт (PDF)</a> · <a href="https://github.com/Elena30R/econtypes">Код</a></span>`;
const Q = D.quality;
const kp = [[D.k, 'типов МО'], [fmtN(Q.boot, 2), 'устойчивость, ARI'], [D.ml ? fmtN(D.ml.acc * 100) + '%' : '—', 'ML-точность типа'],
  [Q.val ? Object.entries(Q.val.holdout).map(([y, h]) => fmtN(h.accuracy * 100) + '%').join(' / ') : '—', 'узнаваемость 2025 / 2026'],
  [D.corr ? D.corr.top.length + '+' : '—', 'значимых связей']];
$('#kpis').innerHTML = kp.map(([v, l]) => `<div class="kpi"><b>${v}</b><span>${l}</span></div>`).join('');

/* ---------- тема ---------- */
function themeMode(){ const a = document.documentElement.getAttribute('data-theme'); return a === 'light' || a === 'dark' ? a : 'auto'; }
function syncThemeSeg(){ $$('#themeSeg [data-theme-set]').forEach(b => b.setAttribute('aria-pressed', b.dataset.themeSet === themeMode())); }
function applyTheme(){ syncThemeSeg(); THEME_HOOKS.forEach(f => { try { f(); } catch (err) { console.error(err); } }); }
function setTheme(m){
  if (m === 'auto') document.documentElement.removeAttribute('data-theme'); else document.documentElement.setAttribute('data-theme', m);
  try { if (m === 'auto') localStorage.removeItem('econtypes-theme'); else localStorage.setItem('econtypes-theme', m); } catch (e) {}
  applyTheme();
}
$$('#themeSeg [data-theme-set]').forEach(b => b.addEventListener('click', () => setTheme(b.dataset.themeSet)));
if (window.matchMedia) matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (themeMode() === 'auto') applyTheme(); });
syncThemeSeg();

/* ---------- вкладки: клавиатура, адрес #, сохранение состояния ---------- */
const TABS = $$('nav.tabs [role=tab]');
function activate(t, opts = {}){
  if (!$('#t-' + t)) t = 'out';
  activeTab = t;
  TABS.forEach(b => { const on = b.dataset.t === t; b.setAttribute('aria-selected', on); b.tabIndex = on ? 0 : -1; if (on && opts.focus) b.focus(); });
  $$('section[role=tabpanel]').forEach(s => s.hidden = s.id !== 't-' + t);
  if (!opts.noHash) { try { history.replaceState(null, '', '#' + t); } catch (e) {} }
  hideTip();
  (TAB_HOOKS[t] || []).forEach(f => f());
  if (opts.scroll !== false) { const t = $('.top'), top = t ? t.offsetTop + t.offsetHeight : $('nav.tabs').offsetTop; if (scrollY > top) scrollTo({top, behavior: 'auto'}); }   // статичная позиция панели вкладок (sticky offsetTop меняется)
}
const onTab = (t, f) => (TAB_HOOKS[t] = TAB_HOOKS[t] || []).push(f);
TABS.forEach((b, k) => {
  b.addEventListener('click', () => activate(b.dataset.t));
  b.addEventListener('keydown', e => {
    let j = null; if (e.key === 'ArrowRight') j = (k + 1) % TABS.length; else if (e.key === 'ArrowLeft') j = (k - 1 + TABS.length) % TABS.length;
    else if (e.key === 'Home') j = 0; else if (e.key === 'End') j = TABS.length - 1;
    if (j != null) { e.preventDefault(); activate(TABS[j].dataset.t, {focus: true}); }
  });
});
window.addEventListener('hashchange', () => { const t = location.hash.slice(1); if (t && t !== activeTab && $('#t-' + t)) activate(t, {noHash: true}); });

/* ---------- выбор МО (общий) ---------- */
function setSel(i){ sel = i; SEL_HOOKS.forEach(f => { try { f(); } catch (err) { console.error(err); } }); }
function goMap(i){ activate('map'); select(i, true); }            // камера ждёт готовности сцены сама (fitView → MAPVS.pending)
function showGroup(ids, label){ group = new Set(ids); groupLabel = label; activate('map'); setSel(null); fitIds(ids); }

/* ---------- копирование команд ---------- */
document.addEventListener('click', e => { const b = e.target.closest('[data-copy]'); if (!b) return;
  const fallback = t => { try { const a = document.createElement('textarea'); a.value = t; a.style.position = 'fixed'; a.style.opacity = '0'; document.body.appendChild(a); a.select(); const ok = document.execCommand('copy'); a.remove(); return ok; } catch (err) { return false; } };
  const txt = b.dataset.copy; const done = () => { const o = b.innerHTML; b.innerHTML = ICON.check; b.setAttribute('aria-label', 'скопировано'); setTimeout(() => { b.innerHTML = o; b.setAttribute('aria-label', 'копировать'); }, 1200); };
  const fail = () => { if (fallback(txt)) done(); else notify(b, 'Не удалось скопировать — выделите команду вручную.', {kind: 'warn'}); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, fail); else fail(); });
const copyCode = c => `<span class="copy"><code style="background:none;padding:0">${esc(c)}</code><button type="button" data-copy="${esc(c)}" aria-label="копировать" title="копировать">${ICON.copy}</button></span>`;
