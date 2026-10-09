/* ==========================================================================
   1. Выводы и рекомендации: итог → 8 фактов в трёх смысловых группах →
   темы мер (риски / возможности / ориентиры) → исследуемый список 63 МО.
   Всё строится из D только чтением; производные (медианы типов, счётчики)
   считаются в копиях. Пропуск ≠ 0: МО без значения индекса не проходит условие.
   Глобально наружу выходят только OUT и rows() (вызывается из 99-init.js).
   ========================================================================== */
$('#t-out').innerHTML = String.raw`
  <div class="ohero">
    <div class="ohero-main">
      <div class="eyebrow" id="outEyebrow"></div>
      <p class="olead" id="sumLead"></p>
      <div class="orest" id="sumRest"></div>
    </div>
    <aside class="ohero-side" aria-label="О странице">
      <p class="oside-why">Зачем это: понять, какие экономики у муниципалитетов, как они связаны друг с другом и что делать в каждом районе. Карта, связи и проверка модели — на следующих вкладках.</p>
      <nav class="otoc" id="outToc" aria-label="На этой странице"></nav>
      <div class="okey" id="outKey"></div>
    </aside>
  </div>

  <section class="sec osec" id="sec-facts" aria-labelledby="h-facts">
    <h3 class="sech" id="h-facts" tabindex="-1">Главное по региону <span class="kicker" id="factsCount"></span></h3>
    <p class="secsub">Факты рассчитаны программой по данным; формулировки и числа — без изменений. Малые графики рядом построены из тех же данных: медианы типов, доли, проверка на новых данных.</p>
    <div class="fgroups" id="finds"></div>
  </section>

  <section class="sec osec" id="sec-topics" aria-labelledby="h-topics">
    <h3 class="sech" id="h-topics" tabindex="-1">Где нужны меры <span class="kicker" id="topicsCount"></span></h3>
    <p class="secsub">Темы рекомендаций, найденные правилами над индексами: риски, возможности и ориентиры. Полоса — сколько МО региона с темой и к каким типам они относятся. Список районов темы раскрывается; «Отфильтровать» оставит в списке ниже только их.</p>
    <div class="tgroups" id="topics"></div>
  </section>

  <section class="sec osec" id="sec-list" aria-labelledby="h-list">
    <h3 class="sech" id="h-list" tabindex="-1">Выводы по каждому району <span class="kicker" id="listCount"></span></h3>
    <p class="secsub">У каждой рекомендации — основание (числа, на которых она построена) и действие. Строка раскрывается; выбранный район становится общим для карты, корреляций и типов.</p>
    <div class="filters" id="outFilters" role="search" aria-label="Фильтры списка районов">
      <label class="field fsearch" for="moFilter"><span class="sr">Найти район</span><input type="search" id="moFilter" placeholder="Название района или города" autocomplete="off"></label>
      <label class="field" for="typeFilter"><span>Тип</span><select id="typeFilter"></select></label>
      <label class="field" for="topicFilter"><span>Тема</span><select id="topicFilter"></select></label>
      <label class="field" for="preset"><span>Отбор по индексам</span><select id="preset"></select></label>
      <button class="btn ghost sm" id="fltReset" type="button" hidden>${ICON.reset}<span>Сбросить</span></button>
    </div>
    <div id="condBox"></div>
    <div class="listbar">
      <p class="lcount" id="moCount" aria-live="polite"></p>
      <div class="lacts">
        <span id="selPill"></span>
        <button class="btn sm" id="grpMap" type="button" hidden></button>
        <button class="btn ghost sm" id="expandAll" type="button" aria-pressed="false">Раскрыть все</button>
      </div>
    </div>
    <div class="molist" id="moRows"></div>
  </section>`;

const OUT = (() => {
  const SUM = (D.summary || []).slice();
  const FIND = (D.findings || []).slice();
  const ixKeys = Object.keys(D.metrics);
  const goTo = el => { if (!el) return; el.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); };
  const nsp = s => String(s).replace(/[   ]/g, ' ');

  /* числа в тексте: только типографика (tabular-nums, полужирный), сам текст не меняется */
  const NUMRE = /[−-]?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?(?:\s?(?:₽|%|‰|км))?|[−-]?\d+(?:[.,]\d+)?(?:[–-]\d+(?:[.,]\d+)?)?(?:\s?(?:₽|%|‰|км|раза|мес))?/g;
  const hlNums = s => esc(s).replace(NUMRE, m => /\d/.test(m) ? `<span class="nn">${m}</span>` : m);

  /* ---------------- итог ---------------- */
  $('#outEyebrow').innerHTML = `<span>Итог: что следует из данных</span><span>${esc(D.period)}</span><span>${n} МО · ${D.k} типов</span>`;
  $('#sumLead').innerHTML = hlNums(SUM[0] || '');
  /* первое предложение абзаца — его тезис (сокращения вроде «г. Уфа» не режут предложение) */
  const SENT = /(?<![\s(][а-яёa-z])[.!?:](?=\s+[А-ЯЁA-Z«])/;
  function firstSentence(t){ let m = SENT.exec(t); if (!m || m.index > 170) { m = /:(?=\s)/.exec(t); if (m && m.index > 90) m = null; }
    return m ? [t.slice(0, m.index + 1), t.slice(m.index + 1)] : ['', t]; }
  $('#sumRest').innerHTML = SUM.slice(1).map((t, k) => { const [a, b] = firstSentence(t);
    return `<p>${a ? `<b>${hlNums(a)}</b>` : ''}${hlNums(b)}</p>`; }).join('');

  /* ---------------- темы ---------------- */
  const byTopic = {};
  N.forEach((x, i) => x.recs.forEach(r => { const a = (byTopic[r.topic] = byTopic[r.topic] || []); if (!a.includes(i)) a.push(i); }));
  const TOPICS = ORDER.filter(t => byTopic[t]).concat(Object.keys(byTopic).filter(t => !ORDER.includes(t)));
  const nRecs = N.reduce((s, x) => s + x.recs.length, 0);
  const byName = (a, b) => N[a].s.localeCompare(N[b].s, 'ru');

  /* ---------------- факты: малые графики из D (сверяются с текстом факта) ---------------- */
  const typeMed = get => D.types.map(t => { const v = t.members.map(i => get(N[i])).filter(z => z != null && Number.isFinite(z)); return {c: t.c, v: median(v), n: v.length, of: t.members.length}; }).filter(d => d.v != null);
  const ext = arr => { let lo = arr[0], hi = arr[0]; arr.forEach(d => { if (d.v < lo.v) lo = d; if (d.v > hi.v) hi = d; }); return [lo, hi]; };
  const has = (txt, s) => nsp(txt).includes(nsp(s));
  const srList = (cap, rows) => `<span class="sr">${esc(cap)}: ${rows.map(esc).join('; ')}.</span>`;

  /* полоса из 7 точек — медианы типов на общей оси; подписаны крайние значения */
  function strip(vals, o){
    const [lo, hi] = ext(vals);
    let a = lo.v, b = hi.v; if (o.zero) { a = Math.min(a, 0); b = Math.max(b, 0); }
    const pad = (b - a) * .07 || 1; a -= pad; b += pad;
    const X = v => ((v - a) / (b - a) * 100).toFixed(2);
    const tip = d => `${typeName(d.c)}: ${o.fmt(d.v)}${d.n < d.of ? ` (по ${d.n} из ${d.of} МО)` : ''}`;
    return `<figure class="fviz fstrip${o.zero ? ' has-zero' : ''}">
      <div class="st-track" aria-hidden="true">${o.zero ? `<span class="st-zero" style="left:${X(0)}%"></span><span class="st-zl" style="--x:${X(0)}">0</span>` : ''}
        ${vals.map(d => `<span class="st-dot${d === lo || d === hi ? ' ext' : ''}" style="left:${X(d.v)}%;--c:${COLV(d.c)}" data-tip="${esc(tip(d))}"></span>`).join('')}</div>
      <div class="st-labs" aria-hidden="true"><span class="st-lab lo" style="--x:${X(lo.v)}">${esc(o.fmt(lo.v))}</span><span class="st-lab hi" style="--x:${X(hi.v)}">${esc(o.fmt(hi.v))}</span></div>
      <figcaption>${esc(o.cap)}</figcaption>${srList(o.cap, vals.map(tip))}</figure>`;
  }
  const VIZ = {
    types(f){
      if (!has(f.title, String(D.k))) return '';
      const T = D.types.map(t => ({c: t.c, k: t.members.length}));
      return `<figure class="fviz fcomp"><div class="cp-bar" aria-hidden="true">${T.map(t => `<span style="flex:${t.k};--c:${COLV(t.c)}" data-tip="${esc(typeName(t.c))}: ${t.k} МО"><i></i><b>${t.k}</b></span>`).join('')}</div>
        <figcaption>${D.k} типов, число МО в каждом (всего ${n})</figcaption>${srList('Число МО по типам', T.map(t => `${typeName(t.c)} — ${t.k}`))}</figure>`;
    },
    spend(f){
      const v = typeMed(x => x.f.spend_total); if (v.length < 2) return ''; const [lo, hi] = ext(v);
      if (!has(f.text, fmtN(lo.v, 0)) || !has(f.text, fmtN(hi.v, 0))) return '';
      return strip(v, {fmt: x => fmtN(x, 0) + ' ₽', cap: 'Траты по картам на жителя, ₽ в месяц · медианы 7 типов'});
    },
    rho(f){
      const vals = [...nsp(f.text).matchAll(/ρ\s*=\s*([−-]?\d+(?:,\d+)?)/g)].map(m => +m[1].replace('−', '-').replace(',', '.'));
      if (!vals.length || vals.some(v => !Number.isFinite(v) || Math.abs(v) > 1)) return '';
      const X = v => ((v + 1) / 2 * 100).toFixed(2), cls = v => v <= -.5 ? 'rn2' : v < 0 ? 'rn1' : v < .5 ? 'rp1' : 'rp2';
      return `<figure class="fviz frho"><div class="rh-rows" aria-hidden="true">${vals.map(v => `<div class="rh-row"><span class="rh-trk"><i class="rh-mid"></i><i class="rh-bar ${cls(v)}" style="left:${X(Math.min(v, 0))}%;width:${(Math.abs(v) / 2 * 100).toFixed(2)}%"></i></span><span class="rh-v">${fmtSigned(v, 2)}</span></div>`).join('')}
        <div class="rh-ax"><span class="rh-axl"><span>−1</span><span>0</span><span>+1</span></span><span></span></div></div>
        <figcaption>ρ трёх связей из текста на шкале −1…+1</figcaption>${srList('Коэффициенты ρ', vals.map(v => fmtSigned(v, 2)))}</figure>`;
    },
    local(f){
      const v = typeMed(x => x.f.proc_local_sh); if (v.length < 2) return ''; const [lo, hi] = ext(v);
      if (!has(f.text, `${Math.round(lo.v * 100)}–${Math.round(hi.v * 100)}%`)) return '';
      return strip(v, {fmt: x => fmtN(x * 100, 1) + ' %', cap: 'Доля стоимости контрактов у местных поставщиков · медианы 7 типов'});
    },
    migr(f){
      const v = typeMed(x => x.f.migr_rate); if (v.length < 2) return ''; const [lo, hi] = ext(v);
      if (!has(f.text, fmtN(Math.abs(lo.v), 1)) || !has(f.text, fmtN(Math.abs(hi.v), 1))) return '';
      return strip(v, {zero: true, fmt: x => fmtSigned(x, 1) + ' ‰', cap: 'Миграционный прирост, ‰ в год · медианы 7 типов; 0 — без оттока'});
    },
    ratio(f){
      const v = typeMed(x => { const a = x.f['sh_Маркетплейсы'], b = x.f['sh_Общественное питание']; return a != null && b ? a / b : null; });
      if (v.length < 2) return ''; const [lo, hi] = ext(v);
      if (!has(f.text, `${fmtN(lo.v, 1)}–${fmtN(hi.v, 1)}`)) return '';
      return strip(v, {fmt: x => fmtN(x, 1) + '×', cap: 'Траты на маркетплейсах ÷ на общепит · медианы 7 типов'});
    },
    holdout(f){
      const V = Q && Q.val; if (!V || !V.holdout) return '';
      const ys = Object.keys(V.holdout).sort(), ch = V.chance_mean;
      if (!ys.every(y => has(f.text, Math.round(V.holdout[y].accuracy * 100) + '%'))) return '';
      const rows = ys.map(y => ({y, a: V.holdout[y].accuracy}));
      return `<figure class="fviz fhold"><div class="ho-rows" aria-hidden="true">${rows.map(r => `<div class="ho-row"><span class="ho-y">${esc(r.y)}</span><span class="ho-trk">${ch != null ? `<i class="ho-ch" style="left:${(ch * 100).toFixed(2)}%"></i>` : ''}<i class="ho-ln" style="left:${(Math.min(ch ?? 0, r.a) * 100).toFixed(2)}%;width:${(Math.abs(r.a - (ch ?? 0)) * 100).toFixed(2)}%"></i><i class="ho-dot" style="left:${(r.a * 100).toFixed(2)}%"></i></span><span class="ho-v">${fmtN(r.a * 100, 1)} %</span></div>`).join('')}</div>
        <figcaption>Тип узнан на новых закупках, доля МО (0–100 %)${ch != null ? `; черта — случайный уровень ${fmtN(ch * 100, 1)} %` : ''}</figcaption>
        ${srList('Проверка на новых данных', rows.map(r => `${r.y}: ${fmtN(r.a * 100, 1)} %`).concat(ch != null ? [`случайный уровень ${fmtN(ch * 100, 1)} %`] : []))}</figure>`;
    },
  };
  /* какой малый график подходит факту: по смыслу текста; если числа не совпали — графика нет */
  function vizKind(f){
    const t = (f.title + ' ' + f.text).toLowerCase();
    if (/типов экономики|\d+ типов/.test(f.title.toLowerCase()) && !/провер/.test(t)) return 'types';
    if (/ρ\s*=/.test(f.text)) return 'rho';
    if (/маркетплейс/.test(t) && /общепит/.test(t)) return 'ratio';
    if (/миграцион/.test(t)) return 'migr';
    if (/местным поставщикам|госзаказ уходит/.test(t)) return 'local';
    if (/тратит по картам|разрыв/.test(t)) return 'spend';
    if (/проверены|узнаётся|бутстреп/.test(t)) return 'holdout';
    return f.mos && f.mos.length ? 'mos' : '';
  }
  const FGROUPS = [
    {id: 'struct', label: 'Как устроена экономика', sub: 'типы, разрыв и главная ось', kinds: ['types', 'spend', 'rho']},
    {id: 'leak', label: 'Что уходит из районов', sub: 'госзаказ, люди, траты', kinds: ['local', 'migr', 'ratio']},
    {id: 'base', label: 'На что опереться', sub: 'центры снабжения и проверка', kinds: ['mos', 'holdout', '']}];
  function factHtml(f, k){
    const kd = vizKind(f), viz = VIZ[kd] ? VIZ[kd](f) : '';
    const mos = (f.mos || []).map(m => N.findIndex(z => z.mo === m)).filter(i => i >= 0);
    return `<li class="fact${viz ? '' : ' noviz'}"><div class="f-head"><span class="f-no mono">${String(k + 1).padStart(2, '0')}</span><b class="f-title">${hlNums(f.title)}</b></div>
      ${viz}<p class="f-tx">${hlNums(f.text)}</p>
      ${mos.length ? `<div class="chips f-mos" role="group" aria-label="Районы из факта — открыть на карте">${mos.map(i => `<button class="chip" type="button" data-go="${i}"><span class="sw" style="--c:${COLV(N[i].c)}"></span>${esc(N[i].s)}</button>`).join('')}</div>` : ''}</li>`;
  }
  (function renderFacts(){
    $('#factsCount').textContent = FIND.length + ' фактов';
    const items = FIND.map((f, k) => ({f, k, kd: vizKind(f)}));
    const used = new Set(), groups = FGROUPS.map(g => ({...g, items: items.filter(it => g.kinds.includes(it.kd) && !used.has(it.k) && used.add(it.k))}));
    const rest = items.filter(it => !used.has(it.k)); if (rest.length) groups[groups.length - 1].items.push(...rest);
    groups.forEach(g => g.items.sort((a, b) => a.k - b.k));
    $('#finds').innerHTML = groups.filter(g => g.items.length).map(g => `<div class="fgroup" data-g="${g.id}">
      <div class="fg-h"><h4>${esc(g.label)}</h4><span>${esc(g.sub)}</span></div>
      <ul class="flist">${g.items.map(it => factHtml(it.f, it.k)).join('')}</ul></div>`).join('');
  })();

  /* ---------------- темы мер ---------------- */
  const KIND_COL = [['risk', 'Риски', 'где теряются деньги, люди или конкуренция'], ['opp', 'Возможности', 'на что опереться в соседстве'], ['info', 'Ориентиры и переходные случаи', 'с кем сравнить, где тип может смениться']];
  function compBar(ids){
    const cnt = D.types.map(t => ({c: t.c, k: ids.filter(i => N[i].c === t.c).length})).filter(t => t.k);
    return `<span class="tc-bar" aria-hidden="true" style="--w:${(ids.length / n * 100).toFixed(2)}%"><span class="tc-in">${cnt.map(t => `<i style="flex:${t.k};--c:${COLV(t.c)}" data-tip="${esc(typeName(t.c))}: ${t.k} МО"></i>`).join('')}</span></span>
      <span class="sr">По типам: ${cnt.map(t => `${esc(typeName(t.c))} — ${t.k}`).join('; ')}.</span>`;
  }
  function topicHtml(t, k){
    const ids = byTopic[t].slice().sort(byName), kd = kind(t), id = 'tp' + k;
    return `<li class="trow ${kd}" data-topic="${esc(t)}">
      <div class="tr-h">${mk(kd)}<b>${esc(t)}</b><span class="tr-n"><span class="mono">${ids.length}</span> МО</span></div>
      <div class="tr-bar">${compBar(ids)}<span class="tr-sh mono">${fmtN(ids.length / n * 100, 0)} %</span></div>
      <p class="tr-mean">${esc(MEANING[t] || '')}</p>
      <div class="tr-acts"><button class="link" type="button" data-names aria-expanded="false" aria-controls="${id}">Районы</button>
        <button class="link" type="button" data-filter>Отфильтровать список</button>
        <button class="link" type="button" data-group>${ICON.map}На карте</button></div>
      <div class="chips tr-chips" id="${id}" hidden>${ids.map(i => `<button class="chip" type="button" data-go="${i}"><span class="sw" style="--c:${COLV(N[i].c)}"></span>${esc(N[i].s)}</button>`).join('')}</div></li>`;
  }
  (function renderTopics(){
    let k = 0;
    $('#topicsCount').textContent = `${TOPICS.length} тем · ${nRecs} рекомендаций`;
    $('#topics').innerHTML = KIND_COL.map(([kd, lbl, sub]) => { const ts = TOPICS.filter(t => kind(t) === kd); if (!ts.length) return '';
      const mo = new Set(); ts.forEach(t => byTopic[t].forEach(i => mo.add(i)));
      return `<div class="tgroup ${kd}"><div class="tg-h"><h4>${mk(kd)}${esc(lbl)}</h4><span>${ts.length} ${ts.length === 1 ? 'тема' : ts.length < 5 ? 'темы' : 'тем'} · <span class="mono">${mo.size}</span> МО · ${esc(sub)}</span></div>
        <ul class="tlist">${ts.map(t => topicHtml(t, k++)).join('')}</ul></div>`; }).join('');
    $('#topics').addEventListener('click', e => {
      const row = e.target.closest('.trow'); if (!row) return; const t = row.dataset.topic;
      if (e.target.closest('[data-names]')) { const b = e.target.closest('[data-names]'), box = row.querySelector('.tr-chips'), open = b.getAttribute('aria-expanded') !== 'true';
        box.hidden = !open; b.setAttribute('aria-expanded', open); row.classList.toggle('open', open); }
      else if (e.target.closest('[data-filter]')) { $('#topicFilter').value = t; render(); goTo($('#sec-list')); $('#h-list').focus({preventScroll: true}); }
      else if (e.target.closest('[data-group]')) showGroup(byTopic[t].slice(), `тема «${t}»`);
    });
  })();
  $('#t-out').addEventListener('click', e => { const b = e.target.closest('[data-go]'); if (b && !b.closest('.morow')) goMap(+b.dataset.go); });

  /* подсказки к точкам малых графиков (мышь); значения доступны текстом в .sr */
  $('#t-out').addEventListener('mouseover', e => { const d = e.target.closest('[data-tip]'); if (d) showTip(e, `<b>${esc(d.dataset.tip)}</b>`); });
  $('#t-out').addEventListener('mouseout', e => { if (e.target.closest('[data-tip]')) hideTip(); });

  /* ---------------- оглавление и ключ ---------------- */
  $('#outToc').innerHTML = [['#sec-facts', 'Главное по региону', FIND.length + ' фактов'], ['#sec-topics', 'Где нужны меры', TOPICS.length + ' тем'], ['#sec-list', 'Выводы по каждому району', n + ' МО']]
    .map(([h, l, c]) => `<a href="${h}"><span>${l}</span><span class="mono">${c}</span></a>`).join('');
  $('#outToc').addEventListener('click', e => { const a = e.target.closest('a'); if (!a) return; e.preventDefault(); const s = $(a.getAttribute('href')); goTo(s); const h = s && s.querySelector('h3'); if (h) h.focus({preventScroll: true}); });
  $('#outKey').innerHTML = `<span>${mk('risk')}риск</span><span>${mk('opp')}возможность</span><span>${mk('info')}ориентир, переходный случай</span>`;

  /* ---------------- фильтры ---------------- */
  $('#typeFilter').innerHTML = '<option value="">все типы</option>' + D.types.map(t => `<option value="${t.c}">${esc(t.name)} (${t.members.length})</option>`).join('');
  $('#topicFilter').innerHTML = '<option value="">все темы</option>' + TOPICS.map(t => `<option value="${esc(t)}">${esc(t)} (${byTopic[t].length})</option>`).join('');
  const PRESETS = [
    ['', 'без условий', []],
    ['bud', 'Бюджетная зависимость + низкая активность + отток', [['budget_dep', '>=', 75], ['activity', '<=', 40], ['demo_resilience', '<=', 40]]],
    ['leak', 'Деньги уходят: госзаказ и траты', [['localization', '<=', 30], ['online_leakage', '>=', 70]]],
    ['comp', 'Мало конкуренции в закупках', [['competition', '<=', 25]]],
    ['hub', 'Опорные центры снабжения', [['hub', '>=', 80]]],
    ['grow', 'Сильная экономика, но уходят люди', [['activity', '>=', 70], ['demo_resilience', '<=', 40]]],
    ['own', 'Свои условия…', [['activity', '>=', 50]]]];
  const COND_MAX = 4;
  $('#preset').innerHTML = PRESETS.map(p => `<option value="${p[0]}">${esc(p[1])}</option>`).join('');
  let conds = [];                 // [{k, op, v}] — v: число 0–100 или NaN (не задано)
  const condActive = c => !!c.k && Number.isFinite(c.v);
  const mpOf = (i, k) => { const v = N[i].mp[k]; return v == null || Number.isNaN(v) ? null : v; };
  /* пропуск ≠ 0: МО без значения индекса условие не проходит */
  const passCond = (i, c) => { const v = mpOf(i, c.k); return v != null && (c.op === '>=' ? v >= c.v : v <= c.v); };
  const condOk = i => conds.every(c => !condActive(c) || passCond(i, c));
  const opTxt = op => op === '>=' ? '≥' : '≤';
  const condLabel = c => `${ixLabel(c.k)} ${opTxt(c.op)} ${fmtN(c.v, 0)}`;

  function condUI(){
    const box = $('#condBox'); if (!conds.length) { box.innerHTML = ''; return; }
    const opt = s => '<option value="">— выберите индекс —</option>' + ixKeys.map(k => `<option value="${k}" ${k === s ? 'selected' : ''}>${esc(ixLabel(k))}</option>`).join('');
    box.innerHTML = `<div class="conds" role="group" aria-labelledby="condLbl">
      <div class="cd-h"><b id="condLbl">Условия отбора</b><span>процентиль индекса среди МО, у которых он есть: 0–100, не процент. Должны выполняться все условия («и»).</span></div>
      <ol class="cd-list">${conds.map((c, t) => `<li class="cd-row" data-ci="${t}">
        ${t ? '<span class="cd-and" aria-hidden="true">и</span>' : '<span class="cd-and" aria-hidden="true"></span>'}
        <label class="sr" for="cdk${t}">Индекс условия ${t + 1}</label><select id="cdk${t}" data-f="k">${opt(c.k)}</select>
        <label class="sr" for="cdo${t}">Сравнение ${t + 1}</label><select id="cdo${t}" data-f="op" class="cd-op"><option value=">=" ${c.op === '>=' ? 'selected' : ''}>≥ не ниже</option><option value="<=" ${c.op === '<=' ? 'selected' : ''}>≤ не выше</option></select>
        <label class="sr" for="cdv${t}">Процентиль ${t + 1}, от 0 до 100</label><input id="cdv${t}" type="number" min="0" max="100" step="5" inputmode="numeric" value="${Number.isFinite(c.v) ? c.v : ''}" data-f="v">
        <span class="cd-stat" data-stat></span>
        <button class="btn ghost sm cd-x" type="button" data-rm aria-label="Убрать условие ${t + 1}">${ICON.close}</button></li>`).join('')}</ol>
      <div class="cd-foot"><button class="btn sm" type="button" id="condAdd" ${conds.length >= COND_MAX ? 'disabled' : ''}>${ICON.plus}<span>Условие «и»</span></button><span class="cd-note" id="condNote"></span></div></div>`;
    box.querySelectorAll('[data-f]').forEach(el => el.addEventListener('input', () => {
      const c = conds[+el.closest('[data-ci]').dataset.ci], f = el.dataset.f;
      if (f === 'k') c.k = el.value; else if (f === 'op') c.op = el.value;
      else { const v = el.value === '' ? NaN : +el.value; c.v = Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : NaN; el.setAttribute('aria-invalid', !Number.isFinite(v) || v < 0 || v > 100); }
      $('#preset').value = 'own'; render(); }));
    box.querySelectorAll('[data-rm]').forEach(b => b.addEventListener('click', () => { const t = +b.closest('[data-ci]').dataset.ci; conds.splice(t, 1);
      $('#preset').value = conds.length ? 'own' : ''; condUI(); render();
      const nx = $('#condBox [data-f="k"]'); (nx || $('#preset')).focus(); }));
    const add = $('#condAdd'); if (add) add.addEventListener('click', () => { if (conds.length >= COND_MAX) return; conds.push({k: '', op: '>=', v: 50}); $('#preset').value = 'own'; condUI(); render(); const s = $$('#condBox [data-f="k"]').pop(); if (s) s.focus(); });
  }
  /* статистика условий: сколько МО с данными, сколько пропусков, сколько проходит */
  function condStats(){
    $$('#condBox [data-ci]').forEach(row => { const c = conds[+row.dataset.ci], el = row.querySelector('[data-stat]'); if (!el) return;
      if (!c.k) { el.innerHTML = '<span class="muted">индекс не выбран — условие не действует</span>'; return; }
      const withV = N.filter((x, i) => mpOf(i, c.k) != null).length, miss = n - withV;
      if (!Number.isFinite(c.v)) { el.innerHTML = `<span class="warnt">введите число 0–100 — условие пока не действует</span>`; return; }
      const pass = N.filter((x, i) => passCond(i, c)).length;
      el.innerHTML = `проходят <b class="nn">${pass}</b> · <span class="nn">${withV}</span> с данными${miss ? ` · <span class="nn">${miss}</span> ${miss === 1 ? 'пропуск' : 'пропуска'} (${N.map((x, i) => mpOf(i, c.k) == null ? esc(x.s) : null).filter(Boolean).join(', ')})` : ''}`; });
  }

  /* ---------------- список ---------------- */
  let lastIds = [], OPEN = new Set();
  const q = () => $('#moFilter').value.trim().toLowerCase();
  const fSearch = i => { const s = q(); return !s || N[i].s.toLowerCase().includes(s) || N[i].mo.toLowerCase().includes(s); };
  const fType = i => { const v = $('#typeFilter').value; return v === '' || N[i].c === +v; };
  const fTopic = i => { const v = $('#topicFilter').value; return !v || N[i].recs.some(r => r.topic === v); };
  const filtersActive = () => !!(q() || $('#typeFilter').value || $('#topicFilter').value || conds.some(condActive));
  const typeOrder = new Map(D.types.map((t, k) => [t.c, k]));

  function recBlock(r){
    const kd = kind(r.topic);
    return `<li class="rec2 ${kd}"><div class="r-h">${mk(kd)}<b>${esc(r.topic)}</b><span class="r-kind">${KIND_LABEL[kd]}</span></div>
      <div class="r-b"><div class="r-ev"><span class="r-l">Основание</span><p>${hlNums(r.evidence)}</p></div>
      <div class="r-ac"><span class="r-l">Что сделать</span><p>${esc(r.action)}</p></div></div></li>`;
  }
  function condVals(i){
    const act = conds.filter(condActive); if (!act.length) return '';
    return `<div class="cvals">${act.map(c => { const v = mpOf(i, c.k), ok = passCond(i, c);
      return `<span class="cv ${ok ? 'ok' : 'no'}">${esc(ixLabel(c.k))} <b class="nn">${v == null ? 'н/д' : fmtN(v, 0)}</b></span>`; }).join('')}</div>`;
  }
  const subHtml = i => (N[i].pop != null ? `<span class="nn">${fmtN(N[i].pop, 0)}</span> жит.` : 'население н/д') + (sel === i ? ' · <span class="selmark">выбран</span>' : '');
  function rowHtml(i){
    const x = N[i], m = mainRec(x), open = OPEN.has(i);
    const tags = [...new Set(x.recs.map(r => r.topic))].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
    return `<details class="morow${sel === i ? ' is-sel' : ''}" data-i="${i}" ${open ? 'open' : ''}><summary>
      <div class="m-nm"><span class="nm"><span class="sw" style="--c:${COLV(x.c)}"></span>${esc(x.s)}</span>
        <span class="m-sub">${subHtml(i)}</span></div>
      <div class="m-main">${m ? `<b>${esc(m.topic)}.</b> ${hlNums(m.evidence)}` : '<span class="muted">рекомендаций нет</span>'}${condVals(i)}</div>
      <div class="m-tags">${tags.map(t => `<span class="tag">${mk(kind(t))}${esc(t)}</span>`).join('')}</div>${ICON.chev}</summary>
      <div class="mobody">
        <p class="mb-sum">${hlNums(x.summary)}</p>
        <div class="mb-cols"><div><h5>Рекомендации <span class="mono">${x.recs.length}</span></h5><ol class="recs2">${x.recs.map(recBlock).join('')}</ol></div>
          <div class="mb-anom"><h5>Чем отличается от своего типа</h5>${x.anom.length ? `<ul>${x.anom.map(a => `<li>${hlNums(a)}</li>`).join('')}</ul>` : '<p class="muted">Отклонений от своего типа не выявлено.</p>'}</div></div>
        <div class="mb-acts"><button class="btn" type="button" data-go="${i}">${ICON.map}<span>Показать на карте</span></button>${cmpToggle(i)}</div></div></details>`;
  }
  function emptyHtml(){
    const parts = [];
    if (q()) parts.push([`поиск «${esc($('#moFilter').value.trim())}»`, N.filter((x, i) => fSearch(i)).length]);
    if ($('#typeFilter').value !== '') parts.push([`тип «${esc(typeName(+$('#typeFilter').value))}»`, N.filter((x, i) => fType(i)).length]);
    if ($('#topicFilter').value) parts.push([`тема «${esc($('#topicFilter').value)}»`, N.filter((x, i) => fTopic(i)).length]);
    conds.filter(condActive).forEach(c => parts.push([esc(condLabel(c)), N.filter((x, i) => passCond(i, c)).length]));
    return `<div class="empty oempty"><b>Нет районов, подходящих под все условия сразу</b>
      <span>Каждое условие по отдельности оставляет:</span>
      <ul>${parts.map(([l, k]) => `<li>${l} — <span class="nn">${k}</span> МО</li>`).join('')}</ul>
      <span>Ослабьте самое строгое условие или сбросьте фильтры — список вернётся к ${n} МО.</span>
      <div><button class="btn" type="button" data-reset>${ICON.reset}<span>Сбросить фильтры</span></button></div></div>`;
  }
  function render(){
    const ids = N.map((x, i) => i).filter(i => fSearch(i) && fType(i) && fTopic(i) && condOk(i))
      .sort((a, b) => typeOrder.get(N[a].c) - typeOrder.get(N[b].c) || byName(a, b));
    lastIds = ids;
    const act = conds.filter(condActive);
    const missOut = act.length ? N.map((x, i) => i).filter(i => fSearch(i) && fType(i) && fTopic(i) && act.some(c => mpOf(i, c.k) == null)).length : 0;
    $('#moCount').innerHTML = `Показано <b class="nn">${ids.length}</b> из <span class="nn">${n}</span> МО`
      + (missOut ? ` · <span class="nn">${missOut}</span> без значения индекса в условии — не проходит (пропуск не считается нулём)` : '');
    $('#listCount').textContent = `${n} МО · ${nRecs} рекомендаций`;
    $('#fltReset').hidden = !filtersActive();
    const gm = $('#grpMap'); gm.hidden = !filtersActive() || !ids.length; gm.innerHTML = `${ICON.map}<span>Показать ${ids.length} МО на карте</span>`;
    $$('#topics .trow').forEach(el => el.classList.toggle('on', el.dataset.topic === $('#topicFilter').value));
    condStats();
    const note = $('#condNote'); if (note) note.textContent = act.length ? `Действует условий: ${act.length} из ${conds.length}.` : 'Ни одно условие пока не действует.';
    const ex = $('#expandAll'); ex.hidden = !ids.length;
    const allOpen = ids.length && ids.every(i => OPEN.has(i)); ex.setAttribute('aria-pressed', allOpen ? 'true' : 'false'); ex.textContent = allOpen ? 'Свернуть все' : 'Раскрыть все';
    selPill(ids);
    if (!ids.length) { $('#moRows').innerHTML = emptyHtml(); return; }
    let html = '', cur = null;
    ids.forEach(i => { if (N[i].c !== cur) { if (cur != null) html += '</div>'; cur = N[i].c; const t = D.types.find(z => z.c === cur), k = ids.filter(j => N[j].c === cur).length;
      html += `<div class="mgroup" role="group" aria-label="${esc(typeName(cur))}"><div class="mg-h"><span class="sw" style="--c:${COLV(cur)}"></span><b>${esc(typeName(cur))}</b><span class="mono">${k}${t ? ' из ' + t.members.length : ''}</span></div>`; }
      html += rowHtml(i); });
    $('#moRows').innerHTML = html + '</div>';
  }
  /* выбранный в другом месте МО: быстрый переход к его строке */
  function selPill(ids){
    const el = $('#selPill'); if (sel == null || !N[sel]) { el.innerHTML = ''; return; }
    const vis = ids.includes(sel);
    el.innerHTML = `<span class="selpill"><span class="sw" style="--c:${COLV(N[sel].c)}"></span>Выбран: <b>${esc(N[sel].s)}</b>
      <button class="link" type="button" data-selgo>${vis ? 'к строке' : 'скрыт фильтром — показать'}</button></span>`;
  }
  function openRow(i, focus){
    let d = $(`#moRows .morow[data-i="${i}"]`);
    if (!d) { resetFilters(); d = $(`#moRows .morow[data-i="${i}"]`); }
    if (!d) return;
    OPEN.add(i); d.open = true; goTo(d); if (focus) d.querySelector('summary').focus({preventScroll: true});
  }
  function resetFilters(){ $('#moFilter').value = ''; $('#typeFilter').value = ''; $('#topicFilter').value = ''; $('#preset').value = ''; conds = []; condUI(); render(); }

  /* события списка: раскрытие (общий выбор), карта, сброс */
  $('#moRows').addEventListener('click', e => {
    const s = e.target.closest('summary'); if (s) { const d = s.parentElement, i = +d.dataset.i; if (!d.open && sel !== i) setSel(i); return; }
    const g = e.target.closest('[data-go]'); if (g) { e.preventDefault(); goMap(+g.dataset.go); return; }
    if (e.target.closest('[data-reset]')) { resetFilters(); $('#moFilter').focus(); }
  });
  $('#moRows').addEventListener('toggle', e => { const d = e.target; if (!d.matches || !d.matches('.morow')) return; const i = +d.dataset.i;
    if (d.open) OPEN.add(i); else OPEN.delete(i);
    const ex = $('#expandAll'), all = lastIds.length && lastIds.every(j => OPEN.has(j)); ex.setAttribute('aria-pressed', all ? 'true' : 'false'); ex.textContent = all ? 'Свернуть все' : 'Раскрыть все'; }, true);
  $('#expandAll').addEventListener('click', () => { const open = $('#expandAll').getAttribute('aria-pressed') !== 'true';
    lastIds.forEach(i => open ? OPEN.add(i) : OPEN.delete(i)); $$('#moRows .morow').forEach(d => { d.open = open; });
    $('#expandAll').setAttribute('aria-pressed', open); $('#expandAll').textContent = open ? 'Свернуть все' : 'Раскрыть все';
    announce(open ? `Раскрыто ${lastIds.length} строк.` : 'Все строки свёрнуты.'); });
  $('#selPill').addEventListener('click', e => { if (e.target.closest('[data-selgo]') && sel != null) openRow(sel, true); });
  $('#grpMap').addEventListener('click', () => {
    const parts = []; if (q()) parts.push(`поиск «${$('#moFilter').value.trim()}»`); if ($('#typeFilter').value !== '') parts.push(`тип «${typeName(+$('#typeFilter').value)}»`);
    if ($('#topicFilter').value) parts.push(`тема «${$('#topicFilter').value}»`); conds.filter(condActive).forEach(c => parts.push(condLabel(c)));
    showGroup(lastIds.slice(), parts.length ? parts.join(' и ') : 'список выводов'); });
  $('#fltReset').addEventListener('click', () => { resetFilters(); $('#moFilter').focus(); });
  $('#preset').addEventListener('input', () => { const p = PRESETS.find(z => z[0] === $('#preset').value) || PRESETS[0]; conds = p[2].map(c => ({k: c[0], op: c[1], v: c[2]})); condUI(); render(); });
  ['moFilter', 'typeFilter', 'topicFilter'].forEach(id => $('#' + id).addEventListener('input', render));

  /* общий выбор МО: подсветка строки без перерисовки списка */
  SEL_HOOKS.push(() => {
    $$('#moRows .morow').forEach(d => { const i = +d.dataset.i, on = i === sel, was = d.classList.contains('is-sel');
      if (on !== was) { d.classList.toggle('is-sel', on); const sub = d.querySelector('.m-sub'); if (sub) sub.innerHTML = subHtml(i); } });
    selPill(lastIds);
  });

  /* малые графики фактов: подписи крайних значений не должны пересекаться (реальные размеры) */
  function declutter(){
    $$('#finds .fstrip').forEach(f => {
      /* точки с близкими значениями — в соседний ряд (простое «уклонение»), положение по оси не меняется */
      const tr = f.querySelector('.st-track'), W = tr.clientWidth, ends = []; let maxR = 0;
      [...tr.querySelectorAll('.st-dot')].map(d => ({d, x: parseFloat(d.style.left) / 100 * W})).sort((a, b) => a.x - b.x).forEach(o => {
        let r = 0; while (ends[r] != null && o.x - ends[r] < 11) r++; ends[r] = o.x; o.d.style.setProperty('--r', r); maxR = Math.max(maxR, r); });
      f.style.setProperty('--rows', maxR + 1);
      const lo = f.querySelector('.st-lab.lo'), hi = f.querySelector('.st-lab.hi');
      [lo, hi].forEach(l => l && l.classList.remove('up')); f.classList.remove('has-up');
      const hit = (a, b) => { if (!a || !b) return false; const r = a.getBoundingClientRect(), s = b.getBoundingClientRect(); return r.left < s.right + 6 && s.left < r.right + 6 && r.top < s.bottom && s.top < r.bottom; };
      if (hit(lo, hi)) { hi.classList.add('up'); f.classList.add('has-up'); } });
  }
  FONTS_READY.then(() => whenSized($('#finds'), () => { declutter(); onResize($('#finds'), declutter); }));

  return {render, openRow, resetFilters, byTopic, get ids(){ return lastIds.slice(); }};
})();
function rows(){ OUT.render(); }
