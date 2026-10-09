"""База econtypes v5 (SQLite + экспорт Parquet). Слои:
  L0 source_registry          — неизменяемые источники (путь, SHA-256, байты, период наблюдения, дата публикации/загрузки)
  L1 mo, mo_alias, fact_*      — нормализованные факты с единицами, периодом, статусом и source_id
     contract, org_geo_*       — контракты (копейки, валюта отдельно) и муниципальная привязка с методом/качеством
     msp_firm                  — реестр МСП на дату снимка
  L2 attribute_mo_period       — признаки МО × период × режим (retrospective | monitoring), с покрытием и импутацией
  L3 run, run_*                — результаты конкретного run_id (метки, ICVI, точная W и её визуальная проекция, co-assignment)
Миграции — нумерованные, применяются идемпотентно; версия хранится в schema_migrations.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "initial layered schema", """
    CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT);
    CREATE TABLE IF NOT EXISTS source_registry(
        source_id TEXT PRIMARY KEY, title TEXT, relative_path TEXT, storage_location TEXT, url TEXT, drive_id TEXT,
        sha256 TEXT, size_bytes INTEGER, retrieved_at TEXT, observation_period TEXT, publication_date TEXT,
        territory TEXT, units TEXT, grain TEXT, keys TEXT, license_terms TEXT, completeness TEXT, known_errors TEXT,
        row_count INTEGER, control_totals_json TEXT, role TEXT, status TEXT, limitations TEXT);
    CREATE TABLE IF NOT EXISTS mo(
        mo_id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, kind TEXT CHECK(kind IN ('ГО','МР')),
        oktmo TEXT, oktmo_status TEXT, sber_territory_id INTEGER, sber_mapping_status TEXT,
        boundary_valid_from TEXT, boundary_valid_to TEXT, boundary_note TEXT);
    CREATE TABLE IF NOT EXISTS mo_alias(alias TEXT PRIMARY KEY, mo_id INTEGER NOT NULL REFERENCES mo, source_id TEXT REFERENCES source_registry);
    CREATE TABLE IF NOT EXISTS fact_mo(
        mo_id INTEGER NOT NULL REFERENCES mo, indicator TEXT NOT NULL, period TEXT NOT NULL, value REAL,
        unit TEXT NOT NULL, status TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES source_registry,
        publication_date TEXT, revision TEXT, note TEXT,
        PRIMARY KEY(mo_id, indicator, period, source_id));
    CREATE TABLE IF NOT EXISTS fact_region_control(
        indicator TEXT, period TEXT, value REAL, unit TEXT, source_id TEXT REFERENCES source_registry,
        PRIMARY KEY(indicator, period, source_id));
    CREATE TABLE IF NOT EXISTS contract(
        canonical_contract_id TEXT PRIMARY KEY, law TEXT, contract_number TEXT, budget_level TEXT,
        sign_date TEXT, amount_kopecks INTEGER, currency TEXT, financial_status TEXT, identity_basis TEXT,
        customer_inn TEXT, customer_kpp TEXT, customer_name TEXT, supplier_inn TEXT, supplier_kpp TEXT, supplier_name TEXT,
        subject TEXT, status_variants TEXT, source_file TEXT, upstream_source_id TEXT,
        customer_inn_valid INTEGER, supplier_inn_valid INTEGER, reestr_inn_agrees INTEGER);
    CREATE INDEX IF NOT EXISTS contract_cust_idx ON contract(customer_inn, customer_kpp);
    CREATE INDEX IF NOT EXISTS contract_supp_idx ON contract(supplier_inn);
    CREATE INDEX IF NOT EXISTS contract_date_idx ON contract(sign_date);
    CREATE TABLE IF NOT EXISTS org_geo_evidence(
        inn TEXT NOT NULL, kpp TEXT, role TEXT NOT NULL CHECK(role IN ('customer','supplier')), mo_id INTEGER REFERENCES mo,
        method TEXT NOT NULL, confidence REAL, evidence TEXT, valid_asof TEXT, source_id TEXT,
        PRIMARY KEY(inn, kpp, role, method));
    CREATE TABLE IF NOT EXISTS org_geo_resolved(
        inn TEXT NOT NULL, kpp TEXT, role TEXT NOT NULL, mo_id INTEGER REFERENCES mo, region_code TEXT,
        quality TEXT NOT NULL, methods_agree INTEGER, PRIMARY KEY(inn, kpp, role));
    CREATE TABLE IF NOT EXISTS tax_office_map(
        code TEXT PRIMARY KEY, mo_id INTEGER REFERENCES mo, n_named INTEGER, purity REAL, usable INTEGER, built_from TEXT);
    CREATE TABLE IF NOT EXISTS msp_firm(
        inn TEXT NOT NULL, snapshot_date TEXT NOT NULL, category_code TEXT, okved_main TEXT, okved_section TEXT,
        region_code TEXT, mo_id_candidate INTEGER REFERENCES mo, geo_status TEXT, headcount INTEGER,
        source_id TEXT, PRIMARY KEY(inn, snapshot_date));
    CREATE TABLE IF NOT EXISTS msp_index_firm(
        inn TEXT NOT NULL, snapshot_date TEXT NOT NULL, region_code TEXT, category_raw TEXT, source_id TEXT,
        PRIMARY KEY(inn, snapshot_date));
    CREATE TABLE IF NOT EXISTS attribute_mo_period(
        mo_id INTEGER NOT NULL REFERENCES mo, period TEXT NOT NULL, feature TEXT NOT NULL, mode TEXT NOT NULL,
        value REAL, unit TEXT, block TEXT, transform TEXT, coverage REAL, imputed INTEGER NOT NULL DEFAULT 0,
        source_ids TEXT, observation_window TEXT, available_from TEXT,
        PRIMARY KEY(mo_id, period, feature, mode));
    CREATE TABLE IF NOT EXISTS run(
        run_id TEXT PRIMARY KEY, created_at TEXT, config_hash TEXT, code_hash TEXT, data_hash TEXT, mode TEXT,
        seed INTEGER, note TEXT);
    CREATE TABLE IF NOT EXISTS run_labels(
        run_id TEXT REFERENCES run, config TEXT, period TEXT, mo_id INTEGER REFERENCES mo, label INTEGER,
        PRIMARY KEY(run_id, config, period, mo_id));
    CREATE TABLE IF NOT EXISTS run_icvi(
        run_id TEXT REFERENCES run, config TEXT, period TEXT, method TEXT, k INTEGER, index_name TEXT,
        value REAL, direction TEXT, space TEXT, matrix TEXT, status TEXT,
        PRIMARY KEY(run_id, config, period, method, k, index_name));
    CREATE TABLE IF NOT EXISTS run_matrix_edges(
        run_id TEXT REFERENCES run, matrix TEXT, i INTEGER REFERENCES mo, j INTEGER REFERENCES mo, weight REAL,
        PRIMARY KEY(run_id, matrix, i, j));
    CREATE TABLE IF NOT EXISTS run_coassign(
        run_id TEXT REFERENCES run, scheme TEXT, i INTEGER REFERENCES mo, j INTEGER REFERENCES mo, p REAL, n_joint INTEGER,
        PRIMARY KEY(run_id, scheme, i, j));
    CREATE TABLE IF NOT EXISTS data_quality_checks(
        check_name TEXT PRIMARY KEY, status TEXT CHECK(status IN ('PASS','FAIL','NOT_RUN','INFO')), details_json TEXT, checked_at TEXT);
    """),
    (2, "views", """
    CREATE VIEW IF NOT EXISTS v_contract_customer_mo AS
      SELECT c.*, r.mo_id AS customer_mo_id, r.quality AS customer_geo_quality
      FROM contract c LEFT JOIN org_geo_resolved r ON r.inn = c.customer_inn AND IFNULL(r.kpp,'') = IFNULL(c.customer_kpp,'') AND r.role='customer';
    CREATE VIEW IF NOT EXISTS v_population_growth AS
      SELECT a.mo_id, a.period, a.value, b.value AS prev_value, (a.value - b.value) * 1.0 / b.value AS growth
      FROM fact_mo a JOIN fact_mo b ON a.mo_id=b.mo_id AND a.indicator='population' AND b.indicator='population'
       AND b.period = printf('%04d', CAST(substr(a.period,1,4) AS INTEGER)-1) || substr(a.period,5);
    """),
]


def connect(path: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def migrate(con: sqlite3.Connection) -> list[int]:
    con.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL, description TEXT)")
    done = {r[0] for r in con.execute("SELECT version FROM schema_migrations")}
    applied = []
    for v, desc, sql in MIGRATIONS:
        if v in done:
            continue
        con.executescript(sql)
        con.execute("INSERT INTO schema_migrations VALUES (?,?,?)", (v, datetime.now(timezone.utc).isoformat(timespec="seconds"), desc))
        applied.append(v)
    con.commit()
    return applied


def sha256_file(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def table_digest(con: sqlite3.Connection, table: str, order_by: str) -> str:
    """Детерминированный хеш содержимого таблицы (для проверки идемпотентности ingest)."""
    h = hashlib.sha256()
    for row in con.execute(f"SELECT * FROM {table} ORDER BY {order_by}"):
        h.update(json.dumps(row, ensure_ascii=False, default=str).encode())
    return h.hexdigest()


def check(con, name: str, passed: bool | None, details) -> None:
    status = "NOT_RUN" if passed is None else ("PASS" if passed else "FAIL")
    if isinstance(passed, str):
        status = passed
    con.execute("INSERT OR REPLACE INTO data_quality_checks VALUES (?,?,?,?)",
                (name, status, json.dumps(details, ensure_ascii=False, default=str), datetime.now(timezone.utc).isoformat(timespec="seconds")))


def integrity(con) -> dict:
    ic = con.execute("PRAGMA integrity_check").fetchone()[0]
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    return dict(integrity=ic, foreign_key_violations=len(fk), fk_sample=fk[:5])


def export_parquet(con, tables: list[str], outdir: Path) -> dict:
    import pandas as pd
    outdir.mkdir(parents=True, exist_ok=True)
    res = {}
    for t in tables:
        df = pd.read_sql(f"SELECT * FROM {t}", con)
        p = outdir / f"{t}.parquet"
        df.to_parquet(p, index=False, compression="zstd")
        res[t] = dict(rows=len(df), bytes=p.stat().st_size, sha256=sha256_file(p))
    return res
