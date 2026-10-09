"""Построение рёбер между МО и диагностика графов.

Правила (каждое проверяется в коде, без молчаливых подстановок):
  * k для kNN — целое 0 ≤ k ≤ N−1. k = 0 даёт пустой граф; k > N−1 — ValueError с объяснением.
  * Диагональ всегда 0. Отсутствующее расстояние (NaN) → ребро невозможно (маска False).
  * Self-tuning affinity (Zelnik-Manor & Perona 2004, NeurIPS 17):
        W_ij = M_ij · exp(−d_ij² / (σ_i σ_j)),  σ_i = расстояние до k_scale-го соседа (без самого узла).
    Если σ_i = 0 (у узла ≥ k_scale точных дубликатов), σ_i заменяется наименьшим положительным
    расстоянием от i (флаг 'sigma_fallback'); если таких нет (все строки совпадают) — граф не определён.
  * M_ij — union-kNN (j∈N_k(i) или i∈N_k(j)) или mutual-kNN (оба условия).
  * Блочное расстояние с пропусками: d_ij² = (Σ_b λ_b) · Σ_b λ_b o_ib o_jb ‖z_i^b − z_j^b‖² / Σ_b λ_b o_ib o_jb,
    где o_ib = 1, если блок b наблюдается у i. Пара без общих наблюдаемых блоков получает NaN.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse.csgraph import connected_components


def _check_k(k, n: int, what: str = "k") -> int:
    if not isinstance(k, (int, np.integer)) or isinstance(k, bool):
        raise ValueError(f"{what} должно быть целым, получено {k!r}")
    if k < 0:
        raise ValueError(f"{what} = {k} < 0")
    if k > n - 1:
        raise ValueError(f"{what} = {k} больше N−1 = {n - 1}: у узла нет столько соседей (N = {n})")
    return int(k)


def pairwise_sq_dist(Z: np.ndarray) -> np.ndarray:
    Z = np.asarray(Z, dtype=float)
    sq = (Z ** 2).sum(1)
    D2 = sq[:, None] + sq[None, :] - 2 * Z @ Z.T
    D2 = np.maximum(D2, 0)
    np.fill_diagonal(D2, 0)
    return D2


def block_distance(blocks: dict[str, np.ndarray], weights: dict[str, float] | None = None) -> tuple[np.ndarray, dict]:
    """Блоки: имя → матрица n×p_b (строка NaN = блок не наблюдается у МО)."""
    names = list(blocks)
    n = len(next(iter(blocks.values())))
    weights = weights or {b: 1.0 for b in names}
    num = np.zeros((n, n))
    den = np.zeros((n, n))
    obs_info = {}
    for b in names:
        Z = np.asarray(blocks[b], dtype=float)
        o = np.isfinite(Z).all(axis=1)
        obs_info[b] = int(o.sum())
        Zf = np.where(o[:, None], Z, 0.0)
        d2 = pairwise_sq_dist(Zf)
        oo = (o[:, None] & o[None, :]).astype(float)
        num += weights[b] * oo * d2
        den += weights[b] * oo
    with np.errstate(invalid="ignore", divide="ignore"):
        D2 = np.where(den > 0, num / den * sum(weights.values()), np.nan)
    np.fill_diagonal(D2, 0)
    return np.sqrt(D2), dict(observed_per_block=obs_info, pairs_without_common_block=int(np.isnan(D2).sum() // 2))


def knn_mask(D: np.ndarray, k: int, mode: str = "union") -> np.ndarray:
    """Маска kNN по матрице расстояний (NaN = недоступно). Связи по равным расстояниям
    разрешаются устойчивой сортировкой (по индексу) — детерминированно."""
    D = np.asarray(D, dtype=float)
    n = len(D)
    k = _check_k(k, n)
    M = np.zeros((n, n), dtype=bool)
    if k == 0:
        return M
    Dm = np.where(np.isfinite(D), D, np.inf)
    np.fill_diagonal(Dm, np.inf)
    idx = np.argsort(Dm, axis=1, kind="stable")[:, :k]
    rows = np.repeat(np.arange(n), k)
    cols = idx.ravel()
    valid = np.isfinite(Dm[rows, cols])
    M[rows[valid], cols[valid]] = True
    if mode == "union":
        M = M | M.T
    elif mode == "mutual":
        M = M & M.T
    else:
        raise ValueError("mode: 'union' | 'mutual'")
    np.fill_diagonal(M, False)
    return M


def local_scale(D: np.ndarray, k_scale: int) -> tuple[np.ndarray, dict]:
    D = np.asarray(D, dtype=float)
    n = len(D)
    k_scale = _check_k(k_scale, n, "k_scale")
    if k_scale == 0:
        raise ValueError("k_scale = 0: масштаб не определён")
    Dm = np.where(np.isfinite(D), D, np.inf)
    np.fill_diagonal(Dm, np.inf)
    srt = np.sort(Dm, axis=1)
    sigma = srt[:, k_scale - 1].copy()
    fallback = []
    for i in range(n):
        if not np.isfinite(sigma[i]):
            fin = srt[i][np.isfinite(srt[i])]
            sigma[i] = fin[-1] if len(fin) else np.nan
            fallback.append((i, "fewer_finite_neighbours"))
        if sigma[i] == 0:
            pos = srt[i][(srt[i] > 0) & np.isfinite(srt[i])]
            if len(pos):
                sigma[i] = pos[0]
                fallback.append((i, "sigma_fallback_min_positive"))
            else:
                sigma[i] = np.nan
                fallback.append((i, "all_neighbours_identical"))
    return sigma, dict(sigma_fallback=fallback)


def self_tuning_affinity(D: np.ndarray, k_nn: int = 8, k_scale: int = 7, mode: str = "union") -> tuple[np.ndarray, dict]:
    D = np.asarray(D, dtype=float)
    n = len(D)
    if n == 0:
        return np.zeros((0, 0)), dict(status="empty")
    if n == 1:
        return np.zeros((1, 1)), dict(status="single_node")
    sigma, info = local_scale(D, k_scale)
    if np.isnan(sigma).all():
        raise ValueError("все строки совпадают: self-tuning масштаб не определён (нет различий между МО)")
    M = knn_mask(D, k_nn, mode)
    with np.errstate(invalid="ignore", over="ignore"):
        S = np.exp(-np.where(np.isfinite(D), D, np.inf) ** 2 / np.outer(sigma, sigma))
    S = np.where(M & np.isfinite(S), S, 0.0)
    np.fill_diagonal(S, 0)
    info.update(status="ok", mode=mode, k_nn=k_nn, k_scale=k_scale)
    return S, info


def cosine_knn(X: np.ndarray, k: int = 8) -> np.ndarray:
    """Базовый граф econtypes v4: косинус → [0,1], union-kNN, нормировка на максимум."""
    X = np.asarray(X, dtype=float)
    nrm = np.linalg.norm(X, axis=1, keepdims=True)
    if (nrm == 0).any():
        raise ValueError("нулевой вектор признаков: косинус не определён")
    Xn = X / nrm
    S = (Xn @ Xn.T + 1) / 2
    np.fill_diagonal(S, 0)
    D = 1 - S
    np.fill_diagonal(D, 0)
    M = knn_mask(D, k, "union")
    S = np.where(M, S, 0.0)
    m = S.max()
    return S / m if m > 0 else S


def threshold_graph(S: np.ndarray, n_edges: int | None = None, tau: float | None = None) -> tuple[np.ndarray, float]:
    """Пороговый граф: оставить S_ij ≥ τ. Если задано n_edges, τ подбирается так, чтобы
    рёбер было не больше n_edges (для сравнения с kNN при равной плотности)."""
    S = np.asarray(S, dtype=float).copy()
    np.fill_diagonal(S, 0)
    iu = np.triu_indices(len(S), 1)
    vals = S[iu]
    if tau is None:
        if n_edges is None:
            raise ValueError("нужен tau или n_edges")
        if n_edges <= 0:
            return np.zeros_like(S), np.inf
        srt = np.sort(vals)[::-1]
        tau = srt[min(n_edges, len(srt)) - 1]
    out = np.where(S >= tau, S, 0.0)
    np.fill_diagonal(out, 0)
    return out, float(tau)


def diagnostics(W: np.ndarray, n_eig: int = 10) -> dict:
    W = np.asarray(W, dtype=float)
    n = len(W)
    A = W > 0
    ncomp, comp = connected_components(A, directed=False)
    deg = A.sum(1)
    wdeg = W.sum(1)
    out = dict(n=n, edges=int(np.triu(A, 1).sum()), density=float(np.triu(A, 1).sum() / max(n * (n - 1) / 2, 1)),
               components=int(ncomp), largest_component=int(np.bincount(comp).max()) if n else 0,
               isolates=int((deg == 0).sum()), degree_min=int(deg.min()) if n else 0,
               degree_median=float(np.median(deg)) if n else 0, degree_max=int(deg.max()) if n else 0,
               weighted_degree_cv=float(wdeg.std() / wdeg.mean()) if n and wdeg.mean() > 0 else np.nan,
               symmetric=bool(np.allclose(W, W.T)))
    if n >= 3 and wdeg.min() > 0:
        Dm = 1 / np.sqrt(wdeg)
        L = np.eye(n) - Dm[:, None] * W * Dm[None, :]
        ev = np.sort(np.linalg.eigvalsh((L + L.T) / 2))
        out["laplacian_eigs"] = [round(float(v), 5) for v in ev[:n_eig]]
        gaps = np.diff(ev[: min(n_eig + 1, n)])
        out["eigengap_k"] = int(np.argmax(gaps[1:]) + 2) if len(gaps) > 1 else None
    else:
        out["laplacian_eigs"] = None
        out["eigengap_k"] = None
    return out


def unit_max(S: np.ndarray) -> np.ndarray:
    S = np.clip(np.asarray(S, dtype=float), 0, None)
    np.fill_diagonal(S, 0)
    m = S.max() if S.size else 0
    return S / m if m > 0 else S


def fuse(attr: np.ndarray, layers: dict[str, np.ndarray], weights: dict[str, float], alpha: float) -> np.ndarray:
    """Линейное слияние (baseline v4, сохранён): W = α S_attr + (1−α) Σ ω_ℓ S_ℓ, ω нормируются."""
    if not 0 <= alpha <= 1:
        raise ValueError("alpha ∈ [0,1]")
    ws = {k: v for k, v in weights.items() if k in layers and v > 0}
    if alpha < 1 and not ws:
        raise ValueError("нет структурных слоёв с положительным весом")
    tot = sum(ws.values()) if ws else 1.0
    struct = sum(ws[k] / tot * layers[k] for k in ws) if ws else np.zeros_like(attr)
    return unit_max(alpha * attr + (1 - alpha) * unit_max(struct))


def snf(affinities: list[np.ndarray], k: int = 8, t: int = 20) -> np.ndarray:
    """Similarity Network Fusion (Wang et al. 2014, Nat. Methods 11:333–337), стандартные шаги:
    P = нормированная полная affinity (P_ii = 1/2, P_ij = W_ij / (2 Σ_{k≠i} W_ik)),
    S = локальная kNN-affinity (S_ij = W_ij / Σ_{k∈N_i} W_ik для j∈N_i),
    P_v ← S_v (mean_{u≠v} P_u) S_vᵀ, затем повторная нормировка; итог — среднее P_v.
    Экспериментальный метод: используется только в сравнении."""
    n = len(affinities[0])
    _check_k(k, n)

    def full_norm(W):
        W = W.copy()
        np.fill_diagonal(W, 0)
        rs = W.sum(1, keepdims=True)
        P = np.divide(W, 2 * rs, out=np.zeros_like(W), where=rs > 0)
        np.fill_diagonal(P, 0.5)
        return P

    def local(W):
        W = W.copy()
        np.fill_diagonal(W, 0)
        S = np.zeros_like(W)
        idx = np.argsort(-W, axis=1, kind="stable")[:, :k]
        for i in range(n):
            s = W[i, idx[i]].sum()
            if s > 0:
                S[i, idx[i]] = W[i, idx[i]] / s
        return S

    Ps = [full_norm(W) for W in affinities]
    Ss = [local(W) for W in affinities]
    L = len(Ps)
    if L < 2:
        return Ps[0]
    for _ in range(t):
        new = []
        for v in range(L):
            other = sum(Ps[u] for u in range(L) if u != v) / (L - 1)
            Pv = Ss[v] @ other @ Ss[v].T
            Pv = (Pv + Pv.T) / 2
            new.append(full_norm(Pv))
        Ps = new
    F = sum(Ps) / L
    np.fill_diagonal(F, 0)
    return unit_max((F + F.T) / 2)
