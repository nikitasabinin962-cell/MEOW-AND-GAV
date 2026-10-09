"""Композиционный анализ долей (Aitchison 1982, JRSS-B 44:139–177; Egozcue et al. 2003, Math. Geol. 35:279–300).

Доли структуры потребления — композиция: Σ_j p_j = 1. Евклидово расстояние по долям и по
производным долей дублирует ограничение суммы и чувствительно к масштабу малых долей.
Используем:
  closure:  C(x)_j = x_j / Σ_r x_r
  clr:      clr(p)_j = log p_j − (1/D) Σ_r log p_r
  ilr:      z = Vᵀ log p,  VᵀV = I_{D−1},  Vᵀ1 = 0  (ортонормированный базис Гельмерта/пивотный)
  d_A(p,q) = ‖clr(p) − clr(q)‖₂ = ‖ilr(p) − ilr(q)‖₂.
Нули:
  * структурный нуль — компонента равна 0 у всех наблюдений (категории нет в данных) → компонента
    исключается из композиции с записью в диагностике;
  * выборочный/округлённый нуль у части наблюдений → мультипликативная замена
    (Martín-Fernández, Barceló-Vidal, Pawlowsky-Glahn 2003, Math. Geol. 35:253–278):
    r_j = δ для нулей, r_j = x_j(1 − Σ_{нули} δ) для ненулевых; δ задаётся явно и проверяется
    в анализе чувствительности. Для денежных долей нуль трат и пропуск наблюдения различаются:
    пропуск (NaN) не заменяется.
"""
from __future__ import annotations

import numpy as np


def closure(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    if (X < 0).any():
        raise ValueError("композиция содержит отрицательные значения")
    s = X.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = X / s
    out[(s == 0).ravel()] = np.nan
    return out


def detect_zeros(P: np.ndarray) -> dict:
    P = np.asarray(P, dtype=float)
    obs = np.isfinite(P).all(axis=1)
    Z = (P == 0) & obs[:, None]
    structural = [int(j) for j in range(P.shape[1]) if obs.any() and Z[obs, j].all()]
    return dict(rows_observed=int(obs.sum()), structural_zero_parts=structural,
                sample_zero_cells=int(Z.sum() - sum(Z[:, j].sum() for j in structural)))


def multiplicative_replacement(P: np.ndarray, delta: float = 1e-4) -> tuple[np.ndarray, int]:
    """Замена нулей; строки с NaN остаются NaN. Возвращает (P', число заменённых ячеек)."""
    P = closure(P)
    out = P.copy()
    n_rep = 0
    for i in range(len(P)):
        row = P[i]
        if not np.isfinite(row).all():
            continue
        z = row == 0
        if z.any():
            if delta * z.sum() >= 1:
                raise ValueError("delta слишком велик для числа нулей")
            out[i] = np.where(z, delta, row * (1 - delta * z.sum()))
            n_rep += int(z.sum())
    return out, n_rep


def clr(P: np.ndarray) -> np.ndarray:
    P = np.asarray(P, dtype=float)
    with np.errstate(divide="raise", invalid="ignore"):
        L = np.log(P)
    return L - L.mean(axis=1, keepdims=True)


def helmert_basis(D: int) -> np.ndarray:
    """Ортонормированный контрастный базис V (D×(D−1)) пивотного вида (Egozcue et al. 2003):
    k-я координата сравнивает k первых частей с (k+1)-й."""
    if D < 2:
        raise ValueError("ILR требует D ≥ 2 частей")
    V = np.zeros((D, D - 1))
    for k in range(1, D):
        V[:k, k - 1] = 1.0 / k
        V[k, k - 1] = -1.0
        V[:, k - 1] *= np.sqrt(k / (k + 1))
    return V


def ilr(P: np.ndarray, V: np.ndarray | None = None) -> np.ndarray:
    P = np.asarray(P, dtype=float)
    V = helmert_basis(P.shape[1]) if V is None else V
    return clr(P) @ V


def ilr_inv(Z: np.ndarray, V: np.ndarray) -> np.ndarray:
    Y = np.exp(Z @ V.T)
    return Y / Y.sum(axis=1, keepdims=True)


def aitchison_distance(P: np.ndarray) -> np.ndarray:
    C = clr(P)
    diff = C[:, None, :] - C[None, :, :]
    return np.sqrt((diff ** 2).sum(-1))


def ilr_coordinates(shares: np.ndarray, part_names: list[str], delta: float = 1e-4) -> dict:
    """Полный конвейер: проверка, структурные нули, замена выборочных нулей, ILR.
    Возвращает координаты, их подписи (какие части сравниваются) и диагностику."""
    P = np.asarray(shares, dtype=float)
    sums = np.nansum(P, axis=1)
    diag = dict(n=len(P), parts=list(part_names), max_abs_sum_minus_1=float(np.nanmax(np.abs(sums[np.isfinite(P).all(1)] - 1)))
                if np.isfinite(P).all(1).any() else np.nan)
    z = detect_zeros(P)
    keep = [j for j in range(P.shape[1]) if j not in z["structural_zero_parts"]]
    diag.update(z, dropped_structural=[part_names[j] for j in z["structural_zero_parts"]])
    P = P[:, keep]
    names = [part_names[j] for j in keep]
    P2, n_rep = multiplicative_replacement(P, delta)
    diag.update(replaced_zero_cells=n_rep, delta=delta)
    V = helmert_basis(len(names))
    Z = ilr(P2, V)
    labels = [f"ilr{k}: [{' ,'.join(names[:k])}] vs {names[k]}" for k in range(1, len(names))]
    return dict(Z=Z, labels=labels, parts=names, V=V, diagnostics=diag)
