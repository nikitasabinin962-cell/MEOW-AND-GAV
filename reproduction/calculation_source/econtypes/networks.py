"""Построение слоёв сети между МО.

Каждый слой — симметричная матрица сходства W (n×n, диагональ 0, значения в [0, 1]).
  attr        — косинусное сходство векторов атрибутов (структура трат + госзаказ)
  comovement  — корреляция помесячных рядов трат после удаления общего для республики
                фактора (кто «ведёт себя одинаково»)
  lead_lag    — максимальная лаговая корреляция (лаг 1..L мес.) и DTW: кто «опережает»
  dtw         — сходство формы рядов по Dynamic Time Warping
  procurement_flow — реальные потоки госзаказа «поставщик МО i → заказчик МО j»
Разреживание: оставляем k ближайших соседей (симметризация по «или»).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def knn_sparsify(S: np.ndarray, k: int) -> np.ndarray:
    S = S.copy()
    np.fill_diagonal(S, 0)
    n = len(S)
    keep = np.zeros_like(S, dtype=bool)
    idx = np.argsort(-S, axis=1)[:, :k]
    keep[np.repeat(np.arange(n), k), idx.ravel()] = True
    keep = keep | keep.T
    return np.where(keep, S, 0.0)


def _unit(S: np.ndarray) -> np.ndarray:
    S = np.clip(S, 0, None)
    np.fill_diagonal(S, 0)
    m = S.max()
    return S / m if m > 0 else S


def attr_similarity(X: np.ndarray) -> np.ndarray:
    Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    S = Xn @ Xn.T
    return _unit((S + 1) / 2)          # косинус [-1,1] → [0,1]


def residual_series(Y: pd.DataFrame) -> pd.DataFrame:
    """log-траты минус среднее по республике в том же месяце: убирает общую сезонность и инфляцию."""
    L = np.log(Y)
    return L.sub(L.mean(axis=0), axis=1)


def comovement(R: pd.DataFrame) -> np.ndarray:
    D = R.diff(axis=1).iloc[:, 1:]       # помесячные изменения остатков
    C = np.corrcoef(D.values)
    return _unit(np.nan_to_num(C))


def lead_lag(R: pd.DataFrame, max_lag: int) -> tuple[np.ndarray, np.ndarray]:
    """Максимум |лаговой корреляции| и знак лидерства: lag[i,j]>0 — i опережает j."""
    D = R.diff(axis=1).iloc[:, 1:].values
    n, T = D.shape
    best = np.zeros((n, n))
    lag = np.zeros((n, n), dtype=int)
    Z = (D - D.mean(1, keepdims=True)) / (D.std(1, keepdims=True) + 1e-12)
    for l in range(1, max_lag + 1):
        A, B = Z[:, :-l], Z[:, l:]      # i в момент t  vs  j в момент t+l
        C = (A @ B.T) / (T - l)
        upd = C > best
        best[upd] = C[upd]
        lag[upd] = l
    S = np.maximum(best, best.T)
    lead = np.where(best > best.T, lag, -lag.T)
    return _unit(S), lead


def dtw_distance(a: np.ndarray, b: np.ndarray, w: int) -> float:
    n = len(a)
    D = np.full((n + 1, n + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(max(1, i - w), min(n, i + w) + 1):
            c = (a[i - 1] - b[j - 1]) ** 2
            D[i, j] = c + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(np.sqrt(D[n, n]))


def dtw_similarity(R: pd.DataFrame, w: int) -> np.ndarray:
    Z = R.values
    Z = (Z - Z.mean(1, keepdims=True)) / (Z.std(1, keepdims=True) + 1e-12)
    n = len(Z)
    Dm = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            Dm[i, j] = Dm[j, i] = dtw_distance(Z[i], Z[j], w)
    sigma = np.median(Dm[np.triu_indices(n, 1)])
    return _unit(np.exp(-(Dm / sigma) ** 2))


def flow_matrix(fl: pd.DataFrame, nodes: list[str], min_rub: float) -> tuple[np.ndarray, np.ndarray]:
    """Направленная матрица F[i,j] (поставщик i → заказчик j) и нормированная симметричная.

    Нормировка F_ij / sqrt(out_i * in_j) убирает эффект масштаба (иначе Уфа связана со всеми).
    """
    pos = {m: i for i, m in enumerate(nodes)}
    F = np.zeros((len(nodes), len(nodes)))
    g = fl.groupby(["supplier_mo", "customer_mo"])["rub"].sum()
    for (s, c), v in g.items():
        if s in pos and c in pos and s != c and v >= min_rub:
            F[pos[s], pos[c]] += v
    out_ = F.sum(1, keepdims=True)
    in_ = F.sum(0, keepdims=True)
    N = F / np.sqrt(np.maximum(out_, 1) * np.maximum(in_, 1))
    S = N + N.T
    return F, _unit(np.log1p(S * 1e3))


def fuse(attr: np.ndarray, layers: dict[str, np.ndarray], weights: dict[str, float], alpha: float) -> np.ndarray:
    tot = sum(weights.values())
    struct = sum(weights[k] / tot * layers[k] for k in weights)
    return _unit(alpha * attr + (1 - alpha) * _unit(struct))


def road_distance(connection: pd.DataFrame, id_map: pd.DataFrame, nodes: list[str]) -> np.ndarray:
    """Матрица автодорожных расстояний (км) между центрами МО (connection.parquet СберИндекса).
    Для МО без id (ЗАТО Межгорье) — NaN."""
    road = connection[connection.type == "highway"]
    ids = id_map.set_index("mo")["territory_id"]
    pos = {int(ids[m]): i for i, m in enumerate(nodes) if m in ids}
    D = np.full((len(nodes), len(nodes)), np.nan)
    np.fill_diagonal(D, 0)
    r = road[road.territory_id_x.isin(pos) & road.territory_id_y.isin(pos)]
    for x, y, d in zip(r.territory_id_x, r.territory_id_y, r.distance):
        D[pos[x], pos[y]] = D[pos[y], pos[x]] = d
    return D


def distance_similarity(D: np.ndarray) -> np.ndarray:
    """Гауссово ядро по расстоянию: σ — медиана попарных расстояний."""
    sigma = np.nanmedian(D[np.triu_indices(len(D), 1)])
    S = np.exp(-(np.nan_to_num(D, nan=np.inf) / sigma) ** 2)
    return _unit(S)


from . import region as R


def road_map_layout(D: np.ndarray, nodes: list[str], fill_from: dict | None = None) -> np.ndarray:
    """Классическое многомерное шкалирование (MDS) матрицы дорожных расстояний → 2D «карта»,
    повернутая по ориентирам (Прокруст: поворот/отражение/масштаб, без искажения формы)."""
    D = D.copy()
    for tgt, (src, add_km) in (fill_from or {}).items():
        if tgt in nodes and src in nodes:
            i, j = nodes.index(tgt), nodes.index(src)
            D[i, :] = D[j, :] + add_km
            D[:, i] = D[i, :]
            D[i, i] = 0
            D[i, j] = D[j, i] = add_km
    n = len(D)
    D = np.nan_to_num(D, nan=np.nanmean(D))
    J = np.eye(n) - 1 / n
    B = -0.5 * J @ (D ** 2) @ J
    w, V = np.linalg.eigh(B)
    idx = np.argsort(w)[::-1][:2]
    Y = V[:, idx] * np.sqrt(np.maximum(w[idx], 0))
    a = [nodes.index(m) for m in R.ORIENT_ANCHORS if m in nodes]
    if len(a) < 2:                      # ориентиры не заданы — раскладка без поворота
        return Y
    T = np.array([[R.ORIENT_ANCHORS[nodes[i]][1] * np.cos(np.radians(R.MID_LAT)), R.ORIENT_ANCHORS[nodes[i]][0]] for i in a])
    Ya = Y[a] - Y[a].mean(0)
    Ta = T - T.mean(0)
    U, S, Vt = np.linalg.svd(Ya.T @ Ta)
    Rot = U @ Vt
    s = S.sum() / (Ya ** 2).sum()
    return (Y - Y[a].mean(0)) @ Rot * s + T.mean(0)   # x ~ долгота·cos(φ), y ~ широта
