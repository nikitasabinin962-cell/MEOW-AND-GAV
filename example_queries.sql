-- Население и темп изменения
SELECT name,observation_date,value,delta_persons,growth
FROM population_growth ORDER BY name,observation_date;

-- Статус МСП поставщика на snapshot 10.09.2026
SELECT msp_status_asof_snapshot,COUNT(*) AS contracts
FROM contract_msp_asof_20260910 GROUP BY 1;

-- ATMO после удаления только точных повторов внутри API
-- Сумма цен НЕ равна оплатам; межисточниковые дубли ещё не доказаны
SELECT law,COUNT(*) AS unique_api_records,SUM(price_kopecks) AS price_kopecks
FROM atmo_unique_contract_candidates GROUP BY law;

-- Происхождение и результаты проверок импорта
SELECT source_id,original_name,source_url,observation_period,sha256 FROM sources;
SELECT check_name,status,details_json FROM data_quality_checks;
