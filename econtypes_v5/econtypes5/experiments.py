"""Сравнительная кластеризация: постановки × методы × K, ICVI с нулевыми распределениями, устойчивость,
Pareto-фронт и правило выбора. Ни K, ни метод не задаются заранее.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from . import clustering as CL
from . import dynamics as DY
from . import icvi as I
from . import stability as ST

PARETO_CRITERIA = {"SW": "max", "CH": "max", "S_Dbw_floor1": "min", "AVI": "max", "AVU": "min", "MQ_newman": "max", "boot_ari_median": "max"}


def cluster(method: str, k: int, X, W, seed: int, resolution: float | None = None):
    if method == "leiden" and resolution is not None:
        return CL.leiden(W, resolution, seed), dict(resolution=resolution)
    return CL.run(method, k, X=X, W=W, seed=seed)


def boot_ari(method: str, k: int, X, W, final: np.ndarray, info: dict, B: int, frac: float, seed: int) -> tuple[np.ndarray, ST.CoAssignment]:
    n = len(final)
    res = info.get("resolution")

    def fn(idx):
        Xs = None if X is None else X[idx]
        Ws = None if W is None else W[np.ix_(idx, idx)]
        if method == "spectral" and Ws is not None:
            from scipy.sparse.csgraph import connected_components
            return CL.spectral(Ws, k, seed)[0]
        if method == "leiden":
            return CL.leiden(Ws, res if res is not None else 1.0, seed)
        return cluster(method, k, Xs, Ws, seed)[0]

    r = ST.node_bootstrap(fn, n, final, B=B, frac=frac, seed=seed)
    return r["ari"], r["co"]


def sweep(name: str, X: np.ndarray, W: np.ndarray, cfg: dict, seed: int, methods: list[str] | None = None,
          ks: list[int] | None = None, null_B: int | None = None, boot_B: int | None = None) -> tuple[pd.DataFrame, dict]:
    cc = cfg["clustering"]
    methods = methods or (cc["methods_graph"] + cc["methods_attr"])
    ks = ks or cc["k_range"]
    null_B = cc["null_B"] if null_B is None else null_B
    boot_B = cc["bootstrap_B"] if boot_B is None else boot_B
    rows, labels = [], {}
    for m in methods:
        for k in ks:
            if k > len(X) - 1:
                continue
            lab, info = cluster(m, k, X, W, seed)
            kr = len(np.unique(lab))
            labels[(m, k)] = lab
            r = I.all_indices(X, W, lab)
            row = dict(config=name, method=m, k_target=k, k=kr, min_size=int(np.bincount(lab).min()),
                       **{kk: r[kk] for kk in ["SW", "CH", "DB", "S_Dbw", "S_Dbw_floor1", "S_Dbw_undefined_terms", "AVI", "AVU",
                                               "MQ_newman", "MQ_mancoridis", "intra_inter_density_ratio"]},
                       status_S_Dbw=r["_status"]["S_Dbw"], status_AVU=r["_status"]["AVU"], **{f"info_{a}": b for a, b in info.items() if not isinstance(b, (list, dict))})
            if kr >= 2 and null_B:
                nz = I.permutation_null(X, W, lab, B=null_B, seed=seed, indices=["SW", "CH", "S_Dbw_floor1", "AVI", "AVU", "MQ_newman"])
                for kk, v in nz.items():
                    row[f"z_{kk}"] = v["z"]
                    row[f"p_{kk}"] = v["p"]
                row["null_B"] = null_B
            if kr >= 2 and boot_B:
                aris, _ = boot_ari(m, k, X, W, lab, info, boot_B, cfg["clustering"]["bootstrap_frac"], seed)
                row.update(boot_ari_median=float(np.median(aris)), boot_ari_q10=float(np.quantile(aris, 0.1)), boot_B=boot_B)
            rows.append(row)
    df = pd.DataFrame(rows)
    df["exact_k"] = df.k == df.k_target   # Leiden может не достичь целевого K при любом разрешении — строка сохраняется с фактическим K
    return df, labels


def pareto_mask(df: pd.DataFrame, criteria: dict = PARETO_CRITERIA) -> np.ndarray:
    cols = [c for c in criteria if c in df and df[c].notna().any()]
    V = np.column_stack([(df[c] if criteria[c] == "max" else -df[c]).fillna(-np.inf).to_numpy() for c in cols])
    n = len(V)
    mask = np.ones(n, dtype=bool)
    for i in range(n):
        dom = np.all(V >= V[i], axis=1) & np.any(V > V[i], axis=1)
        if dom.any():
            mask[i] = False
    return mask


def select(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Правило выбора (зафиксировано до просмотра меток): среди решений Pareto-фронта с минимальным размером
    кластера ≥ min_cluster_size и медианой бутстреп-ARI ≥ stability_floor — максимум среднего ранга по
    z-оценкам шести индексов (каждый z — против нуля с теми же размерами кластеров). Средний ранг —
    правило агрегации, а не доказательство качества; фронт публикуется целиком."""
    cc = cfg["clustering"]
    d = df.copy()
    d["pareto"] = pareto_mask(d)
    zc = [c for c in d.columns if c.startswith("z_")]
    d["z_rank_mean"] = d[zc].rank(ascending=False).mean(axis=1)
    ok = d[(d.pareto) & (d.min_size >= cc["min_cluster_size"]) & (d.boot_ari_median >= cc["stability_floor"]) & (d.k >= 2)]
    if ok.empty:
        ok = d[(d.min_size >= cc["min_cluster_size"])]
    return ok.sort_values("z_rank_mean").iloc[0]


def cross_evaluate(labelings: dict[str, np.ndarray], X_ref: np.ndarray, W_ref: np.ndarray, ref_name: str) -> pd.DataFrame:
    """Все разбиения в одном общем пространстве (X_ref, W_ref) — ICVI разных постановок напрямую не сравнимы."""
    rows = []
    for name, lab in labelings.items():
        r = I.all_indices(X_ref, W_ref, lab)
        rows.append(dict(labeling=name, reference=ref_name, k=len(np.unique(lab)),
                         **{k: r[k] for k in ["SW", "CH", "S_Dbw_floor1", "AVI", "AVU", "MQ_newman"]}))
    return pd.DataFrame(rows)


def agreement(labelings: dict[str, np.ndarray]) -> pd.DataFrame:
    names = list(labelings)
    rows = []
    for a in names:
        for b in names:
            rows.append(dict(a=a, b=b, ARI=adjusted_rand_score(labelings[a], labelings[b]),
                             VI=DY.variation_of_information(labelings[a], labelings[b])))
    return pd.DataFrame(rows)
