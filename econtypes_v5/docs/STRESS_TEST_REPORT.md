# STRESS_TEST_REPORT — econtypes v5

Прогон: `v5-20261009T142841Z-d833d0` (config `d833d01329f4019a`, code `eb402d7943388054`, data `24f5b250a5cc5492`, seed 20261009). Отчёт собирается автоматически `scripts/make_report.py` из файлов проверок; статус берётся из файла, а не вписывается.

Итого: **FAIL** 1, **INFO** 5, **NOT_RUN** 7, **PASS** 56.

Статусы: PASS — проверка исполнена и прошла; FAIL — исполнена и не прошла; INFO — измерение без порога; NOT_RUN — не исполнялась (причина указана).

## код

| проверка | статус | основание | детали |
|---|---|---|---|
| pytest (модульные и краевые тесты) | **PASS** | outputs/pytest_log.txt | 114 passed, 0 failed |

## данные

| проверка | статус | основание | детали |
|---|---|---|---|
| population_sum_equals_region_control | **PASS** | data_quality_checks (база v5) | [{"period": "2022-01-01", "s": 4091621.0, "n": 63}, {"period": "2023-01-01", "s": 4077600.0, "n": 63}, {"period": "2024-01-01", "s": 4064361.0, "n": 63}, {"period": "2025-01-01", " |
| edn_identity_births_minus_deaths | **PASS** | data_quality_checks (база v5) | {"max_abs_violation": 0.0, "residual_vs_region": [{"indicator": "births", "period": "2023", "s": 35278.0, "n": 62, "value": 35388.0, "residual_mezhgorye": 110.0}, {"indicator": "bi |
| migration_2023_consistent_between_publications | **PASS** | data_quality_checks (база v5) | {"max_abs_diff": 0.05000000000001137, "n": 62, "note": "разные округления: 2 и 1 знак"} |
| census_age_groups_sum_to_total | **PASS** | data_quality_checks (база v5) | {"max_abs": 0.0, "region_total": 4091423.0, "sum_62": 4075726.0, "residual_mezhgorye": 15697.0} |
| contracts_independent_recount_csv_vs_v5 | **PASS** | data_quality_checks (база v5) | {"files": 8, "csv": {"rows": 359615, "ids": 359615, "rub_known": "1263174213398.89", "distinct_supplier_inn": 16337, "missing_supplier_inn": 82063, "distinct_customer_inn": 5110},  |
| contracts_kopecks_reconcile_decimal | **PASS** | data_quality_checks (база v5) | {"rows": 359615, "kopeck_mismatch": 0} |
| contract_inn_checksums | **INFO** | data_quality_checks (база v5) | {"invalid_customer_inn": 0, "invalid_supplier_inn": 0} |
| reestr_number_embeds_customer_inn | **INFO** | data_quality_checks (база v5) | {"agree": 278101, "disagree": 1358, "note": "44-ФЗ: 19-значный реестровый номер = уровень бюджета (1 цифра) + ИНН заказчика (10) + год + №; расхождения оставлены как есть"} |
| customer_geography_loo_accuracy | **INFO** | data_quality_checks (база v5) | {"customers": 5138, "named_explicit": 2038, "loo_kpp": {"code": "kpp4", "evaluated": 2034, "assigned": 2034, "abstained": 0, "correct": 2018, "accuracy": 0.992133726647001, "covera |
| identity_basis_reconcile_upstream_357156_2459 | **PASS** | data_quality_checks (база v5) | {"declared_registry_number_buyer_and_search_agree": 68982, "exact_representation_only": 2459, "internal_contract_card_id": 8715, "registry_number_from_contract_card": 279459} |
| SQLite integrity_check + foreign_key_check | **PASS** | outputs/ingest_log.json | {"integrity": "ok", "foreign_key_violations": 0, "fk_sample": []} |
| идемпотентность ingest (два прохода, сравнение дайджестов таблиц) | **PASS** | outputs/IDEMPOTENCY_CHECK.json | 10/10 таблиц совпали |
| базовый D.json v4 не изменён (SHA-1) | **PASS** | reproduction/source/src/data/D.json | d849169e16d7d2c42c1f210426b1490b6832b76a |
| D.json v4 в репозитории дашборда не изменён (SHA-1) | **PASS** | -/src/data/D.json | d849169e16d7d2c42c1f210426b1490b6832b76a |

## повтор проверок аудитора

| проверка | статус | основание | детали |
|---|---|---|---|
| baseline_dimensions_and_finite_v5 | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'N': 62, 'features': 18, 'nonfinite_cells': 0, 'exact_edges': 1079, 'components': 1, 'K': 3} |
| v4_matrix_reproduces_auditor_AVU_MQ_SDbw | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'edges': 1065, 'AVU_published': 0.5358312305082137, 'AVI': 0.3720891681970672, 'old_v4_metric': 0.8017049075869529, 'MQ_newman_W': 0.24413833452756928, 'MQ_newman_display_310': 0. |
| v4_labels_rescored_on_v5_C1_matrix_independent | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'AVU_published_independent': 0.5357349869378856, 'AVU_pipeline': 0.5357349869378856, 'old_v4_metric_intra_inter': 0.798992456449919, 'MQ_C1space': 0.2403399197158515, 'SW_C1space' |
| AVU_formula_and_optimization_direction | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'v5': 0.5692456315848, 'reference': 0.5692456315848, 'direction': 'min'} |
| AVU_disconnected_three_cliques | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'AVU': 0.0, 'AVI': 1.0, 'old_ratio_metric': 1.0} |
| finite_permutation_pvalues_are_positive | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'mc_p(0,999)': 0.001, 'holdout_min_p': 0.0001} |
| DTW_all_constant_series | **PASS** | outputs/PROJECT_CHECKS_v5.json | degenerate_no_positive_distance |
| zero_monthly_expenditure | **PASS** | outputs/PROJECT_CHECKS_v5.json | log(0) не вычисляется: NaN + статус 'nonpositive_values' |
| kNN_k_above_N | **PASS** | outputs/PROJECT_CHECKS_v5.json | k = 6 больше N−1 = 4: у узла нет столько соседей (N = 5) |
| historical_layers_do_not_use_future_EXECUTED | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'monitoring': {'features_identical': True, 'W_identical': True, 'labels_identical': True}, 'retrospective': {'features_identical': False, 'W_identical': False, 'labels_identical': |
| actual_self_tuning_kNN_N_2016 | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'N': 2016, 'seconds': 1.257, 'edges': 12918} |
| label_permutation_invariance | **PASS** | outputs/PROJECT_CHECKS_v5.json | ok |
| ICVI_K_equals_N_rejected_with_status | **PASS** | outputs/PROJECT_CHECKS_v5.json | {'SW': 'undefined_K_ge_N', 'CH': 'undefined_K_ge_N', 'DB': 'undefined_K_ge_N', 'S_Dbw': 'ok', 'S_Dbw_floor1': 'ok', 'AVI': 'ok', 'AVU': 'ok', 'MQ_newman': 'ok', 'MQ_mancoridis': 'o |

## расчёт

| проверка | статус | основание | детали |
|---|---|---|---|
| полный конвейер завершён | **PASS** | outputs/latest/RUN_MANIFEST.json | run_id v5-20261009T142841Z-d833d0; пик RSS 752 МиБ |
| предупреждения численных библиотек перехвачены и записаны | **PASS** | RUN_MANIFEST.json → diagnostics_warnings | 0 предупреждений |
| утечка будущего: искажение данных после 2023Q4 (исполненный тест) | **PASS** | outputs/latest/LEAKAGE_TEST.json | мониторинг: признаки/W/метки идентичны = {'features_identical': True, 'W_identical': True, 'labels_identical': True}; реконструкция меняется = True |
| запись результатов в базу (integrity, FK) | **PASS** | RUN_MANIFEST.json → store | {"integrity": "ok", "foreign_key_violations": 0, "fk_sample": []} |
| вне периода: macro, закупки 2023–2024 (в выборке) | **INFO** | outputs/latest/HOLDOUT_VALIDATION.csv | точность 0,61 против нуля 0,34 (q95 0,44), p = 0,0001, B = 9999 |
| вне периода: macro, закупки 2025 | **PASS** | outputs/latest/HOLDOUT_VALIDATION.csv | точность 0,65 против нуля 0,39 (q95 0,48), p = 0,0001, B = 9999 |
| вне периода: macro, закупки 2026 | **PASS** | outputs/latest/HOLDOUT_VALIDATION.csv | точность 0,68 против нуля 0,39 (q95 0,47), p = 0,0001, B = 9999 |
| вне периода: detailed, закупки 2023–2024 (в выборке) | **INFO** | outputs/latest/HOLDOUT_VALIDATION.csv | точность 0,65 против нуля 0,20 (q95 0,29), p = 0,0001, B = 9999 |
| вне периода: detailed, закупки 2025 | **PASS** | outputs/latest/HOLDOUT_VALIDATION.csv | точность 0,40 против нуля 0,19 (q95 0,27), p = 0,0001, B = 9999 |
| вне периода: detailed, закупки 2026 | **PASS** | outputs/latest/HOLDOUT_VALIDATION.csv | точность 0,40 против нуля 0,21 (q95 0,29), p = 0,0001, B = 9999 |

## нагрузка

| проверка | статус | основание | детали |
|---|---|---|---|
| синтетика N=63: граф+spectral+Leiden+ICVI | **PASS** | outputs/SCALE_BENCHMARK.json | граф 0.001 с, spectral 0.003 с, Leiden 0.348 с, ICVI 0.007 с, пик 268.2 МиБ; DTW всех пар ≈ 0.2 с |
| синтетика N=500: граф+spectral+Leiden+ICVI | **PASS** | outputs/SCALE_BENCHMARK.json | граф 0.026 с, spectral 0.027 с, Leiden 0.028 с, ICVI 0.024 с, пик 283.5 МиБ; DTW всех пар ≈ 11.5 с |
| синтетика N=2016: граф+spectral+Leiden+ICVI | **PASS** | outputs/SCALE_BENCHMARK.json | граф 0.88 с, spectral 0.481 с, Leiden 0.172 с, ICVI 0.245 с, пик 471.2 МиБ; DTW всех пар ≈ 183.8 с |

## дашборд

| проверка | статус | основание | детали |
|---|---|---|---|
| v5.default-tab-is-v5 | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.map-63-polygons | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"nPaths": 63} |
| v5.banner-has-run-id | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | 
    econtypes v5 — пересчёт после исправлений. run_id v5-20261009T121014Z-d833d0. Макроуровень: leiden, K = 3; детальный уровень: spectral, K = 9 (оба выбраны  |
| v5.meta-v4-date-labelled | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.header-kpis-are-v5 | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | 3 / 9типов v5: макро / детальный0,94бутстреп ARI (узлы)0,94бутстреп ARI (месяцы)PASSтест будущей информации1082рёбер точной W |
| v5.time-controls-visible | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.scrubber-p95-ms<300 | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"p95": 63, "times": [25, 36, 40, 40, 41, 46, 48, 63]} |
| v5.scrubber-updates-label | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | 2024Q4 |
| v5.scrubber-keyboard | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.level-switch-detailed-legend | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"nLeg": 9, "nLeg2": 9} |
| v5.select-mo-syncs-profile-map-net | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"h": "ГО Агидель", "onPath": 1, "onEdge": 5} |
| v5.profile-shows-provenance | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"prov": 22} |
| v5.sankey-rendered | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.coassign-rendered | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.icvi-table-rows | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.coverage-table-63 | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.network-note-exact-vs-display | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) |  |
| v5.load-ms<8000 | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"loadMs": 1163} |
| v5.mobile-no-horizontal-scroll | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | {"overflow": 0} |
| v5.no-console-errors | **PASS** | -/docs/v5-checks.json (Playwright, Chromium) | [] |
| дашборд собран из этого же прогона (run_id в шапке) | **FAIL** | -/docs/v5-checks.json | v5-20261009T142841Z-d833d0 |

## не выполнено

| проверка | статус | основание | детали |
|---|---|---|---|
| полная загрузка ATMO 44-ФЗ (493 912 записей, 341 часть) | **NOT_RUN** | — | часть 51 отсутствует в листинге Drive; потоковая загрузка не выполнялась — использованы canonical CSV (359 615 контрактов) и выборочный аудит |
| общероссийский прогон (~2 000+ МО) | **NOT_RUN** | — | нет входов СберИндекса по всем МО; проверено только ядро алгоритмов на синтетике N = 2 016 |
| сырые parquet СберИндекса (consumption, connection, market_access) | **NOT_RUN** | — | не найдены на Drive; sberindex.ru закрыт политикой сети (403); использованы производные v4 |
| прямая загрузка с rosstat.gov.ru / nalog.gov.ru | **NOT_RUN** | — | закрыто политикой сети (403); таблицы Росстата взяты с Drive пользователя с SHA-256 |
| ЕИС (zakupki.gov.ru) через Opera Browser Connector | **NOT_RUN** | — | коннектор в сессии отсутствует; по правилу пользователя другой канал не использовался |
| ручная выборочная сверка привязки адресов с открытыми реестрами | **NOT_RUN** | — | нет сетевого доступа к ФНС/ЕГРЮЛ; точность оценена LOO внутри данных |
| публикация, отправка конкурсной формы | **NOT_RUN** | — | не выполнялось — требуется отдельное указание пользователя |
