/* ==========================================================================
   Карта: честный 2D-резерв на Leaflet (нет WebGL2, потерян контекст, ?render=2d)
   Тот же D.geo, тот же производный контур и швы, та же раскраска fillFor,
   те же связи computeEdges (плоские кривые), выбор, наведение и подписи.
   Нет наклона, высоты дуг, маски свечения и бегущего следа — это сказано в заметке.
   ========================================================================== */
const llOf = c => [c[1], c[0]];
const llLine = path => path.map(llOf);
const rgbaCss = c => `rgba(${c[0]},${c[1]},${c[2]},${((c[3] == null ? 255 : c[3]) / 255).toFixed(3)})`;
class LeafletScene {
  constructor(el){
    this.kind = 'leaflet'; this.role = 'main'; this.el = el; this.alive = true; this.labels = []; this.self = false; this.key = '';
    this.map = L.map(el, {zoomControl: false, attributionControl: false, zoomSnap: .1, zoomDelta: .5, wheelPxPerZoomLevel: 90, minZoom: 5.5, maxZoom: 12,
      renderer: L.svg({padding: .4}), keyboard: true, worldCopyJump: false, inertia: !RM.matches, fadeAnimation: !RM.matches, zoomAnimation: !RM.matches});
    this.map.setView([MAPVS.vs.latitude, MAPVS.vs.longitude], MAPVS.vs.zoom + 1, {animate: false});
    const P = (name, z) => { const p = this.map.createPane(name); p.style.zIndex = z; return name; };
    P('lf-base', 380); P('lf-fill', 400); P('lf-lines', 420); P('lf-sel', 440); P('lf-edges', 460); P('lf-nodes', 480);
    const nofx = {interactive: false, bubblingMouseEvents: false};
    this.base = L.polygon(GEO.outline.map(llLine), {...nofx, pane: 'lf-base', stroke: false, fillOpacity: 1}).addTo(this.map);
    this.fill = L.geoJSON({type: 'FeatureCollection', features: FEAT}, {pane: 'lf-fill', bubblingMouseEvents: false,
      style: () => ({stroke: false, fillOpacity: 1}),
      onEachFeature: (f, lyr) => {
        lyr.on('mousemove', ev => this.hover({mo: f.properties.i}, ev)); lyr.on('mouseout', () => this.hover({}, null));
        lyr.on('click', ev => { L.DomEvent.stop(ev); this.click({mo: f.properties.i}); }); }}).addTo(this.map);
    this.byI = new Array(n); this.fill.eachLayer(l => this.byI[l.feature.properties.i] = l);
    this.seams = L.polyline(GEO.seams.map(llLine), {...nofx, pane: 'lf-lines', weight: .7, lineJoin: 'round'}).addTo(this.map);
    this.outline = L.polyline(GEO.outline.map(llLine), {...nofx, pane: 'lf-lines', weight: 1.1, lineJoin: 'round'}).addTo(this.map);
    this.deco = L.layerGroup().addTo(this.map);          // н/д, пограничные, группа, наведение
    this.selG = L.layerGroup().addTo(this.map);          // выбор
    this.edgeG = L.layerGroup().addTo(this.map);         // связи
    this.nodeG = L.layerGroup().addTo(this.map);         // центры МО
    this.lbl = document.createElement('div'); this.lbl.className = 'mlabels'; this.lbl.setAttribute('aria-hidden', 'true'); el.appendChild(this.lbl);
    this.tiles = null;
    this.map.on('click', () => this.click({}));
    this.map.on('move zoom', () => { if (this.self) return; const c = this.map.getCenter();
      this.self = true; setMapVS({longitude: c.lng, latitude: c.lat, zoom: this.map.getZoom() - 1, pitch: 0, bearing: 0}, this); this.self = false; this.drawLabels(); });
    this.drawNodes();
  }
  size(){ return this.sz || (this.sz = {width: this.el.clientWidth, height: this.el.clientHeight}); }
  viewport(){ const s = this.size(); if (!s.width) return null; const m = this.map;
    return {width: s.width, height: s.height, project: c => { const p = m.latLngToContainerPoint([c[1], c[0]]); return [p.x, p.y]; }}; }
  setVS(vs){ if (!this.alive || this.self) return;
    const c = this.map.getCenter(), z = vs.zoom + 1;
    if (Math.abs(c.lat - vs.latitude) < 1e-7 && Math.abs(c.lng - vs.longitude) < 1e-7 && Math.abs(this.map.getZoom() - z) < 1e-6) return;
    this.self = true; this.map.setView([vs.latitude, vs.longitude], z, {animate: !!vs.transitionDuration && !RM.matches, duration: (vs.transitionDuration || 0) / 1000}); this.self = false; }
  setController(){}
  resized(){ if (!this.alive) return; this.sz = null; resetUiBoxes(); this.map.invalidateSize({pan: false}); }
  retheme(){ this.key = ''; }
  destroy(){ this.alive = false; try { this.map.remove(); } catch (e) {} this.el.innerHTML = ''; }
  hover(pk, ev){
    const mo = pk.mo == null ? null : pk.mo, edge = pk.edge || null;
    if (mo !== MAPST.hoverMO || edge !== MAPST.hoverEdge) { MAPST.hoverMO = mo; MAPST.hoverEdge = edge; MAPST.ver++; scheduleLabels(); }
    if (!ev) { hideTip(); return; } const oe = ev.originalEvent;
    if (edge) showTip(oe, edgeTip(edge)); else if (mo != null) showTip(oe, moTip(mo, 'main')); else hideTip();
  }
  click(pk){ hideTip();
    if (pk.edge) { pinEdge(pk.edge); return; }
    if (pk.mo != null) { select(pk.mo); return; }
    if (MAPST.pinned) { MAPST.pinned = null; mapChanged(); panel(); return; }
    if (sel != null) select(null); }
  drawNodes(){
    this.nodeG.clearLayers(); this.nodes = new Array(n);
    for (let i = 0; i < n; i++) { if (!CENTER[i]) continue;
      const m = L.circleMarker(llOf(CENTER[i]), {pane: 'lf-nodes', radius: N[i].kind === 'ГО' ? 3.6 : 2.8, weight: 1, fillOpacity: 1, bubblingMouseEvents: false});
      m.on('mousemove', ev => this.hover({mo: i}, ev)); m.on('mouseout', () => this.hover({}, null)); m.on('click', ev => { L.DomEvent.stop(ev); this.click({mo: i}); });
      this.nodes[i] = m.addTo(this.nodeG); }
  }
  render(now){
    if (!this.alive) return;
    /* основа, швы, контур — из той же палитры, что у 3D */
    this.base.setStyle({fillColor: rgbaCss(PAL.geo)});
    this.seams.setStyle({color: rgbaCss(PAL.seam)}); this.outline.setStyle({color: rgbaCss(PAL.outline)});
    for (let i = 0; i < n; i++) { const l = this.byI[i]; if (!l) continue; const c = fillFor(i, 'main');
      l.setStyle({fillColor: `rgb(${c[0]},${c[1]},${c[2]})`, fillOpacity: c[3] / 255}); }
    /* декоративные контуры */
    this.deco.clearLayers();
    const ring = (i, o) => RINGS[i].forEach(r => L.polyline(llLine(r), {interactive: false, pane: 'lf-lines', lineJoin: 'round', ...o}).addTo(this.deco));
    const ndMode = MAPST.mode;
    if (!['type', 'quarter', 'macro'].includes(ndMode)) for (let i = 0; i < n; i++) if (valueOf(i, ndMode) == null) ring(i, {color: rgbaCss(PAL.muted), weight: 1.2, dashArray: '4 3'});
    if (MAPST.unc && ['type', 'quarter'].includes(MAPST.mode)) for (let i = 0; i < n; i++) if (UNC(i) && i !== sel) ring(i, {color: rgbaCss([...PAL.ink2.slice(0, 3), 150]), weight: 1, dashArray: '3 3'});
    if (group && sel == null) group.forEach(i => ring(i, {color: rgbaCss([...PAL.pearlEdge.slice(0, 3), 210]), weight: 1.2}));
    if (MAPST.hoverMO != null && MAPST.hoverMO !== sel) ring(MAPST.hoverMO, {color: rgbaCss([...PAL.ink2.slice(0, 3), 190]), weight: 1.2});
    /* выбор: вуаль + тонкая жемчужная кромка (без маски свечения) */
    this.selG.clearLayers();
    if (sel != null) {
      L.geoJSON(FEAT_BY[sel], {interactive: false, pane: 'lf-sel', style: {stroke: false, fillColor: rgbaCss(PAL.pearl), fillOpacity: PAL.dark ? .13 : .07}}).addTo(this.selG);
      RINGS[sel].forEach(r => { L.polyline(llLine(r), {interactive: false, pane: 'lf-sel', color: rgbaCss(PAL.pearl), opacity: .35, weight: 4, lineJoin: 'round'}).addTo(this.selG);
        L.polyline(llLine(r), {interactive: false, pane: 'lf-sel', color: rgbaCss(PAL.pearlEdge), weight: PAL.dark ? 1.4 : 1.6, lineJoin: 'round'}).addTo(this.selG); });
    }
    /* связи: плоские кривые той же геометрии, без высоты; стрелка у получателя */
    const key = [MAPST.ver, sel, MAPST.pinned && MAPST.pinned.e, MAPST.hoverEdge && MAPST.hoverEdge.e].join('|');
    if (key !== this.key) { this.key = key; this.edgeG.clearLayers();
      if (MAPST.stats) {
        const fam = (LMETA[MAPST.layer] || {}).fam || 'sim', base = PAL.fam[fam], pinE = MAPST.pinned && MAPST.pinned.e, d = isDir(MAPST.layer);
        const add = (it, a, w) => { const ll = it.g.path.map(p => [p[1], p[0]]);
          L.polyline(ll, {interactive: false, pane: 'lf-edges', color: `rgb(${base})`, opacity: a, weight: w, lineCap: 'round', lineJoin: 'round'}).addTo(this.edgeG);
          const hit = L.polyline(ll, {pane: 'lf-edges', color: '#000', opacity: 0, weight: 10, bubblingMouseEvents: false}).addTo(this.edgeG);
          hit.on('mousemove', ev => this.hover({edge: it}, ev)); hit.on('mouseout', () => this.hover({}, null)); hit.on('click', ev => { L.DomEvent.stop(ev); this.click({edge: it}); }); };
        MAPST.ctx.forEach(it => add(it, sel != null ? .07 : Math.min(.85, .28 + .5 * it.t), .6 + .7 * it.t));
        MAPST.edges.forEach(it => add(it, pinE ? (it.e === pinE ? .98 : .22) : .5 + .4 * it.t, it.e === pinE ? 2 : .9 + .7 * it.t));
        const hov = MAPST.hoverEdge; if (hov && hov.g) L.polyline(hov.g.path.map(p => [p[1], p[0]]), {interactive: false, pane: 'lf-edges', color: `rgb(${base})`, opacity: .96, weight: 2}).addTo(this.edgeG);
        if (d) { const arr = pinE ? [...MAPST.edges, ...MAPST.ctx].filter(x => x.e === pinE) : (sel != null ? MAPST.edges.slice(-12) : []);
          arr.forEach(it => L.polyline(arrowPath(it.g).map(p => [p[1], p[0]]), {interactive: false, pane: 'lf-edges', color: `rgb(${base})`, opacity: .92, weight: 1.4, lineCap: 'round'}).addTo(this.edgeG)); }
        if (pinE) { const it = [...MAPST.edges, ...MAPST.ctx].find(x => x.e === pinE);
          if (it) [it.s0, it.s1].forEach(j => L.circleMarker(llOf(CENTER[j]), {interactive: false, pane: 'lf-edges', radius: 8, fill: false, color: rgbaCss(PAL.pearlEdge), weight: 1.6}).addTo(this.edgeG)); }
      }
    }
    /* центры МО */
    for (let i = 0; i < n; i++) { const m = this.nodes[i]; if (!m) continue; const a = dimmed(i) ? .43 : 1;
      m.setStyle({fillColor: `rgb(${PAL.types[tslot(N[i].c)]})`, color: i === sel ? rgbaCss(PAL.pearlEdge) : rgbaCss(PAL.nodeLine), weight: i === sel ? 1.6 : 1, radius: i === sel ? 5 : (N[i].kind === 'ГО' ? 3.6 : 2.8), fillOpacity: a, opacity: a}); }
    /* подложка */
    if (MAPST.basemap && !this.tiles) { let errs = 0;
      this.tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {pane: 'lf-base', opacity: PAL.dark ? .35 : .55, className: 'lf-osm', maxZoom: 13}).addTo(this.map);
      this.tiles.on('tileerror', () => { if (++errs === 3) { $('#osm').checked = false; $('#osm').dispatchEvent(new Event('input'));
        notify($('#osm').closest('label'), 'Подложку OpenStreetMap загрузить не удалось (нет сети или сервер недоступен). Карта, данные и выбор работают без неё.', {kind: 'warn'}); } }); }
    if (!MAPST.basemap && this.tiles) { this.map.removeLayer(this.tiles); this.tiles = null; }
    this.base.setStyle({fillOpacity: MAPST.basemap ? .55 : 1});
    this.drawLabels();
  }
  /* подписи — HTML поверх карты по раскладке placeLabels (те же приоритеты и проверка пересечений) */
  drawLabels(){
    const vp = this.viewport(); if (!vp) return;
    this.lbl.innerHTML = this.labels.map(l => { const [x, y] = vp.project(CENTER[l.i]);
      return `<span class="mlbl${l.bold ? ' b' : ''}" style="transform:translate(${x.toFixed(1)}px,${(y - 7).toFixed(1)}px) translate(-50%,-100%)">${esc(N[l.i].s)}</span>`; }).join('');
  }
}
LeafletScene.prototype.placeLabels = DeckScene.prototype.placeLabels;
