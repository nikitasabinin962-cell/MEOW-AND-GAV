/* ==========================================================================
   5. Типы МО: дерево принадлежности (D3 hierarchy/tree + join) →
   медианные индексы на общей шкале → профили семи типов.
   Порядок и идентификаторы типов — из D.types; дерево показывает
   принадлежность к экономическому типу, а не причинность и не
   административное подчинение. D только читается: составы копируются.
   ========================================================================== */
$('#t-types').innerHTML = String.raw`  <div class="phead">
    <div><h2>Типы муниципалитетов</h2>
      <p class="lede" id="typesLede"></p></div>
    <div class="ttools">
      <nav class="tjump" id="typeView" aria-label="Разделы вкладки">
        <button type="button" class="link" data-tv="tree">Дерево</button>
        <button type="button" class="link" data-tv="over">Медианы</button>
        <button type="button" class="link" data-tv="prof">Профили</button>
      </nav>
      <label class="field" for="typeSearch"><span class="sr">Найти МО в дереве типов</span><input type="search" id="typeSearch" list="molist" placeholder="Найти МО в типах" autocomplete="off"></label>
    </div>
  </div>
  <div class="sec tsec" id="typesTreeSec">
    <h3 class="sech">Состав типов <span class="tkick" id="treeKicker"></span></h3>
    <p class="secsub" id="treeSub"></p>
    <div class="ttbar">
      <button class="btn sm" type="button" id="treeAll">Развернуть все</button>
      <button class="btn sm" type="button" id="treeNone">Свернуть</button>
      <label class="check"><input type="checkbox" id="treeFocus" checked> Одна ветвь в фокусе</label>
      <span class="hint ttkeys" id="treeHelp">Клавиатура: Tab — в дерево, ↑ ↓ — узлы, → раскрыть, ← свернуть или к родителю, Home / End, Enter — выбрать.</span>
    </div>
    <div class="ttree">
      <div class="tbox-tree" id="tree"></div>
      <aside class="panel treeinfo" id="treeInfo" aria-label="Карточка выбранного узла дерева"></aside>
    </div>
  </div>
  <div class="sec" id="typesOverSec">
    <h3 class="sech">Медианные индексы типов на общей шкале</h3>
    <p class="secsub">Точка — медиана процентилей индекса по МО типа. Процентиль — место среди 63 МО на шкале 0–100, а не процент. Совпадающие значения разведены по вертикали, положение по шкале не меняется. Выберите тип, чтобы выделить его точки и увидеть числа.</p>
    <div id="typeOver"></div>
  </div>
  <div class="sec" id="typeCards"></div>`;

/* ---------- данные вкладки (копии, D не изменяется) ---------- */
const tyByName = (a, b) => N[a].s.localeCompare(N[b].s, 'ru');
const TY = D.types.map(t => ({c: t.c, name: t.name, members: t.members.slice().sort(tyByName), sig: t.sig.slice(), med: Object.assign({}, t.med)}));
const tyRec = c => TY.find(t => t.c === c);
const SIGMAX = Math.max(...D.types.flatMap(t => t.sig.map(s => Math.abs(s.effect))), 1);
const SIGDOM = Math.max(1, Math.ceil(SIGMAX));
const MEDKEYS = Object.keys(D.metrics).filter(k => D.types.some(t => t.med && t.med[k] != null));
function tyPop(ids){ let s = 0, miss = 0; ids.forEach(i => { if (N[i].pop == null) miss++; else s += N[i].pop; }); return {s, miss}; }
const tyPopTxt = ids => { const p = tyPop(ids); return fmtN(p.s) + ' чел.' + (p.miss ? ` (н/д у ${p.miss} МО)` : ''); };
const tyPopHtml = ids => { const p = tyPop(ids); return `<span class="mono">${fmtN(p.s)}</span> чел.` + (p.miss ? ` (н/д у <span class="mono">${p.miss}</span> МО)` : ''); };
const tySense = s => s > 0 ? '↑ лучше' : s < 0 ? '↓ лучше' : 'без оценки';
const tySenseLong = s => s > 0 ? 'выше — благоприятнее' : s < 0 ? 'выше — неблагоприятнее' : 'нейтральный индекс, без оценки';
const tyRegionShort = String(D.region || 'Регион').replace(/^Республика\s+/, '');

$('#typesLede').textContent = `${D.k} экономических типов найдены без учителя по ${Object.keys(D.feats).length} признакам и связям между МО. Дерево показывает состав типов; ниже — медианные индексы на общей шкале и профили: чем каждый тип отличается от остальных МО. Цвет типа одинаков на всех вкладках.`;
$('#treeSub').textContent = `${tyRegionShort} → ${TY.length} экономических типов → ${n} МО; каждый МО входит ровно в один тип. Это принадлежность к экономическому типу, а не административное подчинение и не причинные связи.`;

/* Сверка состава для раздела «Как это работает»: пустой массив — расхождений нет */
function typesMembershipCheck(){
  const out = [], seen = new Map();
  if (D.types.length !== D.k) out.push(`В D.types ${D.types.length} типов, а D.k = ${D.k}`);
  D.types.forEach(t => {
    if (!Array.isArray(t.members)) { out.push(`Тип «${t.name}»: нет списка members`); return; }
    t.members.forEach(i => {
      if (!N[i]) { out.push(`Тип «${t.name}»: несуществующий индекс МО ${i}`); return; }
      if (!seen.has(i)) seen.set(i, []);
      seen.get(i).push(t.c);
      if (N[i].c !== t.c) out.push(`${N[i].s}: в составе «${t.name}», но nodes[i].c = ${N[i].c} («${typeName(N[i].c)}»)`);
    });
  });
  N.forEach((x, i) => { const s = seen.get(i);
    if (!s) out.push(`${x.s}: нет ни в одном составе types[].members`);
    else if (s.length > 1) out.push(`${x.s}: в ${s.length} составах`); });
  return out;
}

/* ==========================================================================
   Обзор: медианы 13 индексов по типам на общей шкале процентилей
   ========================================================================== */
let tyHL = null;
function tyOverview(){
  const ticks = [0, 25, 50, 75, 100];
  const axis = cls => `<div class="tov-ax ${cls}" aria-hidden="true"><span></span><div class="tk">${ticks.map(v => `<span style="left:${v}%">${v}</span>`).join('')}</div></div>`;
  $('#typeOver').innerHTML = `<div class="tov-lg" role="group" aria-label="Выделить тип на шкале">${TY.map(t =>
      `<button type="button" class="chip" data-hl="${t.c}" aria-pressed="false"><span class="sw" style="--c:${COLV(t.c)}"></span>${esc(t.name)}</button>`).join('')}
      <button type="button" class="link tov-prof" id="tovProf" hidden>Профиль выделенного типа ↓</button></div>
    <div class="tov" id="tovGrid">${axis('top')}${MEDKEYS.map(k => { const d = D.metrics[k];
      return `<div class="tov-row" data-k="${k}"><div class="lab"><span class="nm">${esc(d.label)}</span><small title="${esc(tySenseLong(d.sense))}">${esc(tySense(d.sense))}</small><b class="v"></b></div>
        <div class="trk">${ticks.map(v => `<i class="g${v === 50 ? ' mid' : ''}" style="left:${v}%"></i>`).join('')}${TY.map(t => { const p = t.med[k]; if (p == null) return '';
          return `<span class="tdot" data-c="${t.c}" data-k="${k}" data-p="${p}" style="left:${p}%;--c:${COLV(t.c)}" aria-hidden="true"></span>`; }).join('')}</div></div>`; }).join('')}${axis('bot')}</div>
    <p class="note tov-note">Вертикальная линия 50 — медиана региона. «↑ лучше» — более высокий процентиль благоприятнее, «↓ лучше» — наоборот, «без оценки» — нейтральный индекс. Точные значения — в профилях ниже и в таблице.</p>
    <details class="tov-tab"><summary>${ICON.chev}<span>Таблица медиан: ${MEDKEYS.length} индексов × ${TY.length} типов</span></summary>
      <div class="tbox" hidden><table><caption class="sr">Медианы процентилей индексов по экономическим типам</caption>
        <thead><tr><th scope="col">Индекс</th><th scope="col">Направление</th>${TY.map(t => `<th scope="col" class="n"><span class="sw" style="--c:${COLV(t.c)}"></span> ${esc(t.name)}</th>`).join('')}</tr></thead>
        <tbody>${MEDKEYS.map(k => { const d = D.metrics[k]; return `<tr><th scope="row">${esc(d.label)}</th><td>${esc(tySenseLong(d.sense))}</td>${TY.map(t => `<td class="n">${t.med[k] == null ? NA : fmtN(t.med[k], 1)}</td>`).join('')}</tr>`; }).join('')}</tbody></table></div></details>`;
  const grid = $('#tovGrid');
  grid.addEventListener('mousemove', e => { const el = e.target.closest('.tdot'); if (!el) { hideTip(); return; }
    const t = tyRec(+el.dataset.c), d = D.metrics[el.dataset.k];
    showTip(e, `<b>${esc(t.name)}</b><br>${esc(d.label)}: <span class="tnum">${fmtN(+el.dataset.p, 1)}</span><br><span class="tsub">медиана процентилей МО типа (0–100, не процент) · ${esc(tySenseLong(d.sense))}</span>`); });
  grid.addEventListener('mouseleave', hideTip);
  grid.addEventListener('click', e => { const el = e.target.closest('.tdot'); if (el) tySetHL(tyHL === +el.dataset.c ? null : +el.dataset.c); });
  $$('#typeOver [data-hl]').forEach(b => b.addEventListener('click', () => tySetHL(tyHL === +b.dataset.hl ? null : +b.dataset.hl)));
  $('#tovProf').addEventListener('click', () => { if (tyHL != null) tyGoProfile(tyHL); });
  /* содержимое закрытого details скрыто полностью (не только визуально) */
  const det = $('#typeOver .tov-tab'); det.addEventListener('toggle', () => { det.querySelector('.tbox').hidden = !det.open; });
  whenSized(grid, () => { tyRelane(); onResize(grid, tyRelane); });
}
/* совпадающие медианы: разведение поперёк шкалы (x остаётся точным) */
function tyRelane(){
  document.querySelectorAll('#tovGrid .trk').forEach(trk => {
    const w = trk.clientWidth; if (!w) return;
    const ds = Array.from(trk.querySelectorAll('.tdot')).sort((a, b) => a.dataset.p - b.dataset.p), lanes = {};
    let maxL = 0;
    ds.forEach(el => { const p = +el.dataset.p;
      for (const L of [0, -1, 1, -2, 2, -3, 3]) { const arr = lanes[L] = lanes[L] || [];
        if (arr.every(q => Math.abs(q - p) * w / 100 >= 13)) { arr.push(p); el.style.setProperty('--ln', L); maxL = Math.max(maxL, Math.abs(L)); break; } } });
    trk.style.setProperty('--lanes', maxL);
  });
}
function tySetHL(c){
  tyHL = c;
  $('#tovGrid').classList.toggle('hl', c != null);
  $$('#tovGrid .tdot').forEach(el => el.classList.toggle('on', +el.dataset.c === c));
  $$('#typeOver [data-hl]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.hl === c)));
  $$('#tovGrid .tov-row').forEach(r => { const v = r.querySelector('.v'), t = c == null ? null : tyRec(c);
    v.textContent = t ? (t.med[r.dataset.k] == null ? 'н/д' : fmtN(t.med[r.dataset.k], 1)) : ''; });
  $('#tovProf').hidden = c == null;
  if (c != null) announce(`Выделен тип «${tyRec(c).name}»: значения показаны рядом с названиями индексов.`);
}
function tyGoProfile(c){
  const el = $('#tp-' + c); if (!el) return;
  el.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'});
  $$('.tprof').forEach(x => x.classList.toggle('hl', x === el));
  const h = el.querySelector('h3'); if (h) { h.tabIndex = -1; h.focus({preventScroll: true}); }
}

/* ==========================================================================
   Профили семи типов
   ========================================================================== */
function tyCards(){
  const S = SIGDOM, ticks = d3.range(-S, S + 1), pos = v => (v + S) / (2 * S) * 100;
  const sgn = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v);
  $('#typeCards').innerHTML = `<h3 class="sech" id="typesProfSec">Профили ${TY.length} типов</h3>
    <p class="secsub">«Чем отличается» — разница медианы признака в типе и у остальных МО, в единицах межквартильного размаха (IQR), со знаком. Шкала общая для всех профилей (от −${S} до +${S} IQR), поэтому длины полос сравнимы между типами. Знак — направление, а не оценка; это не проценты.</p>` +
  TY.map(t => {
    const sig = t.sig.slice().sort((a, b) => b.effect - a.effect);
    return `<article class="tprof" id="tp-${t.c}" style="--c:${COLV(t.c)}" aria-labelledby="tph-${t.c}">
      <div class="id"><h3 id="tph-${t.c}"><span class="sw"></span><span>${esc(t.name)}</span></h3>
        <div class="cnt"><span class="mono">${t.members.length}</span> МО · ${tyPopHtml(t.members)}</div>
        <div class="acts"><button class="btn sm" type="button" data-tgrp="${t.c}">${ICON.map} Показать на карте</button><button class="btn sm" type="button" data-ttree="${t.c}">В дереве</button></div></div>
      <div class="sigb"><h4>Чем отличается от остальных МО</h4>
        <div class="sigbars">
          <span class="sh" aria-hidden="true"></span><span class="sdir" aria-hidden="true"><span>← ниже</span><span>выше →</span></span><span class="sh r" aria-hidden="true">IQR</span>
          ${sig.map(s => { const e = s.effect, a = pos(Math.min(0, e)), w = Math.abs(e) / (2 * S) * 100;
            return `<span class="sl">${esc(featLabel(s.feature))}</span><span class="tr" aria-hidden="true">${ticks.map(v => `<i class="gl${v === 0 ? ' z' : ''}" style="left:${pos(v)}%"></i>`).join('')}<i class="bar${e < 0 ? ' neg' : ''}" style="left:${a}%;width:${w}%"></i></span><span class="num mono">${fmtSigned(e, 2)}</span>`; }).join('')}
          <span aria-hidden="true"></span><span class="sax" aria-hidden="true">${ticks.map(v => `<span style="left:${pos(v)}%">${sgn(v)}</span>`).join('')}</span><span aria-hidden="true"></span>
        </div></div>
      <div class="medb"><h4>Медианные индексы: процентиль среди ${n} МО</h4>
        <div class="medtab">
          <span class="mh">Индекс</span><span class="mh" title="направление шкалы">↑↓</span><span class="mh">0 · 50 · 100</span><span class="mh r">медиана</span>
          ${MEDKEYS.map(k => { const d = D.metrics[k], p = t.med[k];
            return `<span>${esc(d.label)}</span><span class="sg" title="${esc(tySenseLong(d.sense))}">${d.sense > 0 ? '↑' : d.sense < 0 ? '↓' : '·'}<span class="sr"> ${esc(tySenseLong(d.sense))}</span></span>${ptrack(p, senseCls(d, p))}<span class="num mono">${p == null ? NA : fmtN(p, 1)}</span>`; }).join('')}
        </div>
        <p class="note">↑ — выше благоприятнее, ↓ — выше неблагоприятнее, · — без оценки. Цвет точки: зелёный — благоприятная сторона медианы региона, красный — неблагоприятная.</p></div>
      <div class="mem"><h4>Состав: все ${t.members.length} МО <span class="hint">— нажмите, чтобы открыть карточку МО в дереве</span></h4>
        <div class="chips">${t.members.map(i => `<button class="chip" type="button" data-mi="${i}">${esc(N[i].s)}</button>`).join('')}</div></div>
    </article>`; }).join('');
  const box = $('#typeCards');
  box.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.tgrp != null) { const t = tyRec(+b.dataset.tgrp); showGroup(t.members.slice(), 'тип «' + t.name + '»'); }
    else if (b.dataset.ttree != null) tyRevealType(+b.dataset.ttree, {focus: true, scrollPage: true});
    else if (b.dataset.mi != null) tyRevealMO(+b.dataset.mi, {focus: true, scrollPage: true, anim: true});
  });
}

/* ==========================================================================
   Дерево: Башкортостан → 7 типов → 63 МО
   Раскладка по измеренному тексту (после загрузки шрифта), стабильные ключи
   r / tC / mI / sC, переходы enter/update/exit, WAI-ARIA Tree View.
   ========================================================================== */
const TREE_MS = 480;
const TYT = {open: new Set(), focusMode: true, card: 'r', fkey: 'r', box: null, svg: null, gL: null, gN: null, L: null, ready: false, lastSel: null, M: null};
const TFONT = {root: '600 14px "Golos Text"', sub: '400 12px "Golos Text"', type: '600 13.5px "Golos Text"', leaf: '400 13px "Golos Text"', leafB: '600 13px "Golos Text"', cnt: '500 12px "JetBrains Mono"', cntU: '400 12px "Golos Text"'};
const TCARD = {padL: 30, gapCnt: 14, chevW: 30, lh: 18, padV: 11, minH: 40};
const TLEAF = {pitch: 26, h: 22, lx: 10};
const r1 = v => Math.round(v * 10) / 10;
let tyCtx = null;
function tyTextW(s, font){ if (!tyCtx) tyCtx = document.createElement('canvas').getContext('2d'); tyCtx.font = font; return tyCtx.measureText(s).width; }
function tyWrap(text, width, font){
  const words = String(text).split(/\s+/).filter(Boolean), lines = []; let cur = '';
  words.forEach(w => { const t = cur ? cur + ' ' + w : w; if (!cur || tyTextW(t, font) <= width) cur = t; else { lines.push(cur); cur = w; } });
  if (cur) lines.push(cur); return lines;
}
function tyMinWidth(names, maxLines, font){
  let lo = Math.ceil(Math.max(...names.flatMap(s => s.split(/\s+/)).map(w => tyTextW(w, font)))), hi = Math.ceil(Math.max(...names.map(s => tyTextW(s, font))));
  while (lo < hi) { const mid = (lo + hi) >> 1; if (names.every(s => tyWrap(s, mid, font).length <= maxLines)) hi = mid; else lo = mid + 1; }
  return lo;
}
/* размеры, не зависящие от ширины контейнера (измеряются один раз после шрифтов) */
function tyMetrics(){
  if (TYT.M) return TYT.M;
  const names = TY.map(t => t.name), M = {rootT: tyRegionShort, rootSub: `${n} МО · ${TY.length} типов`};
  M.rootW = Math.ceil(Math.max(tyTextW(M.rootT, TFONT.root), tyTextW(M.rootSub, TFONT.sub))) + 30;
  M.cntW = Math.ceil(Math.max(...TY.map(t => tyTextW(String(t.members.length), TFONT.cnt) + tyTextW('\u00a0МО', TFONT.cntU))));
  M.leafW = Math.ceil(Math.max(...N.map(x => tyTextW(x.s, TFONT.leafB))));
  M.w2 = tyMinWidth(names, 2, TFONT.type) + 6;
  M.w3 = tyMinWidth(names, 3, TFONT.type) + 6;
  M.chrome = TCARD.padL + TCARD.gapCnt + M.cntW + TCARD.chevW;
  return TYT.M = M;
}
const tyLeafW = i => 11 + TLEAF.lx + Math.ceil(tyTextW(N[i].s, TFONT.leafB)) + 8;
const tyTypeH = lines => Math.max(TCARD.minH, lines.length * TCARD.lh + 2 * TCARD.padV);
function tyLayout(W, BH){
  const M = tyMetrics(), pad = 14, g1 = 28, g2 = 40, leafCol = 11 + TLEAF.lx + M.leafW + 8 + 16;
  const avail = W - 2 * pad - M.rootW - M.chrome - leafCol - g1 - g2;
  return avail >= M.w3 ? tyLayoutTidy(BH, M, {pad, g1, g2, avail}) : tyLayoutIndent(W, M);
}
/* горизонтальное tidy-дерево (d3.tree): колонки корня, типов (2–3 строки) и МО */
function tyLayoutTidy(BH, M, o){
  const tw = Math.min(o.avail, M.w2);
  let extra = o.avail - tw; const a1 = Math.min(extra * .4, 56); extra -= a1; const a2 = Math.min(extra * .6, 90); extra -= a2;
  const cardW = M.chrome + tw, X0 = o.pad + extra / 2, X1 = X0 + M.rootW + o.g1 + a1, X2 = X1 + cardW + o.g2 + a2 + 6;
  const lines = new Map(TY.map(t => [t.c, tyWrap(t.name, tw - 2, TFONT.type)]));
  const root = d3.hierarchy({key: 'r', kind: 'root', children: TY.map(t => ({key: 't' + t.c, kind: 'type', c: t.c,
    children: TYT.open.has(t.c) ? t.members.map(i => ({key: 'm' + i, kind: 'leaf', c: t.c, i})) : [{key: 's' + t.c, kind: 'strip', c: t.c}]}))});
  root.each(d => { const k = d.data.kind; d.hh = k === 'root' ? 46 : k === 'type' ? tyTypeH(lines.get(d.data.c)) : k === 'leaf' ? TLEAF.h : 14; });
  d3.tree().nodeSize([1, 1]).separation((a, b) => a.hh / 2 + b.hh / 2 + (a.depth === 1 ? 12 : a.parent === b.parent ? TLEAF.pitch - TLEAF.h : 16))(root);
  let top = Infinity, bot = -Infinity;
  root.each(d => { top = Math.min(top, d.x - d.hh / 2); bot = Math.max(bot, d.x + d.hh / 2); });
  const padY = 18, H = Math.ceil(Math.max(bot - top + 2 * padY, BH)), off = (H - (bot - top)) / 2 - top;
  /* высокое дерево (раскрыты ветви): корень остаётся в первом экране рядом с первыми типами,
     а не посередине холста высотой ~1700 px — начало дерева видно без поиска прокруткой */
  const rootY = H > BH ? Math.min(root.x + off, Math.max(BH / 2, padY + 23)) : root.x + off;
  const L = {mode: 'tidy', nodes: new Map(), list: [], order: [], H, tw, cardW};
  root.eachBefore(d => { const k = d.data.kind, sib = d.parent ? d.parent.children : [d];
    const o = {key: d.data.key, kind: k, depth: d.depth, c: d.data.c, i: d.data.i, pk: d.parent ? d.parent.data.key : null, y: d.depth ? d.x + off : rootY, h: d.hh,
      x: [X0, X1, X2][d.depth], pos: sib.indexOf(d) + 1, size: sib.length};
    if (k === 'root') o.w = M.rootW;
    else if (k === 'type') { o.w = cardW; o.tw = tw; o.lines = lines.get(o.c); }
    else if (k === 'leaf') o.w = tyLeafW(o.i);
    else o.w = tyRec(o.c).members.length * 9;
    L.nodes.set(o.key, o); L.list.push(o); if (k !== 'strip') L.order.push(o.key); });
  return L;
}
/* узкий экран: дерево с отступами в одну колонку, названия на всю ширину */
function tyLayoutIndent(W, M){
  const pad = 10, X1 = pad + 26, cardW = Math.max(160, W - X1 - pad), tw = cardW - M.chrome;
  const L = {mode: 'indent', nodes: new Map(), list: [], order: [], H: 0, tw, cardW}; let y = pad;
  const add = o => { L.nodes.set(o.key, o); L.list.push(o); L.order.push(o.key); };
  add({key: 'r', kind: 'root', depth: 0, x: pad, y: y + 23, h: 46, w: M.rootW, pos: 1, size: 1}); y += 46 + 10;
  TY.forEach((t, k) => { const lines = tyWrap(t.name, tw - 2, TFONT.type), h = tyTypeH(lines);
    add({key: 't' + t.c, kind: 'type', depth: 1, c: t.c, pk: 'r', x: X1, y: y + h / 2, h, w: cardW, tw, lines, pos: k + 1, size: TY.length}); y += h + 6;
    if (TYT.open.has(t.c)) { t.members.forEach((i, j) => { add({key: 'm' + i, kind: 'leaf', depth: 2, c: t.c, i, pk: 't' + t.c, x: X1 + 34, y: y + 14, h: TLEAF.h, w: tyLeafW(i), pos: j + 1, size: t.members.length}); y += 28; }); y += 6; }
  });
  L.H = Math.ceil(y + pad);
  return L;
}
function tyPortOut(o, mode){ return mode === 'tidy' ? [o.x + o.w, o.y] : [o.x + 16, o.y + o.h / 2]; }
function tyPortIn(o){ return o.kind === 'leaf' || o.kind === 'strip' ? [o.x - 5, o.y] : [o.x, o.y]; }
function tyCurve(a, b, mode){
  if (mode === 'tidy') { const m = r1((a[0] + b[0]) / 2); return `M${r1(a[0])},${r1(a[1])}C${m},${r1(a[1])} ${m},${r1(b[1])} ${r1(b[0])},${r1(b[1])}`; }
  return `M${r1(a[0])},${r1(a[1])}C${r1(a[0])},${r1(b[1])} ${r1(a[0])},${r1(b[1])} ${r1(b[0])},${r1(b[1])}`;
}
const tyNodeEl = key => TYT.gN ? TYT.gN.node().querySelector(`g.tn[data-key="${key}"]`) : null;
/* текущее видимое положение узла (в том числе посреди перехода) */
function tyPosOf(el){ const m = el && /translate\(\s*([-\d.e]+)[\s,]+([-\d.e]+)\s*\)/.exec(el.getAttribute('transform') || ''); return m ? [+m[1], +m[2]] : null; }
const tyCurPos = key => tyPosOf(tyNodeEl(key));

/* построение и обновление содержимого узла */
function tyBuild(d){
  const g = d3.select(this);
  if (d.kind === 'strip') { g.attr('aria-hidden', 'true').style('--c', COLV(d.c));
    tyRec(d.c).members.forEach((_, k) => g.append('circle').attr('class', 'sd').attr('cx', k * 9).attr('r', 3)); return; }
  g.attr('role', 'treeitem');
  if (d.kind === 'root') { g.append('rect').attr('class', 'bg').attr('rx', 8); g.append('text').attr('class', 'nm').attr('x', 15).attr('y', -8).text(TYT.M.rootT); g.append('text').attr('class', 'sub').attr('x', 15).attr('y', 10).text(TYT.M.rootSub); return; }
  g.style('--c', COLV(d.c));
  if (d.kind === 'type') { g.append('rect').attr('class', 'bg').attr('rx', 8); g.append('circle').attr('class', 'dot').attr('cx', 16).attr('r', 5);
    g.append('text').attr('class', 'nm'); const ct = g.append('text').attr('class', 'cnt').attr('text-anchor', 'end'); ct.append('tspan').attr('class', 'cn').text(tyRec(d.c).members.length); ct.append('tspan').text('\u00a0МО');
    g.append('g').attr('class', 'chevw').append('path').attr('class', 'chev').attr('d', 'M-2.5,-4.5L2,0L-2.5,4.5'); return; }
  g.append('rect').attr('class', 'bg').attr('x', -11).attr('y', -TLEAF.h / 2).attr('height', TLEAF.h).attr('rx', 6);
  g.append('circle').attr('class', 'ring').attr('r', 7); g.append('circle').attr('class', 'dot').attr('r', 3.6);
  g.append('text').attr('class', 'nm').attr('x', TLEAF.lx).text(N[d.i].s);
}
function tyUpdate(d){
  const g = d3.select(this);
  if (d.kind === 'strip') return;
  g.attr('role', 'treeitem').attr('aria-level', d.depth + 1).attr('aria-setsize', d.size).attr('aria-posinset', d.pos);
  if (d.kind === 'root') { g.attr('aria-label', `${D.region}: ${n} МО, ${TY.length} экономических типов`); g.select('.bg').attr('x', 0).attr('y', -d.h / 2).attr('width', d.w).attr('height', d.h); return; }
  if (d.kind === 'type') { const t = tyRec(d.c); g.attr('data-type', d.c).attr('aria-label', `${t.name}, ${t.members.length} МО`);
    g.select('.bg').attr('x', 0).attr('y', -d.h / 2).attr('width', d.w).attr('height', d.h);
    const key = d.lines.join('\n'), tx = g.select('.nm');
    if (tx.attr('data-l') !== key) { tx.attr('data-l', key).selectAll('tspan').remove();
      d.lines.forEach((s, k) => tx.append('tspan').attr('x', TCARD.padL).attr('y', r1((k - (d.lines.length - 1) / 2) * TCARD.lh)).text(s)); }
    g.select('.cnt').attr('x', TCARD.padL + d.tw + TCARD.gapCnt + TYT.M.cntW).attr('y', 0);
    g.select('.chevw').attr('transform', `translate(${r1(d.w - 15)},0)`); return; }
  g.attr('data-mo', d.i).attr('aria-label', N[d.i].s);
  g.select('.bg').attr('width', d.w);
}

/* состояния без перерасчёта раскладки: фокус, выбор, раскрытие, путь */
function tyStates(){
  const L = TYT.L; if (!L) return;
  const selKey = sel != null ? 'm' + sel : null, card = TYT.card;
  const path = new Set(); if (card[0] === 'm') { path.add(card); path.add('t' + N[+card.slice(1)].c); } else if (card[0] === 't') path.add(card);
  const focusType = TYT.focusMode && TYT.open.size === 1 ? [...TYT.open][0] : null;
  TYT.gN.selectChildren('g.tn').filter(d => L.nodes.has(d.key))
    .attr('tabindex', d => d.kind === 'strip' ? null : d.key === TYT.fkey ? 0 : -1)
    .attr('aria-selected', d => d.kind === 'strip' ? null : String(d.key === card))
    .attr('aria-expanded', d => d.kind === 'root' ? 'true' : d.kind === 'type' ? String(TYT.open.has(d.c)) : null)
    .classed('cur', d => d.key === card).classed('hit', d => d.key === selKey)
    .classed('open', d => d.kind === 'type' && TYT.open.has(d.c))
    .classed('dim', d => focusType != null && d.kind !== 'root' && d.c !== focusType);
  TYT.gL.selectChildren('path.lk').filter(d => L.nodes.has(d.key))
    .classed('on', d => path.has(d.key) && L.nodes.has(d.key)).classed('dim', d => focusType != null && d.c !== focusType);
  $$('#treeInfo [data-act="toggle"]').forEach(b => { const on = TYT.open.has(+b.dataset.c); b.textContent = on ? 'Свернуть ветвь' : 'Раскрыть ветвь'; b.setAttribute('aria-expanded', String(on)); });
  $$('#typeCards [data-mi]').forEach(b => b.classList.toggle('on', +b.dataset.mi === sel));
  const vis = L.order.filter(k => k[0] === 'm').length;
  $('#treeKicker').innerHTML = `<span class="mono">${TY.length}</span> типов · <span class="mono">${n}</span> МО · показано МО: <span class="mono">${vis}</span> из <span class="mono">${n}</span>`;
}

function tyRender(opt = {}){
  if (!TYT.ready) return;
  const anim = !!opt.anim && !RM.matches, T = anim ? TREE_MS : 0, ease = d3.easeCubicInOut;
  const prevL = TYT.L, W = TYT.box.clientWidth, BH = TYT.box.clientHeight;
  const L = TYT.L = tyLayout(W, BH);
  if (!L.nodes.has(TYT.fkey)) { const o = prevL && prevL.nodes.get(TYT.fkey); TYT.fkey = o && o.pk && L.nodes.has(o.pk) ? o.pk : 'r'; }
  const svg = TYT.svg, curH = +svg.attr('height') || 0;
  svg.interrupt('treeH').attr('width', W);
  if (!anim || L.H >= curH) svg.attr('height', L.H); else svg.transition('treeH').delay(T).duration(0).attr('height', L.H);
  /* точка входа: текущий порт родителя (там, где он виден сейчас) */
  const entry = d => { const po = (prevL && prevL.nodes.get(d.pk)) || L.nodes.get(d.pk), cp = tyCurPos(d.pk) || [po.x, po.y];
    return tyPortOut(Object.assign({}, po, {x: cp[0], y: cp[1]}), prevL ? prevL.mode : L.mode); };
  const exitTo = d => tyPortOut(L.nodes.get(d.pk), L.mode);
  const tr = o => `translate(${r1(o.x)},${r1(o.y)})`, trp = p => `translate(${r1(p[0] + 5)},${r1(p[1])})`;

  /* связи */
  const links = L.list.filter(o => o.pk).map(o => ({key: o.key, pk: o.pk, c: o.c, kind: o.kind, d: tyCurve(tyPortOut(L.nodes.get(o.pk), L.mode), tyPortIn(o), L.mode)}));
  const ls = TYT.gL.selectChildren('path.lk').data(links, d => d.key);
  const le = ls.enter().append('path').attr('class', d => 'lk ' + (d.kind === 'type' ? 'l1' : 'l2')).attr('data-key', d => d.key)
    .style('stroke', d => d.kind === 'type' ? null : COLV(d.c));
  const lu = le.merge(ls).classed('gone', false);
  const lx = ls.exit().classed('gone', true);
  if (anim) {
    le.attr('d', d => { const p = entry(d); return tyCurve(p, p, L.mode); }).style('opacity', 0);
    lu.transition('tree').duration(T).ease(ease).attr('d', d => d.d).style('opacity', 1);
    lx.transition('tree').duration(T).ease(ease).attr('d', d => { const p = exitTo(d); return tyCurve(p, p, L.mode); }).style('opacity', 0).remove();
  } else { lu.interrupt('tree').attr('d', d => d.d).style('opacity', null); lx.interrupt('tree').remove(); }

  /* узлы; фокус запоминается до соединения: у уходящего узла снимается tabindex, и браузер сразу уводит фокус на body */
  const aeG = document.activeElement && document.activeElement.closest ? document.activeElement.closest('#tree g.tn') : null;
  const aeKey = aeG && !aeG.classList.contains('gone') ? aeG.dataset.key : null;
  const ns = TYT.gN.selectChildren('g.tn').data(L.list, d => d.key);
  /* Подпись существующего узла остаётся видимой при движении, только если она уже была полностью видна и узел не уходил.
     Узел, пойманный посреди входа/ухода (быстрые повторные действия), прячет подпись и показывает её у цели — как новый,
     иначе подписи листьев, собранных у порта родителя, наслаиваются друг на друга. */
  const hideLab = new Set();
  if (anim) ns.each(function(d){
    const nm = this.querySelector('.nm'); if (!nm) return;
    const op = +getComputedStyle(nm).opacity, p = tyPosOf(this);
    if (!this.classList.contains('gone') && op > .99) return;
    if (!p || Math.hypot(p[0] - d.x, p[1] - d.y) > 3) hideLab.add(d.key); });
  const ne = ns.enter().append('g').attr('class', d => 'tn ' + d.kind).attr('data-key', d => d.key).each(tyBuild);
  const nu = ne.merge(ns).classed('gone', false).attr('aria-hidden', d => d.kind === 'strip' ? 'true' : null).each(tyUpdate);
  const nx = ns.exit().classed('gone', true).attr('aria-hidden', 'true').attr('role', null).attr('tabindex', null).attr('aria-selected', null);
  const FADE = '.nm, .sub, .cnt, .bg, .dot, .ring, .sd, .chev';
  if (anim) {
    ne.attr('transform', d => d.pk ? trp(entry(d)) : tr(d));
    nu.transition('tree').duration(T).ease(ease).attr('transform', tr);
    /* подписи появляются, когда узел почти на месте; исчезают до того, как уйдут с места */
    ne.selectAll('.dot, .ring, .sd').style('opacity', 0).transition('fade').delay(T * .15).duration(T * .6).style('opacity', 1);
    ne.selectAll('.nm, .bg').style('opacity', 0).transition('fade').delay(T * .7).duration(T * .3).style('opacity', 1);
    ns.filter(d => !hideLab.has(d.key)).selectAll(FADE).transition('fade').duration(T * .3).style('opacity', 1);
    const nh = ns.filter(d => hideLab.has(d.key));
    nh.selectAll('.dot, .ring, .sd').transition('fade').duration(T * .3).style('opacity', 1);
    nh.selectAll('.nm, .bg').transition('fade').duration(T * .12).style('opacity', 0).transition().delay(T * .58).duration(T * .3).style('opacity', 1);
    nx.transition('tree').duration(T).ease(ease).attr('transform', d => trp(exitTo(d))).remove();
    nx.selectAll('.nm, .bg').transition('fade').duration(T * .3).style('opacity', 0);
    nx.selectAll('.dot, .ring, .sd').transition('fade').delay(T * .3).duration(T * .6).style('opacity', 0);
  } else {
    nu.interrupt('tree').attr('transform', tr);
    nu.selectAll(FADE).interrupt('fade').style('opacity', null);
    nx.interrupt('tree').remove();
  }
  tyStates();
  /* фокус не теряется, если его узел ушёл со свёрнутой ветвью: переходит к родителю */
  if (aeKey && !L.nodes.has(aeKey)) tyFocus(TYT.fkey, {noScroll: true});
  if (opt.reveal) { const s = tyScrollToKey(opt.reveal, anim); if (s && opt.page) tyPageReveal(s.a, s.b, s.st, anim); }
}

/* прокрутка внутри контейнера дерева к целевой (итоговой) позиции узла/ветви;
   возвращает целевой scrollTop и диапазон, который должен быть виден (координаты холста) */
function tyScrollToKey(key, smooth){
  const L = TYT.L, o = L.nodes.get(key); if (!o) return null;
  let a = o.y - o.h / 2, b = o.y + o.h / 2;
  if (o.kind === 'type' && TYT.open.has(o.c)) tyRec(o.c).members.forEach(i => { const m = L.nodes.get('m' + i); if (m) { a = Math.min(a, m.y - m.h / 2); b = Math.max(b, m.y + m.h / 2); } });
  a -= 12; b += 12;
  const box = TYT.box, h = box.clientHeight; let st = box.scrollTop;
  if (b - a > h) st = o.kind === 'type' ? o.y - o.h / 2 - 12 : a; else if (a < st) st = a; else if (b > st + h) st = b - h;
  st = Math.max(0, Math.min(st, L.H - h));
  if (Math.abs(st - box.scrollTop) > .5) box.scrollTo({top: st, behavior: smooth && !RM.matches ? 'smooth' : 'auto'});
  return {st, a: Math.max(a, st), b: Math.min(b, st + h)};
}
/* нижняя граница липкой панели вкладок: всё, что выше, перекрыто */
const tyNavBottom = () => { const nv = $('nav.tabs'); return nv ? Math.max(0, nv.getBoundingClientRect().bottom) : 0; };
/* прокрутка страницы, чтобы диапазон [a, b] холста (при scrollTop контейнера st) оказался в окне, не под панелью вкладок */
function tyPageReveal(a, b, st, smooth){
  const box = TYT.box, br = box.getBoundingClientRect(), y0 = br.top + box.clientTop - st, top = tyNavBottom() + 8, bot = innerHeight - 8;
  const A = y0 + a, B = y0 + b; let dy = 0;
  if (B - A > bot - top || A < top) dy = A - top; else if (B > bot) dy = B - bot;
  if (Math.abs(dy) > .5) window.scrollBy({top: dy, behavior: smooth && !RM.matches ? 'smooth' : 'auto'});
}
/* показать контейнер дерева целиком (переход из профилей, поиск, карточка под деревом на узком экране):
   если места хватает — вместе с заголовком раздела; уже видимое дерево страницу не сдвигает */
function tyShowTree(smooth){
  const sec = $('#typesTreeSec').getBoundingClientRect(), br = TYT.box.getBoundingClientRect(), top = tyNavBottom() + 8, bot = innerHeight - 8;
  if (br.top >= top && br.bottom <= bot) return;
  const dy = br.bottom - sec.top <= bot - top ? sec.top - top : br.height > bot - top || br.top < top ? br.top - top : br.bottom - bot;
  window.scrollBy({top: dy, behavior: smooth && !RM.matches ? 'smooth' : 'auto'});
}
function tyFocus(key, opt = {}){
  TYT.fkey = key; tyStates();
  const el = tyNodeEl(key); if (!el) return;
  el.focus({preventScroll: true});
  if (!opt.noScroll) { const s = tyScrollToKey(key, false); if (s) tyPageReveal(s.a, s.b, s.st, false); }
}

function tyToggle(c, open, opt = {}){
  if (open == null) open = !TYT.open.has(c);
  if (open) { if (TYT.focusMode) TYT.open.clear(); TYT.open.add(c); } else TYT.open.delete(c);
  tyRender({anim: true, reveal: open ? 't' + c : null, page: !!opt.page});
}
function tyActivate(d, opt = {}){
  if (d.kind === 'root') { TYT.fkey = 'r'; tyCard('r'); }
  else if (d.kind === 'type' || d.kind === 'strip') { TYT.fkey = 't' + d.c; tyToggle(d.c, d.kind === 'strip' ? true : null, {page: true}); tyCard('t' + d.c); }
  else if (d.kind === 'leaf') { TYT.fkey = 'm' + d.i; TYT.lastSel = d.i; tyCard('m' + d.i); setSel(d.i); announce(`${N[d.i].s}: карточка МО открыта.`);
    if (opt.pointer) tyCardIntoView(); }
}
/* узкий экран (карточка под деревом): после выбора МО касанием/щелчком карточка показывается целиком
   (или с начала, если выше окна); клавиатурный выбор страницу не прокручивает — фокус остаётся видимым в дереве */
function tyCardIntoView(){
  if (getComputedStyle($('.ttree')).gridTemplateColumns.split(' ').length > 1) return;
  const box = $('#treeInfo'), r = box.getBoundingClientRect(), top = tyNavBottom() + 8, bot = innerHeight - 8;
  if (r.top >= top && r.bottom <= bot) return;
  const dy = r.height > bot - top || r.top < top ? r.top - top : r.bottom - bot;
  window.scrollBy({top: dy, behavior: RM.matches ? 'auto' : 'smooth'});
}
function tyTypeahead(ch, from){
  const ord = TYT.L.order, low = ch.toLowerCase(), label = k => (k === 'r' ? TYT.M.rootT : k[0] === 't' ? tyRec(+k.slice(1)).name : N[+k.slice(1)].s).toLowerCase().replace(/^г\.\s*/, '');
  for (let s = 1; s <= ord.length; s++) { const k = ord[(from + s) % ord.length]; if (label(k).startsWith(low)) return k; }
  return null;
}
function tyKey(e){
  const g = e.target.closest && e.target.closest('g.tn'); if (!g || g.classList.contains('gone')) return;
  const d = d3.select(g).datum(), ord = TYT.L.order, k = ord.indexOf(d.key); let to = null;
  switch (e.key) {
    case 'ArrowDown': to = ord[Math.min(ord.length - 1, k + 1)]; break;
    case 'ArrowUp': to = ord[Math.max(0, k - 1)]; break;
    case 'Home': to = ord[0]; break;
    case 'End': to = ord[ord.length - 1]; break;
    case 'ArrowRight':
      if (d.kind === 'root') to = ord[1];
      else if (d.kind === 'type') { if (!TYT.open.has(d.c)) tyToggle(d.c, true, {page: true}); else to = 'm' + tyRec(d.c).members[0]; }
      break;
    case 'ArrowLeft':
      if (d.kind === 'type' && TYT.open.has(d.c)) tyToggle(d.c, false); else if (d.pk) to = d.pk;
      break;
    case 'Enter': case ' ': tyActivate(d); break;
    case '*': if (d.kind !== 'type') return; tyExpandAll(d.key); break;   /* APG: раскрыть все узлы того же уровня */
    default:
      if (e.key.length === 1 && /\S/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) { to = tyTypeahead(e.key, k); if (!to) return; }
      else return;
  }
  e.preventDefault();
  if (to && to !== d.key) tyFocus(to);
}

/* раскрыть родителя МО, выбрать МО и показать его карточку */
function tyRevealMO(i, opt = {}){
  if (i == null || !N[i] || !TYT.ready) return;
  const c = N[i].c;
  if (!TYT.open.has(c)) { if (TYT.focusMode) TYT.open.clear(); TYT.open.add(c); }
  TYT.fkey = 'm' + i; TYT.lastSel = i; TYT.card = 'm' + i;
  tyRender({anim: !!opt.anim, reveal: 'm' + i});
  tyCard('m' + i);
  if (sel !== i) setSel(i);
  if (opt.scrollPage) tyShowTree(true);
  if (opt.focus) { const el = tyNodeEl('m' + i); if (el) el.focus({preventScroll: true}); }
}
function tyRevealType(c, opt = {}){
  if (!TYT.ready) return;
  if (!TYT.open.has(c)) { if (TYT.focusMode) TYT.open.clear(); TYT.open.add(c); }
  TYT.fkey = 't' + c;
  tyRender({anim: true, reveal: 't' + c});
  tyCard('t' + c);
  if (opt.scrollPage) tyShowTree(true);
  if (opt.focus) { const el = tyNodeEl('t' + c); if (el) el.focus({preventScroll: true}); }
}
/* «Развернуть все» (и клавиша * на типе): все 7 ветвей, режим одной ветви выключается;
   после кнопки — начало дерева (корень и первые типы), после клавиши — узел с фокусом */
function tyExpandAll(keepKey){
  TYT.focusMode = false; $('#treeFocus').checked = false; TY.forEach(t => TYT.open.add(t.c));
  tyRender({anim: true});
  if (keepKey) { const s = tyScrollToKey(keepKey, true); if (s) tyPageReveal(s.a, s.b, s.st, true); }
  else TYT.box.scrollTo({top: 0, behavior: RM.matches ? 'auto' : 'smooth'});
  announce(`Раскрыты все ${TY.length} ветвей: ${n} МО.`);
}

/* ---------- карточка выбранного узла ---------- */
function tyCard(key){
  TYT.card = key; const box = $('#treeInfo');
  if (key === 'r') {
    const mx = Math.max(...TY.map(t => t.members.length));
    box.innerHTML = `<span class="eyebrow">Регион</span><h3>${esc(D.region)}</h3>
      <dl class="tc-kv"><div><dt>МО</dt><dd class="mono">${n}</dd></div><div><dt>Типов</dt><dd class="mono">${TY.length}</dd></div><div><dt>Население</dt><dd>${tyPopHtml(N.map((_, i) => i))}</dd></div></dl>
      <h4 class="tc-h4">Число МО по типам</h4>
      <ul class="tc-sizes">${TY.map(t => `<li><button type="button" class="tc-size" data-act="open" data-c="${t.c}"><span class="nm"><span class="sw" style="--c:${COLV(t.c)}"></span>${esc(t.name)}</span><span class="bar" aria-hidden="true"><i style="width:${t.members.length / mx * 100}%;background:${COLV(t.c)}"></i></span><span class="mono v">${t.members.length}</span></button></li>`).join('')}</ul>
      <p class="hint">Нажмите на тип в дереве или в списке, чтобы раскрыть его состав, и на МО — чтобы открыть его карточку.</p>`;
  } else if (key[0] === 't') {
    const t = tyRec(+key.slice(1)), top = t.sig.slice().sort((a, b) => Math.abs(b.effect) - Math.abs(a.effect)).slice(0, 3), on = TYT.open.has(t.c);
    box.innerHTML = `<span class="eyebrow">Экономический тип</span><h3 class="tc-type"><span class="sw" style="--c:${COLV(t.c)}"></span><span>${esc(t.name)}</span></h3>
      <div class="tc-meta"><span class="mono">${t.members.length}</span> МО · ${tyPopHtml(t.members)}</div>
      <h4 class="tc-h4">Сильнее всего отличается от остальных МО</h4>
      <ul class="tc-sig">${top.map(s => `<li><span>${esc(featLabel(s.feature))}</span><span><span class="mono">${fmtSigned(s.effect, 2)}</span> IQR</span><span class="hint">${s.effect > 0 ? 'выше' : 'ниже'} остальных МО</span></li>`).join('')}</ul>
      <div class="acts"><button class="btn sm" type="button" data-act="toggle" data-c="${t.c}" aria-expanded="${on}">${on ? 'Свернуть ветвь' : 'Раскрыть ветвь'}</button>
        <button class="btn sm" type="button" data-act="prof" data-c="${t.c}">Профиль типа ↓</button>
        <button class="btn sm" type="button" data-act="grp" data-c="${t.c}">${ICON.map} Показать на карте</button></div>`;
  } else {
    const i = +key.slice(1), x = N[i], m = mainRec(x), k = m ? kind(m.topic) : null;
    box.innerHTML = `<span class="eyebrow">${x.kind === 'ГО' ? 'Городской округ' : 'Муниципальный район'}</span><h3>${esc(x.s)}</h3>
      <button type="button" class="tc-tline" data-act="type" data-c="${x.c}" title="Показать тип в дереве"><span class="sw" style="--c:${COLV(x.c)}"></span><span>${esc(typeName(x.c))}</span></button>
      <dl class="tc-kv"><div><dt>Население</dt><dd><span class="mono">${fmtN(x.pop)}</span> чел.</dd></div><div><dt>Устойчивость отнесения</dt><dd class="mono">${fmtN(x.stab, 2)}</dd></div></dl>
      <p class="tc-txt">${esc(x.summary)}</p>
      ${m ? `<div class="tc-rec"><div class="tc-rk">${mk(k)}<span>Главная рекомендация · ${esc(KIND_LABEL[k])}</span></div><b>${esc(m.topic)}</b><p class="tc-ev">${esc(m.evidence)}</p><p class="tc-ac">${esc(m.action)}</p></div>` : '<p class="hint">Рекомендаций в данных нет.</p>'}
      <div class="acts"><button class="btn sm" type="button" data-act="go" data-i="${i}">${ICON.map} Открыть на карте</button>${cmpToggle(i, 'btn sm')}</div>`;
  }
  tyStates();
}

function treeInit(){
  TYT.box = $('#tree');
  const svg = TYT.svg = d3.select(TYT.box).append('svg').attr('role', 'tree').attr('aria-label', `Типы МО: ${tyRegionShort} → ${TY.length} типов → ${n} МО`).attr('aria-describedby', 'treeHelp').attr('tabindex', -1);
  TYT.gL = svg.append('g').attr('class', 'links').attr('aria-hidden', 'true');
  TYT.gN = svg.append('g').attr('class', 'nodes');
  svg.on('click', e => { const g = e.target.closest('g.tn'); if (!g || g.classList.contains('gone')) return; tyActivate(d3.select(g).datum(), {pointer: e.detail > 0}); });
  svg.on('keydown', tyKey);
  svg.on('focusin', e => { const g = e.target.closest && e.target.closest('g.tn'); if (g && !g.classList.contains('gone') && g.getAttribute('role')) { const k = d3.select(g).datum().key; if (k !== TYT.fkey) { TYT.fkey = k; tyStates(); } } });
  $('#treeInfo').addEventListener('click', e => {
    const b = e.target.closest('[data-act]'); if (!b) return; const c = +b.dataset.c;
    switch (b.dataset.act) {
      case 'open': tyRevealType(c, {focus: false, scrollPage: true}); break;
      case 'toggle': TYT.fkey = 't' + c; tyToggle(c, null, {page: true}); break;
      case 'prof': tyGoProfile(c); break;
      case 'grp': { const t = tyRec(c); showGroup(t.members.slice(), 'тип «' + t.name + '»'); break; }
      case 'type': tyRevealType(c, {focus: true, scrollPage: true}); break;
      case 'go': goMap(+b.dataset.i); break;
    }
  });
  $('#treeAll').addEventListener('click', () => tyExpandAll());
  $('#treeNone').addEventListener('click', () => { TYT.open.clear(); tyRender({anim: true}); TYT.box.scrollTo({top: 0, behavior: RM.matches ? 'auto' : 'smooth'}); announce('Все ветви свёрнуты.'); });
  $('#treeFocus').addEventListener('change', e => { TYT.focusMode = e.target.checked;
    if (TYT.focusMode && TYT.open.size > 1) { const ck = TYT.card[0] === 't' ? +TYT.card.slice(1) : TYT.card[0] === 'm' ? N[+TYT.card.slice(1)].c : null;
      const keep = ck != null && TYT.open.has(ck) ? ck : [...TYT.open][0]; TYT.open.clear(); TYT.open.add(keep); tyRender({anim: true, reveal: 't' + keep}); }
    else tyStates(); });
  tyCard('r');
  const fontsOk = FONTS_READY.then(() => Promise.all([TFONT.root, TFONT.type, TFONT.leaf, TFONT.leafB, TFONT.sub, TFONT.cnt, TFONT.cntU].map(f => document.fonts && document.fonts.load ? document.fonts.load(f, 'Башкортостан МО 0123456789').catch(() => {}) : null)));
  fontsOk.then(() => whenSized(TYT.box, () => {
    TYT.ready = true;
    if (sel != null && activeTab === 'types') tyRevealMO(sel, {anim: false}); else tyRender({anim: false});
    onResize(TYT.box, () => tyRender({anim: false}));
  }));
}

/* ---------- поиск, навигация, синхронизация выбора ---------- */
$('#typeSearch').addEventListener('change', e => {
  const v = e.target.value.trim(); if (!v) return;
  const i = findMO(v);
  if (i < 0) { notify(e.target.closest('.field'), `МО «${esc(v)}» не найден. Выберите название из списка.`, {kind: 'warn'}); return; }
  tyRevealMO(i, {anim: true, scrollPage: true});
  announce(`${N[i].s}: тип «${typeName(N[i].c)}», карточка открыта.`);
});
$$('#typeView [data-tv]').forEach(b => b.addEventListener('click', () => {
  const id = {tree: 'typesTreeSec', over: 'typesOverSec', prof: 'typeCards'}[b.dataset.tv];
  $('#' + id).scrollIntoView({block: 'start', behavior: RM.matches ? 'auto' : 'smooth'});
}));
SEL_HOOKS.push(() => {
  if (!TYT.ready) return;
  if (activeTab === 'types' && sel != null && sel !== TYT.lastSel) tyRevealMO(sel, {anim: true});
  else tyStates();
});
onTab('types', () => { if (TYT.ready && sel != null && sel !== TYT.lastSel) tyRevealMO(sel, {anim: false}); });

function typesInit(){ tyOverview(); tyCards(); treeInit(); }
