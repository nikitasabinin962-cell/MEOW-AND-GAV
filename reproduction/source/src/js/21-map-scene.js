/* ==========================================================================
   2. Карта и сеть — 3D-сцена на deck.gl (WebGL2)
   Одна фабрика сцены для основной карты и сопоставления «Сеть и миграция».
   Общие: D.geo (только чтение), производный контур/швы GEO, проекция
   Web Mercator, выбор, маркеры, подписи, камера. Различается только
   тематическая раскраска (тип/показатель ↔ миграционный прирост).
   Высота дуг — способ раскладки связей, не величина.
   ========================================================================== */
const DK = window.deck;
const GL2 = (() => { try { return !!document.createElement('canvas').getContext('webgl2'); } catch (e) { return false; } })();
const FORCE_2D = /render=2d/.test(location.search);

/* ---------- геометрия: единый адаптер неизменного D.geo ---------- */
const FEAT = D.geo.features.map(f => ({type: 'Feature', geometry: f.geometry, properties: {i: f.properties.i}}));
const FEAT_BY = new Array(n); FEAT.forEach(f => FEAT_BY[f.properties.i] = f);
const CENTER = new Array(n); D.geo.features.forEach(f => CENTER[f.properties.i] = [f.properties.lon, f.properties.lat]);
const RINGS = new Array(n).fill(null).map(() => []);       // кольца МО (внешние и отверстия) для контуров выбора
const BBOX = new Array(n);
FEAT.forEach(f => { const i = f.properties.i, g = f.geometry, polys = g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates];
  let w = 1e9, s = 1e9, e = -1e9, nn = -1e9;
  polys.forEach(p => p.forEach(r => { RINGS[i].push(r); r.forEach(c => { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); nn = Math.max(nn, c[1]); }); }));
  BBOX[i] = [[w, s], [e, nn]]; });
const REGION_BOUNDS = (() => { let w = 1e9, s = 1e9, e = -1e9, nn = -1e9; GEO.outline[0].forEach(c => { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); nn = Math.max(nn, c[1]); }); return [[w, s], [e, nn]]; })();
const OUTLINE_POLY = [{polygon: GEO.outline[0]}];
/* платформа: одинаковая тонкая толщина под регионом (оформление наклонной сцены, не величина); верх на z=0, низ на −SLAB м */
const SLAB_PX = 5, SLAB_POLY = [{polygon: GEO.outline[0]}];
const slabMeters = z => SLAB_PX * 40075016 * Math.cos(54.5 * Math.PI / 180) / (512 * 2 ** z);   // постоянные ~5 px экрана при любом масштабе

/* ---------- цвета: CSS-токены → RGBA для WebGL ---------- */
function rgbArr(c, a = 1){ const [r, g, b] = hex2rgb(cv(c)); return [r, g, b, Math.round(a * 255)]; }
const PAL = {};
function readPalette(){
  const dark = isDark();
  Object.assign(PAL, {
    dark,
    bg: rgbArr('--map-bg'), geo: rgbArr('--geo'),
    seam: dark ? [16, 23, 29, 235] : [255, 255, 255, 240],
    outline: dark ? rgbArr('#7D93A3', .95) : rgbArr('#7E95A3', .95),
    ink: rgbArr('--ink'), ink2: rgbArr('--ink2'), muted: rgbArr('--muted'),
    pearl: rgbArr('--pearl'), pearlEdge: rgbArr('--pearl-edge'),
    types: [0, 1, 2, 3, 4, 5, 6].map(k => hex2rgb(css('--c' + k))),
    fam: {proc: hex2rgb(css('--flow-proc')), model: hex2rgb(css('--flow-model')), sim: hex2rgb(css('--flow-sim'))},
    trail: {proc: hex2rgb(css('--trail-proc')), model: hex2rgb(css('--trail-model')), sim: hex2rgb(css('--trail-sim'))},
    seq0: hex2rgb(css('--seq0')), seq1: hex2rgb(css('--seq1')),
    migNeg: hex2rgb(css('--mig-neg')), migPos: hex2rgb(css('--mig-pos')), migZero: hex2rgb(css('--mig-zero')),
    halo: dark ? [16, 23, 29, 230] : [242, 245, 246, 235],
    slab: dark ? [11, 16, 20, 255] : [203, 213, 220, 255],
    typeA: dark ? .44 : .38, nodeLine: dark ? [18, 27, 34, 245] : [255, 255, 255, 250],
  });
}
readPalette();
const lerp3 = (a, b, t) => [0, 1, 2].map(k => Math.round(a[k] + (b[k] - a[k]) * Math.max(0, Math.min(1, t))));

/* ---------- подписи: собственная раскладка с измерением текста и приоритетами ---------- */
const MEASURE = document.createElement('canvas').getContext('2d');
const TW = {};
function textW(t, weight){ const k = weight + '|' + t; if (TW[k] == null) { MEASURE.font = `${weight} 12px "Golos Text", system-ui, sans-serif`; TW[k] = MEASURE.measureText(t).width; } return TW[k]; }
const LABEL_CHARS = Array.from(new Set(N.map(x => x.s).join('') + '0123456789.,-−—«»() ')).join('');

/* ---------- траектории связей: одна 3D-кривая для линии и светового следа ---------- */
const ARC_S = 32;
function arcGeom(a, b, hub, lift){
  const lat0 = (a[1] + b[1]) / 2 * Math.PI / 180, kx = Math.cos(lat0);
  const dx = (b[0] - a[0]) * kx, dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1e-9;
  const nx = -dy / L, ny = dx / L;                      // левая нормаль: встречные направления расходятся
  const bend = L * (0.10 + 0.05 * hub);
  const Lm = L * 111320, H = Math.min(0.18 * Lm, 38000) * lift;
  const path = [], ts = []; let acc = 0, prev = null;
  for (let s = 0; s <= ARC_S; s++) {
    const t = s / ARC_S, sn = Math.sin(Math.PI * t), off = bend * sn;
    const p = [a[0] + (b[0] - a[0]) * t + nx * off / kx, a[1] + (b[1] - a[1]) * t + ny * off, H * sn];
    if (prev) acc += Math.hypot((p[0] - prev[0]) * kx * 111.32, (p[1] - prev[1]) * 111.32, (p[2] - prev[2]) / 1000);
    path.push(p); ts.push(acc); prev = p;
  }
  return {path, ts: ts.map(v => v / (acc || 1)), km: acc};
}
/* маленькая стрелка направления в цвете семейства — у самой кривой, ближе к получателю; размер в пикселях экрана */
function arrowPath(g, px = 7){ const p = g.path, k = Math.round(ARC_S * .82), a = p[k - 1], b = p[k], c = p[k + 1];
  const kx = Math.cos(b[1] * Math.PI / 180), s = px * 360 / (512 * 2 ** MAPVS.vs.zoom) * kx;   // градусы широты на px у этой точки
  const dx = (c[0] - a[0]) * kx, dy = c[1] - a[1], l = Math.hypot(dx, dy) || 1e-9, ux = dx / l, uy = dy / l, nx = -uy, ny = ux;
  const dz = (c[2] - a[2]) / 2;
  const pt = (f, side) => [b[0] + (-ux * s * f + nx * s * .6 * side) / kx, b[1] - uy * s * f + ny * s * .6 * side, b[2] - dz * f * .6];
  return [pt(1, 1), b, pt(1, -1)]; }

/* ---------- сцена ---------- */
class DeckScene {
  constructor(el, role){
    this.kind = 'deck'; this.el = el; this.role = role; this.labels = []; this.alive = true;
    this.deck = new DK.Deck({
      parent: el, views: new DK.MapView({repeat: false}),
      viewState: MAPVS.vs, controller: {dragRotate: MAPVS.dim === '3d', touchRotate: MAPVS.dim === '3d', keyboard: true, inertia: 300},
      onViewStateChange: ({viewState, interactionState}) => { setMapVS(viewState, this); return viewState; },
      getCursor: ({isDragging, isHovering}) => isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab',
      pickingRadius: 6,
      useDevicePixels: Math.min(window.devicePixelRatio || 1, 2),
      parameters: {depthTest: false},
      onHover: info => mapHover(info, this), onClick: (info, ev) => mapClick(info, this, ev),
      onWebGLInitialized: gl => { const c = gl.canvas || (this.deck && this.deck.getCanvas && this.deck.getCanvas()); if (!c) return;
        c.addEventListener('webglcontextlost', ev => { ev.preventDefault(); sceneLost(this); }, {once: true});
        c.tabIndex = 0; c.setAttribute('role', 'img');                                   // клавиатура: стрелки — сдвиг, +/− — масштаб, Shift+стрелки — наклон/поворот
        c.setAttribute('aria-label', (role === 'mig' ? 'Карта миграционного прироста' : 'Карта муниципалитетов и связей') + '. Клавиши: стрелки — сдвиг, плюс и минус — масштаб, Shift со стрелками — наклон и поворот. Данные карты — в карточке справа, рейтинге и таблице связей ниже.'); },
      onError: err => { console.warn('deck', err); },
      onAfterRender: () => { this.rendered = (this.rendered || 0) + 1; this.drawLabels(); },
    });
    this.canvas = () => this.el.querySelector('canvas'); this.sz = {width: el.clientWidth, height: el.clientHeight};
    this.lbl = document.createElement('div'); this.lbl.className = 'mlabels'; this.lbl.setAttribute('aria-hidden', 'true'); el.appendChild(this.lbl); this.lblKey = '';
  }
  size(){ return this.sz; }                                         // размер кэшируется: в кадре анимации layout не читается
  viewport(){ const s = this.size(); if (!s.width) return null; return new DK.WebMercatorViewport({...MAPVS.vs, ...s}); }
  setVS(vs){ if (this.alive) this.deck.setProps({viewState: vs}); }
  setController(){ this.deck.setProps({controller: {dragRotate: MAPVS.dim === '3d', touchRotate: MAPVS.dim === '3d', keyboard: true, inertia: 300}}); }
  destroy(){ this.alive = false; try { this.deck.finalize(); } catch (e) {} this.el.innerHTML = ''; }
  resized(){ if (!this.alive) return; this.sz = {width: this.el.clientWidth, height: this.el.clientHeight}; resetUiBoxes(); this.deck.redraw('resize'); }
  /* подписи — HTML поверх WebGL: точный шрифт, постоянный размер, без уменьшения вдали; позиция — из того же вьюпорта, что и кадр */
  drawLabels(){
    const vp = (this.deck.getViewports && this.deck.getViewports()[0]) || this.viewport(); if (!vp || !this.lbl) return;
    /* раскладка — для той камеры, которая рисуется в этом кадре: если кадр опередил отложенную раскладку
       (смена камеры, полёт, перетаскивание), подписи перераскладываются здесь же, а не кадром позже */
    const vk = vpKey(vp); if (vk !== this.placedVk) this.placeLabels(vp);
    const key = vk + '|' + this.labelsVer; if (key === this.lblKey) return; this.lblKey = key;
    this.lbl.innerHTML = this.labels.map(l => { const [x, y] = vp.project(CENTER[l.i]);
      return `<span class="mlbl${l.bold ? ' b' : ''}" style="transform:translate(${x.toFixed(1)}px,${(y - 7).toFixed(1)}px) translate(-50%,-100%)">${esc(N[l.i].s)}</span>`; }).join('');
  }
  retheme(){}                                                        // слои пересобираются из PAL при renderScenes
  /* подписи: приоритет выбранное → концы связи → наведение → крупные по населению; без пересечений */
  placeLabels(vpIn){
    const vp = vpIn || this.viewport(); if (!vp) { this.labels = []; return; }
    this.placedVk = vpKey(vp);
    const z = vp.zoom != null ? vp.zoom : MAPVS.vs.zoom, pri = [];   // у вьюпорта 2D-резерва (Leaflet) масштаба нет — общий из камеры
    const must = new Set([sel, MAPST.hoverMO, ...(MAPST.pinned ? [MAPST.pinned.e[0], MAPST.pinned.e[1]] : [])].filter(v => v != null));
    for (let i = 0; i < n; i++) { const x = N[i];
      let p = Math.log10(x.pop) + (x.kind === 'ГО' ? 1.2 : 0);
      if (i === sel) p += 100; else if (MAPST.pinned && (i === MAPST.pinned.e[0] || i === MAPST.pinned.e[1])) p += 80; else if (i === MAPST.hoverMO) p += 60;
      else if (group && group.has(i)) p += 3; else if (sel != null && MAPST.related.has(i)) p += 2;
      pri.push([p, i]); }
    pri.sort((a, b) => b[0] - a[0]);
    const W = vp.width, H = vp.height, out = [], ui = reservedBoxes(this), placed = [];
    const cap = z < 6.6 ? 16 : z < 7.4 ? 30 : 80;
    for (const [p, i] of pri) {
      if (out.length >= cap && !must.has(i)) continue;
      const [x, y] = vp.project(CENTER[i]);
      const bold = i === sel || must.has(i), w = textW(N[i].s, bold ? 600 : 500) * (bold ? 13 / 12 : 1) + 8, h = bold ? 18 : 16;
      const box = [x - w / 2, y - 7 - h, x + w / 2, y - 5];
      if (box[0] < 2 || box[1] < 2 || box[2] > W - 2 || box[3] > H - 2) continue;              // подпись целиком в кадре
      const hit = b => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]);
      if (ui.some(hit)) continue;                                                                   // не под плавающими кнопками и заметками
      if (!must.has(i) && placed.some(hit)) continue;
      placed.push(box); out.push({i, bold, box});
    }
    this.labels = out; this.labelsVer = (this.labelsVer || 0) + 1;
  }
}

/* области плавающих элементов над сценой (переключатель режимов, камера, заметки, полоса выбора): подписи их обходят.
   Кэш по размеру сцены и состоянию интерфейса — в кадре анимации layout не читается. */
const UIBOX = {key: '', boxes: []};
function reservedBoxes(scene){
  const key = [scene.el.id, scene.sz && scene.sz.width, scene.sz && scene.sz.height, MAPST.view, sel != null, $('#fbNote') && $('#fbNote').hidden].join('|');
  if (UIBOX.key === key && UIBOX.scene === scene) return UIBOX.boxes;
  const r = scene.el.getBoundingClientRect(), pad = 4;
  const boxes = [...document.querySelectorAll('#mapwrap .mapfloat, #mapwrap .scene-lbl')].filter(e => !e.hidden && e.offsetParent !== null).map(e => e.getBoundingClientRect())
    .filter(b => b.width && b.height && b.right > r.left && b.left < r.right && b.bottom > r.top && b.top < r.bottom)
    .map(b => [b.left - r.left - pad, b.top - r.top - pad, b.right - r.left + pad, b.bottom - r.top + pad]);
  Object.assign(UIBOX, {key, scene, boxes}); return boxes;
}
function resetUiBoxes(){ UIBOX.key = ''; }

const vpKey = vp => [vp.longitude, vp.latitude, vp.zoom, vp.pitch, vp.bearing, vp.width, vp.height].map(v => +(+v).toFixed(6)).join('|');

/* ---------- состояние камеры: одно на обе сцены ---------- */
const MAPVS = {vs: {longitude: 56.0, latitude: 54.6, zoom: 6.2, pitch: 35, bearing: 0}, dim: '3d', scenes: [], pending: null};
function setMapVS(vs, from){
  MAPVS.vs = {longitude: vs.longitude, latitude: vs.latitude, zoom: vs.zoom, pitch: vs.pitch || 0, bearing: vs.bearing || 0};
  if (from) { MAPVS.scenes.forEach(s => { if (s !== from) s.setVS({...MAPVS.vs}); }); from.setVS(vs); }   // ведущая сцена ведёт, вторая повторяет кадр в кадр
  else MAPVS.scenes.forEach(s => s.setVS(vs));                                                             // внешняя команда (кнопки, подгонка) — всем сценам
  scheduleLabels();
}
/* подгонка камеры: рамка проекции в фактическом (в т.ч. наклонном) вьюпорте с учётом плавающих элементов.
   fitBounds считает только вид сверху; при наклоне север сжимается, юг растёт — поэтому масштаб и центр
   уточняются по экранной рамке спроецированных точек (контур региона или стороны прямоугольника). */
const REGION_PTS = GEO.outline[0].filter((_, k) => k % 3 === 0);
const rectPts = ([[w, s], [e, nn]]) => { const P = []; for (let k = 0; k <= 4; k++) { const t = k / 4; P.push([w + (e - w) * t, s], [w + (e - w) * t, nn], [w, s + (nn - s) * t], [e, s + (nn - s) * t]); } return P; };
const pbox = P => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; P.forEach(([x, y]) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }); return [x0, y0, x1, y1]; };
function fitView(bounds, {pad = 48, keepPitch = true, duration = 520, maxZoom = 10.5, pts = null} = {}){
  const s = MAPVS.scenes[0], sz = s && s.size();
  if (!s || !sz.width) { MAPVS.pending = {bounds, pad, maxZoom, pts}; return; }
  MAPVS.pending = null;
  const flat = s.kind === 'leaflet' || MAPVS.dim !== '3d', split = MAPST.view === 'split';
  /* в сопоставлении сверху — подписи сцен, снизу справа — переключатель режимов и камера */
  const padding = typeof pad === 'number' ? {top: pad + (split ? 46 : flat ? 0 : 14), bottom: pad + (split ? 104 : 0), left: pad, right: pad} : pad;
  const f = new DK.WebMercatorViewport({width: sz.width, height: sz.height}).fitBounds(bounds, {padding, maxZoom});
  const target = {...MAPVS.vs, longitude: f.longitude, latitude: f.latitude, zoom: f.zoom,
    pitch: flat ? 0 : (keepPitch ? (MAPVS.vs.pitch || 35) : 35), bearing: flat ? 0 : MAPVS.vs.bearing};
  if (target.pitch > 1 || target.bearing) {
    const P = pts || rectPts(bounds), W = sz.width - padding.left - padding.right, H = sz.height - padding.top - padding.bottom;
    const cx = padding.left + W / 2, cy = padding.top + H / 2;
    for (let k = 0; k < 3; k++) {
      let vp = new DK.WebMercatorViewport({...sz, ...target}), b = pbox(P.map(p => vp.project(p)));
      target.zoom = Math.min(maxZoom, target.zoom + Math.log2(Math.max(.25, Math.min(4, Math.min(W / Math.max(1, b[2] - b[0]), H / Math.max(1, b[3] - b[1]))))));
      vp = new DK.WebMercatorViewport({...sz, ...target}); b = pbox(P.map(p => vp.project(p)));
      const c = vp.unproject([sz.width / 2 + (b[0] + b[2]) / 2 - cx, sz.height / 2 + (b[1] + b[3]) / 2 - cy]);
      target.longitude = c[0]; target.latitude = c[1];
    }
  }
  if (duration && !RM.matches) { target.transitionDuration = duration; target.transitionInterpolator = new DK.LinearInterpolator(['longitude', 'latitude', 'zoom', 'pitch', 'bearing']); }
  setMapVS(target, null);
}
let labelTimer = null;
function scheduleLabels(){ if (labelTimer) return; labelTimer = requestAnimationFrame(() => { labelTimer = null; MAPVS.scenes.forEach(s => s.placeLabels()); renderScenes(); }); }
