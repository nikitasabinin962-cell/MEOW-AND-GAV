"""Хранилище данных проекта: любая база, которую понимает SQLAlchemy.

По умолчанию — файл SQLite (`data/econtypes.db`), ничего ставить не нужно.
PostgreSQL/MySQL — строкой подключения в config.yaml (`database.url`) или флагом `--db`:
    econtypes --db postgresql+psycopg2://user:pass@host/dbname ingest

Таблицы делятся на два слоя:
  raw_*   — очищенные исходные данные (пишет `econtypes ingest`);
  res_*   — результаты расчётов (пишут `run`, `metrics`, `correlate`).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

RAW_TABLES = ["contracts", "positions", "population", "prefix_map", "consumption", "id_map",
              "connection", "market_access", "external", "contracts_holdout", "positions_holdout"]


def engine(url: str):
    if url.startswith("sqlite:///"):
        Path(url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url)


def write(eng, name: str, df: pd.DataFrame, index: bool = False) -> None:
    df = df.copy()
    for c in df.columns:                       # Period и прочие объекты → строки
        if isinstance(df[c].dtype, pd.PeriodDtype):
            df[c] = df[c].astype(str)
    multi = eng.dialect.name != "sqlite"       # SQLite: лимит числа параметров, executemany быстрее
    df.to_sql(name, eng, if_exists="replace", index=index,
              chunksize=max(1, 30000 // max(1, df.shape[1])) if multi else 50000, method="multi" if multi else None)


def read(eng, name: str, **kw) -> pd.DataFrame:
    return pd.read_sql_table(name, eng, **kw)


def tables(eng) -> list[str]:
    return inspect(eng).get_table_names()


def summary(eng) -> pd.DataFrame:
    rows = []
    with eng.connect() as con:
        for t in sorted(tables(eng)):
            n = con.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            rows.append((t, n))
    return pd.DataFrame(rows, columns=["table", "rows"])


def load_raw(eng) -> dict:
    """Собирает словарь исходных данных в том виде, в каком его ждёт пайплайн."""
    r = {k: read(eng, "raw_" + k) for k in RAW_TABLES if "raw_" + k in tables(eng)}
    for k in ("contracts", "contracts_holdout"):
        if k in r:
            r[k]["date"] = pd.to_datetime(r[k]["date"])
            for c in ("customer_inn", "supplier_inn", "contract_id"):
                r[k][c] = r[k][c].astype(str)
    for k in ("positions", "positions_holdout"):
        if k in r:
            r[k]["contract_id"] = r[k]["contract_id"].astype(str)
            r[k]["okpd2_2"] = r[k]["okpd2_2"].astype(str).str.zfill(2)
    r["pop"] = r.pop("population")
    r["prefix_map"]["prefix"] = r["prefix_map"]["prefix"].astype(str).str.zfill(4)
    r["cons"] = r.pop("consumption")
    r["market_access"] = r["market_access"].set_index("mo")["market_access"]
    r["external"] = r["external"].set_index("mo")
    return r
