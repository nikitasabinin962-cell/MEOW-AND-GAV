/* ==========================================================================
   Типы МО: переходы между экономическими типами по кварталам (ТЗ 12.3).
   Источник — nodes[i].q (тип МО в каждом из D.quarters; та же система типов,
   «типы по скользящим кварталам»). Вес ленты — число МО, блок — число МО типа
   в квартале. Не миграция населения и не денежный поток; номера типов —
   категории, не рейтинг. D только читается.
   ========================================================================== */
const TF = (() => {
  const Q = D.quarters, K = Q.length;
  const TT = D.types.map((t, k) => ({c: t.c, name: t.name, no: k + 1}));          // порядок и номера — как в D.types
  const tOf = c => TT.find(t => t.c === c) || {c, name: typeName(c), no: '?'};
  const valid = N.every(x => Array.isArray(x.q) && x.q.length === K && x.q.every(c => TT.some(t => t.c === c)));
  const qShort = q => q.replace(/^(\d{4})Q(\d)$/, '$1 · Q$2');
  /* блоки и ленты */
  const cnt = Q.map((_, k) => { const m = new Map(); N.forEach(x => m.set(x.q[k], (m.get(x.q[k]) || 0) + 1)); return m; });
  const links = []; for (let k = 0; k < K - 1; k++) { const m = new Map();
    N.forEach((x, i) => { const key = x.q[k] + '>' + x.q[k + 1]; if (!m.has(key)) m.set(key, {k, a: x.q[k], b: x.q[k + 1], ids: []}); m.get(key).ids.push(i); });
    TT.forEach(ta => TT.forEach(tb => { const l = m.get(ta.c + '>' + tb.c); if (l) links.push(l); })); }
  const changes = Q.slice(0, -1).map((_, k) => N.filter(x => x.q[k] !== x.q[k + 1]).length);
  const stable = N.filter(x => new Set(x.q).size === 1).length;
  return {Q, K, TT, tOf, valid, qShort, cnt, links, changes, stable, focusType: null, pick: null, chart: null};
})();

function tfInit(){
  const host = $('#typesOverSec') || $('#t-types').lastElementChild;
  const html = `<div class="sec tflow" id="typesFlowSec">
    <h3 class="sech">Переходы между типами по кварталам <span class="kicker">${esc(TF.Q[0])}–${esc(TF.Q[TF.K - 1])} · ${n} МО</span></h3>
    <p class="secsub">Тип каждого МО в каждом квартале (типы по скользящим кварталам — та же система из 7 типов). Блок — число МО типа в квартале, ширина ленты — число МО, перешедших из типа в тип между соседними кварталами. <b>Это не миграция населения и не денежный поток</b>; номера типов — названия категорий, а не рейтинг.</p>
    ${TF.valid ? `<div class="tf-stats" id="tfStats"></div>
    <div class="tf-legend" id="tfLegend" role="group" aria-label="Выделить тип"></div>
    <div class="tbox tf-box"><div id="tfChart" role="img"></div></div>
    <div class="tf-pick" id="tfPick" aria-live="polite"></div>
    <details class="tf-det"><summary>${ICON.chev}<span>Таблица: тип каждого МО по ${TF.K} кварталам</span></summary><div class="tbox tf-tbox"><table class="tf-tab"><caption class="sr">Тип МО по кварталам</caption><thead id="tfHead"></thead><tbody id="tfBody"></tbody></table></div></details>`
    : `<div class="empty">Квартальные назначения неполные — переходы не строятся, чтобы не выдумывать данные.</div>`}
  </div>`;
  if (host && host.parentElement && host.id === 'typesOverSec') host.insertAdjacentHTML('afterend', html); else $('#t-types').insertAdjacentHTML('beforeend', html);
  if (!TF.valid) return;
  /* сводка */
  $('#tfStats').innerHTML = `<span class="tf-st"><b>Сменили тип</b> между соседними кварталами:</span>` + TF.changes.map((v, k) =>
    `<span class="tf-st"><span class="mono">${esc(TF.Q[k].slice(2))}→${esc(TF.Q[k + 1].slice(4))}</span> <b class="mono">${v}</b></span>`).join('') +
    `<span class="tf-st">из ${n} МО · без смены типа все ${TF.K} кварталов: <b class="mono">${TF.stable}</b></span>`;
  /* легенда-переключатель типов */
  $('#tfLegend').innerHTML = TF.TT.map(t => `<button type="button" class="chip" data-tfc="${t.c}" aria-pressed="false"><span class="sw" style="--c:${COLV(t.c)}"></span><span class="mono">${t.no}</span> ${esc(t.name)}</button>`).join('');
  $('#tfLegend').addEventListener('click', e => { const b = e.target.closest('[data-tfc]'); if (!b) return; const c = +b.dataset.tfc;
    TF.focusType = TF.focusType === c ? null : c; TF.pick = null; tfSync(); });
  /* таблица */
  $('#tfHead').innerHTML = `<tr><th scope="col">МО</th>${TF.Q.map(q => `<th scope="col" class="c">${esc(TF.qShort(q))}</th>`).join('')}<th scope="col" class="n">Смен</th></tr>`;
  const order = N.map((x, i) => i).sort((a, b) => TF.tOf(N[a].c).no - TF.tOf(N[b].c).no || N[a].s.localeCompare(N[b].s, 'ru'));
  $('#tfBody').innerHTML = order.map(i => { const x = N[i], ch = x.q.slice(1).filter((c, k) => c !== x.q[k]).length;
    return `<tr data-i="${i}"><th scope="row"><button type="button" class="link" data-tfi="${i}">${esc(x.s)}</button></th>${x.q.map((c, k) => { const t = TF.tOf(c);
      return `<td class="c${k && c !== x.q[k - 1] ? ' chg' : ''}" title="${esc(TF.Q[k])}: ${esc(t.name)}"><span class="sw" style="--c:${COLV(c)}"></span><span class="mono">${t.no}</span></td>`; }).join('')}<td class="n mono">${ch}</td></tr>`; }).join('');
  $('#tfBody').addEventListener('click', e => { const b = e.target.closest('[data-tfi]'); if (b) setSel(+b.dataset.tfi); });
  $('#tfPick').addEventListener('click', e => { const b = e.target.closest('[data-tfi]'); if (b) setSel(+b.dataset.tfi); });
  TF.chart = makeChart($('#tfChart'), tfOption, {renderer: 'svg', onInit: ch => ch.on('click', p => {
    if (p.dataType === 'edge') { const l = TF.links[p.data.li]; TF.pick = {kind: 'link', l}; }
    else if (p.dataType === 'node') { const [k, c] = p.data.name.split('·').map(Number); TF.pick = {kind: 'node', k, c}; }
    tfSync(false); })});
  tfSync(false);
}
/* значения выделения: выбранный МО (общий выбор) → его путь; иначе тип из легенды; иначе всё */
function tfOn(l){ if (sel != null) return N[sel].q[l.k] === l.a && N[sel].q[l.k + 1] === l.b;
  if (TF.focusType != null) return l.a === TF.focusType || l.b === TF.focusType;
  if (TF.pick && TF.pick.kind === 'link') return l === TF.pick.l;
  return null; }
function tfOption(ch){
  const W = ch.getWidth(), L = 30, R = Math.min(300, Math.max(170, W * .26)), NW = 14, top = 36;
  const nodes = [];
  TF.Q.forEach((q, k) => TF.TT.forEach(t => { const v = TF.cnt[k].get(t.c) || 0; if (!v) return;
    const onPath = sel != null && N[sel].q[k] === t.c, dimT = TF.focusType != null && TF.focusType !== t.c && sel == null;
    nodes.push({name: k + '·' + t.c, depth: k, value: v, itemStyle: {color: COL(t.c), opacity: dimT ? .35 : 1, borderColor: onPath ? css('--pearl-edge') : 'transparent', borderWidth: onPath ? 2 : 0},
      label: {show: k === TF.K - 1, position: 'right', distance: 8, width: R - 16, overflow: 'break', lineHeight: 15, fontSize: 12, color: css('--ink2'), formatter: () => `${t.no}  ${t.name}`}}); }));
  const anyOn = TF.links.some(l => tfOn(l) != null) && (sel != null || TF.focusType != null || (TF.pick && TF.pick.kind === 'link'));
  const edges = TF.links.map((l, li) => { const on = tfOn(l), stay = l.a === l.b;
    const op = !anyOn ? (stay ? .26 : .42) : on ? .82 : .07;
    return {source: l.k + '·' + l.a, target: (l.k + 1) + '·' + l.b, value: l.ids.length, li, lineStyle: {color: 'gradient', opacity: op, curveness: .5}}; });
  const colX = k => L + NW / 2 + k * (W - L - R - NW) / (TF.K - 1);
  return {animationDurationUpdate: 300,
    tooltip: {trigger: 'item', confine: true, formatter: p => {
      if (p.dataType === 'edge') { const l = TF.links[p.data.li], a = TF.tOf(l.a), b = TF.tOf(l.b), names = l.ids.map(i => N[i].s);
        return `<b>${esc(TF.Q[l.k])} → ${esc(TF.Q[l.k + 1])}</b><br>${l.a === l.b ? `остались в типе ${a.no} «${esc(a.name)}»` : `из ${a.no} «${esc(a.name)}»<br>в ${b.no} «${esc(b.name)}»`}<br><b>${l.ids.length} МО</b>: ${esc(names.slice(0, 8).join(', '))}${names.length > 8 ? ` и ещё ${names.length - 8}` : ''}`; }
      const [k, c] = p.data.name.split('·').map(Number), t = TF.tOf(c); return `<b>${esc(TF.Q[k])}</b><br>${t.no} «${esc(t.name)}»: <b>${p.data.value} МО</b>`; }},
    graphic: TF.Q.map((q, k) => ({type: 'text', left: Math.max(0, colX(k) - 26), top: 8, style: {text: TF.qShort(q), fill: css('--ink2'), font: '500 11.5px "JetBrains Mono", monospace', width: 52, align: 'center'}})),
    series: [{type: 'sankey', left: L, right: R, top, bottom: 8, nodeWidth: NW, nodeGap: 7, layoutIterations: 0, draggable: false, nodeAlign: 'justify',
      emphasis: {focus: 'adjacency', lineStyle: {opacity: .9}}, data: nodes, links: edges}]};
}
function tfSync(scroll){
  if (!TF.valid || !$('#tfPick')) return;
  $$('#tfLegend [data-tfc]').forEach(b => b.setAttribute('aria-pressed', TF.focusType === +b.dataset.tfc && sel == null));
  $$('#tfBody tr').forEach(r => r.classList.toggle('on', +r.dataset.i === sel));
  let h = '';
  if (sel != null) { const x = N[sel]; let prev = null;
    h = `<b>${esc(x.s)}</b>: ` + x.q.map((c, k) => { const t = TF.tOf(c), chg = prev != null && prev !== c; prev = c;
      return `<span class="tf-q${chg ? ' chg' : ''}"><span class="mono">${esc(TF.Q[k].slice(2))}</span> <span class="sw" style="--c:${COLV(c)}"></span>${t.no}</span>`; }).join(' → ') +
      ` <span class="hint">· смен типа: ${x.q.slice(1).filter((c, k) => c !== x.q[k]).length}; итоговый тип модели — ${esc(typeName(x.c))}. Путь проходит по выделенным лентам; в каждой ленте — все МО с таким же переходом.</span>`; }
  else if (TF.pick && TF.pick.kind === 'link') { const l = TF.pick.l, a = TF.tOf(l.a), b = TF.tOf(l.b);
    h = `<b>${esc(TF.Q[l.k])} → ${esc(TF.Q[l.k + 1])}</b>, ${l.a === l.b ? `остались в типе ${a.no}` : `из типа ${a.no} в тип ${b.no}`} — ${l.ids.length} МО: ` + l.ids.map(i => `<button type="button" class="link" data-tfi="${i}">${esc(N[i].s)}</button>`).join(', '); }
  else if (TF.pick && TF.pick.kind === 'node') { const t = TF.tOf(TF.pick.c), ids = N.map((x, i) => i).filter(i => N[i].q[TF.pick.k] === TF.pick.c);
    h = `<b>${esc(TF.Q[TF.pick.k])}</b>, тип ${t.no} «${esc(t.name)}» — ${ids.length} МО: ` + ids.map(i => `<button type="button" class="link" data-tfi="${i}">${esc(N[i].s)}</button>`).join(', '); }
  else h = `<span class="hint">Нажмите на ленту или блок — появится список МО; выберите МО (здесь, в дереве или на карте) — подсветится его путь по кварталам.</span>`;
  $('#tfPick').innerHTML = h;
  $('#tfChart').setAttribute('aria-label', `Переходы МО между ${TF.TT.length} типами по ${TF.K} кварталам. Сменили тип между соседними кварталами: ${TF.changes.join(', ')} МО; без смены за все кварталы ${TF.stable}. Точные данные — в таблице ниже.`);
  if (TF.chart && TF.chart.chart) TF.chart.refresh(true);
}
SEL_HOOKS.push(() => { if (TF.valid && $('#tfPick')) { TF.pick = null; tfSync(false); } });
