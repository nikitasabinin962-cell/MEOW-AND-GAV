"""Сборка всех промежуточных объектов из сырых данных (общая для статического и динамического анализа)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer
from sklearn.preprocessing import RobustScaler, StandardScaler

from . import eis, external as E, features as F, mo_directory as md

SBER_COLS_PREFIX = ("spend_total", "sh_", "market_access")


def load_all(cfg: dict) -> dict:
    d = cfg["data"]
    contracts, positions = eis.load(d["eis_files"])
    pop = md.load_population(d["population"])
    mos = pop.mo.tolist()
    cust = contracts[["customer_inn", "customer_name"]].rename(columns={"customer_inn": "inn", "customer_name": "name"}).drop_duplicates("inn")
    prefix_map = md.build_prefix_map(cust, mos)
    cons = pd.read_parquet(d["consumption"])
    connection = pd.read_parquet(d["connection"])
    id_map = md.match_sber_ids(cons, pd.read_parquet(d["sber_spending"]), connection, mos)
    ma = pd.read_parquet(d["market_access"]).merge(id_map, on="territory_id").set_index("mo")["market_access"]
    contracts = F.attach_mo(contracts, prefix_map)
    contracts = contracts[(contracts.date >= d["period_start"]) & (contracts.date <= d["period_end"])]
    ext = E.load_external(cfg, pop)
    return dict(contracts=contracts, positions=positions, pop=pop, prefix_map=prefix_map,
                cons=cons, id_map=id_map, connection=connection, market_access=ma, external=ext)


def panel(cfg: dict, raw: dict, freq: str) -> pd.DataFrame:
    fc = cfg["features"]
    sp = F.sber_panel(raw["cons"], raw["id_map"], fc["spending_categories"], freq)
    pp = F.procurement_panel(raw["contracts"], raw["positions"], raw["pop"], fc["okpd2_groups"], freq,
                             cfg["data"]["exclude_republican_customers_from_ufa"])
    panel = F.build_panel(sp, pp, raw["pop"], raw["market_access"])
    return panel.join(raw["external"], on="mo")


def design_matrix(tab: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """Агрегированная таблица МО × признаки → (сырые признаки, флаг импутации, масштабированная X)."""
    t = tab.copy()
    sber_cols = [c for c in t.columns if c.startswith(SBER_COLS_PREFIX)]
    imputed = t[sber_cols].isna().any(axis=1)
    for c in cfg["features"]["log_transform"]:
        t[c] = np.log(t[c].clip(lower=1))
    t["supply_out_pc"] = np.log1p(t["supply_out_pc"])
    t = t.fillna({c: 0 for c in t.columns if c.startswith("okpd_") or c.startswith("proc_")})
    # МО без надёжных данных СберИндекса (склейка одноимённых МО / ЗАТО): KNN-импутация по остальным признакам
    t[:] = KNNImputer(n_neighbors=5).fit_transform(t)
    sc = RobustScaler() if cfg["features"]["scaler"] == "robust" else StandardScaler()
    X = sc.fit_transform(t)
    X = np.clip(X, -4, 4)                  # ограничиваем влияние выбросов (Уфа, Межгорье)
    return t, imputed, X
