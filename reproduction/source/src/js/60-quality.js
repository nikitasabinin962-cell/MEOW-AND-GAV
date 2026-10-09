/* ==========================================================================
   6. Качество модели (V4): что проверяется → результаты против базового
   уровня → методы → важность признаков → слои → устойчивость → ограничения.
   Только фактические значения из D.quality и D.ml; интервалы не выдумываются,
   разнородные проверки не сводятся в общий балл. D не изменяется.
   Графики — выровненные dot/interval-строки на HTML: у каждой метрики своя ось
   с делениями, числа подписаны прямо; оси и домены пересчитываются по реальной
   ширине дорожки (onResize), строки сортируются со стабильными DOM-узлами (FLIP).
   ========================================================================== */
$('#t-quality').innerHTML = `<div class="phead">
    <div><h2>Качество модели</h2>
      <p class="lede">Сначала — что проверяется и с чем сравнивается, затем фактические значения. Ни одна из проверок не переводится в «процент доверия» и не сводится в общий балл: у каждой метрики своя шкала и свой базовый уровень.</p></div>
  </div>
  <div id="qual"></div>`;

const QL = {mk: null, is: 'mdi', imp: null, entered: false, rk: null};

/* ---------- форматирование: минус — настоящий, ноль — ноль, пропуск — н/д ---------- */
const qlMinus = (s, v) => v < 0 ? '−' + s : s;
const qlFix = (v, d) => v == null || Number.isNaN(v) ? 'н/д' : v === 0 ? '0' : qlMinus(fmtN(Math.abs(v), d), v);
const q5 = v => qlFix(v, 5);   // важность: 5 знаков — точность записи в данных
const q4 = v => qlFix(v, 4);   // z, индексы, ARI: 4 знака — точность записи в данных
const qlPct = (v, d = 1) => v == null || Number.isNaN(v) ? 'н/д' : fmtN(v * 100, d) + '%';
const qlP = p => p == null ? 'p: н/д' : p === 0 ? 'p = 0 (в данных)' : 'p = ' + fmtN(p, 4);
const qlDec = st => Math.max(0, Math.ceil(-Math.log10(st) - 1e-9));
const qlTick = (v, st) => Math.abs(v) < 1e-12 ? '0' : qlMinus(fmtN(Math.abs(v), qlDec(st)), v);

/* ---------- оси: «красивый» шаг и домен, концы домена — на делениях ---------- */
function qlStep(span, k){ const s0 = (span || 1) / Math.max(1, k), mag = 10 ** Math.floor(Math.log10(s0)), e = s0 / mag;
  return (e > 5 ? 10 : e > 2 ? 5 : e > 1 ? 2 : 1) * mag; }
/* Домен и деления. Шаг — «красивый» (1, 2, 5 × 10ⁿ); края домена кратны половине шага, деления — кратны шагу,
   поэтому ось не раздувается до целого лишнего шага (ноль и все значения остаются внутри).
   Среди шагов выбирается наименьший размах, при котором подписи делений (моно 11,5 px ≈ 7 px на знак)
   не сталкиваются; при равном размахе — шаг ближе к W/5 (60–110 px). */
function qlDom(lo, hi, W, fmt = qlTick){
  let best = null; const tgt = Math.max(60, Math.min(110, W / 5));
  for (let k = Math.max(1, Math.floor(W / 40)); k >= 1; k--) {
    const st = qlStep(hi - lo, k), mi = st / 2;
    const a = +(Math.floor(lo / mi + 1e-9) * mi).toFixed(12), b = +(Math.ceil(hi / mi - 1e-9) * mi).toFixed(12);
    const t0 = Math.ceil(a / st - 1e-9), t1 = Math.floor(b / st + 1e-9), ticks = [];
    for (let j = t0; j <= t1; j++) ticks.push(+(j * st).toFixed(12));
    if (ticks.length < 2) continue;
    const need = Math.max(...ticks.map(t => String(fmt(t, st)).length)) * 7 + 16, gap = st / (b - a) * W;
    if (gap < need) continue;
    const d = {lo: a, hi: b, step: st, ticks, gap};
    if (!best || d.hi - d.lo < best.hi - best.lo - 1e-12 || (Math.abs(d.hi - d.lo - (best.hi - best.lo)) < 1e-12 && Math.abs(d.gap - tgt) < Math.abs(best.gap - tgt))) best = d;
  }
  if (best) return best;
  const st = qlStep(hi - lo, 1), a = Math.floor(lo / st + 1e-9) * st, b = Math.ceil(hi / st - 1e-9) * st;
  return {lo: a, hi: b, step: st, ticks: [a, b], gap: W};
}

/* ---------- раскладка зарегистрированных графиков по реальной ширине дорожек ----------
   Разметка дорожки: .ql-tr[data-sc] → метки с data-x (точка), data-x0/x1 (отрезок), .ql-v[data-at][data-side] (подпись).
   Для шкалы с fit:true верхняя граница домена расширяется, чтобы подписи справа помещались в дорожку. */
const QL_CHARTS = [];
function qlRegister(root, scales){
  const c = {root, scales};
  QL_CHARTS.push(c);
  onResize(root, () => qlLayout(c, false));
  FONTS_READY.then(() => qlLayout(c, false));
  return c;
}
function qlLayout(c, animate){
  const R = c.root; if (!R.isConnected || !R.offsetWidth) return;
  if (!animate) R.classList.add('ql-still');
  for (const [key, sc] of Object.entries(c.scales)) {
    const tracks = [...R.querySelectorAll(`.ql-tr[data-sc="${key}"]`)]; if (!tracks.length) continue;
    const W = tracks[0].clientWidth; if (!W) continue;
    let d = qlDom(sc.lo, sc.hi, W, sc.fmt);
    if (sc.fit) {
      const labs = tracks.flatMap(t => [...t.querySelectorAll('.ql-v[data-side="r"]')]).map(el => ({end: +el.dataset.at, w: el.offsetWidth}));
      for (let it = 0; it < 6; it++) {
        let need = d.hi;
        labs.forEach(o => { const room = W - 10 - o.w; if (room < 24) return;
          const x = (o.end - d.lo) / (d.hi - d.lo) * W; if (x > room) need = Math.max(need, d.lo + (o.end - d.lo) * W / room); });
        if (need <= d.hi + 1e-12) break;
        d = qlDom(sc.lo, need, W, sc.fmt);
      }
    }
    sc.d = d;
    const P = v => (v - d.lo) / (d.hi - d.lo) * 100;
    const grid = d.ticks.map(t => `<i class="${Math.abs(t) < 1e-12 ? 'z' : ''}" style="left:${P(t)}%"></i>`).join('');
    /* широкая раскладка (дорожка во всю высоту строки): деления — один общий слой под всеми строками,
       поэтому при перестановке строк сетка не рвётся; узкая (дорожка под названием) — сетка в каждой дорожке */
    const body = tracks[0].closest('.ql-b'), wide = !!body && tracks[0].offsetTop < 2;
    let bg = body && body.querySelector(`:scope > .ql-bgg[data-sc="${key}"]`);
    if (body && wide) {
      if (!bg) { bg = document.createElement('div'); bg.className = 'ql-bgg ql-g'; bg.dataset.sc = key; bg.setAttribute('aria-hidden', 'true'); body.prepend(bg); }
      const br = body.getBoundingClientRect(), tr = tracks[0].getBoundingClientRect();
      bg.style.left = (tr.left - br.left) + 'px'; bg.style.width = tr.width + 'px'; bg.hidden = false; bg.innerHTML = grid;
    } else if (bg) bg.hidden = true;
    tracks.forEach(t => {
      const g = t.querySelector('.ql-g'); if (g) g.innerHTML = wide && body ? '' : grid;
      t.querySelectorAll('[data-x]').forEach(el => { el.style.left = P(+el.dataset.x) + '%'; });
      t.querySelectorAll('[data-x0]').forEach(el => { const a = P(Math.min(+el.dataset.x0, +el.dataset.x1)), b = P(Math.max(+el.dataset.x0, +el.dataset.x1));
        el.style.left = a + '%'; el.style.width = (b - a) + '%'; });
      t.querySelectorAll('.ql-v[data-at]').forEach(el => { el.style.left = P(+el.dataset.at) + '%'; });
    });
    R.querySelectorAll(`.ql-ax[data-sc="${key}"]`).forEach(ax => {
      ax.innerHTML = d.ticks.map(t => { const lab = (sc.fmt || qlTick)(t, d.step), x = P(t) / 100 * W, hw = lab.length * 3.6;
        return `<i style="left:${P(t)}%"></i><span class="${x < hw + 1 ? 'f' : x > W - hw - 1 ? 'l' : ''}${Math.abs(t) < 1e-12 ? ' z' : ''}" style="left:${P(t)}%">${lab}</span>`; }).join('');
    });
  }
  if (!animate) { void R.offsetWidth; R.classList.remove('ql-still'); }
}
/* перестановка строк с сохранением DOM-узлов: First → Last → Invert → Play.
   Метки (точки, отрезки) едут вместе со строкой и сохраняют её идентичность. Текст строк, которые
   переезжают дальше половины своей высоты, гаснет за 40 мс, пока строка ещё стоит, и возвращается
   только когда до места осталось ≤ 1,5 px (момент считается по той же кривой Безье для каждого dy) —
   поэтому подписи не проезжают друг по другу ни в одном промежуточном кадре. Движение — 260 мс после
   40 мс удержания (всего 300 мс), текст полностью виден не позже ~340 мс. Повторный клик во время
   перелёта продолжает движение из текущего положения и текущей прозрачности текста (без вспышки).
   На время движения общая сетка опускается под строки: transform создаёт контекст наложения. */
const QL_TXT = '.ql-n, .ql-v, .ql-num';
const QL_EASE = [.25, .75, .3, 1], QL_HOLD = 40, QL_MOVE = 260, QL_FADE = 60;
const QL_BZ = (() => { const [x1, y1, x2, y2] = QL_EASE, B = (a, b, s) => 3 * (1 - s) ** 2 * s * a + 3 * (1 - s) * s * s * b + s ** 3, T = [];
  for (let i = 0; i <= 400; i++) { const s = i / 400; T.push([B(x1, x2, s), B(y1, y2, s)]); } return T; })();
/* доля времени движения, после которой остаток пути строки со сдвигом dy не больше eps px */
function qlSettle(dy, eps = 1.5){ const need = 1 - eps / Math.max(Math.abs(dy), eps); const p = QL_BZ.find(([, y]) => y >= need); return p ? p[0] : 1; }
function qlFlip(body, rows){
  const first = new Map(rows.map(e => [e, e.getBoundingClientRect().top]));
  const op0 = new Map(); rows.forEach(e => e.querySelectorAll(QL_TXT).forEach(t => op0.set(t, +getComputedStyle(t).opacity)));
  rows.forEach(e => { e.getAnimations().forEach(a => a.cancel()); e.querySelectorAll(QL_TXT).forEach(t => t.getAnimations().forEach(a => a.cancel())); });
  rows.forEach(e => body.appendChild(e));
  const tok = body._qlTok = (body._qlTok || 0) + 1;
  if (RM.matches || !body.offsetParent) { body.classList.remove('ql-mv'); return; }
  const ease = `cubic-bezier(${QL_EASE})`, runs = [];
  rows.forEach(e => {
    const dy = first.get(e) - e.getBoundingClientRect().top, txt = [...e.querySelectorAll(QL_TXT)], dim = txt.some(t => op0.get(t) < .999);
    if (Math.abs(dy) >= 1) runs.push(e.animate([{transform: `translateY(${dy}px)`}, {transform: 'none'}], {duration: QL_MOVE, delay: QL_HOLD, easing: ease, fill: 'backwards'}));
    if (Math.abs(dy) < 1) { if (dim) txt.forEach(t => t.animate([{opacity: op0.get(t)}, {opacity: 1}], {duration: QL_HOLD + QL_FADE, easing: 'linear'})); return; }
    if (Math.abs(dy) <= e.offsetHeight / 2 && !dim) return;
    const tIn = QL_HOLD + qlSettle(dy) * QL_MOVE, dur = tIn + QL_FADE;
    txt.forEach(t => t.animate([{opacity: op0.get(t)}, {opacity: 0, offset: QL_HOLD / dur}, {opacity: 0, offset: tIn / dur}, {opacity: 1}], {duration: dur, easing: 'linear'}));
  });
  if (!runs.length) { body.classList.remove('ql-mv'); return; }
  body.classList.add('ql-mv');
  Promise.all(runs.map(a => a.finished.catch(() => null))).then(() => { if (body._qlTok === tok) body.classList.remove('ql-mv'); });
}
const qlTrack = (sc, inner, cls = '') => `<div class="ql-tr ${cls}" data-sc="${sc}"><div class="ql-g"></div>${inner}</div>`;

function qualityInit(){
  const V = Q.val, ml = D.ml, LN = k => (typeof LAYERS !== 'undefined' && LAYERS[k]) || k;
  const MN = {spectral_fused: 'Спектральная, признаки + связи', louvain_fused: 'Louvain, признаки + связи', kmeans_attr: 'k-means, признаки', gmm_attr: 'Гауссовы смеси, признаки',
    ward_attr: 'Уорд, признаки', louvain_struct: 'Louvain, только связи', spectral_struct: 'Спектральная, только связи'};
  const yrs = V && V.holdout ? Object.keys(V.holdout) : [];

  /* ===== А. что проверяется ===== */
  const A = `<ol class="ql-checks">
    <li><a href="#q-methods">Выбор метода</a><span>${Q.icvi.length} алгоритмов кластеризации сравниваются по индексам качества на одной шкале z.</span></li>
    <li><a href="#q-ml">Объяснимость</a><span>Восстанавливает ли случайный лес тип МО, которого не видел при обучении, и какие признаки для этого важны.</span></li>
    <li><a href="#q-val">Новые данные</a><span>Узнаётся ли тип по закупкам ${yrs.length ? yrs.map(esc).join(' и ') : 'следующих лет'} — вне периода построения ${esc(D.period)}.</span></li>
    <li><a href="#q-stab">Устойчивость</a><span>Бутстреп по МО и согласованность соседних кварталов.</span></li>
    <li><a href="#q-layers">География и слои</a><span>Цельность типов на карте и вклад каждого слоя связей.</span></li></ol>`;

  /* ===== Б. результат против базового уровня: aligned dot/bullet, у каждой проверки своя ось ===== */
  const bRow = ({title, sub, val, base, ref, sc, fmt}) => {
    const side = base != null && val < base ? 'l' : 'r';
    const marks = (base != null ? `<span class="ql-gain" data-x0="${base}" data-x1="${val}"></span><span class="ql-bl" data-x="${base}"></span><span class="ql-base" data-x="${base}"></span>` : '')
      + `<span class="ql-dot${ref ? ' ref' : ''}" data-x="${val}"></span><span class="ql-v" data-side="${side}" data-at="${val}">${fmt(val)}</span>`;
    return `<div class="ql-r"><div class="ql-n"><b>${title}</b><small>${sub}</small><span class="sr">: ${ref ? 'ориентир' : 'результат'} ${fmt(val)}${base != null ? ', базовый уровень ' + fmt(base) : ''}</span></div>${qlTrack(sc, marks, 'ql-c1')}</div>`;
  };
  const bAxis = (sc, cap) => `<div class="ql-r ql-f" aria-hidden="true"><div class="ql-n"><small>${cap}</small></div><div class="ql-hc ql-c1"><div class="ql-ax" data-sc="${sc}"></div></div></div>`;
  const card = (id, h, what, rows, sc, cap, hint) => `<div class="ql-card" id="${id}"><h4>${h}</h4><p class="ql-what">${what}</p>
    <div class="ql-d k-b" data-chart="${sc}"><div class="ql-b">${rows.join('')}</div>${bAxis(sc, cap)}</div>${hint ? `<p class="ql-hint">${hint}</p>` : ''}</div>`;
  const cards = [];
  if (ml) cards.push(card('q-ml', 'Объяснимость типа: машинное обучение',
    `Случайный лес восстанавливает тип МО, которого не видел при обучении (leave-one-out, ${n} МО). Базовый уровень — всегда угадывать самый крупный класс.`,
    [bRow({title: 'Точность случайного леса', sub: `leave-one-out · база: крупнейший класс ${qlPct(ml.base)}`, val: ml.acc, base: ml.base, sc: 'acc1', fmt: qlPct})],
    'acc1', 'доля МО с верно восстановленным типом', 'Шкала 0–100% — доля МО. Важность признаков этой модели — ниже, в разделе «Что определяет тип».'));
  if (V) cards.push(card('q-val', 'Проверка на новых данных',
    `Типы построены по ${esc(D.period)}. Затем МО заново относятся к ближайшему типу только по закупкам следующих лет; эти годы не входили в построение типов.`,
    yrs.map(y => { const h = V.holdout[y]; return bRow({title: esc(y), sub: `${qlP(h.p_value)} · база: случайное отнесение ${qlPct(V.chance_mean)}`, val: h.accuracy, base: V.chance_mean, sc: 'acc2', fmt: qlPct}); })
      .concat(V.accuracy_in_sample != null ? [bRow({title: 'То же правило на данных построения', sub: `ориентир, ${esc(D.period)}; не проверка на новых данных`, val: V.accuracy_in_sample, ref: true, sc: 'acc2', fmt: qlPct})] : []),
    'acc2', 'доля МО, тип которых совпал с исходным',
    `Случайный уровень — среднее значение при случайном отнесении, как оно записано в данных. Годы показаны отдельными строками, а не временным рядом: это отдельные проверки. Год без данных не проверялся (это не ноль и не успех).`));
  cards.push(card('q-stab', 'Устойчивость при повторных выборках',
    'Бутстреп: 80% МО × 200 повторов; совпадение разбиений измеряется ARI (скорректированный индекс Рэнда): 1 — полное совпадение, 0 — уровень случайного разбиения. ARI — не процент точности.',
    [bRow({title: 'Детальная типология', sub: `${D.k} типов · база: случайное разбиение, ARI 0`, val: Q.boot, base: 0, sc: 'ari', fmt: v => qlFix(v, 3)}),
     bRow({title: 'Макроуровень', sub: `${Object.keys(D.macro_names).length} макротипа · база: ARI 0`, val: Q.macro_boot, base: 0, sc: 'ari', fmt: v => qlFix(v, 3)})],
    'ari', 'ARI, 0…1 (1 — полное совпадение)', ''));
  const sp = Q.spatial;
  cards.push(card('q-geo', 'География: цельность типов',
    'Местоположение в модель не входило. Если типы — цельные территории, МО одного типа ближе друг к другу, чем при случайном разбиении на группы.',
    [bRow({title: 'Среднее расстояние внутри типа', sub: `${qlP(sp.p_value)} · база: случайное разбиение ${fmtN(sp.random_mean_km, 1)} км`, val: sp.within_km, base: sp.random_mean_km, sc: 'km', fmt: v => fmtN(v, 1) + ' км'})],
    'km', 'км; меньше — территориально цельнее', 'Случайный уровень — среднее расстояние при случайном разбиении, как оно записано в данных.'));
  /* раскладка 2×2: одно- и многострочные карточки попарно, чтобы не оставлять пустот */
  const CORD = ['q-ml', 'q-geo', 'q-val', 'q-stab'], cid = h => CORD.indexOf((h.match(/id="(q-[a-z]+)"/) || [])[1]);
  cards.sort((a, b) => cid(a) - cid(b));
  const B = `<div class="sec"><h3 class="sech">Ключевые результаты против базового уровня <span class="kicker">${cards.length} проверки, у каждой своя шкала</span></h3>
    <p class="secsub">Каждая проверка сравнивается со своим базовым уровнем и не переводится в общий «балл качества».</p>
    <div class="ql-legend" aria-hidden="true"><span><i class="ql-lg base"></i>базовый уровень</span><span><i class="ql-lg dot"></i>результат</span><span><i class="ql-lg gain"></i>отрыв от базового уровня</span><span><i class="ql-lg ref"></i>ориентир, не проверка</span></div>
    <div class="ql-cards">${cards.join('')}</div></div>`;

  /* ===== В. методы: упорядоченные точки + точная таблица ===== */
  const IXZ = ['SW', 'CH', 'DB', 'S_Dbw', 'MQ', 'AVI', 'AVU'].filter(k => Q.icvi.some(r => r['z_' + k] != null));
  const hasZm = Q.icvi.some(r => r.z_mean != null);
  const MK = (hasZm ? ['mean'] : []).concat(IXZ);
  const mkName = k => k === 'mean' ? 'среднее z' : 'z ' + k;
  const zAll = Q.icvi.flatMap(r => MK.map(k => r['z_' + k])).filter(v => v != null);
  const zLo = Math.min(0, ...zAll), zHi = Math.max(0, ...zAll);
  const best = {}; MK.forEach(k => { const vs = Q.icvi.map(r => r['z_' + k]).filter(v => v != null); best[k] = vs.length ? Math.max(...vs) : null; });
  const mRow = r => `<div class="ql-r${r.method === Q.method ? ' fin' : ''}" data-k="${esc(r.method)}">
      <div class="ql-n">${esc(MN[r.method] || r.method)}${r.method === Q.method ? '<span class="ql-fin">итоговая модель</span>' : ''}</div>
      ${qlTrack('z', MK.map(k => r['z_' + k] == null ? '' : `<span class="ql-cx${k === 'mean' ? ' mean' : ''}" data-ix="${k}" data-x="${r['z_' + k]}" data-tip="${esc(`<b>${esc(MN[r.method] || r.method)}</b><br>${mkName(k)} = <span class="tnum">${q4(r['z_' + k])}</span>`)}"></span>`).join('')
        + `<span class="ql-dot main" data-x="0"></span>`, 'ql-c1')}
      <div class="ql-num ql-c2 mono"></div></div>`;
  const mTable = `<div class="tbox ql-mtab" tabindex="0" role="region" aria-label="Точная таблица методов (прокручивается)"><table><caption class="sr">z-значения и исходные значения индексов качества для ${Q.icvi.length} методов</caption>
    <thead><tr><th scope="col">Метод</th>${IXZ.map(k => `<th scope="col" class="n" data-ix="${k}">z ${k}<small>исходное</small></th>`).join('')}${hasZm ? '<th scope="col" class="n" data-ix="mean">среднее z<small>7 индексов</small></th>' : ''}<th scope="col" class="n">мин. размер<small>МО</small></th></tr></thead><tbody>
    ${Q.icvi.map(r => `<tr class="${r.method === Q.method ? 'fin' : ''}"><th scope="row">${esc(MN[r.method] || r.method)}${r.method === Q.method ? '<span class="ql-fin">итоговая модель</span>' : ''}<small class="mono">${esc(r.method)}</small></th>
      ${IXZ.map(k => `<td class="n${r['z_' + k] === best[k] ? ' best' : ''}" data-ix="${k}">${q4(r['z_' + k])}<small>${r[k] == null ? 'н/д' : q4(r[k])}</small></td>`).join('')}
      ${hasZm ? `<td class="n${r.z_mean === best.mean ? ' best' : ''}" data-ix="mean">${q4(r.z_mean)}<small>&nbsp;</small></td>` : ''}<td class="n">${r.minsize ?? 'н/д'}</td></tr>`).join('')}</tbody></table></div>`;
  const C1 = `<div class="sec" id="q-methods"><h3 class="sech">Сравнение методов кластеризации <span class="kicker">k = ${D.k}, ${Q.icvi.length} методов</span></h3>
    <p class="secsub">Индексы качества (ICVI) нормированы на случайные перестановки меток: z = (значение − среднее по перестановкам) / стандартное отклонение. z = 0 — уровень случайного разбиения; больше — лучше; для S_Dbw и DB знак обращён (меньшее исходное значение даёт большее z). «Среднее z» — среднее ${IXZ.length} индексов, а не отдельная проверка.</p>
    <div class="ql-tools"><span class="ql-tl" id="qlMLab">Показатель и порядок строк</span><div class="seg" role="group" aria-labelledby="qlMLab" id="qlMSeg">${MK.map(k => `<button type="button" data-mk="${k}" aria-pressed="${k === MK[0]}">${k === 'mean' ? 'среднее z' : k}</button>`).join('')}</div></div>
    <div class="ql-panel"><div class="ql-legend in" aria-hidden="true"><span><i class="ql-lg dot"></i>выбранный показатель</span><span><i class="ql-lg cx"></i>другие индексы метода</span>${hasZm ? '<span><i class="ql-lg mean"></i>среднее z</span>' : ''}</div>
      <div class="ql-d k-m" id="qlM">
        <div class="ql-r ql-h" aria-hidden="true"><div class="ql-n"><small>Метод</small></div><div class="ql-hc ql-c1"><div class="ql-ht"><b id="qlMName"></b> <span>стандартных отклонений от случайного разбиения</span></div><div class="ql-ax" data-sc="z"></div></div><div class="ql-hc ql-c2 ql-hn"><b>z</b></div></div>
        <div class="ql-b" id="qlMB">${Q.icvi.map(mRow).join('')}</div>
        <div class="ql-r ql-f" aria-hidden="true"><div class="ql-n"></div><div class="ql-hc ql-c1"><div class="ql-ax" data-sc="z"></div></div><div class="ql-hc ql-c2"></div></div>
      </div></div>
    <h4 class="ql-sub">Точная таблица: z и исходные значения</h4>${mTable}
    <p class="note">*_attr — только признаки; *_struct — только связи; *_fused — признаки и связи вместе (итоговая модель: ${esc(Q.method)}). Жирным — лучшее z в столбце. Для DB в данных есть только z, исходное значение отсутствует (н/д). Мин. размер — число МО в самом маленьком кластере.</p></div>`;

  /* ===== Г. важность признаков: две выровненные оси с общей колонкой названий ===== */
  let C2 = '';
  if (ml && ml.imp && ml.imp.length) {
    const IMP = ml.imp.map(r => ({...r, label: featLabel(r.feature)}));   // копии: D.ml.imp не трогаем
    const nZero = IMP.filter(r => r.perm_importance === 0).length, nZeroStd = IMP.filter(r => r.perm_importance === 0 && r.perm_std === 0).length;
    const pv = IMP.filter(r => r.perm_importance != null);
    const pLo = Math.min(0, ...pv.map(r => r.perm_importance - (r.perm_std || 0))), pHi = Math.max(0, ...pv.map(r => r.perm_importance + (r.perm_std || 0)));
    const mHi = Math.max(0, ...IMP.map(r => r.importance ?? 0));
    const iTip = r => esc(`<b>${esc(r.label)}</b><br>MDI: <span class="tnum">${q5(r.importance)}</span><br>Перестановочная: <span class="tnum">${q5(r.perm_importance)}</span>`
      + (r.perm_importance == null ? '' : ` ± <span class="tnum">${q5(r.perm_std)}</span>` + (r.perm_std > 0 ? `<br><span class="tsub">±1 ст. откл.: от ${q5(r.perm_importance - r.perm_std)} до ${q5(r.perm_importance + r.perm_std)}</span>` : ''))
      + (r.perm_importance === 0 ? '<br><span class="tsub">ровно 0: перемешивание не меняло точность</span>' : ''));
    const iRow = r => {
      const m = r.importance, p = r.perm_importance, s = r.perm_std;
      const mdi = m == null ? `<span class="ql-v na" data-side="r" data-at="0"><span class="sr">MDI </span>н/д</span>`
        : `<span class="ql-stem" data-x0="0" data-x1="${m}"></span><span class="ql-dot" data-x="${m}"></span><span class="ql-v" data-side="r" data-at="${m}"><span class="sr">MDI </span>${q5(m)}</span>`;
      const perm = p == null ? `<span class="ql-v na" data-side="r" data-at="0"><span class="sr">перестановочная важность </span>н/д</span>`
        : (s > 0 ? `<span class="ql-wh" data-x0="${p - s}" data-x1="${p + s}"></span>` : '')
          + `<span class="ql-dot${p === 0 ? ' zero' : ''}" data-x="${p}"></span>`
          + `<span class="ql-v${p === 0 ? ' mut' : ''}" data-side="r" data-at="${p + (s > 0 ? s : 0)}"><span class="v1"><span class="sr">перестановочная важность </span>${q5(p)}</span><span class="v2"> ± ${s == null ? '<span class="na">н/д</span>' : q5(s)}</span></span>`;
      return `<div class="ql-r" data-k="${esc(r.feature)}" data-tip="${iTip(r)}"><div class="ql-n">${esc(r.label)}</div>
        <div class="ql-tag ql-g1" aria-hidden="true">MDI</div>${qlTrack('mdi', mdi, 'ql-c1')}
        <div class="ql-tag ql-g2" aria-hidden="true">Перест.</div>${qlTrack('perm', perm, 'ql-c2')}</div>`;
    };
    C2 = `<div class="sec" id="q-imp"><h3 class="sech">Что определяет тип: важность признаков <span class="kicker">${IMP.length} признаков · случайный лес</span></h3>
      <p class="secsub">Две разные метрики на разных осях, без нормировки строк и без общего рейтинга. <b>MDI</b> — среднее снижение неоднородности по 300 деревьям случайного леса (безразмерная величина). <b>Перестановочная важность</b> — падение точности при перемешивании признака; показана исходная величина из данных, без пересчёта. Важность — вклад в предсказание типа, а не причинное влияние.</p>
      <div class="ql-tools"><span class="ql-tl" id="qlILab">Порядок строк</span><div class="seg" role="group" aria-labelledby="qlILab" id="qlISeg">
        <button type="button" data-is="mdi" aria-pressed="true">по MDI</button><button type="button" data-is="perm" aria-pressed="false">по перестановочной</button><button type="button" data-is="abc" aria-pressed="false">по алфавиту</button></div></div>
      <div class="ql-panel">
        <div class="ql-legend in" aria-hidden="true"><span><i class="ql-lg stem"></i>MDI</span><span><i class="ql-lg wh"></i>перестановочная: точка и ±1 стандартное отклонение</span><span><i class="ql-lg zero"></i>ровно 0</span></div>
        <div class="ql-d k-imp" id="qlI">
          <div class="ql-r ql-h" aria-hidden="true"><div class="ql-n"><small id="qlIN">Признак</small></div>
            <div class="ql-tag ql-g1">MDI</div><div class="ql-hc ql-c1" data-col="mdi"><div class="ql-ht"><b>MDI</b> <span>снижение неоднородности</span></div><div class="ql-ax" data-sc="mdi"></div></div>
            <div class="ql-tag ql-g2">Перест.</div><div class="ql-hc ql-c2" data-col="perm"><div class="ql-ht"><b>Перестановочная важность</b> <span>падение точности, ±1 ст. откл.</span></div><div class="ql-ax" data-sc="perm"></div></div></div>
          <div class="ql-b" id="qlIB">${IMP.map(iRow).join('')}</div>
          <div class="ql-r ql-f" aria-hidden="true"><div class="ql-n"></div><div class="ql-tag ql-g1">MDI</div><div class="ql-hc ql-c1"><div class="ql-ax" data-sc="mdi"></div></div><div class="ql-tag ql-g2">Перест.</div><div class="ql-hc ql-c2"><div class="ql-ax" data-sc="perm"></div></div></div>
        </div>
        <p class="ql-cap"><b>±1 стандартное отклонение по перестановкам — не 95% доверительный интервал и не причинное влияние признака.</b> ${nZero ? `У ${nZero} из ${IMP.length} признаков перестановочная важность ровно 0${nZeroStd === nZero ? ' и стандартное отклонение тоже 0' : ''}: перемешивание каждого из них по отдельности не меняло точность. Это настоящие нули из данных — они стоят на нуле оси, полос минимальной длины нет. MDI у этих признаков больше нуля: метрики измеряют разное. ` : ''}При равной перестановочной важности порядок — по MDI.</p>
      </div>
      <details class="ql-det"><summary>${ICON.chev}<span>Таблица чисел: все ${IMP.length} признаков, точные значения</span></summary>
        <div class="tbox" tabindex="0" role="region" aria-label="Важность признаков, таблица (прокручивается)"><table><caption class="sr">Важность признаков: MDI и перестановочная важность со стандартным отклонением</caption>
          <thead><tr><th scope="col" class="n">№</th><th scope="col">Признак</th><th scope="col" class="n">MDI</th><th scope="col" class="n">Перестановочная</th><th scope="col" class="n">Ст. откл. по перестановкам</th><th scope="col" class="n">Перестановочная ±1 ст. откл.</th></tr></thead>
          <tbody id="qlIT"></tbody></table></div></details></div>`;

    QL.imp = IMP;
  }

  /* ===== Д. вклад слоёв: ARI с итоговой моделью на оси 0…1 + все показатели в таблице ===== */
  const LAY = Q.edges_cmp.slice().sort((a, b) => (b.ARI_vs_final ?? -1) - (a.ARI_vs_final ?? -1));
  const LF = ['ARI_vs_final', 'MQ', 'SW', 'CH', 'DB', 'S_Dbw', 'AVI', 'AVU'].filter(k => LAY.some(r => r[k] != null));
  const C3 = `<div class="sec" id="q-layers"><h3 class="sech">Вклад каждого слоя связей <span class="kicker">${LAY.length} слоёв</span></h3>
    <p class="secsub">Кластеризация только по одному слою и её совпадение с итоговой моделью (ARI: 1 — полное совпадение, 0 — уровень случайного разбиения). Названия слоёв — как на карте. Ни один слой не повторяет итог: модель совмещает признаки и разные связи.</p>
    <div class="ql-panel"><div class="ql-d k-l" id="qlL">
      <div class="ql-r ql-h" aria-hidden="true"><div class="ql-n"><small>Слой</small></div><div class="ql-hc ql-c1"><div class="ql-ht"><b>ARI с итоговой моделью</b> <span>0…1</span></div><div class="ql-ax" data-sc="lari"></div></div></div>
      <div class="ql-b">${LAY.map(r => `<div class="ql-r"><div class="ql-n">${esc(LN(r.edges))}</div>${qlTrack('lari', r.ARI_vs_final == null ? `<span class="ql-v na" data-side="r" data-at="0">н/д</span>`
        : `<span class="ql-stem" data-x0="0" data-x1="${r.ARI_vs_final}"></span><span class="ql-dot" data-x="${r.ARI_vs_final}"></span><span class="ql-v" data-side="r" data-at="${r.ARI_vs_final}">${qlFix(r.ARI_vs_final, 3)}</span>`, 'ql-c1')}</div>`).join('')}</div>
      <div class="ql-r ql-f" aria-hidden="true"><div class="ql-n"></div><div class="ql-hc ql-c1"><div class="ql-ax" data-sc="lari"></div></div></div>
    </div></div>
    <details class="ql-det"><summary>${ICON.chev}<span>Все показатели слоёв: ARI, MQ, SW, CH, DB, S_Dbw, AVI, AVU, мин. размер</span></summary>
      <div class="tbox" tabindex="0" role="region" aria-label="Показатели слоёв (прокручивается)"><table><caption class="sr">Показатели кластеризации по отдельным слоям связей</caption><thead><tr><th scope="col">Слой</th>${LF.map(k => `<th scope="col" class="n">${k === 'ARI_vs_final' ? 'ARI с итогом' : k}</th>`).join('')}<th scope="col" class="n">мин. размер</th></tr></thead><tbody>
      ${LAY.map(r => `<tr><th scope="row">${esc(LN(r.edges))}</th>${LF.map(k => `<td class="n">${q4(r[k])}</td>`).join('')}<td class="n">${r.minsize ?? 'н/д'}</td></tr>`).join('')}</tbody></table></div></details>
    <p class="note">MQ — модулярность разбиения этого слоя; SW, CH, DB, S_Dbw, AVI, AVU — индексы качества кластеризации в исходных единицах (не z). Мин. размер — число МО в самом маленьком кластере.</p></div>`;

  /* ===== Е. устойчивость во времени: последовательность соседних кварталов ===== */
  /* подпись перехода: на узком графике короче (Q1→2), чтобы 7 подписей не налезали друг на друга */
  const qLab = (r, nw) => { const y1 = r.from.slice(0, 4), y2 = r.to.slice(0, 4);
    return r.from.slice(4) + '→' + (nw ? r.to.slice(5) : r.to.slice(4)) + '\n' + (y1 === y2 ? y1 : nw ? y1.slice(2) + '→' + y2.slice(2) : y1 + '→' + y2.slice(2)); };
  const D1 = `<div class="sec" id="q-qari"><h3 class="sech">Согласованность соседних кварталов <span class="kicker">ARI, 0…1 · ${Q.qari.length} переходов</span></h3>
    <p class="secsub">Типы по скользящим кварталам (эволюционная спектральная кластеризация); ARI показывает, насколько разбиение квартала совпадает со следующим. Это не та же величина, что бутстреп-ARI выше. Переходы отдельных МО — на карте в режиме «Тип по кварталам» и в карточке МО.</p>
    <div class="ql-panel"><div id="qlQ" class="ql-qari" role="img" aria-label="ARI между соседними кварталами: ${Q.qari.map(r => `${r.from}→${r.to} ${fmtN(r.ARI, 2)}`).join('; ')}"></div></div>
    <details class="ql-det"><summary>${ICON.chev}<span>Таблица: ARI по ${Q.qari.length} парам соседних кварталов</span></summary>
      <div class="tbox ql-narrow"><table><thead><tr><th scope="col">Из квартала</th><th scope="col">В квартал</th><th scope="col" class="n">ARI</th></tr></thead><tbody>
      ${Q.qari.map(r => `<tr><td>${esc(r.from)}</td><td>${esc(r.to)}</td><td class="n">${q4(r.ARI)}</td></tr>`).join('')}</tbody></table></div></details></div>`;

  /* ===== Ж. сопоставимость признаков в годы проверки: dumbbell на оси 0…1 ===== */
  let D2 = '';
  const feats = yrs.length ? Object.keys(V.holdout[yrs[0]].feature_rank_corr || {}) : [];
  if (feats.length) {
    const y0 = yrs[0], y1 = yrs[1];
    const fr = (y, f) => (V.holdout[y].feature_rank_corr || {})[f];
    const FO = feats.slice().sort((a, b) => (fr(y0, b) ?? -9) - (fr(y0, a) ?? -9));
    const rLo = Math.min(0, ...FO.flatMap(f => yrs.map(y => fr(y, f))).filter(v => v != null));
    D2 = `<div class="sec" id="q-rank"><h3 class="sech">Сопоставимость признаков в годы проверки <span class="kicker">ранговая корреляция</span></h3>
      <p class="secsub">Поле feature_rank_corr из данных проверки: ранговая корреляция каждого закупочного признака по МО для года проверки. Чем ниже значение, тем сильнее изменилась структура закупок относительно периода построения — и тем труднее узнать тип. Строки упорядочены по ${esc(y0)}.</p>
      <div class="ql-panel"><div class="ql-legend in" aria-hidden="true">${yrs.map((y, k) => `<span><i class="ql-lg ${k ? 'dia' : 'dot2'}"></i>${esc(y)}</span>`).join('')}${y1 ? `<span><i class="ql-lg conn"></i>разница между годами</span>` : ''}</div>
        <div class="ql-d k-r" id="qlR">
          <div class="ql-r ql-h" aria-hidden="true"><div class="ql-n"><small>Признак</small></div><div class="ql-hc ql-c1"><div class="ql-ht"><b>Ранговая корреляция</b> <span>по МО</span></div><div class="ql-ax" data-sc="rk"></div></div>${yrs.map((y, k) => `<div class="ql-hc ql-hn ql-y${k + 1}"><b>${esc(y)}</b></div>`).join('')}</div>
          <div class="ql-b">${FO.map(f => { const a = fr(y0, f), b = y1 ? fr(y1, f) : null;
            return `<div class="ql-r"><div class="ql-n">${esc(featLabel(f))}</div>${qlTrack('rk', (a != null && b != null ? `<span class="ql-conn" data-x0="${a}" data-x1="${b}"></span>` : '')
              + (a != null ? `<span class="ql-dot y0" data-x="${a}"></span>` : '') + (b != null ? `<span class="ql-dia" data-x="${b}"></span>` : ''), 'ql-c1')}
              ${yrs.map((y, k) => `<div class="ql-num ql-y${k + 1} mono">${fr(y, f) == null ? '<span class="na">н/д</span>' : qlFix(fr(y, f), 3)}</div>`).join('')}</div>`; }).join('')}</div>
          <div class="ql-r ql-f" aria-hidden="true"><div class="ql-n"></div><div class="ql-hc ql-c1"><div class="ql-ax" data-sc="rk"></div></div></div>
        </div></div></div>`;
    QL.rk = {lo: rLo, hi: 1};
  }

  /* ===== З. пояснения и ограничения ===== */
  const E = `<div class="sec" id="q-limits"><h3 class="sech">Пояснения и ограничения</h3><ul class="ql-limits">
    <li>z-значения ICVI сравнивают методы между собой на шкале «стандартных отклонений от случайного разбиения»; это не вероятность и не «доверие в процентах».</li>
    <li>ARI (бутстреп, кварталы, слои) измеряет совпадение разбиений на шкале до 1; это не доля правильных ответов.</li>
    <li>Точность ML и проверка на новых данных — доли совпавших типов; рядом всегда показан базовый уровень.</li>
    <li>Проверка на новых данных использует только закупочные признаки ${yrs.map(esc).join(' и ')} — остальные источники для этих лет в модель не подавались. Годы проверки и данные построения не соединяются в один временной ряд.</li>
    <li>p = 0 — так значение записано в данных. Если p считался как доля случайных повторов с не менее сильным результатом, это значит, что ни один повтор его не достиг; число повторов в данных не указано, поэтому более точная граница p не приводится. p = 0 не означает, что случайное совпадение невозможно.</li>
    <li>Важность признаков — вклад в предсказание, а не причинный эффект. MDI и перестановочная важность — разные величины на разных осях; общего рейтинга из них не строится.</li>
    <li>Усы перестановочной важности — ±1 стандартное отклонение по перестановкам, а не 95% доверительный интервал. Нулевое стандартное отклонение — ноль; отсутствующее показывается как н/д, а не как 0.</li>
    <li>Разнородные проверки (точность, ARI, расстояния, z) не сводятся в общий балл: у каждой своя шкала и свой базовый уровень.</li>
    <li>Типы построены по периоду ${esc(D.period)}; дата сборки (${esc(D.generated)}) — время пересчёта, а не период наблюдений.</li></ul></div>`;

  $('#qual').innerHTML = A + B + C1 + C2 + C3 + D1 + D2 + E;

  /* ---------- оси и раскладка ---------- */
  $$('#qual .ql-d.k-b').forEach(R => { const k = R.dataset.chart;
    const fmt = k === 'km' ? (t, st) => fmtN(t, qlDec(st)) : k === 'ari' ? qlTick : (t => fmtN(t * 100, 0) + '%');
    const hi = k === 'km' ? Math.max(sp.within_km, sp.random_mean_km) : 1;
    qlRegister(R, {[k]: {lo: 0, hi, fmt}}); });
  const zSc = {lo: zLo, hi: zHi, fmt: qlTick};
  QL.mChart = qlRegister($('#qlM'), {z: zSc});
  if (ml && $('#qlI')) {
    const pv = QL.imp.filter(r => r.perm_importance != null);
    QL.iChart = qlRegister($('#qlI'), {
      mdi: {lo: 0, hi: Math.max(0, ...QL.imp.map(r => r.importance ?? 0)), fit: true},
      perm: {lo: Math.min(0, ...pv.map(r => r.perm_importance - (r.perm_std || 0))), hi: Math.max(0, ...pv.map(r => r.perm_importance + (r.perm_std || 0))), fit: true}});
  }
  qlRegister($('#qlL'), {lari: {lo: 0, hi: 1}});
  if ($('#qlR')) qlRegister($('#qlR'), {rk: {lo: QL.rk.lo, hi: QL.rk.hi}});

  /* ---------- методы: выбор показателя → точка скользит, строки переставляются ---------- */
  const setM = (k, focus) => {
    QL.mk = k;
    $$('#qlMSeg [data-mk]').forEach(b => b.setAttribute('aria-pressed', b.dataset.mk === k));
    $('#qlMName').textContent = mkName(k);
    const rows = $$('#qlMB > .ql-r'), byK = new Map(Q.icvi.map(r => [r.method, r]));
    rows.forEach(el => { const r = byK.get(el.dataset.k), v = r['z_' + k];
      const dot = el.querySelector('.ql-dot.main'); dot.dataset.x = v ?? 0; dot.hidden = v == null;
      el.querySelectorAll('.ql-cx').forEach(c => c.classList.toggle('on', c.dataset.ix === k));
      el.querySelector('.ql-num').innerHTML = v == null ? '<span class="na">н/д</span>' : qlFix(v, 2); });
    const order = rows.slice().sort((a, b) => (byK.get(b.dataset.k)['z_' + k] ?? -1e9) - (byK.get(a.dataset.k)['z_' + k] ?? -1e9) || Q.icvi.indexOf(byK.get(a.dataset.k)) - Q.icvi.indexOf(byK.get(b.dataset.k)));
    qlFlip($('#qlMB'), order);
    qlLayout(QL.mChart, true);
    $$('#q-methods .ql-mtab [data-ix]').forEach(c => c.classList.toggle('on', c.dataset.ix === k));
    if (focus) announce(`Методы упорядочены по показателю ${mkName(k)}.`);
  };
  $('#qlMSeg').addEventListener('click', e => { const b = e.target.closest('[data-mk]'); if (b) setM(b.dataset.mk, true); });
  $('#qlM').addEventListener('click', e => { const c = e.target.closest('.ql-cx'); if (c) setM(c.dataset.ix, true); });
  setM(MK[0], false);

  /* ---------- важность: сортировка по выбранной метрике ---------- */
  if (ml && $('#qlI')) {
    const cmpMdi = (a, b) => (b.importance ?? -1e9) - (a.importance ?? -1e9) || a.label.localeCompare(b.label, 'ru');
    const SORTS = {mdi: cmpMdi, perm: (a, b) => (b.perm_importance ?? -1e9) - (a.perm_importance ?? -1e9) || cmpMdi(a, b), abc: (a, b) => a.label.localeCompare(b.label, 'ru')};
    const SNAME = {mdi: 'по MDI', perm: 'по перестановочной важности', abc: 'по алфавиту'};
    const setI = (k, user) => {
      QL.is = k;
      $$('#qlISeg [data-is]').forEach(b => b.setAttribute('aria-pressed', b.dataset.is === k));
      $$('#qlI .ql-h [data-col]').forEach(c => c.classList.toggle('on', c.dataset.col === k));
      $('#qlIN').textContent = k === 'abc' ? 'Признак, А → Я' : 'Признак';
      const order = QL.imp.slice().sort(SORTS[k]);
      const rows = $$('#qlIB > .ql-r'), el = new Map(rows.map(r => [r.dataset.k, r]));
      qlFlip($('#qlIB'), order.map(r => el.get(r.feature)));
      $('#qlIT').innerHTML = order.map((r, j) => `<tr><td class="n">${j + 1}</td><th scope="row">${esc(r.label)}</th><td class="n">${q5(r.importance)}</td><td class="n">${q5(r.perm_importance)}</td>
        <td class="n">${r.perm_importance == null ? 'н/д' : q5(r.perm_std)}</td>
        <td class="n">${r.perm_importance == null ? 'н/д' : r.perm_std == null ? 'ст. откл. н/д' : r.perm_std === 0 ? 'интервал нулевой ширины' : `от ${q5(r.perm_importance - r.perm_std)} до ${q5(r.perm_importance + r.perm_std)}`}</td></tr>`).join('');
      if (user) announce(`Признаки упорядочены ${SNAME[k]}.`);
    };
    $('#qlISeg').addEventListener('click', e => { const b = e.target.closest('[data-is]'); if (b) setI(b.dataset.is, true); });
    setI('mdi', false);
  }

  /* ---------- квартальная согласованность: ECharts, тема и размер — через makeChart ---------- */
  /* три раскладки по реальной ширине: широкая и узкая — время по горизонтали; очень узкая (< 300 px) —
     переходы строками сверху вниз, ARI по горизонтали, чтобы семь подписей не сталкивались */
  const qMode = w => w < 300 ? 'tiny' : w < 520 ? 'narrow' : 'wide';
  QL.qChart = makeChart($('#qlQ'), ch => {
    const ink = css('--ink'), ink2 = css('--ink2'), acc = css('--accent'), sur = css('--surface'), soft = css('--line-soft'), mono = 'JetBrains Mono, monospace';
    const mode = QL.qMode = qMode($('#qlQ').clientWidth), nw = mode !== 'wide', tiny = mode === 'tiny';
    const valAx = {type: 'value', min: 0, max: 1, interval: tiny ? .5 : .25, name: tiny ? '' : 'ARI', nameTextStyle: {color: ink2, fontSize: 12, align: tiny ? 'left' : 'right'}, nameLocation: 'end', splitLine: {lineStyle: {color: soft}},
      axisLabel: {formatter: v => v === 0 ? '0' : fmtN(v, tiny ? 1 : 2), fontFamily: mono, fontSize: 11.5, color: ink2}};
    const catAx = {type: 'category', data: Q.qari.map(r => tiny ? `${r.from.slice(2, 4)} ${r.from.slice(4)}→${r.to.slice(0, 4) === r.from.slice(0, 4) ? '' : r.to.slice(2, 4) + ' '}${r.to.slice(4)}` : qLab(r, nw)),
      inverse: tiny, axisTick: {alignWithLabel: true}, axisLabel: {interval: 0, fontSize: 12, lineHeight: 16, color: ink2, hideOverlap: false}};
    return {
      animationDuration: 500, animationEasing: 'cubicOut',
      grid: tiny ? {left: 82, right: 40, top: 26, bottom: 12} : {left: nw ? 36 : 44, right: nw ? 10 : 16, top: 30, bottom: 46},
      tooltip: {trigger: 'item', formatter: p => { const r = Q.qari[p.dataIndex]; return `<b>${esc(r.from)} → ${esc(r.to)}</b><br>ARI <span style="font-family:${mono}">${q4(r.ARI)}</span>`; }},
      xAxis: tiny ? {...valAx, position: 'top', nameTextStyle: {color: ink2, fontSize: 12}} : catAx,
      yAxis: tiny ? catAx : valAx,
      series: [{type: 'line', data: Q.qari.map(r => r.ARI), symbol: 'circle', symbolSize: 9, lineStyle: {width: 1.5, color: ink2}, itemStyle: {color: acc, borderColor: sur, borderWidth: 1.5},
        emphasis: {scale: 1.35}, label: {show: true, position: tiny ? 'right' : 'top', distance: 7, formatter: p => fmtN(p.value, 2), fontFamily: mono, fontSize: 12, color: ink}}]
    };
  }, {renderer: 'svg'});
  onResize($('#qlQ'), r => { if (qMode(r.width) !== QL.qMode && QL.qChart.chart) QL.qChart.refresh(true); });

  /* ---------- подсказки (дублируют видимые числа; не единственный путь к значению) ---------- */
  const qual = $('#qual');
  qual.addEventListener('mousemove', e => { const t = e.target.closest('[data-tip]'); if (t) showTip(e, t.dataset.tip); else hideTip(); });
  qual.addEventListener('mouseleave', hideTip);
  $$('#qual .ql-checks a').forEach(a => a.onclick = e => { e.preventDefault(); const t = $(a.getAttribute('href')); if (!t) return;
    t.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); t.setAttribute('tabindex', '-1'); t.focus({preventScroll: true}); });

  /* ---------- мягкое появление меток при первом входе (без reduced motion) ---------- */
  onTab('quality', () => {
    if (QL.entered) return; QL.entered = true;
    if (RM.matches) return;
    requestAnimationFrame(() => {
      $$('#qual .k-imp .ql-b > .ql-r, #qual .k-b .ql-b > .ql-r, #qual .k-l .ql-b > .ql-r').forEach((row, j) => {
        const d = Math.min(j, 16) * 14;
        /* отрыв от базового уровня растёт от базы к результату (у расстояния результат левее базы) */
        row.querySelectorAll('.ql-gain').forEach(s => { s.style.transformOrigin = +s.dataset.x1 < +s.dataset.x0 ? 'right center' : 'left center'; });
        row.querySelectorAll('.ql-stem, .ql-gain').forEach(s => s.animate([{transform: 'scaleX(0)'}, {transform: 'scaleX(1)'}], {duration: 420, delay: d, easing: 'cubic-bezier(.25,.75,.3,1)', fill: 'backwards'}));
        row.querySelectorAll('.ql-wh').forEach(s => s.animate([{transform: 'scaleX(0)', opacity: 0}, {transform: 'scaleX(1)', opacity: 1}], {duration: 380, delay: d + 120, easing: 'ease-out', fill: 'backwards'}));
        row.querySelectorAll('.ql-dot, .ql-base').forEach(s => s.animate([{opacity: 0}, {opacity: 1}], {duration: 300, delay: d + 80, easing: 'ease-out', fill: 'backwards'}));
      });
    });
  });
}
