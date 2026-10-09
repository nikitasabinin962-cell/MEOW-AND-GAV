/* ==========================================================================
   Карта → «Матрица связей» → «Типы × типы» (ТЗ 12.2): направленная хорд-диаграмма
   сумм представленных записей flow_rub между семью экономическими типами.
   Матрица 7×7 = сумма аддитивного рублёвого поля по nodes[source].c → nodes[target].c,
   диагональ (внутри типа) сохраняется. Только для flow_rub: корреляции, сходство,
   лаги и процентили не суммируются. D только читается.
   ========================================================================== */
const TCH = {pick: null, hover: null};
function typeFlowMatrix(){
  const T = D.types.map((t, k) => ({c: t.c, name: t.name, no: k + 1})), idx = new Map(T.map((t, k) => [t.c, k]));
  const M = T.map(() => T.map(() => 0)), C = T.map(() => T.map(() => 0)); let total = 0;
  D.layers.flow_rub.forEach(e => { const a = idx.get(N[e[0]].c), b = idx.get(N[e[1]].c); if (a == null || b == null) return; M[a][b] += e[2]; C[a][b]++; total += e[2]; });
  return {T, M, C, total, recs: D.layers.flow_rub.length};
}
const mlnRub = v => fmtN(v / 1e6, v >= 1e10 ? 0 : 1) + ' млн ₽';
function renderTypeChord(host){
  const F = typeFlowMatrix(), K = F.T.length;
  host.innerHTML = `<div class="tch">
    <div class="tch-fig" id="tchFig"><svg id="tchSvg" role="img" aria-label="Направленная хорд-диаграмма: суммы представленных контрактов от поставщиков одного типа к заказчикам другого. Точные суммы — в таблице справа."></svg></div>
    <div class="tch-side">
      <div class="tch-info" id="tchInfo" aria-live="polite"></div>
      <div class="tbox tch-tbox"><table class="tch-tab"><caption>Суммы, млн ₽: строки — тип поставщиков, столбцы — тип заказчиков</caption>
        <thead><tr><th scope="col"><span aria-hidden="true">↓ из · в →</span><span class="sr">Тип поставщиков; столбцы — тип заказчиков</span></th>${F.T.map(t => `<th scope="col" class="n" title="${esc(t.name)}"><span class="sw" style="--c:${COLV(t.c)}"></span>${t.no}</th>`).join('')}<th scope="col" class="n">Всего</th></tr></thead>
        <tbody>${F.T.map((t, a) => `<tr><th scope="row" title="${esc(t.name)}"><span class="sw" style="--c:${COLV(t.c)}"></span>${t.no}<span class="sr"> ${esc(t.name)}</span></th>${F.T.map((u, b) => `<td class="n${a === b ? ' diag' : ''}${F.C[a][b] ? '' : ' nil'}" data-a="${a}" data-b="${b}">${F.C[a][b] ? fmtN(F.M[a][b] / 1e6, 0) : '—'}</td>`).join('')}<td class="n tot">${fmtN(F.M[a].reduce((s, v) => s + v, 0) / 1e6, 0)}</td></tr>`).join('')}</tbody></table></div>
      <ol class="tch-names">${F.T.map(t => `<li><span class="sw" style="--c:${COLV(t.c)}"></span><span class="mono">${t.no}</span> ${esc(t.name)}</li>`).join('')}</ol>
      <p class="hint">Сумма ${F.recs} представленных записей слоя за 2023–2024 — ${mlnRub(F.total)}; это не весь госзаказ республики. Направление — как в данных слоя: поставщики → заказчики; оплата идёт в обратную сторону. «—» — нет записей в представленном наборе (не доказанный ноль). Диагональ — контракты внутри одного типа.</p>
    </div></div>`;
  host.querySelectorAll('.tch-tab td[data-a]').forEach(td => td.onclick = () => { if (!F.C[+td.dataset.a][+td.dataset.b]) return; TCH.pick = {a: +td.dataset.a, b: +td.dataset.b}; TCH.hover = null; tchDraw(F); });
  const fig = $('#tchFig');
  whenSized(fig, () => { tchDraw(F); if (!TCH.ro) TCH.ro = onResize(fig, () => { if ($('#tchSvg')) tchDraw(typeFlowMatrix()); }); });
}
function tchDraw(F){
  const svgEl = $('#tchSvg'), fig = $('#tchFig'); if (!svgEl || !fig) return;
  const W = fig.clientWidth, H = Math.max(320, Math.min(fig.clientHeight || 520, W)), R = Math.max(110, Math.min(W, H) / 2 - 46), r0 = R - 14;
  const svg = d3.select(svgEl).attr('viewBox', `${-W / 2} ${-H / 2} ${W} ${H}`).attr('width', W).attr('height', H);
  const chords = d3.chordDirected().padAngle(.045).sortSubgroups(d3.descending).sortChords(d3.descending)(F.M);
  const arc = d3.arc().innerRadius(r0).outerRadius(R), ribbon = d3.ribbonArrow().radius(r0 - 1.5).padAngle(1 / r0).headRadius(Math.min(14, r0 * .07));
  const act = TCH.pick || TCH.hover;
  const on = ch => !act ? true : act.g != null ? ch.source.index === act.g : (ch.source.index === act.a && ch.target.index === act.b);
  svg.selectAll('*').remove();
  const gR = svg.append('g').attr('class', 'tch-ribbons');
  gR.selectAll('path').data(chords).join('path').attr('d', ribbon)
    .attr('style', d => `fill:var(--c${tslot(F.T[d.source.index].c)});fill-opacity:${on(d) ? (act ? .86 : .46) : .07};stroke:var(--surface);stroke-width:.6`)
    .on('mouseenter', (ev, d) => { if (TCH.pick) return; TCH.hover = {a: d.source.index, b: d.target.index}; tchDraw(F); })
    .on('mouseleave', () => { if (TCH.pick) return; TCH.hover = null; tchDraw(F); })
    .on('click', (ev, d) => { TCH.pick = TCH.pick && TCH.pick.a === d.source.index && TCH.pick.b === d.target.index ? null : {a: d.source.index, b: d.target.index}; TCH.hover = null; tchDraw(F); })
    .append('title').text(d => `${F.T[d.source.index].no} → ${F.T[d.target.index].no}: ${mlnRub(F.M[d.source.index][d.target.index])}`);
  const gA = svg.append('g').attr('class', 'tch-groups').selectAll('g').data(chords.groups).join('g')
    .attr('tabindex', 0).attr('role', 'button')
    .attr('aria-label', d => `Тип ${F.T[d.index].no} «${F.T[d.index].name}»: поставщики — ${mlnRub(F.M[d.index].reduce((s, v) => s + v, 0))}, заказчики — ${mlnRub(F.M.reduce((s, row) => s + row[d.index], 0))}`)
    .attr('aria-pressed', d => !!(TCH.pick && TCH.pick.g === d.index))
    .on('mouseenter', (ev, d) => { if (TCH.pick) return; TCH.hover = {g: d.index}; tchDraw(F); })
    .on('mouseleave', () => { if (TCH.pick) return; TCH.hover = null; tchDraw(F); })
    .on('click', (ev, d) => { TCH.pick = TCH.pick && TCH.pick.g === d.index ? null : {g: d.index}; TCH.hover = null; tchDraw(F); const el = svgEl.querySelector(`.tch-groups g:nth-child(${d.index + 1})`); if (el) el.focus(); })
    .on('keydown', (ev, d) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ev.currentTarget.dispatchEvent(new MouseEvent('click', {bubbles: true})); } });
  gA.append('path').attr('d', arc).attr('style', d => `fill:var(--c${tslot(F.T[d.index].c)});stroke:var(--surface);stroke-width:1`);
  gA.append('text').attr('class', 'tch-no').each(function (d){ const a = (d.startAngle + d.endAngle) / 2 - Math.PI / 2, rr = R + 15;
    d3.select(this).attr('x', Math.cos(a) * rr).attr('y', Math.sin(a) * rr).attr('dy', '.35em').attr('text-anchor', 'middle').text(F.T[d.index].no); });
  /* панель значения */
  let h;
  if (act && act.g != null) { const g = act.g, out = F.M[g].reduce((s, v) => s + v, 0), inn = F.M.reduce((s, row) => s + row[g], 0);
    h = `<b><span class="sw" style="--c:${COLV(F.T[g].c)}"></span>${F.T[g].no} ${esc(F.T[g].name)}</b><div>поставщики этого типа → заказчикам: <b class="mono">${mlnRub(out)}</b></div><div>заказчики этого типа ← от поставщиков: <b class="mono">${mlnRub(inn)}</b></div><div class="hint">внутри типа: ${mlnRub(F.M[g][g])}</div>`; }
  else if (act) { const {a, b} = act, v = F.M[a][b];
    h = `<b><span class="sw" style="--c:${COLV(F.T[a].c)}"></span>${F.T[a].no} → <span class="sw" style="--c:${COLV(F.T[b].c)}"></span>${F.T[b].no}</b><div>Поставщики типа «${esc(F.T[a].name)}» → заказчики типа «${esc(F.T[b].name)}»</div><div><b class="mono">${mlnRub(v)}</b> · записей ${F.C[a][b]} · ${fmtN(v / F.total * 100, 1)}% суммы представленных записей</div>`; }
  else h = `<span class="hint">Наведите или нажмите на дугу типа или ленту — появятся суммы. Ширина ленты у источника — сумма от поставщиков одного типа заказчикам другого; стрелка — к заказчикам.</span>`;
  $('#tchInfo').innerHTML = h;
  document.querySelectorAll('.tch-tab td[data-a]').forEach(td => td.classList.toggle('on', !!act && (act.g != null ? +td.dataset.a === act.g : +td.dataset.a === act.a && +td.dataset.b === act.b)));
}
