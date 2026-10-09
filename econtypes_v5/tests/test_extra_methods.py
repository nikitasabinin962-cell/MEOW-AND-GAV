import numpy as np
import pandas as pd
import pytest

from econtypes5 import extra_methods as EM, stats as S


def test_eci_normalization_and_sign():
    # «вложенная» структура: диверсифицированные регионы имеют и редкие, и распространённые отрасли
    rows = []
    for m in range(6):
        rows.append([10 if s <= m else 1 for s in range(6)])
    counts = pd.DataFrame(rows, index=[f"m{i}" for i in range(6)], columns=[f"s{j}" for j in range(6)])
    eci, pci, info = EM.economic_complexity(counts)
    assert np.isclose(eci.mean(), 0) and np.isclose(eci.std(ddof=0), 1)
    div = pd.Series(info["diversity"])
    assert eci.corr(div) >= 0          # знаковая нормировка: ECI неотрицательно связан с разнообразием
    assert info["eigenvalues"][0] == pytest.approx(1.0)   # стохастическая матрица: ведущее собственное число 1


def test_relatedness_density_bounds():
    rng = np.random.default_rng(0)
    counts = pd.DataFrame(rng.integers(0, 20, (8, 5)), index=list("abcdefgh"), columns=list("ABCDE"))
    d = EM.relatedness_density(counts)
    v = d.to_numpy()
    assert np.nanmin(v) >= 0 and np.nanmax(v) <= 1 + 1e-12


def test_ebh_more_conservative_than_bh_on_example():
    p = np.array([1e-6, 1e-4, 0.001, 0.01, 0.02, 0.3, 0.5, 0.8, np.nan])
    bh = S.fdr(p, "bh") < 0.05
    eb = EM.e_bh(p, 0.05)
    assert eb.sum() <= bh[np.isfinite(p)].sum() and eb[0]


def test_demographic_balance_identity():
    pop = pd.DataFrame({"2024-01-01": [1000.0, 2000.0], "2025-01-01": [990.0, 2010.0]}, index=[0, 1])
    facts = pd.DataFrame([dict(mo_id=0, indicator="births", period="2024", value=10, source_id="x"),
                          dict(mo_id=0, indicator="deaths", period="2024", value=15, source_id="x"),
                          dict(mo_id=0, indicator="migr_rate", period="2024", value=-50.0, source_id="x"),
                          dict(mo_id=1, indicator="births", period="2024", value=20, source_id="x"),
                          dict(mo_id=1, indicator="deaths", period="2024", value=10, source_id="x")])
    b = EM.demographic_balance(pop, facts, 2024)
    r0 = b.loc[0]
    assert r0.dN == -10 and r0.natural == -5
    assert r0.migration_est == pytest.approx(-50 * 995 / 10000)
    assert r0.residual_A == pytest.approx(-10 - (-5) - r0.migration_est)
    assert b.loc[1, "status"] == "data_gap"


def test_type_naming_respects_sign_of_rates():
    # тип с наименьшим оттоком не должен называться «миграционным притоком»
    from econtypes5.pipeline import plain
    assert plain("migr_rate", +1.3, -29.2) == "меньший миграционный отток"
    assert plain("migr_rate", +1.3, +4.0) == "миграционный приток"
    assert plain("migr_rate", -1.0, -104.7) == "сильный миграционный отток"
    assert plain("natinc_rate", -1.36, -9.9) == "сильная естественная убыль"
    assert plain("natinc_rate", +0.8, -2.0) == "меньшая естественная убыль"
    assert plain("sber_ilr2", -1.48, -0.3) == "выше доля общепита"
