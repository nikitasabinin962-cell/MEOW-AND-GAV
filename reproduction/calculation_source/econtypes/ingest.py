"""Загрузка исходных файлов в базу данных.

    econtypes ingest                     — все источники из config.yaml → таблицы raw_*
    econtypes add-eis <папка> <год>      — новая выгрузка ЕИС (CSV из поиска контрактов) → parquet + запись в config

Сюда стекаются разнородные форматы (CSV ЕИС в cp1251, parquet СберИндекса, PDF Башкортостанстата,
DOCX законов о бюджете, HTML/Word паспорта БД ПМО), а в базу ложатся единообразные таблицы.
"""
from __future__ import annotations

import glob
import math
import re
from collections import Counter

import pandas as pd

from . import db, eis, features as F, prepare as P


def ingest(cfg: dict, eng) -> pd.DataFrame:
    raw = P.load_all(cfg)
    ids = set(raw["id_map"].territory_id)
    cons = raw["cons"][raw["cons"].territory_id.isin(ids)]
    con = raw["connection"]
    con = con[con.territory_id_x.isin(ids) & con.territory_id_y.isin(ids)]
    keep = set(raw["contracts"].contract_id)
    db.write(eng, "raw_contracts", raw["contracts"])
    db.write(eng, "raw_positions", raw["positions"][raw["positions"].contract_id.isin(keep)])
    db.write(eng, "raw_population", raw["pop"])
    db.write(eng, "raw_prefix_map", raw["prefix_map"])
    db.write(eng, "raw_consumption", cons)
    db.write(eng, "raw_id_map", raw["id_map"])
    db.write(eng, "raw_connection", con)
    db.write(eng, "raw_market_access", raw["market_access"].rename("market_access").reset_index())
    db.write(eng, "raw_external", raw["external"].rename_axis("mo").reset_index())
    # закупки вне периода обучения — для внешней проверки
    hold = cfg["data"].get("eis_holdout", {})
    if hold:
        hc, hp = [], []
        for year, path in hold.items():
            c, p = eis.load([path])
            c = F.attach_mo(c, raw["prefix_map"])
            c["holdout"] = str(year)
            hc.append(c)
            hp.append(p[p.contract_id.isin(set(c.contract_id))])
        db.write(eng, "raw_contracts_holdout", pd.concat(hc))
        db.write(eng, "raw_positions_holdout", pd.concat(hp))
    return db.summary(eng)


def merge_eis_folder(folder: str, out_parquet: str) -> pd.DataFrame:
    """Склейка CSV из поиска контрактов ЕИС с отчётом о пропущенных страницах."""
    fs = glob.glob(folder + "/**/*ContractSearch*.csv", recursive=True)
    if not fs:
        raise FileNotFoundError(f"в {folder} нет файлов ContractSearch*.csv")
    df = pd.concat([pd.read_csv(f, sep=";", encoding="cp1251", dtype=str) for f in fs]).drop_duplicates()
    df.to_parquet(out_parquet, compression="zstd")
    pages = [tuple(map(int, m.groups())) for f in fs if (m := re.search(r"ContractSearch\(?(\d+)-(\d+)", f))]
    ends = [b for a, b in pages if b % 500]
    have = Counter(a for a, b in pages)
    missing = {f"{s}-{s + 499}": sum(1 for x in ends if x >= s) - have[s] for s in sorted(have)
               if sum(1 for x in ends if x >= s) > have[s]}
    k = df.drop_duplicates("Номер реестровой записи контракта")
    months = pd.to_datetime(k["Контракт: дата"], dayfirst=True, errors="coerce").dt.to_period("M").value_counts().sort_index()
    print(f"файлов {len(fs)}, контрактов {len(k)}; запросов {len(ends)}, страниц ожидается ≥ "
          f"{sum(math.ceil(x / 500) for x in ends)}, есть {len(pages)}")
    if missing:
        print("не хватает страниц:", missing)
    return months.rename("контрактов").to_frame()
