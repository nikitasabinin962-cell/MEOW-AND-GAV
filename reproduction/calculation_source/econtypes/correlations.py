"""Поиск корреляционных связей:  econtypes correlate

1. Ранговые корреляции Спирмена между всеми признаками и индексами (по МО), p-value
   и поправка Бенджамини–Хохберга на множественные сравнения (FDR).
2. Частные корреляции при контроле размера и урбанизации (log_pop, urban_share): связь,
   которая остаётся после исключения эффекта «большой город — всё больше».
3. Лаговая кросс-корреляция помесячных рядов: опережают ли закупки трат населения (и наоборот).
4. Связи между индексами и принадлежностью к типу (Краскел–Уоллис): какие индексы различают типы.

Результаты: таблицы res_correlations, res_partial_corr, res_lag_corr, res_type_tests и
outputs/tables/*.csv, тепловая карта outputs/figures/correlations.png.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from . import db, features as F, region as R

CONTROLS = ["log_pop", "urban_share"]


def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = p[o] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n); out[o] = np.minimum(q, 1)
    return out


def _table(eng) -> pd.DataFrame:
    tab = db.read(eng, "res_features").set_index("mo")
    met = db.read(eng, "res_metrics").set_index("mo")
    keep = [c for c in met.columns if not c.endswith("_pct") and met[c].dtype.kind in "fi"
            and c not in ("cluster", "bootstrap_stability")]
    return tab.join(met[keep].add_prefix("m_"))


def spearman(T: pd.DataFrame, min_n: int = 15) -> pd.DataFrame:
    cols, rows = list(T.columns), []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            d = T[[a, b]].dropna()
            if len(d) < min_n or d[a].nunique() < 3 or d[b].nunique() < 3:
                continue
            r, p = stats.spearmanr(d[a], d[b])
            rows.append(dict(x=a, y=b, rho=r, p=p, n=len(d)))
    r = pd.DataFrame(rows)
    r["q_fdr"] = bh(r.p.values)
    return r.sort_values("p")


def partial(T: pd.DataFrame, pairs: pd.DataFrame, controls=CONTROLS) -> pd.DataFrame:
    """Частная ранговая корреляция: ранги x и y очищаются регрессией на ранги контролей."""
    rows = []
    for x, y in pairs[["x", "y"]].itertuples(index=False):
        if x in controls or y in controls:
            continue
        d = T[[x, y] + controls].dropna().rank()
        if len(d) < 15:
            continue
        Z = np.c_[np.ones(len(d)), d[controls].values]
        res = lambda v: v - Z @ np.linalg.lstsq(Z, v, rcond=None)[0]
        r, p = stats.pearsonr(res(d[x].values), res(d[y].values))
        rows.append(dict(x=x, y=y, partial_rho=r, p=p, n=len(d)))
    r = pd.DataFrame(rows)
    if len(r):
        r["q_fdr"] = bh(r.p.values)
    return r


def lag_corr(cfg: dict, raw: dict, nodes: list[str], max_lag: int = 3) -> pd.DataFrame:
    """Для каждого МО: корреляция приростов log(закупки) и log(траты) при сдвиге −L…+L месяцев.
    lag > 0: закупки ведут (изменение госзаказа предшествует изменению трат)."""
    pm = F.procurement_panel(raw["contracts"], raw["positions"], raw["pop"], cfg["features"]["okpd2_groups"], "M",
                             cfg["data"]["exclude_republican_customers_from_ufa"])["proc_pc"].unstack()
    pm.columns = pm.columns.astype(str)
    sm = F.sber_monthly(raw["cons"], raw["id_map"])
    sm.columns = [str(pd.Period(c, "M")) for c in sm.columns]
    common = sorted(set(pm.columns) & set(sm.columns))
    rows = []
    for mo in nodes:
        if mo not in pm.index or mo not in sm.index:
            continue
        a = np.log(pm.loc[mo, common].astype(float).clip(lower=1)).diff().values[1:]
        b = np.log(sm.loc[mo, common].astype(float).clip(lower=1)).diff().values[1:]
        for L in range(-max_lag, max_lag + 1):
            x, y = (a[:-L], b[L:]) if L > 0 else ((a[-L:], b[:len(b) + L]) if L < 0 else (a, b))
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() >= 10:
                rows.append(dict(mo=mo, lag=L, r=stats.pearsonr(x[ok], y[ok])[0], n=int(ok.sum())))
    return pd.DataFrame(rows)


def type_tests(T: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
    rows = []
    for c in T.columns:
        d = T[c].dropna()
        groups = [d[labels.reindex(d.index) == k].values for k in labels.unique()]
        groups = [g for g in groups if len(g) >= 2]
        if len(groups) >= 2 and d.nunique() > 2:
            h, p = stats.kruskal(*groups)
            eps2 = (h - len(groups) + 1) / (len(d) - len(groups))   # размер эффекта ε²
            rows.append(dict(variable=c, H=h, p=p, epsilon2=eps2))
    r = pd.DataFrame(rows)
    r["q_fdr"] = bh(r.p.values)
    return r.sort_values("epsilon2", ascending=False)


def run(cfg: dict, eng) -> dict:
    out = Path(cfg["paths"]["outputs"]); (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    T = _table(eng)
    S = spearman(T)
    sig = S[S.q_fdr < 0.05]
    Pc = partial(T, sig)
    cl = db.read(eng, "res_clusters").set_index("mo")
    raw = db.load_raw(eng)
    L = lag_corr(cfg, raw, list(T.index), cfg["network"]["max_lag"])
    Lagg = L.groupby("lag").r.agg(["median", "mean", lambda s: (s > 0).mean()]).rename(columns={"<lambda_0>": "share_pos"}).reset_index()
    best = L.loc[L.groupby("mo").r.apply(lambda s: s.abs().idxmax())] if len(L) else L
    TT = type_tests(T, cl.cluster)
    for name, df in {"correlations": S, "partial_corr": Pc, "lag_corr": L, "lag_corr_summary": Lagg,
                     "lag_corr_best": best, "type_tests": TT}.items():
        df.to_csv(out / f"tables/{name}.csv", index=False)
        db.write(eng, "res_" + name, df)
    _heatmap(T, out / "figures/correlations.png")
    return dict(n_pairs=len(S), n_sig=len(sig), n_partial_sig=int((Pc.q_fdr < 0.05).sum()) if len(Pc) else 0,
                lag_summary=Lagg.round(3).to_dict(orient="records"))


def _heatmap(T: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C = T.corr(method="spearman")
    fig, ax = plt.subplots(figsize=(14, 12))
    im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(C))); ax.set_xticklabels(C.columns, rotation=90, fontsize=7)
    ax.set_yticks(range(len(C))); ax.set_yticklabels(C.index, fontsize=7)
    fig.colorbar(im, shrink=0.6, label="ρ Спирмена")
    ax.set_title(f"Ранговые корреляции признаков и индексов (МО: {R.NAME})")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
