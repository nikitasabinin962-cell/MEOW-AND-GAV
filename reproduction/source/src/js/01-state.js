/* ==========================================================================
   Общее состояние, уведомления, видимость/размер контейнеров
   ========================================================================== */

/* ---------- готовность шрифтов: графики и измерение текста ждут её ---------- */
const FONTS_READY = (document.fonts && document.fonts.ready) ? document.fonts.ready.catch(() => {}) : Promise.resolve();

/* ---------- контейнер стал видимым и получил ненулевой размер ---------- */
function whenSized(el, cb){
  if (!el) return;
  if (el.clientWidth > 0 && el.clientHeight > 0) { cb(el.getBoundingClientRect()); return; }
  const ro = new ResizeObserver(() => { if (el.clientWidth > 0 && el.clientHeight > 0) { ro.disconnect(); cb(el.getBoundingClientRect()); } });
  ro.observe(el);
}
/* наблюдение за размером с отбрасыванием нулевых (скрытых) состояний */
function onResize(el, cb){
  let last = '';
  const ro = new ResizeObserver(es => { const r = es[0].contentRect; if (!r.width || !r.height) return;
    const key = Math.round(r.width) + 'x' + Math.round(r.height); if (key === last) return; last = key; cb(r); });
  ro.observe(el); return ro;
}

/* ---------- уведомления рядом с действием + общий live-регион ---------- */
const liveRegion = (() => { const d = document.createElement('div'); d.className = 'sr'; d.setAttribute('role', 'status'); d.setAttribute('aria-live', 'polite'); document.body.appendChild(d); return d; })();
function announce(text){ liveRegion.textContent = ''; setTimeout(() => { liveRegion.textContent = text; }, 30); }
function notify(anchor, html, opts = {}){
  const text = html.replace(/<[^>]+>/g, '');
  announce(text);
  document.querySelectorAll('.notice[data-auto]').forEach(n => n.remove());
  const n = document.createElement('div');
  n.className = 'notice' + (opts.kind ? ' ' + opts.kind : ''); n.setAttribute('role', 'status'); n.dataset.auto = '1';
  n.innerHTML = `<span class="notice-tx">${html}</span>` + (opts.action ? `<button type="button" class="link notice-act">${esc(opts.action.label)}</button>` : '')
    + `<button type="button" class="notice-x" aria-label="закрыть уведомление">${ICON.close}</button>`;
  if (anchor && anchor.isConnected) { anchor.insertAdjacentElement('afterend', n); n.classList.add('inline'); }
  else { n.classList.add('toast'); document.body.appendChild(n); }
  n.querySelector('.notice-x').onclick = () => n.remove();
  if (opts.action) n.querySelector('.notice-act').onclick = () => { n.remove(); opts.action.run(); };
  setTimeout(() => n.remove(), opts.ms || 7000);
  return n;
}

/* ---------- сравнение: единое состояние, стабильные маркеры по ID ---------- */
const CMP_MAX = 5;
const CMP = {ids: cmpSet, slot: new Map()};   // cmpSet — тот же массив (совместимость модулей)
const CMP_HOOKS = [];
const cmpHas = i => CMP.ids.includes(i);
const cmpSlot = i => CMP.slot.has(i) ? CMP.slot.get(i) : null;
function cmpChanged(){
  const bd = $('#cmpBadge'); if (bd) { bd.hidden = !CMP.ids.length; bd.textContent = CMP.ids.length; }
  syncCmpButtons();
  CMP_HOOKS.forEach(f => { try { f(); } catch (err) { console.error(err); } });
}
/* идемпотентное добавление: уже добавленный МО не удаляется */
function addToComparison(i, anchor){
  if (i == null || !N[i]) return {ok: false, reason: 'bad'};
  if (cmpHas(i)) return {ok: true, already: true};
  if (CMP.ids.length >= CMP_MAX) {
    notify(anchor, `В сравнении уже ${CMP_MAX} районов: ${CMP.ids.map(j => esc(N[j].s)).join(', ')}. Уберите один, чтобы добавить «${esc(N[i].s)}».`,
      {kind: 'warn', action: {label: 'Открыть сравнение', run: () => activate('cmp')}});
    return {ok: false, reason: 'limit'};
  }
  const used = new Set(CMP.slot.values()); let s = 0; while (used.has(s)) s++;
  CMP.slot.set(i, s); CMP.ids.push(i); cmpChanged();
  announce(`${N[i].s} добавлен в сравнение (${CMP.ids.length} из ${CMP_MAX}).`);
  return {ok: true};
}
function removeFromComparison(i){
  const k = CMP.ids.indexOf(i); if (k < 0) return;
  CMP.ids.splice(k, 1); CMP.slot.delete(i); cmpChanged();
  announce(`${N[i].s} убран из сравнения.`);
}
function clearComparison(){ CMP.ids.splice(0, CMP.ids.length); CMP.slot.clear(); cmpChanged(); announce('Сравнение очищено.'); }
function setComparison(ids){ clearComparison(); ids.slice(0, CMP_MAX).forEach(i => addToComparison(i)); }
/* совместимость: старый toggle теперь явно разделён */
function addCmp(i){ if (cmpHas(i)) removeFromComparison(i); else addToComparison(i); }

/* Явный переключатель «в сравнении» с актуальным aria-pressed — единственный элемент, который и добавляет, и убирает */
function cmpBtnInner(i){ return cmpHas(i) ? `${ICON.check}<span>В сравнении</span><span class="sr"> — нажмите, чтобы убрать</span>` : `${ICON.plus}<span>К сравнению</span>`; }
function cmpToggle(i, cls = 'btn'){ return `<button type="button" class="${cls} cmptog" data-cmp-toggle="${i}" aria-pressed="${cmpHas(i)}" title="${cmpHas(i) ? 'Убрать из сравнения' : 'Добавить в сравнение районов'}">${cmpBtnInner(i)}</button>`; }
function syncCmpButtons(root = document){
  root.querySelectorAll('[data-cmp-toggle]').forEach(b => { const i = +b.dataset.cmpToggle, on = cmpHas(i);
    if (b.getAttribute('aria-pressed') !== String(on)) { b.setAttribute('aria-pressed', on); b.innerHTML = cmpBtnInner(i); b.title = on ? 'Убрать из сравнения' : 'Добавить в сравнение районов'; } });
}
document.addEventListener('click', e => {
  const b = e.target.closest('[data-cmp-toggle]'); if (!b) return;
  e.preventDefault(); e.stopPropagation();
  const i = +b.dataset.cmpToggle;
  if (cmpHas(i)) removeFromComparison(i); else addToComparison(i, b);
}, true);
