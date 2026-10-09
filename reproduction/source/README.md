# econtypes · дашборд «Экономические типы муниципалитетов Башкортостана» — V4

Одностраничный автономный дашборд: 63 МО, 7 экономических типов, 13 индексов, 32 признака, 9 слоёв связей, корреляции, проверка модели и методика. Система «Графит и жемчуг»: светлая и тёмная темы на всех семи вкладках, 3D-карта на WebGL2 с честным 2D-резервом.

## Запуск

Откройте **`econtypes.html`** в браузере (Chrome, Edge, Firefox, Safari последних версий). Сервер, сеть и ключи не нужны: данные, шрифты (Golos Text, JetBrains Mono) и библиотеки (deck.gl, ECharts, D3, Leaflet) встроены в файл.

- Карта по умолчанию — 3D-сцена deck.gl (WebGL2). Без WebGL2, после потери контекста или с параметром `?render=2d` — 2D-сцена Leaflet с той же геометрией и тем же выбором, с пояснением о режиме.
- Из сети может загружаться только подложка OpenStreetMap — и только по явному флажку «подложка OSM». Если тайлы недоступны, флажок снимается сам и появляется сообщение.

## Сборка

```bash
python3 build.py                     # → econtypes.html
python3 build.py --out dist/x.html   # другой выходной файл
python3 build.py --check             # + сводка состава данных
```

| путь | что это |
|---|---|
| `src/template.html` | разметка семи вкладок |
| `src/css/*.css` | токены тем и стили по вкладкам (порядок по имени файла) |
| `src/js/*.js` | модули по вкладкам и общие: `00-core`…`04-shared`, `10-out`, `21…25-map-*`, `30-cmp`, `40-corr`, `50-types`, `55-types-flow`, `60-quality`, `70-how`, `99-init` (карта модулей — `docs/dev/ARCH.md`) |
| `src/vendor/` | deck.gl 9.4.0, ECharts 6.1.0, D3 7.9.0, Leaflet 1.9.4 (без изменений) и их лицензии |
| `src/fonts/` | Golos Text и JetBrains Mono (SIL OFL 1.1) |
| `src/data/D.json` | блок данных `D`, байт в байт из исходного `Дашборд_econtypes (9).html` |
| `src/data/geo-derived.json` | производная геометрия (контур объединения, швы) — отдельно от `D`; пересчёт — `tools/derive_geo.py` |

Сборка извлекает блок `D` из готового файла и сверяет SHA-1 с эталоном `d849169e16d7d2c42c1f210426b1490b6832b76a`; при расхождении она прерывается.

## Проверки

Нужны Node.js и Playwright 1.56 с Chromium (WebGL2 — через GPU или SwiftShader).

```bash
npm install                                  # playwright
node tests/check.js econtypes.html           # именованные смысловые проверки → docs/checks.json
node tests/qa-selftest.js                    # самопроверка помощника поиска наложений
node tests/a11y-audit.js econtypes.html      # аудит доступности → docs/a11y-audit.json
node tests/shots.js econtypes.html           # кадры → docs/shots/, ленты движения → docs/motion/
```

Отбор проверок: `ONLY='^map\.' node tests/check.js econtypes.html`.

Отчёт V4 — что изменено по каждому замечанию и вкладке, поимённый список проверок с результатами, браузеры и ограничения: [`docs/REPORT_V4.md`](docs/REPORT_V4.md). Отчёт и кадры первой редакции сохранены как история: `docs/REPORT.md`, `docs/screenshots/`.
