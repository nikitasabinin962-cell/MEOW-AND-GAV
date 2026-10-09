# HANDOFF_STATE: econtypes v5

Обновлено 09.10.2026. Расчеты берем из `outputs/latest/RUN_MANIFEST.json`, базу из `data/DB_MANIFEST.json`. Оба указывают один прогон. В интерфейсе ничего не пересчитываем.

## Версии и ветки

| Репозиторий | Ветка | Коммит | Что внутри |
|---|---|---|---|
| `nikitasabinin962-cell/MEOW-AND-GAV` (публичный) | `claude/compassionate-carson-i2yna8` | `989685d` (прогон и база) и следующий коммит с документами | расчет `econtypes_v5/`, база, отчеты |
| `nikitasabinin962-cell/-` (приватный, дашборд) | `claude/compassionate-carson-i2yna8` | `1d28fe0` | `econtypes_v5.html`, `econtypes.html` (архив v4), исходники |

Обе ветки выросли из `claude/new-session-cbhyc1` (`47f4a41` и `7c7dd66`), их история не переписывалась. PR и слияний нет.

## Актуальный прогон

- run_id `v5-20261009T142841Z-d833d0`, code_hash `eb402d7943388054` (совпадает с текущим `econtypes5/*.py`), config_hash `d833d01329f4019a`, seed 20261009.
- Окно: типология 2023–2024 (24 месяца, 8 кварталов); проверка вне периода 2025 и 2026 (январь–сентябрь).
- 63 МО, типология 62 (ЗАТО Межгорье без СберИндекса отдельно). Макро spectral K = 3, детальный spectral K = 5.
- Время 1 018 с, пик памяти 752 МиБ, 4 vCPU. Тест будущей информации PASS. pytest 114 PASS.
- Прошлый прогон `v5-20261009T121014Z-d833d0` (K = 3 Leiden и K = 9) считался на коде до исправлений DTW, лагов и окна 2026. Он остался только в истории git.

## Что сделано в этой сессии

1. Сверка: опубликованная v5 (`47f4a41`) согласована, код, прогон и база совпадали. Поздних правок Codex (DTW, лаги, holdout) на GitHub не было, они повторены и проверены здесь.
2. Исправления в коде: `timeseries.py` (DTW на общем сплошном окне, лаговая стрелка только при однозначном максимуме), `pipeline.py` (holdout: счетчик по тем же кварталам, majority baseline, balanced accuracy, ARI, NMI, матрицы ошибок), `dashboard_export.py` (holdout и блок download в D5). Тесты `tests/test_timeseries_contract.py`.
3. Один полный пересчет на исправленном коде, пересборка базы, аудит 13/13, идемпотентность PASS, отчеты пересобраны.
4. Полная база: `scripts/package_db.py` делает снимок через backup API, проверяет восстановление и пишет `data/DB_MANIFEST.json`. Ссылка без входа в GitHub проверена скачиванием.
5. Дашборд: кнопки «Скачать всю базу» и «Описание данных», панель проверки 2025–2026, подписи сети и архивных индексов по формулам (`-/docs/UI_TEXT_CHANGES.md`), `tools/fetch_db.py`, офлайн-проверка.

Что проверено и чем: `FINAL_CHECKS.md`.

## Команды

```bash
cd econtypes_v5
bash scripts/run_all.sh                         # все заново, около 20 мин на 4 vCPU
.venv/bin/python -m pytest -q tests             # 114 тестов, около 10 с
.venv/bin/python scripts/package_db.py          # снимок базы и DB_MANIFEST
.venv/bin/python scripts/package_db.py --url-sha <коммит с архивом>   # ссылки на скачивание
.venv/bin/python -m econtypes5.dashboard_export --out ../../-/src/v5/D5.json
(cd ../../- && python3 build.py --version v5 --update-manifest && node tests/v5-check.js econtypes_v5.html)
```

## Остается

- Сырые parquet СберИндекса, ЕИС через Opera Browser Connector, прямой доступ к rosstat.gov.ru и nalog.gov.ru недоступны в среде (`docs/DATA_GAPS.md`).
- Лаговые связи проверены (`scripts/lag_tests.py`, `outputs/latest/LAG_EDGE_*`): после BH и BY значимых нет, распределение p как при нуле, стрелки не подтверждены; типы от слоя не зависят (абляция ARI 1,000). Слой оставлен в W, в тексте только «разведочно». Если исключать слой из модели, это новый прогон и решение заказчика.
- Вкладки 1–7 дашборда показывают архив v4 с исправленными подписями. Перенос чисел v5 в сами эти вкладки не делался: схемы v4 (7 типов, 13 индексов) не совпадают с моделью v5.
- Windows: инструкции написаны, запуск не проверялся. 2D-резерв карты проверен в Chromium без WebGL (`-/tests/fallback-2d.js`); реальный GPU, Firefox и Safari нет.
- Перенос v5 во вкладки 1–7: ждет решения, нужна ли одна версия вместо «v5 + архив v4».
