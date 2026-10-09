# econtypes v5 — экономическая структура муниципалитетов как кластеризация атрибутированных сетей

Конкурс СберИндекса, задача 1. **Региональный кейс: 63 МО Республики Башкортостан** (типология — 62 МО; ЗАТО Межгорье без СберИндекса — отдельно). Результат не является общероссийским.

v5 — отдельная версия поверх архивного проекта v4: исходные файлы и папки (`../reproduction`, `../econtypes_research_20261009.sqlite` и др.) не изменяются; строится новая база `data/econtypes_v5.sqlite`.

## Одна команда

```bash
cd econtypes_v5
bash scripts/run_all.sh            # ≈ 15 мин на 4 vCPU; --quick — ≈ 4 мин (уменьшенные B, только для проверки)
```

Нужно: Python 3.11+ (проверено на 3.13), `pdftotext` (poppler-utils), для дашборда — Node.js и репозиторий дашборда рядом (`FRONT=../../-` по умолчанию), для PDF — LibreOffice. Скрипт создаёт `.venv` из `requirements.lock`, затем:

1. ingest — новая база (SQLite, слои L0–L3, миграции, контроли, экспорт Parquet; сверка SHA-256 исследовательской базы);
2. pytest — модульные и краевые тесты;
3. полный расчёт (`econtypes5.pipeline`) → `outputs/latest/` + `RUN_MANIFEST.json` с `run_id`;
4. повтор 12 проверок аудитора на v5 → `outputs/PROJECT_CHECKS_v5.json`;
5. нагрузка на синтетике N = 63/500/2016 → `outputs/SCALE_BENCHMARK.json`;
6. идемпотентность ingest (два прохода) → `outputs/IDEMPOTENCY_CHECK.json`;
7. матрицы требований и формул → `docs/REQUIREMENTS_MATRIX.csv`, `docs/FORMULA_IMPLEMENTATION_MATRIX.csv`;
8. экспорт D5 и сборка дашборда `-/econtypes_v5.html` (+ браузерные проверки Playwright);
9. отчёт → `docs/REPORT_v5.md/.docx/.pdf`, `docs/STRESS_TEST_REPORT.md`, `docs/SOURCE_REGISTRY.csv`.

## Что смотреть

| Файл | Содержание |
|---|---|
| `docs/REPORT_v5.docx` (`.pdf`, `.md`) | отчёт: данные, методология, типы и паспорта, динамика, проверки, ограничения |
| `CHANGELOG.md` | исправления v4 → v5 и их влияние на выводы |
| `docs/STRESS_TEST_REPORT.md` | фактические PASS/FAIL/NOT_RUN |
| `docs/METHODOLOGY_v5.md`, `docs/DATA_DICTIONARY.md`, `docs/DATA_GAPS.md` | формулы, словарь, пробелы данных |
| `outputs/latest/LABELS_STATIC.csv`, `LABELS_MO_PERIOD*.csv/.parquet` | типы МО: статика и по кварталам (режим, β) |
| `outputs/latest/FORMULA_FEATURES_MO_PERIOD.*` | признаки МО × период × режим с единицами, покрытием и датой доступности |
| `outputs/latest/CORRELATIONS_MO_PERIOD.*` | корреляции с перестановочными и пространственными p, BH/BY |
| `outputs/latest/CLUSTER_COMPARISON.csv`, `ABLATION_SENSITIVITY.csv` | сравнение постановок, абляция |
| `outputs/latest/TYPE_PASSPORTS*.csv` | паспорта типов |
| `-/econtypes_v5.html` | автономный дашборд (вкладка «v5: пересчёт»; вкладки v4 — архив) |

## Отдельные шаги

```bash
.venv/bin/python -m econtypes5.ingest                 # база (≈40 с)
.venv/bin/python -m pytest -q tests                   # тесты (≈10 с)
.venv/bin/python -m econtypes5.pipeline [--quick]     # расчёт
.venv/bin/python scripts/make_report.py               # отчёты из outputs/latest
```

Правило выбора K и метода зафиксировано в `econtypes5/experiments.py::select` (Pareto по z-оценкам ICVI → минимальный размер ≥ 3 → бутстреп-ARI ≥ 0,5 → средний ранг z); K = 7 не навязывается. Seed — `config/config_v5.yaml`.

## Ограничения

Сырых parquet СберИндекса нет — используются архивные производные v4; привязка организаций к МО — по названию и коду налогового органа (LOO-точность измерена), не ОКТМО; снимок МСП 2026 — не исторический. Сеть контейнера не пускала к rosstat.gov.ru, sberindex.ru, nalog.gov.ru, zakupki.gov.ru; ЕИС по правилу пользователя открывается только через Opera Browser Connector (в сессии его не было). Подробно — `docs/DATA_GAPS.md` и раздел «Ограничения» отчёта.

## Полная база для скачивания

`data/econtypes_v5.sqlite.gz` — полный снимок базы после прогона, указанного в `data/DB_MANIFEST.json` (run_id, размер, SHA-256, число строк в каждой таблице, ссылка без входа в GitHub). Проверка и распаковка — в конце `docs/DATA_DICTIONARY.md`. Пересоздать снимок: `.venv/bin/python scripts/package_db.py` (входит в `run_all.sh`). Можно и не скачивать: `bash scripts/run_all.sh` пересобирает базу из `../econtypes_research_20261009.sqlite` (Git LFS).
