"""Дополнительные методы из файлов 3 и 4, применимые к доступным данным (внешние показатели и
интерпретация; в обучение типологии не входят).

  demographic_balance — ΔN = B − D + M + A (файл 3, метод 1): A — остаток (границы, пересмотры, ошибки учёта).
      M в персонах = коэффициент ‱ × средняя численность / 10 000. Остаток не называется «скрытой миграцией».
  age_dependency      — 65+/(20–64) и (0–19)/(20–64) ×100 (файл 3, метод 5); ВПН-2020 даёт 5-летние группы.
  economic_complexity — метод отражений Hidalgo & Hausmann 2009 (PNAS 106:10570) на бинарной матрице RCA≥1
      МО × секция ОКВЭД (число фирм МСП, снимок 10.09.2026); ECI — второй собственный вектор M̃ = D⁻¹ M U⁻¹ Mᵀ.
  relatedness_density — плотность ω_ms = Σ_s' M_ms' φ_ss' / Σ_s' φ_ss', φ_ss' = min(P(RCA_s|RCA_s'), P(RCA_s'|RCA_s))
      (Hidalgo et al. 2007, Science 317:482; принцип relatedness — Hidalgo et al. 2018).
  e_bh               — e-BH (Wang & Ramdas 2022, JRSS-B 84:822) с калибратором p→e: e = κ p^(κ−1), κ = 1/2;
      контроль FDR при произвольной зависимости; сравнение с BH/BY.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def demographic_balance(pop: pd.DataFrame, facts: pd.DataFrame, year: int) -> pd.DataFrame:
    """pop: МО × даты '{Y}-01-01'; facts: fact_mo (births/deaths/natinc в персонах, migr_rate ‱)."""
    a, b = f"{year}-01-01", f"{year + 1}-01-01"
    out = pd.DataFrame(index=pop.index)
    out["dN"] = pop[b] - pop[a]
    f = facts[facts.period == str(year)]

    def get(ind, src=None):
        s = f[f.indicator == ind]
        if src:
            s = s[s.source_id == src]
        s = s.sort_values("source_id").drop_duplicates("mo_id", keep="first")
        return s.set_index("mo_id").value.reindex(out.index)

    out["births"] = get("births")
    out["deaths"] = get("deaths")
    out["natural"] = out.births - out.deaths
    mean_pop = (pop[a] + pop[b]) / 2
    out["migr_rate_per10k"] = get("migr_rate")
    out["migration_est"] = out.migr_rate_per10k * mean_pop / 10000
    out["residual_A"] = out.dN - out.natural - out.migration_est
    out["residual_share_of_pop"] = out.residual_A / pop[a]
    out["year"] = year
    out["status"] = np.where(out[["births", "deaths", "migr_rate_per10k"]].notna().all(axis=1), "computed", "data_gap")
    return out


def age_dependency(age_facts: pd.DataFrame) -> pd.DataFrame:
    pv = age_facts.pivot(index="mo_id", columns="indicator", values="value")
    g = lambda *k: sum(pv[f"census_age_{x}"] for x in k)
    young = g("0-4", "5-9", "10-14", "15-19")
    work = g("20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64")
    old = g("65-69", "70-74", "75-79", "80-84", "85иболее")
    return pd.DataFrame({"old_age_ratio_65_20_64": 100 * old / work, "youth_ratio_0_19_20_64": 100 * young / work})


def rca_matrix(counts: pd.DataFrame) -> pd.DataFrame:
    share_m = counts.div(counts.sum(axis=1), axis=0)
    share_s = counts.sum() / counts.values.sum()
    return share_m / share_s


def economic_complexity(counts: pd.DataFrame, threshold: float = 1.0) -> tuple[pd.Series, pd.Series, dict]:
    M = (rca_matrix(counts) >= threshold).astype(float)
    M = M.loc[M.sum(axis=1) > 0, M.sum(axis=0) > 0]
    kc0 = M.sum(axis=1)          # разнообразие МО
    kp0 = M.sum(axis=0)          # повсеместность отрасли
    Mt = (M.values / kc0.values[:, None]) @ (M.values / kp0.values[None, :]).T
    w, v = np.linalg.eig(Mt)
    order = np.argsort(-w.real)
    vec = v[:, order[1]].real
    eci = (vec - vec.mean()) / vec.std()
    # знак: ECI положительно связан с разнообразием (стандартная нормировка)
    if np.corrcoef(eci, kc0)[0, 1] < 0:
        eci = -eci
    Mp = (M.values / kp0.values[None, :]).T @ (M.values / kc0.values[:, None])
    wp, vp = np.linalg.eig(Mp)
    op = np.argsort(-wp.real)
    pci = vp[:, op[1]].real
    pci = (pci - pci.mean()) / pci.std()
    if np.corrcoef(M.values.T @ eci, pci)[0, 1] < 0:
        pci = -pci
    return pd.Series(eci, index=M.index, name="eci"), pd.Series(pci, index=M.columns, name="pci"), dict(
        diversity=kc0.to_dict(), ubiquity=kp0.to_dict(), eigenvalues=[round(float(x), 4) for x in np.sort(w.real)[::-1][:5]])


def relatedness_density(counts: pd.DataFrame, threshold: float = 1.0) -> pd.DataFrame:
    M = (rca_matrix(counts) >= threshold).astype(float)
    co = M.T @ M
    ub = np.diag(co).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        P1 = co / ub[None, :]
        P2 = co / ub[:, None]
    phi = np.fmin(P1, P2)
    np.fill_diagonal(phi.values, 0)
    dens = (M @ phi) / phi.sum(axis=0).replace(0, np.nan)
    return dens


def e_bh(p: np.ndarray, alpha: float = 0.05, kappa: float = 0.5) -> np.ndarray:
    p = np.asarray(p, float)
    m = np.isfinite(p)
    e = np.full_like(p, np.nan)
    e[m] = kappa * np.power(np.clip(p[m], 1e-300, 1), kappa - 1)
    rej = np.zeros_like(p, dtype=bool)
    em = e[m]
    n = len(em)
    order = np.argsort(-em)
    k_star = 0
    for k in range(1, n + 1):
        if em[order[k - 1]] >= n / (alpha * k):
            k_star = k
    idx = np.where(m)[0][order[:k_star]]
    rej[idx] = True
    return rej
