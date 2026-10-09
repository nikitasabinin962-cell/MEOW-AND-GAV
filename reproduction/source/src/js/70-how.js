/* ==========================================================================
   7. Как это работает: обзор → 9 этапов → индексы и формулы → источники и
   ссылки → период → другие регионы → обновление → неоднозначности →
   «О проекте и технические проверки» (раскрывается, по умолчанию свёрнут).
   Глобально наружу: HOW и howInit() (вызывается из 99-init.js).
   ========================================================================== */
$('#t-how').innerHTML = String.raw`  <div class="phead">
    <div><h2>Как это работает</h2>
      <p class="lede">Методика расчёта: девять этапов программы <code>econtypes</code>, ${Object.keys(D.metrics).length} индексов с формулами, источники, перенос на другие регионы и обновление данных. Технические проверки — в последнем разделе.</p></div>
  </div>
  <div id="how"></div>`;

const HOW = {};
function howInit(){
  const STEPS = [
    ['ingest', 'Данные в базу', 'Реестр контрактов ЕИС (44-ФЗ), траты по картам и расстояния СберИндекса, демография и бюджет Башкортостанстата, занятость и зарплаты БД ПМО Росстата. Контракты привязываются к МО по ИНН заказчика и поставщика.'],
    ['features', 'Профиль МО', 'Госзаказ на жителя, доля местных поставщиков, отраслевая структура по ОКПД2, структура трат населения, демография, дотации, занятость, плотность. Робастная нормировка, пропуски — kNN-заполнение.'],
    ['network', 'Сеть МО', 'Слои: синхронность месячных трат, опережение на 1–3 мес., сходство формы рядов (DTW), денежные потоки госзаказа между МО, сходство признаков. Каждый слой прорежен до ' + D.knn + ' соседей и взвешен.'],
    ['cluster', 'Типы (без учителя)', '7 методов: k-means, Уорд, GMM по признакам; спектральная кластеризация и Louvain по связям и по совмещённой сети. Число типов выбирается автоматически по индексам качества.'],
    ['icvi', 'Оценка качества', 'SW, CH, DB, S_Dbw, модулярность, AVI, AVU нормируются на случайные перестановки, чтобы сравнивать методы на одной шкале.'],
    ['dynamics', 'Динамика', 'Эволюционная спектральная кластеризация по скользящим четырём кварталам: видно, какие МО меняют тип.'],
    ['explain', 'Объяснение (с учителем)', 'Случайный лес учится предсказывать тип по признакам; точность на отложенных МО и важность признаков показывают, что типы осмысленны. Модель классифицирует МО на новых данных.'],
    ['metrics', 'Индексы и связи', '13 индексов (локализация, конкуренция, бюджетная зависимость, хаб снабжения…), корреляции Спирмена с поправкой FDR, частные корреляции, лаги.'],
    ['report', 'Выводы и рекомендации', 'Правила над процентилями индексов и сравнением с медианой своего типа. Каждая рекомендация показывает числа, на которых она основана.']];
  const PH = [['Данные', 'сбор и профиль', 3], ['Модель', 'типы и их проверка', 4], ['Результат', 'индексы и выводы', 2]];
  const WHERE = {localization: 'карточка МО → Индексы', external_dep: 'карточка МО → Индексы', competition: 'карточка МО → Индексы', budget_dep: 'карточка МО → Индексы; выводы', online_leakage: 'карточка МО → Индексы; выводы',
    activity: 'карточка МО → Индексы; выводы', demo_resilience: 'карточка МО → Индексы; выводы', hub: 'карточка МО → Индексы; выводы', supply_reach: 'карточка МО → Индексы', bridge: 'карточка МО → Индексы', sync: 'карточка МО → Индексы', leadership: 'карточка МО → Индексы', typicality: 'карточка МО → Индексы; пунктир на карте'};
  const SRC = [
    ['Реестр контрактов ЕИС (44-ФЗ)', 'контракты муниципальных заказчиков: стоимость, ОКПД2, ИНН заказчика и поставщика', 'привязка к МО по ИНН → доли местных, уфимских и внешних поставщиков, отраслевая структура, потоки ₽ между МО'],
    ['СберИндекс', 'безналичные траты по картам по месяцам и категориям; расстояния между МО', 'траты на жителя и их структура, ряды для синхронности, опережения и DTW; слой «близость по дорогам»'],
    ['Башкортостанстат', 'демография и бюджет', 'рождаемость, смертность, миграционный прирост, дотации на выравнивание на жителя'],
    ['БД ПМО Росстата', 'занятость и зарплаты', 'средняя зарплата, работники на 1000 жителей, структура занятости'],
    ['geoBoundaries / OpenStreetMap', 'границы МО', 'геометрия карты; в расчёт типов местоположение не входит']];
  const LINKS = {about: 'https://elena30r.github.io/econtypes/', pdf: 'https://elena30r.github.io/econtypes/report.pdf', code: 'https://github.com/Elena30R/econtypes'};
  const TOC = [['h-short', 'Коротко'], ['h-steps', 'Девять этапов'], ['h-ix', 'Индексы и формулы'], ['h-src', 'Источники и ссылки'], ['h-period', 'Период и сборка'],
    ['h-reg', 'Другие регионы'], ['h-upd', 'Обновление данных'], ['h-amb', 'Неоднозначности'], ['h-about', 'О проекте и проверки']];

  /* ---------- набор формул: записаны по описаниям D.metrics; параметры, которых в описании нет, не придумываются ---------- */
  const v = (s, sub, sup) => `<span class="fv">${s}${sup && sub ? `<span class="fsc"><span>${sup}</span><span>${sub}</span></span>` : sup ? `<sup>${sup}</sup>` : sub ? `<sub>${sub}</sub>` : ''}</span>`;
  const fr = (a, b) => `<span class="ffr"><span class="ffn">${a}</span><span class="ffd">${b}</span></span>`;
  const op = s => `<span class="fop">${s}</span>`;
  const fn = s => `<span class="ffn2">${s}</span>`;
  const P = s => `<span class="fpg">${fn('P')}(${s})</span>`;
  const brk = s => `[\u00a0${s}\u00a0]`;
  const FX = {
    localization: [`${v('Л', 'i')} ${op('=')} ${fr(v('V', 'i', 'мест'), v('V', 'i'))}`, 'V — стоимость контрактов муниципальных заказчиков МО i; «мест» — у поставщиков из того же МО'],
    external_dep: [`${v('В', 'i')} ${op('=')} ${v('s', 'i', 'Уфа')} ${op('+')} ${v('s', 'i', 'вне РБ')}`, 's — доля контрактов у поставщиков из Уфы и из-за пределов РБ'],
    competition: [`${v('К', 'i')} ${op('=')} 1 ${op('−')} ${fr(v('V', 'i', 'ед'), v('V', 'i'))}`, '«ед» — контракты с единственным поставщиком'],
    budget_dep: [`${v('Б', 'i')} ${op('=')} ${fr('1', '2')} ${brk(`${P('дотации на жителя')} ${op('+')} ${P('доля занятых в бюджетном секторе')}`)}`, 'P(·) — процентиль среди МО'],
    online_leakage: [`${v('У', 'i')} ${op('=')} ${fr(v('M', 'i'), `${v('M', 'i')} ${op('+')} ${v('R', 'i')}`)}`, 'M — траты на маркетплейсах, R — на общепит (траты по картам)'],
    activity: [`${v('А', 'i')} ${op('=')} ${fr('1', '3')} ${brk(`${P('траты на жителя')} ${op('+')} ${P('зарплата')} ${op('+')} ${P('занятые на 1000')}`)}`, 'P(·) — процентиль среди МО'],
    demo_resilience: [`${v('Д', 'i')} ${op('=')} ${fr('1', '3')} ${brk(`${P('рождаемость')} ${op('+')} ${P('−смертность')} ${op('+')} ${P('миграционный прирост')}`)}`, 'смертность входит со знаком минус: ниже смертность — выше процентиль'],
    hub: [`${v('Х', 'i')} ${op('=')} ${fn('PageRank')}${v('', 'i')}( ${v('G', 'заказчик → поставщик')} )`, 'G — направленная сеть денежных потоков госзаказа; коэффициент затухания в описании не указан'],
    supply_reach: [`${v('О', 'i')} ${op('=')} ${fr(`| { j ≠ i : ${v('S', 'ij')} ≥ порог } |`, `n ${op('−')} 1`)}`, 'S<sub>ij</sub> — продажи поставщиков МО i заказчикам МО j; n − 1 — остальные МО региона; значение порога в описании не указано'],
    bridge: [`${v('М', 'i')} ${op('=')} ${op('Σ')}${v('', 's ≠ i ≠ t')} ${fr(`${v('σ', 'st')}(i)`, v('σ', 'st'))}`, 'σ<sub>st</sub> — число кратчайших путей s → t в совмещённой сети, σ<sub>st</sub>(i) — из них через i; нормировка в описании не указана'],
    sync: [`${v('С', 'i')} ${op('=')} ${op('Σ')}${v('', 'j')} ${v('w', 'ij')}`, 'w — веса связей слоя «Синхронность трат»'],
    leadership: [`${v('Оп', 'i')} ${op('=')} | { j : i опережает j на 1–3 мес. } |`, 'по лаговой корреляции месячных трат'],
    typicality: [`${v('Т', 'i')} ${op('=')} ${fr(`${v('b', 'i')} ${op('−')} ${v('a', 'i')}`, `max(${v('a', 'i')}, ${v('b', 'i')})`)}`, 'силуэт: a — среднее расстояние до МО своего типа, b — до МО ближайшего другого типа; −1…1'],
  };
  const PCT_FX = `${v('P', 'i')} ${op('=')} 100 ${op('·')} ${fr(v('r', 'i'), v('n', 'k'))}`;
  const ixKeys = Object.keys(D.metrics);
  const senseBadge = s => s > 0 ? '<span class="sense up">↑ выше — лучше</span>' : s < 0 ? '<span class="sense dn">↓ выше — хуже</span>' : '<span class="sense neu">нейтральный</span>';
  const nRecs = N.reduce((s, x) => s + x.recs.length, 0);
  const lastQ = D.quarters[D.quarters.length - 1], lastM = D.months[D.months.length - 1];

  const flow = [
    ['Данные', [[n, 'МО'], [Object.keys(D.feats).length, 'признака'], [D.months.length, 'месяца трат'], [SRC.length, 'источников']]],
    ['Модель', [[Object.keys(D.layers).length, 'слоёв сети'], [Q.icvi.length, 'методов'], [D.k, 'типов']]],
    ['Результат', [[ixKeys.length, 'индексов'], [(D.findings || []).length, 'фактов'], [nRecs, 'рекомендаций']]]];

  $('#how').innerHTML = `<div class="howgrid">
    <nav class="howtoc" aria-label="Содержание методики"><span class="ht-h">Содержание</span>${TOC.map(([id, l]) => `<a href="#${id}" data-id="${id}">${l}</a>`).join('')}</nav>
    <div class="howmain">
    <section id="h-short" class="hsec" aria-labelledby="hh-short"><h3 id="hh-short" tabindex="-1">Коротко</h3>
      <div class="prose"><p>Программа <code>econtypes</code> берёт исходные таблицы из базы данных, строит для каждого муниципалитета профиль из ${Object.keys(D.feats).length} признаков, связывает муниципалитеты сетью из нескольких слоёв, находит типы методами машинного обучения без учителя, проверяет их и превращает результат в индексы, выводы и рекомендации. Эта страница собирается заново после каждого пересчёта (${esc(D.generated)}).</p></div>
      <ol class="hflow" aria-label="От данных к выводам">${flow.map(([ph, st], k) => `<li class="hf-ph"><span class="hf-l">${k + 1}. ${ph}</span><div class="hf-st">${st.map(([x, l]) => `<span><b class="mono">${fmtN(x, 0)}</b><span>${l}</span></span>`).join('')}</div></li>`).join('')}</ol>
    </section>

    <section id="h-steps" class="hsec" aria-labelledby="hh-steps"><h3 id="hh-steps" tabindex="-1">Девять этапов</h3>
      <p class="hint">Каждый этап — отдельная команда программы; этапы выполняются по порядку, результат каждого записывается в базу.</p>
      <div class="pipe2" aria-hidden="true">${(() => { let k = 0; return PH.map(([l, sub, c]) => { const st = STEPS.slice(k, k + c); const s0 = k; k += c;
        return `<div class="p2-ph" style="flex:${c}"><div class="p2-h"><b>${l}</b><span>${sub}</span></div><div class="p2-nodes">${st.map((s, j) => `<a class="p2-n" href="#st-${s[0]}" tabindex="-1"><i></i><b class="mono">${s0 + j + 1}. ${s[0]}</b><span>${esc(s[1])}</span></a>`).join('')}</div></div>`; }).join(''); })()}</div>
      ${(() => { let k = 0; return PH.map(([l, sub, c]) => { const st = STEPS.slice(k, k + c), start = k + 1; k += c;
        return `<div class="stph"><h4 class="stph-h"><span>${l}</span><span class="muted">этапы ${start}–${start + c - 1} · ${sub}</span></h4>
          <ol class="steps2" start="${start}">${st.map((s, j) => `<li id="st-${s[0]}"><span class="st-no mono" aria-hidden="true">${start + j}</span><div class="st-h"><b>${esc(s[1])}</b>${copyCode('econtypes ' + s[0])}</div><p class="st-tx">${esc(s[2])}</p></li>`).join('')}</ol></div>`; }).join(''); })()}
    </section>

    <section id="h-ix" class="hsec" aria-labelledby="hh-ix"><h3 id="hh-ix" tabindex="-1">Индексы и формулы <span class="kicker">${ixKeys.length}</span></h3>
      <div class="pctcard"><div class="fx fx-big" aria-hidden="true">${PCT_FX}</div>
        <div><p><b>В интерфейсе индекс показан как процентиль</b> — место МО среди ${n} МО на шкале 0–100, а не процент. r<sub>i</sub> — ранг МО по возрастанию значения индекса, n<sub>k</sub> — число МО, у которых значение есть (равным значениям — средний ранг). Исходное значение индекса m — в своих единицах (колонка «Индекс»); расчёт по конкретному МО раскрывается в карточке района на карте.</p>
        <p class="hint" id="pctCheck"></p></div></div>
      <div class="tbox ixbox"><table class="ixtab2" role="table"><caption class="sr">Тринадцать индексов: формула, описание расчёта, как читать</caption>
        <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Индекс</th><th scope="col" role="columnheader">Как считается</th><th scope="col" role="columnheader">Как читать</th></tr></thead><tbody role="rowgroup">
        ${ixKeys.map(k => { const m = D.metrics[k], f = FX[k];
          return `<tr role="row"><th scope="row" role="rowheader"><span class="ix-l">${esc(m.label)}</span>${senseBadge(m.sense)}<span class="ix-u">m: ${esc((IX_RAW[k] || {}).unit || '—')}</span></th>
            <td role="cell">${f ? `<div class="fx" aria-hidden="true">${f[0]}</div>` : ''}<p class="fx-src">${esc(m.formula)}</p>${f ? `<p class="fx-n">${f[1]}</p>` : ''}</td>
            <td role="cell"><p>${esc(m.interp)}</p><p class="ix-w">Где видно: ${esc(WHERE[k] || 'карточка МО → Индексы')}</p></td></tr>`; }).join('')}
        </tbody></table></div>
      <p class="hint">Формулы записаны по описаниям индексов в данных; параметры, которых там нет (порог охвата, нормировка посреднической центральности, коэффициент PageRank), не указываются. Сверка формул с хранимыми значениями — в разделе «О проекте и технические проверки».</p>
    </section>

    <section id="h-src" class="hsec" aria-labelledby="hh-src"><h3 id="hh-src" tabindex="-1">Источники и ссылки</h3>
      <div class="tbox"><table class="srctab"><caption class="sr">Источники данных и шаги обработки</caption><thead><tr><th scope="col">Источник</th><th scope="col">Что берётся</th><th scope="col">Шаг обработки</th></tr></thead><tbody>${SRC.map(r => `<tr><th scope="row">${esc(r[0])}</th><td>${esc(r[1])}</td><td class="ink2">${esc(r[2])}</td></tr>`).join('')}</tbody></table></div>
      <ul class="hlinks">
        <li><a href="${LINKS.about}">О проекте</a><span>страница проекта</span></li>
        <li><a href="${LINKS.pdf}">Отчёт (PDF)</a><span class="pdfnote">${mk('info')}не пересоздавался в этой версии интерфейса (V4) — может не совпадать с текущим видом страниц</span></li>
        <li><a href="${LINKS.code}">Код</a><span>репозиторий программы econtypes</span></li></ul>
    </section>

    <section id="h-period" class="hsec" aria-labelledby="hh-period"><h3 id="hh-period" tabindex="-1">Период и сборка</h3><dl class="kv">
      <dt>Период данных</dt><dd class="mono">${esc(D.period)}</dd>
      <dt>Кварталы динамики</dt><dd><span class="mono">${esc(D.quarters[0])} — ${esc(lastQ)}</span> <span class="muted">(${D.quarters.length})</span></dd>
      <dt>Месячные ряды</dt><dd><span class="mono">${esc(D.months[0])} — ${esc(lastM)}</span> <span class="muted">(${D.months.length})</span></dd>
      <dt>Проверка на новых данных</dt><dd>${Q.val ? Object.keys(Q.val.holdout).map(esc).join(', ') + ' — только закупки, вне периода построения' : 'не проводилась'}</dd>
      <dt>Сборка страницы</dt><dd class="mono">${esc(D.generated)}</dd></dl></section>

    <section id="h-reg" class="hsec" aria-labelledby="hh-reg"><h3 id="hh-reg" tabindex="-1">Другие регионы</h3><div class="prose">
      <p>Модель типовая: Башкортостан — пример применения. Всё региональное задаётся в разделе <code>region</code> конфигурации (название, код субъекта в ИНН, региональный центр, особые МО); остальной расчёт одинаков для любого субъекта. Основные данные федеральные: набор СберИндекса покрывает ≈2 100 МО России, реестр ЕИС, БД ПМО и границы МО есть для всех регионов; региональная демография и законы о бюджете необязательны. Типы без заданных названий получают имя по профилю.</p></div>
      <div class="cmds"><div class="crow"><span>Запуск для другого региона</span>${copyCode('econtypes --config config/регион.yaml all')}</div><div class="crow"><span>Порядок действий</span><span><code>docs/SCALING.md</code> в репозитории проекта</span></div></div></section>

    <section id="h-upd" class="hsec" aria-labelledby="hh-upd"><h3 id="hh-upd" tabindex="-1">Обновление данных</h3>
      <div class="cmds"><div class="crow"><span>Новая выгрузка ЕИС</span>${copyCode('econtypes add-eis папка 2026')}</div>
        <div class="crow"><span>Пересчёт всех этапов</span>${copyCode('econtypes all')}</div>
        <div class="crow"><span>Любая другая база</span>${copyCode('econtypes --db postgresql://… all')}</div></div>
      <p class="hint">Все таблицы результатов (типы, индексы, рёбра, корреляции, рекомендации) лежат в базе в таблицах <code>res_*</code>.</p></section>

    <section id="h-amb" class="hsec" aria-labelledby="hh-amb"><h3 id="hh-amb" tabindex="-1">Неоднозначности, вынесенные отдельно</h3>
      <div class="callout">${mk('info')}<div><b>Направление слоя «Потоки госзаказа, ₽».</b> Формула индекса хаба описывает PageRank «в направленной сети денежных потоков заказчик → поставщик», а слой на карте «Потоки госзаказа, ₽» подписан «поставщик → заказчик». Направления рёбер в данных при редизайне не менялись; на карте стрелка понимается как направление поставки (оплата идёт обратно). Какая ориентация использовалась в расчёте индекса, нужно сверить с кодом этапа <code>metrics</code>.</div></div>
      <div class="callout">${mk('info')}<div><b>Нет матрицы миграции.</b> Межмуниципальной матрицы миграции (откуда → куда, сколько человек, за какой период) в данных нет. Поэтому миграция показана только как показатель района (миграционный прирост, ‰), а не как маршруты.</div></div></section>

    <section id="h-about" class="hsec" aria-labelledby="hh-about"><details class="about" id="aboutBox">
      <summary><span class="ab-sum"><h3 id="hh-about" tabindex="-1">О проекте и технические проверки</h3><span class="hint">авторы и ссылки · SHA-1 данных · состав типов · сверка формул · геометрия границ · версии библиотек</span></span>${ICON.chev}</summary>
      <div class="about-body" id="aboutBody"></div></details></section>
  </div></div>`;

  /* ---------- оглавление: прокрутка + фокус на заголовок, scrollspy ---------- */
  const go = id => { const s = $('#' + id); if (!s) return; if (id === 'h-about') openAbout(false);
    s.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'});
    const h = s.querySelector('h3'); if (h) h.focus({preventScroll: true}); setSpy(id); spyLock = {id, until: performance.now() + 1200}; };
  $('#how').addEventListener('click', e => { const a = e.target.closest('.howtoc a, .pipe2 a'); if (!a) return; e.preventDefault();
    const id = a.getAttribute('href').slice(1); if (id.startsWith('st-')) { const li = $('#' + id); li.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'center'}); li.classList.add('flash'); setTimeout(() => li.classList.remove('flash'), 1200); } else go(id); });
  function setSpy(id){ $$('#how .howtoc a').forEach(a => { const on = a.dataset.id === id; a.classList.toggle('on', on); if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current'); }); }
  /* scrollspy: активен последний раздел, чей верх прошёл линию чтения под шапкой; внизу страницы — последний */
  let spyRaf = 0, spyLock = null;
  function spy(){ spyRaf = 0; if (activeTab !== 'how') return;
    if (spyLock && performance.now() < spyLock.until) { setSpy(spyLock.id); return; }
    const line = 140, ids = TOC.map(([id]) => id); let cur = ids[0];
    ids.forEach(id => { const el = $('#' + id); if (el && el.getBoundingClientRect().top <= line) cur = id; });
    if (innerHeight + scrollY >= document.documentElement.scrollHeight - 4) { const last = ids.filter(id => { const r = $('#' + id).getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; }).pop(); if (last) cur = last; }
    setSpy(cur); }
  addEventListener('scroll', () => { if (!spyRaf) spyRaf = requestAnimationFrame(spy); }, {passive: true});
  onTab('how', () => requestAnimationFrame(spy));
  setSpy('h-short');

  /* ---------- раздел «О проекте и технические проверки» ---------- */
  let built = false;
  const box = $('#aboutBox');
  box.addEventListener('toggle', () => { if (box.open && !built) buildAbout(); });
  function openAbout(scroll = true){ if (!box.open) box.open = true; if (!built) buildAbout(); if (scroll) { box.scrollIntoView({behavior: RM.matches ? 'auto' : 'smooth', block: 'start'}); $('#hh-about').focus({preventScroll: true}); setSpy('h-about'); spyLock = {id: 'h-about', until: performance.now() + 1200}; } }
  HOW.openAbout = openAbout;
  document.addEventListener('click', e => { const a = e.target.closest('[data-goto-about]'); if (!a) return; e.preventDefault();
    activate('how', {scroll: false}); openAbout(true); });

  const OKM = '<span class="st ok" aria-hidden="true">✓</span>', BADM = '<span class="st bad" aria-hidden="true">✕</span>', NAM = '<span class="st nc" aria-hidden="true">○</span>';
  const stat = (ok, txt) => `<span class="ab-st ${ok === true ? 'ok' : ok === false ? 'bad' : 'nc'}">${ok === true ? OKM : ok === false ? BADM : NAM}${txt}</span>`;
  const km2 = x => fmtN(x, 2) + ' км²';
  const SHA_REF = '__D_SHA1__';

  /* процентиль со средним рангом при равных значениях (как в данных) */
  function pctAvg(vals){ const idx = vals.map((x, i) => [x, i]).filter(d => d[0] != null && Number.isFinite(d[0])).sort((a, b) => a[0] - b[0]), nk = idx.length, out = vals.map(() => null);
    for (let s = 0; s < nk;) { let e = s; while (e + 1 < nk && idx[e + 1][0] === idx[s][0]) e++; const r = (s + e) / 2 + 1; for (let q = s; q <= e; q++) out[idx[q][1]] = 100 * r / nk; s = e + 1; } return out; }
  function cmpRows(get, ref){ let mx = 0, cnt = 0, skip = 0; N.forEach((x, i) => { const a = get(x, i), b = ref(x, i); if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b)) { skip++; return; } cnt++; mx = Math.max(mx, Math.abs(a - b)); }); return {mx, cnt, skip}; }
  const fpct = (k, sign = 1) => pctAvg(N.map(x => x.f[k] == null ? null : sign * x.f[k]));
  const meanP = arrs => (x, i) => { const ps = arrs.map(a => a[i]); return ps.some(p => p == null) ? null : ps.reduce((s, p) => s + p, 0) / ps.length; };
  const layerSum = (lay, fnE) => { const acc = N.map(() => 0); (D.layers[lay] || []).forEach(e => fnE(e, acc)); return acc; };
  function formulaChecks(){
    const T = 1e-4, rows = [];
    const add = (k, how, r, tol = T) => rows.push({k, how, ...r, ok: r.cnt ? r.mx <= tol : null});
    add('localization', 'm = доля госзаказа у местных поставщиков (признак)', cmpRows(x => x.m.localization, x => x.f.proc_local_sh));
    add('external_dep', 'm = доля у поставщиков из Уфы + из других регионов', cmpRows(x => x.m.external_dep, x => x.f.proc_ufa_sh == null || x.f.proc_out_sh == null ? null : x.f.proc_ufa_sh + x.f.proc_out_sh));
    add('competition', 'm = 1 − доля закупок у единственного поставщика', cmpRows(x => x.m.competition, x => x.f.proc_single_sh == null ? null : 1 - x.f.proc_single_sh));
    add('budget_dep', 'm = среднее процентилей двух признаков', cmpRows(x => x.m.budget_dep, meanP([fpct('grants_pc'), fpct('emp_sh_budget')])), .01);
    add('online_leakage', 'm = маркетплейсы / (маркетплейсы + общепит)', cmpRows(x => x.m.online_leakage, x => { const a = x.f['sh_Маркетплейсы'], b = x.f['sh_Общественное питание']; return a == null || b == null || a + b === 0 ? null : a / (a + b); }));
    add('activity', 'm = среднее процентилей трёх признаков', cmpRows(x => x.m.activity, meanP([fpct('spend_total'), fpct('wage'), fpct('emp_per_1000')])), .01);
    add('demo_resilience', 'm = среднее процентилей; смертность со знаком минус', cmpRows(x => x.m.demo_resilience, meanP([fpct('birth_rate'), fpct('death_rate', -1), fpct('migr_rate')])), .01);
    const sync = layerSum('comovement', (e, a) => { a[e[0]] += e[2]; a[e[1]] += e[2]; });
    add('sync', 'm = сумма весов связей МО в слое «Синхронность трат»', cmpRows(x => x.m.sync, (x, i) => sync[i]), 1e-3);
    const lead = layerSum('lead_lag', (e, a) => { a[e[0]] += 1; });
    add('leadership', 'm = число исходящих связей МО в слое «Опережение трат»', cmpRows(x => x.m.leadership, (x, i) => lead[i]), 0);
    add('supply_reach', 'm · (n − 1) — целое число МО', cmpRows(x => x.m.supply_reach == null ? null : x.m.supply_reach * (n - 1), x => x.m.supply_reach == null ? null : Math.round(x.m.supply_reach * (n - 1))), 1e-3);
    add('typicality', 'm = силуэт МО из nodes[].typ', cmpRows(x => x.m.typicality, x => x.typ));
    rows.push({k: 'hub', how: 'PageRank по полному графу потоков — в браузере не пересчитывается', ok: null});
    rows.push({k: 'bridge', how: 'посредническая центральность — в браузере не пересчитывается', ok: null});
    return rows;
  }
  /* процентили: mp из m по среднему рангу; равенства, возникшие из-за округления хранимых m, дают расхождение не больше полуранга */
  function pctChecks(){ return ixKeys.map(k => { const vals = N.map(x => x.m[k] == null ? null : x.m[k]), p = pctAvg(vals), nk = vals.filter(z => z != null).length;
    const r = cmpRows((x, i) => p[i] == null ? null : Math.round(p[i] * 10) / 10, x => x.mp[k]);
    const nul = N.filter(x => (x.m[k] == null) !== (x.mp[k] == null)).length;
    const mism = N.map((x, i) => i).filter(i => p[i] != null && x0(i, k) != null && Math.abs(Math.round(p[i] * 10) / 10 - N[i].mp[k]) > .05);
    const tied = mism.every(i => vals.filter(z => z === vals[i]).length > 1);
    const ok = !nul && (!mism.length || (tied && r.mx <= 100 / nk / 2 + .05));
    return {k, ...r, nul, mism: mism.length, tied, ok}; }); }
  const x0 = (i, k) => N[i].mp[k];
  HOW.pctChecks = pctChecks; HOW.formulaChecks = formulaChecks;

  /* SHA-1 исходного текста блока D (как в build.py): поиск «const D = » и разбор JSON по скобкам */
  async function verifySha(){
    try {
      if (!(window.crypto && crypto.subtle && window.TextEncoder)) return {ok: null, why: 'в этом окружении нет Web Crypto (crypto.subtle)'};
      const mark = 'const D' + ' = ', sc = [...document.scripts].find(s => !s.src && s.textContent.includes(mark));
      if (!sc) return {ok: null, why: 'встроенный блок данных не найден'};
      const t = sc.textContent, i = t.indexOf(mark) + mark.length; if (t[i] !== '{') return {ok: null, why: 'блок данных имеет неожиданный вид'};
      let depth = 0, inStr = false, j = i;
      for (; j < t.length; j++) { const ch = t.charCodeAt(j); if (inStr) { if (ch === 92) j++; else if (ch === 34) inStr = false; continue; }
        if (ch === 34) inStr = true; else if (ch === 123 || ch === 91) depth++; else if (ch === 125 || ch === 93) { depth--; if (depth === 0) break; } }
      const bytes = new TextEncoder().encode(t.slice(i, j + 1)), buf = await crypto.subtle.digest('SHA-1', bytes);
      const hex = [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
      return {ok: SHA_REF.startsWith('__') ? null : hex === SHA_REF, hex, bytes: bytes.length};
    } catch (err) { return {ok: null, why: 'ошибка: ' + err.message}; }
  }

  function buildAbout(){
    built = true;
    const G = (typeof GEO !== 'undefined' && GEO) || {}, gs = G.stats || {};
    const tm = typeof typesMembershipCheck === 'function' ? {src: 'typesMembershipCheck()', issues: typesMembershipCheck()} : {src: 'расчёт на этой странице', issues: (() => { const o = [];
      N.forEach((x, i) => { const inT = D.types.filter(t => t.members.includes(i)); if (inT.length !== 1) o.push(`${x.s}: в ${inT.length} составах`); else if (inT[0].c !== x.c) o.push(`${x.s}: состав «${inT[0].name}», а nodes[i].c = ${x.c}`); }); return o; })()};
    const lay = Object.entries(D.layers).map(([k, a]) => `${k} ${a.length}`).join(' · ');
    const nv = D.corr ? D.corr.vars.length : 0;
    const comp = [['МО', n], ['типов', `${D.types.length} (D.k = ${D.k})`], ['индексов', ixKeys.length], ['признаков', Object.keys(D.feats).length], ['переменных корреляции', nv ? `${nv}, пар без диагонали ${fmtN(nv * (nv - 1) / 2, 0)}` : 'нет'],
      ['слоёв сети', `${Object.keys(D.layers).length}: ${lay}`], ['кварталов', D.quarters.length], ['месяцев', D.months.length], ['фактов', (D.findings || []).length], ['абзацев общего вывода', (D.summary || []).length], ['объектов геометрии', D.geo && D.geo.features ? D.geo.features.length : 'нет']];
    const fc = formulaChecks(), pc = pctChecks(), pcBad = pc.filter(r => !r.ok), pcTie = pc.filter(r => r.ok && r.mism);
    const gapTop = (G.gaps || []).slice(0, 5), ovTop = (G.overlaps || []).slice(0, 5), holes = (G.holes || []).slice().sort((a, b) => b.km2 - a.km2);
    const enclaves = holes.filter(h => h.covered >= .99).length;
    const pctOf = x => gs.region_km2 ? fmtN(x / gs.region_km2 * 100, 3) + ' %' : '';
    const nm = i => N[i] ? esc(N[i].s) : '—';
    const libs = [
      ['deck.gl', '9.4.0', window.deck && deck.VERSION, 'MIT', '3D-карта (WebGL2)'],
      ['Apache ECharts', '6.1.0', window.echarts && echarts.version, 'Apache-2.0', 'статистические графики'],
      ['D3', '7.9.0', window.d3 && d3.version, 'ISC', 'дерево типов, геометрия'],
      ['Leaflet', '1.9.4', window.L && L.version, 'BSD-2-Clause', 'резервная 2D-карта'],
      ['Golos Text', '400–700', document.fonts && document.fonts.check('500 14px "Golos Text"') ? 'загружен' : 'не загружен', 'OFL-1.1', 'шрифт интерфейса'],
      ['JetBrains Mono', '400, 500', document.fonts && document.fonts.check('500 14px "JetBrains Mono"') ? 'загружен' : 'не загружен', 'OFL-1.1', 'числа и команды']];

    $('#aboutBody').innerHTML = `<div class="ab-grid">
      <section class="ab-card" aria-labelledby="ab1"><h4 id="ab1">О проекте</h4><dl class="kv kv-s">
        <dt>Название</dt><dd>${esc(D.title)}</dd><dt>Регион</dt><dd>${esc(D.region)}</dd>${D.authors ? `<dt>Авторы</dt><dd>${esc(D.authors)}</dd>` : ''}
        <dt>Период данных</dt><dd class="mono">${esc(D.period)}</dd><dt>Сборка данных</dt><dd class="mono">${esc(D.generated)}</dd>
        <dt>Сборка страницы</dt><dd><span class="mono">__BUILD_TIME__</span><span class="ab-note">время сборки HTML (build.py), не дата данных</span></dd>
        <dt>Ссылки</dt><dd class="ab-links"><a href="${LINKS.about}">О проекте</a><span><a href="${LINKS.pdf}">Отчёт (PDF)</a><span class="ab-note">не пересоздавался в V4</span></span><a href="${LINKS.code}">Код</a></dd></dl></section>

      <section class="ab-card" aria-labelledby="ab2"><h4 id="ab2">Целостность данных D</h4>
        <p>SHA-1 исходного текста JSON-блока <code>D</code>, сверенный сборкой (<code>build.py</code>) с эталоном:</p>
        <p class="sha">${SHA_REF.startsWith('__') ? '<span class="muted">не подставлен сборкой</span>' : copyCode(SHA_REF)}</p>
        <p id="shaLive">${stat(null, 'проверка в браузере…')}</p>
        <p class="hint">Страница только читает D: все группировки, медианы и координаты графиков строятся в отдельных копиях.</p>
        <table class="ab-tab"><caption class="sr">Состав данных D</caption><tbody>${comp.map(([l, x]) => `<tr><th scope="row">${esc(l)}</th><td>${typeof x === 'number' ? `<span class="mono">${fmtN(x, 0)}</span>` : esc(x)}</td></tr>`).join('')}</tbody></table></section>

      <section class="ab-card" aria-labelledby="ab3"><h4 id="ab3">Состав типов</h4>
        <p>${tm.issues.length ? stat(false, `расхождений: ${tm.issues.length}`) : stat(true, `каждый из ${n} МО ровно в одном типе; types[].members совпадают с nodes[i].c`)}</p>
        ${tm.issues.length ? `<ul class="ab-list">${tm.issues.map(s => `<li>${esc(s)}</li>`).join('')}</ul>` : ''}
        <ul class="ab-types">${D.types.map(t => `<li><span class="sw" style="--c:${COLV(t.c)}"></span><span>${esc(t.name)}</span><span class="mono">${t.members.length}</span></li>`).join('')}</ul>
        <p class="hint">Проверка: ${esc(tm.src)}.</p></section>

      <section class="ab-card wide" aria-labelledby="ab4"><h4 id="ab4">Сверка формул и процентилей с данными</h4>
        <p>${pcBad.length ? stat(false, `процентили: не воспроизводятся у ${pcBad.length} индексов (${pcBad.map(r => esc(ixLabel(r.k))).join(', ')})`) : stat(true, `процентили mp воспроизводятся из m по формуле со средним рангом для всех ${ixKeys.length} индексов`)}</p>
        ${pcTie.length ? `<p class="hint">${pcTie.map(r => `${esc(ixLabel(r.k))}: ${r.mism} МО`).join('; ')} — значения m, одинаковые после округления до 5 знаков, в исходном расчёте различались; расхождение не больше полуранга (${fmtN(Math.max(...pcTie.map(r => r.mx)), 1)} пункта).</p>` : ''}
        <div class="tbox"><table class="ab-ftab ab-stack" role="table"><caption class="sr">Сверка формул индексов</caption><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Индекс</th><th scope="col" role="columnheader">Что проверено</th><th scope="col" role="columnheader" class="n">МО</th><th scope="col" role="columnheader" class="n">макс. |Δ|</th><th scope="col" role="columnheader">Итог</th></tr></thead><tbody role="rowgroup">
          ${fc.map(r => `<tr role="row"><th scope="row" role="rowheader">${esc(ixLabel(r.k))}</th><td role="cell" data-label="Проверено">${esc(r.how)}</td><td role="cell" data-label="МО" class="n">${r.cnt != null ? r.cnt + (r.skip ? ` <span class="muted">(${r.skip} без данных)</span>` : '') : '—'}</td><td role="cell" data-label="макс. |Δ|" class="n">${r.cnt ? fmtN(r.mx, r.mx && r.mx < .001 ? 6 : 4) : '—'}</td><td role="cell" data-label="Итог">${r.ok === true ? stat(true, 'совпадает') : r.ok === false ? stat(false, 'расходится') : stat(null, 'не проверяется')}</td></tr>`).join('')}
        </tbody></table></div>
        <p class="hint">МО с пропуском хотя бы одной части формулы в сверку не входят и не считаются нулём.</p></section>

      <section class="ab-card wide" aria-labelledby="ab5"><h4 id="ab5">Геометрия границ</h4>
        ${gs.features ? `<p>В <code>D.geo</code> ${gs.features} объектов: ${gs.polygon} Polygon и ${gs.multipolygon} MultiPolygon, ${gs.inner_rings} внутренних колец. Это исходная геометрия geoBoundaries; <b>D.geo не изменялся</b>. Топология проверена отдельно (<code>tools/derive_geo.py</code>, shapely), результат — производный блок <code>GEO</code> рядом с D.</p>
        <div class="geo-kpi">
          <div><b class="mono">${fmtN(gs.gaps, 0)}</b><span>щелей между соседними МО</span><span class="muted">${km2(gs.gaps_km2)} всего · ${pctOf(gs.gaps_km2)} площади региона</span></div>
          <div><b class="mono">${fmtN(gs.overlaps, 0)}</b><span>перекрытий соседних МО</span><span class="muted">${km2(gs.overlaps_km2)} всего · ${pctOf(gs.overlaps_km2)}</span></div>
          <div><b class="mono">${fmtN(gs.inner_rings, 0)}</b><span>внутренних колец (дыр в полигоне МО)</span><span class="muted">${enclaves} из них целиком заняты другими МО</span></div>
          <div><b class="mono">${fmtN(gs.segments_shared_twice, 0)}</b><span>отрезков общих границ совпадают у соседей</span><span class="muted">${fmtN(gs.segments_single, 0)} встречаются один раз (контур региона и несовпавшие стыки)</span></div></div>
        <p class="ab-expl">${mk('info')}<span>Щели и перекрытия — свойства исходных границ, а не ошибка отрисовки: соседние МО в geoBoundaries не всегда сходятся точно. Данные ради красивой картинки не правились. На карте щели показываются цветом основы региона (заливка общего контура всех МО), поэтому не выглядят как пропавшая территория; площадь региона по контуру — ${gs.region_km2 ? fmtN(gs.region_km2, 0) + ' км²' : 'н/д'}.</span></p>
        <div class="geo-tabs">
          <div class="tbox"><table><caption>Крупнейшие щели</caption><thead><tr><th scope="col">Между МО</th><th scope="col" class="n">км²</th></tr></thead><tbody>${gapTop.map(g => `<tr><td>${(g.near || []).map(nm).join(' / ')}</td><td class="n">${fmtN(g.km2, 2)}</td></tr>`).join('')}</tbody></table></div>
          <div class="tbox"><table><caption>Крупнейшие перекрытия</caption><thead><tr><th scope="col">Пара МО</th><th scope="col" class="n">км²</th></tr></thead><tbody>${ovTop.map(o => `<tr><td>${nm(o.a)} / ${nm(o.b)}</td><td class="n">${fmtN(o.km2, 2)}</td></tr>`).join('')}</tbody></table></div>
          <div class="tbox"><table><caption>Внутренние кольца<span class="ab-note">«занято» — доля кольца, покрытая другими МО</span></caption><thead><tr><th scope="col">В полигоне МО</th><th scope="col" class="n">км²</th><th scope="col" class="n">занято</th></tr></thead><tbody>${holes.map(h => `<tr><td>${nm(h.mo)}</td><td class="n">${fmtN(h.km2, 2)}</td><td class="n">${fmtN(h.covered * 100, 1)} %</td></tr>`).join('')}</tbody></table></div></div>`
        : `<p>${stat(null, 'производная диагностика геометрии (GEO) в странице отсутствует')}</p>`}</section>

      <section class="ab-card wide" aria-labelledby="ab6"><h4 id="ab6">Встроенные библиотеки и шрифты</h4>
        <div class="tbox"><table class="ab-ltab ab-stack" role="table"><caption class="sr">Библиотеки, версии и лицензии</caption><thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Компонент</th><th scope="col" role="columnheader">Версия в сборке</th><th scope="col" role="columnheader">Обнаружено в странице</th><th scope="col" role="columnheader">Лицензия</th><th scope="col" role="columnheader">Для чего</th></tr></thead><tbody role="rowgroup">
          ${libs.map(([nmx, ver, got, lic, use]) => `<tr role="row"><th scope="row" role="rowheader">${esc(nmx)}</th><td role="cell" data-label="Версия" class="mono">${esc(ver)}</td><td role="cell" data-label="В странице">${got ? stat(got === ver || got === 'загружен', esc(got)) : stat(false, 'не найдено')}</td><td role="cell" data-label="Лицензия" class="mono">${esc(lic)}</td><td role="cell" data-label="Для чего" class="ink2">${esc(use)}</td></tr>`).join('')}
        </tbody></table></div>
        <p class="hint">Всё встроено в файл: внешние CDN, ключи API и загрузка данных по сети для просмотра не нужны.</p></section>
    </div>`;
    verifySha().then(r => { const el = $('#shaLive'); if (!el) return;
      el.innerHTML = r.ok === true ? stat(true, `проверено в браузере: текст блока D (${fmtN(r.bytes, 0)} байт) даёт тот же SHA-1`)
        : r.ok === false ? stat(false, `в браузере получено ${esc(r.hex)} — не совпадает с эталоном`)
        : stat(null, r.hex ? `в браузере получено ${esc(r.hex)}; эталон не подставлен сборкой` : `в браузере не проверено: ${esc(r.why)}`);
      HOW.sha = r; });
  }

  /* короткий итог сверки процентилей — в разделе индексов */
  const pc = pctChecks(), bad = pc.filter(r => !r.ok), tie = pc.filter(r => r.ok && r.mism);
  $('#pctCheck').innerHTML = bad.length ? `Сверка с данными: у ${bad.length} индексов процентили не воспроизводятся этой формулой — подробности в разделе о проекте.`
    : `Сверено с данными: формула воспроизводит хранимые процентили всех ${ixKeys.length} индексов${tie.length ? ` (у ${tie.reduce((s, r) => s + r.mism, 0)} МО — с точностью до полуранга из-за округления хранимых значений)` : ''}.`;
}
