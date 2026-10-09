/* ==========================================================================
   3. Сравнение районов (V4)
   Единое состояние — 01-state.js: CMP.ids, cmpSlot(i), addToComparison(i, anchor),
   removeFromComparison(i), clearComparison(), CMP_HOOKS. Код района в сравнении
   (цвет --sN, форма маркера, штрих линии) закреплён за слотом его ID: удаление,
   добавление, вкладка и тема не меняют код оставшихся. Тип МО — отдельный бейдж.
   А. Профиль индексов: общая шкала процентилей 0–100; у каждого района своя
      дорожка внутри строки индекса — X точный, совпадения стоят друг под другом.
   Б. Месячные траты (ECharts): общая абсолютная шкала, «Вместе» и малые графики
      на одном домене Y, выбранный месяц (←/→), пропуски не соединяются.
   В. Полная таблица: значение индекса m и процентиль mp раздельно, 32 признака, н/д.
   D не изменяется: ряды и списки копируются (slice/map).
   ========================================================================== */
$('#t-cmp').innerHTML = `<div class="phead">
    <div><h2>Сравнение районов</h2>
      <p class="lede">До пяти районов рядом: профиль 13 индексов на общей шкале процентилей, месячные траты на общей шкале в рублях и полная таблица — значение каждого индекса в его единицах отдельно от процентиля и 32 исходных показателя с единицами. Набор общий для всех вкладок: районы добавляются здесь, из карточки района на карте, из корреляций, типов МО и выводов.</p></div>
  </div>
  <div class="cmpbar cx-bar" id="cxTools">
    <label class="field" for="cmpAdd"><span>Район</span><select id="cmpAdd"></select></label>
    <button class="btn primary" type="button" id="cxAddBtn" disabled>${ICON.plus}<span>Добавить</span></button>
    <span class="cx-count" id="cxCount"></span>
    <button class="btn ghost" type="button" id="cmpClear">${ICON.close}<span>Очистить сравнение</span></button>
  </div>
  <ul class="cx-slots" id="cmpSlots" aria-label="Районы в сравнении"></ul>
  <div id="cmpBody"></div>`;

/* ---------- состояние вкладки (не данные): режим, месяц, фокус профиля ---------- */
const CX = {mode: 'joint', month: D.months.length - 1, ix: Object.keys(D.metrics)[0], hot: null, pin: null, cur: {r: 0, l: 0},
  key: null, rec: null, ro: null, el: null, dom: null, sig: '', seen: new Set(), mtOpen: false, ssOpen: false, keyTip: false};
const CX_IX = Object.keys(D.metrics), CX_FT = Object.keys(D.feats), CX_M = D.months.length;
const CX_ORDER = N.map((x, i) => i).sort((a, b) => N[a].s.localeCompare(N[b].s, 'ru'));
const CX_SHAPE = ['circle', 'square', 'diamond', 'triangle', 'ring'];
const CX_SHAPE_NAME = ['круг', 'квадрат', 'ромб', 'треугольник', 'кольцо'];
const CX_DASH = [[], [7, 4], [2, 3], [10, 3, 2, 3], [4, 2]];
const CX_DASH_NAME = ['сплошная', 'штриховая', 'пунктирная', 'штрихпунктирная', 'короткий штрих'];
const CX_EC_SYM = ['circle', 'rect', 'diamond', 'triangle', 'circle'];
const CX_MON = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const CX_MONF = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];
const CX_WIDE = window.matchMedia ? matchMedia('(min-width: 1000px)') : {matches: true, addEventListener(){}};
const cxYM = k => D.months[k].split('-');
const cxMon = k => { const [y, m] = cxYM(k); return CX_MON[+m - 1] + ' ' + y; };
const cxMonF = k => { const [y, m] = cxYM(k); return CX_MONF[+m - 1] + ' ' + y; };
const cxS = i => cmpSlot(i) ?? 0;
const cxRub = v => v == null ? 'н/д' : fmtN(v) + ' ₽';

/* ---------- код района в сравнении: форма + штрих + цвет слота ---------- */
function cxShape(s, cx, cy, r){
  const c = `var(--s${s})`;
  switch (CX_SHAPE[s]) {
    case 'square': return `<rect x="${cx - r * .86}" y="${cy - r * .86}" width="${r * 1.72}" height="${r * 1.72}" rx="1" fill="${c}"/>`;
    case 'diamond': return `<path d="M${cx} ${cy - r * 1.2}L${cx + r * 1.2} ${cy}L${cx} ${cy + r * 1.2}L${cx - r * 1.2} ${cy}Z" fill="${c}"/>`;
    case 'triangle': return `<path d="M${cx} ${cy - r * 1.15}L${cx + r * 1.1} ${cy + r * .85}L${cx - r * 1.1} ${cy + r * .85}Z" fill="${c}"/>`;
    case 'ring': return `<circle cx="${cx}" cy="${cy}" r="${r * .8}" fill="none" stroke="${c}" stroke-width="2.2"/>`;
    default: return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${c}"/>`;
  }
}
const cxIcon = (s, px = 14) => `<svg class="cx-shape" width="${px}" height="${px}" viewBox="0 0 14 14" aria-hidden="true" focusable="false">${cxShape(s, 7, 7, 4.6)}</svg>`;
const cxLineSamp = s => `<svg class="cx-lsamp" width="26" height="10" viewBox="0 0 26 10" aria-hidden="true" focusable="false"><line x1="1" x2="25" y1="5" y2="5" stroke="var(--s${s})" stroke-width="2" stroke-dasharray="${CX_DASH[s].join(' ')}"/></svg>`;
const cxCode = s => `<span class="cx-code" title="код в сравнении: ${CX_SHAPE_NAME[s]}, линия ${CX_DASH_NAME[s]}">${cxIcon(s)}${cxLineSamp(s)}</span>`;
const cxType = i => `<span class="cx-tb"><span class="sw" style="--c:${COLV(N[i].c)}" aria-hidden="true"></span><span><span class="sr">тип: </span>${esc(typeName(N[i].c))}</span></span>`;
const cxTri = up => `<svg viewBox="0 0 8 8" aria-hidden="true" focusable="false"><path d="${up ? 'M4 .8L7.6 7H.4Z' : 'M4 7.2L7.6 1H.4Z'}"/></svg>`;
const cxIxUnit = k => { const u = IX_RAW[k] || {}; return u.kind === 'share' ? (u.unit ? u.unit + ', %' : '%') : (u.unit || 'значение индекса'); };
const cxFtUnit = k => (D.feats[k] || [])[1] === '%' ? 'доля, %' : featUnitText(k);

/* ---------- точность по выбранному набору: округление не прячет различие ----------
   x = 0 — общий формат (fmtIxRaw / fmtF). Если разные исходные значения выбранных районов
   совпали бы после округления, в строке добавляется знак (не больше +3) — одинаково для всей строки. */
function cxIxF(key, v, x){
  if (!x || v == null || Number.isNaN(v)) return fmtIxRaw(key, v);
  const m = IX_RAW[key] || {kind: 'score', d: 2};   // правила fmtIxRaw (02-meta.js) + x знаков
  return m.kind === 'share' ? fmtN(v * 100, 1 + x) + '%' : m.kind === 'meanpct' ? fmtN(v, 1 + x) : m.kind === 'count' ? fmtN(v, x) : fmtN(v, (m.d ?? 2) + x);
}
function cxFtF(key, v, x){
  if (!x || v == null) return fmtF(key, v);
  const u = (D.feats[key] || ['', ''])[1];          // правила fmtF (00-core.js) + x знаков
  return u === '%' ? fmtN(v * 100, 1 + x) + '%' : fmtN(v, (Math.abs(v) >= 100 ? 0 : 2) + x) + (u ? ' ' + u : '');
}
function cxDigits(vals, f){
  const u = [...new Set(vals.filter(v => v != null && !Number.isNaN(v)))];
  for (let x = 0; x < 3; x++) if (new Set(u.map(v => f(v, x))).size === u.length) return x;
  return 3;
}
const cxIxX = (key, ids) => cxDigits(ids.map(i => N[i].m[key]), (v, x) => cxIxF(key, v, x));

/* ---------- ряд трат: покрытие, первая/последняя доступная дата, пропуски ---------- */
function cxStat(i){
  const v = N[i].sp, have = [];
  v.forEach((x, k) => { if (x != null) have.push(k); });
  const runs = []; let a = null;
  v.forEach((x, k) => { if (x == null) { if (a == null) a = k; } else if (a != null) { runs.push([a, k - 1]); a = null; } });
  if (a != null) runs.push([a, v.length - 1]);
  return {n: have.length, first: have.length ? have[0] : null, last: have.length ? have[have.length - 1] : null, runs};
}
function cxCover(i){
  const st = cxStat(i);
  if (!st.n) return `ряд отсутствует: нет данных ни за один из ${CX_M} месяцев`;
  const per = `${cxMon(st.first)} — ${cxMon(st.last)}`;
  if (st.n === CX_M) return `${CX_M} из ${CX_M} мес. · ${per}`;
  const gaps = st.runs.map(([p, q]) => p === q ? cxMon(p) : `${cxMon(p)} — ${cxMon(q)}`).join(', ');
  return `${st.n} из ${CX_M} мес. · первая ${cxMon(st.first)}, последняя ${cxMon(st.last)} · пропуски (не ноль): ${gaps}`;
}

/* ---------- «выше/ниже среди выбранных»: по отображаемым значениям, без ничьих ---------- */
function cxMarks(vals, disp, sense){
  const out = vals.map(() => null), ok = vals.map((v, t) => ({v, t, d: disp[t]})).filter(o => o.v != null);
  if (ok.length < 2) return out;
  ok.sort((a, b) => b.v - a.v);
  const top = ok[0], bot = ok[ok.length - 1];
  if (top.d === bot.d) return out;
  const val = hi => sense > 0 ? (hi ? 'good' : 'bad') : sense < 0 ? (hi ? 'bad' : 'good') : 'neu';
  if (ok.filter(o => o.d === top.d).length === 1) out[top.t] = {hi: true, v: val(true)};
  if (ok.filter(o => o.d === bot.d).length === 1) out[bot.t] = {hi: false, v: val(false)};
  return out;
}
function cxMarkHtml(m){
  if (!m) return '';
  const many = CMP.ids.length > 2, w = m.hi ? (many ? 'выше всех' : 'выше') : (many ? 'ниже всех' : 'ниже');
  const v = m.v === 'good' ? ' · благоприятнее' : m.v === 'bad' ? ' · неблагоприятнее' : '';
  return `<span class="cx-mk ${m.v}">${cxTri(m.hi)}<span>${w}${v}</span></span>`;
}

/* ==========================================================================
   Панель: добавление, счётчик, очистка, карточки слотов
   ========================================================================== */
function cxTools(){
  const s = $('#cmpAdd'), cur = s.value, k = CMP.ids.length;
  s.innerHTML = '<option value="">выберите район…</option>' + CX_ORDER.map(i => `<option value="${i}"${cmpHas(i) ? ' disabled' : ''}>${esc(N[i].s)}${cmpHas(i) ? ' — уже в сравнении' : ''}</option>`).join('');
  s.value = cur !== '' && !cmpHas(+cur) ? cur : '';
  $('#cxAddBtn').disabled = s.value === '';
  $('#cxCount').innerHTML = `<b>${k}</b> из ${CMP_MAX}` + (k >= CMP_MAX ? ' · достигнут предел: уберите район, чтобы добавить другой' : '');
  $('#cmpClear').disabled = !k;
}
function cxSlots(){
  const ids = CMP.ids;
  $('#cmpSlots').innerHTML = ids.map(i => { const s = cxS(i), on = sel === i;
    return `<li class="cx-card${on ? ' on' : ''}" data-i="${i}" style="--sc:var(--s${s})">${cxCode(s)}
      <button type="button" class="cx-nm" data-cxsel="${i}" aria-pressed="${on}" title="Выделить район во всех графиках сравнения">${esc(N[i].s)}</button>
      <div class="cx-ca"><button type="button" class="btn ghost sm cx-ic" data-cxmap="${i}" aria-label="Показать ${esc(N[i].s)} на карте" title="Показать на карте">${ICON.map}</button><button type="button" class="btn ghost sm cx-ic" data-cxrm="${i}" aria-label="Убрать ${esc(N[i].s)} из сравнения" title="Убрать из сравнения">${ICON.close}</button></div><div class="cx-ct">${cxType(i)}</div></li>`; }).join('')
    + (ids.length && ids.length < CMP_MAX ? `<li class="cx-free">свободно ${CMP_MAX - ids.length} из ${CMP_MAX}</li>` : '');
}
function cxAddFromSelect(){
  const s = $('#cmpAdd'); if (s.value === '') { s.focus(); return; }
  const r = addToComparison(+s.value, $('#cxTools'));
  if (r.ok) { s.value = ''; $('#cxAddBtn').disabled = true; s.focus(); }
}
$('#cmpAdd').addEventListener('change', e => { $('#cxAddBtn').disabled = e.target.value === ''; });
$('#cmpAdd').addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.value !== '') { e.preventDefault(); cxAddFromSelect(); } });
$('#cxAddBtn').addEventListener('click', cxAddFromSelect);
$('#cmpClear').addEventListener('click', () => { clearComparison(); $('#cmpAdd').focus(); });
$('#cmpSlots').addEventListener('click', e => {
  const rm = e.target.closest('[data-cxrm]'), sl = e.target.closest('[data-cxsel]'), mp = e.target.closest('[data-cxmap]');
  if (rm) { const i = +rm.dataset.cxrm, ids = CMP.ids.slice(), k = ids.indexOf(i), nx = ids[k + 1] ?? ids[k - 1];
    removeFromComparison(i);
    const f = nx != null ? $(`#cmpSlots [data-cxrm="${nx}"]`) : $('#cmpAdd'); if (f) f.focus(); return; }
  if (sl) { const i = +sl.dataset.cxsel; setSel(sel === i ? null : i); return; }
  if (mp) goMap(+mp.dataset.cxmap);
});

/* ==========================================================================
   Пустое состояние
   ========================================================================== */
function cxEmpty(){
  const big = N.map((x, i) => i).filter(i => N[i].kind === 'ГО').sort((a, b) => N[b].pop - N[a].pop).slice(0, CMP_MAX);
  return `<div class="cx-empty"><h3>В сравнении пока нет районов</h3>
    <p>Выберите район в списке «Район» выше и нажмите «Добавить» — или нажмите «К сравнению» в карточке района на карте, в корреляциях, в типах МО или в выводах. Можно сравнить до ${CMP_MAX} районов; набор сохраняется при переходах между вкладками и смене темы.</p>
    <p class="cx-eh">Быстрый старт — ${CMP_MAX} крупнейших городских округов по населению:</p>
    <div class="cx-epre">${big.map(i => `<span class="cx-tb"><span class="sw" style="--c:${COLV(N[i].c)}" aria-hidden="true"></span><span>${esc(N[i].s)} · ${fmtN(N[i].pop)} чел.</span></span>`).join('')}</div>
    <div><button class="btn primary" type="button" id="cxBig" data-ids="${big.join(',')}">${ICON.plus}<span>Сравнить эти ${CMP_MAX}</span></button></div></div>`;
}

/* ==========================================================================
   А. Профиль индексов: выровненный multi-dot с дорожками районов
   ========================================================================== */
/* шаг дорожки: при 1–2 районах маркер получает зону 24×24; при 3–5 дорожки компактнее (24×12–14),
   эквивалент ≥ 24 px — кнопка названия индекса и кнопки районов в панели значений; на сенсорных — 24 (CSS) */
const cxPitch = k => k <= 2 ? 24 : k === 3 ? 14 : 12;
function cxTipHtml(key, i){
  const d = D.metrics[key], p = N[i].mp[key];
  return `<b>${esc(N[i].s)}</b><div class="tsub">${esc(d.label)}</div>` + (p == null
    ? '<div>нет данных: значения индекса и процентиля нет</div>'
    : `<div>процентиль среди ${n} МО: <span class="tnum">${fmtN(p, 0)}</span></div><div>значение индекса: <span class="tnum">${cxIxF(key, N[i].m[key], cxIxX(key, CMP.ids))}</span></div><div class="tsub">${esc(cxIxUnit(key))}</div>`);
}
function cxProfile(ids){
  const k = ids.length, T = [0, 25, 50, 75, 100];
  const grid = T.map(v => `<span class="cx-g${v === 50 ? ' mid' : ''}" style="left:${v}%" aria-hidden="true"></span>`).join('');
  const axis = top => `<div class="cx-pr cx-axr" aria-hidden="true"><div class="cx-pl">${top ? `<span class="cx-axt">процентиль среди ${n} МО</span>` : ''}</div><div class="cx-pt"><div class="cx-pi">${T.map(v => `<span class="cx-tk${v === 0 ? ' l' : v === 100 ? ' r' : ''}" style="left:${v}%">${v === 50 ? '50 · медиана' : v}</span>`).join('')}</div></div></div>`;
  const rows = CX_IX.map((key, r) => { const d = D.metrics[key], x = cxIxX(key, ids);
    const lanes = ids.map((i, l) => { const s = cxS(i), p = N[i].mp[key], nw = CX.seen.has(i) ? '' : ' nw';
      const at = `data-r="${r}" data-l="${l}" data-i="${i}" tabindex="${r === CX.cur.r && l === CX.cur.l ? 0 : -1}" style="--l:${l}${p == null ? '' : `;left:${p}%`}"`;
      const band = `<span class="cx-band" data-ci="${i}" style="--l:${l}" aria-hidden="true"></span>`;
      if (p == null) return band + `<button type="button" class="cx-na" ${at} aria-label="${esc(N[i].s)}, ${esc(d.label)}: нет данных (н/д)"><span>н/д — нет данных</span></button>`;
      const a = Math.min(p, 50), b = Math.max(p, 50);
      return band + `<span class="cx-stem${nw}" style="--l:${l};--sc:var(--s${s});left:${a}%;width:${b - a}%" aria-hidden="true"></span>`
        + `<button type="button" class="cx-dot${nw}" ${at} aria-label="${esc(N[i].s)}, ${esc(d.label)}: ${fmtPctile(p)} среди ${n} МО; значение индекса ${cxIxF(key, N[i].m[key], x)}, ${esc(cxIxUnit(key))}"><svg viewBox="0 0 14 14" aria-hidden="true" focusable="false">${cxShape(s, 7, 7, 4.8)}</svg></button>`; }).join('');
    /* название индекса — кнопка (≥ 24 px): значения всех выбранных районов в панели; клавиатура — маркеры (↑/↓) */
    return `<div class="cx-pr" data-r="${r}" data-k="${key}"><div class="cx-pl"><button type="button" class="cx-ixb" data-cxix="${key}" tabindex="-1" title="Показать значения всех выбранных районов"><span class="cx-pn">${esc(d.label)}</span><span class="cx-ps">${esc(senseTxt(d))}</span></button></div><div class="cx-pt"><div class="cx-pi">${grid}${lanes}</div></div></div>`; }).join('');
  return `<section class="sec cx-sec" id="cxProfSec" aria-labelledby="cxProfH" tabindex="-1">
    <h3 class="sech" id="cxProfH">Профиль индексов <span class="kicker">процентиль среди ${n} МО · 0–100, не процент</span></h3>
    <p class="secsub">У каждого района своя дорожка внутри строки индекса. Положение по горизонтали — точный процентиль без сдвигов, поэтому совпадающие значения стоят на одной вертикали друг под другом. Отрезок идёт от медианы региона (50) к значению. Наведите, нажмите или выберите маркер с клавиатуры — ${CX_WIDE.matches ? 'справа' : 'ниже'} появятся значение индекса в его единицах и процентиль; нажатие на название индекса показывает значения всех выбранных районов.</p>
    <ol class="cx-lord" aria-label="Порядок дорожек в каждой строке">${ids.map((i, l) => `<li data-ci="${i}"><span class="no">${l + 1}</span>${cxIcon(cxS(i))}<span>${esc(N[i].s)}</span></li>`).join('')}</ol>
    ${k < 2 ? '<p class="cx-one">Добавьте ещё хотя бы один район: сопоставление и отметки «выше/ниже среди выбранных» появляются при двух и более.</p>' : ''}
    <div class="cx-prof"><div class="cx-plot" role="group" aria-label="Профиль индексов, процентили выбранных районов" aria-describedby="cxKeys" style="--pk:${cxPitch(k)}px;--k:${k}">${axis(true)}${rows}${axis(false)}
      <p class="note cx-keys" id="cxKeys">Клавиатура: ↑/↓ — соседний индекс, ←/→ — другой район в той же строке, Home/End — первый/последний район, Enter — выделить район во всех графиках. Точные значения всех индексов — в полной таблице ниже.</p></div>
      <aside class="cx-insp" id="cxInsp" aria-label="Значения выбранного индекса"></aside></div></section>`;
}
function cxInsp(){
  const el = $('#cxInsp'); if (!el) return;
  const key = CX.ix, d = D.metrics[key], ids = CMP.ids, hot = CX.hot != null ? CX.hot : (CX.pin && CX.pin.k === key ? CX.pin.i : null);
  const groups = new Map();
  ids.forEach(i => { const p = N[i].mp[key]; if (p == null) return; const g = fmtN(p, 0); if (!groups.has(g)) groups.set(g, []); groups.get(g).push(i); });
  const ties = [...groups.entries()].filter(([, v]) => v.length > 1);
  const miss = ids.filter(i => N[i].mp[key] == null), x = cxIxX(key, ids);
  el.innerHTML = `<div class="cx-ih"><span class="eyebrow">Индекс ${CX_IX.indexOf(key) + 1} из ${CX_IX.length}</span><h4>${esc(d.label)}</h4><span class="cx-sense">${esc(senseTxt(d))}</span></div>
    <p class="cx-if">${esc(d.formula)}</p><p class="cx-ii">${esc(d.interp)}</p>
    <dl class="cx-idl"><dt>значение индекса</dt><dd>${esc(cxIxUnit(key))}</dd><dt>процентиль</dt><dd>место среди ${n} МО, 0–100 (не процент)</dd></dl>
    <table class="cx-it"><thead><tr><th scope="col">Район</th><th scope="col" class="n">Значе&shy;ние</th><th scope="col" class="n">Процен&shy;тиль</th></tr></thead>
    <tbody>${ids.map(i => `<tr class="${i === hot ? 'hot' : ''}" data-ci="${i}"><th scope="row"><button type="button" class="cx-ipick" data-cxpick="${i}" tabindex="-1" aria-pressed="${sel === i}" title="Выделить район во всех графиках сравнения"><span class="cx-in">${cxIcon(cxS(i))}<span>${esc(N[i].s)}</span></span></button></th><td class="n">${N[i].m[key] == null ? NA : cxIxF(key, N[i].m[key], x)}</td><td class="n">${N[i].mp[key] == null ? NA : fmtN(N[i].mp[key], 0)}</td></tr>`).join('')}</tbody></table>
    ${x ? `<p class="cx-tie">Значения показаны с дополнительным знаком: при обычном округлении разные значения выбранных районов совпали бы.</p>` : ''}
    ${ties.map(([p, v]) => `<p class="cx-tie">Одинаковый процентиль ${p}: ${v.map(i => esc(N[i].s)).join(', ')} — маркеры на одной вертикали, каждый в своей дорожке.</p>`).join('')}
    ${miss.length ? `<p class="cx-tie">Нет данных (н/д, не ноль): ${miss.map(i => esc(N[i].s)).join(', ')}.</p>` : ''}`;
  cxEmphIn(el);
  $$('#t-cmp .cx-pr[data-k]').forEach(r => { const on = r.dataset.k === key; r.classList.toggle('cur', on); const b = r.querySelector('.cx-ixb'); if (b) { if (on) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); } });
}
/* узкий экран: панель значений встаёт сразу под активной строкой (после нажатия/фокуса) */
function cxPlace(){
  const ins = $('#cxInsp'), prof = $('#t-cmp .cx-prof'), plot = $('#t-cmp .cx-plot'); if (!ins || !prof) return;
  if (CX_WIDE.matches) { if (ins.parentElement !== prof) prof.appendChild(ins); return; }
  const row = CX.pin ? $(`#t-cmp .cx-pr[data-k="${CX.pin.k}"]`) : null;
  if (row) { if (row.nextElementSibling !== ins) row.after(ins); }
  else { const keys = $('#cxKeys'); if (keys && keys.previousElementSibling !== ins) plot.insertBefore(ins, keys); }
}
CX_WIDE.addEventListener('change', () => { cxPlace(); const sub = $('#cxProfSec .secsub'); if (sub) sub.innerHTML = sub.innerHTML.replace(/справа|ниже(?= появятся)/, CX_WIDE.matches ? 'справа' : 'ниже'); });
function cxMarkerAt(r, l){ return $(`#t-cmp .cx-plot [data-r="${r}"][data-l="${l}"]`); }
/* отметка закреплённого маркера и вход по Tab на ту же строку (roving tabindex) */
function cxPinMark(){
  const plot = $('#t-cmp .cx-plot'); if (!plot) return;
  plot.querySelectorAll('.pin').forEach(o => o.classList.remove('pin'));
  if (!CX.pin) return;
  const r = CX_IX.indexOf(CX.pin.k), l = CX.pin.i == null ? -1 : CMP.ids.indexOf(CX.pin.i);
  const b = l >= 0 ? cxMarkerAt(r, l) : null; if (!b) return;
  b.classList.add('pin');
  plot.querySelectorAll('.cx-dot[tabindex="0"],.cx-na[tabindex="0"]').forEach(o => { if (o !== b) o.tabIndex = -1; }); b.tabIndex = 0; CX.cur = {r, l};
}
function cxBindProfile(){
  const plot = $('#t-cmp .cx-plot'); if (!plot) return;
  /* эквиваленты маркеров с зоной ≥ 24 px: название индекса → значения всех районов; район в панели → выделение */
  plot.addEventListener('click', e => { const ib = e.target.closest('[data-cxix]'); if (!ib) return;
    const key = ib.dataset.cxix, i = sel != null && cmpHas(sel) ? sel : CX.pin && cmpHas(CX.pin.i) ? CX.pin.i : null;
    CX.ix = key; CX.hot = null; CX.pin = {k: key, i}; hideTip(); cxPinMark(); cxInsp(); cxPlace(); });
  $('#cxInsp').addEventListener('click', e => { const b = e.target.closest('[data-cxpick]'); if (!b) return;
    const i = +b.dataset.cxpick; CX.pin = {k: CX.ix, i}; CX.hot = null; cxPinMark();
    $$('#cxInsp tr[data-ci]').forEach(tr => tr.classList.toggle('hot', +tr.dataset.ci === i));
    setSel(sel === i ? null : i); });
  const info = b => ({key: CX_IX[+b.dataset.r], i: +b.dataset.i, r: +b.dataset.r, l: +b.dataset.l});
  const tipAt = b => { const r = b.getBoundingClientRect(), x = info(b); showTip({clientX: r.right + 2, clientY: r.bottom + 2}, cxTipHtml(x.key, x.i)); };
  plot.addEventListener('mouseover', e => { const b = e.target.closest('.cx-dot,.cx-na'); if (!b || !CX_WIDE.matches) return; const x = info(b);
    showTip(e, cxTipHtml(x.key, x.i)); if (CX_WIDE.matches) { CX.ix = x.key; CX.hot = x.i; cxInsp(); } });
  plot.addEventListener('mousemove', e => { const b = e.target.closest('.cx-dot,.cx-na'); if (b && CX_WIDE.matches) { const x = info(b); showTip(e, cxTipHtml(x.key, x.i)); } });
  plot.addEventListener('mouseout', e => { const b = e.target.closest('.cx-dot,.cx-na'); if (!b || b.contains(e.relatedTarget)) return; hideTip();
    if (CX.hot != null) { CX.hot = null; if (CX.pin) CX.ix = CX.pin.k; cxInsp(); } });
  plot.addEventListener('focusin', e => { const b = e.target.closest('.cx-dot,.cx-na'); if (!b) return; const x = info(b);
    plot.querySelectorAll('.cx-dot[tabindex="0"],.cx-na[tabindex="0"]').forEach(o => { if (o !== b) o.tabIndex = -1; }); b.tabIndex = 0;
    CX.cur = {r: x.r, l: x.l}; CX.ix = x.key; CX.pin = {k: x.key, i: x.i}; CX.hot = null;
    plot.querySelectorAll('.pin').forEach(o => o.classList.remove('pin')); b.classList.add('pin');
    cxInsp(); cxPlace(); if (CX_WIDE.matches && b.matches(':focus-visible')) tipAt(b); });
  plot.addEventListener('focusout', e => { if (e.target.closest('.cx-dot,.cx-na')) hideTip(); });
  plot.addEventListener('click', e => { const b = e.target.closest('.cx-dot,.cx-na'); if (!b) return; const x = info(b);
    if (document.activeElement !== b) b.focus(); CX.pin = {k: x.key, i: x.i}; CX.ix = x.key;
    if (sel !== x.i) setSel(x.i); if (CX_WIDE.matches) tipAt(b); else hideTip(); });
  plot.addEventListener('keydown', e => { const b = e.target.closest('.cx-dot,.cx-na'); if (!b) return;
    const k = CMP.ids.length; let {r, l} = info(b);
    if (e.key === 'ArrowDown') r = Math.min(CX_IX.length - 1, r + 1); else if (e.key === 'ArrowUp') r = Math.max(0, r - 1);
    else if (e.key === 'ArrowRight') l = Math.min(k - 1, l + 1); else if (e.key === 'ArrowLeft') l = Math.max(0, l - 1);
    else if (e.key === 'Home') l = 0; else if (e.key === 'End') l = k - 1;
    else if (e.key === 'Escape') { hideTip(); return; } else return;
    e.preventDefault(); const t = cxMarkerAt(r, l); if (t) t.focus(); });
}

/* ==========================================================================
   Б. Месячные траты: ECharts, общая абсолютная шкала, выбранный месяц
   ========================================================================== */
function cxSpend(ids){
  return `<section class="sec cx-sec" id="cxSpendSec" aria-labelledby="cxSpendH" tabindex="-1">
    <div class="cx-shd"><h3 class="sech" id="cxSpendH">Безналичные траты на жителя <span class="kicker">₽ в месяц · ${CX_M} месяцев · ${cxMon(0)} — ${cxMon(CX_M - 1)}</span></h3>
      <div class="seg" role="group" aria-label="Вид графика трат"><button type="button" data-cxmode="joint" aria-pressed="${CX.mode === 'joint'}">Вместе</button><button type="button" data-cxmode="multi" aria-pressed="${CX.mode === 'multi'}">Малые графики</button></div></div>
    <p class="secsub" id="cxSpendSub"></p>
    <ul class="cx-leg" id="cxLeg" aria-label="Районы: значение в выбранном месяце и покрытие ряда">${ids.map(i => { const s = cxS(i), st = cxStat(i);
      return `<li><button type="button" class="cx-li${st.n ? '' : ' miss'}" data-cxsel="${i}" data-ci="${i}" aria-pressed="${sel === i}">${cxCode(s)}<span class="cx-ln">${esc(N[i].s)}</span><span class="cx-lv" data-cxv="${i}"></span><span class="cx-lc">${esc(cxCover(i))}</span></button></li>`; }).join('')}</ul>
    <div class="cx-monbar" role="group" aria-label="Выбранный месяц">
      <button type="button" class="btn sm cx-mb" data-cxmon="-1" aria-label="Предыдущий месяц"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg></button>
      <span class="cx-monl" id="cxMonL"></span>
      <button type="button" class="btn sm cx-mb" data-cxmon="1" aria-label="Следующий месяц"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg></button>
      <span class="hint">или ←/→, Home/End на графике; щелчок по графику выбирает месяц</span></div>
    <div class="cx-chart" id="cxSpend" tabindex="0" role="group" aria-roledescription="график" aria-label="Траты на жителя по месяцам. Стрелки влево и вправо выбирают месяц, значения выбранного месяца — в списке районов выше" aria-describedby="cxLive"></div>
    <p class="sr" id="cxLive" aria-live="polite"></p>
    ${cxSeas()}
    <details class="cx-mt" id="cxMt"${CX.mtOpen ? ' open' : ''}><summary>${ICON.chev}<span>Все ${CX_M} месяцев — таблица значений, ₽ на жителя</span></summary>${cxMonthTable(ids)}</details></section>`;
}
/* ---------- сезонность (ТЗ 12.4): 2 года × 12 месяцев на общей шкале — раскрываемый блок под графиком ----------
   Только реальные 24 месяца двух календарных лет (иначе блока нет, дни не имитируются). Цвет клетки — тот же домен,
   что у оси Y графика (общая шкала всех выбранных районов); пропуск — штриховка «н/д», не ноль. Чисел в клетках нет
   (на средних тонах ни тёмный, ни светлый текст не даёт 4,5:1): точные значения — скрытым текстом в клетках для
   чтения с экрана, строкой выбранного месяца под полосой, в списке районов и в таблице всех месяцев. Щелчок по клетке
   выбирает месяц графика. Вход — короткое проявление клеток; после раскрытия значения неподвижны. */
const CX_SEAS = CX_M === 24 && /-01$/.test(D.months[0]) && /-12$/.test(D.months[CX_M - 1]);
const cxSeas = () => !CX_SEAS ? '' : `<details class="cx-mt cx-ss" id="cxSs"${CX.ssOpen ? ' open' : ''}><summary>${ICON.chev}<span>Сезонность: 2 года × 12 месяцев на общей шкале</span></summary><div id="cxSsBody"></div></details>`;
function cxSeasBody(ids){
  const d = CX.dom; if (!d) return '<p class="note">У выбранных районов нет данных о тратах ни за один месяц.</p>';
  const yrs = [cxYM(0)[0], cxYM(12)[0]], span = d.hi - d.lo || 1;
  const pc = v => Math.round(8 + 92 * Math.max(0, Math.min(1, (v - d.lo) / span)));   // 8%: самое малое значение отличается от пустой клетки
  const head = `<tr><th scope="col"><span class="sr">Район и год</span></th>${CX_MON.map((m, j) => `<th scope="col" data-mm="${j}">${m}</th>`).join('')}</tr>`;
  const body = ids.map(i => { const st = cxStat(i), nm = `${cxIcon(cxS(i))}<span class="cx-ssnm">${esc(N[i].s)}</span>`;
    /* ряда нет совсем — одна строка с объяснением вместо 24 заштрихованных клеток */
    if (!st.n) return `<tr data-ci="${i}" class="y1 none"><th scope="row"><span class="cx-ssh">${nm}</span></th><td colspan="12" class="cx-ssnone">нет данных о тратах ни за один месяц — не ноль</td></tr>`;
    return yrs.map((y, r) => `<tr data-ci="${i}" class="${r ? 'y2' : 'y1'}"><th scope="row"><span class="cx-ssh">${r ? `<span class="sr">${esc(N[i].s)}, </span>` : nm}<span class="cx-ssy">${y}</span></span></th>`
      + CX_MON.map((m, j) => { const k = r * 12 + j, v = N[i].sp[k], lab = `${esc(N[i].s)}, ${cxMonF(k)}: `;
        return v == null ? `<td class="nd" data-k="${k}" title="${lab}н/д — нет данных (не ноль)"><span class="sr">н/д</span></td>`
          : `<td class="v" data-k="${k}" style="--t:${pc(v)}%" title="${lab}${cxRub(v)}"><span class="sr">${cxRub(v)}</span></td>`; }).join('') + '</tr>').join(''); }).join('');
  return `<p class="note cx-ssn">Каждая строка — календарный год района, столбцы — месяцы. Цвет — траты на жителя на общей шкале всех выбранных районов (та же, что у оси графика); штриховка — пропуск в данных, не ноль. Нажмите клетку — месяц выберется на графике.</p>
    <div class="cx-ssleg" aria-hidden="true"><span class="grad"></span><span class="mono">${fmtN(d.lo)} ₽</span><span>→</span><span class="mono">${fmtN(d.hi)} ₽</span><span class="cx-ssnd"><span class="ndsw"></span>н/д — нет данных</span></div>
    <div class="tbox cx-ssbox" role="region" aria-label="Сезонность трат: районы по годам и месяцам" tabindex="0"><table class="cx-sst"><caption class="sr">Траты на жителя, ₽ в месяц: строки — район и год, столбцы — месяцы</caption>
      <colgroup><col class="cx-ssc0">${'<col>'.repeat(12)}</colgroup><thead>${head}</thead><tbody>${body}</tbody></table></div>
    <p class="cx-ssr" id="cxSsR"></p>`;
}
/* выбранный месяц: клетка в каждой строке своего года, заголовок столбца, строка значений под полосой */
function cxSeasMark(){
  const T = $('#cxSs .cx-sst'); if (!T) return; const k = CX.month;
  T.querySelectorAll('td.cur, th.cur').forEach(e => e.classList.remove('cur'));
  T.querySelectorAll(`td[data-k="${k}"]`).forEach(e => e.classList.add('cur'));
  const h = T.querySelector(`thead th[data-mm="${k % 12}"]`); if (h) h.classList.add('cur');
  const r = $('#cxSsR'); if (r) r.innerHTML = `<b>${cxMonF(k)}:</b> ` + CMP.ids.map(i => `<span class="cx-ssri">${cxIcon(cxS(i), 12)}${esc(N[i].s)} — <span class="mono">${N[i].sp[k] == null ? 'н/д' : cxRub(N[i].sp[k])}</span></span>`).join(' ');
}
function cxSeasOpen(anim){
  const b = $('#cxSsBody'); if (!b) return;
  b.innerHTML = cxSeasBody(CMP.ids); cxSeasMark(); cxEmphIn(b);
  if (!anim || RM.matches) return;
  b.querySelectorAll('.cx-sst td').forEach(c => c.animate([{opacity: 0}, {opacity: 1}], {duration: 240, delay: (+c.dataset.k % 12) * 14, easing: 'ease-out', fill: 'backwards'}));
}
function cxMonthTable(ids){
  const st = ids.map(cxStat);
  const head = `<tr><th scope="col">Месяц</th>${ids.map(i => `<th scope="col" class="n" data-ci="${i}"><span class="cx-hn">${cxIcon(cxS(i))}<span>${esc(N[i].s)}</span></span></th>`).join('')}</tr>`;
  const body = D.months.map((m, k) => `<tr data-mk="${k}"${k === CX.month ? ' class="sel"' : ''}><th scope="row"><button type="button" class="link cx-mkb" data-cxmk="${k}" aria-label="Выбрать ${cxMonF(k)}">${cxMon(k)}</button></th>${ids.map((i, t) => { const v = N[i].sp[k], s = st[t];
    const tag = k === s.first && k === s.last ? 'единственная' : k === s.first ? 'первая' : k === s.last ? 'последняя' : '';
    return `<td class="n" data-ci="${i}">${v == null ? NA : fmtN(v)}${tag ? `<span class="cx-ft">${tag}</span>` : ''}</td>`; }).join('')}</tr>`).join('');
  const foot = [['Доступно месяцев', (i, s) => `${s.n} из ${CX_M}`], ['Медиана доступных месяцев', i => { const m = median(N[i].sp); return m == null ? NA : fmtN(m); }],
    ['Минимум', (i, s) => s.n ? fmtN(Math.min(...N[i].sp.filter(v => v != null))) : NA], ['Максимум', (i, s) => s.n ? fmtN(Math.max(...N[i].sp.filter(v => v != null))) : NA]]
    .map(([l, f]) => `<tr><th scope="row">${l}</th>${ids.map((i, t) => `<td class="n" data-ci="${i}">${f(i, st[t])}</td>`).join('')}</tr>`).join('');
  return `<p class="note cx-mtn">Отмечены первая и последняя доступные даты каждого ряда; «н/д» — пропуск в данных, не ноль. Нажмите месяц, чтобы выбрать его на графике.</p>
    <div class="tbox cx-mtbox" role="region" aria-label="Траты по месяцам, таблица" tabindex="0"><table class="cx-mtab" style="--k:${ids.length}"><thead>${head}</thead><tbody>${body}</tbody><tfoot>${foot}</tfoot></table></div>`;
}
function cxDom(ids){
  const all = []; ids.forEach(i => N[i].sp.forEach(v => { if (v != null) all.push(v); }));
  if (!all.length) return null;
  let lo = Math.min(...all), hi = Math.max(...all); if (hi - lo < 1) { lo -= 500; hi += 500; }
  const t = niceTicks(lo, hi, 5), st = t.length > 1 ? t[1] - t[0] : (hi - lo);
  return {lo: Math.floor(lo / st) * st, hi: Math.ceil(hi / st) * st, st};
}
function cxColors(){ return {s: [0, 1, 2, 3, 4].map(t => css('--s' + t)), ink: css('--ink'), ink2: css('--ink2'), muted: css('--muted'), ls: css('--line-strong'),
  lsoft: css('--line-soft'), line: css('--line'), surf: css('--surface'), pe: css('--pearl-edge')}; }
/* подписи месяцев: шаг по реальной ширине, первая и последняя дата видны всегда */
function cxLabels(pw){
  const sp = pw / (CX_M - 1), need = 36, st = [1, 2, 3, 4, 6, 12].find(s => s * sp >= need) || 12, set = new Set();
  for (let k = 0; k < CX_M; k += st) set.add(k);
  const lm = Math.floor((CX_M - 1) / st) * st;
  if (lm !== CX_M - 1) { if ((CX_M - 1 - lm) * sp < need) set.delete(lm); set.add(CX_M - 1); }
  return {set, st};
}
const cxAxLab = k => { const [y, m] = cxYM(k); return k === 0 || k === CX_M - 1 || m === '01' ? CX_MON[+m - 1] + '\n' + y : CX_MON[+m - 1]; };
function cxLayout(W){
  const ids = CMP.ids, k = ids.length;
  if (CX.mode === 'joint') { const small = W < 560, end = W >= 720;
    const g = {left: small ? 54 : 64, right: end ? Math.min(176, 30 + 7.4 * Math.max(...ids.filter(i => cxStat(i).n).map(i => N[i].s.length), 4)) : 16, top: 34, bottom: 46};
    const H = small ? 300 : 360, lab = cxLabels(W - g.left - g.right);
    return {sig: ['j', small, end, lab.st, g.right].join(), H, g, lab, end}; }
  const cols = Math.max(1, Math.min(k, W >= 940 ? 3 : W >= 580 ? 2 : 1)), rows = Math.ceil(k / cols), gx = 28, gy = 18, ph = 214;
  const pw = (W - gx * (cols - 1)) / cols, gl = 54, gr = 12, gt = 40, gb = 44, lab = cxLabels(pw - gl - gr);
  return {sig: ['m', cols, lab.st].join(), H: rows * ph + (rows - 1) * gy, cols, gx, gy, ph, pw, gl, gr, gt, gb, lab};
}
function cxXAxis(gi, lab, C){ return {type: 'category', gridIndex: gi, data: D.months.slice(), boundaryGap: false,
  axisLine: {lineStyle: {color: C.ls}}, axisTick: {alignWithLabel: true, interval: 0, lineStyle: {color: C.line}},
  axisLabel: {interval: k => lab.set.has(k), formatter: (v, k) => cxAxLab(k), color: C.ink2, fontSize: 11.5, lineHeight: 14}, splitLine: {show: false}}; }
function cxYAxis(gi, C, name){ const d = CX.dom; return {type: 'value', gridIndex: gi, min: d.lo, max: d.hi, interval: d.st,
  axisLabel: {formatter: v => fmtN(v), color: C.ink2, fontSize: 11.5}, splitLine: {lineStyle: {color: C.lsoft}}, axisLine: {show: false}, axisTick: {show: false},
  name: name ? '₽ на жителя в месяц' : '', nameLocation: 'end', nameGap: 14, nameTextStyle: {color: C.ink2, fontSize: 11.5, align: 'left'}}; }
function cxLine(i, gi, C){
  const s = cxS(i), col = C.s[s], st = cxStat(i), em = sel === i, dim = sel != null && cmpHas(sel) && sel !== i && CX.mode === 'joint';
  const data = N[i].sp.map((v, k) => v == null ? null : (k === st.first || k === st.last) ? {value: v, symbolSize: 9} : v);
  return {id: `L${i}_${gi}`, name: N[i].s, type: 'line', xAxisIndex: gi, yAxisIndex: gi, data, connectNulls: false, showSymbol: true, showAllSymbol: true,
    symbol: CX_EC_SYM[s], symbolSize: 5, z: em ? 6 : 4, cursor: 'default',
    lineStyle: {color: col, width: em ? 3 : 2, type: CX_DASH[s].length ? CX_DASH[s].slice() : 'solid', opacity: dim ? .3 : 1},
    itemStyle: s === 4 ? {color: C.surf, borderColor: col, borderWidth: 1.8, opacity: dim ? .3 : 1} : {color: col, opacity: dim ? .3 : 1},
    emphasis: {focus: 'series', lineStyle: {width: 3}}, blur: {lineStyle: {opacity: .2}, itemStyle: {opacity: .2}},
    endLabel: {show: false}};
}
function cxCursor(gi, list, C){
  const k = CX.month, m = D.months[k];
  const pts = list.filter(i => N[i].sp[k] != null).map(i => { const s = cxS(i), col = C.s[s];
    return {value: [m, N[i].sp[k]], symbol: CX_EC_SYM[s], itemStyle: s === 4 ? {color: C.surf, borderColor: col, borderWidth: 2.6} : {color: col, borderColor: C.surf, borderWidth: 2}}; });
  return {id: `C${gi}`, type: 'scatter', xAxisIndex: gi, yAxisIndex: gi, data: pts, symbolSize: 12, z: 9, silent: true, tooltip: {show: false},
    markLine: {silent: true, symbol: ['none', 'none'], label: {show: false}, lineStyle: {color: C.pe, width: 1.5, type: 'solid', opacity: .9}, data: [{xAxis: m}]}};
}
function cxTooltip(C){ return {trigger: 'axis', confine: true, className: 'cx-tip', axisPointer: {type: 'line', lineStyle: {color: C.ls, width: 1}},
  formatter: ps => { const p = Array.isArray(ps) ? ps[0] : ps; if (!p) return ''; const k = D.months.indexOf(p.axisValue); return k < 0 ? '' : cxTipMonth(k); }}; }
function cxTipMonth(k){ return `<div class="cx-tt"><b>${cxMonF(k)}</b>` + CMP.ids.map(i => `<div class="cx-tr">${cxIcon(cxS(i), 12)}<span>${esc(N[i].s)}</span><span class="cx-tv">${N[i].sp[k] == null ? (cxStat(i).n ? 'н/д · пропуск' : 'ряда нет') : cxRub(N[i].sp[k])}</span></div>`).join('') + '</div>'; }
function cxShapeGraphic(s, x, y, col, surf, id){
  const r = 5, base = {id, z: 10, silent: true};
  switch (CX_SHAPE[s]) {
    case 'square': return {...base, type: 'rect', shape: {x: x - 4.3, y: y - 4.3, width: 8.6, height: 8.6}, style: {fill: col}};
    case 'diamond': return {...base, type: 'polygon', shape: {points: [[x, y - 6], [x + 6, y], [x, y + 6], [x - 6, y]]}, style: {fill: col}};
    case 'triangle': return {...base, type: 'polygon', shape: {points: [[x, y - 5.7], [x + 5.5, y + 4.2], [x - 5.5, y + 4.2]]}, style: {fill: col}};
    case 'ring': return {...base, type: 'circle', shape: {cx: x, cy: y, r: 4}, style: {fill: surf, stroke: col, lineWidth: 2.2}};
    default: return {...base, type: 'circle', shape: {cx: x, cy: y, r}, style: {fill: col}};
  }
}
/* прямые подписи рядов справа: позиции по домену, раздвигаются по реальной высоте строки (без наложений) */
function cxEndLabels(ids, W, L, C){
  const d = CX.dom, g = L.g, ph = L.H - g.top - g.bottom, pw = W - g.left - g.right, gap = 16;
  const Y = v => g.top + (1 - (v - d.lo) / (d.hi - d.lo)) * ph;
  const labs = ids.map(i => { const st = cxStat(i); if (!st.n) return null; const v = N[i].sp[st.last];
    return {i, y: Y(v), ly: Y(v), x: g.left + pw * st.last / (CX_M - 1)}; }).filter(Boolean).sort((a, b) => a.y - b.y);
  for (let k = 1; k < labs.length; k++) if (labs[k].ly - labs[k - 1].ly < gap) labs[k].ly = labs[k - 1].ly + gap;
  const maxY = g.top + ph + 6;
  if (labs.length && labs[labs.length - 1].ly > maxY) { labs[labs.length - 1].ly = maxY;
    for (let k = labs.length - 2; k >= 0; k--) if (labs[k + 1].ly - labs[k].ly < gap) labs[k].ly = labs[k + 1].ly - gap; }
  const x0 = W - g.right + 14, out = [];
  labs.forEach(l => {
    out.push({id: `el${l.i}`, type: 'text', x: x0, y: l.ly, silent: true, z: 10, style: {text: N[l.i].s, fill: sel === l.i ? C.ink : C.ink2,
      font: `${sel === l.i ? 600 : 500} 12px "Golos Text", system-ui, sans-serif`, textVerticalAlign: 'middle', verticalAlign: 'middle'}});
    out.push({id: `ek${l.i}`, type: 'polyline', silent: true, z: 2, shape: {points: [[l.x + 7, l.y], [x0 - 8, l.y], [x0 - 3, l.ly]]}, style: {stroke: C.ls, lineWidth: 1, fill: null}});
  });
  return out;
}
function cxSpendOpt(ch){
  const ids = CMP.ids.slice(), C = cxColors(), W = ch.getWidth(), L = cxLayout(W);
  CX.sig = L.sig; if (CX.el) CX.el.style.height = L.H + 'px';
  const base = {animationDuration: 650, animationDurationUpdate: 280, animationEasingUpdate: 'cubicOut', tooltip: cxTooltip(C)};
  if (CX.mode === 'joint') {
    const series = ids.map(i => cxLine(i, 0, C)); series.push(cxCursor(0, ids, C));
    return {...base, grid: {...L.g}, xAxis: cxXAxis(0, L.lab, C), yAxis: cxYAxis(0, C, true), series, graphic: {elements: L.end ? cxEndLabels(ids, W, L, C) : []}};
  }
  const grid = [], xAxis = [], yAxis = [], series = [], gr = [];
  ids.forEach((i, t) => { const c = t % L.cols, r = Math.floor(t / L.cols), x0 = c * (L.pw + L.gx), y0 = r * (L.ph + L.gy), s = cxS(i), st = cxStat(i);
    grid.push({left: x0 + L.gl, top: y0 + L.gt, width: L.pw - L.gl - L.gr, height: L.ph - L.gt - L.gb});
    xAxis.push(cxXAxis(t, L.lab, C)); yAxis.push(cxYAxis(t, C, false));
    ids.filter(j => j !== i).forEach(j => series.push({id: `O${j}_${t}`, type: 'line', xAxisIndex: t, yAxisIndex: t, data: N[j].sp.slice(), connectNulls: false,
      showSymbol: false, silent: true, z: 1, lineStyle: {color: C.ls, width: 1, opacity: .7}, emphasis: {disabled: true}, tooltip: {show: false}}));
    series.push(cxLine(i, t, C)); series.push(cxCursor(t, [i], C));
    gr.push(cxShapeGraphic(s, x0 + 6, y0 + 13, C.s[s], C.surf, `gs${t}`));
    gr.push({id: `gt${t}`, type: 'text', x: x0 + 18, y: y0 + 4, silent: true, style: {text: N[i].s, fill: C.ink, font: '600 13px "Golos Text", system-ui, sans-serif', textVerticalAlign: 'top', verticalAlign: 'top'}});
    gr.push({id: `gc${t}`, type: 'text', x: x0 + L.pw - 4, y: y0 + 6, silent: true, style: {text: st.n ? `${st.n} из ${CX_M} мес.` : 'ряда нет', fill: C.muted,
      font: '11.5px "Golos Text", system-ui, sans-serif', textAlign: 'right', align: 'right', textVerticalAlign: 'top', verticalAlign: 'top'}});
    if (!st.n) gr.push({id: `gn${t}`, type: 'text', x: x0 + L.gl + (L.pw - L.gl - L.gr) / 2, y: y0 + L.gt + (L.ph - L.gt - L.gb) / 2, silent: true,
      style: {text: 'Нет данных о тратах\nни за один месяц', fill: C.ink2, font: '12.5px "Golos Text", system-ui, sans-serif', textAlign: 'center', align: 'center',
        textVerticalAlign: 'middle', verticalAlign: 'middle', lineHeight: 17, backgroundColor: C.surf, padding: [4, 8]}});
  });
  return {...base, grid, xAxis, yAxis, series, graphic: {elements: gr}, axisPointer: {link: [{xAxisIndex: 'all'}]}};
}
function cxSpendText(){
  const sub = $('#cxSpendSub'); if (!sub) return;
  const d = CX.dom;
  sub.textContent = (CX.mode === 'joint' ? 'Все выбранные районы на одной абсолютной шкале.' : `Малые графики на том же домене Y, что и общий график (${d ? fmtN(d.lo) + '–' + fmtN(d.hi) + ' ₽' : 'нет данных'}); серые линии — остальные выбранные районы.`)
    + (d && d.lo > 0 ? ' Ось Y начинается не с нуля.' : '') + ' Пропуски не соединяются линией и не заменяются нулём; крупные маркеры — первая и последняя доступные даты ряда.';
}
function cxMonthUI(){
  const k = CX.month, L = $('#cxMonL'); if (!L) return;
  L.textContent = cxMonF(k);
  $$('#cxSpendSec [data-cxmon]').forEach(b => { const off = (+b.dataset.cxmon < 0 && k === 0) || (+b.dataset.cxmon > 0 && k === CX_M - 1); b.setAttribute('aria-disabled', off); });
  CMP.ids.forEach(i => { const e = $(`#cxLeg [data-cxv="${i}"]`); if (e) { const v = N[i].sp[k];
    e.textContent = v != null ? cxRub(v) : cxStat(i).n ? 'н/д · пропуск' : 'ряда нет'; e.classList.toggle('nd', v == null); } });
  $$('#cxMt tbody tr').forEach(tr => tr.classList.toggle('sel', +tr.dataset.mk === k));
  cxSeasMark();
  $('#cxLive').textContent = cxMonF(k) + ': ' + CMP.ids.map(i => `${N[i].s} — ${N[i].sp[k] != null ? cxRub(N[i].sp[k]) : 'нет данных'}`).join('; ');
}
function cxSetMonth(k, viaKey){
  k = Math.max(0, Math.min(CX_M - 1, k)); if (k === CX.month && !viaKey) return;
  CX.month = k; cxMonthUI();
  if (CX.rec && CX.rec.chart) { CX.rec.refresh(false); if (viaKey) cxKeyTip(); }
}
function cxKeyTip(){
  const ch = CX.rec && CX.rec.chart; if (!ch) return;
  const x = ch.convertToPixel({xAxisIndex: 0}, D.months[CX.month]), g = ch.getModel().getComponent('grid', 0);
  const y = g ? g.coordinateSystem.getRect().y + 24 : 40;
  if (x != null && !Number.isNaN(x)) ch.dispatchAction({type: 'showTip', x, y});
}
function cxChartBind(ch){
  ch.getZr().on('click', e => { const g = CX.mode === 'joint' ? 1 : CMP.ids.length;
    for (let t = 0; t < g; t++) if (ch.containPixel({gridIndex: t}, [e.offsetX, e.offsetY])) {
      const v = ch.convertFromPixel({gridIndex: t}, [e.offsetX, e.offsetY]); const k = Math.round(Array.isArray(v) ? v[0] : v);
      if (!Number.isNaN(k)) cxSetMonth(k); return; } });
}
function cxSpendInit(){
  const el = $('#cxSpend'); if (!el) return; CX.el = el;
  CX.dom = cxDom(CMP.ids); cxSpendText(); cxMonthUI();
  if (CX.ssOpen) cxSeasOpen(false);   // блок сезонности остаётся раскрытым при смене набора — без повторного входа
  if (!CX.dom) { el.removeAttribute('tabindex'); el.classList.add('none');
    el.innerHTML = '<div class="cx-nodata"><b>График не строится: у выбранных районов нет данных о тратах ни за один месяц.</b><span>Причина указана у каждого района в списке выше; все 24 месяца — в таблице ниже (н/д).</span></div>';
    $$('#cxSpendSec [data-cxmon], #cxSpendSec [data-cxmode]').forEach(b => b.setAttribute('aria-disabled', 'true')); return; }
  el.style.height = cxLayout(el.clientWidth || 1000).H + 'px';
  CX.rec = makeChart(el, cxSpendOpt, {renderer: 'svg', onInit: cxChartBind});
  CX.ro = onResize(el, r => { if (!CX.rec || !CX.rec.chart) return; const L = cxLayout(r.width); if (L.sig !== CX.sig) { CX.rec.chart.resize(); CX.rec.refresh(true); } });
  el.addEventListener('keydown', e => { let k = CX.month;
    if (e.key === 'ArrowLeft') k--; else if (e.key === 'ArrowRight') k++; else if (e.key === 'Home') k = 0; else if (e.key === 'End') k = CX_M - 1;
    else if (e.key === 'Escape') { if (CX.rec && CX.rec.chart) CX.rec.chart.dispatchAction({type: 'hideTip'}); return; } else return;
    e.preventDefault(); cxSetMonth(k, true); });
  el.addEventListener('blur', () => { if (CX.rec && CX.rec.chart) CX.rec.chart.dispatchAction({type: 'hideTip'}); });
}
function cxBindSpend(){
  const sec = $('#cxSpendSec'); if (!sec) return;
  sec.addEventListener('click', e => {
    const md = e.target.closest('[data-cxmode]'), mb = e.target.closest('[data-cxmon]'), mk = e.target.closest('[data-cxmk]'), sl = e.target.closest('[data-cxsel]');
    if (md) { if (md.getAttribute('aria-disabled') === 'true' || CX.mode === md.dataset.cxmode) return; CX.mode = md.dataset.cxmode;
      $$('#cxSpendSec [data-cxmode]').forEach(b => b.setAttribute('aria-pressed', b.dataset.cxmode === CX.mode)); cxSpendText();
      if (CX.rec && CX.rec.chart) { CX.rec.refresh(true); CX.rec.chart.resize(); } return; }
    if (mb) { if (mb.getAttribute('aria-disabled') === 'true') return; cxSetMonth(CX.month + +mb.dataset.cxmon); return; }
    if (mk) { cxSetMonth(+mk.dataset.cxmk); return; }
    const sc = e.target.closest('#cxSs td[data-k]'); if (sc) { cxSetMonth(+sc.dataset.k); return; }
    if (sl) { const i = +sl.dataset.cxsel; setSel(sel === i ? null : i); }
  });
  const hl = (e, type) => { const b = e.target.closest('#cxLeg [data-cxsel]'); if (!b || !CX.rec || !CX.rec.chart || (e.relatedTarget && b.contains(e.relatedTarget))) return;
    const i = +b.dataset.cxsel, t = CX.mode === 'joint' ? 0 : CMP.ids.indexOf(i); if (t < 0) return;
    CX.rec.chart.dispatchAction({type, seriesId: `L${i}_${t}`}); };
  sec.addEventListener('mouseover', e => hl(e, 'highlight'));
  sec.addEventListener('mouseout', e => hl(e, 'downplay'));
  $('#cxMt').addEventListener('toggle', e => { CX.mtOpen = e.target.open; });
  const ss = $('#cxSs'); if (ss) ss.addEventListener('toggle', e => { CX.ssOpen = e.target.open; if (CX.ssOpen) cxSeasOpen(true); else $('#cxSsBody').innerHTML = ''; });
}

/* ==========================================================================
   В. Полная таблица: значение индекса и процентиль раздельно; 32 признака
   ========================================================================== */
const CX_FG = [
  ['Госзаказ', k => k.startsWith('proc_') || k.startsWith('okpd_') || k === 'supply_out_pc'],
  ['Безналичные траты', k => k === 'spend_total' || k.startsWith('sh_')],
  ['Расселение и доступность', k => ['urban_share', 'market_access', 'log_pop', 'log_density'].includes(k)],
  ['Демография', k => ['birth_rate', 'death_rate', 'migr_rate'].includes(k)],
  ['Бюджет, зарплата и занятость', k => k === 'grants_pc' || k === 'wage' || k.startsWith('emp_')]];
function cxTable(ids){
  const k = ids.length, cs = k + 1;
  const head = `<tr><th scope="col" class="cx-c0">Показатель</th>${ids.map(i => `<th scope="col" data-ci="${i}"><span class="cx-hn">${cxIcon(cxS(i))}<span>${esc(N[i].s)}</span></span></th>`).join('')}</tr>`;
  const grp = (t, sub) => `<tr class="grp"><th colspan="${cs}" scope="colgroup"><span class="cx-gs">${t}${sub ? `<small>${sub}</small>` : ''}</span></th></tr>`;
  const cell = (i, html) => `<td data-ci="${i}">${html}</td>`;
  const gen = `<tr><th scope="row"><span class="cx-rl">Тип МО</span></th>${ids.map(i => cell(i, cxType(i))).join('')}</tr>
    <tr><th scope="row"><span class="cx-rl">Население</span><span class="u">человек</span></th>${ids.map(i => cell(i, `<span class="cx-raw">${fmtN(N[i].pop)}</span>`)).join('')}</tr>
    <tr><th scope="row"><span class="cx-rl">Проблемы и возможности</span><span class="u">темы рекомендаций</span></th>${ids.map(i => cell(i, `<span class="cx-tags">${[...new Set(N[i].recs.map(r => r.topic))].filter(t => t !== 'Ориентир').sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b)).map(t => `<span class="tag">${mk(kind(t))}<span>${esc(t)}</span></span>`).join('')}</span>`)).join('')}</tr>`;
  const ix = CX_IX.map(key => { const d = D.metrics[key], vals = ids.map(i => N[i].m[key]), x = cxIxX(key, ids), disp = ids.map(i => cxIxF(key, N[i].m[key], x)), mks = cxMarks(vals, disp, d.sense);
    return `<tr data-k="${key}"><th scope="row"><span class="cx-rl">${esc(d.label)}</span><span class="u">значение: ${esc(cxIxUnit(key))}</span><span class="u">${esc(senseTxt(d))}</span></th>${ids.map((i, t) => cell(i,
      N[i].m[key] == null && N[i].mp[key] == null ? `<span class="cx-raw">${NA}</span><span class="cx-pc">процентиль: ${NA}</span>`
        : `<span class="cx-raw">${N[i].m[key] == null ? NA : disp[t]}</span><span class="cx-pc">${N[i].mp[key] == null ? 'процентиль: ' + NA : fmtPctile(N[i].mp[key])}</span>${cxMarkHtml(mks[t])}`)).join('')}</tr>`; }).join('');
  const used = new Set();
  const ft = CX_FG.concat([['Прочие показатели', () => true]]).map(([g, f]) => { const ks = CX_FT.filter(x => !used.has(x) && f(x)); ks.forEach(x => used.add(x)); if (!ks.length) return '';
    return grp(g, '') + ks.map(key => { const vals = ids.map(i => N[i].f[key]), x = cxDigits(vals, (v, x) => cxFtF(key, v, x)), disp = ids.map(i => cxFtF(key, N[i].f[key], x)), mks = cxMarks(vals, disp, 0);
      return `<tr data-f="${key}"><th scope="row"><span class="cx-rl">${esc(FL(key))}</span><span class="u">${esc(cxFtUnit(key))}</span></th>${ids.map((i, t) => cell(i, `<span class="cx-num">${vals[t] == null ? NA : disp[t]}</span>${cxMarkHtml(mks[t])}`)).join('')}</tr>`; }).join(''); }).join('');
  return `<section class="sec cx-sec" id="cxTabSec" aria-labelledby="cxTabH" tabindex="-1">
    <h3 class="sech" id="cxTabH">Полная таблица <span class="kicker">${CX_IX.length} индексов · ${CX_FT.length} исходных показателей</span></h3>
    <p class="secsub">Для индексов — две разные величины: значение индекса в его собственных единицах (доля показана в процентах, средний процентиль и безразмерные индексы — как есть) и процентиль — место района среди ${n} МО на шкале 0–100, а не процент. Отметки «выше/ниже среди выбранных» ставятся только при различии видимых значений; если обычное округление скрыло бы различие между выбранными районами, в строке показан дополнительный знак. У индексов с известным направлением добавлена оценка «благоприятнее/неблагоприятнее», у нейтральных индексов и исходных показателей оценки нет. «н/д» — значения нет в данных (это не ноль).</p>
    ${k < 2 ? '<p class="cx-one">Сейчас в сравнении один район — отметки появятся, когда районов станет два и больше.</p>' : ''}
    <div class="tbox cx-tbox" role="region" aria-labelledby="cxTabH" tabindex="0"><table class="cx-tab" style="--k:${k}"><thead>${head}</thead><tbody>
    ${grp('Общее', '')}${gen}
    ${grp('Индексы', `значение индекса и процентиль среди ${n} МО`)}${ix}
    ${grp('Исходные показатели', 'в своих единицах')}${ft}</tbody></table></div></section>`;
}

/* ==========================================================================
   Выделение выбранного МО (общий sel ↔ SEL_HOOKS) во всех блоках вкладки
   ========================================================================== */
function cxEmphIn(root){ root.querySelectorAll('[data-ci]').forEach(e => e.classList.toggle('on', +e.dataset.ci === sel)); }
function cxEmph(){
  const T = $('#t-cmp'); if (!T) return;
  cxEmphIn(T);
  $$('#cmpSlots .cx-card').forEach(c => { const on = +c.dataset.i === sel; c.classList.toggle('on', on); const b = c.querySelector('.cx-nm'); if (b) b.setAttribute('aria-pressed', on); });
  $$('#cxLeg [data-cxsel]').forEach(b => b.setAttribute('aria-pressed', +b.dataset.cxsel === sel));
  $$('#cxInsp [data-cxpick]').forEach(b => b.setAttribute('aria-pressed', +b.dataset.cxpick === sel));
  if (CX.rec && CX.rec.chart) CX.rec.refresh(false);
}
SEL_HOOKS.push(cxEmph);

/* ==========================================================================
   Сборка вкладки
   ========================================================================== */
function cxNav(){
  return `<nav class="cx-nav" aria-label="Разделы сравнения"><button type="button" class="chip" data-cxgo="cxProfSec">Профиль индексов</button><button type="button" class="chip" data-cxgo="cxSpendSec">Месячные траты</button><button type="button" class="chip" data-cxgo="cxTabSec">Полная таблица</button></nav>`;
}
function renderCmp(){
  cxTools(); cxSlots();
  const ids = CMP.ids, key = ids.map(i => i + ':' + cxS(i)).join(',');
  const B = $('#cmpBody');
  if (key === CX.key && B.childElementCount) { cxEmph(); return; }
  CX.key = key;
  if (CX.rec) { CX.rec.dispose(); CX.rec = null; } if (CX.ro) { CX.ro.disconnect(); CX.ro = null; }
  CX.el = null; hideTip();
  if (CX.pin && CX.pin.i != null && !cmpHas(CX.pin.i)) CX.pin = {k: CX.pin.k, i: null};   // индекс в панели сохраняется
  if (CX.hot != null && !cmpHas(CX.hot)) CX.hot = null;
  if (!ids.length) { B.innerHTML = cxEmpty(); CX.seen.clear(); CX.cur = {r: 0, l: 0};
    $('#cxBig').addEventListener('click', e => { const b = e.currentTarget; b.dataset.ids.split(',').forEach(i => addToComparison(+i, $('#cxTools')));
      const f = $('#cmpSlots .cx-nm'); if (f) f.focus(); });
    return; }
  if (CX.cur.l >= ids.length) CX.cur.l = ids.length - 1;
  B.innerHTML = cxNav() + cxProfile(ids) + cxSpend(ids) + cxTable(ids);
  CX.seen = new Set(ids);
  B.querySelector('.cx-nav').addEventListener('click', e => { const b = e.target.closest('[data-cxgo]'); if (!b) return; const s = $('#' + b.dataset.cxgo);
    s.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); s.focus({preventScroll: true}); });
  cxBindProfile(); cxPinMark(); cxInsp(); cxPlace(); cxBindSpend(); cxSpendInit(); cxEmph();
}
CMP_HOOKS.push(renderCmp);
onTab('cmp', renderCmp);
