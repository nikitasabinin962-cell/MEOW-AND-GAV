/* ==========================================================================
   Карта: разметка, контролы, легенда, инспектор, рейтинг, режимы, запуск
   ========================================================================== */
$('#t-map').innerHTML = String.raw`
<div class="mapbar">
  <div class="grp">
    <label class="field" for="colorBy"><span>Раскраска</span><select id="colorBy"></select></label>
    <label class="field" for="qSlider" id="qWrap" hidden><span>Квартал</span><input type="range" id="qSlider" min="0" max="7" value="7"><span id="qLbl" class="mono"></span></label>
  </div>
  <span class="sep" aria-hidden="true"></span>
  <div class="grp">
    <label class="field" for="edgeLayer"><span>Связи</span><select id="edgeLayer"></select></label>
    <label class="field" for="edgeThr"><span>Сила ≥</span><input type="range" id="edgeThr" min="0" max="95" value="0"><span id="thrLbl" class="mono"></span></label>
    <label class="field" for="density"><span>Плотность</span><select id="density"><option value="15">сильнейшие 15</option><option value="30" selected>сильнейшие 30</option><option value="60">сильнейшие 60</option><option value="all">все выше порога</option></select></label>
  </div>
  <button type="button" class="btn sm togsbtn" id="togsBtn" aria-expanded="false" aria-controls="mapTogs">Параметры слоёв</button>
  <div class="togs" id="mapTogs">
    <label class="check" for="onlySel"><input type="checkbox" id="onlySel"> только связи выбранного МО</label>
    <label class="check" for="motionChk" id="motionWrap"><input type="checkbox" id="motionChk" checked> <span id="motionTxt">движение направленных потоков</span></label>
    <label class="check" for="glowChk" id="glowWrap"><input type="checkbox" id="glowChk" checked> подсветка связей</label>
    <label class="check" for="uncChk" title="пограничные районы: силуэт &lt; 0, устойчивость &lt; 0,5 или вероятность типа &lt; 0,5"><input type="checkbox" id="uncChk" checked> пограничные — пунктиром</label>
    <label class="check" for="osm"><input type="checkbox" id="osm"> подложка OpenStreetMap (нужна сеть)</label>
  </div>
  <div class="right">
    <span id="groupInfo" class="hint"></span>
    <label class="field" for="search"><span class="sr">Найти МО</span><input type="search" id="search" list="molist" placeholder="Найти МО: Уфа, Белорецкий…" autocomplete="off"></label>
    <datalist id="molist"></datalist>
  </div>
</div>
<div class="mapcard">
  <div class="maprow">
    <div class="mapwrap" id="mapwrap">
      <div class="scene" id="sceneA" role="region" aria-label="Карта муниципалитетов Башкортостана"></div>
      <div class="scene" id="sceneB" hidden role="region" aria-label="Карта миграционного прироста"></div>
      <div class="scene-lbl float" id="lblA" hidden><b>Сеть связей</b><span>линии — связи между МО</span></div>
      <div class="scene-lbl float" id="lblB" hidden><b>Миграционный прирост, ‰</b><span>показатель района, не маршруты</span></div>
      <div class="flowmatrix" id="flowMatrix" hidden></div>
      <div class="mapfloat float seg viewsw" role="group" aria-label="Режим области карты">
        <button type="button" data-view="map" aria-pressed="true">Карта</button>
        <button type="button" data-view="split" aria-pressed="false">Сеть и миграция</button>
        <button type="button" data-view="matrix" aria-pressed="false">Матрица связей</button>
      </div>
      <div class="mapfloat mapctl float" role="group" aria-label="Камера">
        <button type="button" class="btn ghost sm" id="zIn" aria-label="Приблизить" title="Приблизить"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
        <button type="button" class="btn ghost sm" id="zOut" aria-label="Отдалить" title="Отдалить"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
        <button type="button" class="btn ghost sm" id="fitAll">Весь регион</button>
        <button type="button" class="btn ghost sm" id="dimBtn" aria-pressed="true">3D</button>
      </div>
      <div class="mapfloat float fbnote" id="fbNote" hidden></div>
      <div class="mapfloat attr" id="attrib"></div>
      <div class="mapfloat float selbar" id="selbar"></div>
    </div>
    <aside id="panel" aria-label="Карточка района и связи"></aside>
  </div>
  <div class="legendbar" id="legend" aria-live="polite"></div>
</div>
<details class="sec etable" id="etSec">
  <summary><span class="sech">Все записи слоя связей <span class="kicker" id="etCount"></span></span><span class="hint">таблица — точные значения и доступ без мыши</span></summary>
  <div class="etbar"><label class="field" for="etFilter"><span>МО</span><input type="search" id="etFilter" list="molist" placeholder="все МО" autocomplete="off"></label>
    <label class="check" for="etSelOnly"><input type="checkbox" id="etSelOnly" checked> только выбранный МО</label><span class="hint" id="etNote"></span></div>
  <div class="tbox etbox"><table class="ktab"><thead id="etHead"></thead><tbody id="etBody"></tbody></table></div>
</details>
<div class="sec rank" id="rankSec" hidden>
  <div class="rankhead"><h3 class="sech" id="rankTitle"></h3><span class="hint" id="rankNote"></span></div>
  <div class="rankbox"><div id="rankChart"></div></div>
</div>`;

/* ---------- контролы ---------- */
const mapPlural = (k, one, few, many) => { const a = Math.abs(k) % 100, b = a % 10; return a > 10 && a < 20 ? many : b === 1 ? one : b >= 2 && b <= 4 ? few : many; };
const colorOpts = [['type', 'Тип МО (кластер)'], ['macro', 'Макротип (3)'], ['quarter', 'Тип по кварталам (динамика)'], ['stab', 'Устойчивость отнесения']]
  .concat(Object.entries(D.metrics).map(([k, v]) => ['m:' + k, 'Индекс: ' + v.label]))
  .concat(Object.entries(D.feats).map(([k, v]) => ['f:' + k, 'Признак: ' + v[0]]));
$('#colorBy').innerHTML = `<optgroup label="Типология">${colorOpts.slice(0, 4).map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</optgroup>
  <optgroup label="Миграция"><option value="f:migr_rate">Миграционный прирост, ‰ (шкала вокруг нуля)</option></optgroup>
  <optgroup label="Индексы (процентиль)">${colorOpts.filter(o => o[0].startsWith('m:')).map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</optgroup>
  <optgroup label="Признаки">${colorOpts.filter(o => o[0].startsWith('f:') && o[0] !== 'f:migr_rate').map(([v, l]) => `<option value="${v}">${esc(l)}</option>`).join('')}</optgroup>`;
$('#togsBtn').onclick = () => { const on = !$('.mapbar').classList.contains('showtogs'); $('.mapbar').classList.toggle('showtogs', on); $('#togsBtn').setAttribute('aria-expanded', on); };
$('#qSlider').max = D.quarters.length - 1; $('#qSlider').value = D.quarters.length - 1;
$('#edgeLayer').innerHTML = Object.entries(LAYERS).filter(([k]) => k === 'none' || D.layers[k]).map(([k, l]) => `<option value="${k}">${esc(l)}</option>`).join('');
$('#edgeLayer').value = 'backbone';
$('#molist').innerHTML = N.map(x => `<option value="${esc(x.s)}">`).join('');
if (RM.matches) { $('#motionChk').checked = false; MAPST.motion = false; }
const is2D = () => !!(MAPVS.scenes[0] && MAPVS.scenes[0].kind === 'leaflet');     // честный 2D-резерв: без следа и подсветки
function syncMotionCtl(){
  const d = isDir(MAPST.layer), none = MAPST.layer === 'none', flat = is2D();
  $('#motionChk').disabled = !d || flat; $('#motionWrap').classList.toggle('off', !d || flat);
  $('#motionTxt').textContent = flat ? 'движение: недоступно в 2D-режиме' : d ? 'движение направленных потоков' : 'движение: только у направленных слоёв';
  $('#motionWrap').title = flat ? 'В 2D-режиме бегущего следа нет; направление — стрелка у получателя и подпись «A → B»' : d ? 'Световой след идёт от источника к получателю; скорость и момент условные' : 'У этого слоя нет направления — бегущий след не рисуется';
  $('#glowChk').disabled = d || none || flat; $('#glowWrap').classList.toggle('off', d || none || flat);
  $('#glowWrap').title = flat ? 'В 2D-режиме подсветки нет' : d ? 'У направленного слоя вместо подсветки — световой след направления' : 'Мягкое изменение яркости сильнейших связей без направления';
}
function mapChanged(recalcEdges = true){ MAPST.ver++; if (recalcEdges) computeEdges(); scheduleLabels(); legend(); renderRank(); mapAnimSync(); if (MAPST.view === 'matrix') renderFlowMatrix(); if (recalcEdges) renderEdgeTable(); }
$('#colorBy').addEventListener('input', () => { MAPST.mode = $('#colorBy').value; $('#qWrap').hidden = MAPST.mode !== 'quarter'; mapChanged(false); if (sel != null) panel(); });
$('#qSlider').addEventListener('input', () => { MAPST.qi = +$('#qSlider').value; $('#qLbl').textContent = D.quarters[MAPST.qi]; mapChanged(false); });
$('#edgeLayer').addEventListener('input', () => { MAPST.layer = $('#edgeLayer').value; MAPST.thrP = MAPST.layer === 'backbone' ? 0 : 60; $('#edgeThr').value = MAPST.thrP; MAPST.pinned = null; MAPST.dirFilter = 'all'; syncMotionCtl(); mapChanged(); panel(); });
$('#edgeThr').addEventListener('input', () => { MAPST.thrP = +$('#edgeThr').value; mapChanged(); });
$('#density').addEventListener('input', () => { MAPST.density = $('#density').value; mapChanged(); });
$('#onlySel').addEventListener('input', () => { MAPST.onlySel = $('#onlySel').checked; mapChanged(); });
$('#motionChk').addEventListener('input', () => { MAPST.motion = $('#motionChk').checked; mapAnimSync(); legend(); });
$('#glowChk').addEventListener('input', () => { MAPST.glow = $('#glowChk').checked; MAPST.ver++; mapAnimSync(); legend(); });
$('#uncChk').addEventListener('input', () => { MAPST.unc = $('#uncChk').checked; MAPST.ver++; renderScenes(); });
$('#osm').addEventListener('input', () => { MAPST.basemap = $('#osm').checked; BASEMAP.layer = MAPST.basemap ? basemapLayer() : null; updateAttribution(); renderScenes(); });
/* повторный «change» при уходе фокуса с поля (тот же МО) не пересобирает карточку — иначе первый клик в ней теряется */
$('#search').addEventListener('change', e => { const i = findMO(e.target.value); if (i >= 0 && i !== sel) select(i, true); });
$('#search').addEventListener('keydown', e => { if (e.key === 'Enter' && sel != null && findMO(e.target.value) === sel) fitView(BBOX[sel], {pad: 70, maxZoom: 8.3}); });   // Enter по уже выбранному — вернуть камеру к нему
$('#zIn').onclick = () => setMapVS({...MAPVS.vs, zoom: Math.min(11, MAPVS.vs.zoom + .6), transitionDuration: RM.matches ? 0 : 250}, null);
$('#zOut').onclick = () => setMapVS({...MAPVS.vs, zoom: Math.max(4.5, MAPVS.vs.zoom - .6), transitionDuration: RM.matches ? 0 : 250}, null);
$('#fitAll').onclick = () => fitView(REGION_BOUNDS, {pad: 28, pts: REGION_PTS});
$('#dimBtn').onclick = () => setDim(MAPVS.dim === '3d' ? '2d' : '3d');
function setDim(d, quiet){
  MAPVS.dim = d; const b = $('#dimBtn'); b.textContent = d === '3d' ? '3D' : '2D'; b.setAttribute('aria-pressed', d === '3d');
  b.title = d === '3d' ? 'Сейчас — наклонная 3D-сцена. Нажмите для вида сверху (точная карта)' : 'Сейчас — вид сверху. Нажмите для умеренного наклона';
  MAPVS.scenes.forEach(s => s.setController && s.setController());
  setMapVS({...MAPVS.vs, pitch: d === '3d' ? 35 : 0, bearing: d === '3d' ? MAPVS.vs.bearing : 0, transitionDuration: RM.matches || quiet ? 0 : 450,
    transitionInterpolator: new DK.LinearInterpolator(['pitch', 'bearing'])}, null);
}
function updateAttribution(){ $('#attrib').innerHTML = `Границы МО: geoBoundaries / OpenStreetMap` + (MAPST.basemap ? ` · Подложка: © <a href="https://www.openstreetmap.org/copyright">участники OpenStreetMap</a>` : ''); }

/* ---------- выбор МО, связи, группа ---------- */
function select(i, zoom){
  const nv = (i == null || (sel === i && !zoom)) ? null : i;
  if (nv !== sel) { MAPST.pinned = null; MAPST.selAll = false; MAPST.dirFilter = 'all'; MAPST.selT0 = performance.now(); }
  setSel(nv);
  if (sel != null && zoom) fitView(BBOX[sel], {pad: 70, maxZoom: 8.3});      // район в окружении соседей, а не во весь экран
}
SEL_HOOKS.push(() => { MAPST.selT0 = performance.now(); mapChanged(); panel(); selbar(); });
function fitIds(ids, pad = 40){ if (!ids.length) return; let w = 1e9, s = 1e9, e = -1e9, nn = -1e9;
  ids.forEach(i => { const b = BBOX[i]; w = Math.min(w, b[0][0]); s = Math.min(s, b[0][1]); e = Math.max(e, b[1][0]); nn = Math.max(nn, b[1][1]); }); fitView([[w, s], [e, nn]], {pad}); }
function pinEdge(it){ MAPST.pinned = {e: it.e, lay: it.lay || MAPST.layer}; MAPST.pinT0 = performance.now(); mapChanged(); panel();
  announce(`Выбрана связь: ${N[it.e[0]].s} ${isDir(MAPST.layer) ? '→' : '↔'} ${N[it.e[1]].s}`); }
function showBoth(){ const e = MAPST.pinned && MAPST.pinned.e; if (!e) return; const a = CENTER[e[0]], b = CENTER[e[1]];
  fitView([[Math.min(a[0], b[0]), Math.min(a[1], b[1])], [Math.max(a[0], b[0]), Math.max(a[1], b[1])]], {pad: 90}); }
function clearGroup(){ group = null; groupLabel = ''; $('#groupInfo').innerHTML = ''; mapChanged(false); if (sel == null) panel(); }

/* ---------- наведение и нажатие (общие для сцен) ---------- */
function pickKind(info){ if (!info || !info.picked || !info.layer) return {}; const k = info.layer.id.split('-').slice(1).join('-');
  if (k === 'edges' || k === 'ctx') return {edge: info.object};
  if (k === 'fill') return {mo: info.object.properties.i};
  if (k === 'nodehit') return {mo: info.object};
  return {}; }
function mapHover(info, scene){
  const {mo = null, edge = null} = pickKind(info);
  if (mo !== MAPST.hoverMO || edge !== MAPST.hoverEdge) { MAPST.hoverMO = mo; MAPST.hoverEdge = edge; MAPST.ver++; scheduleLabels(); }
  const r = scene.el.getBoundingClientRect(), ev = {clientX: r.left + info.x, clientY: r.top + info.y};
  if (edge) showTip(ev, edgeTip(edge)); else if (mo != null) showTip(ev, moTip(mo, scene.role)); else hideTip();
}
function mapClick(info, scene){
  const {mo = null, edge = null} = pickKind(info); hideTip();
  if (edge) { pinEdge(edge); return; }
  if (mo != null) { select(mo); return; }
  if (MAPST.pinned) { MAPST.pinned = null; mapChanged(); panel(); return; }
  if (sel != null) select(null);
}
function edgeValueText(e, lay){ return lay === 'flow_rub' ? fmtN(e[2] / 1e6, 1) + ' млн ₽' : lay === 'lead_lag' ? `сила ${fmtN(e[2], 2)}, опережение ${e[3]} мес.` : 'вес ' + fmtN(e[2], 3); }
function edgeMeaning(e, lay){
  const a = esc(N[e[0]].s), b = esc(N[e[1]].s);
  if (lay === 'flow_rub') return `Поставщики из «${a}» → заказчики в «${b}»: сумма контрактов в представленном наборе за 2023–2024. Направление — как в данных слоя (поставщик → заказчик); оплата идёт в обратную сторону.`;
  if (lay === 'lead_lag') return `Траты в «${a}» опережают траты в «${b}» на ${e[3]} мес. (по разметке слоя: ведущий → ведомый). Это закономерность временных рядов, не перенос денег или людей.`;
  return `Связь «${a}» и «${b}» без направления: ${esc(LAYERS[lay] || lay).toLowerCase()}.`;
}
function edgeTip(it){ const e = it.e, lay = MAPST.layer, d = isDir(lay);
  return `<b>${esc(N[e[0]].s)} ${d ? '→' : '↔'} ${esc(N[e[1]].s)}</b><div class="tsub">${esc(LAYERS[lay])}</div><div class="tnum">${edgeValueText(e, lay)}</div><div class="tsub">${d ? 'направление: ' + esc(LMETA[lay].dir) : 'ненаправленная связь'} · нажмите, чтобы закрепить</div>`; }
function moTip(i, role){ const x = N[i], mode = role === 'mig' ? 'f:migr_rate' : MAPST.mode; let v = '';
  if (mode.startsWith('m:')) v = `<div class="tnum">${esc(D.metrics[mode.slice(2)].label)}: ${fmtPctile(x.mp[mode.slice(2)])}</div>`;
  if (mode.startsWith('f:')) v = `<div class="tnum">${esc(D.feats[mode.slice(2)][0])}: ${fmtF(mode.slice(2), x.f[mode.slice(2)])}</div>` + (mode === 'f:migr_rate' ? '<div class="tsub">показатель района, не маршрут</div>' : '');
  if (mode === 'stab') v = `<div class="tnum">устойчивость ${fmtN(x.stab, 2)}</div>`;
  if (mode === 'quarter') v = `<div class="tsub">в ${D.quarters[MAPST.qi]}: ${esc(typeName(x.q[MAPST.qi]))}</div>`;
  return `<b>${esc(x.s)}</b><div class="tsub"><span class="sw" style="--c:${COLV(x.c)}"></span> ${esc(typeName(x.c))}</div><div class="tnum">население ${fmtN(x.pop)}</div>${v}`; }

/* ---------- легенда (строка под картой — не закрывает территорию) ---------- */
function legend(){
  const el = $('#legend'), mode = MAPST.mode; let h = '<div class="lg-col">';
  if (mode === 'type' || mode === 'quarter') {
    h += `<h5>${mode === 'quarter' ? 'Тип в ' + D.quarters[MAPST.qi] : 'Экономический тип'}</h5><div class="lg-types">` + D.types.map(t =>
      `<button class="lrow" type="button" data-c="${t.c}" title="приблизить к МО типа"><span class="sw" style="--c:${COLV(t.c)}"></span><span>${esc(t.name)}</span><span class="mono muted">${mode === 'quarter' ? N.filter(x => x.q[MAPST.qi] === t.c).length : t.members.length}</span></button>`).join('') + '</div>';
  } else if (mode === 'macro') {
    h += '<h5>Макротип</h5><div class="lg-types">' + Object.entries(D.macro_names).map(([c, nm]) => `<span class="lrow"><span class="sw" style="--c:var(--c${MACRO_SLOT[+c % 3]})"></span>${esc(nm)}</span>`).join('') + '</div>';
  } else h += scaleLegend(mode, false);
  h += '</div>';
  if (MAPST.view === 'split') h += '<div class="lg-col">' + scaleLegend('f:migr_rate', true) + '</div>';
  const st = MAPST.stats, lay = MAPST.layer;
  if (st) { const m = LMETA[lay] || {}, d = isDir(lay);
    h += `<div class="lg-col"><h5>Связи: ${esc(LAYERS[lay])}</h5>
      <div class="lnote">${d ? 'направленный слой: ' + esc(m.dir) : 'ненаправленный слой'} · ${esc(m.unit)}</div>
      <div class="ewidth"><svg width="64" height="14" aria-hidden="true"><path d="M2 11 Q 16 3 30 11" fill="none" stroke="var(${FAMV[m.fam]})" stroke-opacity=".6" stroke-width="1"/><path d="M34 11 Q 48 1 62 11" fill="none" stroke="var(${FAMV[m.fam]})" stroke-opacity=".95" stroke-width="2"/></svg><span>толщина и яркость — сила; высота дуги лишь разводит пути</span></div>
      <div class="lnote" id="edgeCount">Показано <b class="mono">${st.shown}</b> из ${st.layerTotal} ${mapPlural(st.layerTotal, 'записи', 'записей', 'записей')} слоя${st.extra ? ` + ${st.extra} ${mapPlural(st.extra, 'связь', 'связи', 'связей')} выбранного МО из совмещённой сети` : ''} · выше порога ${st.above}${st.cap !== Infinity && sel == null ? ` · плотность: сильнейшие ${st.cap}` : ''}${sel != null ? ` · у выбранного МО ${st.selShown} из ${st.selTotal}` : ''}</div>
      ${!st.shown ? '<div class="empty-e">Нет связей выше порога. Уменьшите «Сила ≥» или выберите другой слой.</div>' : ''}</div>
      <div class="lg-col"><h5>${d ? 'Направление' : 'Подсветка'}</h5><div class="lnote">${is2D()
        ? (d ? 'В 2D-режиме бегущего следа нет: направление показывают маленькая стрелка у получателя и подпись «A → B» в карточке связи.' : 'В 2D-режиме подсветки нет; сила связи — толщина и яркость линии.')
        : d
        ? (MAPST.motion ? `Световой след идёт от источника к получателю по той же дуге (${esc(m.dir)}). Момент и скорость условные — это не время и не объём платежа.` : 'Движение выключено; направление показывает маленькая стрелка у получателя и подпись «A → B».')
        : (MAPST.glow ? 'Мягкая подсветка сильнейших связей без направления — у слоя нет источника и получателя.' : 'Подсветка выключена.')}</div>
      ${lay === 'flow_rub' ? `<div class="lnote">${esc(m.dirNote)}</div>` : ''}</div>`;
  }
  h += `<div class="lg-col narrow"><h5>Миграция</h5><div class="lnote">Маршрутов между МО (откуда → куда) в данных нет; есть только прирост района, ‰. <button class="link" type="button" id="toMigr">Показать миграционный прирост</button></div></div>`;
  el.innerHTML = h;
  el.querySelectorAll('[data-c]').forEach(r => r.onclick = () => fitIds(N.map((x, i) => i).filter(i => N[i].c === +r.dataset.c)));
  $('#toMigr').onclick = () => { $('#colorBy').value = 'f:migr_rate'; $('#colorBy').dispatchEvent(new Event('input')); };
}
function scaleLegend(mode, isRight){
  const sc = scaleFor(mode), ttl = mode === 'f:migr_rate' ? 'Миграционный прирост, ‰' : colorOpts.find(o => o[0] === mode)[1].replace(/^(Индекс|Признак): /, '');
  const g = (a, b) => `linear-gradient(90deg,rgb(${a}),rgb(${b}))`;
  let h = `<h5>${esc(ttl)}${isRight ? ' — правая карта' : ''}</h5>`;
  if (sc.kind === 'div') {
    const stops = Array.from({length: 21}, (_, k) => { const v = -sc.M + 2 * sc.M * k / 20, t = sc.t(v), c = t < 0 ? lerp3(PAL.migZero, PAL.migNeg, -t) : lerp3(PAL.migZero, PAL.migPos, t); return `rgb(${c}) ${k * 5}%`; });
    h += `<div class="grad" style="background:linear-gradient(90deg,${stops.join(',')})"></div>
      <div class="ends five"><span>−${fmtN(sc.M, 0)}</span><span>−${fmtN(sc.M / 2, 0)}</span><span>0</span><span>+${fmtN(sc.M / 2, 0)}</span><span>+${fmtN(sc.M, 0)}</span></div>
      <div class="lnote">${mode === 'f:migr_rate' ? 'отток ← 0 → прирост · ' : ''}шкала симметрична вокруг нуля; факт: от ${fmtF(mode.slice(2), sc.min)} до ${fmtF(mode.slice(2), sc.max)}</div>`;
  } else {
    let ends = ['ниже', 'выше'], note = 'ранговая шкала: цвет — место МО среди всех';
    if (mode.startsWith('f:')) ends = [fmtF(mode.slice(2), sc.lo), fmtF(mode.slice(2), sc.hi)];
    if (mode.startsWith('m:')) { ends = ['0', '100']; note = 'процентиль среди МО, 0–100 (не процент) · ' + senseWord(D.metrics[mode.slice(2)].sense); }
    if (mode === 'stab') { ends = ['0', '1']; note = 'доля бутстреп-выборок, 0–1'; }
    h += `<div class="grad" style="background:${g(PAL.seq0, PAL.seq1)}"></div><div class="ends"><span>${ends[0]}</span><span>${ends[1]}</span></div><div class="lnote">${note}</div>`;
  }
  if (sc.missing) h += `<div class="lnote"><span class="ndsw" aria-hidden="true"></span> н/д: ${sc.missing} МО — без заливки, пунктирная граница</div>`;
  return h;
}

/* ---------- рейтинг под картой: та же метрика, синхронный выбор ----------
   Опция строится заново из текущего состояния при каждом обновлении (смена раскраски, выбор, тема):
   makeChart хранит функцию построения, поэтому она не должна замыкать прежний режим. */
let RANK = null;
const rankMode = () => MAPST.view === 'split' ? 'f:migr_rate' : MAPST.mode;
const rankTitle = mode => mode === 'f:migr_rate' ? 'Миграционный прирост, ‰' : colorOpts.find(o => o[0] === mode)[1].replace(/^(Индекс|Признак): /, '');
function rankRows(){ const mode = rankMode();
  const rows = N.map((x, i) => ({i, v: valueOf(i, mode)})); const ok = rows.filter(r => r.v != null).sort((a, b) => b.v - a.v), miss = rows.filter(r => r.v == null);
  return {mode, rows: ok.concat(miss)}; }
function rankOption(){
  const {mode, rows} = rankRows(), sc = scaleFor(mode), ttl = rankTitle(mode), div = sc.kind === 'div', pct = mode.startsWith('f:') && (D.feats[mode.slice(2)] || [])[1] === '%';
  const fmt = v => v == null ? 'н/д' : mode.startsWith('m:') ? fmtN(v, 0) : mode === 'stab' ? fmtN(v, 2) : fmtF(mode.slice(2), v);
  const col = r => { if (r.v == null) return 'transparent'; const c = themeRGB(r.i, mode, 'main'); return `rgb(${c.rgb.join(',')})`; };
  const lim = div ? Math.ceil(sc.M * 1.18 / 5) * 5 : null;          // симметрично вокруг нуля, с местом под подписи значений
  return {grid: {left: 190, right: 96, top: 30, bottom: 10, containLabel: false}, animationDurationUpdate: 350,
    tooltip: {trigger: 'item', formatter: p => { const r = rows[p.dataIndex]; return `<b>${esc(N[r.i].s)}</b><br>${esc(ttl)}: ${fmt(r.v)}<br><span style="opacity:.8">${esc(typeName(N[r.i].c))}</span>`; }},
    xAxis: {type: 'value', position: 'top', min: div ? -lim : (mode.startsWith('m:') ? 0 : null), max: div ? lim : (mode.startsWith('m:') ? 100 : null), splitNumber: 4,
      axisLabel: {color: css('--ink2'), fontSize: 11.5, showMinLabel: !div, showMaxLabel: !div, formatter: v => pct ? fmtN(v * 100, 0) + '%' : (v < 0 ? '−' : '') + fmtN(Math.abs(v), Math.abs(v) < 10 && v % 1 ? 1 : 0)}},
    yAxis: {type: 'category', inverse: true, data: rows.map(r => N[r.i].s), axisTick: {show: false}, axisLine: {show: div, lineStyle: {color: css('--ink2')}},
      axisLabel: {fontSize: 12, color: css('--ink2'), width: 176, overflow: 'truncate',
        formatter: (v, k) => { const t = rows[k].v == null ? v + ' · н/д' : v; return rows[k].i === sel ? '{s|' + t + '}' : t; }, rich: {s: {fontWeight: 700, color: css('--ink')}}}},
    series: [{type: 'bar', barWidth: 11, data: rows.map(r => ({value: r.v, itemStyle: {color: col(r), borderRadius: 2, borderColor: r.i === sel ? css('--pearl-edge') : 'transparent', borderWidth: r.i === sel ? 2 : 0},
        label: {position: r.v != null && r.v < 0 ? 'left' : 'right'}})),
      label: {show: true, position: 'right', formatter: p => fmt(rows[p.dataIndex].v), color: css('--ink2'), fontFamily: 'JetBrains Mono', fontSize: 11.5},
      markLine: div ? {symbol: 'none', silent: true, lineStyle: {color: css('--ink2'), width: 1.2, type: 'solid'}, label: {show: false}, data: [{xAxis: 0}]} : undefined}]};
}
function renderRank(){
  const sec = $('#rankSec'), mode = rankMode();
  if (['type', 'quarter', 'macro'].includes(mode)) { sec.hidden = true; return; }
  sec.hidden = false;
  const sc = scaleFor(mode), ttl = rankTitle(mode);
  $('#rankTitle').innerHTML = `Рейтинг МО: ${esc(ttl)} <span class="kicker">${n - sc.missing} МО с данными${sc.missing ? `, н/д ${sc.missing}` : ''}</span>`;
  $('#rankNote').textContent = mode.startsWith('m:') ? 'Процентиль среди МО (0–100). Нажмите на строку — МО выделится на карте.' : sc.kind === 'div' ? 'Нулевая ось в центре: слева отток, справа прирост. Нажмите на строку — МО выделится на карте.' : 'Нажмите на строку — МО выделится на карте.';
  const box = $('#rankChart'); box.style.height = (n * 19 + 46) + 'px';
  if (!RANK || !RANK.el.isConnected) { RANK = makeChart(box, rankOption, {onInit: ch => ch.on('click', p => { const {rows} = rankRows(); select(rows[p.dataIndex].i, true); })}); }
  else { RANK.refresh(true); if (RANK.chart) RANK.chart.resize(); }
}

/* ---------- таблица всех записей слоя: эквивалент WebGL-сцены для чтения и клавиатуры ---------- */
function renderEdgeTable(){
  const sec = $('#etSec'), lay = MAPST.layer; if (!sec) return;
  if (lay === 'none' || !D.layers[lay]) { $('#etCount').textContent = '— слой выключен'; $('#etHead').innerHTML = ''; $('#etBody').innerHTML = ''; return; }
  const E = D.layers[lay], d = isDir(lay), ll = lay === 'lead_lag';
  $('#etCount').textContent = `${LAYERS[lay]} · ${E.length} ${mapPlural(E.length, 'запись', 'записи', 'записей')}`;
  if (!sec.open) return;
  const q = findMO($('#etFilter').value), only = $('#etSelOnly').checked && sel != null, f = only ? sel : (q >= 0 ? q : null);
  const rows = E.map((e, k) => [e, k]).filter(([e]) => f == null || e[0] === f || e[1] === f).sort((a, b) => b[0][2] - a[0][2]);
  $('#etNote').textContent = f == null ? `показаны все ${rows.length}, по убыванию силы` : `${rows.length} из ${E.length} касаются «${N[f].s}», по убыванию силы`;
  $('#etHead').innerHTML = `<tr><th>${d ? (ll ? 'Ведущий ряд' : 'Поставщики из') : 'МО A'}</th><th aria-label="направление"></th><th>${d ? (ll ? 'Ведомый ряд' : 'Заказчики в') : 'МО B'}</th><th class="n">${lay === 'flow_rub' ? 'Сумма, млн ₽' : 'Вес'}</th>${ll ? '<th class="n">Опережение, мес.</th>' : ''}<th><span class="sr">действие</span></th></tr>`;
  const pin = MAPST.pinned && MAPST.pinned.e;
  $('#etBody').innerHTML = rows.map(([e, k]) => `<tr class="${e === pin ? 'on' : ''}"><td>${esc(N[e[0]].s)}</td><td class="c">${d ? '→' : '↔'}</td><td>${esc(N[e[1]].s)}</td>
    <td class="n">${lay === 'flow_rub' ? fmtN(e[2] / 1e6, 1) : fmtN(e[2], 3)}</td>${ll ? `<td class="n">${e[3]}</td>` : ''}<td><button class="link" type="button" data-etk="${k}" aria-label="Показать на карте: ${esc(N[e[0]].s)} ${d ? '→' : '↔'} ${esc(N[e[1]].s)}">на карте</button></td></tr>`).join('')
    || `<tr><td colspan="${ll ? 6 : 5}" class="muted">В слое нет записей с этим МО.</td></tr>`;
}
$('#etSec').addEventListener('toggle', renderEdgeTable);
$('#etFilter').addEventListener('input', () => { if ($('#etFilter').value) $('#etSelOnly').checked = false; renderEdgeTable(); });
$('#etSelOnly').addEventListener('input', renderEdgeTable);
$('#etBody').addEventListener('click', ev => { const b = ev.target.closest('[data-etk]'); if (!b) return; const e = D.layers[MAPST.layer][+b.dataset.etk];
  if (MAPST.view === 'matrix') setView('map'); pinEdge({e, lay: MAPST.layer}); showBoth(); $('#mapwrap').scrollIntoView({block: 'nearest', behavior: RM.matches ? 'auto' : 'smooth'}); });

/* ---------- режимы области: Карта / Сеть и миграция / Матрица связей ---------- */
$$('.viewsw [data-view]').forEach(b => b.onclick = () => setView(b.dataset.view));
function setView(v){
  resetUiBoxes(); hideTip(); MAPST.hoverMO = null; MAPST.hoverEdge = null;   // уходящая сцена не успеет сообщить «курсор ушёл» — подсказка и наведение сбрасываются здесь
  if (v === 'split' && MAPVS.scenes[0] && MAPVS.scenes[0].kind === 'leaflet') { notify($('.viewsw'), 'Режим «Сеть и миграция» с двумя синхронными сценами требует WebGL2; в 2D-режиме переключите раскраску на «Миграционный прирост».', {kind: 'warn'}); return; }
  if (v === 'split' && MAPST.view !== 'split') { MAPST.dimBeforeSplit = MAPVS.dim; if (MAPVS.dim === '3d') setDim('2d', true); }   // сопоставление — по умолчанию вид сверху
  if (v !== 'split' && MAPST.view === 'split' && MAPST.dimBeforeSplit && MAPST.dimBeforeSplit !== MAPVS.dim && MAPVS.scenes[0] && MAPVS.scenes[0].kind === 'deck') setDim(MAPST.dimBeforeSplit, true);
  MAPST.view = v; $$('.viewsw [data-view]').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === v));
  $('#mapwrap').classList.toggle('split', v === 'split'); $('#mapwrap').classList.toggle('matrix', v === 'matrix'); $('#sceneB').hidden = v !== 'split'; $('#lblA').hidden = $('#lblB').hidden = v !== 'split';
  $('#flowMatrix').hidden = v !== 'matrix';
  if (v === 'split' && MAPVS.scenes.length < 2) whenSized($('#sceneB'), () => { const s = new DeckScene($('#sceneB'), 'mig'); MAPVS.scenes.push(s);
    MAPVS.scenes[0].resized(); fitView(sel != null ? BBOX[sel] : REGION_BOUNDS, {pad: 24, maxZoom: 6.8, duration: 0}); s.placeLabels(); renderScenes(); });   // половина ширины: регион или выбранный МО среди соседей (без сильного приближения)
  if (v !== 'split' && MAPVS.scenes.length > 1) { MAPVS.scenes.splice(1).forEach(s => s.destroy()); whenSized($('#sceneA'), () => { MAPVS.scenes[0] && MAPVS.scenes[0].resized(); scheduleLabels(); }); }
  if (v === 'matrix') renderFlowMatrix();
  legend(); renderRank(); mapAnimSync(); scheduleLabels(); if (sel != null) panel();
}

/* ---------- матрица связей: точное чтение плотной сети ---------- */
let FMX = null, fmxSort = 'type';
let fmxMode = 'mo';                                                  // «МО × МО» или «Типы × типы» (только для аддитивных рублёвых сумм flow_rub)
function renderFlowMatrix(){
  const box = $('#flowMatrix'), lay = MAPST.layer;
  if (lay === 'none' || !D.layers[lay]) { box.innerHTML = '<div class="empty" style="margin:20px">Выберите слой связей — матрица покажет все его записи.</div>'; return; }
  const lvl = lay === 'flow_rub' ? `<div class="seg" role="group" aria-label="Уровень матрицы"><button type="button" data-fm="mo" aria-pressed="${fmxMode === 'mo'}">МО × МО</button><button type="button" data-fm="types" aria-pressed="${fmxMode === 'types'}">Типы × типы</button></div>` : '';
  if (lay === 'flow_rub' && fmxMode === 'types') {
    box.innerHTML = `<div class="fmx-head"><div><b>${esc(LAYERS[lay])} — между экономическими типами</b><span class="hint">направленная хорд-диаграмма: сумма представленных записей от поставщиков типа A к заказчикам типа B</span></div><div class="fmx-tools">${lvl}</div></div><div class="fmx-scroll" id="fmxTypes"></div>`;
    box.querySelectorAll('[data-fm]').forEach(b => b.onclick = () => { fmxMode = b.dataset.fm; renderFlowMatrix(); });
    if (FMX) { FMX.dispose(); FMX = null; }
    renderTypeChord($('#fmxTypes')); return;
  }
  const dir = isDir(lay), E = D.layers[lay], tot = new Array(n).fill(0);
  E.forEach(e => { tot[e[0]] += e[2]; tot[e[1]] += e[2]; });
  const order = N.map((x, i) => i).sort(fmxSort === 'type' ? (a, b) => N[a].c - N[b].c || tot[b] - tot[a] : fmxSort === 'total' ? (a, b) => tot[b] - tot[a] : (a, b) => N[a].s.localeCompare(N[b].s, 'ru'));
  const pos = new Array(n); order.forEach((i, k) => pos[i] = k);
  const cells = []; E.forEach(e => { cells.push([pos[e[1]], pos[e[0]], lay === 'flow_rub' ? Math.log10(e[2]) : e[2], e]); if (!dir) cells.push([pos[e[0]], pos[e[1]], lay === 'flow_rub' ? Math.log10(e[2]) : e[2], e]); });
  const vals = cells.map(c => c[2]), lo = Math.min(...vals), hi = Math.max(...vals);
  box.innerHTML = `<div class="fmx-head"><div><b>${esc(LAYERS[lay])}</b><span class="hint">${dir ? 'строки — источник (' + esc(LMETA[lay].dir.split(' → ')[0]) + '), столбцы — получатель' : 'симметричная матрица ненаправленного слоя'} · ${E.length} записей · пустая клетка — нет записи в представленном наборе (не доказанный ноль)</span></div>
    <div class="fmx-tools">${lvl}<div class="seg" role="group" aria-label="Порядок"><button type="button" data-fs="type" aria-pressed="${fmxSort === 'type'}">по типам</button><button type="button" data-fs="total" aria-pressed="${fmxSort === 'total'}">по сумме связей</button><button type="button" data-fs="name" aria-pressed="${fmxSort === 'name'}">по алфавиту</button></div></div></div>
    <div class="fmx-scroll"><div id="fmxChart" style="width:${n * 15 + 220}px;height:${n * 15 + 200}px"></div></div>`;
  box.querySelectorAll('[data-fs]').forEach(b => b.onclick = () => { fmxSort = b.dataset.fs; renderFlowMatrix(); });
  box.querySelectorAll('[data-fm]').forEach(b => b.onclick = () => { fmxMode = b.dataset.fm; renderFlowMatrix(); });
  const build = () => ({grid: {left: 200, top: 180, right: 20, bottom: 20},
    tooltip: {formatter: p => { const e = p.data[3]; return `<b>${esc(N[e[0]].s)} ${dir ? '→' : '↔'} ${esc(N[e[1]].s)}</b><br>${edgeValueText(e, lay)}`; }},
    xAxis: {type: 'category', position: 'top', data: order.map(i => N[i].s), axisLabel: {rotate: 90, fontSize: 11, interval: 0}, splitArea: {show: false}, axisTick: {show: false}},
    yAxis: {type: 'category', inverse: true, data: order.map(i => N[i].s), axisLabel: {fontSize: 11, interval: 0}, axisTick: {show: false}},
    visualMap: {show: false, min: lo, max: hi, inRange: {color: [mix('--seq0', '--seq1', .32), css('--seq1')]}, dimension: 2},   // самая слабая запись заметно отличается от пустой клетки
    series: [{type: 'heatmap', data: cells, itemStyle: {borderColor: css('--surface'), borderWidth: .5}, emphasis: {itemStyle: {borderColor: css('--ink'), borderWidth: 1.5}}}]});
  if (FMX) FMX.dispose();
  FMX = makeChart($('#fmxChart'), build, {renderer: 'canvas', onInit: ch => ch.on('click', p => { const e = p.data[3]; setView('map'); pinEdge({e, lay}); showBoth(); })});
}

/* ---------- инспектор ---------- */
let showAllNb = false;
function edgeCard(){
  if (!MAPST.pinned) return '';
  const e = MAPST.pinned.e, lay = MAPST.pinned.lay, d = isDir(lay), m = LMETA[lay] || {};
  return `<section class="edgecard" aria-label="Выбранная связь"><div class="idrow"><span class="eyebrow">Выбранная связь · ${esc(LAYERS[lay])}</span><button class="btn ghost sm" type="button" id="unpin" aria-label="Снять выбор связи">${ICON.close}</button></div>
    <div class="ends"><button class="link" type="button" data-go="${e[0]}">${esc(N[e[0]].s)}</button> <span class="arrow">${d ? '→' : '↔'}</span> <button class="link" type="button" data-go="${e[1]}">${esc(N[e[1]].s)}</button></div>
    <div class="val mono">${edgeValueText(e, lay)}</div>
    <div class="txt">${edgeMeaning(e, lay)}</div>
    <div class="hint">${d ? 'Направление: ' + esc(m.dir) : 'Ненаправленная связь'} · единица: ${esc(m.unit || '')} · период данных: ${esc(D.period)}</div>
    <div class="acts"><button class="btn sm" type="button" id="showBoth">Показать оба МО</button></div></section>`;
}
function panel(){
  const P = $('#panel');
  if (sel == null) {
    const cnt = {}; N.forEach(x => new Set(x.recs.map(r => r.topic)).forEach(t => cnt[t] = (cnt[t] || 0) + 1));
    P.innerHTML = `<div class="insp">${edgeCard()}
      ${group ? `<section><h4>Подсвечено: ${esc(groupLabel)} <span class="mono">${group.size} МО</span></h4><div class="chips">${[...group].map(i => `<button class="chip" type="button" data-go="${i}"><span class="sw" style="--c:${COLV(N[i].c)}"></span>${esc(N[i].s)}</button>`).join('')}</div>
        <div><button class="btn sm" type="button" id="grpClr">Сбросить подсветку</button></div></section>` : ''}
      <section><span class="eyebrow">Регион</span><h2>${esc(D.region)}</h2>
        <div class="facts2"><div><b>${n}</b>МО</div><div><b>${D.k}</b>типов</div><div><b>${Object.keys(D.layers).length}</b>слоёв связей</div></div>
        <div class="txt">Нажмите на район — откроется карточка. Наведите на дугу — увидите связь, нажмите — закрепите её здесь с обоими концами. Перетаскивание с правой кнопкой или Ctrl — наклон и поворот; «3D/2D» — вид сверху.</div></section>
      <section><h4>Типы <span class="hint">нажмите — приблизить</span></h4><div class="chips">${D.types.map(t => `<button class="chip" type="button" data-type="${t.c}"><span class="sw" style="--c:${COLV(t.c)}"></span>${esc(t.name)} · ${t.members.length}</button>`).join('')}</div></section>
      <section><h4>Темы рекомендаций <span class="hint">число МО</span></h4><div class="probs">${Object.entries(cnt).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
        `<span style="display:flex;gap:8px;align-items:center">${mk(kind(k))}${esc(k)}</span><span class="hbar"><i style="width:${v / n * 100}%;background:var(--${kind(k)})"></i></span><span class="num mono">${v}</span>`).join('')}</div></section>
      <section><h4>Сеть</h4><div class="txt">Итоговая сеть = ${fmtN(D.alpha * 100)}% сходство признаков + ${fmtN((1 - D.alpha) * 100)}% связи: ${Object.entries(D.weights).map(([k, w]) => esc(LAYERS[k] || k).toLowerCase() + ' ' + fmtN(w * 100) + '%').join(', ')}. Каждый МО связан с ${D.knn} ближайшими соседями.</div></section></div>`;
  } else {
    const x = N[sel], tp = D.types.find(t => t.c === x.c), lay = MAPST.layer, d = isDir(lay), st = MAPST.stats;
    const med = k => median(tp.members.map(i => N[i].f[k])), reg = k => median(N.map(z => z.f[k]));
    /* ключевые показатели: единица — в названии строки, в ячейках только числа (таблица помещается в карточку без прокрутки вбок) */
    const kU = k => D.feats[k][1], kV = (k, v) => v == null ? NA : kU(k) === '%' ? fmtN(v * 100, 1) : fmtN(v, Math.abs(v) >= 100 ? 0 : 2);
    const mbar = Object.entries(D.metrics).map(([k, dd]) => { const p = x.mp[k], cls = senseCls(dd, p);
      return `<details class="ixrow"><summary><span class="l" title="${esc(senseTxt(dd))}">${ICON.chev}<span>${esc(dd.label)}</span></span>${ptrack(p, cls)}<span class="num mono">${p == null ? NA : fmtN(p)}</span></summary><div class="calc">${explain(k, sel)}</div></details>`; }).join('');
    const keyF = ['spend_total', 'wage', 'emp_per_1000', 'grants_pc', 'proc_pc', 'proc_local_sh', 'proc_single_sh', 'sh_Маркетплейсы', 'migr_rate', 'urban_share'].filter(k => D.feats[k]);
    const nb = (MAPST.edges || []).slice().sort((a, b) => b.e[2] - a.e[2]);
    const bj = x.bench ? N.findIndex(z => z.mo === x.bench) : -1;
    P.innerHTML = `<div class="insp">
      <section class="idhead"><div class="idrow"><div><span class="eyebrow">${x.kind === 'ГО' ? 'Городской округ' : 'Муниципальный район'}</span><h2>${esc(x.s)}</h2></div>
        <button class="btn ghost sm" type="button" id="closeSel" aria-label="Закрыть карточку">${ICON.close}</button></div>
        <div class="typeline"><span class="sw" style="--c:${COLV(x.c)}"></span>${esc(typeName(x.c))}</div><div class="macro">макротип: ${esc(D.macro_names[x.macro])}</div>
        <div class="facts2"><div><b>${fmtN(x.pop)}</b>население</div><div title="доля бутстреп-выборок, где МО остаётся со своим типом"><b>${fmtN(x.stab, 2)}</b>устойчивость</div><div title="силуэт МО в своём кластере, −1…1"><b>${fmtN(x.typ, 2)}</b>типичность</div></div>
        <nav class="navs" aria-label="Разделы карточки"><a href="#p-net">Связи</a><a href="#p-recs">Выводы</a><a href="#p-ix">Индексы</a><a href="#p-key">Показатели</a><a href="#p-dyn">Динамика</a></nav></section>
      ${edgeCard()}
      ${valueBlock(sel)}
      <section><div class="txt" style="color:var(--ink)">${esc(x.summary)}</div>
        <div class="acts">${cmpToggle(sel)}${bj >= 0 ? `<button class="btn" type="button" id="benchBtn" aria-expanded="false">Сравнить с ориентиром: ${esc(N[bj].s)}</button>` : ''}</div><div id="benchBox"></div></section>
      <section id="p-net"><h4>Связи: ${esc(LAYERS[lay] || 'слой выключен')} <span class="mono nw">${st ? st.selShown + ' из ' + st.selTotal : ''}</span></h4>
        ${lay === 'none' || !st ? '<div class="hint">Слой связей выключен.</div>' : `
        ${d ? `<div class="seg sm" role="group" aria-label="Направление относительно МО"><button type="button" data-dir="all" aria-pressed="${MAPST.dirFilter === 'all'}">Все</button><button type="button" data-dir="out" aria-pressed="${MAPST.dirFilter === 'out'}">Исходящие</button><button type="button" data-dir="in" aria-pressed="${MAPST.dirFilter === 'in'}">Входящие</button></div>
          <div class="hint">${lay === 'flow_rub' ? 'Исходящие — «МО → другие»: поставщики этого МО и их заказчики; входящие — заказчики этого МО и их поставщики (по направлению данных).' : 'Исходящие — МО опережает других; входящие — другие опережают МО.'}</div>` : ''}
        ${nb.length ? `<div class="nblist">${nb.map(it => { const e = it.e, j = e[0] === sel ? e[1] : e[0], arrow = d ? (e[0] === sel ? '→' : '←') : '↔';
          return `<button type="button" data-pin="${D.layers[lay].indexOf(e) >= 0 ? D.layers[lay].indexOf(e) : 'f' + D.layers.fused.indexOf(e)}" class="${MAPST.pinned && MAPST.pinned.e === e ? 'on' : ''}"><span>${arrow} ${esc(N[j].s)}</span><span class="mono">${edgeValueText(e, lay)}</span></button>`; }).join('')}</div>
          ${st.selTotal > 12 ? `<div><button class="link" type="button" id="nbAll">${MAPST.selAll ? 'Показать сильнейшие 12' : 'Показать все ' + st.selTotal}</button></div>` : ''}` : '<div class="hint">В этом слое у МО нет связей (с учётом фильтра направления).</div>'}`}
        ${x.analogs.length ? `<h4>Аналоги по сети</h4><div class="chips">${x.analogs.map(a => { const j = N.findIndex(z => z.mo === a); return j < 0 ? '' : `<button class="chip" type="button" data-go="${j}"><span class="sw" style="--c:${COLV(N[j].c)}"></span>${esc(N[j].s)}${x.bench === a ? ' · ориентир' : ''}</button>`; }).join('')}</div>` : ''}</section>
      <section id="p-recs"><h4>Выводы и рекомендации <span class="mono">${x.recs.length}</span></h4><div class="recs">${x.recs.map(recHtml).join('')}</div>
        ${x.anom.length ? `<div class="anom"><h5>Чем отличается от своего типа</h5><ul>${x.anom.map(a => `<li>${esc(a)}</li>`).join('')}</ul></div>` : ''}</section>
      ${uncBlock(sel)}
      <section id="p-ix"><h4>Индексы, процентиль среди МО <span class="hint">нажмите — расчёт</span></h4>
        <div class="hint">Точка — место МО (0–100, не процент); риска в центре — медиана региона. Цвет: <span style="color:var(--opp)">●</span> благоприятно · <span style="color:var(--risk)">●</span> неблагоприятно · <span style="color:var(--info)">●</span> нейтральный индекс.</div><div>${mbar}</div></section>
      <section id="p-key"><h4>Ключевые показатели</h4><div class="tbox"><table class="ktab"><thead><tr><th>Показатель</th><th class="n">МО</th><th class="n">медиана типа</th><th class="n">медиана региона</th></tr></thead><tbody>
        ${keyF.map(k => `<tr><td>${esc(D.feats[k][0])}${kU(k) ? `<span class="u">, ${esc(kU(k))}</span>` : ''}</td><td class="n" style="color:var(--ink)">${kV(k, x.f[k])}</td><td class="n">${kV(k, med(k))}</td><td class="n">${kV(k, reg(k))}</td></tr>`).join('')}</tbody></table></div></section>
      <section id="p-dyn"><h4>Тип по кварталам</h4><div class="qhist">${x.q.map((c, j) => `<div title="${D.quarters[j]}: ${esc(typeName(c))}"><span style="--c:${COLV(c)}"></span>${D.quarters[j].slice(2)}</div>`).join('')}</div>
        <h4 style="margin-top:6px">Безналичные траты на жителя, ₽/мес</h4>${spark(x.sp, D.months)}</section></div>`;
    $('#closeSel').onclick = () => select(null);
    if ($('#benchBtn')) $('#benchBtn').onclick = () => { const b = $('#benchBox'), open = !b.innerHTML; b.innerHTML = open ? benchTable(sel, bj) : ''; $('#benchBtn').setAttribute('aria-expanded', open); };
    if ($('#nbAll')) $('#nbAll').onclick = () => { MAPST.selAll = !MAPST.selAll; mapChanged(); panel(); $('#p-net').scrollIntoView({block: 'nearest'}); };
    P.querySelectorAll('[data-dir]').forEach(b => b.onclick = () => { MAPST.dirFilter = b.dataset.dir; MAPST.pinned = null; mapChanged(); panel(); });
    P.querySelectorAll('[data-pin]').forEach(b => b.onclick = () => { const v = b.dataset.pin, e = v.startsWith('f') ? D.layers.fused[+v.slice(1)] : D.layers[lay][+v];
      const it = MAPST.edges.find(z => z.e === e) || {e}; pinEdge(it); });
    /* переход к разделу карточки: позиция считается относительно самой карточки (offsetTop отсчитывается от body);
       на узком экране карточка не прокручивается сама — прокручивается страница с учётом липкой панели вкладок */
    P.querySelectorAll('.navs a').forEach(a => a.onclick = ev => { ev.preventDefault(); const t = $(a.getAttribute('href')), sm = RM.matches ? 'auto' : 'smooth';
      if (P.scrollHeight > P.clientHeight + 2) P.scrollTo({top: t.getBoundingClientRect().top - P.getBoundingClientRect().top + P.scrollTop - P.querySelector('.idhead').offsetHeight - 4, behavior: sm});
      else { const tb = $('nav.tabs'), off = tb && getComputedStyle(tb).position === 'sticky' ? tb.offsetHeight : 0; scrollTo({top: t.getBoundingClientRect().top + scrollY - off - 8, behavior: sm}); }
      t.tabIndex = -1; t.focus({preventScroll: true}); });
  }
  P.querySelectorAll('[data-go]').forEach(b => b.onclick = () => select(+b.dataset.go, true));
  P.querySelectorAll('[data-type]').forEach(b => b.onclick = () => fitIds(N.map((x, i) => i).filter(i => N[i].c === +b.dataset.type)));
  if ($('#grpClr')) $('#grpClr').onclick = clearGroup;
  if ($('#unpin')) $('#unpin').onclick = () => { MAPST.pinned = null; mapChanged(); panel(); };
  if ($('#showBoth')) $('#showBoth').onclick = showBoth;
  if (!MAPST.pinned) P.scrollTop = 0;
}
/* значение текущей раскраски: точное число, место среди МО, шкала — рядом с картой, а не только в tooltip */
function valueBlock(i){
  const mode = MAPST.view === 'split' ? 'f:migr_rate' : MAPST.mode; if (['type', 'quarter', 'macro'].includes(mode)) return '';
  const v = valueOf(i, mode), ok = N.map((z, j) => valueOf(j, mode)).filter(t => t != null), ttl = mode === 'f:migr_rate' ? 'Миграционный прирост, ‰' : colorOpts.find(o => o[0] === mode)[1].replace(/^(Индекс|Признак): /, '');
  const val = v == null ? NA : mode.startsWith('m:') ? fmtPctile(v) : mode === 'stab' ? fmtN(v, 2) : fmtF(mode.slice(2), v);
  const place = v == null ? 'нет значения — район на карте без заливки, с пунктирной границей' : `${ok.filter(t => t > v).length + 1}-е место из ${ok.length} по убыванию`;
  const sc = scaleFor(mode), side = sc.kind === 'div' && v != null ? (v > 0 ? ' · прирост' : v < 0 ? ' · отток' : ' · ноль') : '';
  return `<section class="valblk"><span class="eyebrow">Раскраска карты${MAPST.view === 'split' ? ' (правая сцена)' : ''}</span><div class="vrow2"><span>${esc(ttl)}</span><b class="mono">${val}</b></div><div class="hint">${place}${side}</div></section>`;
}
function selbar(){ resetUiBoxes(); $('.mapcard').classList.toggle('hassel', sel != null); const b = $('#selbar'); if (sel == null) { b.classList.remove('on'); b.innerHTML = ''; return; }
  b.classList.add('on'); b.innerHTML = `<span class="sw" style="--c:${COLV(N[sel].c)}"></span><b>${esc(N[sel].s)}</b><button class="btn sm" type="button" id="toCard">Карточка ↓</button>`;
  $('#toCard').onclick = () => $('#panel').scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth'}); }

/* ---------- расчёт индексов, неопределённость, ориентир, траты (как в исходной версии) ---------- */
function pctOf(k, v, neg){ const a = N.map(z => z.f[k]).filter(t => t != null); if (v == null) return null;
  const le = a.filter(t => neg ? t >= v : t <= v).length, eq = a.filter(t => t === v).length; return 100 * (le - (eq - 1) / 2) / a.length; }
function explain(k, i){
  const x = N[i], f = x.f, d = D.metrics[k], v = x.m[k];
  const line = (a, b) => `<div>${a}${b != null ? ': <b>' + b + '</b>' : ''}</div>`, pc = (key, neg) => fmtN(pctOf(key, f[key], neg)) + '-й';
  let s = `<div><i>${esc(d.formula)}</i></div>`;
  if (k === 'localization') s += line(FL('proc_local_sh'), fmtF('proc_local_sh', f.proc_local_sh));
  else if (k === 'external_dep') s += line(FL('proc_ufa_sh'), fmtF('proc_ufa_sh', f.proc_ufa_sh)) + line(FL('proc_out_sh'), fmtF('proc_out_sh', f.proc_out_sh)) + line('Сумма', fmtN(v * 100, 1) + '%');
  else if (k === 'competition') s += line(FL('proc_single_sh'), fmtF('proc_single_sh', f.proc_single_sh)) + line('1 − доля', fmtN(v * 100, 1) + '%');
  else if (k === 'online_leakage') s += line('Маркетплейсы', fmtF('sh_Маркетплейсы', f['sh_Маркетплейсы'])) + line('Общепит', fmtF('sh_Общественное питание', f['sh_Общественное питание'])) + line('Маркетплейсы / (маркетплейсы + общепит)', v == null ? 'н/д' : fmtN(v * 100, 1) + '%');
  else if (k === 'budget_dep') s += line(FL('grants_pc') + ' — ' + fmtF('grants_pc', f.grants_pc), pc('grants_pc') + ' процентиль') + line(FL('emp_sh_budget') + ' — ' + fmtF('emp_sh_budget', f.emp_sh_budget), f.emp_sh_budget == null ? 'н/д' : pc('emp_sh_budget') + ' процентиль') + line('Среднее процентилей', fmtN(v, 1));
  else if (k === 'activity') s += ['spend_total', 'wage', 'emp_per_1000'].map(q => line(FL(q) + ' — ' + fmtF(q, f[q]), f[q] == null ? 'н/д' : pc(q) + ' процентиль')).join('') + line('Среднее процентилей', v == null ? 'н/д' : fmtN(v, 1));
  else if (k === 'demo_resilience') s += line('Рождаемость — ' + fmtF('birth_rate', f.birth_rate), f.birth_rate == null ? 'н/д' : pc('birth_rate') + ' процентиль') + line('Смертность — ' + fmtF('death_rate', f.death_rate) + ' (чем ниже, тем лучше)', f.death_rate == null ? 'н/д' : pc('death_rate', true) + ' процентиль') + line('Миграция — ' + fmtF('migr_rate', f.migr_rate), f.migr_rate == null ? 'н/д' : pc('migr_rate') + ' процентиль') + line('Среднее процентилей', v == null ? 'н/д' : fmtN(v, 1));
  else s += line('Значение индекса', fmtIxRaw(k, v));
  s += line('Место среди ' + n + ' МО', fmtPctile(x.mp[k])) + `<div class="muted">${esc(d.interp)}</div>`;
  return s;
}
function uncBlock(i){
  const x = N[i]; if (!x.p) return '';
  const pr = x.p.map((p, c) => [c, p]).sort((a, b) => b[1] - a[1]).slice(0, 3), u = UNC(i);
  return `<section><h4>${u ? 'Пограничный район: тип определён неуверенно' : 'Тип определён уверенно'}</h4>
    <div class="hint">Вероятность типа по модели случайного леса; силуэт ${fmtN(x.typ, 2)}, устойчивость в бутстрепе ${fmtN(x.stab, 2)}.</div>
    <div class="probs">${pr.map(([c, p]) => `<span style="display:flex;gap:7px;align-items:center;min-width:0"><span class="sw" style="--c:${COLV(c)}"></span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(typeName(c))}">${esc(typeName(c))}</span></span><span class="hbar"><i style="width:${p * 100}%;background:${COLV(c)}"></i></span><span class="num mono">${fmtN(p * 100)}%</span>`).join('')}</div></section>`;
}
const CMP_F = ['spend_total', 'wage', 'emp_per_1000', 'grants_pc', 'emp_sh_budget', 'emp_sh_industry', 'proc_pc', 'proc_local_sh', 'proc_single_sh', 'sh_Маркетплейсы', 'sh_Общественное питание', 'migr_rate', 'birth_rate', 'death_rate', 'urban_share'];
function benchTable(i, j){
  if (j < 0) return '';
  const a = N[i], b = N[j];
  const rowsM = Object.entries(D.metrics).filter(([k, d]) => d.sense !== 0).map(([k, d]) => { const dv = a.mp[k] == null || b.mp[k] == null ? null : a.mp[k] - b.mp[k]; const better = dv != null && d.sense * dv > 5, worse = dv != null && d.sense * dv < -5;
    return `<tr><td>${esc(d.label)}</td><td class="n">${fmtPctileShort(a.mp[k])}</td><td class="n">${fmtPctileShort(b.mp[k])}</td><td class="n">${dv == null ? '—' : (dv > 0 ? '+' : '') + fmtN(dv)}${better ? '<span class="mark best">выше по смыслу</span>' : worse ? '<span class="mark worst">ниже по смыслу</span>' : ''}</td></tr>`; }).join('');
  const rowsF = CMP_F.filter(k => D.feats[k]).map(k => { const u = D.feats[k][1], va = a.f[k], vb = b.f[k];
    const dv = va == null || vb == null ? null : (u === '%' ? (va - vb) * 100 : va - vb);
    return `<tr><td>${esc(FL(k))}</td><td class="n">${fmtF(k, va)}</td><td class="n">${fmtF(k, vb)}</td><td class="n">${dv == null ? '—' : (dv > 0 ? '+' : '') + fmtN(dv, Math.abs(dv) < 10 ? 1 : 0) + (u === '%' ? ' п.п.' : '')}</td></tr>`; }).join('');
  return `<div class="tbox" style="margin-top:6px;max-height:420px"><table class="ktab"><thead><tr><th>Индекс, процентиль</th><th class="n">${esc(a.s)}</th><th class="n">${esc(b.s)}</th><th class="n">Δ</th></tr></thead><tbody>${rowsM}
    <tr class="grp"><th colspan="4">Показатели</th></tr>${rowsF}</tbody></table></div><div class="hint">Разница больше 5 процентилей с учётом направления индекса; нейтральные индексы не оцениваются.</div>`;
}
function spark(vals, labels){
  const v = vals.map((x, i) => [i, x]).filter(p => p[1] != null); if (v.length < 3) return '<div class="hint">Ряда безналичных трат СберИндекса для этого МО нет в данных.</div>';
  const W = 380, H = 96, P = 6, ys = v.map(p => p[1]), lo = Math.min(...ys), hi = Math.max(...ys);
  const X = i => P + 40 + i / (vals.length - 1) * (W - 2 * P - 40), Y = y => H - 18 - (y - lo) / Math.max(1, hi - lo) * (H - 30);
  let d = '', pen = false; vals.forEach((y, i) => { if (y == null) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(y).toFixed(1); pen = true; });
  const last = v[v.length - 1], miss = vals.length - v.length;
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" style="max-width:${W}px" role="img" aria-label="безналичные траты на жителя по месяцам, ${labels[0]} — ${labels[labels.length - 1]}">
    <line class="gl" x1="${X(0)}" x2="${X(vals.length - 1)}" y1="${Y(hi)}" y2="${Y(hi)}"/><line class="gl" x1="${X(0)}" x2="${X(vals.length - 1)}" y1="${Y(lo)}" y2="${Y(lo)}"/>
    <text class="tk" x="${X(0) - 6}" y="${Y(hi) + 4}" text-anchor="end">${fmtN(hi)}</text><text class="tk" x="${X(0) - 6}" y="${Y(lo) + 4}" text-anchor="end">${fmtN(lo)}</text>
    <path d="${d}" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-linejoin="round"/><circle cx="${X(last[0])}" cy="${Y(last[1])}" r="3" fill="var(--ink)"/>
    <text class="tk" x="${X(0)}" y="${H - 2}">${labels[0]}</text><text class="tk" x="${X(vals.length - 1)}" y="${H - 2}" text-anchor="end">${labels[labels.length - 1]}</text></svg>
    <div class="hint">Последний месяц (${labels[last[0]]}): <span class="mono" style="color:var(--ink)">${fmtN(last[1])} ₽</span>${miss ? ` · пропусков: ${miss} (линия прерывается)` : ''}</div>`;
}

/* ---------- запуск, потеря контекста, резервный 2D ---------- */
function sceneLost(scene){
  if (!scene.alive) return; hideTip(); MAPST.hoverMO = null; MAPST.hoverEdge = null; MAPVS.scenes.forEach(s => s.destroy()); MAPVS.scenes = [];
  startFallback('Контекст WebGL потерян (например, из-за нехватки памяти GPU).');
}
function startFallback(reason){
  $('#fbNote').hidden = false; resetUiBoxes();
  $('#fbNote').innerHTML = `<b>2D-режим.</b> ${esc(reason)} Наклон и объёмные дуги недоступны; данные, выбор, связи, таблицы и рейтинги работают.${GL2 && !FORCE_2D ? ' <button class="link" type="button" id="retry3d">Попробовать 3D снова</button>' : ''}`;
  if ($('#retry3d')) $('#retry3d').onclick = () => { MAPVS.scenes.forEach(s => s.destroy()); MAPVS.scenes = []; $('#fbNote').hidden = true; startDeck(); };
  $('#dimBtn').disabled = true; $('#dimBtn').title = '3D недоступен в 2D-режиме';
  if (MAPST.view === 'split') setView('map');
  const s = new LeafletScene($('#sceneA')); MAPVS.scenes = [s]; syncMotionCtl(); const p = MAPVS.pending; fitView(p ? p.bounds : REGION_BOUNDS, {pad: p ? p.pad : 24, maxZoom: p ? p.maxZoom : 10.5, pts: p ? p.pts : REGION_PTS, duration: 0}); mapChanged(); panel();
}
function startDeck(){
  try { const s = new DeckScene($('#sceneA'), 'main'); MAPVS.scenes = [s]; $('#dimBtn').disabled = false; } catch (err) { console.warn(err); startFallback('Не удалось создать 3D-сцену.'); return; }
  syncMotionCtl(); const p = MAPVS.pending; fitView(p ? p.bounds : REGION_BOUNDS, {pad: p ? p.pad : 24, maxZoom: p ? p.maxZoom : 10.5, pts: p ? p.pts : REGION_PTS, duration: 0}); mapChanged(); panel();
}
let mapStarted = false;
function mapInit(){
  syncMotionCtl(); updateAttribution(); computeEdges(); legend(); panel(); renderEdgeTable(); $('#qLbl').textContent = D.quarters[MAPST.qi];
  if ('IntersectionObserver' in window) new IntersectionObserver(es => { mapOnScreen = es[0].isIntersecting; mapAnimSync(); }).observe($('#mapwrap'));
}
onTab('map', () => FONTS_READY.then(() => whenSized($('#sceneA'), () => {
  if (!mapStarted) { mapStarted = true; if (!GL2 || FORCE_2D) startFallback(FORCE_2D ? 'Включён параметром адреса render=2d.' : 'Браузер не поддерживает WebGL2.'); else startDeck(); }
  if (group) $('#groupInfo').innerHTML = `Подсвечено: ${group.size} МО <button class="link" type="button" id="groupClr">сбросить</button>`;
  if ($('#groupClr')) $('#groupClr').onclick = clearGroup;
  mapChanged(false); if (sel == null) panel(); renderRank();
})));
onResize($('#mapwrap'), () => { MAPVS.scenes.forEach(s => s.resized && s.resized()); scheduleLabels(); });
THEME_HOOKS.push(() => { readPalette(); if (MAPST.basemap) BASEMAP.layer = basemapLayer(); MAPST.ver++; MAPVS.scenes.forEach(s => s.retheme && s.retheme()); legend(); renderScenes(); renderRank(); });
