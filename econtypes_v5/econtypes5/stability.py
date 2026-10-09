"""Устойчивость разбиений: co-assignment, устойчивость узла, схемы бутстрепа.

  P_ij = Σ_b O_ij^(b) 1(c_i^(b) = c_j^(b)) / Σ_b O_ij^(b),  O_ij^(b) = 1, если i и j оба наблюдались в запуске b.
  Знаменатель 0 → NaN (пара ни разу не наблюдалась совместно).
  Устойчивость узла i: среднее P_ij по j из кластера i в итоговом разбиении, j ≠ i (самопара исключена).
Частоты co-assignment — характеристика воспроизводимости процедуры, а не вероятность
«истинного» экономического типа.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
from sklearn.metrics import adjusted_rand_score


class CoAssignment:
    def __init__(self, n: int):
        self.same = np.zeros((n, n))
        self.obs = np.zeros((n, n))
        self.runs = 0

    def add(self, idx: np.ndarray, lab: np.ndarray):
        idx = np.asarray(idx)
        lab = np.asarray(lab)
        s = (lab[:, None] == lab[None, :]).astype(float)
        self.same[np.ix_(idx, idx)] += s
        self.obs[np.ix_(idx, idx)] += 1
        self.runs += 1

    def matrix(self) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            P = np.where(self.obs > 0, self.same / self.obs, np.nan)
        return P

    def node_stability(self, final: np.ndarray) -> np.ndarray:
        P = self.matrix()
        n = len(final)
        out = np.full(n, np.nan)
        for i in range(n):
            m = (final == final[i])
            m[i] = False
            v = P[i, m]
            v = v[np.isfinite(v)]
            if len(v):
                out[i] = float(v.mean())
        return out


def node_bootstrap(cluster_fn: Callable[[np.ndarray], np.ndarray], n: int, final: np.ndarray, B: int = 200,
                   frac: float = 0.8, seed: int = 42) -> dict:
    """Схема 1: подвыборка узлов без возвращения (доля frac), перестроение кластеров на подграфе."""
    rng = np.random.default_rng(seed)
    co = CoAssignment(n)
    aris = []
    for _ in range(B):
        idx = np.sort(rng.choice(n, int(round(frac * n)), replace=False))
        lab = cluster_fn(idx)
        co.add(idx, lab)
        aris.append(adjusted_rand_score(final[idx], lab))
    return dict(scheme="node_subsample", B=B, frac=frac, seed=seed, ari=np.array(aris), co=co)


def full_rebuild_bootstrap(rebuild_fn: Callable[[np.random.Generator], np.ndarray], n: int, final: np.ndarray,
                           B: int = 100, seed: int = 42, scheme: str = "rebuild") -> dict:
    """Схемы 2–3: перестроение признаков/сети целиком (бутстреп временных блоков месяцев или
    возмущение признаков/параметров); rebuild_fn возвращает метки всех n узлов (NaN-узлы = −1)."""
    rng = np.random.default_rng(seed)
    co = CoAssignment(n)
    aris = []
    for _ in range(B):
        lab = np.asarray(rebuild_fn(rng))
        idx = np.where(lab >= 0)[0]
        co.add(idx, lab[idx])
        aris.append(adjusted_rand_score(final[idx], lab[idx]))
    return dict(scheme=scheme, B=B, seed=seed, ari=np.array(aris), co=co)


def moving_block_months(months: list[str], block: int, rng: np.random.Generator) -> list[str]:
    """Moving-block bootstrap (Künsch 1989) для календаря месяцев: последовательность из
    случайных блоков длины `block`, итоговая длина = исходной. Возвращает список месяцев (с повторами)."""
    T = len(months)
    if not 1 <= block <= T:
        raise ValueError("block вне [1, T]")
    out = []
    while len(out) < T:
        s = int(rng.integers(0, T - block + 1))
        out.extend(months[s:s + block])
    return out[:T]
