"""Статистика связей: корреляции, перестановочные тесты, поправки на множественность,
пространственные нули, разложение «между МО / внутри МО».

Все p-значения Monte Carlo: p = (b + 1)/(B + 1) (Phipson & Smyth 2010, SAGMB 9:39),
b — число симуляций не менее экстремальных, B — число симуляций. Сохраняются B, seed, сторона.
Pearson — для оправданно линейных связей (после трансформаций), Spearman — для монотонных.
Поправки: Benjamini–Hochberg (BH; валидна при независимости/PRDS) и Benjamini–Yekutieli (BY;
при произвольной зависимости) — scipy.stats.false_discovery_control (scipy 1.17).
Пространственный нуль: Moran spectral randomization (Wagner & Dray 2015, MEE 6:1169) —
суррогат сохраняет спектр по собственным векторам Морана, т.е. пространственную автокорреляцию.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as ss


def mc_p(b: int, B: int) -> float:
    if B <= 0:
        raise ValueError("B > 0")
    return (b + 1) / (B + 1)


def _clean(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m], int((~m).sum())


def _rowcorr(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    A = A - A.mean(axis=-1, keepdims=True)
    B = B - B.mean(axis=-1, keepdims=True)
    den = np.sqrt((A ** 2).sum(-1) * (B ** 2).sum(-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, (A * B).sum(-1) / den, np.nan)


def corr_test(x, y, method: str = "spearman", B: int = 9999, seed: int = 0, ci_B: int = 2000,
              null_y: np.ndarray | None = None) -> dict:
    """Коэффициент, n, пропуски, асимптотическое p (scipy), перестановочное двустороннее p = (b+1)/(B+1),
    бутстреп-CI 95% (percentile, пары МО ресэмплируются вместе). Если передан null_y (B×n суррогатов y,
    например пространственных MSR), перестановочное p считается по ним. Векторизовано (ранги по строкам)."""
    from scipy.stats import rankdata
    x0, y0 = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x0) & np.isfinite(y0)
    x, y = x0[m], y0[m]
    n = len(x)
    out = dict(method=method, n=n, n_missing=int((~m).sum()))
    if n < 4 or np.std(x) == 0 or np.std(y) == 0:
        out.update(r=np.nan, p_asym=np.nan, p_perm=np.nan, ci_lo=np.nan, ci_hi=np.nan, status="undefined")
        return out
    sp = method == "spearman"
    tr = (lambda a: rankdata(a, axis=-1)) if sp else (lambda a: a)
    res = ss.spearmanr(x, y) if sp else ss.pearsonr(x, y)
    r = float(res.statistic)
    p_asym = float(res.pvalue)
    rng = np.random.default_rng(seed)
    if null_y is None:
        tx, ty = tr(x), tr(y)
        perms = rng.permuted(np.tile(ty, (B, 1)), axis=1)
        null = _rowcorr(np.broadcast_to(tx, perms.shape), perms)
        scheme = "iid_permutation"
    else:
        ny = np.asarray(null_y)[:, m]
        null = _rowcorr(np.broadcast_to(tr(x), ny.shape), tr(ny))
        B = len(null)
        scheme = "spatial_surrogate"
    b = int(np.sum(np.abs(null) >= abs(r) - 1e-12))
    boots = np.array([])
    if ci_B:
        idx = rng.integers(0, n, (ci_B, n))
        boots = _rowcorr(tr(x[idx]), tr(y[idx]))
        boots = boots[np.isfinite(boots)]
    lo, hi = (np.quantile(boots, [0.025, 0.975]) if len(boots) else (np.nan, np.nan))
    out.update(r=r, p_asym=p_asym, p_perm=mc_p(b, B), B=B, seed=seed, perm_scheme=scheme, alternative="two-sided",
               ci_lo=float(lo), ci_hi=float(hi), ci_method=f"percentile bootstrap B={ci_B}", status="ok")
    return out


def fdr(p: np.ndarray, method: str = "bh") -> np.ndarray:
    p = np.asarray(p, float)
    out = np.full_like(p, np.nan)
    m = np.isfinite(p)
    if m.any():
        out[m] = ss.false_discovery_control(p[m], method=method)
    return out


# ---------- пространственные веса и суррогаты ----------

def moran_I(y: np.ndarray, Wsp: np.ndarray) -> float:
    y = np.asarray(y, float)
    z = y - y.mean()
    S0 = Wsp.sum()
    return float(len(y) / S0 * (z @ Wsp @ z) / (z @ z)) if S0 > 0 and (z @ z) > 0 else np.nan


def moran_eigenvectors(Wsp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(Wsp)
    W = (Wsp + Wsp.T) / 2
    H = np.eye(n) - 1.0 / n
    M = H @ W @ H
    val, vec = np.linalg.eigh(M)
    keep = np.abs(val) > 1e-10
    return val[keep], vec[:, keep]


def msr_surrogates(y: np.ndarray, Wsp: np.ndarray, B: int, seed: int = 0) -> np.ndarray:
    """Moran spectral randomization, вариант 'pair' упрощённо — случайные знаки коэффициентов
    по MEM (сохраняет вклад каждого собственного вектора, значит и I Морана), среднее и дисперсию."""
    y = np.asarray(y, float)
    _, V = moran_eigenvectors(Wsp)
    mu = y.mean()
    c = V.T @ (y - mu)
    resid = (y - mu) - V @ c
    rng = np.random.default_rng(seed)
    S = rng.choice([-1.0, 1.0], size=(B, len(c)))
    return mu + (S * c) @ V.T + resid


# ---------- кластеры против внешних показателей ----------

def epsilon_squared(groups: list[np.ndarray]) -> float:
    allv = np.concatenate(groups)
    n = len(allv)
    H = ss.kruskal(*groups).statistic if len(groups) > 1 else np.nan
    return float(H / ((n ** 2 - 1) / (n + 1))) if np.isfinite(H) else np.nan


def cluster_vs_external(labels: np.ndarray, y: np.ndarray, B: int = 9999, seed: int = 0,
                        surrogate_y: np.ndarray | None = None) -> dict:
    """Номера кластеров — номинальная шкала. Статистика — Kruskal–Wallis H; p перестановочное
    (перестановка меток при фиксированных размерах) и, если даны, по пространственным суррогатам y."""
    lab = np.asarray(labels)
    y = np.asarray(y, float)
    m = np.isfinite(y)
    lab, y = lab[m], y[m]
    ks = np.unique(lab)
    groups = [y[lab == k] for k in ks]
    if len(ks) < 2 or any(len(g) == 0 for g in groups):
        return dict(n=int(m.sum()), status="undefined")
    H = float(ss.kruskal(*groups).statistic)
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(B):
        pl = rng.permutation(lab)
        null.append(ss.kruskal(*[y[pl == k] for k in ks]).statistic)
    b = int(np.sum(np.asarray(null) >= H - 1e-12))
    out = dict(n=int(m.sum()), n_missing=int((~m).sum()), H=H, eps2=epsilon_squared(groups), p_perm=mc_p(b, B), B=B, seed=seed,
               medians={int(k): float(np.median(g)) for k, g in zip(ks, groups)}, status="ok")
    if surrogate_y is not None:
        sy = np.asarray(surrogate_y)[:, m]
        nullS = [ss.kruskal(*[v[lab == k] for k in ks]).statistic for v in sy]
        bS = int(np.sum(np.asarray(nullS) >= H - 1e-12))
        out.update(p_spatial=mc_p(bS, len(nullS)), B_spatial=len(nullS))
    return out


def within_between(panel: pd.DataFrame, x: str, y: str, unit: str = "mo", B: int = 2000, seed: int = 0,
                   method: str = "pearson") -> dict:
    """Разложение панели: between — корреляция средних по МО; within — корреляция отклонений
    от средних МО (fixed-effects demeaning). CI within — кластерный бутстреп по МО
    (наблюдения одного МО переносятся вместе), учитывает повторные наблюдения."""
    d = panel[[unit, x, y]].dropna()
    if d[unit].nunique() < 5:
        return dict(status="undefined")
    means = d.groupby(unit)[[x, y]].mean()
    f = (lambda a, b: ss.pearsonr(a, b).statistic) if method == "pearson" else (lambda a, b: ss.spearmanr(a, b).statistic)
    between = float(f(means[x], means[y])) if means[x].std() > 0 and means[y].std() > 0 else np.nan
    dm = d[[x, y]] - d.groupby(unit)[[x, y]].transform("mean")
    within = float(f(dm[x], dm[y])) if dm[x].std() > 0 and dm[y].std() > 0 else np.nan
    rng = np.random.default_rng(seed)
    units = d[unit].unique()
    g = {u: dm.loc[d[unit] == u] for u in units}
    bw = []
    for _ in range(B):
        pick = rng.choice(units, len(units), replace=True)
        s = pd.concat([g[u] for u in pick])
        if s[x].std() > 0 and s[y].std() > 0:
            bw.append(f(s[x], s[y]))
    lo, hi = np.quantile(bw, [0.025, 0.975]) if bw else (np.nan, np.nan)
    return dict(status="ok", n_units=int(len(units)), n_obs=int(len(d)), between=between, within=within,
                within_ci_lo=float(lo), within_ci_hi=float(hi), within_ci="cluster bootstrap by MO, B=%d" % B)
