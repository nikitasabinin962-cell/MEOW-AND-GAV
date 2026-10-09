"""Слои сети по помесячным рядам трат СберИндекса — только по данным до конца окна.

Отличия от v4 (networks.residual_series/comovement/lead_lag/dtw_similarity):
  * ряды обрезаются по ``end`` (включительно) до любых вычислений → слой окна t не зависит
    от месяцев после t (проверяется тестом изменения будущего);
  * log(0) не вычисляется: нулевые/отрицательные траты → NaN в ряду, статус 'nonpositive';
  * постоянный ряд (σ = 0) не получает связей: строка слоя = 0, статус 'constant';
  * МО с недостаточным числом наблюдений (< min_obs) исключаются из слоя (статус 'too_short');
  * корреляции считаются по попарно общим месяцам; NaN не превращается в 0 «сходства».
Все статусы возвращаются вызывающему коду.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def restrict(Y: pd.DataFrame, end: str | None = None, start: str | None = None) -> pd.DataFrame:
    cols = [c for c in Y.columns if (end is None or str(c) <= end) and (start is None or str(c) >= start)]
    return Y[cols]


def residual_series(Y: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """log-траты минус кросс-секционное среднее того же месяца (по МО с наблюдением)."""
    Yv = Y.astype(float)
    nonpos = (Yv <= 0)
    status = {m: "nonpositive_values" for m in Y.index[nonpos.any(axis=1)]}
    L = np.log(Yv.where(Yv > 0))
    return L.sub(L.mean(axis=0, skipna=True), axis=1), status


def _corr_pairwise(D: np.ndarray, min_obs: int) -> np.ndarray:
    n = len(D)
    C = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(i + 1, n):
            m = np.isfinite(D[i]) & np.isfinite(D[j])
            if m.sum() < min_obs:
                continue
            a, b = D[i, m], D[j, m]
            sa, sb = a.std(), b.std()
            if sa == 0 or sb == 0:
                continue
            # округление может дать |r| чуть больше 1
            C[i, j] = C[j, i] = float(np.clip(np.mean((a - a.mean()) * (b - b.mean())) / (sa * sb), -1, 1))
    return C


def layer_status(R: pd.DataFrame, min_obs: int) -> dict:
    st = {}
    for m, row in R.iterrows():
        v = row.to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        if len(v) < min_obs:
            st[m] = "too_short"
        elif np.allclose(v, v[0]):
            st[m] = "constant"
    return st


def comovement(R: pd.DataFrame, min_obs: int = 6) -> tuple[np.ndarray, dict]:
    """Корреляция помесячных приращений остатков; отрицательные корреляции → 0 (не сходство)."""
    D = R.diff(axis=1).iloc[:, 1:].to_numpy(dtype=float)
    C = _corr_pairwise(D, min_obs)
    S = np.where(np.isfinite(C), np.clip(C, 0, None), 0.0)
    np.fill_diagonal(S, 0)
    st = layer_status(R.diff(axis=1).iloc[:, 1:], min_obs)
    return S, dict(node_status=st, months=R.shape[1], undefined_pairs=int(np.isnan(C[np.triu_indices(len(C), 1)]).sum()))


def lead_lag(R: pd.DataFrame, max_lag: int = 3, min_obs: int = 6, tol: float = 1e-9) -> tuple[np.ndarray, np.ndarray, dict]:
    """max_{1≤l≤L} corr(Δr_i(t), Δr_j(t+l)) — разведочная связь со сдвигом, не причинность.

    r[i,j] — лучший Pearson r, когда ряд i идёт раньше j; lag[i,j] — этот сдвиг; n_overlap[i,j] — число
    общих наблюдений при нём. Вес слоя S = max(r_ij, r_ji, 0) симметричный.
    Направление lead[i,j] > 0 (i раньше j на lead мес.) ставится только при однозначном максимуме:
    r > 0, лучший сдвиг единственный и r_ij строго больше r_ji. Иначе lead = 0 — стрелку не рисуем.
    """
    D = R.diff(axis=1).iloc[:, 1:].to_numpy(dtype=float)
    n, T = D.shape
    best = np.full((n, n), np.nan)
    lag = np.zeros((n, n), dtype=int)
    nobs = np.zeros((n, n), dtype=int)
    tie = np.zeros((n, n), dtype=bool)
    for l in range(1, max_lag + 1):
        if T - l < min_obs:
            break
        A, B = D[:, :-l], D[:, l:]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                m = np.isfinite(A[i]) & np.isfinite(B[j])
                if m.sum() < min_obs:
                    continue
                a, b = A[i, m], B[j, m]
                if a.std() == 0 or b.std() == 0:
                    continue
                c = float(np.clip(np.corrcoef(a, b)[0, 1], -1, 1))
                if not np.isfinite(best[i, j]) or c > best[i, j] + tol:
                    best[i, j], lag[i, j], nobs[i, j], tie[i, j] = c, l, int(m.sum()), False
                elif abs(c - best[i, j]) <= tol:
                    tie[i, j] = True
    b0 = np.nan_to_num(best, nan=-np.inf)
    S = np.maximum(b0, b0.T)
    S = np.where(np.isfinite(S), np.clip(S, 0, None), 0.0)
    np.fill_diagonal(S, 0)
    fwd = (b0 > b0.T + tol) & (b0 > 0) & ~tie
    bwd = (b0.T > b0 + tol) & (b0.T > 0) & ~tie.T
    lead = np.where(fwd, lag, np.where(bwd, -lag.T, 0))
    np.fill_diagonal(lead, 0)
    iu = np.triu_indices(n, 1)
    pair_def = np.isfinite(best)[iu] | np.isfinite(best.T)[iu]
    no_dir = int((pair_def & (lead[iu] == 0)).sum())
    return S, lead, dict(max_lag=max_lag, months=T + 1, r=best, lag=lag, n_overlap=nobs,
                         pairs_defined=int(pair_def.sum()), pairs_without_direction=no_dir,
                         status="exploratory_no_fdr")


def dtw_distance(a: np.ndarray, b: np.ndarray, w: int) -> float:
    n, m = len(a), len(b)
    w = max(w, abs(n - m))
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0
    for i in range(1, n + 1):
        for j in range(max(1, i - w), min(m, i + w) + 1):
            c = (a[i - 1] - b[j - 1]) ** 2
            D[i, j] = c + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(np.sqrt(D[n, m]))


def dtw_similarity(R: pd.DataFrame, w: int = 2, min_obs: int = 6) -> tuple[np.ndarray, dict]:
    """DTW по z-нормированным остаткам на попарно общем окне календаря.

    Пара сравнивается по месяцам, где наблюдены оба ряда, и только если эти месяцы идут подряд.
    Выбрасывать пропуски внутри ряда нельзя: это сжимает календарь, и DTW сопоставляет месяцы,
    которые на деле далеко друг от друга. Такие пары получают NaN (не 0 сходства) и
    считаются в gap_pairs. σ-ядро — медиана положительных расстояний; если все расстояния 0,
    слой пуст, статус 'degenerate'."""
    st = layer_status(R, min_obs)
    V = R.to_numpy(dtype=float)
    skip = [m in st for m in R.index]
    n = len(V)
    Dm = np.full((n, n), np.nan)
    np.fill_diagonal(Dm, 0)
    gap_pairs = short_pairs = 0
    for i in range(n):
        if skip[i]:
            continue
        for j in range(i + 1, n):
            if skip[j]:
                continue
            idx = np.flatnonzero(np.isfinite(V[i]) & np.isfinite(V[j]))
            if len(idx) < min_obs:
                short_pairs += 1
                continue
            if idx[-1] - idx[0] + 1 != len(idx):
                gap_pairs += 1
                continue
            a, b = V[i, idx], V[j, idx]
            if a.std() == 0 or b.std() == 0:
                short_pairs += 1
                continue
            Dm[i, j] = Dm[j, i] = dtw_distance((a - a.mean()) / a.std(), (b - b.mean()) / b.std(), w)
    vals = Dm[np.triu_indices(n, 1)]
    pos = vals[np.isfinite(vals) & (vals > 0)]
    base = dict(node_status=st, gap_pairs=gap_pairs, short_pairs=short_pairs, window=w, D=Dm)
    if len(pos) == 0:
        return np.zeros((n, n)), dict(base, status="degenerate_no_positive_distance")
    sigma = float(np.median(pos))
    S = np.where(np.isfinite(Dm), np.exp(-(Dm / sigma) ** 2), 0.0)
    np.fill_diagonal(S, 0)
    return S, dict(base, status="ok", sigma=sigma)
