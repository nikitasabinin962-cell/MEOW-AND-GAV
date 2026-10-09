# econtypes V4 — архитектура исходников (для разработчиков)

Итог — один автономный файл `econtypes.html`, собираемый `python3 build.py [--out путь]`.
Без CDN, ключей и fetch: шрифты, библиотеки, данные встроены.

## Файлы и владельцы

| файл | что | владелец |
|---|---|---|
| `src/template.html` | шапка, вкладки, пустые `<section id="t-…">`, подвал, `#tt` | общий (не менять без необходимости) |
| `src/css/00-base.css` | токены светлой/тёмной тем, компоненты, уведомления, `.ptrack` | общий |
| `src/css/10-out.css` … `70-how.css` | стили одной вкладки | владелец вкладки |
| `src/js/00-core.js` | утилиты, тема, вкладки, шапка, выбор МО | общий |
| `src/js/01-state.js` | готовность шрифтов, `whenSized/onResize`, `notify/announce`, **сравнение** | общий |
| `src/js/02-meta.js` | метаданные показателей и форматирование (m ≠ mp) | общий |
| `src/js/03-charts.js` | ECharts: тема из токенов, `makeChart` | общий |
| `src/js/04-shared.js` | слои сети, направления, темы рекомендаций, `ptrack`, `findMO` | общий |
| `src/js/10-out.js` | 1. Выводы и рекомендации | вкладка |
| `src/js/2?-map-*.js` | 2. Карта и сеть: `21-map-scene` (сцена deck.gl, камера, подписи), `22-map-layers` (слои, движение), `23-map-ui` (разметка, панель, матрица МО × МО — ТЗ 12.1), `24-map-fallback` (2D-резерв Leaflet), `25-map-typechord` («Типы × типы» — ТЗ 12.2) | вкладка |
| `src/js/30-cmp.js` | 3. Сравнение районов (+ сезонность трат 2 × 12 — ТЗ 12.4) | вкладка |
| `src/js/40-corr.js` | 4. Корреляции | вкладка |
| `src/js/50-types.js`, `55-types-flow.js` | 5. Типы МО; переходы между типами по кварталам (ТЗ 12.3) | вкладка |
| `src/js/60-quality.js` | 6. Качество модели | вкладка |
| `src/js/70-how.js` | 7. Как это работает (+ раскрываемый раздел «О проекте и технические проверки») | вкладка |
| `src/js/99-init.js` | порядок инициализации | общий |

Каждый модуль вкладки сам строит разметку своей секции: `$('#t-xxx').innerHTML = …` в начале файла.
Модули склеиваются в один `<script>` по имени файла; все объявления верхнего уровня — общие глобальные.

## Встроенные библиотеки (глобальные)

`L` — Leaflet 1.9.4 (только 2D-резерв карты), `d3` — D3 7.9.0, `echarts` (`ECH`) — ECharts 6.1.0 (полная сборка: UniversalTransition, custom series, matrix — доступны), `deck` — deck.gl 9.4.0 (WebGL2).

## Общие API (использовать, не дублировать)

- Данные: `D` (не изменять!), `GEO` (производная геометрия), `N = D.nodes`, `n = 63`.
- Утилиты: `$`, `$$`, `css(var)`, `esc`, `fmtN(v,d)`, `fmtF(feat,v)`, `fmtSigned`, `featLabel`, `featUnit`, `FL`, `NA`, `mix`, `rgba`, `isDark()`, `niceTicks`, `median`, `ICON`, `showTip(e,html)/hideTip()`.
- Типы: `COLV(c)` → `var(--cK)` для HTML/SVG, `COL(c)` → вычисленный цвет; `typeName(c)`, `TYPES`, `typeOf(i)`.
- Темы рекомендаций: `ORDER`, `MEANING`, `RISK`, `OPP`, `kind(t)`, `mk(kind)`, `mainRec(x)`, `recHtml(r)`.
- Показатели: `IX_RAW`, `fmtIxRaw(k,v)` (исходное m в своих единицах), `fmtPctile(v)` («NN-й процентиль»), `ixLabel`, `ixSense`, `senseWord`, `featUnitText`, `axisName(var)`, `fmtVar(var,x)`, `axisVal`, `isShareVar`, `ptrack(p,cls)`, `senseCls`, `senseTxt`.
- Выбор МО (общий для всех вкладок): `sel`, `setSel(i)`, `SEL_HOOKS.push(fn)`; переход на карту `goMap(i)`; группа `showGroup(ids,label)`.
- Сравнение (единое состояние): `CMP.ids`, `cmpHas(i)`, `cmpSlot(i)` (стабильный слот 0–4 за ID), `addToComparison(i, anchorEl)` (идемпотентно, лимит 5 → `notify` у кнопки), `removeFromComparison(i)`, `clearComparison()`, `setComparison(ids)`, `CMP_HOOKS.push(fn)`, `cmpToggle(i, cls)` — HTML переключателя с `aria-pressed`, синхронизируется автоматически во всём документе.
- Уведомления: `notify(anchorEl, html, {kind:'warn', action:{label, run}})`, `announce(text)` (live-регион).
- Вкладки: `activate(tab)`, `onTab(tab, fn)` (вход на вкладку), `activeTab`.
- Тема: `THEME_HOOKS.push(fn)`; `RM.matches` — reduced motion.
- Размеры: `FONTS_READY` (Promise), `whenSized(el, cb)`, `onResize(el, cb)`. Не создавать графики в скрытых/нулевых контейнерах и не использовать setTimeout вместо этого.
- ECharts: `makeChart(el, build, {renderer:'svg'|'canvas', onInit})` → `{chart, refresh(notMerge), dispose()}`; тема и resize обрабатываются сами.

## Правила

1. `D` не мутировать (никаких sort/push/присваиваний на массивах D; копировать `slice()`).
2. Пропуск ≠ 0, процентиль ≠ процент, медиана/среднее/IQR/std подписаны своими именами, без выдуманных CI/p.
3. Цвет типа — только тип; знак корреляции — `--rn*/--rp*`; риск/возможность/ориентир — `--risk/--opp/--info`; выбор — `--pearl-edge`; миграция — `--mig-neg/--mig-zero/--mig-pos`.
4. Текст значимой информации ≥ 4,5:1 (токены `--ink`, `--ink2`, `--muted` подобраны; `--faint` — только декоративно).
5. Подписи не должны пересекаться: проверять реальные bounding box (`tests/lib/qa.js → overlaps`), а не длину строки.
6. Анимации: ECharts/D3 переходы 200–700 мс, без бесконечных циклов; при `RM.matches` — мгновенно.
7. Клавиатура и touch: все действия — реальные `<button>`/`<a>`; tooltip не единственный путь к числу.
8. Не трогать чужие файлы. Сборка для своей проверки: `python3 build.py --out dist/<имя>.html`.
9. Браузерные проверки: `NODE_PATH=/opt/node-tools/node_modules node <скрипт>`; Chromium в `/opt/pw-browsers`; помощники `tests/lib/qa.js` (`launch`, `openPage` с офлайн-блокировкой сети, `overlaps`, `minFontPx`).
10. Набор проверок: `tests/check.js` (+ `tests/checks-tabs.js`) — именованные смысловые проверки, `tests/qa-selftest.js` — самопроверка помощника наложений, `tests/a11y-audit.js` — аудит доступности, `tests/shots.js` — кадры и ленты движения для отчёта. Ожидания в проверках синхронизируются по отрисованным кадрам (`MAPVS.scenes[k].rendered`), а не по фиксированным паузам: в SwiftShader кадр может занимать секунду.
