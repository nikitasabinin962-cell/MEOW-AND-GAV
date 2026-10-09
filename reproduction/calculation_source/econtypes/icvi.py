"""Внутренние индексы качества кластеризации (ICVI) в двух пространствах.

Пространство признаков (X):
  SW   — силуэт (↑), CH — Калински–Харабаш (↑), DB — Дэвис–Болдин (↓),
  S_Dbw — разброс + межкластерная плотность, Halkidi & Vazirgiannis 2001 (↓).
Пространство сети (W):
  MQ   — модулярность Ньюмана (↑);
  AVI  — средняя изолированность (Average Isolability): доля веса связей узлов кластера,
         остающаяся внутри кластера, W(S,S)/W(S,V), усреднённая по кластерам (↑);
  AVU  — средняя объединённость (Average Unifiability): плотность связей внутри кластера
         относительно суммы плотностей внутри и наружу, d_in/(d_in+d_out) (↑).
Названия AVI/AVU следуют работе Shalileh, Tsyplakova, Antonov (Доклады РАН, 2025);
формулы выше — наша операционализация, приведена явно для воспроизводимости.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score


def s_dbw(X: np.ndarray, labels: np.ndarray) -> float:
    ks = np.unique(labels)
    if len(ks) < 2:
        return np.nan
    cent = np.array([X[labels == k].mean(0) for k in ks])
    var_all = np.linalg.norm(X.var(0))
    sig = [np.linalg.norm(X[labels == k].var(0)) for k in ks]
    scat = np.mean(sig) / (var_all + 1e-12)
    stdev = np.sqrt(np.sum(sig)) / len(ks)

    def density(pt, mask):
        return np.sum(np.linalg.norm(X[mask] - pt, axis=1) <= stdev)

    dens = 0.0
    for i, a in enumerate(ks):
        for j, b in enumerate(ks):
            if i == j:
                continue
            m = (labels == a) | (labels == b)
            u = (cent[i] + cent[j]) / 2
            denom = max(density(cent[i], m), density(cent[j], m))
            dens += density(u, m) / denom if denom > 0 else 0
    dens /= len(ks) * (len(ks) - 1)
    return float(scat + dens)


def modularity(W: np.ndarray, labels: np.ndarray) -> float:
    m2 = W.sum()
    if m2 == 0:
        return np.nan
    k = W.sum(1)
    same = labels[:, None] == labels[None, :]
    return float(((W - np.outer(k, k) / m2) * same).sum() / m2)


def avi_avu(W: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    iso, uni = [], []
    n = len(W)
    for c in np.unique(labels):
        s = labels == c
        ns = s.sum()
        w_in = W[np.ix_(s, s)].sum()
        w_out = W[np.ix_(s, ~s)].sum()
        iso.append(w_in / (w_in + w_out) if (w_in + w_out) > 0 else 0)
        d_in = w_in / (ns * (ns - 1)) if ns > 1 else 0
        d_out = w_out / (ns * (n - ns)) if n > ns else 0
        uni.append(d_in / (d_in + d_out) if (d_in + d_out) > 0 else 0)
    return float(np.mean(iso)), float(np.mean(uni))


def all_indices(X: np.ndarray, W: np.ndarray, labels: np.ndarray) -> dict:
    if len(np.unique(labels)) < 2:
        return dict(SW=np.nan, CH=np.nan, DB=np.nan, S_Dbw=np.nan, MQ=np.nan, AVI=np.nan, AVU=np.nan)
    avi, avu = avi_avu(W, labels)
    return dict(
        SW=silhouette_score(X, labels),
        CH=calinski_harabasz_score(X, labels),
        DB=davies_bouldin_score(X, labels),
        S_Dbw=s_dbw(X, labels),
        MQ=modularity(W, labels),
        AVI=avi,
        AVU=avu,
    )


HIGHER_BETTER = {"SW": True, "CH": True, "DB": False, "S_Dbw": False, "MQ": True, "AVI": True, "AVU": True}


def baseline_normalized(X: np.ndarray, W: np.ndarray, labels: np.ndarray, n_perm: int = 50, seed: int = 0) -> dict:
    """Нормировка ICVI на случайную базовую линию (рекомендация Shalileh et al., 2025).

    Многие индексы механически зависят от числа кластеров k (SW и CH обычно падают, AVU растёт).
    Сравниваем значение индекса с распределением на случайных перестановках меток с теми же
    размерами кластеров: z = (I − mean_null)/std_null, знак выровнен так, что больше = лучше.
    Это делает решения с разным k сопоставимыми.
    """
    rng = np.random.default_rng(seed)
    obs = all_indices(X, W, labels)
    null = [all_indices(X, W, rng.permutation(labels)) for _ in range(n_perm)]
    z = {}
    for k, hb in HIGHER_BETTER.items():
        v = np.array([d[k] for d in null], dtype=float)
        sd = np.nanstd(v)
        zz = (obs[k] - np.nanmean(v)) / sd if sd > 0 else 0.0
        z["z_" + k] = zz if hb else -zz
    return z
