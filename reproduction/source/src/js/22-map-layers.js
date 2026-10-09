/* ==========================================================================
   Карта: состояние, раскраска, связи и построение слоёв deck.gl
   ========================================================================== */
const MAPST = {
  mode: 'type', qi: D.quarters.length - 1, layer: 'backbone', thrP: 0, density: '30', dirFilter: 'all', selAll: false,
  onlySel: false, motion: !RM.matches, glow: true, unc: true, basemap: false,
  hoverMO: null, hoverEdge: null, pinned: null, related: new Set(), edges: [], ctx: [], stats: null,
  view: 'map', selT0: 0, pinT0: -1e9, clock: 0, ver: 0,
};
const MACRO_SLOT = [6, 3, 2];
const UNC = i => N[i].typ < 0 || N[i].stab < .5 || (N[i].p && Math.max(...N[i].p) < .5);

/* ---------- значения раскраски ---------- */
function valueOf(i, mode){
  if (mode === 'stab') return N[i].stab;
  if (mode.startsWith('m:')) return N[i].mp[mode.slice(2)];
  if (mode.startsWith('f:')) return N[i].f[mode.slice(2)];
  return null;
}
const SCALE_CACHE = {};
function scaleFor(mode){
  if (SCALE_CACHE[mode]) return SCALE_CACHE[mode];
  const vals = N.map((_, i) => valueOf(i, mode)).filter(v => v != null);
  let sc;
  if (mode === 'stab') sc = {kind: 'seq', t: v => v, lo: 0, hi: 1};
  else if (mode.startsWith('m:')) sc = {kind: 'seq', t: v => v / 100, lo: 0, hi: 100};
  else {
    const lo = Math.min(...vals), hi = Math.max(...vals);
    if (lo < 0 && hi > 0) { const M = Math.max(-lo, hi);          // симметрично вокруг нуля; степень 0,6 усиливает различие малых отклонений, легенда строится той же функцией
      sc = {kind: 'div', t: v => { const x = Math.max(-1, Math.min(1, v / M)); return Math.sign(x) * Math.abs(x) ** .6; }, lo: -M, hi: M, M, min: lo, max: hi}; }
    else { const s = vals.slice().sort((a, b) => a - b);
      sc = {kind: 'rank', t: v => { let a = 0, b = s.length; while (a < b) { const m = (a + b) >> 1; s[m] < v ? a = m + 1 : b = m; } return a / Math.max(1, s.length - 1); }, lo, hi}; }
  }
  sc.missing = N.length - vals.length;
  return SCALE_CACHE[mode] = sc;
}
function themeRGB(i, mode, role){
  if (role === 'mig') mode = 'f:migr_rate';
  if (mode === 'type') return {rgb: PAL.types[tslot(N[i].c)], a: PAL.typeA};
  if (mode === 'quarter') return {rgb: PAL.types[tslot(N[i].q[MAPST.qi])], a: PAL.typeA};
  if (mode === 'macro') return {rgb: PAL.types[MACRO_SLOT[N[i].macro % 3]], a: PAL.typeA};
  const v = valueOf(i, mode); if (v == null) return null;
  const sc = scaleFor(mode);
  if (sc.kind === 'div') { const t = sc.t(v); return {rgb: t < 0 ? lerp3(PAL.migZero, PAL.migNeg, -t) : lerp3(PAL.migZero, PAL.migPos, t), a: .94}; }
  return {rgb: lerp3(PAL.seq0, PAL.seq1, sc.t(v)), a: .92};
}
/* приглушённый контекст: при закреплённой связи — всё, кроме её двух концов (и выбранного МО); иначе — не связанные с выбранным */
function dimmed(i){ const pe = MAPST.pinned && MAPST.pinned.e;
  return pe ? i !== pe[0] && i !== pe[1] && i !== sel : sel != null && i !== sel && !MAPST.related.has(i); }
function fillFor(i, role){
  const c = themeRGB(i, MAPST.mode, role); if (!c) return [0, 0, 0, 0];
  let a = c.a;
  if (dimmed(i)) a *= .5;
  else if (sel == null && !MAPST.pinned && group && !group.has(i)) a *= .35;
  if (MAPST.hoverMO === i && i !== sel) a = Math.min(1, a + .08);
  return [...c.rgb, Math.round(a * 255)];
}

/* ---------- связи ---------- */
const GEOM_CACHE = new Map();
function geomFor(e, s0, s1, hub, lift){ const k = s0 + '>' + s1 + '|' + lift.toFixed(2) + '|' + hub.toFixed(2);
  if (!GEOM_CACHE.has(k)) GEOM_CACHE.set(k, arcGeom(CENTER[s0], CENTER[s1], hub, lift)); return GEOM_CACHE.get(k); }
function computeEdges(){
  MAPST.related = new Set(); MAPST.edges = []; MAPST.ctx = []; MAPST.stats = null;
  const lay = MAPST.layer; if (lay === 'none' || !D.layers[lay]) { $('#thrLbl').textContent = ''; return; }
  let E = D.layers[lay];
  if (lay === 'backbone' && sel != null) {      // у выбранного МО — все его связи итоговой сети (как в исходной версии)
    const seen = new Set(E.map(e => Math.min(e[0], e[1]) + '-' + Math.max(e[0], e[1])));
    E = E.concat(D.layers.fused.filter(e => (e[0] === sel || e[1] === sel) && !seen.has(Math.min(e[0], e[1]) + '-' + Math.max(e[0], e[1]))));
  }
  const val = e => lay === 'flow_rub' ? Math.log10(e[2]) : e[2];
  const W = E.map(val).sort((a, b) => a - b), thr = W[Math.floor(MAPST.thrP / 100 * (W.length - 1))], wmin = W[0], wmax = W[W.length - 1];
  $('#thrLbl').textContent = lay === 'flow_rub' ? fmtN(10 ** thr / 1e6, 1) + ' млн ₽' : fmtN(thr, 2);
  const dir = isDir(lay), deg = {};
  E.forEach(e => { deg[e[0]] = (deg[e[0]] || 0) + 1; deg[e[1]] = (deg[e[1]] || 0) + 1; });
  const mk = (e, touches) => { const [s0, s1] = dir || e[0] < e[1] ? [e[0], e[1]] : [e[1], e[0]];
    const hub = Math.max(deg[s0] || 0, deg[s1] || 0) > 6 ? (((s0 * 31 + s1 * 17) % 5) - 2) * .25 : 0;
    const w = val(e), t = Math.sqrt(Math.max(0, (w - wmin) / Math.max(1e-9, wmax - wmin)));
    return {e, w, t, s0, s1, hub, dir, lay, touches}; };
  const above = E.filter(e => val(e) >= thr).sort((a, b) => b[2] - a[2]);
  const cap = MAPST.density === 'all' ? Infinity : +MAPST.density;
  let overview = above.slice(0, cap).map(e => mk(e, false));
  let touch = [], selTotal = 0;
  if (sel != null) {
    let T = E.filter(e => e[0] === sel || e[1] === sel);
    if (dir && MAPST.dirFilter === 'out') T = T.filter(e => e[0] === sel);
    if (dir && MAPST.dirFilter === 'in') T = T.filter(e => e[1] === sel);
    T.sort((a, b) => b[2] - a[2]); selTotal = T.length;
    touch = (MAPST.selAll ? T : T.slice(0, 12)).map(e => mk(e, true));
    touch.forEach(it => { MAPST.related.add(it.e[0]); MAPST.related.add(it.e[1]); });
    const tk = new Set(touch.map(it => it.e));
    overview = MAPST.onlySel ? [] : overview.filter(it => !tk.has(it.e));
  }
  if (MAPST.pinned && MAPST.pinned.lay === lay && !touch.some(it => it.e === MAPST.pinned.e) && !overview.some(it => it.e === MAPST.pinned.e)) touch.push(mk(MAPST.pinned.e, true));
  if (MAPST.pinned && MAPST.pinned.lay !== lay) MAPST.pinned = null;
  const lift = it => sel != null && it.touches ? 1 : .6;
  [...overview, ...touch].forEach(it => { it.g = geomFor(it.e, it.s0, it.s1, it.hub, lift(it)); });
  MAPST.ctx = overview.sort((a, b) => a.w - b.w);                // слабые позади
  MAPST.edges = touch.sort((a, b) => a.w - b.w);
  MAPST.stats = {lay, total: E.length, layerTotal: D.layers[lay].length, extra: E.length - D.layers[lay].length, above: above.length, shown: overview.length + touch.length, overview: overview.length, cap, selTotal, selShown: touch.length};
}
function animSet(){
  if (!MAPST.stats) return [];
  if (MAPST.pinned) { const it = [...MAPST.edges, ...MAPST.ctx].find(x => x.e === MAPST.pinned.e); return it ? [it] : []; }
  const src = sel != null ? MAPST.edges : MAPST.ctx;
  return src.slice().sort((a, b) => b.w - a.w).slice(0, sel != null ? 12 : 10);
}

/* ---------- построение слоёв одной сцены ---------- */
const MASKX = new DK.MaskExtension(), DASHX = new DK.PathStyleExtension({dash: true});
function selRings(){ return sel == null ? [] : RINGS[sel].map(r => ({path: r})); }
function glowWidth(scene){ if (sel == null) return 8; const vp = scene.viewport(); if (!vp) return 8;
  const [[w, s], [e, nn]] = BBOX[sel], a = vp.project([w, s]), b = vp.project([e, nn]);
  const k = Math.min(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1])); return Math.max(3, Math.min(PAL.dark ? 12 : 10, k * .16)); }
function buildLayers(scene, now){
  const role = scene.role, L = [], id = s => role + '-' + s, ver = MAPST.ver + '|' + role;
  const lineA = PAL.dark ? 1 : 1;
  if (MAPST.basemap && role === 'main' && BASEMAP.layer) L.push(BASEMAP.layer);
  if (MAPVS.vs.pitch > 1) { const zb = Math.round(MAPVS.vs.zoom * 4) / 4, h = slabMeters(zb);
    L.push(new DK.SolidPolygonLayer({id: id('slab'), data: SLAB_POLY, getPolygon: d => d.polygon.map(c => [c[0], c[1], -h]), extruded: true, getElevation: h, wireframe: false,
      getFillColor: PAL.slab, material: false, updateTriggers: {getFillColor: ver, getPolygon: zb, getElevation: zb}})); }
  L.push(new DK.SolidPolygonLayer({id: id('base'), data: OUTLINE_POLY, getPolygon: d => d.polygon, getFillColor: PAL.geo, updateTriggers: {getFillColor: ver}}));
  L.push(new DK.GeoJsonLayer({id: id('fill'), data: FEAT, filled: true, stroked: false, pickable: true,
    getFillColor: f => fillFor(f.properties.i, role), updateTriggers: {getFillColor: [ver, sel, MAPST.hoverMO, MAPST.mode, MAPST.qi]}}));
  L.push(new DK.PathLayer({id: id('seams'), data: GEO.seams, getPath: d => d, getColor: PAL.seam, getWidth: .7, widthUnits: 'pixels', jointRounded: true, updateTriggers: {getColor: ver}}));
  L.push(new DK.PathLayer({id: id('outline'), data: GEO.outline, getPath: d => d, getColor: PAL.outline, getWidth: 1.1, widthUnits: 'pixels', jointRounded: true, updateTriggers: {getColor: ver}}));
  /* н/д: без заливки (видна основа) + пунктир по границе МО */
  const ndMode = role === 'mig' ? 'f:migr_rate' : MAPST.mode;
  if (!['type', 'quarter', 'macro'].includes(ndMode)) {
    const nd = []; for (let i = 0; i < n; i++) if (valueOf(i, ndMode) == null) RINGS[i].forEach(r => nd.push({path: r}));
    if (nd.length) L.push(new DK.PathLayer({id: id('nd'), data: nd, getPath: d => d.path, getColor: PAL.muted, getWidth: 1.2, widthUnits: 'pixels', getDashArray: [4, 3], dashJustified: true, extensions: [DASHX], updateTriggers: {getColor: ver}}));
  }
  if (MAPST.unc && role === 'main' && ['type', 'quarter'].includes(MAPST.mode)) {
    const un = []; for (let i = 0; i < n; i++) if (UNC(i) && i !== sel) RINGS[i].forEach(r => un.push({path: r}));
    L.push(new DK.PathLayer({id: id('unc'), data: un, getPath: d => d.path, getColor: [...PAL.ink2.slice(0, 3), 150], getWidth: 1, widthUnits: 'pixels', getDashArray: [3, 3], dashJustified: true, extensions: [DASHX], updateTriggers: {getColor: ver}}));
  }
  if (group && sel == null) {
    const gr = []; group.forEach(i => RINGS[i].forEach(r => gr.push({path: r})));
    L.push(new DK.PathLayer({id: id('group'), data: gr, getPath: d => d.path, getColor: [...PAL.pearlEdge.slice(0, 3), PAL.dark ? 200 : 210], getWidth: 1.2, widthUnits: 'pixels', jointRounded: true, updateTriggers: {getColor: ver}}));
  }
  if (MAPST.hoverMO != null && MAPST.hoverMO !== sel) L.push(new DK.PathLayer({id: id('hover-' + MAPST.hoverMO), data: RINGS[MAPST.hoverMO].map(r => ({path: r})), getPath: d => d.path, getColor: [...PAL.ink2.slice(0, 3), 190], getWidth: 1.2, widthUnits: 'pixels', jointRounded: true}));
  /* выбор: вуаль + мягкий внутренний свет по маске той же территории + тонкая кромка */
  if (sel != null) {
    const fa = RM.matches ? 1 : Math.min(1, Math.max(0, (now - MAPST.selT0) / 300));
    const gw = glowWidth(scene), rings = selRings();
    const sk = '-' + sel;                                       // отдельные id на каждый выбор: свежие буферы, без «хвостов» прошлого полигона
    L.push(new DK.GeoJsonLayer({id: id('selmask' + sk), data: [FEAT_BY[sel]], operation: 'mask'}));
    L.push(new DK.GeoJsonLayer({id: id('selveil' + sk), data: [FEAT_BY[sel]], filled: true, stroked: false, getFillColor: [...PAL.pearl.slice(0, 3), Math.round((PAL.dark ? .13 : .07) * 255)], opacity: fa, updateTriggers: {getFillColor: ver}}));
    /* шесть узких ступеней с малой прозрачностью складываются в плавный градиент к кромке (без видимых полос) */
    [1, .84, .68, .52, .36, .2].forEach((k, j) => L.push(new DK.PathLayer({id: id('selglow' + j + sk), data: rings, getPath: d => d.path, getColor: [...PAL.pearl.slice(0, 3), Math.round((PAL.dark ? .075 : .085) * 255)],
      getWidth: gw * 2 * k, widthUnits: 'pixels', jointRounded: true, extensions: [MASKX], maskId: id('selmask' + sk), opacity: fa, updateTriggers: {getColor: ver, getWidth: gw}})));
    L.push(new DK.PathLayer({id: id('seledge' + sk), data: rings, getPath: d => d.path, getColor: [...PAL.pearlEdge.slice(0, 3), PAL.dark ? 235 : 240], getWidth: PAL.dark ? 1.4 : 1.6, widthUnits: 'pixels', jointRounded: true, opacity: fa, updateTriggers: {getColor: ver}}));
  }
  /* связи (только основная сцена) */
  if (role === 'main' && MAPST.stats) {
    const fam = (LMETA[MAPST.layer] || {}).fam || 'sim', base = PAL.fam[fam], tr = PAL.trail[fam];
    const ctxA = it => sel != null ? .07 : (.28 + .5 * it.t) * (PAL.dark ? 1 : 1.05);
    L.push(new DK.PathLayer({id: id('ctx'), data: MAPST.ctx, getPath: it => it.g.path, getColor: it => [...base, Math.round(Math.min(.85, ctxA(it)) * 255)],
      getWidth: it => .6 + .7 * it.t, widthUnits: 'pixels', jointRounded: true, capRounded: true, pickable: true, billboard: false,
      updateTriggers: {getColor: [ver, sel, fam], getPath: MAPST.ver}}));
    const pinE = MAPST.pinned && MAPST.pinned.e;
    L.push(new DK.PathLayer({id: id('edges'), data: MAPST.edges, getPath: it => it.g.path,
      getColor: it => [...base, Math.round((pinE ? (it.e === pinE ? .98 : .22) : .5 + .4 * it.t) * 255)],
      getWidth: it => it.e === pinE ? 1.8 : .8 + .7 * it.t, widthUnits: 'pixels', jointRounded: true, capRounded: true, pickable: true,
      updateTriggers: {getColor: [ver, fam, pinE], getWidth: pinE, getPath: MAPST.ver}}));
    const hov = MAPST.hoverEdge;
    if (hov && hov.g) L.push(new DK.PathLayer({id: id('hovedge'), data: [hov], getPath: it => it.g.path, getColor: [...base, 245], getWidth: 1.8, widthUnits: 'pixels', capRounded: true}));
    const A = animSet();
    if (MAPST.stats && isDir(MAPST.layer)) {
      /* маленькая стрелка направления у выбранных/закреплённых связей — видна и на паузе */
      const arr = (pinE ? A : (sel != null ? MAPST.edges.slice(-12) : [])).map(it => ({path: arrowPath(it.g), it}));
      if (arr.length) L.push(new DK.PathLayer({id: id('arrows'), data: arr, getPath: d => d.path, getColor: [...base, 235], getWidth: 1.3, widthUnits: 'pixels', capRounded: true, jointRounded: true, updateTriggers: {getColor: ver}}));
      if (MAPST.motion && A.length) {                                  // при reduced motion флажок по умолчанию снят; включённый вручную — работает
        const period = 2800, tt = pinE ? Math.max(0, now - MAPST.pinT0) : now;
        const cur = ((tt % period) / period) * 1.45 - .05;
        L.push(new DK.TripsLayer({id: id('trails'), data: A, getPath: it => it.g.path, getTimestamps: it => it.g.ts, getColor: [...tr, 255],
          currentTime: cur, trailLength: .34, fadeTrail: true, getWidth: it => it.e === pinE ? 3 : 2.2, widthUnits: 'pixels', capRounded: true, jointRounded: true,
          updateTriggers: {getColor: ver, getPath: MAPST.ver, getWidth: pinE}}));
      }
    } else if (MAPST.stats && MAPST.glow && A.length) {
      /* ненаправленный слой: мягкое изменение яркости всей связи, без направления */
      const ph = MAPST.motion ? .5 + .5 * Math.sin(now / 900) : .6;
      L.push(new DK.PathLayer({id: id('soft'), data: A, getPath: it => it.g.path, getColor: [...tr, Math.round((.28 + .42 * ph) * 255)],
        getWidth: it => (pinE && it.e === pinE ? 3.2 : 2.6), widthUnits: 'pixels', capRounded: true, jointRounded: true, updateTriggers: {getColor: [ver, Math.round(ph * 40)], getPath: MAPST.ver}}));
    }
    if (pinE) {
      const it = [...MAPST.edges, ...MAPST.ctx].find(x => x.e === pinE);
      if (it) { const end = [CENTER[it.s0], CENTER[it.s1]];
        const k = Math.max(0, Math.min(1, ((now - MAPST.pinT0) - 2800 * .72) / 600));
        L.push(new DK.ScatterplotLayer({id: id('ends'), data: end.map((p, j) => ({p, j})), getPosition: d => d.p, stroked: true, filled: false, radiusUnits: 'pixels',
          getRadius: d => d.j === 1 && k > 0 && k < 1 && !RM.matches ? 8 + 10 * k : 8, getLineColor: d => [...PAL.pearlEdge.slice(0, 3), d.j === 1 && k > 0 && k < 1 ? Math.round(240 * (1 - k)) + 15 : 230],
          lineWidthUnits: 'pixels', getLineWidth: 1.6, updateTriggers: {getRadius: Math.round(k * 30), getLineColor: [ver, Math.round(k * 30)]}}));
      }
    }
  }
  /* центры МО: маленький знак цвета типа с тонкой оболочкой; выбор — жемчужное кольцо */
  const nodeA = i => dimmed(i) ? 110 : 255;
  L.push(new DK.ScatterplotLayer({id: id('nodes'), data: N.map((x, i) => i).filter(i => CENTER[i]), getPosition: i => CENTER[i], radiusUnits: 'pixels',
    getRadius: i => N[i].kind === 'ГО' ? 3.6 : 2.8, getFillColor: i => [...PAL.types[tslot(N[i].c)], nodeA(i)], stroked: true, getLineColor: i => [...PAL.nodeLine.slice(0, 3), nodeA(i)],
    lineWidthUnits: 'pixels', getLineWidth: 1, updateTriggers: {getFillColor: [ver, sel], getLineColor: [ver, sel]}}));
  L.push(new DK.ScatterplotLayer({id: id('nodehit'), data: N.map((x, i) => i).filter(i => CENTER[i]), getPosition: i => CENTER[i], radiusUnits: 'pixels', getRadius: 10, getFillColor: [0, 0, 0, 1], pickable: true}));
  if (sel != null && CENTER[sel]) L.push(new DK.ScatterplotLayer({id: id('selring'), data: [sel], getPosition: i => CENTER[i], radiusUnits: 'pixels', getRadius: 7.5, filled: false, stroked: true,
    getLineColor: [...PAL.pearlEdge.slice(0, 3), 240], lineWidthUnits: 'pixels', getLineWidth: 1.4, updateTriggers: {getLineColor: ver}}));
  return L;
}

/* ---------- отрисовка всех сцен ---------- */
function renderScenes(){
  const now = performance.now(); MAPST.clock = now;
  MAPVS.scenes.forEach(s => { if (!s.alive) return; if (s.kind === 'leaflet') s.render(now); else if (s.deck) s.deck.setProps({layers: buildLayers(s, now)}); });
}

/* ---------- единый планировщик движения: пауза вне вкладки/экрана, при reduced motion ---------- */
let mapRaf = null, mapOnScreen = true;
function mapNeedsFrames(){
  if (activeTab !== 'map' || document.hidden || !mapOnScreen || MAPST.view === 'matrix' || !MAPVS.scenes.length || MAPVS.scenes[0].kind === 'leaflet') return false;
  const fading = sel != null && performance.now() - MAPST.selT0 < 400;
  const moving = MAPST.stats && animSet().length > 0 && (isDir(MAPST.layer) ? MAPST.motion : (MAPST.glow && MAPST.motion));
  const pinning = MAPST.pinned && performance.now() - MAPST.pinT0 < 4200;
  return fading || moving || pinning;
}
function mapTick(){ mapRaf = null; if (!mapNeedsFrames()) { renderScenes(); return; } renderScenes(); mapRaf = requestAnimationFrame(mapTick); }
function mapAnimSync(){ if (mapNeedsFrames()) { if (!mapRaf) mapRaf = requestAnimationFrame(mapTick); } else { if (mapRaf) cancelAnimationFrame(mapRaf); mapRaf = null; renderScenes(); } }
document.addEventListener('visibilitychange', mapAnimSync);
RM.addEventListener && RM.addEventListener('change', () => { if (RM.matches) { MAPST.motion = false; const c = $('#motionChk'); if (c) c.checked = false; } mapAnimSync(); });

/* ---------- подложка OpenStreetMap (необязательная, нужна сеть) ---------- */
const BASEMAP = {layer: null, errors: 0};
function basemapLayer(){
  BASEMAP.errors = 0;
  return new DK.TileLayer({id: 'osm', data: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', minZoom: 0, maxZoom: 13, tileSize: 256, opacity: PAL.dark ? .35 : .55,
    onTileError: () => { if (++BASEMAP.errors === 3) { MAPST.basemap = false; BASEMAP.layer = null; const c = $('#osm'); if (c) c.checked = false; updateAttribution();
      notify($('#osm') && $('#osm').closest('label'), 'Подложку OpenStreetMap загрузить не удалось (нет сети или сервер недоступен). Карта, данные и выбор работают без неё.', {kind: 'warn'}); renderScenes(); } },
    renderSubLayers: p => { const {boundingBox} = p.tile; return new DK.BitmapLayer(p, {data: null, image: p.data, bounds: [boundingBox[0][0], boundingBox[0][1], boundingBox[1][0], boundingBox[1][1]], desaturate: .85, tintColor: PAL.dark ? [150, 165, 175] : [255, 255, 255]}); }});
}
