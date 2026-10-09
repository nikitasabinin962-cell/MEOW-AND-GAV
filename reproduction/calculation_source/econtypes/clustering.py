"""Методы кластеризации и их сравнение.

Три семейства (чтобы показать вклад атрибутов и структуры по отдельности):
  *_attr   — только атрибуты узлов: k-means, Ward, GMM;
  *_struct — только структура (слои сети без атрибутов): спектральная, Louvain;
  *_fused  — атрибутированная сеть W = α·S_attr + (1−α)·S_struct: спектральная, Louvain.
"""
from __future__ import annotations

import networkx as nx
import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
from sklearn.mixture import GaussianMixture


def spectral(W: np.ndarray, k: int, seed: int) -> np.ndarray:
    A = W + 1e-6  # гарантируем связность графа
    np.fill_diagonal(A, 0)
    return SpectralClustering(k, affinity="precomputed", random_state=seed, assign_labels="cluster_qr").fit_predict(A)


def louvain(W: np.ndarray, resolution: float, seed: int) -> np.ndarray:
    G = nx.from_numpy_array(W)
    comms = nx.community.louvain_communities(G, weight="weight", resolution=resolution, seed=seed)
    lab = np.zeros(len(W), dtype=int)
    for c, nodes in enumerate(sorted(comms, key=len, reverse=True)):
        lab[list(nodes)] = c
    return lab


def louvain_k(W: np.ndarray, k: int, seed: int) -> np.ndarray:
    """Подбор разрешения Louvain, дающего число сообществ, ближайшее к k."""
    best, bestd = None, 1e9
    for r in np.linspace(0.3, 3.0, 28):
        lab = louvain(W, r, seed)
        d = abs(len(np.unique(lab)) - k)
        if d < bestd:
            best, bestd = lab, d
        if d == 0:
            break
    return best


def run(method: str, X: np.ndarray, W_struct: np.ndarray, W_fused: np.ndarray, k: int, cfg: dict) -> np.ndarray:
    seed = cfg["random_state"]
    if method == "kmeans_attr":
        return KMeans(k, n_init=cfg["n_init"], random_state=seed).fit_predict(X)
    if method == "ward_attr":
        return AgglomerativeClustering(k, linkage="ward").fit_predict(X)
    if method == "gmm_attr":
        return GaussianMixture(k, covariance_type="diag", n_init=10, random_state=seed).fit(X).predict(X)
    if method == "spectral_struct":
        return spectral(W_struct, k, seed)
    if method == "louvain_struct":
        return louvain_k(W_struct, k, seed)
    if method == "spectral_fused":
        return spectral(W_fused, k, seed)
    if method == "louvain_fused":
        return louvain_k(W_fused, k, seed)
    raise ValueError(method)
