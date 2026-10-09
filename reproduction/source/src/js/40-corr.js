/* ==========================================================================
   4. Корреляции: пара показателей (пузыри ↔ медианы по типам ↔ распределение),
   матрица (клетки / круги / список пар), лаговый профиль, сильнейшие связи.
   ρ, q и частные корреляции берутся из D.corr как есть; визуальные шкалы
   (лог, масштаб, агрегаты по типам) их не пересчитывают. D не изменяется:
   все представления строятся из копий (slice/map).
   Внешний API модуля: corrInit(), getVar(i, v), selectPair(a, b, opts).
   ========================================================================== */

/* значение переменной корреляции у МО: признак nodes[i].f или исходный индекс nodes[i].m (не процентиль mp); пропуск → null */
function getVar(i, v){
  const o = v.startsWith('m_') ? N[i].m : N[i].f, x = o ? o[v.startsWith('m_') ? v.slice(2) : v] : null;
  return x == null || !Number.isFinite(+x) ? null : +x;
}

const CORRTAB = (() => {
  const host = $('#t-corr');
  if (!D.corr) {
    host.innerHTML = `<div class="phead"><div><h2>Корреляции показателей</h2></div></div><div class="empty"><b>Корреляции не рассчитаны</b><span>Запустите <code>econtypes correlate</code>.</span></div>`;
    return {init(){}, selectPair(){}};
  }

  /* ---------- справочники ---------- */
  const CV = D.corr.vars.slice();
  const VIDX = {}; CV.forEach((v, k) => { VIDX[v] = k; });
  const CGROUPS = [
    ['Госзаказ', v => v.startsWith('proc_') || v.startsWith('okpd_') || v === 'supply_out_pc'],
    ['Траты населения', v => v === 'spend_total' || v.startsWith('sh_')],
    ['Население и территория', v => ['urban_share', 'market_access', 'log_pop', 'log_density', 'birth_rate', 'death_rate', 'migr_rate'].includes(v)],
    ['Бюджет и занятость', v => v === 'grants_pc' || v === 'wage' || v.startsWith('emp_')],
    ['Индексы', v => v.startsWith('m_')]];
  const gOf = v => { const k = CGROUPS.findIndex(g => g[1](v)); return k < 0 ? CGROUPS.length : k; };
  const GNAME = g => (CGROUPS[g] || ['Прочее'])[0];
  const ORDV = CV.map((v, k) => [v, k]).sort((a, b) => gOf(a[0]) - gOf(b[0]) || a[1] - b[1]).map(z => z[0]);   // порядок показа: по группам
  const pairKey = (a, b) => a < b ? a + '|' + b : b + '|' + a;
  const PART = {}; D.corr.top.forEach(r => { PART[pairKey(r.x, r.y)] = r; });
  const CTRL = ['log_pop', 'urban_share'];
  const rhoOf = (a, b) => { const r = D.corr.rho[VIDX[a]][VIDX[b]]; return r == null ? null : r; };
  const qOf = (a, b) => { const q = D.corr.q[VIDX[a]][VIDX[b]]; return q == null ? null : q; };
  const fq = q => q == null ? 'н/д' : q < .001 ? '< 0,001' : fmtN(q, 3);
  const fqEq = q => q == null ? 'q н/д' : q < .001 ? 'q < 0,001' : 'q = ' + fmtN(q, 3);
  const norm = s => String(s || '').toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, ' ').trim();
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const POPMAX = Math.max(...N.map(x => x.pop || 0));
  const TIDX = {}; TYPES.forEach((t, k) => { TIDX[t.c] = k; });
  const KT = TYPES.length;
  const MOS_OF = c => N.map((x, i) => i).filter(i => N[i].c === c).sort((a, b) => N[a].s.localeCompare(N[b].s, 'ru'));
  const MCTX = document.createElement('canvas').getContext('2d');
  const textW = (s, font) => { MCTX.font = font; return MCTX.measureText(String(s)).width; };
  const FONT_NUM = '500 12px "JetBrains Mono", monospace';
  const lagTxt = l => (l > 0 ? '+' : l < 0 ? '−' : '') + Math.abs(l);
  const ALLPAIRS = []; for (let i = 0; i < ORDV.length; i++) for (let j = 0; j < i; j++) { const a = ORDV[i], b = ORDV[j]; ALLPAIRS.push({a, b, rho: rhoOf(a, b), q: qOf(a, b)}); }
  const NSIG = ALLPAIRS.filter(p => p.q != null && p.q < .05).length;
  /* квантиль по методу R-7 (линейная интерполяция порядковых статистик; как d3.quantile и numpy по умолчанию) */
  function q7(s, p){ const m = s.length; if (!m) return null; if (m === 1) return s[0]; const h = (m - 1) * p, lo = Math.floor(h); return lo + 1 < m ? s[lo] + (h - lo) * (s[lo + 1] - s[lo]) : s[lo]; }

  function partialInfo(a, b){
    if (CTRL.includes(a) || CTRL.includes(b)) return {txt: 'не рассчитывается', note: 'Один из показателей — контрольная переменная (население, лог, или доля горожан); частная корреляция для таких пар не считается и не равна нулю.'};
    const pr = PART[pairKey(a, b)];
    if (pr && pr.prho != null) return {val: pr.prho, keep: pr.pq < .05, note: `При контроле размера (население, лог) и урбанизации (доля горожан): частная ρ = ${fmtSigned(pr.prho, 2)}, ${fqEq(pr.pq)} — связь ${pr.pq < .05 ? 'сохраняется' : 'не сохраняется'}.`};
    return {txt: 'нет в данных', note: 'Частная корреляция в данных есть только для пар из таблицы сильнейших значимых связей; для этой пары она не рассчитывалась.'};
  }
  /* подпись оси/показателя с единицами (индексы — исходные значения m, не процентили) */
  function axisCaption(v){
    if (v.startsWith('m_')) { const k = v.slice(2), m = IX_RAW[k] || {}; return `${D.metrics[k].label} — индекс, ${m.kind === 'share' ? (m.unit ? m.unit + ', %' : '%') : (m.unit || 'значение индекса')}`; }
    const u = (D.feats[v] || ['', ''])[1];
    if (v.startsWith('log_')) return featLabel(v) + ' — логарифм, безразмерный';
    return featLabel(v) + ', ' + (u === '%' ? '%' : u || 'безразмерный');
  }

  /* ---------- разметка ---------- */
  host.innerHTML = `
  <div class="phead">
    <div><h2>Корреляции показателей</h2>
      <p class="lede" id="corrLede"></p></div>
    <div class="cr-kpis" aria-label="Состав матрицы">
      <div><b class="mono">${CV.length}</b><span>показателей и индексов</span></div>
      <div><b class="mono">${fmtN(ALLPAIRS.length)}</b><span>уникальных пар</span></div>
      <div><b class="mono">${NSIG}</b><span>значимы, q &lt; 0,05</span></div>
    </div>
  </div>
  <div class="cwork">
    <div class="cr-mat" id="crMat">
      <div class="cr-mtools">
        <div class="seg" role="group" aria-label="Представление пар" id="cmView">
          <button type="button" data-view="cells">Клетки</button>
          <button type="button" data-view="circles">Круги</button>
          <button type="button" data-view="list">Список пар</button>
        </div>
        <div class="seg" role="group" aria-label="Форма матрицы" id="triSeg">
          <button type="button" data-tri="1">Треугольная</button>
          <button type="button" data-tri="0">Полная</button>
        </div>
        <input type="search" id="cmSearch" placeholder="Найти показатель" aria-label="Поиск показателя по названию" autocomplete="off">
      </div>
      <div class="cr-groups" role="group" aria-label="Группы показателей" id="cmGroups">
        <span class="cr-gl">Группы:</span>
        ${CGROUPS.map((g, k) => `<button type="button" class="chip" data-g="${k}" aria-pressed="true">${esc(g[0])} <span class="mono cr-gn">${ORDV.filter(v => gOf(v) === k).length}</span></button>`).join('')}
      </div>
      <div class="cr-legend" id="cmLegend" aria-label="Легенда матрицы"></div>
      <div class="cr-read" id="cmRead" aria-hidden="true"></div>
      <div id="heat" class="cr-heat" tabindex="0" role="group" aria-roledescription="матрица корреляций" aria-label="Матрица корреляций: стрелки — перемещение по клеткам, Enter — выбрать пару" aria-describedby="cmRead">
        <div class="cr-hwrap"><div id="cmEc" class="cr-ec" aria-hidden="true" hidden></div><div id="cmTbl"></div></div>
      </div>
      <span class="sr" id="heatLive" aria-live="polite"></span>
      <div id="pairList" class="cr-plist" hidden>
        <div class="cr-pltools">
          <label class="field"><span>Порядок</span><select id="plSort">
            <option value="abs">по |ρ|, сильные сначала</option>
            <option value="neg">по ρ, отрицательные сначала</option>
            <option value="pos">по ρ, положительные сначала</option>
            <option value="q">по q, наименьшие сначала</option>
            <option value="name">по названию</option>
          </select></label>
          <span class="hint" id="plCount" aria-live="polite"></span>
        </div>
        <ul id="plUl"></ul>
        <button type="button" class="btn sm" id="plMore">Показать ещё 30</button>
      </div>
    </div>

    <div class="cr-pair panel" id="pairBox">
      <div class="cr-phd">
        <div class="eyebrow">Выбранная пара <button type="button" class="link cr-tomat" id="toMat">к матрице</button></div>
        <div class="vars" id="scTitle"></div>
      </div>
      <div class="cr-stats" id="scStat" aria-live="polite"></div>
      <p class="note" id="scNote"></p>
      <div class="cr-tools" id="scTools">
        <div class="seg" role="group" aria-label="Вид диаграммы пары" id="bMode">
          <button type="button" data-bm="bub">Пузыри</button>
          <button type="button" data-bm="med">Медианы по типам</button>
          <button type="button" data-bm="dist">Распределение по типам</button>
        </div>
        <div class="cr-tswap">
        <div class="cr-tl" id="bBubTools">
          <div class="seg" role="group" aria-label="Размер точки" id="bSize">
            <button type="button" data-bs="pop">Площадь ∝ населению</button>
            <button type="button" data-bs="eq">Одинаковые точки</button>
          </div>
          <div class="seg" role="group" aria-label="Логарифмические шкалы" id="bLog">
            <button type="button" data-lg="x">лог X</button>
            <button type="button" data-lg="y">лог Y</button>
          </div>
          <div class="cr-zoom" role="group" aria-label="Масштаб диаграммы">
            <button type="button" class="btn sm" data-zoom="out" aria-label="Уменьшить масштаб" title="Уменьшить масштаб">−</button>
            <button type="button" class="btn sm" data-zoom="in" aria-label="Увеличить масштаб" title="Увеличить масштаб">+</button>
            <button type="button" class="btn sm" id="bReset" disabled>${ICON.reset}<span>Сброс</span></button>
          </div>
        </div>
        <div class="cr-tl off" id="bAggTools">
          <div class="seg" role="group" aria-label="Показатель для агрегата по типам" id="bAgg">
            <button type="button" data-ag="y">по Y</button>
            <button type="button" data-ag="x">по X</button>
          </div>
        </div>
        </div>
      </div>
      <div class="cr-bbox">
        <div class="cr-cap" id="bCapY"></div>
        <div class="cr-stage" id="bStage">
          <div id="bubble" role="img"></div>
          <div class="cr-tycol" id="tyCol" role="group" aria-label="Типы МО: выбрать тип"></div>
        </div>
        <div class="cr-cap cr-capx" id="bCapX"></div>
      </div>
      <div id="scLegend" class="cr-sclegend"><div class="cr-tleg" id="scTypes" role="group" aria-label="Типы МО: выделить тип"></div><div id="scBody"></div></div>
      <div class="cr-mopick" id="moPick">
        <label class="field"><span>МО</span><select id="moSel"><option value="">— выберите на диаграмме или в списке —</option>${TYPES.map(t => `<optgroup label="${esc(t.name)}">${MOS_OF(t.c).map(i => `<option value="${i}">${esc(N[i].s)}</option>`).join('')}</optgroup>`).join('')}</select></label>
        <div id="moCard"></div>
      </div>
      <div id="typeDrill"></div>
      <details class="cr-det" id="tyTabD"><summary>${ICON.chev}<span id="tyTabS">Медиана и квартили по типам</span></summary><div id="tyTab"></div></details>
      <details class="cr-det" id="ptTabD"><summary>${ICON.chev}<span id="ptTabS">Значения пары по всем МО</span></summary><div id="ptTab"></div></details>
    </div>
  </div>

  <div class="sec cr-lagsec">
    <h3 class="sech">Опережение госзаказа над тратами населения <span class="kicker">отдельный глобальный расчёт</span></h3>
    <p class="secsub">Медианная по МО корреляция месячных приростов госзаказа и безналичных трат при сдвиге одного ряда относительно другого. Лаг &gt; 0 — госзаказ впереди. Расчёт глобальный для пары «госзаказ — траты» и <b>не зависит от пары, выбранной в матрице</b>. Сдвиг — временная закономерность, а не доказательство причинности.</p>
    <div class="cr-lag">
      <div class="cr-lagmain">
        <div class="cr-lagtop">
          <div class="cr-lagleg" aria-label="Легенда лагового графика">
            <span><svg width="26" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" fill="var(--rn2)"/><circle cx="19" cy="7" r="5.5" fill="var(--rp2)"/></svg>медиана ρ по МО (цвет — знак)</span>
            <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="3.6" fill="none" stroke="var(--ink2)" stroke-width="1.5"/></svg>среднее ρ по МО</span>
            <span><svg width="22" height="14" aria-hidden="true"><rect x="1" y="4" width="20" height="6" rx="2" fill="var(--line)"/><rect x="1" y="4" width="9" height="6" rx="2" fill="var(--ink2)"/></svg>доля МО с ρ &gt; 0</span>
          </div>
          <button type="button" class="btn sm" id="lagReplay">${ICON.reset}<span>Повторить появление</span></button>
        </div>
        <div id="lagc" class="cr-lagc" role="img" aria-label="Профиль семи лагов: медиана и среднее ρ по МО. Точные значения — в карточке и таблице."></div>
        <div class="cr-lagctl" id="lagCtl" role="radiogroup" aria-label="Сдвиг, месяцев"></div>
        <div class="cr-lagax"><span>← траты впереди</span><span>сдвиг, месяцев</span><span>госзаказ впереди →</span></div>
      </div>
      <div class="cr-lagside">
        <div class="cr-lagcard" id="lagCard" aria-live="polite"></div>
        <div id="lagTable"></div>
      </div>
    </div>
  </div>

  <div class="sec">
    <h3 class="sech">Сильнейшие значимые связи <span class="kicker" id="topCount"></span></h3>
    <p class="secsub">Исключены пары, где индекс построен из того же признака. «При контроле» — частная корреляция после удаления эффекта размера (население, лог) и урбанизации (доля горожан); «сохраняется» — значима и при контроле. Строка выбирает пару: она отмечается в матрице и открывается на диаграмме.</p>
    <div class="tbox"><table id="topcorr"><caption class="sr">Сильнейшие значимые связи: ρ Спирмена, q, частная корреляция</caption></table></div>
  </div>`;

  /* ======================================================================
     МАТРИЦА: клетки / круги (ECharts matrix + scatter) / список пар
     ====================================================================== */
  const MS = {view: null, tri: true, groups: new Set(CGROUPS.map((g, k) => k)), q: '', listN: 30, sort: 'abs'};
  let ROWS = [], COLS = [], TRI = true, selPair = null, cur = null, CSTOPS = [], CREC = null, CELLPX = 22, CGEOM = '';
  const narrowMQ = matchMedia('(max-width: 699px)');
  // узкий экран: список пар идёт в потоке страницы (без вложенной прокрутки, которая перехватывает жест), поэтому первая страница короче
  const list0 = () => narrowMQ.matches ? 15 : 30;
  MS.listN = list0();
  const viewNow = () => MS.view || (narrowMQ.matches ? 'list' : 'cells');
  function rcol(r){ r = clamp(r, -1, 1); for (let k = 0; k < 4; k++) if (r <= CSTOPS[k + 1][0]) return mix(CSTOPS[k][1], CSTOPS[k + 1][1], (r - CSTOPS[k][0]) / .5); return CSTOPS[4][1]; }
  const cellCol = (r, q) => q < .05 ? rcol(r) : mix(rcol(r), CSTOPS[2][1], .72);
  const circCol = r => rcol(Math.sign(r) * (.32 + .68 * Math.abs(r)));   // круги: знак + насыщенность; величину несёт площадь
  const circD = r => (CELLPX - 3) * Math.sqrt(Math.abs(r));   // диаметр ∝ √|ρ| ⇒ площадь ∝ |ρ| (без минимального размера: ρ≈0 — почти невидимая точка)
  const rhoInk = r => r == null ? 'var(--muted)' : r > 0 ? 'var(--rp2)' : r < 0 ? 'var(--rn2)' : 'var(--ink2)';
  function stops(){ CSTOPS = [[-1, css('--rn2')], [-.5, css('--rn1')], [0, css('--r0')], [.5, css('--rp1')], [1, css('--rp2')]]; }

  function matVars(){
    const vis = ORDV.filter(v => MS.groups.has(gOf(v))), q = norm(MS.q);
    const rows = q ? vis.filter(v => norm(featLabel(v)).includes(q) || norm(GNAME(gOf(v))).includes(q)) : vis;
    return {rows, cols: vis, tri: MS.tri && !q};
  }
  const validCell = (r, c) => r >= 0 && c >= 0 && r < ROWS.length && c < COLS.length && ROWS[r] !== COLS[c] && !(TRI && c > r);
  function cellFor(a, b){
    let r = ROWS.indexOf(a), c = COLS.indexOf(b); if (r >= 0 && c >= 0 && validCell(r, c)) return [r, c];
    r = ROWS.indexOf(b); c = COLS.indexOf(a); if (r >= 0 && c >= 0 && validCell(r, c)) return [r, c];
    return null;
  }
  const tdAt = (r, c) => $(`#cmTbl td[data-r="${r}"][data-c="${c}"]`);

  function legendHtml(){
    const v = viewNow();
    const hatch = `<span class="cr-sq cr-na" aria-hidden="true"></span>`;
    if (v === 'circles') {
      const ex = [.25, .5, 1].map(r => { const d = circD(r); return `<span class="cr-cx"><svg width="${CELLPX + 2}" height="${CELLPX + 2}" aria-hidden="true"><circle cx="${CELLPX / 2 + 1}" cy="${CELLPX / 2 + 1}" r="${d / 2}" fill="var(--rp2)" fill-opacity=".85"/></svg><span class="mono">|ρ| = ${fmtN(r, 2)}</span></span>`; }).join('');
      return `<div class="cr-lg1"><span class="cr-scale"><span class="mono">−1</span><span class="cr-ramp"></span><span class="mono">+1</span></span><span>цвет — знак и сила ρ (синий — отрицательная, медный — положительная; знак не означает «хорошо/плохо»)</span></div>
        <div class="cr-lg1">${ex}<span>площадь круга ∝ |ρ| (диаметр ∝ √|ρ|)</span></div>
        <div class="cr-lg1"><span class="cr-cx"><svg width="18" height="18" aria-hidden="true"><circle cx="9" cy="9" r="6.5" fill="var(--rn2)"/></svg>заливка — значимо, q &lt; 0,05</span><span class="cr-cx"><svg width="18" height="18" aria-hidden="true"><circle cx="9" cy="9" r="6" fill="none" stroke="var(--rn2)" stroke-width="1.4"/></svg>контур — q ≥ 0,05 после FDR</span><span class="cr-cx">${hatch}штриховка — значения нет</span></div>`;
    }
    if (v === 'list') return `<div class="cr-lg1"><span class="cr-scale"><span class="mono">−1</span><span class="cr-ramp"></span><span class="mono">+1</span></span><span>ρ Спирмена со знаком; полоса — величина и направление. «незначимо» — q ≥ 0,05 после поправки Бенджамини–Хохберга.</span></div>`;
    return `<div class="cr-lg1"><span class="cr-scale"><span class="mono">−1</span><span class="cr-ramp"></span><span class="mono">+1</span></span><span>отрицательная · 0 · положительная — знак, а не «хорошо/плохо»</span></div>
      <div class="cr-lg1"><span class="cr-cx"><span class="cr-sq" style="background:${mix(css('--rp2'), css('--r0'), .72)}" aria-hidden="true"></span>приглушено: q ≥ 0,05 после Бенджамини–Хохберга</span><span class="cr-cx">${hatch}штриховка — значения нет</span></div>`;
  }

  function heat(){
    stops();
    ({rows: ROWS, cols: COLS, tri: TRI} = matVars());
    const circ = viewNow() === 'circles';
    $('#cmLegend').innerHTML = legendHtml();
    const box = $('#cmTbl');
    if (!ROWS.length || !COLS.length) {
      box.innerHTML = `<div class="empty cr-empty"><b>Ничего не найдено</b><span>Нет показателей, подходящих под поиск «${esc(MS.q)}» в выбранных группах. Очистите поиск или включите группы.</span></div>`;
      cur = null; placeCircles(); readout(null); return;
    }
    const bands = []; COLS.forEach(v => { const g = gOf(v); if (!bands.length || bands[bands.length - 1][0] !== g) bands.push([g, 1]); else bands[bands.length - 1][1]++; });
    const cgs = new Set(COLS.map((v, k) => k && gOf(v) !== gOf(COLS[k - 1]) ? k : -1).filter(k => k > 0));
    const rgs = new Set(ROWS.map((v, k) => k && gOf(v) !== gOf(ROWS[k - 1]) ? k : -1).filter(k => k > 0));
    let h = `<table class="cm${circ ? ' circ' : ''}"><caption class="sr">Матрица ρ Спирмена: строки — ${ROWS.length} показателей, столбцы — ${COLS.length}</caption><thead><tr class="gband"><th class="corner" rowspan="2" scope="col"><span>${TRI ? 'Нижний треугольник' : MS.q ? 'Найденные строки × все столбцы' : 'Полная матрица'}</span><span class="mono cr-dim">${ROWS.length} × ${COLS.length}</span></th>`
      + bands.map(([g, c], k) => `<th colspan="${c}" class="gb${k ? ' gl' : ''}" title="${esc(GNAME(g))}" scope="colgroup"><span style="max-width:${Math.max(16, c * 23 - 12)}px">${esc(GNAME(g))}</span></th>`).join('')
      + `</tr><tr class="clr">` + COLS.map((v, c) => `<th class="cl${cgs.has(c) ? ' gl' : ''}" data-c="${c}" scope="col" title="${esc(featLabel(v))}"><div>${esc(featLabel(v))}</div></th>`).join('') + `</tr></thead><tbody>`;
    for (let r = 0; r < ROWS.length; r++) {
      const a = ROWS[r];
      h += `<tr class="${rgs.has(r) ? 'gt' : ''}"><th class="rl" data-r="${r}" scope="row" title="${esc(featLabel(a))}">${esc(featLabel(a))}</th>`;
      for (let c = 0; c < COLS.length; c++) {
        const b = COLS[c], gl = cgs.has(c) ? ' gl' : '';
        if (a === b) { h += `<td class="diag${gl}" data-r="${r}" data-c="${c}"></td>`; continue; }
        if (TRI && c > r) { h += `<td class="blank${gl}" data-r="${r}" data-c="${c}"></td>`; continue; }
        const rho = rhoOf(a, b), q = qOf(a, b);
        if (rho == null) { h += `<td class="nul${gl}" data-r="${r}" data-c="${c}"></td>`; continue; }
        h += `<td class="v${q < .05 ? '' : ' ns'}${gl}" data-r="${r}" data-c="${c}"${circ ? '' : ` style="background:${cellCol(rho, q)}"`}></td>`;
      }
      h += '</tr>';
    }
    box.innerHTML = h + '</tbody></table>';
    measureCorner();
    cur = null;
    markCell(); placeCircles(true); readout(null);
  }

  function measureCorner(){   // ширина липкой колонки подписей — для «липких» названий групп
    const tb = $('#cmTbl table'), corner = tb && tb.querySelector('th.corner');
    if (corner && corner.offsetWidth) tb.style.setProperty('--cmrl', corner.offsetWidth + 'px');
    fitBands();
  }
  /* название группы над столбцами: липкое у левого края, а ширина — по видимой части своей полосы.
     Иначе при прокрутке вбок липкий текст упирается в край полосы и уходит под угол («ение и территория») */
  function fitBands(){
    const tb = $('#cmTbl table'), corner = tb && tb.querySelector('th.corner'); if (!corner || !corner.offsetWidth) return;
    const cr = corner.getBoundingClientRect().right;
    tb.querySelectorAll('tr.gband th.gb').forEach(th => { const sp = th.firstElementChild; if (!sp) return;
      const r = th.getBoundingClientRect(), w = Math.floor(r.right - Math.max(r.left, cr) - 12);
      sp.style.maxWidth = Math.max(0, w) + 'px'; sp.style.visibility = w < 18 ? 'hidden' : ''; });
  }
  { let raf = 0; $('#heat').addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; fitBands(); }); }, {passive: true}); }
  /* круги: ECharts matrix + scatter под прозрачными клетками таблицы (клетки дают клавиатуру, липкие подписи, выбор) */
  function placeCircles(force){
    const ec = $('#cmEc'), on = viewNow() === 'circles' && ROWS.length && COLS.length && $('#cmTbl table');
    ec.hidden = !on; if (!on) return;
    const tb = $('#cmTbl table'), body = tb.tBodies[0], r0 = body.rows[0], rl = body.rows[body.rows.length - 1];
    const c0 = r0.cells[1], cl = r0.cells[r0.cells.length - 1], d0 = rl.cells[1];
    if (!c0 || !cl || !d0 || !tb.offsetWidth) return;   // вкладка скрыта: разместим при входе
    const x0 = tb.offsetLeft + c0.offsetLeft, y0 = tb.offsetTop + c0.offsetTop;
    const w = cl.offsetLeft + cl.offsetWidth - c0.offsetLeft, hh = d0.offsetTop + d0.offsetHeight - c0.offsetTop;
    const key = [x0, y0, w, hh, ROWS.join(), COLS.join(), TRI].join('|');
    if (!force && key === CGEOM) return; CGEOM = key;
    CELLPX = Math.min(w / COLS.length, hh / ROWS.length);
    Object.assign(ec.style, {left: x0 + 'px', top: y0 + 'px', width: w + 'px', height: hh + 'px'});
    if (!CREC) CREC = makeChart(ec, buildCircles, {renderer: 'svg'});
    else if (CREC.chart) { CREC.chart.resize(); CREC.chart.setOption(withMotion(buildCircles()), {notMerge: true}); }
  }
  function buildCircles(){
    stops();
    const data = [];
    ROWS.forEach((a, r) => COLS.forEach((b, c) => {
      if (!validCell(r, c)) return; const rho = rhoOf(a, b), q = qOf(a, b); if (rho == null) return;
      const col = circCol(rho), sig = q < .05;
      data.push({value: [String(c), String(r), rho], symbolSize: circD(rho),
        itemStyle: sig ? {color: col, opacity: .92, borderWidth: 0} : {color: 'rgba(0,0,0,0)', borderColor: col, borderWidth: 1.3, opacity: 1}});
    }));
    return {animationDuration: 420, animationDurationUpdate: 300, animationEasing: 'cubicOut',
      matrix: {left: 0, top: 0, right: 0, bottom: 0,
        x: {show: false, data: COLS.map((v, c) => String(c))}, y: {show: false, data: ROWS.map((v, r) => String(r))},
        body: {itemStyle: {color: 'rgba(0,0,0,0)', borderWidth: 0}}, backgroundStyle: {color: 'rgba(0,0,0,0)', borderWidth: 0}},
      series: [{id: 'circ', type: 'scatter', coordinateSystem: 'matrix', silent: true, data,
        animationDelay: i => Math.min(260, i * .25)}]};
  }

  function markCell(){
    $$('#cmTbl td.sel').forEach(td => td.classList.remove('sel'));
    if (!selPair) return;
    [[selPair[0], selPair[1]], [selPair[1], selPair[0]]].forEach(([a, b]) => {
      const r = ROWS.indexOf(a), c = COLS.indexOf(b); if (r >= 0 && c >= 0 && validCell(r, c)) { const td = tdAt(r, c); if (td) td.classList.add('sel'); } });
  }
  function scrollToCell(center = true){
    if (!selPair) return; const rc = cellFor(...selPair); if (!rc) return; ensureVisible(tdAt(...rc), center);
  }
  function ensureVisible(td, center){
    const box = $('#heat'), tb = box.querySelector('table'); if (!td || !tb || !box.clientWidth) return;
    const rl = tb.querySelector('th.rl'), lw = rl ? rl.offsetWidth : 0, th = tb.tHead ? tb.tHead.offsetHeight : 0;
    const x = tb.offsetLeft + td.offsetLeft, y = tb.offsetTop + td.offsetTop, w = td.offsetWidth, h = td.offsetHeight;
    const vw = box.clientWidth - lw, vh = box.clientHeight - th;
    if (center) { box.scrollLeft = Math.max(0, x - lw - (vw - w) / 2); box.scrollTop = Math.max(0, y - th - (vh - h) / 2); return; }
    if (x - lw < box.scrollLeft) box.scrollLeft = Math.max(0, x - lw - w); else if (x + w > box.scrollLeft + box.clientWidth) box.scrollLeft = x + 2 * w - box.clientWidth;
    if (y - th < box.scrollTop) box.scrollTop = Math.max(0, y - th - h); else if (y + h > box.scrollTop + box.clientHeight) box.scrollTop = y + 2 * h - box.clientHeight;
  }
  function cellText(a, b){ const rho = rhoOf(a, b), q = qOf(a, b), pi = partialInfo(a, b);
    if (rho == null) return `${featLabel(a)} ↔ ${featLabel(b)}: значения нет в данных`;
    return `${featLabel(a)} ↔ ${featLabel(b)}: ρ ${fmtSigned(rho, 2)}, q ${fq(q)} (${q < .05 ? 'значимо' : 'незначимо'} после FDR); при контроле: ${pi.val != null ? fmtSigned(pi.val, 2) : pi.txt}`; }
  function readout(rc){
    const el = $('#cmRead');
    if (!rc) { el.innerHTML = `<span class="hint">${viewNow() === 'list' ? '' : 'Наведите на клетку или перейдите в матрицу клавишей Tab: стрелки — перемещение, Home/End — край строки, Enter — открыть пару.'}</span>`; return; }
    const a = ROWS[rc[0]], b = COLS[rc[1]], rho = rhoOf(a, b), q = qOf(a, b);
    el.innerHTML = `<span class="cr-rd-n"><b>${esc(featLabel(a))}</b> <span class="muted">↔</span> <b>${esc(featLabel(b))}</b></span>` + (rho == null ? `<span class="mono">н/д</span>` :
      `<span class="mono" style="color:${rhoInk(rho)}">ρ ${fmtSigned(rho, 2)}</span><span class="mono">${fqEq(q)}</span><span class="tag">${q < .05 ? 'значимо' : 'незначимо'}</span>`);
  }
  function cellTip(a, b){ const rho = rhoOf(a, b), q = qOf(a, b), pi = partialInfo(a, b);
    if (rho == null) return `<b>${esc(featLabel(a))}</b><div class="tsub">↔ ${esc(featLabel(b))}</div><div>значения нет в данных</div>`;
    return `<b>${esc(featLabel(a))}</b><div class="tsub">↔ ${esc(featLabel(b))}</div><div class="tnum">ρ Спирмена ${fmtSigned(rho, 2)} · q ${fq(q)}</div><div class="tsub">${q < .05 ? 'значимо после FDR' : 'незначимо после FDR'}</div>`
      + `<div class="tsub">при контроле: ${pi.val != null ? fmtSigned(pi.val, 2) + (pi.keep ? ' (сохраняется)' : ' (не сохраняется)') : esc(pi.txt)}</div>`; }
  function setCur(rc, announceIt = true){
    $$('#cmTbl td.cur').forEach(t => t.classList.remove('cur'));
    $$('#cmTbl th.hl').forEach(t => t.classList.remove('hl'));
    cur = rc; if (!rc) { readout(null); return; }
    const td = tdAt(...rc); if (td) { td.classList.add('cur'); ensureVisible(td, false); }
    hl(rc, true); readout(rc);
    if (announceIt) $('#heatLive').textContent = cellText(ROWS[rc[0]], COLS[rc[1]]);
  }
  function hl(rc, on){ if (!rc) return; const a = $(`#cmTbl th.rl[data-r="${rc[0]}"]`), b = $(`#cmTbl th.cl[data-c="${rc[1]}"]`); [a, b].forEach(x => x && x.classList.toggle('hl', on)); }
  function firstValid(){ for (let r = 0; r < ROWS.length; r++) for (let c = 0; c < COLS.length; c++) if (validCell(r, c)) return [r, c]; return null; }
  function stepCell([r, c], [dr, dc]){ let R = r + dr, C = c + dc; while (R >= 0 && C >= 0 && R < ROWS.length && C < COLS.length) { if (validCell(R, C)) return [R, C]; R += dr; C += dc; } return null; }

  /* события матрицы — один раз, делегированием на постоянном контейнере */
  (() => {
    const box = $('#heat'); let hov = null;
    box.addEventListener('mousemove', e => {
      const td = e.target.closest('td.v,td.nul');
      if (hov && (!td || hov.join() !== [+td.dataset.r, +td.dataset.c].join())) { hl(hov, false); if (cur) hl(cur, true); hov = null; }
      if (!td) { hideTip(); if (!cur) readout(null); return; }
      const rc = [+td.dataset.r, +td.dataset.c]; hov = rc; hl(rc, true); readout(rc); showTip(e, cellTip(ROWS[rc[0]], COLS[rc[1]]));
    });
    box.addEventListener('mouseleave', () => { hideTip(); if (hov) hl(hov, false); hov = null; if (cur) { hl(cur, true); readout(cur); } else readout(null); });
    box.addEventListener('click', e => {
      const td = e.target.closest('td.v'); if (!td) return;
      const rc = [+td.dataset.r, +td.dataset.c]; setCur(rc, false); hideTip();
      selectPairImpl(ROWS[rc[0]], COLS[rc[1]], {from: 'matrix', reveal: true});
    });
    // повторный вход клавишей Tab: курсор восстанавливается (blur снимает только класс, позиция cur сохраняется)
    box.addEventListener('focus', () => { if (!ROWS.length || !box.matches(':focus-visible')) return; setCur(cur && validCell(...cur) ? cur : (selPair && cellFor(...selPair)) || firstValid()); });
    box.addEventListener('blur', () => { $$('#cmTbl td.cur').forEach(t => t.classList.remove('cur')); });
    box.addEventListener('keydown', e => {
      if (!ROWS.length || e.target !== box) return;
      if (!cur) cur = (selPair && cellFor(...selPair)) || firstValid(); if (!cur) return;
      const mv = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]}[e.key];
      if (mv) { e.preventDefault(); const nx = stepCell(cur, mv); setCur(nx || cur); return; }
      if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); const r = cur[0]; const cs = COLS.map((v, c) => c).filter(c => validCell(r, c)); if (cs.length) setCur([r, e.key === 'Home' ? cs[0] : cs[cs.length - 1]]); return; }
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); const a = ROWS[cur[0]], b = COLS[cur[1]]; if (validCell(...cur) && rhoOf(a, b) != null) selectPairImpl(a, b, {from: 'matrix', reveal: true}); }
    });
  })();

  /* список пар (узкий экран и альтернатива матрице) */
  function renderList(){
    const q = norm(MS.q), vis = new Set(ORDV.filter(v => MS.groups.has(gOf(v))));
    const hit = v => norm(featLabel(v)).includes(q) || norm(GNAME(gOf(v))).includes(q);
    let L = ALLPAIRS.filter(p => vis.has(p.a) && vis.has(p.b) && (!q || hit(p.a) || hit(p.b)));
    const total = L.length, A = p => p.rho == null ? -1 : Math.abs(p.rho);
    const cmp = {abs: (x, y) => A(y) - A(x), neg: (x, y) => (x.rho ?? 9) - (y.rho ?? 9), pos: (x, y) => (y.rho ?? -9) - (x.rho ?? -9),
      q: (x, y) => (x.q ?? 9) - (y.q ?? 9) || A(y) - A(x), name: (x, y) => featLabel(x.a).localeCompare(featLabel(y.a), 'ru') || featLabel(x.b).localeCompare(featLabel(y.b), 'ru')}[MS.sort];
    L = L.slice().sort(cmp);
    const shown = L.slice(0, MS.listN), sk = selPair ? pairKey(...selPair) : '';
    $('#plCount').textContent = total ? `Показано ${shown.length} из ${fmtN(total)} пар` : '';
    $('#plUl').innerHTML = total ? shown.map(p => { const w = p.rho == null ? 0 : Math.abs(p.rho) * 50;
      return `<li><button type="button" class="cr-pli" data-a="${esc(p.a)}" data-b="${esc(p.b)}" aria-pressed="${pairKey(p.a, p.b) === sk}">
        <span class="cr-pln"><span>${esc(featLabel(p.a))}</span><span class="cr-plx" aria-hidden="true">↔</span><span>${esc(featLabel(p.b))}</span></span>
        <span class="cr-plv"><b class="mono" style="color:${rhoInk(p.rho)}">${p.rho == null ? 'н/д' : 'ρ ' + fmtSigned(p.rho, 2)}</b>
          <span class="rhobar" aria-hidden="true"><i style="${(p.rho || 0) >= 0 ? 'left:50%' : 'right:50%'};width:${w}%;background:${(p.rho || 0) >= 0 ? 'var(--rp2)' : 'var(--rn2)'}"></i></span>
          <span class="cr-plq mono">${fqEq(p.q)}${p.q != null && p.q >= .05 ? ' · незначимо' : ''}</span></span></button></li>`; }).join('')
      : `<li class="empty cr-empty"><b>Ничего не найдено</b><span>Нет пар для поиска «${esc(MS.q)}» в выбранных группах.</span></li>`;
    $('#plMore').hidden = shown.length >= total;
  }
  $('#plUl').addEventListener('click', e => { const b = e.target.closest('.cr-pli'); if (b) selectPairImpl(b.dataset.a, b.dataset.b, {from: 'list', reveal: true}); });
  $('#plMore').addEventListener('click', () => { MS.listN += 30; renderList(); });
  $('#plSort').addEventListener('change', e => { MS.sort = e.target.value; MS.listN = list0(); renderList(); });

  function renderMatrixArea(){
    const v = viewNow(), list = v === 'list';
    $$('#cmView [data-view]').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === v));
    const triDis = list || !!MS.q;
    $$('#triSeg [data-tri]').forEach(b => { b.setAttribute('aria-pressed', (b.dataset.tri === '1') === (MS.tri && !MS.q)); b.disabled = triDis; });
    $('#triSeg').title = list ? 'Форма относится к матрице' : MS.q ? 'При поиске показываются найденные строки против всех столбцов' : '';
    $('#heat').hidden = list; $('#pairList').hidden = !list; $('#cmRead').hidden = list;
    if (list) { $('#cmLegend').innerHTML = legendHtml(); readout(null); renderList(); $('#cmEc').hidden = true; }
    else heat();
  }
  $$('#cmView [data-view]').forEach(b => b.addEventListener('click', () => { MS.view = b.dataset.view; renderMatrixArea(); if (viewNow() !== 'list') requestAnimationFrame(() => scrollToCell()); }));
  $$('#triSeg [data-tri]').forEach(b => b.addEventListener('click', () => { MS.tri = b.dataset.tri === '1'; renderMatrixArea(); requestAnimationFrame(() => scrollToCell()); }));
  $('#cmSearch').addEventListener('input', e => { MS.q = e.target.value; MS.listN = list0(); renderMatrixArea(); });
  $$('#cmGroups [data-g]').forEach(b => b.addEventListener('click', () => {
    const g = +b.dataset.g;
    if (MS.groups.has(g)) { if (MS.groups.size === 1) { notify(b, 'Нужна хотя бы одна группа показателей.'); return; } MS.groups.delete(g); } else MS.groups.add(g);
    $$('#cmGroups [data-g]').forEach(x => x.setAttribute('aria-pressed', MS.groups.has(+x.dataset.g)));
    MS.listN = list0(); renderMatrixArea();
  }));
  narrowMQ.addEventListener('change', () => { if (!MS.view) renderMatrixArea(); });

  /* ======================================================================
     ПАРА: пузыри ↔ медианы по типам ↔ распределение по типам (ECharts)
     ====================================================================== */
  const BS = {mode: 'bub', size: 'pop', agg: 'y', xlog: false, ylog: false, zoom: null, focus: null};   // size — помнится в памяти сессии
  let PA = null, PB = null, PTS = [], PREC = null, GEO = null, CURD = [], LEGD = null, DRK = '';
  const PTSof = (a, b) => N.map((x, i) => ({i, x: getVar(i, a), y: getVar(i, b), pop: x.pop, c: x.c})).filter(p => p.x != null && p.y != null);
  const shareK = v => isShareVar(v) ? 100 : 1;
  const canLog = key => PTS.length > 0 && PTS.every(p => p[key] > 0);
  const aggVar = () => BS.agg === 'y' ? PB : PA;

  function typeStats(key){
    return TYPES.map((t, k) => { const s = PTS.filter(p => p.c === t.c).map(p => p[key]).sort((a, b) => a - b);
      return {c: t.c, k, n: s.length, med: q7(s, .5), q1: q7(s, .25), q3: q7(s, .75), min: s.length ? s[0] : null, max: s.length ? s[s.length - 1] : null}; });
  }
  /* границы оси: данные + отступ в пикселях (радиус пузыря); деления ставит ECharts, крайние нецелые подписи скрыты */
  function padDom(lo, hi, padPx, plotPx){
    if (lo === hi) { const d = Math.abs(lo) * .1 || 1; lo -= d; hi += d; }
    const span = hi - lo, pad = span * padPx / Math.max(40, plotPx - 2 * padPx);
    return {min: lo - pad, max: hi + pad};
  }
  function logDom(lo, hi, padPx, plotPx){   // lo/hi уже в log10
    if (lo === hi) { lo -= .1; hi += .1; }
    const span = hi - lo, pad = span * padPx / Math.max(40, plotPx - 2 * padPx); lo -= pad; hi += pad;
    const gen = ms => { const r = []; for (let e = Math.floor(lo); e <= Math.ceil(hi); e++) ms.forEach(m => { const l = Math.log10(m) + e; if (l >= lo && l <= hi) r.push(+l.toFixed(12)); }); return r; };
    let t = gen([1, 2, 5]);
    if (t.length < 4) t = gen([1, 2, 3, 5, 7]);
    if (t.length < 4) t = gen([1, 1.5, 2, 3, 4, 5, 6, 7, 8]);
    if (t.length > 7) t = t.filter(l => { const m = Math.round(10 ** (l - Math.floor(l + 1e-9))); return m === 1 || m === 5; });
    if (t.length < 2) t = [lo, hi];
    return {min: lo, max: hi, ticks: t};
  }
  function numTxt(v, d){ return (v < 0 ? '−' : '') + fmtN(Math.abs(v), d); }
  /* подпись деления: без хвостовых нулей, точность по величине (деления — «круглые» числа ECharts) */
  function tickFmt(share){ return v => { const a = Math.abs(v); if (a < 1e-12) return '0' + (share ? '%' : '');
    const d = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
    return (v < 0 ? '−' : '') + a.toLocaleString('ru-RU', {maximumFractionDigits: d}) + (share ? '%' : ''); }; }
  const edgeLabels = (ax, dom) => { ax.axisLabel.showMinLabel = Math.abs(dom.min) < 1e-12; ax.axisLabel.showMaxLabel = Math.abs(dom.max) < 1e-12; return ax; };
  function logTickFmt(share){ return l => { const v = 10 ** l, d = v >= 10 ? 0 : v >= 1 ? 1 : v >= .1 ? 2 : 3; return numTxt(+v.toPrecision(3), d) + (share ? '%' : ''); }; }

  /* геометрия сцены: высота одинакова во всех трёх режимах (зависит только от ширины) */
  function layoutStage(){
    const st = $('#bStage'), W = st.clientWidth; if (!W) return GEO;
    const narrow = W < 520, xs = W < 360, colW = clamp(Math.round(W * (xs ? .5 : narrow ? .46 : .34)), 120, 232);
    const col = $('#tyCol'); col.style.width = colW + 'px'; col.classList.toggle('xs', xs);
    let need = 0; col.querySelectorAll('.cr-tyrow').forEach(r => { const h0 = r.style.height; r.style.height = 'auto'; need = Math.max(need, r.offsetHeight); r.style.height = h0; });
    const top = 8, bottom = 30, base = narrow ? 400 : 440;
    const H = Math.max(base, Math.ceil(KT * Math.max(40, need + 8) + top + bottom));
    if (Math.abs(st.offsetHeight - H) > 1) st.style.height = H + 'px';
    GEO = {W, H, narrow, colW, top, bottom, band: (H - top - bottom) / KT,
      b: {left: narrow ? 50 : 58, right: 16, top: 12, bottom: 28}, a: {left: colW + 10, right: 18, top, bottom}};
    col.querySelectorAll('.cr-tyrow').forEach((r, k) => { r.style.top = (top + k * GEO.band) + 'px'; r.style.height = GEO.band + 'px'; });
    return GEO;
  }

  function T(){ return {ink: css('--ink'), ink2: css('--ink2'), muted: css('--muted'), surface: css('--surface'), line: css('--line'), soft: css('--line-soft'), strong: css('--line-strong'), pearl: css('--pearl-edge'), dark: isDark()}; }
  const UT = {enabled: true, divideShape: 'split', delay: (i, cnt) => cnt > 1 ? 70 * i / cnt : 0};
  const axisCommon = (t, fmt, extra = {}) => Object.assign({type: 'value', axisLabel: {formatter: fmt, color: t.ink2, fontSize: 11.5, hideOverlap: true},
    axisLine: {show: true, onZero: false, lineStyle: {color: t.strong}}, axisTick: {show: false}, splitLine: {show: true, lineStyle: {color: t.soft}}}, extra);

  function buildPair(chart, how){
    const G = GEO || layoutStage() || {W: 560, H: 440, colW: 190, top: 8, bottom: 30, band: 57, b: {left: 58, right: 16, top: 12, bottom: 28}, a: {left: 200, right: 18, top: 8, bottom: 30}};
    const W = chart ? chart.getWidth() : G.W, H = chart ? chart.getHeight() : G.H;
    const t = T(), dur = how === 'mode' ? 600 : how === 'data' ? 520 : how === 'resize' ? 0 : how === 'sel' ? 180 : 450;
    const o = {animationDuration: 450, animationDurationUpdate: dur, animationEasing: 'cubicOut', animationEasingUpdate: 'cubicInOut',
      textStyle: {fontFamily: 'Golos Text, system-ui, sans-serif'}, tooltip: {show: false}};
    CURD = [];
    if (!PA) return Object.assign(o, {series: []});
    if (BS.mode === 'med') return Object.assign(o, medOpt(G, W, H, t));
    if (BS.mode === 'dist') return Object.assign(o, distOpt(G, W, H, t));
    return Object.assign(o, bubOpt(G, W, H, t));
  }
  const fillA = t => t.dark ? .40 : .34;
  function ptStyle(p, t, eq){
    const col = COL(p.c), on = BS.focus == null || BS.focus === p.c, isSel = p.i === sel;
    return {color: rgba(col, eq ? (t.dark ? .72 : .66) : fillA(t)), borderColor: col, borderWidth: isSel ? 1.8 : 1, opacity: on ? 1 : .16};
  }
  function selRing(t, pos, d, labelPos){
    const sp = PTS.find(p => p.i === sel);
    return {id: 'selRing', type: 'scatter', silent: true, z: 10, animationDurationUpdate: 180,
      data: sp && pos ? [{value: pos(sp), symbolSize: d(sp) + 9}] : [],
      // opacity: 1 — у scatter по умолчанию 0,8, и подпись выбранного МО наследовала бы её
      itemStyle: {color: 'rgba(0,0,0,0)', borderColor: t.pearl, borderWidth: 2, opacity: 1, shadowBlur: t.dark ? 12 : 6, shadowColor: rgba(t.pearl, t.dark ? .7 : .45)},
      // подпись — с ореолом по контуру букв, без непрозрачной плашки: соседние точки под подписью остаются видны
      label: {show: !!labelPos, formatter: sp ? N[sp.i].s : '', position: labelPos && sp ? labelPos(sp) : 'right', distance: 6, color: t.ink, fontSize: 12.5, fontWeight: 600,
        textBorderColor: rgba(t.surface, .9), textBorderWidth: 3}};
  }
  /* лог-деления для полного домена или окна увеличения (значения — log10 в единицах оси) */
  function logTicksNow(dx, dy, zoom){
    const pick = (d, z) => !d.ticks ? null : z ? logDom(z[0], z[1], 0, 300).ticks.filter(v => v >= z[0] - 1e-9 && v <= z[1] + 1e-9) : d.ticks;
    return {x: pick(dx, zoom && zoom.x), y: pick(dy, zoom && zoom.y)};
  }
  function logGrid(tx, ty, dx, dy){ const g = [];
    if (tx) tx.forEach(v => g.push([[v, dy.min], [v, dy.max]]));
    if (ty) ty.forEach(v => g.push([[dx.min, v], [dx.max, v]])); return g; }
  function bubOpt(G, W, H, t){
    const g = G.b, pw = W - g.left - g.right, ph = H - g.top - g.bottom;
    const sx = shareK(PA), sy = shareK(PB), lx = BS.xlog && canLog('x'), ly = BS.ylog && canLog('y');
    const tx = v => lx ? Math.log10(v * sx) : v * sx, ty = v => ly ? Math.log10(v * sy) : v * sy;
    const eq = BS.size === 'eq', Dmax = clamp(.15 * Math.min(pw, ph), 26, 64);
    G.Dmax = Dmax;
    const diam = p => eq ? 9 : Dmax * Math.sqrt((p.pop || 0) / POPMAX);   // площадь ∝ населению: d = 2·√(K·pop/π), K = π(Dmax/2)²/popmax
    const rmax = PTS.length ? Math.max(...PTS.map(diam)) / 2 : 5;
    const xs = PTS.map(p => tx(p.x)), ys = PTS.map(p => ty(p.y));
    const dx = lx ? logDom(Math.min(...xs), Math.max(...xs), rmax + 4, pw) : padDom(Math.min(...xs), Math.max(...xs), rmax + 4, pw);
    const dy = ly ? logDom(Math.min(...ys), Math.max(...ys), rmax + 4, ph) : padDom(Math.min(...ys), Math.max(...ys), rmax + 4, ph);
    const order = PTS.slice().sort((a, b) => (b.pop || 0) - (a.pop || 0) || a.i - b.i);   // крупные снизу, мелкие сверху
    const data = order.map(p => ({id: 'm' + p.i, groupId: 't' + p.c, name: N[p.i].s, value: [tx(p.x), ty(p.y)], symbolSize: diam(p), itemStyle: ptStyle(p, t, eq)}));
    CURD = order.map((p, k) => ({p, d: diam(p), v: data[k].value}));
    const zx = BS.zoom ? BS.zoom.x : [dx.min, dx.max], zy = BS.zoom ? BS.zoom.y : [dy.min, dy.max];
    const zoomed = !!BS.zoom;
    const xAxis = axisCommon(t, lx ? logTickFmt(isShareVar(PA)) : tickFmt(isShareVar(PA)), {min: dx.min, max: dx.max, splitNumber: G.narrow ? 4 : 5});
    const yAxis = axisCommon(t, ly ? logTickFmt(isShareVar(PB)) : tickFmt(isShareVar(PB)), {min: dy.min, max: dy.max, splitNumber: 5});
    // лог-деления — по видимому окну (при увеличении их пересчитывает и обработчик datazoom), иначе в окне остаётся 1–2 подписи
    const tks = logTicksNow(dx, dy, zoomed ? {x: zx, y: zy} : null);
    if (lx) { xAxis.axisLabel.customValues = tks.x; xAxis.axisTick = {show: false, customValues: tks.x}; xAxis.splitLine.show = false; } else edgeLabels(xAxis, dx);
    if (ly) { yAxis.axisLabel.customValues = tks.y; yAxis.axisTick = {show: false, customValues: tks.y}; yAxis.splitLine.show = false; } else edgeLabels(yAxis, dy);
    const series = [{id: 'pts', type: 'scatter', universalTransition: UT, data, z: 3, cursor: 'pointer',
      emphasis: {scale: false, itemStyle: {borderColor: t.ink, borderWidth: 1.8}}}];
    // лог-оси: сетка на делениях лог-шкалы (собственные линии, чтобы совпадали с подписями)
    const glines = logGrid(lx && tks.x, ly && tks.y, dx, dy);
    if (glines.length) series.unshift({id: 'loggrid', type: 'lines', coordinateSystem: 'cartesian2d', silent: true, z: 0, animation: false, polyline: false,
      data: glines.map(c => ({coords: c})), lineStyle: {color: t.soft, width: 1, opacity: 1}});
    const fr = sp => { const [x0, x1] = zx; return (tx(sp.x) - x0) / ((x1 - x0) || 1); };
    series.push(selRing(t, sp => [tx(sp.x), ty(sp.y)], diam, sp => fr(sp) > .62 ? 'left' : 'right'));
    const dz = (ax, z, full) => Object.assign({type: 'inside', id: 'dz' + ax, [ax === 'x' ? 'xAxisIndex' : 'yAxisIndex']: 0, filterMode: 'none',
      zoomOnMouseWheel: 'ctrl', moveOnMouseWheel: false, moveOnMouseMove: zoomed, preventDefaultMouseMove: zoomed},
      zoomed ? {startValue: z[0], endValue: z[1]} : {start: 0, end: 100});
    BS.dom = {x: [dx.min, dx.max], y: [dy.min, dy.max]}; BS.ldom = {dx, dy, lx, ly};
    return {grid: Object.assign({}, g), xAxis, yAxis, series, dataZoom: [dz('x', zx), dz('y', zy)]};
  }
  function aggAxisFmt(v){ return tickFmt(isShareVar(v)); }
  function medOpt(G, W, H, t){
    const g = G.a, pw = W - g.left - g.right, v = aggVar(), s = shareK(v), st = typeStats(BS.agg);
    const labs = st.map(x => x.med == null ? '' : fmtVar(v, x.med));
    const meds = st.filter(x => x.med != null).map(x => x.med * s);
    let lo = Math.min(0, ...meds), hi = Math.max(0, ...meds); if (lo === hi) hi = lo + 1;
    // запас под подписи только с тех сторон нуля, где есть столбцы (все медианы < 0 — подписи только слева)
    const sides = (meds.some(m => m < 0) ? 1 : 0) + (meds.some(m => m > 0) ? 1 : 0) || 1;
    const lw = Math.max(0, ...labs.map(l => textW(l, FONT_NUM))) + 12, span = hi - lo, k = span / Math.max(40, pw - sides * lw);
    if (hi > 0) hi += lw * k; if (lo < 0) lo -= lw * k;
    const dom = {min: lo, max: hi};
    const bw = clamp(G.band * .46, 8, 26);
    const data = st.map(x => { const col = COL(x.c), on = BS.focus == null || BS.focus === x.c;
      return {id: 'type' + x.c, groupId: 't' + x.c, name: typeName(x.c), value: x.med == null ? '-' : x.med * s,
        // фокус типа приглушает заливку остальных столбцов, но не их числа: подпись медианы остаётся читаемой (--muted ≥ 4,5:1)
        itemStyle: {color: rgba(col, on ? (t.dark ? .78 : .72) : (t.dark ? .2 : .16)), borderColor: on ? col : rgba(col, .45), borderWidth: 1, borderRadius: x.med != null && x.med < 0 ? [2, 0, 0, 2] : [0, 2, 2, 0], opacity: 1},
        label: {show: x.med != null, position: x.med != null && x.med < 0 ? 'left' : 'right', distance: 6, formatter: labs[x.k], color: on ? t.ink : t.muted, fontFamily: 'JetBrains Mono, monospace', fontSize: 12, fontWeight: 500}}; });
    const xAxis = edgeLabels(axisCommon(t, aggAxisFmt(v), {min: dom.min, max: dom.max, splitNumber: G.narrow ? 3 : 4}), dom);
    const yAxis = {type: 'category', data: TYPES.map(x => 't' + x.c), inverse: true, axisLabel: {show: false}, axisTick: {show: false},
      axisLine: {show: true, onZero: true, lineStyle: {color: t.ink2, width: 1.2}}, splitLine: {show: false}};
    const series = [{id: 'pts', type: 'bar', universalTransition: UT, barWidth: bw, data, z: 3, cursor: 'pointer', emphasis: {focus: 'none', itemStyle: {borderColor: t.ink, borderWidth: 1.5}}}];
    const sp = PTS.find(p => p.i === sel);
    series.push(selRing(t, p => [p[BS.agg] * s, TIDX[p.c]], () => 9, null));
    if (sp) series[series.length - 1].itemStyle.borderWidth = 2.2;
    return {grid: Object.assign({}, g), xAxis, yAxis, series};
  }
  function distOpt(G, W, H, t){
    const g = G.a, pw = W - g.left - g.right, v = aggVar(), s = shareK(v), key = BS.agg, st = typeStats(key);
    const vals = PTS.map(p => p[key] * s), r = G.narrow ? 4 : 4.5;
    const dom = padDom(Math.min(...vals), Math.max(...vals), r + 6, pw);
    const X = val => (val - dom.min) / ((dom.max - dom.min) || 1) * pw;
    const lim = Math.max(0, G.band / 2 - r - 3), sep = 2 * r + 1;
    const off = {};
    TYPES.forEach(ty => {   // dodge: смещение только поперёк числовой оси, значение по X не меняется
      const ps = PTS.filter(p => p.c === ty.c).map(p => ({p, x: X(p[key] * s)})).sort((a, b) => a.x - b.x || a.p.i - b.p.i), placed = [];
      ps.forEach(q => { let best = 0, bestOv = Infinity;
        for (let k = 0; k <= 2 * Math.ceil(lim / 1.5) + 1; k++) {
          const y = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 1.5; if (Math.abs(y) > lim) continue;
          let ov = 0; placed.forEach(z => { const d = Math.hypot(q.x - z.x, y - z.y); if (d < sep) ov = Math.max(ov, sep - d); });
          if (ov === 0) { best = y; bestOv = 0; break; } if (ov < bestOv) { bestOv = ov; best = y; } }
        placed.push({x: q.x, y: best}); off[q.p.i] = best / G.band; });
    });
    const order = PTS.slice().sort((a, b) => (b.pop || 0) - (a.pop || 0) || a.i - b.i);
    const data = order.map(p => ({id: 'm' + p.i, groupId: 't' + p.c, name: N[p.i].s, value: [p[key] * s, TIDX[p.c] + off[p.i]], symbolSize: 2 * r, itemStyle: ptStyle(p, t, true)}));
    CURD = order.map((p, k) => ({p, d: 2 * r, v: data[k].value}));
    const xAxis = edgeLabels(axisCommon(t, aggAxisFmt(v), {min: dom.min, max: dom.max, splitNumber: G.narrow ? 3 : 5}), dom);
    const yAxis = {type: 'value', min: -.5, max: KT - .5, inverse: true, axisLabel: {show: false}, axisTick: {show: false}, axisLine: {show: false}, splitLine: {show: false}};
    const box = st.filter(x => x.n > 0).map(x => [x.q1 * s, x.q3 * s, x.med * s, x.k, x.c, x.n]);
    const series = [
      {id: 'rows', type: 'custom', silent: true, z: 0, animation: false, data: TYPES.slice(1).map((x, k) => [k + .5]),
        renderItem: (p, api) => { const cs = p.coordSys, y = api.coord([dom.min, api.value(0)])[1];
          return {type: 'line', shape: {x1: cs.x, y1: y, x2: cs.x + cs.width, y2: y}, style: {stroke: t.soft, lineWidth: 1}}; }},
      {id: 'iqr', type: 'custom', z: 1, data: box, encode: {x: [0, 1, 2], y: 3},
        renderItem: (p, api) => { const k = api.value(3), c = api.value(4), a = api.coord([api.value(0), k]), b = api.coord([api.value(1), k]), m = api.coord([api.value(2), k]);
          const h = clamp(G.band * .5, 12, 26), col = COL(c), on = BS.focus == null || BS.focus === c;
          return {type: 'group', children: [
            {type: 'rect', shape: {x: a[0], y: a[1] - h / 2, width: Math.max(1, b[0] - a[0]), height: h, r: 3}, style: {fill: rgba(col, t.dark ? .20 : .14), stroke: rgba(col, .7), lineWidth: 1, opacity: on ? 1 : .3}},
            {type: 'line', shape: {x1: m[0], y1: m[1] - h / 2 - 3, x2: m[0], y2: m[1] + h / 2 + 3}, style: {stroke: t.ink, lineWidth: 2, opacity: on ? 1 : .35}}]}; }},
      {id: 'pts', type: 'scatter', universalTransition: UT, data, z: 3, cursor: 'pointer', emphasis: {scale: false, itemStyle: {borderColor: t.ink, borderWidth: 1.8}}},
      selRing(t, p => [p[key] * s, TIDX[p.c] + off[p.i]], () => 2 * r, sp => X(sp[key] * s) / pw > .6 ? 'left' : 'right')];
    return {grid: Object.assign({}, g), xAxis, yAxis, series};
  }

  /* ---------- подсказки и выбор на диаграмме: ближайшая точка с увеличенной зоной попадания ---------- */
  function nearestPt(chart, x, y){
    let best = null, bd = Infinity;
    CURD.forEach(q => { const px = chart.convertToPixel({seriesId: 'pts'}, q.v); if (!px) return;
      const d = Math.hypot(px[0] - x, px[1] - y), lim = Math.max(q.d / 2, 6) + 5; if (d <= lim && d < bd) { bd = d; best = q; } });
    return best;
  }
  function ptTip(i){
    const x = getVar(i, PA), y = getVar(i, PB);
    return `<b>${esc(N[i].s)}</b><div class="tsub"><span class="sw" style="--c:${COLV(N[i].c)}"></span> ${esc(typeName(N[i].c))}</div>
      <div class="tnum">X: ${esc(fmtVar(PA, x))}</div><div class="tsub">${esc(axisCaption(PA))}</div>
      <div class="tnum">Y: ${esc(fmtVar(PB, y))}</div><div class="tsub">${esc(axisCaption(PB))}</div>
      <div class="tnum">население: ${fmtN(N[i].pop)} чел.</div>`;
  }
  function typeTip(c){
    const v = aggVar(), x = typeStats(BS.agg)[TIDX[c]];
    return `<b><span class="sw" style="--c:${COLV(c)}"></span> ${esc(typeName(c))}</b><div class="tnum">n = ${x.n} МО с обоими значениями</div>`
      + (x.n ? `<div class="tnum">медиана: ${esc(fmtVar(v, x.med))}</div><div class="tnum">Q1–Q3: ${esc(fmtVar(v, x.q1))} … ${esc(fmtVar(v, x.q3))}</div>` : '<div>нет данных</div>')
      + `<div class="tsub">${esc(axisCaption(v))}</div>`;
  }
  function bindPair(chart){
    const zr = chart.getZr();
    zr.on('mousemove', e => {
      if (BS.mode === 'med' || !PA) return;
      const q = nearestPt(chart, e.offsetX, e.offsetY);
      zr.setCursorStyle(q ? 'pointer' : 'default');
      if (q) { showTip(e.event, ptTip(q.p.i)); return; }
      if (BS.mode === 'dist' && chart.containPixel({gridIndex: 0}, [e.offsetX, e.offsetY])) {
        const v = chart.convertFromPixel({gridIndex: 0}, [e.offsetX, e.offsetY]), k = Math.round(v[1]), x = typeStats(BS.agg)[k], s = shareK(aggVar());
        if (x && x.n && v[0] >= x.q1 * s && v[0] <= x.q3 * s) { showTip(e.event, typeTip(x.c)); return; }
      }
      hideTip();
    });
    zr.on('globalout', hideTip);
    zr.on('click', e => {
      if (BS.mode === 'med' || !PA) return;
      const q = nearestPt(chart, e.offsetX, e.offsetY); if (q) { hideTip(); setSel(sel === q.p.i ? null : q.p.i); }
    });
    chart.on('mousemove', p => {
      if (BS.mode === 'med' && p.seriesId === 'pts') showTip(p.event.event, typeTip(TYPES[p.dataIndex].c));
    });
    chart.on('mouseout', p => { if (BS.mode === 'med' && p.seriesId === 'pts') hideTip(); });
    chart.on('click', p => { if (BS.mode === 'med' && p.seriesId === 'pts') setFocus(TYPES[p.dataIndex].c); });
    chart.on('datazoom', () => {
      if (BS.mode !== 'bub') return;
      const o = chart.getOption(), zx = o.dataZoom && o.dataZoom[0], zy = o.dataZoom && o.dataZoom[1];
      if (!zx || !zy || !BS.dom) return;
      const full = z => z.start <= .01 && z.end >= 99.99, val = (z, d) => [d[0] + z.start / 100 * (d[1] - d[0]), d[0] + z.end / 100 * (d[1] - d[0])];
      const wasZ = !!BS.zoom;
      BS.zoom = full(zx) && full(zy) ? null : {x: val(zx, BS.dom.x), y: val(zy, BS.dom.y)};
      $('#bReset').disabled = !BS.zoom;
      if (wasZ !== !!BS.zoom) chart.setOption({dataZoom: [{id: 'dzx', moveOnMouseMove: !!BS.zoom, preventDefaultMouseMove: !!BS.zoom}, {id: 'dzy', moveOnMouseMove: !!BS.zoom, preventDefaultMouseMove: !!BS.zoom}]});
      const L = BS.ldom;
      if (L && (L.lx || L.ly)) {   // лог-шкала: деления и сетка — по новому окну
        const tk = logTicksNow(L.dx, L.dy, BS.zoom), u = {series: [{id: 'loggrid', data: logGrid(L.lx && tk.x, L.ly && tk.y, L.dx, L.dy).map(c => ({coords: c}))}]};
        if (L.lx) u.xAxis = [{axisLabel: {customValues: tk.x}, axisTick: {customValues: tk.x}}];
        if (L.ly) u.yAxis = [{axisLabel: {customValues: tk.y}, axisTick: {customValues: tk.y}}];
        chart.setOption(u);
      }
    });
  }
  function drawPair(how){
    hideTip();
    if (!PREC || !PREC.chart) return;
    if (how !== 'resize' && how !== 'sel') layoutStage();
    const opt = withMotion(buildPair(PREC.chart, how));
    if (how === 'sel' || how === 'resize') PREC.chart.setOption(opt, {replaceMerge: ['series']}); else PREC.chart.setOption(opt, {notMerge: true});
    $('#bReset').disabled = !BS.zoom;
    if (BS.mode === 'bub' && GEO && GEO.Dmax !== LEGD) legend();   // легенда размера — тем же K, что и пузыри
  }
  function zoomBy(f){
    if (BS.mode !== 'bub' || !BS.dom || !PREC || !PREC.chart) return;
    const z = BS.zoom || {x: BS.dom.x.slice(), y: BS.dom.y.slice()};
    const sc = (a, d) => { const c = (a[0] + a[1]) / 2, h = (a[1] - a[0]) / 2 * f; let lo = c - h, hi = c + h;
      if (hi - lo >= d[1] - d[0]) return d.slice(); if (lo < d[0]) { hi += d[0] - lo; lo = d[0]; } if (hi > d[1]) { lo -= hi - d[1]; hi = d[1]; } return [lo, hi]; };
    const nx = sc(z.x, BS.dom.x), ny = sc(z.y, BS.dom.y);
    PREC.chart.dispatchAction({type: 'dataZoom', batch: [{dataZoomId: 'dzx', startValue: nx[0], endValue: nx[1]}, {dataZoomId: 'dzy', startValue: ny[0], endValue: ny[1]}]});
  }

  /* ---------- HTML вокруг диаграммы ---------- */
  function syncTools(){
    $$('#bMode [data-bm]').forEach(b => b.setAttribute('aria-pressed', b.dataset.bm === BS.mode));
    /* обе группы в одной ячейке сетки: неактивная скрыта visibility (не в Tab и не в дереве доступности), высота строки не меняется —
       график не прыгает при переходе «пузыри ↔ агрегаты» */
    $('#bBubTools').classList.toggle('off', BS.mode !== 'bub'); $('#bAggTools').classList.toggle('off', BS.mode === 'bub');
    $('#scTypes').hidden = BS.mode !== 'bub';   // в агрегатах легенду и выбор типа даёт колонка названий слева — без дубля семи длинных названий
    $$('#bSize [data-bs]').forEach(b => b.setAttribute('aria-pressed', b.dataset.bs === BS.size));
    const cx = canLog('x'), cy = canLog('y');
    $$('#bLog [data-lg]').forEach(b => { const ok = b.dataset.lg === 'x' ? cx : cy; b.disabled = !ok; b.setAttribute('aria-pressed', ok && BS[b.dataset.lg + 'log']);
      b.title = ok ? 'Логарифмическая шкала ' + b.dataset.lg.toUpperCase() : 'Лог-шкала недоступна: есть нулевые или отрицательные значения'; });
    $$('#bAgg [data-ag]').forEach(b => { b.setAttribute('aria-pressed', b.dataset.ag === BS.agg); b.title = featLabel(b.dataset.ag === 'y' ? PB || '' : PA || ''); });
    $('#bReset').disabled = !BS.zoom;
  }
  function captions(){
    if (!PA) return;
    const lx = BS.xlog && canLog('x'), ly = BS.ylog && canLog('y');
    /* подпись оси Y: все три варианта в одной ячейке сетки, виден текущий — высота по самому длинному,
       поэтому график не сдвигается при смене режима ни на какой ширине */
    const capY = {bub: `<span class="cr-axk">Y ↑</span><span>${esc(axisCaption(PB))}${ly ? ' · <b>логарифмическая шкала</b>' : ''}</span>`,
      med: '<span class="cr-axk">Тип МО</span><span>столбец — медиана по МО типа, от нуля</span>',
      dist: '<span class="cr-axk">Тип МО</span><span>точка — МО · полоса — Q1–Q3 · черта — медиана</span>'};
    $('#bCapY').innerHTML = ['bub', 'med', 'dist'].map(m => `<span class="cr-capv${m === BS.mode ? ' on' : ''}">${capY[m]}</span>`).join('');
    if (BS.mode === 'bub') {
      $('#bCapX').innerHTML = `<span>${esc(axisCaption(PA))}${lx ? ' · <b>логарифмическая шкала</b>' : ''}</span><span class="cr-axk">→ X</span>`;
    } else {
      const v = aggVar();
      $('#bCapX').innerHTML = `<span>${BS.mode === 'med' ? 'медиана: ' : ''}${esc(axisCaption(v))} <span class="muted">(${BS.agg.toUpperCase()}, линейная шкала)</span></span><span class="cr-axk">→ ${BS.agg.toUpperCase()}</span>`;
    }
    const nm = {bub: 'Пузырьковая диаграмма', med: 'Медианы по типам', dist: 'Распределение по типам'}[BS.mode];
    $('#bubble').setAttribute('aria-label', `${nm}: X — ${featLabel(PA)}, Y — ${featLabel(PB)}; ${PTS.length} МО из ${n}. Точные значения — в карточке МО и таблицах ниже.`);
  }
  function typeCol(){   // строки строятся один раз; дальше меняются только n и состояние (фокус клавиатуры не теряется)
    const st = typeStats(BS.agg), col = $('#tyCol');
    col.classList.toggle('on', BS.mode !== 'bub');
    if (col.children.length !== st.length) {
      col.innerHTML = st.map(x => `<button type="button" class="cr-tyrow" data-c="${x.c}"><span class="sw" style="--c:${COLV(x.c)}" aria-hidden="true"></span><span class="cr-tyt">${esc(typeName(x.c))} <span class="cr-tyn mono"></span></span></button>`).join('');
      if (GEO) col.querySelectorAll('.cr-tyrow').forEach((r, k) => { r.style.top = (GEO.top + k * GEO.band) + 'px'; r.style.height = GEO.band + 'px'; });
    }
    col.querySelectorAll('.cr-tyrow').forEach((r, k) => { const x = st[k];
      r.setAttribute('aria-pressed', BS.focus === x.c); r.tabIndex = BS.mode === 'bub' ? -1 : 0;
      r.querySelector('.cr-tyn').textContent = `n = ${x.n}${x.n ? '' : ' · нет данных'}`; });
  }
  $('#tyCol').addEventListener('click', e => { const b = e.target.closest('.cr-tyrow'); if (b) setFocus(+b.dataset.c); });
  function setFocus(c){ BS.focus = BS.focus === c ? null : c; typeCol(); legend(); drill(); drawPair('sel');
    announce(BS.focus == null ? 'Выделение типа снято' : 'Выделен тип: ' + typeName(c)); }

  function sizeLegend(){
    const Dm = GEO && GEO.Dmax ? GEO.Dmax : 50, vals = [20000, 200000, 1000000].filter(v => v <= POPMAX * 1.05);
    const ds = vals.map(v => Dm * Math.sqrt(v / POPMAX)), H = Math.ceil(Math.max(...ds)) + 2;
    return `<div class="cr-sizeleg" aria-label="Легенда размера: площадь круга пропорциональна населению">${vals.map((v, k) => `<span><svg width="${Math.ceil(ds[k]) + 2}" height="${H}" aria-hidden="true"><circle cx="${ds[k] / 2 + 1}" cy="${H - ds[k] / 2 - 1}" r="${ds[k] / 2}" fill="none" stroke="var(--ink2)" stroke-width="1"/></svg><span class="mono">${fmtN(v)} чел.</span></span>`).join('')}
      <span class="cr-sznote">площадь круга ∝ населению (диаметр ∝ √население); масштаб общий для всех пар</span></div>`;
  }
  function legend(){
    if (!PA) return;
    const miss = N.map((x, i) => i).filter(i => getVar(i, PA) == null || getVar(i, PB) == null);
    const missTxt = miss.length ? ` Нет на диаграмме (${miss.length}): ${miss.map(i => `${esc(N[i].s)} — нет ${[getVar(i, PA) == null ? 'X' : '', getVar(i, PB) == null ? 'Y' : ''].filter(Boolean).join(' и ')}`).join('; ')}. Пропуски не заменены нулями.` : '';
    const tl = $('#scTypes');
    if (!tl.children.length) tl.innerHTML = TYPES.map(x => `<button type="button" class="cr-tchip" data-c="${x.c}"><span class="sw" style="--c:${COLV(x.c)}" aria-hidden="true"></span>${esc(x.name)}</button>`).join('');
    tl.querySelectorAll('.cr-tchip').forEach(b => b.setAttribute('aria-pressed', BS.focus === +b.dataset.c));
    let body = '';
    if (BS.mode === 'bub') {
      const lx = BS.xlog && canLog('x'), ly = BS.ylog && canLog('y');
      const logNote = [!canLog('x') ? 'X' : '', !canLog('y') ? 'Y' : ''].filter(Boolean);
      LEGD = GEO && GEO.Dmax;
      body = (BS.size === 'pop' ? sizeLegend() : `<p class="note"><b>Одинаковые точки:</b> размер не кодирует население (дополнительный режим рассеяния).</p>`)
        + `<p class="note">n = <b>${PTS.length}</b> МО с обоими значениями из ${n}. Одна точка — один МО; цвет — тип${BS.size === 'pop' ? '; крупные круги лежат ниже мелких' : ''}. Оси: ${lx || ly ? `${lx ? 'X логарифмическая' : 'X линейная'}, ${ly ? 'Y логарифмическая' : 'Y линейная'}` : 'линейные'}${logNote.length ? `; лог-шкала ${logNote.join(' и ')} недоступна: есть нулевые или отрицательные значения` : ''}. Ctrl + колесо или кнопки ± — масштаб, перетаскивание — сдвиг увеличенной области. Линия регрессии не строится.${missTxt}</p>`;
    } else if (BS.mode === 'med') {
      body = `<p class="note">Медиана «${esc(featLabel(aggVar()))}» по ${KT} типам на тех же ${PTS.length} МО, у которых есть обе координаты; n — число таких МО в типе. Тип без данных показан как «нет данных», а не нулевой столбец. Медиана не суммирует доли и индексы. ρ, q и частная корреляция выше рассчитаны по отдельным МО, а не по медианам типов. Нажмите на строку типа — ниже откроется его состав.${missTxt}</p>`;
    } else {
      body = `<p class="note">Каждая точка — МО (размер одинаковый); внутри строки типа точки разнесены только по вертикали, значение по горизонтали не меняется. Полоса — межквартильный размах Q1–Q3 (разброс наблюдений, не доверительный интервал), черта — медиана. Квартили — линейная интерполяция порядковых статистик (метод R-7, как d3.quantile / numpy). n = ${PTS.length} МО с обеими координатами; ρ и q — по отдельным МО.${missTxt}</p>`;
    }
    $('#scBody').innerHTML = body;
  }
  $('#scTypes').addEventListener('click', e => { const b = e.target.closest('.cr-tchip'); if (b) setFocus(+b.dataset.c); });

  function drill(){
    const el = $('#typeDrill');
    if (BS.focus == null || !PA) { el.innerHTML = ''; DRK = ''; return; }
    const c = BS.focus, key = BS.agg, v = key === 'y' ? PB : PA, x = typeStats(key)[TIDX[c]];
    const k = [c, PA, PB, key].join('|');
    if (k === DRK) { el.querySelectorAll('.cr-drl [data-i]').forEach(b => b.setAttribute('aria-pressed', +b.dataset.i === sel)); return; }
    DRK = k;
    const ps = PTS.filter(p => p.c === c).sort((a, b) => b[key] - a[key]);
    const missing = MOS_OF(c).filter(i => !PTS.some(p => p.i === i));
    el.innerHTML = `<div class="cr-drill"><div class="cr-drh"><b><span class="sw" style="--c:${COLV(c)}" aria-hidden="true"></span>${esc(typeName(c))}</b>
      <button type="button" class="btn ghost sm" data-unfocus>Снять выделение</button></div>
      <div class="hint">n = ${x.n}${x.n ? ` · медиана ${esc(fmtVar(v, x.med))} · Q1–Q3 ${esc(fmtVar(v, x.q1))} … ${esc(fmtVar(v, x.q3))}` : ' · нет данных'} — по «${esc(featLabel(v))}», по убыванию:</div>
      <div class="cr-drl">${ps.map(p => `<button type="button" data-i="${p.i}" aria-pressed="${p.i === sel}"><span>${esc(N[p.i].s)}</span><span class="mono">${esc(fmtVar(v, p[key]))}</span></button>`).join('')}</div>
      ${missing.length ? `<div class="hint">Без пары значений: ${missing.map(i => esc(N[i].s)).join(', ')}.</div>` : ''}</div>`;
  }
  $('#typeDrill').addEventListener('click', e => {
    if (e.target.closest('[data-unfocus]')) { const c = BS.focus; setFocus(c); (BS.mode === 'bub' ? $(`#scTypes .cr-tchip[data-c="${c}"]`) : $(`#tyCol .cr-tyrow[data-c="${c}"]`)).focus(); return; }
    const b = e.target.closest('[data-i]'); if (b) setSel(+b.dataset.i);
  });

  function moCard(){
    $('#moSel').value = sel == null ? '' : String(sel);
    const el = $('#moCard');
    if (sel == null || !N[sel] || !PA) { el.innerHTML = `<p class="hint">Выберите МО на диаграмме, в списке выше или в любой вкладке — он подсветится кольцом здесь и на карте.</p>`; return; }
    const i = sel, x = getVar(i, PA), y = getVar(i, PB), on = x != null && y != null;
    el.innerHTML = `<div class="cr-mocard"><div class="cr-moh"><b>${esc(N[i].s)}</b><span class="tag"><span class="sw" style="--c:${COLV(N[i].c)}" aria-hidden="true"></span>${esc(typeName(N[i].c))}</span></div>
      <dl class="cr-mov"><div><dt>X · ${esc(featLabel(PA))}</dt><dd class="mono">${x == null ? NA : esc(fmtVar(PA, x))}</dd></div>
        <div><dt>Y · ${esc(featLabel(PB))}</dt><dd class="mono">${y == null ? NA : esc(fmtVar(PB, y))}</dd></div>
        <div><dt>Население</dt><dd class="mono">${fmtN(N[i].pop)} чел.</dd></div></dl>
      ${on ? '' : `<p class="note">Этого МО нет на диаграмме пары: нет значения ${x == null && y == null ? 'X и Y' : x == null ? 'X' : 'Y'} (пропуск не заменён нулём).</p>`}
      <div class="cr-acts"><button type="button" class="btn sm" data-gomap="${i}">${ICON.map}<span>На карте</span></button>${cmpToggle(i, 'btn sm')}<button type="button" class="btn ghost sm" data-unsel>Снять выбор</button></div></div>`;
  }
  $('#moSel').addEventListener('change', e => setSel(e.target.value === '' ? null : +e.target.value));
  $('#moCard').addEventListener('click', e => {
    const g = e.target.closest('[data-gomap]'); if (g) { goMap(+g.dataset.gomap); return; }
    if (e.target.closest('[data-unsel]')) { setSel(null); $('#moSel').focus(); }
  });

  function tables(){   // содержимое раскрывающихся таблиц строится только когда они открыты
    if (!PA) return;
    const key = BS.agg, v = aggVar(), st = typeStats(key);
    $('#tyTabS').textContent = `Медиана и квартили по типам — ${BS.agg.toUpperCase()}: ${featLabel(v)}`;
    $('#ptTabS').textContent = `Значения пары по всем ${n} МО (${PTS.length} на диаграмме, ${n - PTS.length} без значения)`;
    $('#tyTab').innerHTML = !$('#tyTabD').open ? '' : `<div class="tbox"><table><caption class="sr">Медиана, Q1, Q3 и n по типам МО</caption><thead><tr><th scope="col">Тип</th><th class="n" scope="col">n</th><th class="n" scope="col">Q1</th><th class="n" scope="col">медиана</th><th class="n" scope="col">Q3</th></tr></thead><tbody>${st.map(x =>
      `<tr><th scope="row" style="font-weight:400"><span class="sw" style="--c:${COLV(x.c)}" aria-hidden="true"></span> ${esc(typeName(x.c))}</th><td class="n">${x.n}</td>${x.n ? `<td class="n">${esc(fmtVar(v, x.q1))}</td><td class="n">${esc(fmtVar(v, x.med))}</td><td class="n">${esc(fmtVar(v, x.q3))}</td>` : `<td class="n" colspan="3">${NA}</td>`}</tr>`).join('')}</tbody></table></div>
      <p class="note">Квартили — метод R-7 (линейная интерполяция порядковых статистик) по фактической выборке пары; IQR — разброс наблюдений, не доверительный интервал медианы.</p>`;
    const all = TYPES.flatMap(t => MOS_OF(t.c));
    $('#ptTab').innerHTML = !$('#ptTabD').open ? '' : `<div class="tbox cr-pttab"><table><caption class="sr">Значения X и Y по МО</caption><thead><tr><th scope="col">МО</th><th scope="col">Тип</th><th class="n" scope="col">X</th><th class="n" scope="col">Y</th><th class="n" scope="col">население</th></tr></thead><tbody>${all.map(i => { const x = getVar(i, PA), y = getVar(i, PB);
      return `<tr data-i="${i}" tabindex="-1" class="${i === sel ? 'sel' : ''}"><td>${esc(N[i].s)}</td><td><span class="sw" style="--c:${COLV(N[i].c)}" aria-hidden="true"></span> <span class="cr-tsm">${esc(typeName(N[i].c))}</span></td><td class="n">${x == null ? NA : esc(fmtVar(PA, x))}</td><td class="n">${y == null ? NA : esc(fmtVar(PB, y))}</td><td class="n">${fmtN(N[i].pop)}</td></tr>`; }).join('')}</tbody></table></div>`;
    roveRows($('#ptTab tbody'));
  }
  ['#tyTabD', '#ptTabD'].forEach(id => $(id).addEventListener('toggle', tables));
  /* длинные таблицы строк: одна остановка Tab на таблицу (выбранная или первая строка), внутри — стрелки, Home/End */
  function roveRows(tb){ if (!tb) return; const rows = [...tb.querySelectorAll('tr')]; if (!rows.length) return;
    const cur = rows.find(r => r.classList.contains('sel')) || rows[0]; rows.forEach(r => r.tabIndex = r === cur ? 0 : -1);
    if (tb._rove) return; tb._rove = true;
    tb.addEventListener('focusin', e => { const tr = e.target.closest('tr'); if (!tr) return; tb.querySelectorAll('tr').forEach(r => r.tabIndex = r === tr ? 0 : -1); });
    tb.addEventListener('keydown', e => { const tr = e.target.closest('tr'); if (!tr) return; const all = [...tb.querySelectorAll('tr')], k = all.indexOf(tr);
      const to = e.key === 'ArrowDown' ? all[k + 1] : e.key === 'ArrowUp' ? all[k - 1] : e.key === 'Home' ? all[0] : e.key === 'End' ? all[all.length - 1] : null;
      if (to) { e.preventDefault(); to.focus(); } }); }
  $('#ptTab').addEventListener('click', e => { const tr = e.target.closest('tr[data-i]'); if (tr) setSel(+tr.dataset.i); });
  $('#ptTab').addEventListener('keydown', e => { const tr = e.target.closest('tr[data-i]'); if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); setSel(+tr.dataset.i); } });

  function pairHead(){
    const a = PA, b = PB, rho = rhoOf(a, b), q = qOf(a, b), pi = partialInfo(a, b);
    $('#scTitle').innerHTML = `<span><i>X</i>${esc(featLabel(a))}</span><span><i>Y</i>${esc(featLabel(b))}</span>`;
    $('#scStat').innerHTML = rho == null ? '<span class="pill">значения ρ нет в данных</span>' :
      `<div class="cr-st"><b style="color:${rhoInk(rho)}">${fmtSigned(rho, 2)}</b><span>ρ Спирмена по МО</span></div>
       <div class="cr-st"><b class="sm">${fq(q)}</b><span>q (FDR)</span></div>
       <div class="cr-st"><b class="sm">${pi.val != null ? fmtSigned(pi.val, 2) + (pi.keep ? ' *' : '') : esc(pi.txt)}</b><span>частная ρ при контроле</span></div>
       <div class="cr-st"><b class="sm">${PTS.length} из ${n}</b><span>МО с обоими значениями</span></div>
       <span class="pill ${q < .05 ? 'yes' : ''}"><span class="mk" aria-hidden="true"></span>${q < .05 ? 'значимо после FDR' : 'незначимо после FDR'}</span>`;
    $('#scNote').innerHTML = `q — p-value с поправкой Бенджамини–Хохберга по всем парам матрицы; q < 0,05 — связь значима. ${esc(pi.note)}${pi.keep ? ' * — сохраняется при контроле.' : ''} Корреляция не означает причинность.`;
  }

  function selectPairImpl(a, b, opts = {}){
    if (!(a in VIDX) || !(b in VIDX) || a === b) return;
    const same = PA === a && PB === b;
    selPair = [a, b]; PA = a; PB = b; PTS = PTSof(a, b);
    if (!same) { BS.zoom = null; if (!canLog('x')) BS.xlog = false; if (!canLog('y')) BS.ylog = false; }
    markCell(); if (opts.from !== 'matrix' && viewNow() !== 'list') scrollToCell();
    if (viewNow() === 'list') $$('#plUl .cr-pli').forEach(x => x.setAttribute('aria-pressed', pairKey(x.dataset.a, x.dataset.b) === pairKey(a, b)));
    $$('#topcorr tbody tr').forEach(tr => { const on = pairKey(tr.dataset.a, tr.dataset.b) === pairKey(a, b); tr.classList.toggle('sel', on); if (on) tr.setAttribute('aria-current', 'true'); else tr.removeAttribute('aria-current'); });
    pairHead(); syncTools(); captions(); typeCol(); legend(); drill(); moCard(); tables();
    drawPair(opts.from === 'init' ? 'init' : 'data');
    if (opts.from && opts.from !== 'init') announce(`Пара: ${featLabel(a)} и ${featLabel(b)}. ${cellText(a, b)}. n = ${PTS.length} из ${n}.`);
    if (opts.reveal) revealPair();
  }
  function stacked(){ const m = $('#crMat'), p = $('#pairBox'); return p.offsetTop > m.offsetTop + 40; }
  function revealPair(){ if (!stacked()) return; const r = $('#pairBox').getBoundingClientRect(); if (r.top > innerHeight * .5 || r.bottom < 120) $('#pairBox').scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); }
  $('#toMat').addEventListener('click', () => { const m = $('#crMat'); m.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); const f = viewNow() === 'list' ? $('#cmSearch') : $('#heat'); setTimeout(() => f.focus({preventScroll: true}), RM.matches ? 0 : 400); });

  function setMode(m){
    if (m === BS.mode) return; BS.mode = m;
    syncTools(); captions(); typeCol(); legend(); drill(); tables(); drawPair('mode');
    announce({bub: 'Пузырьковая диаграмма', med: 'Медианы по типам', dist: 'Распределение по типам'}[m]);
  }
  $$('#bMode [data-bm]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.bm)));
  $$('#bSize [data-bs]').forEach(b => b.addEventListener('click', () => { if (BS.size === b.dataset.bs) return; BS.size = b.dataset.bs; BS.zoom = null; syncTools(); legend(); drawPair('data'); }));
  $$('#bLog [data-lg]').forEach(b => b.addEventListener('click', () => { const k = b.dataset.lg + 'log'; BS[k] = !BS[k]; BS.zoom = null; syncTools(); captions(); legend(); drawPair('data'); }));
  $$('#bAgg [data-ag]').forEach(b => b.addEventListener('click', () => { if (BS.agg === b.dataset.ag) return; BS.agg = b.dataset.ag; syncTools(); captions(); typeCol(); legend(); drill(); tables(); drawPair('data'); }));
  $$('#scTools [data-zoom]').forEach(b => b.addEventListener('click', () => zoomBy(b.dataset.zoom === 'in' ? 1 / 1.5 : 1.5)));
  $('#bReset').addEventListener('click', () => { if (!PREC || !PREC.chart) return; BS.zoom = null;
    PREC.chart.dispatchAction({type: 'dataZoom', batch: [{dataZoomId: 'dzx', start: 0, end: 100}, {dataZoomId: 'dzy', start: 0, end: 100}]}); $('#bReset').disabled = true; });

  SEL_HOOKS.push(() => {
    if (!PA) return;
    moCard(); drill();
    $$('#ptTab tr[data-i]').forEach(tr => tr.classList.toggle('sel', +tr.dataset.i === sel));
    drawPair('sel');
  });

  /* ======================================================================
     ЛАГИ: профиль семи медиан + средние + доля МО; выбор лага
     ====================================================================== */
  const LAG = D.lag && D.lag.length ? D.lag.map(r => ({lag: r.lag, median: r.median, mean: r.mean, share_pos: r.share_pos})) : [];
  const LBEST = LAG.length ? LAG.reduce((b, r, k) => Math.abs(r.median) > Math.abs(LAG[b].median) ? k : b, 0) : -1;
  const LG = {pin: LBEST, hov: null, intro: true};
  let LREC = null;
  const lagCur = () => LG.hov != null ? LG.hov : LG.pin;
  function lagMeaning(r){
    const k = Math.abs(r.lag), m = k === 1 ? 'месяц' : 'месяца';
    if (r.lag > 0) return `Госзаказ впереди на ${k} ${m}: прирост госзаказа месяца t сопоставлен с приростом трат месяца t+${k}.`;
    if (r.lag < 0) return `Траты впереди на ${k} ${m}: прирост трат месяца t сопоставлен с приростом госзаказа месяца t+${k}.`;
    return 'Без сдвига: приросты госзаказа и трат одного и того же месяца.';
  }
  function lagCard(){
    const k = lagCur(), r = LAG[k]; if (!r) return;
    const sgnTxt = r.median < 0 ? 'Отрицательная медиана: у типичного МО при этом сдвиге приросты двух рядов чаще расходятся по направлению.' : r.median > 0 ? 'Положительная медиана: у типичного МО при этом сдвиге приросты двух рядов чаще совпадают по направлению.' : 'Медиана равна нулю.';
    $('#lagCard').innerHTML = `<div class="cr-lch"><span class="cr-lcl mono">лаг ${lagTxt(r.lag)} мес</span>${k === LBEST ? '<span class="tag">наибольшая |медиана| из семи</span>' : ''}${LG.hov != null && LG.hov !== LG.pin ? '<span class="hint">просмотр</span>' : ''}</div>
      <dl class="cr-lcv">
        <div><dt>медиана ρ по МО</dt><dd class="mono cr-big" style="color:${rhoInk(r.median)}">${fmtSigned(r.median, 3)}</dd><dd class="cr-ex mono">в данных ${fmtSigned(r.median, 5)}</dd></div>
        <div><dt>среднее ρ по МО</dt><dd class="mono">${fmtSigned(r.mean, 3)}</dd></div>
        <div><dt>доля МО с ρ &gt; 0</dt><dd class="mono">${fmtN(r.share_pos * 100, 1)}%</dd><dd class="cr-sbar" aria-hidden="true"><i style="width:${r.share_pos * 100}%"></i><b></b></dd></div>
      </dl>
      <p class="cr-lcm">${esc(lagMeaning(r))} ${esc(sgnTxt)}</p>
      <p class="note">Медиана и среднее — два разных агрегата одних и тех же корреляций по МО; их расхождение — не погрешность. Это не причинность и не время платежей.</p>`;
  }
  function lagCtl(){   // кнопки строятся один раз; при выборе меняются только атрибуты (фокус не теряется)
    const k = lagCur(), ctl = $('#lagCtl');
    if (ctl.children.length === LAG.length) {
      ctl.querySelectorAll('.cr-lb').forEach(b => { const j = +b.dataset.k; b.setAttribute('aria-checked', j === LG.pin); b.tabIndex = j === LG.pin ? 0 : -1; b.classList.toggle('view', j === k); });
      return;
    }
    ctl.innerHTML = LAG.map((r, j) => `<button type="button" role="radio" class="cr-lb${j === LBEST ? ' best' : ''}" data-k="${j}" aria-checked="${j === LG.pin}" tabindex="${j === LG.pin ? 0 : -1}"
      aria-label="лаг ${lagTxt(r.lag)} мес: медиана ${fmtSigned(r.median, 3)}, среднее ${fmtSigned(r.mean, 3)}, доля МО с ρ больше 0 — ${fmtN(r.share_pos * 100, 1)}%${j === LBEST ? '; наибольшая по модулю медиана' : ''}">
      <span class="cr-lbl mono">${lagTxt(r.lag)}</span><span class="cr-lbs" aria-hidden="true"><i style="width:${r.share_pos * 100}%"></i><b></b></span><span class="cr-lbp mono" aria-hidden="true">${fmtN(r.share_pos * 100)}%</span></button>`).join('');
    $$('#lagCtl .cr-lb').forEach(b => b.classList.toggle('view', +b.dataset.k === k));
  }
  function lagTableHtml(){
    const k = lagCur();
    return `<details class="cr-det" open><summary>${ICON.chev}<span>Все семь лагов: таблица</span></summary><div class="tbox"><table><caption class="sr">Лаговые корреляции госзаказа и трат</caption><thead><tr><th class="n" scope="col">лаг, мес</th><th class="n" scope="col">медиана ρ</th><th class="n" scope="col">среднее ρ</th><th class="n" scope="col">доля МО с ρ &gt; 0</th></tr></thead><tbody>${LAG.map((r, j) =>
      `<tr class="${j === k ? 'sel' : ''}" data-k="${j}"><td class="n">${lagTxt(r.lag)}${j === LBEST ? ' <span class="cr-tbest">макс. |медиана|</span>' : ''}</td><td class="n">${fmtSigned(r.median, 3)}</td><td class="n">${fmtSigned(r.mean, 3)}</td><td class="n">${fmtN(r.share_pos * 100, 1)}%</td></tr>`).join('')}</tbody></table></div></details>`;
  }
  function lagSync(){ lagCard(); lagCtl(); const k = lagCur(); $$('#lagTable tr[data-k]').forEach(tr => tr.classList.toggle('sel', +tr.dataset.k === k));
    if (LREC && LREC.chart) LREC.chart.setOption(withMotion(lagSel()), {replaceMerge: []}); }
  function lagSel(){
    const k = lagCur(), r = LAG[k], t = T();
    return {animationDurationUpdate: 200, animationEasingUpdate: 'cubicOut', series: [
      {id: 'band', data: [{name: 'band', value: [k, 0]}], symbolSize: lagBandSize(LREC && LREC.chart)},
      {id: 'sel', data: [{name: 'sel', value: [k, r.median]}], itemStyle: {color: 'rgba(0,0,0,0)', borderColor: t.pearl, borderWidth: 2, shadowBlur: t.dark ? 10 : 5, shadowColor: rgba(t.pearl, .5)}}]};
  }
  function lagBandSize(chart){ const W = chart ? chart.getWidth() : 680, H = chart ? chart.getHeight() : 270; return [Math.max(20, (W - 68) / LAG.length * .84), Math.max(40, H - 36 + 12)]; }
  /* подпись медианы: у края домена — сбоку; иначе с внешней от нуля стороны (не пересекает нулевую ось и подпись «0»),
     но если среднее заметно (> ~6 px) лежит с той же стороны — с противоположной, чтобы не закрыть полый маркер среднего */
  function lagLabPos(r, j, M){
    if (Math.abs(r.median) > .78 * M) return j === LAG.length - 1 ? 'left' : 'right';
    const away = r.median < 0 ? 'bottom' : 'top', meanAway = r.median < 0 ? r.mean < r.median : r.mean > r.median;
    const gapPx = Math.abs(r.mean - r.median) / (2 * M) * 230;
    return meanAway && gapPx > 6 ? (away === 'top' ? 'bottom' : 'top') : away;
  }
  function lagOpt(chart){
    const t = T(), k = lagCur(), mx = Math.max(...LAG.flatMap(r => [Math.abs(r.median), Math.abs(r.mean)]), .1);
    const step = mx > .6 ? .5 : mx > .3 ? .2 : .1, M = Math.ceil(mx * 1.12 / step) * step;
    const sc = v => v >= 0 ? css('--rp2') : css('--rn2'), intro = LG.intro;
    const o = {animation: true, animationDuration: intro ? 440 : 0, animationEasing: 'cubicOut', animationDurationUpdate: 200, animationEasingUpdate: 'cubicOut',
      textStyle: {fontFamily: 'Golos Text, system-ui, sans-serif'}, tooltip: {show: false},
      grid: {left: 52, right: 16, top: 26, bottom: 10},
      xAxis: {type: 'category', data: LAG.map(r => lagTxt(r.lag)), boundaryGap: true, axisLabel: {show: false}, axisTick: {show: false}, axisLine: {show: false}, splitLine: {show: false}},
      yAxis: {type: 'value', min: -M, max: M, interval: step, axisLabel: {formatter: v => Math.abs(v) < 1e-9 ? '0' : fmtSigned(v, step < .2 ? 1 : 1), color: t.ink2, fontSize: 11.5},
        axisLine: {show: false}, axisTick: {show: false}, splitLine: {lineStyle: {color: t.soft}}, name: 'ρ', nameLocation: 'end', nameGap: 10, nameTextStyle: {color: t.ink2, fontSize: 12, align: 'right'}},
      series: [
        // полоса выбранного лага: символ-прямоугольник по центру столбца (домен симметричен, y = 0 — середина), переезжает как кольцо
        {id: 'band', type: 'scatter', silent: true, z: 0, symbol: 'roundRect', symbolSize: lagBandSize(chart), data: [{name: 'band', value: [k, 0]}],
          itemStyle: {color: rgba(t.pearl, t.dark ? .12 : .10), borderColor: rgba(t.pearl, t.dark ? .35 : .3), borderWidth: 1}, animationDuration: intro ? 200 : 0},
        {id: 'conn', type: 'custom', silent: true, z: 1, data: LAG.map((r, j) => [j, r.median, r.mean]), renderItem: (p, api) => { const a = api.coord([api.value(0), api.value(1)]), b = api.coord([api.value(0), api.value(2)]);
          return {type: 'line', shape: {x1: a[0], y1: a[1], x2: b[0], y2: b[1]}, style: {stroke: t.strong, lineWidth: 1.5}}; },
          animationDuration: intro ? 360 : 0, animationDelay: intro ? 150 : 0},
        {id: 'med', type: 'line', z: 3, data: LAG.map((r, j) => ({value: r.median, symbolSize: j === LBEST ? 15 : 11,
            itemStyle: {color: sc(r.median), borderColor: j === LBEST ? t.ink : t.surface, borderWidth: j === LBEST ? 2 : 1.5},
            label: {position: lagLabPos(r, j, M)}})),
          symbol: 'circle', lineStyle: {color: rgba(t.ink2, .55), width: 1.4}, smooth: false,
          label: {show: true, formatter: p => fmtSigned(p.value, 2), color: t.ink, fontFamily: 'JetBrains Mono, monospace', fontSize: 11.5, distance: 7, backgroundColor: rgba(t.surface, .82), padding: [1, 3], borderRadius: 3},
          markLine: {silent: true, symbol: 'none', animation: false, label: {show: false}, data: [{yAxis: 0}], lineStyle: {color: t.ink2, width: 1.2, type: 'solid'}},
          animationDuration: intro ? 420 : 0, animationDelay: j => intro ? j * 12 : 0},
        {id: 'mean', type: 'scatter', z: 4, data: LAG.map((r, j) => [j, r.mean]), symbol: 'circle', symbolSize: 7.5,
          itemStyle: {color: 'rgba(0,0,0,0)', borderColor: t.ink2, borderWidth: 1.6}, animationDuration: intro ? 340 : 0, animationDelay: j => intro ? 120 + j * 12 : 0},
        {id: 'sel', type: 'scatter', z: 5, silent: true, symbolSize: 26, data: [{name: 'sel', value: [k, LAG[k].median]}],
          itemStyle: {color: 'rgba(0,0,0,0)', borderColor: t.pearl, borderWidth: 2, shadowBlur: t.dark ? 10 : 5, shadowColor: rgba(t.pearl, .5)}, animationDuration: intro ? 320 : 0, animationDelay: intro ? 210 : 0}]};
    return o;
  }
  function bindLag(chart){
    LG.intro = false;
    const zr = chart.getZr();
    // столбец лага под курсором: {gridIndex} даёт [индекс категории, ρ]; {xAxisIndex} для категориальной оси в ECharts 6 возвращает null
    const idxAt = (x, y) => { if (!chart.containPixel({gridIndex: 0}, [x, y])) return null; const v = chart.convertFromPixel({gridIndex: 0}, [x, y]); const k = Math.round(Array.isArray(v) ? v[0] : v); return Number.isFinite(k) && k >= 0 && k < LAG.length ? k : null; };
    zr.on('mousemove', e => { const k = idxAt(e.offsetX, e.offsetY); zr.setCursorStyle(k == null ? 'default' : 'pointer'); if (k !== LG.hov) { LG.hov = k; lagSync(); } });
    zr.on('globalout', () => { if (LG.hov != null) { LG.hov = null; lagSync(); } });
    zr.on('click', e => { const k = idxAt(e.offsetX, e.offsetY); if (k != null) { LG.pin = k; LG.hov = null; lagSync(); } });
  }
  function lagInit(){
    if (!LAG.length) { $('#lagc').innerHTML = '<div class="empty">Лаговый анализ не рассчитан.</div>'; $('#lagReplay').hidden = true; return; }
    lagCard(); lagCtl(); $('#lagTable').innerHTML = lagTableHtml();
    const ctl = $('#lagCtl');
    ctl.addEventListener('click', e => { const b = e.target.closest('.cr-lb'); if (b) { LG.pin = +b.dataset.k; LG.hov = null; lagSync(); } });
    ctl.addEventListener('mouseover', e => { const b = e.target.closest('.cr-lb'); if (b && +b.dataset.k !== LG.hov) { LG.hov = +b.dataset.k; lagSync(); } });
    ctl.addEventListener('mouseleave', () => { if (LG.hov != null) { LG.hov = null; lagSync(); } });
    ctl.addEventListener('focusin', e => { const b = e.target.closest('.cr-lb'); if (b && +b.dataset.k !== LG.pin) { LG.pin = +b.dataset.k; LG.hov = null; lagSync(); } });
    ctl.addEventListener('keydown', e => {
      const map = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1}; let k = LG.pin;
      if (e.key in map) k = (k + map[e.key] + LAG.length) % LAG.length; else if (e.key === 'Home') k = 0; else if (e.key === 'End') k = LAG.length - 1; else return;
      e.preventDefault(); LG.pin = k; LG.hov = null; lagSync(); ctl.querySelector(`[data-k="${k}"]`).focus();
    });
    $('#lagReplay').addEventListener('click', () => {
      if (!LREC || !LREC.chart) return; LG.intro = true; LREC.chart.clear(); LREC.chart.setOption(withMotion(lagOpt(LREC.chart)), true); LG.intro = false; announce('Лаговый профиль показан заново');
    });
    const create = () => { if (LREC) return; LREC = makeChart($('#lagc'), lagOpt, {renderer: 'svg', onInit: bindLag});
      onResize($('#lagc'), () => { if (LREC.chart) { LREC.chart.resize(); LREC.chart.setOption({series: [{id: 'band', symbolSize: lagBandSize(LREC.chart)}]}); } }); };
    if ('IntersectionObserver' in window) { const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); create(); } }, {threshold: .35}); io.observe($('#lagc')); }
    else create();
  }

  /* ======================================================================
     ТАБЛИЦА СИЛЬНЕЙШИХ СВЯЗЕЙ
     ====================================================================== */
  function topTable(){
    $('#topCount').textContent = D.corr.top.length + ' пар';
    $('#topcorr').innerHTML = `<caption class="sr">Сильнейшие значимые связи: ρ Спирмена, q, частная корреляция</caption><thead><tr><th scope="col">Показатель 1</th><th scope="col">Показатель 2</th><th class="n" scope="col">ρ Спирмена</th><th class="n" scope="col">q (FDR)</th><th class="n" scope="col">при контроле</th><th scope="col">Устойчивость</th></tr></thead><tbody>` +
      D.corr.top.map(r => { const w = Math.abs(r.rho) * 45;
        return `<tr data-a="${esc(r.x)}" data-b="${esc(r.y)}" tabindex="-1"><td>${esc(featLabel(r.x))}</td><td>${esc(featLabel(r.y))}</td>
        <td class="n" data-l="ρ Спирмена"><span class="rhocell"><span>${fmtSigned(r.rho, 2)}</span><span class="rhobar" aria-hidden="true"><i style="${r.rho >= 0 ? 'left:50%' : 'right:50%'};width:${w}%;background:${r.rho >= 0 ? 'var(--rp2)' : 'var(--rn2)'}"></i></span></span></td>
        <td class="n" data-l="q (FDR)">${fq(r.q)}</td><td class="n" data-l="при контроле">${r.prho == null ? '<span class="na">—</span>' : fmtSigned(r.prho, 2)}</td>
        <td>${r.prho == null ? '<span class="hint">не рассчитывалась</span>' : r.pq < .05 ? '<span class="tag">' + mk('opp') + 'сохраняется при контроле</span>' : '<span class="tag">' + mk('info') + 'не сохраняется</span>'}</td></tr>`; }).join('') + '</tbody>';
    const go = tr => { selectPairImpl(tr.dataset.a, tr.dataset.b, {from: 'table'});
      const pb = $('#pairBox'), r = pb.getBoundingClientRect(); if (r.top < 0 || r.top > innerHeight * .6) pb.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); };
    roveRows($('#topcorr tbody'));
    $('#topcorr').addEventListener('click', e => { const tr = e.target.closest('tbody tr'); if (tr) go(tr); });
    $('#topcorr').addEventListener('keydown', e => { const tr = e.target.closest('tbody tr'); if (tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); go(tr); } });
  }

  /* ======================================================================
     ЗАПУСК, ТЕМА, РАЗМЕР, ВКЛАДКА
     ====================================================================== */
  function init(){
    $('#corrLede').textContent = `ρ Спирмена по ${n} МО: ${CV.length} показателей и индексов, ${fmtN(ALLPAIRS.length)} уникальных пар. Значимость — после поправки Бенджамини–Хохберга (FDR). Выберите клетку матрицы, строку списка или таблицы: справа откроется пара — пузырьковая диаграмма, медианы и распределения по типам.`;
    renderMatrixArea(); topTable(); lagInit();
    if (D.corr.top.length) selectPairImpl(D.corr.top[0].x, D.corr.top[0].y, {from: 'init'});
    PREC = makeChart($('#bubble'), ch => { layoutStage(); return buildPair(ch, 'init'); }, {renderer: 'svg', onInit: ch => { bindPair(ch); if (BS.mode === 'bub' && GEO && GEO.Dmax !== LEGD) legend(); }});
    onResize($('#bStage'), () => { const h0 = GEO ? GEO.H : 0; layoutStage(); if (PREC && PREC.chart) { PREC.chart.resize(); drawPair('resize'); } if (GEO && GEO.H !== h0) legend(); });
    onResize($('#heat'), () => { measureCorner(); placeCircles(); });
  }
  THEME_HOOKS.push(() => { if (viewNow() !== 'list') heat(); else $('#cmLegend').innerHTML = legendHtml(); });
  onTab('corr', () => requestAnimationFrame(() => { if (viewNow() !== 'list') { measureCorner(); placeCircles(); scrollToCell(); } }));

  return {init, selectPair: selectPairImpl};
})();

/* выбор пары показателей (может вызываться из других модулей) */
function selectPair(a, b, opts){ return CORRTAB.selectPair(a, b, opts); }
function corrInit(){ CORRTAB.init(); }
