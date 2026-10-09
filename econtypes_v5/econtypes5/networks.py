"""Матрицы признаков и сетей для четырёх постановок сравнения (v4-признаки/граф × v5-признаки/граф).

Экономический смысл слоёв:
  attr         — сходство профилей МО (кто похож по структуре экономики);
  comovement   — синхронность помесячных изменений относительных трат (общие шоки спроса);
  lead_lag     — максимальная лаговая корреляция приращений (распространение изменений с запаздыванием);
  dtw          — сходство формы рядов трат с допуском сдвига (сезонные/циклические профили);
  procurement_flow — нормированные денежные потоки госзаказа «поставщик МО i → заказчик МО j»
                     (география по методам org_geo_resolved, качество фиксируется);
  distance     — НЕ входит в модель: отдельный контрольный слой (в v5 геометрия МО из D.json).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.impute import KNNImputer
from sklearn.preprocessing import RobustScaler

from . import features as F
from . import graphs as G
from . import timeseries as TS

ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT.parent / "reproduction" / "calculation_source"
V4_WEIGHTS = {"comovement": 0.35, "lead_lag": 0.10, "dtw": 0.15, "procurement_flow": 0.40}


# ------------------------------------------------------------------ признаки
def x_old(d: F.Data, nodes: list[int]) -> tuple[np.ndarray, list[str]]:
    """32 архивных признака v4 с преобразованиями v4 (log, log1p, нули в закупках, KNN-импутация,
    RobustScaler, клиппинг ±4) — воспроизведение «прежних признаков» на тех же узлах."""
    cols = [c for c in d.v4.columns]
    t = d.v4.loc[nodes, cols].copy()
    t.columns = [c[3:] for c in cols]
    for c in ["proc_pc", "spend_total"]:
        t[c] = np.log(t[c].clip(lower=1))
    t["supply_out_pc"] = np.log1p(t["supply_out_pc"])
    t = t.fillna({c: 0 for c in t.columns if c.startswith(("okpd_", "proc_"))})
    X = np.clip(RobustScaler().fit_transform(KNNImputer(n_neighbors=5).fit_transform(t)), -4, 4)
    return X, list(t.columns)


# Преобразования перед стандартизацией: HHI — лог-шкала отношения; закупки 223-ФЗ нуль-инфлированы
# (4 МО без заказчиков 223-ФЗ за 2023–2024) → ранговое нормальное преобразование (ties = средний ранг).
TRANSFORM = {"supplier_hhi": "log", "proc223_pc_log": "rank_normal"}


def transform(df: pd.DataFrame) -> pd.DataFrame:
    from scipy.stats import norm, rankdata
    out = df.copy()
    for c, t in TRANSFORM.items():
        if c not in out:
            continue
        v = out[c]
        if t == "log":
            out[c] = np.log(v.where(v > 0))
        elif t == "rank_normal":
            m = v.notna()
            r = rankdata(v[m].to_numpy(), method="average")
            out.loc[m, c] = norm.ppf((r - 0.5) / m.sum())
    return out


def robust_z(df: pd.DataFrame) -> pd.DataFrame:
    med = df.median()
    iqr = (df.quantile(0.75) - df.quantile(0.25)).replace(0, np.nan)
    z = (df - med) / (iqr / 1.349)
    return z.clip(-4, 4)


def x_new(panel: pd.DataFrame, nodes: list[int], period: str, mode: str, blocks: list[str] | None = None,
          block_weights: dict | None = None) -> tuple[np.ndarray, list[str], dict]:
    """Блочная матрица v5: робастная стандартизация координат, вес блока λ_b = 1/p_b (каждый блок
    вносит средний квадрат разности своих координат), X = [√λ_b z_b] — евклидово расстояние по X равно
    блочному расстоянию. Блок, отсутствующий у всех узлов в данном режиме/окне, исключается; если блок
    отсутствует у части узлов — эти узлы исключаются из окна (возвращается список)."""
    blocks = blocks or list(F.BLOCKS)
    cols, mats, used = [], [], []
    wide = F.wide(panel, period, mode, sum((F.BLOCKS[b] for b in blocks), []))
    wide = wide.reindex(nodes)
    info = dict(dropped_blocks=[], dropped_columns=[], nodes_missing={})
    for b in blocks:
        fb = [c for c in F.BLOCKS[b] if not wide[c].isna().all()]   # показатель недоступен в этом окне/режиме
        info["dropped_columns"] += [c for c in F.BLOCKS[b] if c not in fb]
        if not fb:
            info["dropped_blocks"].append(b)
            continue
        sub = transform(wide[fb])
        miss = sub.index[sub.isna().any(axis=1)].tolist()
        if miss:
            info["nodes_missing"][b] = miss
        lam = (block_weights or {}).get(b, 1.0) / len(fb)
        z = robust_z(sub) * np.sqrt(lam)
        mats.append(z)
        cols += fb
        used.append(b)
    Z = pd.concat(mats, axis=1)
    info["blocks"] = used
    return Z.to_numpy(dtype=float), cols, info


# ------------------------------------------------------------------ структурные слои
def struct_layers_new(d: F.Data, nodes: list[int], months: list[str], quarters: list[str], cfg: dict,
                      geo: tuple = F.CUSTOMER_GEO_INCLUSIVE) -> tuple[dict, dict]:
    Y = d.spend.loc[nodes, months]
    R, st = TS.residual_series(Y)
    info = dict(nonpositive=st, months=len(months))
    lay = {}
    lay["comovement"], i1 = TS.comovement(R, cfg["min_obs"])
    lay["lead_lag"], lead, i2 = TS.lead_lag(R, cfg["max_lag"], cfg["min_obs"])
    lay["dtw"], i3 = TS.dtw_similarity(R, cfg["dtw_window"], cfg["min_obs"])
    info.update(comovement=i1["undefined_pairs"], dtw=i3["status"], dtw_gap_pairs=i3["gap_pairs"],
                lag_pairs_without_direction=i2["pairs_without_direction"],
                node_status={**i1["node_status"], **i3["node_status"]})
    lay["procurement_flow"], finfo = flow_layer(d, nodes, quarters, cfg["flow_min_rub"], geo)
    info["flow"] = finfo
    info["lead"] = lead
    return lay, info


def flow_layer(d: F.Data, nodes: list[int], quarters: list[str], min_rub: float, geo: tuple) -> tuple[np.ndarray, dict]:
    c = d.contracts
    c = c[c.quarter.isin(quarters) & (c.currency == "RUB") & (c.financial_status == "known") & c.cq.isin(geo)
          & c.smo.notna() & (c.sreg == "02")]
    c = c[~((c.cmo == d.ufa) & c.budget_level.isin(["1", "2"]))]
    pos = {m: i for i, m in enumerate(nodes)}
    g = c.groupby(["smo", "cmo"]).rub.sum()
    Fm = np.zeros((len(nodes), len(nodes)))
    for (s, t), v in g.items():
        s, t = int(s), int(t)
        if s in pos and t in pos and s != t and v >= min_rub:
            Fm[pos[s], pos[t]] += v
    out_, in_ = Fm.sum(1, keepdims=True), Fm.sum(0, keepdims=True)
    Nm = Fm / np.sqrt(np.maximum(out_, 1) * np.maximum(in_, 1))
    S = G.unit_max(np.log1p((Nm + Nm.T) * 1e3))
    q = c.groupby("sq").rub.sum()
    return S, dict(rub_between_mo=float(Fm.sum()), pairs=int((Fm > 0).sum()), supplier_geo_quality_rub=q.round(0).to_dict())


def struct_layers_old(nodes_names: list[str]) -> dict:
    """Слои v4 из архивного network_edges.csv (после kNN v4, веса округлены до 4 знаков)."""
    e = pd.read_csv(REPRO / "outputs/tables/network_edges.csv")
    idx = {m: i for i, m in enumerate(nodes_names)}
    out = {}
    for key in V4_WEIGHTS:
        A = np.zeros((len(nodes_names), len(nodes_names)))
        for r in e[e.layer == key].itertuples():
            if r.source in idx and r.target in idx:
                A[idx[r.source], idx[r.target]] = A[idx[r.target], idx[r.source]] = r.weight
        out[key] = A
    return out


def attr_old_rule(X: np.ndarray, k: int) -> np.ndarray:
    return G.cosine_knn(X, k)


def attr_new_rule(X: np.ndarray, k: int, k_scale: int, mode: str = "union") -> tuple[np.ndarray, dict]:
    D = np.sqrt(G.pairwise_sq_dist(X))
    return G.self_tuning_affinity(D, k, k_scale, mode)


def fuse_graph(attr: np.ndarray, struct: dict, k: int, alpha: float, weights: dict = V4_WEIGHTS, sparsify_struct: bool = True) -> np.ndarray:
    lay = {}
    for name, S in struct.items():
        if sparsify_struct:
            D = 1 - G.unit_max(S)
            np.fill_diagonal(D, 0)
            M = G.knn_mask(np.where(S > 0, D, np.nan), min(k, len(S) - 1), "union")
            lay[name] = np.where(M, S, 0.0)
        else:
            lay[name] = S
    return G.fuse(attr, lay, weights, alpha)


def display_projection(W: np.ndarray, k: int = 4) -> np.ndarray:
    """Визуальная проекция точной W (union-kNN k=4) — только для показа; ICVI по ней не считаются."""
    D = 1 - G.unit_max(W)
    np.fill_diagonal(D, 0)
    M = G.knn_mask(np.where(W > 0, D, np.nan), k, "union")
    return np.where(M, W, 0.0)


def spatial_weights(nodes_names: list[str]) -> np.ndarray:
    """Смежность полигонов МО (queen: общая граница или вершина) по геометрии D.json v4."""
    from shapely.geometry import shape
    D = json.loads((ROOT.parent / "reproduction/source/src/data/D.json").read_text())
    geo = {f["properties"]["mo"]: shape(f["geometry"]).buffer(0) for f in D["geo"]["features"]}
    n = len(nodes_names)
    Wsp = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            a, b = geo.get(nodes_names[i]), geo.get(nodes_names[j])
            if a is not None and b is not None and a.buffer(1e-4).intersects(b):
                Wsp[i, j] = Wsp[j, i] = 1
    return Wsp


def load_config(path: Path | None = None) -> dict:
    return yaml.safe_load(open(path or ROOT / "config" / "config_v5.yaml"))
