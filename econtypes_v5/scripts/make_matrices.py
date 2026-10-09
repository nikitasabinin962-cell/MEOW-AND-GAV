"""Формирует docs/FORMULA_IMPLEMENTATION_MATRIX.csv и docs/REQUIREMENTS_MATRIX.csv с run_id последнего полного прогона."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
man = json.loads((ROOT / "outputs/latest/RUN_MANIFEST.json").read_text())
RID = man["run_id"]
L = "outputs/latest/"

F = [  # документ/раздел, метод, формула, первоисточник, данные, смысл, функция, тест, файл, статус, причина
    ("Задание 3.1; Shalileh et al. 2026", "AVI (Average Isolability)", "AVI = mean_a E_aa/(E_aa+B_a)", "Biswas & Biswas 2017 ESWA 71:1–17; Shalileh, Tsyplakova, Antonov DOI 10.1134/S1064562425700589", "точная W", "изолированность типов в сети", "icvi.avi_avu", "tests/test_icvi.py::test_avi_avu_matches_naive", L + "ICVI_SWEEP.csv", "IMPLEMENTED", "обязательный ICVI"),
    ("Задание 3.1; Shalileh et al. 2026 ф. 20–21", "AVU (Average Unifiability)", "AVU = (1/K) Σ_a Σ_{b≠a} E_ab/(B_a+B_b−E_ab), ↓", "там же", "точная W", "слитность типов; ↓ лучше", "icvi.avi_avu", "test_three_isolated_cliques, test_complete_graph_analytic, test_avu_binary_at_K2", L + "ICVI_SWEEP.csv", "IMPLEMENTED", "заменяет ошибочный AVU v4 (сохранён как intra_inter_density_ratio)"),
    ("Задание 3.2", "MQ — модулярность Ньюмана", "Q = (1/2m) Σ_ij [W_ij − γ k_i k_j/2m] δ(c_i,c_j)", "Newman 2004 PRE 70:056131; Reichardt & Bornholdt 2006", "точная W", "доля веса внутри типов сверх случайной", "icvi.newman_modularity", "test_modularity_matches_naive_and_networkx", L + "ICVI_SWEEP.csv", "IMPLEMENTED", "γ=1; трактовка MQ организатора не подтверждена — считаются оба MQ"),
    ("Задание 3.2", "MQ — Modularization Quality", "(1/K)Σμ_i/N_i² − Σ_{i<j} ε_ij/(2N_iN_j)/(K(K−1)/2)", "Mancoridis et al. 1998 IWPC", "точная W", "альтернативная трактовка MQ", "icvi.mancoridis_mq", "test_mancoridis_bounds_and_cliques", L + "ICVI_SWEEP.csv", "IMPLEMENTED", "для сравнения"),
    ("Задание 3.3", "S_Dbw", "Scat + Dens_bw; плотность по C_i∪C_j (union) / own; явные соглашения 0/0, x/0", "Halkidi & Vazirgiannis 2001 ICDM", "X", "компактность + межкластерная плотность", "icvi.s_dbw", "test_sdbw_matches_naive, test_sdbw_undefined_conventions, test_sdbw_degenerate_cases", L + "ICVI_SWEEP.csv", "IMPLEMENTED", "находка: в v4 Dens_bw ≡ 0 (S_Dbw = Scat)"),
    ("Задание 3.6", "Monte Carlo p", "p = (b+1)/(B+1)", "Phipson & Smyth 2010 SAGMB 9:39", "любые", "конечные p > 0", "stats.mc_p; icvi.permutation_null", "test_mc_p_never_zero, test_permutation_null_pvalue_positive", L + "ICVI_SWEEP.csv; HOLDOUT_VALIDATION.csv", "IMPLEMENTED", ""),
    ("Файл 4, метод 14; METHODS_SELECTION §2", "ILR / расстояние Эйчисона", "z = Vᵀ log p; d_A = ‖clr p − clr q‖", "Aitchison 1982 JRSS-B 44:139; Egozcue et al. 2003", "доли трат, география поставщиков, возраст", "структура без дублирования ограничения суммы", "compositional.ilr_coordinates", "test_ilr_isometry_and_identities, test_zeros_handling", L + "FORMULA_FEATURES_MO_PERIOD.parquet", "IMPLEMENTED", "структура трат — только агрегат 2023–2024 (реконструкция)"),
    ("METHODS_SELECTION §5", "Self-tuning affinity", "W_ij = M_ij exp(−d²/(σ_iσ_j)), σ_i — до 7-го соседа; union/mutual kNN", "Zelnik-Manor & Perona 2004 NeurIPS", "X v5 (блочное расстояние)", "сходство профилей с локальным масштабом", "graphs.self_tuning_affinity", "test_self_tuning_formula, test_self_tuning_duplicates_and_identical", L + "GRAPH_DIAGNOSTICS.csv; ABLATION_SENSITIVITY.csv", "IMPLEMENTED", ""),
    ("METHODS_SELECTION §6", "Линейное слияние слоёв", "W = αS_attr + (1−α)Σω_ℓ S_ℓ", "baseline v4", "слои", "baseline", "graphs.fuse; networks.fuse_graph", "test_snf_runs_symmetric (косвенно)", L + "ABLATION_SENSITIVITY.csv", "IMPLEMENTED", "веса v4 сохранены"),
    ("METHODS_SELECTION §6", "SNF", "P_v ← S_v (mean_{u≠v} P_u) S_vᵀ", "Wang et al. 2014 Nat. Methods 11:333", "слои", "альтернативное слияние", "graphs.snf", "test_snf_runs_symmetric", L + "ABLATION_SENSITIVITY.csv", "EXPERIMENTAL", "сравнение; итог не меняет"),
    ("METHODS_SELECTION §7", "Эволюционное сглаживание", "W̃_t = (1−β)W_t + βW̃_{t−1}", "Chakrabarti et al. 2006 KDD", "W по окнам", "гладкость динамики", "pipeline.stage_dynamics", "LEAKAGE_TEST.json", L + "DYNAMICS_BETA_SENSITIVITY.csv", "IMPLEMENTED", "β-сетка 0…0,9"),
    ("METHODS_SELECTION §7", "Регуляризация проекторов", "min tr(HᵀLH) + η‖HHᵀ − H_{t−1}H_{t−1}ᵀ‖²", "предлагаемая постановка", "L_t", "сглаживание пространства кластеров", "—", "—", "—", "NOT_APPLICABLE", "отложено как сравнительный эксперимент; заменено эволюционным сглаживанием W"),
    ("METHODS_SELECTION §7", "Переходы, Жаккар, split/merge", "T_ab = |C_a∩C_b|/|C_a|; J_ab; венгерское выравнивание", "Kuhn 1955; Greene et al. 2010 (события сообществ)", "метки по кварталам", "события типов во времени", "dynamics.*", "test_hungarian_renaming_and_split_merge, test_node_entry_exit_and_vi", L + "DYNAMICS_EVENTS.csv", "IMPLEMENTED", ""),
    ("METHODS_SELECTION §8", "Co-assignment", "P_ij = ΣO_ij 1(c_i=c_j)/ΣO_ij; без самопары", "Monti et al. 2003 (consensus clustering)", "бутстреп", "устойчивость узлов/пар", "stability.CoAssignment", "test_coassignment_joint_observation_and_self_excluded", L + "COASSIGNMENT.parquet", "IMPLEMENTED", "3 схемы бутстрепа"),
    ("Файл 4, метод 1; METHODS_SELECTION §3", "Сглаженный LQ МСП", "p̂ = (n+κπ)/(n_m+κ), LQ = p̂/π; κ по hold-out правдоподобию", "Stan case study (partial pooling)", "реестр МСП 10.09.2026, адресные кандидаты МО", "специализация по числу фирм", "features.msp_lq", "—", L + "EXTERNAL_INDICATORS_MO.csv", "EXPERIMENTAL", "география — кандидаты по адресу (не ОКТМО), снимок 2026 → внешний показатель, не признак"),
    ("Файл 4, метод 2", "Экономическая сложность (ECI)", "ECI — 2-й собств. вектор D⁻¹MU⁻¹Mᵀ", "Hidalgo & Hausmann 2009 PNAS 106:10570", "МСП 2026", "сложность отраслевой структуры", "extra_methods.economic_complexity", "tests/test_extra_methods.py", L + "EXTERNAL_INDICATORS_MO.csv; MSP_SECTION_COMPLEXITY.csv", "EXPERIMENTAL", "21 секция ОКВЭД — грубое разрешение"),
    ("Файл 4, метод 3", "Близость отраслей / плотность", "ω_ms = Σ M_ms' φ_ss'/Σ φ_ss'", "Hidalgo et al. 2007 Science; Hidalgo et al. 2018", "МСП 2026", "реалистичная диверсификация", "extra_methods.relatedness_density", "tests/test_extra_methods.py", L + "MSP_RELATEDNESS_DENSITY.csv", "EXPERIMENTAL", ""),
    ("Файл 4, метод 4", "Оценка закупочной возможности", "предлагаемая формула econtypes", "—", "позиции ОКПД2 контрактов", "отбор ниш", "—", "—", "—", "DATA_GAP", "нет товарных позиций ОКПД2 (DATA_GAPS №6)"),
    ("Файл 4, метод 5", "Оптимальный транспорт", "Sinkhorn", "Cuturi 2013", "мощности поставщиков", "покрытие спроса", "—", "—", "—", "DATA_GAP", "нет мощностей поставщиков"),
    ("Файл 4, методы 6–8", "TabPFN / TabICLv2 / Chronos-2", "—", "Hollmann et al. 2025 Nature и др.", "панель", "прогноз", "—", "—", "—", "NOT_APPLICABLE", "прогноз своих меток не проверяет экономическую истинность; отложено"),
    ("Файл 4, метод 9", "Conformal / LSCP", "—", "Vovk; LSCP ICML 2026", "прогноз", "интервалы прогноза", "—", "—", "—", "NOT_APPLICABLE", "в кластеризации нет прогнозной задачи"),
    ("Файл 4, метод 10", "M²DG граф с пропусками", "—", "IEEE Access 2026", "сеть закупок", "—", "—", "—", "—", "DATA_GAP", "нет проверенной географии потоков и ИНН ATMO"),
    ("Файл 4, метод 11", "Индикаторы риска закупок", "—", "IJIO 2026", "метки нарушений", "—", "—", "—", "—", "NOT_APPLICABLE", "нет меток"),
    ("Файл 4, методы 12–13", "DML / Synthetic DiD", "—", "Chernozhukov et al. 2018; Arkhangelsky et al. 2021", "воздействие", "причинный эффект", "—", "—", "—", "NOT_APPLICABLE", "нет причинной постановки"),
    ("Файл 4, метод 15", "e-BH", "отклонить k* наибольших e: e_(k) ≥ m/(αk); e = κp^{κ−1}", "Wang & Ramdas 2022 JRSS-B 84:822", "p корреляций", "FDR при произвольной зависимости", "extra_methods.e_bh", "test_ebh_more_conservative_than_bh_on_example", L + "CORRELATIONS_MO_PERIOD.csv", "IMPLEMENTED", "чувствительность к BH/BY"),
    ("Файл 4, метод 16", "Символьная регрессия", "—", "PySR 2023", "—", "—", "—", "—", "—", "NOT_APPLICABLE", "отложено"),
    ("Файл 3, метод 1", "Демографический баланс", "ΔN = B − D + M + A", "базовая демография", "численность, ЕДН 2023–2024, миграция ‱", "компоненты изменения населения", "extra_methods.demographic_balance", "test_demographic_balance_identity", L + "DEMOGRAPHIC_BALANCE.csv", "IMPLEMENTED", "M из коэффициента × средняя численность; A — остаток"),
    ("Файл 3, метод 1", "Разложение рождений (экспозиция/коэффициенты)", "ΔB = ΔW·f̄ + W̄·Δf", "—", "рождения по возрасту матери", "", "—", "—", "—", "DATA_GAP", "DATA_GAPS №18"),
    ("Файл 3, метод 2", "Байесовский когортный прогноз", "—", "Goes & Engelhardt 2026", "история компонентов", "прогноз", "—", "—", "—", "NOT_APPLICABLE", "не требуется для кластеризации; отложено"),
    ("Файл 3, метод 3", "Hamilton–Perry", "CCR = N_{a+5,t}/N_{a,t−5}", "Statistics Canada 2026", "два возрастных среза", "", "—", "—", "—", "DATA_GAP", "только ВПН-2020"),
    ("Файл 3, метод 4", "Миграционная сеть", "p_ij", "Wiśniowski & Raymer 2025", "OD-матрица", "", "—", "—", "—", "DATA_GAP", "только сальдо"),
    ("Файл 3, метод 5", "Возрастная нагрузка", "65+/(20–64)·100; (0–19)/(20–64)·100", "Sanderson & Scherbov 2015 (для POADR)", "ВПН-2020", "старение/детская нагрузка", "extra_methods.age_dependency", "—", L + "EXTERNAL_INDICATORS_MO.csv", "IMPLEMENTED", "POADR — DATA_GAP (нет таблиц смертности МО)"),
    ("Файл 3, методы 6–7, 9", "Спрос на школы, E2SFCA, сетка", "—", "Béres & Péterffy 2026; Luo & Qi 2009; Lee & Jeong 2026", "мощности, маршруты, поселения", "", "—", "—", "—", "DATA_GAP", ""),
    ("Файл 3, метод 8", "BYM2 сглаживание малых чисел", "log r = Xβ + v + (√φ u* + √(1−φ) z)/√τ", "Riebler et al. 2016", "счётчики за несколько лет, соседство", "", "—", "—", "—", "NOT_APPLICABLE", "события по МО — сотни; шум мал по сравнению с межмуниципальной вариацией; отложено"),
    ("Файл 3, метод 10", "Факторы изменения населения", "g = f(X_t)", "Kompil et al. JRC 2026", "панель", "", "pipeline.stage_correlations (описательно)", "—", L + "CORRELATIONS_MO_PERIOD.csv", "EXPERIMENTAL", "только корреляции, не прогнозная модель"),
    ("Задание 7, 10", "Moran spectral randomization", "суррогаты с сохранением I Морана", "Wagner & Dray 2015 MEE 6:1169", "смежность МО", "пространственный нуль", "stats.msr_surrogates", "test_msr_preserves_moran", L + "EXTERNAL_VALIDATION.csv; CORRELATIONS_MO_PERIOD.csv", "IMPLEMENTED", ""),
    ("Дополнение", "Pearson/Spearman + BH/BY + bootstrap CI", "r; p_perm; q", "scipy 1.17", "признаки × внешние", "связи", "stats.corr_test, stats.fdr", "test_spearman_perm_matches_scipy_permutation_test, test_fdr_bh_by", L + "CORRELATIONS_MO_PERIOD.csv", "IMPLEMENTED", ""),
    ("Дополнение", "Between/within с кластерным бутстрепом", "corr средних МО; corr отклонений", "панельная эконометрика", "панель кварталов", "различия МО vs изменения внутри МО", "stats.within_between", "test_within_between", L + "CORRELATIONS_MO_PERIOD.csv", "IMPLEMENTED", ""),
    ("Задание 3.6", "Holdout с корректным нулём", "перестановка предсказанных меток при фиксированных референтных", "—", "контракты 2025–2026", "воспроизводимость разметки по закупкам", "pipeline.stage_holdout", "outputs/PROJECT_CHECKS_v5.json", L + "HOLDOUT_VALIDATION.csv", "IMPLEMENTED", "не независимая экономическая истинность"),
]

with open(ROOT / "docs/FORMULA_IMPLEMENTATION_MATRIX.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["source_document_section", "method", "formula", "primary_source", "required_data", "economic_meaning", "function", "test", "output_file", "run_id", "status", "reason"])
    for r in F:
        w.writerow(list(r[:9]) + [RID if r[9] in ("IMPLEMENTED", "EXPERIMENTAL") else ""] + list(r[9:]))

REQ = [  # требование — модуль — файл — проверка — раздел отчёта
    ("1 Методология 15%", "econtypes5/*; docs/METHODOLOGY_v5.md", "docs/METHODOLOGY_v5.md", "outputs/pytest_log.txt; PROJECT_CHECKS_v5.json", "REPORT §3"),
    ("1 Сеть и атрибуты 15%", "features.py, networks.py, graphs.py, timeseries.py", L + "FORMULA_FEATURES_MO_PERIOD.parquet; GRAPH_DIAGNOSTICS.csv", "test_math_modules.py; LEAKAGE_TEST.json", "REPORT §3"),
    ("1 Математическая динамика 15%", "pipeline.stage_dynamics, dynamics.py", L + "LABELS_MO_PERIOD.parquet; DYNAMICS_*.csv", "LEAKAGE_TEST.json (исполненный)", "REPORT §7"),
    ("1 ICVI SW CH S_Dbw AVI AVU MQ 15%", "icvi.py, experiments.py", L + "ICVI_SWEEP.csv; K_SELECTION.csv", "tests/test_icvi.py (независимые реализации)", "REPORT §3 (табл. 1), §6"),
    ("1 Интерпретация, воспроизводимость 30%", "pipeline.stage_passports/external_validation/correlations; scripts/run_all.sh", L + "TYPE_PASSPORTS*.csv; EXTERNAL_VALIDATION.csv; RUN_MANIFEST.json", "EXTERNAL_VALIDATION (пространственные p); clean rerun", "REPORT §4, §8, §12"),
    ("1 Визуализация 10%", "../-/src/v5/js/80-v5.js; build.py --version v5", "../-/econtypes_v5.html", "../-/docs/v5-checks.json (Playwright)", "../-/README.md (раздел v5); STRESS_TEST_REPORT"),
    ("3.1 AVU опубликованный, ↓", "icvi.avi_avu", L + "ICVI_SWEEP.csv", "test_three_isolated_cliques, test_complete_graph_analytic", "REPORT §1, §10; CHANGELOG"),
    ("3.2 MQ трактовка, γ", "icvi.newman_modularity, mancoridis_mq", L + "ICVI_SWEEP.csv", "test_modularity_matches_naive_and_networkx", "METHODOLOGY §4"),
    ("3.3 S_Dbw сверка", "icvi.s_dbw", L + "ICVI_SWEEP.csv", "test_sdbw_matches_naive, test_sdbw_undefined_conventions", "METHODOLOGY §4"),
    ("3.4 Окна без будущего", "timeseries.restrict, features (режимы), networks.struct_layers_new", L + "LEAKAGE_TEST.json", "stage_leakage_test (PASS/FAIL)", "REPORT §7"),
    ("3.5 Точная W vs проекция", "networks.display_projection, stage_store", "run_matrix_edges; GRAPH_DIAGNOSTICS.csv", "v5-checks: network-note-exact-vs-display", "REPORT §3"),
    ("3.6 p=(b+1)/(B+1), holdout", "stats.mc_p, stage_holdout", L + "HOLDOUT_VALIDATION.csv", "test_mc_p_never_zero; потолок «в выборке» в HOLDOUT_VALIDATION", "REPORT §9"),
    ("3.7 DTW/log0/kNN", "timeseries, graphs._check_k", "—", "test_constant_series_no_nan_layers, test_residuals_zero_spending_not_log, test_knn_k_bounds", "STRESS_TEST_REPORT"),
    ("3.8 ИНН ≠ ОКТМО", "geography.py, ingest.build_geography", "org_geo_resolved, tax_office_map", "LOO accuracy в data_quality_checks", "REPORT §2, DATA_GAPS №5"),
    ("3.9 Имена по профилям", "pipeline.stage_passports", L + "TYPE_PASSPORTS*.csv", "test_type_naming_respects_sign_of_rates", "REPORT §4, METHODOLOGY §9.2"),
    ("3.10 Переименование прокси", "CHANGELOG.md", "—", "—", "CHANGELOG"),
    ("4.1 Реестр источников", "ingest.register_sources", "docs/SOURCE_REGISTRY.csv; source_registry", "SHA-256 сверка в ingest", "DATA_DICTIONARY"),
    ("4.2 Входы СберИндекса", "—", "—", "—", "DATA_GAPS №1–3"),
    ("4.3 Слои L0–L3, run_id", "db.py (миграции)", "data/econtypes_v5.sqlite", "integrity/FK в data_quality_checks", "DATA_DICTIONARY"),
    ("4.4 Копейки, валюты, identity", "ingest.load_contracts, io_robust", "contract", "contracts_kopecks_reconcile_decimal; test_money_*", "STRESS_TEST_REPORT"),
    ("4.5 SQLite + Parquet, идемпотентность, пересверка", "db.export_parquet, ingest.independent_contract_recount", "outputs/db_parquet/", "contracts_independent_recount_csv_vs_v5; idempotency", "STRESS_TEST_REPORT"),
    ("5.1–5.2 СБИС/ЕИС identity 357156/2459", "ingest.run_checks", "data_quality_checks", "identity_basis_reconcile_upstream_357156_2459", "STRESS_TEST_REPORT"),
    ("5.3–5.6 ATMO", "external/atmo_audit/", "ATMO44_b6z6lq_PART_AUDIT.csv; ATMO44_SAMPLE_CONTENT_AUDIT.json", "аудит метаданных 340/341 частей; выборка 2 частей", "DATA_GAPS №9–10"),
    ("5.8–5.9 МСП", "ingest.load_msp", "msp_firm, msp_index_firm", "join 173892/103660/82063 (PASS)", "STRESS_TEST_REPORT"),
    ("5.10 HTTP 429/5xx, resume", "io_robust.Fetcher/paginate", "—", "tests/test_data_edge_cases.py (локальный сервер)", "STRESS_TEST_REPORT"),
    ("5.11 ЕИС только через Opera", "—", "—", "сайт ЕИС не открывался", "HANDOFF_STATE"),
    ("6 Росстат", "rosstat.py", "external/rosstat_drive/", "контроли Σ МО vs республика; тождества", "DATA_GAPS"),
    ("7 Признаки и рёбра", "features.py, networks.py", L + "FORMULA_FEATURES_MO_PERIOD.parquet", "test_math_modules.py", "METHODOLOGY §2–3"),
    ("8 Динамика и неопределённость", "pipeline.stage_dynamics, stage_uncertainty", L + "UNCERTAINTY_SUMMARY.csv; COASSIGNMENT.parquet", "LEAKAGE_TEST.json", "REPORT §7"),
    ("9 Интерпретация и визуализация", "stage_passports; 80-v5.js", L + "TYPE_PASSPORTS*.csv; ../-/econtypes_v5.html", "v5-checks.json", "REPORT §4, §5"),
    ("10 Стресс-тесты и нагрузка", "tests/, scripts/scale_benchmark.py", "docs/STRESS_TEST_REPORT.md; outputs/SCALE_BENCHMARK.json", "фактические PASS/FAIL/NOT_RUN", "STRESS_TEST_REPORT"),
    ("Дополнение: FORMULA_IMPLEMENTATION_MATRIX", "scripts/make_matrices.py", "docs/FORMULA_IMPLEMENTATION_MATRIX.csv", "—", "REPORT §3"),
    ("Дополнение: корреляции", "stats.py, stage_correlations", L + "CORRELATIONS_MO_PERIOD.parquet", "test_spearman_perm_matches_scipy_permutation_test", "REPORT §8"),
    ("Комплект: Word/PDF отчёт", "scripts/make_report.py", "docs/REPORT_v5.docx; docs/REPORT_v5.pdf; docs/REPORT_v5.md", "числа читаются из outputs/latest", "—"),
    ("Комплект: README с одной командой, CHANGELOG, HANDOFF_STATE, CLAUDE.md", "scripts/run_all.sh", "README.md; CHANGELOG.md; HANDOFF_STATE.md; CLAUDE.md", "clean rerun run_all.sh", "REPORT §12"),
    ("Комплект: метки МО × период", "pipeline.stage_dynamics, stage_store", L + "LABELS_STATIC.csv; LABELS_MO_PERIOD*.parquet", "—", "REPORT §4, §7"),
    ("Дополнение: сравнительная кластеризация", "experiments.py, stage_comparison/ablation", L + "CLUSTER_COMPARISON.csv; ABLATION_SENSITIVITY.csv", "—", "REPORT §6"),
]
with open(ROOT / "docs/REQUIREMENTS_MATRIX.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["requirement", "module", "output_file", "verifying_check", "report_section", "run_id"])
    for r in REQ:
        w.writerow(list(r) + [RID])
print("ok", RID, len(F), len(REQ))
