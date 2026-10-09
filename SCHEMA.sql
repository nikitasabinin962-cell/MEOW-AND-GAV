CREATE INDEX atmo_identity_idx ON atmo_contract_observations(law,api_record_type,api_record_id);

CREATE INDEX contract_supplier_inn_idx ON processed_contracts(supplier_inn);

CREATE INDEX msp_inn_idx ON msp_snapshot_rows(inn,snapshot_date);

CREATE INDEX msp_supplier_index_inn_idx ON msp_supplier_index_snapshot(inn,snapshot_date);

CREATE TABLE atmo_contract_observations(row_id INTEGER PRIMARY KEY,law TEXT,api_record_type TEXT,api_record_id TEXT,api_contract_id TEXT,registration_number TEXT,status_code TEXT,published_at_utc TEXT,contract_at_utc TEXT,contract_date_rb TEXT,executed_at_utc TEXT,price_kopecks INTEGER,starting_price_kopecks INTEGER,customer_api_id TEXT,customer_name TEXT,customer_municipality_raw TEXT,supplier_api_id TEXT,supplier_name TEXT,customer_inn TEXT,supplier_inn TEXT,okpd2 TEXT,subject TEXT,proposals_count INTEGER,delivery_addresses_json TEXT,source_id TEXT REFERENCES sources,raw_json TEXT);

CREATE TABLE baseline_cluster_labels(mo_id INTEGER REFERENCES municipalities,period TEXT,label INTEGER,version TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,period));

CREATE TABLE baseline_feature_aggregates(mo_id INTEGER REFERENCES municipalities,feature TEXT,value REAL,period_start TEXT,period_end TEXT,status TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,feature));

CREATE TABLE baseline_graph_edges(layer TEXT,source_mo INTEGER REFERENCES municipalities,target_mo INTEGER REFERENCES municipalities,weight REAL,lag INTEGER,directed INTEGER,unit TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(layer,source_mo,target_mo));

CREATE TABLE baseline_monthly_spending(mo_id INTEGER REFERENCES municipalities,period TEXT,value REAL,unit TEXT,status TEXT,source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,period));

CREATE TABLE data_quality_checks(check_name TEXT PRIMARY KEY,status TEXT,details_json TEXT);

CREATE TABLE dataset_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);

CREATE TABLE msp_municipality_candidates(row_id INTEGER PRIMARY KEY REFERENCES msp_snapshot_rows,mo_id_candidate INTEGER REFERENCES municipalities,method TEXT,verified_oktmo TEXT,status TEXT);

CREATE TABLE msp_snapshot_rows(row_id INTEGER PRIMARY KEY,inn TEXT,region_code TEXT,legal_form TEXT,category_code TEXT,category TEXT,name TEXT,okved_main TEXT,headcount_raw TEXT,district_raw TEXT,city_raw TEXT,locality_raw TEXT,inclusion_date_raw TEXT,snapshot_date TEXT,source_xml TEXT,inn_checksum_valid INTEGER,source_id TEXT REFERENCES sources);

CREATE TABLE msp_supplier_index_snapshot(row_id INTEGER PRIMARY KEY,inn TEXT,category_raw TEXT,region_code TEXT,okved_main TEXT,legal_form TEXT,snapshot_date TEXT,source_id TEXT REFERENCES sources);

CREATE TABLE municipalities(mo_id INTEGER PRIMARY KEY,name TEXT UNIQUE,kind TEXT,official_oktmo TEXT,territory_id INTEGER,sber_mapping_status TEXT);

CREATE TABLE population(mo_id INTEGER REFERENCES municipalities,observation_date TEXT,value INTEGER CHECK(value>0),unit TEXT DEFAULT 'persons',source_id TEXT REFERENCES sources,PRIMARY KEY(mo_id,observation_date));

CREATE TABLE processed_contracts("canonical_contract_id" TEXT PRIMARY KEY,"processing_group" TEXT,"has_eis" TEXT,"has_atmo" TEXT,"identity_basis" TEXT,"raw_records" INTEGER,"representation_variants" INTEGER,"contract_number" TEXT,"sign_date" TEXT,"sign_date_variants" TEXT,"amount" TEXT,"amount_cents" INTEGER,"amount_min" TEXT,"amount_max" TEXT,"currency" TEXT,"currency_variants" TEXT,"financial_status" TEXT,"customer" TEXT,"customer_inn" TEXT,"customer_kpp" TEXT,"supplier" TEXT,"supplier_inn" TEXT,"supplier_kpp" TEXT,"subject" TEXT,"status_variants" TEXT,"contract_url" TEXT,"tender_url" TEXT,"eis_purchase_reg_number" TEXT,"atmo_purchase_id" TEXT,"law" TEXT,"territory" TEXT,"first_raw_record_id" TEXT,"source_file" TEXT, import_source_id TEXT REFERENCES sources);

CREATE TABLE procurement_notice_exports(row_id INTEGER PRIMARY KEY,source_id TEXT REFERENCES sources,raw_json TEXT);

CREATE TABLE sources(source_id TEXT PRIMARY KEY,relative_path TEXT,original_name TEXT,sha256 TEXT,size_bytes INTEGER,source_url TEXT,observation_period TEXT,role TEXT,limitations TEXT);

CREATE VIEW atmo_identity_conflicts AS SELECT law,api_record_type,api_record_id,api_contract_id,COUNT(*) AS rows,COUNT(DISTINCT raw_json) AS payload_versions FROM atmo_contract_observations GROUP BY law,api_record_type,api_record_id,api_contract_id HAVING COUNT(DISTINCT raw_json)>1;

CREATE VIEW atmo_monthly_observed AS SELECT law,substr(contract_date_rb,1,7) AS month,COUNT(*) AS observation_rows,SUM(price_kopecks) AS price_kopecks FROM atmo_contract_observations GROUP BY law,substr(contract_date_rb,1,7);

CREATE VIEW atmo_monthly_unique_candidates AS SELECT law,substr(contract_date_rb,1,7) AS month,COUNT(*) AS unique_api_records,SUM(price_kopecks) AS price_kopecks FROM atmo_unique_contract_candidates GROUP BY law,substr(contract_date_rb,1,7);

CREATE VIEW atmo_unique_contract_candidates AS SELECT o.* FROM atmo_contract_observations o WHERE o.row_id IN (SELECT MIN(row_id) FROM atmo_contract_observations GROUP BY law,api_record_type,api_record_id,api_contract_id HAVING COUNT(DISTINCT raw_json)=1);

CREATE VIEW contract_msp_asof_20260910 AS SELECT c.canonical_contract_id,c.sign_date,c.law,c.supplier_inn,c.amount_cents,c.currency,c.identity_basis,m.region_code AS msp_region_on_snapshot,'2026-09-10' AS msp_snapshot_date,CASE WHEN c.supplier_inn IS NULL THEN 'supplier_inn_unavailable' WHEN m.inn IS NOT NULL THEN 'found_in_snapshot' ELSE 'not_found_in_snapshot' END AS msp_status_asof_snapshot FROM processed_contracts c LEFT JOIN msp_supplier_index_unique m ON m.inn=c.supplier_inn AND m.snapshot_date='2026-09-10';

CREATE VIEW msp_candidate_counts AS SELECT m.name,c.status,COUNT(DISTINCT r.inn) AS distinct_inns FROM msp_snapshot_rows r JOIN msp_municipality_candidates c USING(row_id) LEFT JOIN municipalities m ON m.mo_id=c.mo_id_candidate GROUP BY c.mo_id_candidate,c.status;

CREATE VIEW msp_supplier_index_unique AS SELECT inn,snapshot_date,MIN(region_code) AS region_code,MIN(category_raw) AS category_raw,COUNT(*) AS source_rows FROM msp_supplier_index_snapshot GROUP BY inn,snapshot_date;

CREATE VIEW msp_unique_entities AS SELECT inn,snapshot_date,COUNT(*) AS source_rows,MIN(category_code) AS category_code,COUNT(DISTINCT okved_main) AS okved_versions,MAX(inn_checksum_valid) AS checksum_valid FROM msp_snapshot_rows GROUP BY inn,snapshot_date;

CREATE VIEW population_growth AS SELECT p.mo_id,m.name,p.observation_date,p.value,prev.value AS previous_value,p.value-prev.value AS delta_persons,1.0*(p.value-prev.value)/prev.value AS growth FROM population p JOIN municipalities m USING(mo_id) LEFT JOIN population prev ON prev.mo_id=p.mo_id AND prev.observation_date=date(p.observation_date,'-1 year');