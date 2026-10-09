"""Отслеживание кластеров во времени.

Подход — эволюционная спектральная кластеризация (Chakrabarti et al., 2006):
  W̃_t = (1 − β)·W_t + β·W̃_{t−1},
где W_t — совмещённая матрица квартала t (атрибуты квартала + потоки госзаказа квартала +
долгосрочные слои синхронности трат). Сглаживание β гасит шум отдельных кварталов
(крупный контракт может «перебросить» район), но сохраняет устойчивые сдвиги.
Метки кластеров кварталов выравниваются с итоговой статической разбивкой венгерским
алгоритмом (максимум пересечения), поэтому «кластер 2» означает один и тот же тип
экономики во всех кварталах. Изменения измеряем ARI между соседними кварталами,
числом переходов МО и матрицей переходов.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score


def align(labels: np.ndarray, ref: np.ndarray) -> np.ndarray:
    ks, rs = np.unique(labels), np.unique(ref)
    M = np.array([[np.sum((labels == a) & (ref == b)) for b in rs] for a in ks])
    r, c = linear_sum_assignment(-M)
    mp = {ks[i]: rs[j] for i, j in zip(r, c)}
    nxt = max(rs) + 1
    out = np.empty_like(labels)
    for a in ks:
        if a not in mp:
            mp[a] = nxt
            nxt += 1
        out[labels == a] = mp[a]
    return out


def transitions(lab_df: pd.DataFrame) -> pd.DataFrame:
    """lab_df: МО × периоды. Матрица переходов «кластер в t → кластер в t+1» (суммарно)."""
    pairs = []
    cols = list(lab_df.columns)
    for a, b in zip(cols[:-1], cols[1:]):
        pairs += list(zip(lab_df[a], lab_df[b]))
    p = pd.DataFrame(pairs, columns=["from", "to"])
    return pd.crosstab(p["from"], p["to"])


def stability(lab_df: pd.DataFrame) -> pd.DataFrame:
    cols = list(lab_df.columns)
    ari = [adjusted_rand_score(lab_df[a], lab_df[b]) for a, b in zip(cols[:-1], cols[1:])]
    return pd.DataFrame({"from": [str(c) for c in cols[:-1]], "to": [str(c) for c in cols[1:]], "ARI": ari})
