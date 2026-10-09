# DATA_DICTIONARY — база econtypes v5 и выходные файлы

База: `data/econtypes_v5.sqlite` (строится `python -m econtypes5.ingest`, около 50 с; распакованная около 330 МБ). Готовый снимок для скачивания: `data/econtypes_v5.sqlite.gz`, его размер, SHA-256, число строк в каждой таблице и run_id записаны в `data/DB_MANIFEST.json`. Экспорт для аналитики: `outputs/db_parquet/*.parquet` (zstd). Деньги — целые копейки (`amount_kopecks`), валюта — отдельным полем; суммы складываются только внутри одной валюты и `financial_status='known'`.

## L0 — источники

**source_registry** — одна строка на файл-источник: `source_id` (PK), `title`, `relative_path`, `storage_location`, `url`, `drive_id`, `sha256`, `size_bytes`, `retrieved_at` (дата загрузки ≠ период наблюдения), `observation_period`, `publication_date`, `territory`, `units`, `grain`, `keys`, `license_terms`, `completeness`, `known_errors`, `row_count`, `control_totals_json`, `role`, `status`, `limitations`.

## L1 — нормализованные факты

| Таблица | Зерно / ключ | Поля и смысл |
|---|---|---|
| **mo** | `mo_id` (0…62, как в research DB и D.json v4) | `name` (нотация v4: «МР Абзелиловский», «ГО Уфа»), `kind`, `oktmo` (NULL; `oktmo_status` объясняет), `sber_territory_id` (алгоритмическое сопоставление v4), `boundary_valid_from/to`, `boundary_note` |
| **mo_alias** | `alias` | Варианты названий → `mo_id` |
| **fact_mo** | (`mo_id`, `indicator`, `period`, `source_id`) | `value`, `unit`, `status` (`observed` / `archived_derived` / `derived`), `publication_date`, `revision`, `note`. Индикаторы: `population` (чел., на 01.01), `births`/`deaths`/`natinc` (чел.), `birth_rate`/`death_rate`/`natinc_rate` (‰), `migr_rate` (‱), `census_age_*` (чел., 5-летние группы ВПН-2020), `census_edu_*`, `census_main_*`/`census_livelihood_total` (чел.), `sber_spend_pc_month` (руб./жителя/мес., архив D.json v4), `v4_*` (32 архивных признака v4) |
| **fact_region_control** | (`indicator`, `period`, `source_id`) | Республиканские итоги из тех же таблиц — для сверки Σ МО |
| **contract** | `canonical_contract_id` | `law`, `contract_number`, `budget_level` (44-ФЗ: 1 — федеральный, 2 — субъекта, 3 — муниципальный; из реестрового номера), `sign_date`, `amount_kopecks`, `currency`, `financial_status` (`known` / `identity_unconfirmed` / `currency_conflict`), `identity_basis`, `customer_inn/kpp/name`, `supplier_inn/kpp/name`, `subject`, `status_variants`, `source_file` (XLSX СБИС), `upstream_source_id`, `customer_inn_valid`, `supplier_inn_valid`, `reestr_inn_agrees` |
| **tax_office_map** | `code` (4 цифры КПП) | `mo_id`, `n_named` (организаций с явным МО в названии), `purity`, `usable` |
| **org_geo_evidence** | (`inn`, `kpp`, `role`, `method`) | Каждый признак привязки: `mo_id`, `confidence`, `evidence`, `valid_asof`, `source_id` |
| **org_geo_resolved** | (`inn`, `kpp`, `role`) | Итоговая привязка: `mo_id`, `region_code`, `quality` (см. METHODOLOGY §10), `methods_agree` |
| **msp_firm** | (`inn`, `snapshot_date`) | Реестр МСП РБ на 10.09.2026: `category_code` (1 микро, 2 малое, 3 среднее), `okved_main`, `okved_section`, `region_code`, `mo_id_candidate` (по тексту адреса), `geo_status`, `headcount` (NULL = нет данных, не 0) |
| **msp_index_firm** | (`inn`, `snapshot_date`) | Отбор релевантных фирм разных регионов (не весь национальный реестр) |

## L2 — признаки

**attribute_mo_period** — (`mo_id`, `period`, `feature`, `mode`): `value` (исходная шкала до стандартизации), `unit`, `block`, `transform`, `coverage` (доля стоимости/месяцев с известными данными), `imputed` (в v5 всегда 0 — импутации нет), `source_ids`, `observation_window`, `available_from` (конец окна). `period` ∈ {2023Q1…2024Q4, static}; `mode` ∈ {retrospective, monitoring}.

## L3 — результаты прогона

| Таблица | Содержание |
|---|---|
| **run** | `run_id`, `created_at`, `config_hash`, `code_hash`, `data_hash`, `mode`, `seed`, `note` |
| **run_labels** | (`run_id`, `config`, `period`, `mo_id`) → `label`. `config`: разметки сравнения (`C4_v5features_v5graph|leiden|K=3|selected` и т. п.), `dynamic|monitoring|beta=0.5`, `dynamic_detailed|…` |
| **run_icvi** | Индексы каждой ячейки сетки: `index_name`, `value`, `direction`, `space` (attributes/network), `matrix` (`W_exact[C4…]` или `X[C4…]`), `status` |
| **run_matrix_edges** | Точная W (`…|exact`), визуальная проекция (`…|display_k4`), слои C4 до слияния (`C4…|layer:attr_self_tuning|comovement|lead_lag|dtw|procurement_flow`) |
| **run_coassign** | (`run_id`, `scheme`, `i`, `j`) → `p`, `n_joint` |
| **data_quality_checks** | `check_name`, `status` (PASS/FAIL/INFO/NOT_RUN), `details_json`, `checked_at` |

Служебная таблица **schema_migrations**: `version`, `applied_at`, `description` — применённые миграции схемы; `max(version)` = `schema_version` в DB_MANIFEST.

Представления: `v_contract_customer_mo` (контракт + МО заказчика + качество привязки), `v_population_growth`.

## Выходные файлы прогона (`outputs/run_<run_id>/`, копия — `outputs/latest/`)

| Файл | Содержание |
|---|---|
| `FORMULA_FEATURES_MO_PERIOD.parquet/csv` | Панель признаков МО × период × режим с единицами, блоком, покрытием, импутацией, hindsight, источником, окном |
| `EXTERNAL_INDICATORS_MO.csv` | Внешние показатели (не в обучении): перепись, МСП LQ/ECI, архив v4, баланс |
| `CONFIG_FEATURES.csv` | Состав признаков постановок C1–C4 |
| `GRAPH_DIAGNOSTICS.csv` | Рёбра, компоненты, изоляты, степени, спектр нормированного лапласиана, eigengap — для точных W, проекций, слоёв и правил ребра |
| `ICVI_SWEEP.csv` | Постановка × метод × K: сырые индексы, статусы, z, p, B, бутстреп-ARI, Pareto |
| `K_SELECTION.csv` | Выбранное решение в каждой постановке (+ детальный уровень C4) |
| `CLUSTER_COMPARISON.csv` | Разметки сравнения: K, ARI/VI с итогом и с v4, индексы в своём пространстве и в общих пространствах C4 и C1, бутстреп |
| `ABLATION_SENSITIVITY.csv` | Абляция блоков/слоёв, α, k, k_scale, mutual, правила ребра, SNF, строгая география |
| `UNCERTAINTY_SUMMARY.csv`, `NODE_STABILITY.csv`, `COASSIGNMENT.parquet/csv` | Три схемы бутстрепа; устойчивость узлов; co-assignment пар с числом совместных наблюдений |
| `LABELS_MO_PERIOD(.parquet/_DETAILED)` | Метки МО × квартал × режим × β (макро и детальный уровни) |
| `DYNAMICS_QUALITY*`, `DYNAMICS_BETA_SENSITIVITY*`, `DYNAMICS_EVENTS*`, `DYNAMICS_PROFILE_SHIFT*` | Качество снимков, ARI/VI во времени, события split/merge/birth/death, сдвиг профилей |
| `LEAKAGE_TEST.json` | Исполненный тест отсутствия будущей информации |
| `TYPE_PASSPORTS.csv`, `TYPE_PASSPORTS_DETAILED.csv` | Экономические паспорта типов |
| `EXTERNAL_VALIDATION.csv` | Типы против независимых показателей: H, ε², p (перестановочное и пространственное), q BH/BY, I Морана |
| `CORRELATIONS_MO_PERIOD.parquet/csv`, `FEATURE_CORR_MATRIX.csv` | Корреляции признаков с внешними показателями; панель within/between; дублирование признаков |
| `HOLDOUT_VALIDATION.csv` | Узнаваемость типа по закупкам 2025 и 2026 (YTD) с корректной нулевой моделью |
| `DEMOGRAPHIC_BALANCE.csv` | ΔN = B − D + M + A по МО, 2023 и 2024 |
| `MSP_SECTION_COMPLEXITY.csv`, `MSP_RELATEDNESS_DENSITY.csv` | PCI/повсеместность секций; плотность связанности МО × секция |
| `MEZHGORYE_STATUS.json` | Отдельный статус ЗАТО Межгорье |
| `RUN_MANIFEST.json` | run_id, хеши, итог, тайминги, пиковая память, N/T/E, захваченные предупреждения |

## Как скачать и проверить полную базу

1. Скачайте `econtypes_v5.sqlite.gz` по ссылке `url` из `data/DB_MANIFEST.json` (или кнопкой «Скачать всю базу» во вкладке v5 дашборда). Вход в GitHub не нужен.
2. Сверьте SHA-256 архива с полем `sha256`: `sha256sum econtypes_v5.sqlite.gz` (Windows: `certutil -hashfile econtypes_v5.sqlite.gz SHA256`).
3. Распакуйте: `gunzip -k econtypes_v5.sqlite.gz` (Windows: 7-Zip). SHA-256 распакованного файла — поле `sqlite_sha256`.
4. Проверьте: `sqlite3 econtypes_v5.sqlite "PRAGMA integrity_check; PRAGMA foreign_key_check;"` и сравните `SELECT count(*)` по таблицам с `table_counts`.

Снимок содержит все таблицы, представления и индексы базы. Чего в нём нет и почему: поле `not_included` и `docs/DATA_GAPS.md`.
