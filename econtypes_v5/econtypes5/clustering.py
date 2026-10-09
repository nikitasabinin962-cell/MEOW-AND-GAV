"""Методы кластеризации v5.

  * spectral(W, K)      — спектральная кластеризация по готовой affinity (sklearn, cluster_qr).
                          Несвязный граф регуляризуется добавлением ε ко всем вне-диагональным
                          весам (как в v4, ε = 1e-6); ε и число компонент возвращаются.
  * leiden(W, K|γ)      — Leiden (Traag, Waltman, van Eck 2019, Sci. Rep. 9:5233), RB-конфигурационная
                          модель с разрешением γ; при заданном K γ подбирается бисекцией по сетке.
  * louvain(W, K)       — Louvain (networkx), подбор разрешения как в v4 (сравнение).
  * kmeans/ward/gmm(X)  — методы атрибутивного пространства.
Все методы детерминированы при фиксированном seed.
"""
from __future__ import annotations

import numpy as np
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
from sklearn.mixture import GaussianMixture


def relabel_by_size(lab: np.ndarray) -> np.ndarray:
    lab = np.asarray(lab)
    u, c = np.unique(lab, return_counts=True)
    order = u[np.argsort(-c, kind="stable")]
    mp = {old: new for new, old in enumerate(order)}
    return np.array([mp[x] for x in lab])


def spectral(W: np.ndarray, k: int, seed: int = 42, eps: float = 1e-6) -> tuple[np.ndarray, dict]:
    W = np.asarray(W, dtype=float)
    n = len(W)
    if not 2 <= k <= n - 1:
        raise ValueError(f"spectral: K={k} вне [2, N−1={n - 1}]")
    ncomp, _ = connected_components(W > 0, directed=False)
    A = W + eps
    np.fill_diagonal(A, 0)
    lab = SpectralClustering(k, affinity="precomputed", random_state=seed, assign_labels="cluster_qr").fit_predict(A)
    return relabel_by_size(lab), dict(components_before_regularization=int(ncomp), eps=eps)


def _igraph(W: np.ndarray):
    import igraph as ig
    iu = np.triu_indices(len(W), 1)
    m = W[iu] > 0
    g = ig.Graph(n=len(W), edges=list(zip(iu[0][m].tolist(), iu[1][m].tolist())))
    g.es["weight"] = W[iu][m].tolist()
    return g


def leiden(W: np.ndarray, resolution: float = 1.0, seed: int = 42) -> np.ndarray:
    import leidenalg as la
    g = _igraph(np.asarray(W, dtype=float))
    part = la.find_partition(g, la.RBConfigurationVertexPartition, weights="weight",
                             resolution_parameter=resolution, seed=seed, n_iterations=-1)
    return relabel_by_size(np.array(part.membership))


def leiden_k(W: np.ndarray, k: int, seed: int = 42, grid=None) -> tuple[np.ndarray, dict]:
    """Разрешение γ, дающее число сообществ, ближайшее к k (сначала сетка, затем бисекция)."""
    grid = grid if grid is not None else np.round(np.linspace(0.1, 4.0, 40), 3)
    best, info = None, None
    for g in grid:
        lab = leiden(W, float(g), seed)
        d = abs(len(np.unique(lab)) - k)
        if best is None or d < info["abs_k_diff"]:
            best, info = lab, dict(resolution=float(g), k_real=int(len(np.unique(lab))), abs_k_diff=int(d))
        if d == 0:
            break
    if info["abs_k_diff"]:
        lo, hi = 0.05, 8.0
        for _ in range(30):
            mid = (lo + hi) / 2
            lab = leiden(W, mid, seed)
            kr = len(np.unique(lab))
            if abs(kr - k) < info["abs_k_diff"]:
                best, info = lab, dict(resolution=mid, k_real=int(kr), abs_k_diff=int(abs(kr - k)))
            if kr == k:
                break
            lo, hi = (mid, hi) if kr < k else (lo, mid)
    return best, info


def louvain_k(W: np.ndarray, k: int, seed: int = 42) -> tuple[np.ndarray, dict]:
    import networkx as nx
    G = nx.from_numpy_array(np.asarray(W, dtype=float))
    best, info = None, None
    for r in np.linspace(0.3, 3.0, 28):
        comms = nx.community.louvain_communities(G, weight="weight", resolution=float(r), seed=seed)
        lab = np.zeros(len(W), dtype=int)
        for c, nodes in enumerate(comms):
            lab[list(nodes)] = c
        d = abs(len(comms) - k)
        if best is None or d < info["abs_k_diff"]:
            best, info = relabel_by_size(lab), dict(resolution=float(r), k_real=len(comms), abs_k_diff=int(d))
        if d == 0:
            break
    return best, info


def kmeans(X: np.ndarray, k: int, seed: int = 42, n_init: int = 50) -> np.ndarray:
    return relabel_by_size(KMeans(k, n_init=n_init, random_state=seed).fit_predict(X))


def ward(X: np.ndarray, k: int) -> np.ndarray:
    return relabel_by_size(AgglomerativeClustering(k, linkage="ward").fit_predict(X))


def gmm(X: np.ndarray, k: int, seed: int = 42) -> np.ndarray:
    return relabel_by_size(GaussianMixture(k, covariance_type="diag", n_init=10, random_state=seed).fit(X).predict(X))


def run(method: str, k: int, X: np.ndarray | None = None, W: np.ndarray | None = None, seed: int = 42) -> tuple[np.ndarray, dict]:
    if method == "spectral":
        return spectral(W, k, seed)
    if method == "leiden":
        return leiden_k(W, k, seed)
    if method == "louvain":
        return louvain_k(W, k, seed)
    if method == "kmeans":
        return kmeans(X, k, seed), {}
    if method == "ward":
        return ward(X, k), {}
    if method == "gmm":
        return gmm(X, k, seed), {}
    raise ValueError(method)
