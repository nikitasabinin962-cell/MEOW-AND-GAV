"""Внешняя проверка: сохраняются ли типы МО в закупках вне периода обучения (2025, 2026 и любые новые годы).

Если кластеры отражают устойчивую экономическую структуру, то по одним только признакам госзаказа
нового года МО должны «узнаваться»: ближайший центроид типа (посчитанный на 2023–2024) совпадает
с присвоенным типом чаще, чем случайно. Запуск: econtypes validate
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

from . import db, features as F


def _panel(c, p, pop, cfg, nodes):
    pp = F.procurement_panel(c, p, pop, cfg["features"]["okpd2_groups"], "Y", True)
    return pp.groupby("mo").mean().reindex(nodes)


def validate(cfg: dict, eng) -> dict:
    out = Path(cfg["paths"]["outputs"])
    raw = db.load_raw(eng)
    cl = db.read(eng, "res_clusters")
    nodes, final = cl.mo.tolist(), cl.cluster.values
    pop = raw["pop"]
    panels = {"train": _panel(raw["contracts"], raw["positions"], pop, cfg, nodes)}
    if "contracts_holdout" in raw:
        hc, hp = raw["contracts_holdout"], raw["positions_holdout"]
        for y in sorted(hc.holdout.unique()):
            c = hc[hc.holdout == y]
            panels[y] = _panel(c, hp[hp.contract_id.isin(set(c.contract_id))], pop, cfg, nodes)
    cols = [c for c in panels["train"].columns if c != "supply_out_pc"]

    def prep(df):
        d = df[cols].fillna(0).copy()
        d["proc_pc"] = np.log(d["proc_pc"].clip(1))
        return d

    A = prep(panels["train"])
    sc = RobustScaler().fit(A)
    XA = np.clip(sc.transform(A), -4, 4)
    ks = np.unique(final)
    cent = np.array([XA[final == k].mean(0) for k in ks])
    nearest = lambda X: ks[np.argmin(((X[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)]
    rng = np.random.default_rng(0)
    null = np.array([float((rng.permutation(final) == final).mean()) for _ in range(5000)])
    res = dict(accuracy_in_sample=float((nearest(XA) == final).mean()), chance_mean=float(null.mean()), holdout={})
    for y in [k for k in panels if k != "train"]:
        B = prep(panels[y])
        acc = float((nearest(np.clip(sc.transform(B), -4, 4)) == final).mean())
        rho = {c: round(float(A[c].rank().corr(B[c].rank())), 3) for c in cols}
        res["holdout"][y] = dict(accuracy=acc, p_value=float(np.mean(null >= acc)), feature_rank_corr=rho)
    json.dump(res, open(out / "validation_holdout.json", "w"), ensure_ascii=False, indent=1)
    return res
