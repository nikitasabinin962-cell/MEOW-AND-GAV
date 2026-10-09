# CLAUDE.md — постоянный контекст econtypes v5

## Задача
Конкурс СберИндекса, задача 1: выявить экономическую структуру муниципалитетов кластеризацией атрибутированных сетей. Узел — МО, атрибуты — экономические характеристики, ребро — математически определённая экономическая близость. Основа — СберИндекс. Нужны интерпретация типов, динамика, воспроизводимость.
Веса критериев: методология 15%, сеть и атрибуты 15%, математическая динамика 15%, ICVI (SW, CH, S_Dbw, AVI, AVU, MQ) 15%, интерпретация/воспроизводимость/обоснование 30%, визуализация 10%.

## Охват и честные ограничения
- Региональный кейс: 63 МО Башкортостана; типология — 62 МО (ЗАТО Межгорье без СберИндекса — отдельно). Не называть результат общероссийским.
- Сырых parquet СберИндекса нет: используются архивные производные v4 (помесячные траты на жителя, агрегированные доли 2023–2024). Структура трат — только в режиме реконструкции.
- ИНН/КПП → МО — не ОКТМО: многоуровневая привязка с измеренной точностью (LOO 99,2% для кода налогового органа). Первые цифры ИНН — только чувствительность.
- Снимок МСП 10.09.2026 — не исторический статус; только внешний показатель.
- Сайт ЕИС открывать только через Opera Browser Connector; если коннектора нет — работать с экспортами (правило пользователя).
- Не отправлять конкурсную форму, не публиковать данные и не создавать удалённые репозитории без явного указания.

## Команды
```bash
bash scripts/run_all.sh                 # всё: база → тесты → расчёт → аудит → нагрузка → идемпотентность → матрицы → D5/дашборд → отчёт
.venv/bin/python -m econtypes5.ingest   # только база (≈40 с)
.venv/bin/python -m pytest -q tests     # тесты (≈10 с)
.venv/bin/python -m econtypes5.pipeline [--quick]   # расчёт (полный ≈10 мин, quick ≈2 мин)
.venv/bin/python -m econtypes5.dashboard_export --out ../../-/src/v5/D5.json
.venv/bin/python scripts/make_report.py # REPORT_v5.md/.docx/.pdf, STRESS_TEST_REPORT, SOURCE_REGISTRY — только из outputs/latest
(cd ../../- && python3 build.py --version v5 --update-manifest && node tests/v5-check.js econtypes_v5.html)
```

## Устройство
- `econtypes5/icvi.py` — исправленные ICVI (AVU опубликованный ↓; MQ Newman и Mancoridis; S_Dbw с явными соглашениями).
- `compositional.py` (ILR), `graphs.py` (kNN-проверки, self-tuning, SNF, диагностика), `timeseries.py` (слои только по окну), `clustering.py` (spectral, Leiden), `dynamics.py` (венгерское выравнивание, Жаккар, split/merge), `stability.py` (co-assignment), `stats.py` (перестановки, BH/BY, MSR, within/between), `extra_methods.py` (баланс, ECI, e-BH).
- `db.py` (слои L0–L3, миграции), `ingest.py` (сборка базы, контроли), `rosstat.py` (парсеры таблиц Росстата), `geography.py` (привязка к МО).
- `features.py` (панель МО × период × режим), `networks.py` (постановки C1–C4), `experiments.py` (сетка, Pareto, выбор), `pipeline.py` (все этапы, run_id), `dashboard_export.py`.
- Правило выбора K зафиксировано в `experiments.select` — не подгонять под желаемые типы; K = 7 не навязывать.

## Где данные
`../PROJECT_DATA_MAP.md`, `docs/DATA_DICTIONARY.md`, `docs/DATA_GAPS.md`, `external/rosstat_drive/DRIVE_DOWNLOADS.jsonl` (SHA-256 загруженных с Drive файлов), `../econtypes_research_20261009.sqlite` (Git LFS).

## Ход работы
`HANDOFF_STATE.md` — что сделано, команды, следующие шаги. Экономические выводы ссылаются на `run_id` из `outputs/latest/RUN_MANIFEST.json`.
