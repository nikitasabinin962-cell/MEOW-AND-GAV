"""Контракт слоёв по рядам: DTW не сжимает календарь, лаговая стрелка только при однозначном максимуме."""
import numpy as np
import pandas as pd

from econtypes5 import timeseries as TS


def _frame(rows):
    cols = [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 13)]
    return pd.DataFrame(rows, columns=cols[: len(rows[0])])


def test_dtw_pair_with_internal_gap_is_undefined_not_compressed():
    rng = np.random.default_rng(1)
    base = np.sin(np.arange(24) / 3)
    a = base + rng.normal(0, .05, 24)
    b = base + rng.normal(0, .05, 24)
    c = base.copy()
    c[[5, 6, 7]] = np.nan  # пропуск внутри ряда
    S, info = TS.dtw_similarity(_frame([a, b, c]), w=2, min_obs=6)
    assert info["gap_pairs"] == 2
    assert np.isnan(info["D"][0, 2]) and np.isnan(info["D"][1, 2])
    assert S[0, 2] == 0 and S[1, 2] == 0 and S[0, 1] > 0


def test_dtw_leading_gap_uses_common_contiguous_window():
    base = np.sin(np.arange(24) / 3)
    a = base.copy()
    b = base.copy()
    b[:4] = np.nan  # ряд начинается позже: общее окно сплошное
    _, info = TS.dtw_similarity(_frame([a, b, a + 1e-3 * np.arange(24)]), w=2, min_obs=6)
    assert info["gap_pairs"] == 0
    assert np.isfinite(info["D"][0, 1]) and info["D"][0, 1] < 1e-9


def test_lead_lag_direction_only_when_unambiguous():
    rng = np.random.default_rng(3)
    x = rng.normal(size=26).cumsum()
    lead_series = x[2:]
    follow = x[:-2]  # тот же ряд на 2 мес. позже
    R = _frame([lead_series[:24], follow[:24]])
    S, lead, info = TS.lead_lag(R, max_lag=3, min_obs=6)
    assert lead[0, 1] == 0 or lead[1, 0] == -lead[0, 1]
    assert np.all(np.abs(info["r"][np.isfinite(info["r"])]) <= 1)
    assert info["status"] == "exploratory_no_fdr"
    # одинаковые ряды: максимум симметричен, направления нет
    same = _frame([x[:24], x[:24]])
    _, lead2, info2 = TS.lead_lag(same, max_lag=3, min_obs=6)
    assert lead2[0, 1] == 0 and lead2[1, 0] == 0
    assert info2["pairs_without_direction"] == 1


def test_lead_lag_negative_best_gives_no_arrow():
    rng = np.random.default_rng(5)
    x = rng.normal(size=24)
    R = _frame([x, -x])
    S, lead, info = TS.lead_lag(R, max_lag=1, min_obs=6)
    if np.nanmax(info["r"]) <= 0:
        assert lead[0, 1] == 0 and lead[1, 0] == 0 and S[0, 1] == 0


def test_lead_lag_clear_shift_gets_arrow():
    rng = np.random.default_rng(7)
    x = rng.normal(size=30).cumsum()
    a, b = x[3:27], x[1:25]  # a раньше b на 2 мес.
    _, lead, info = TS.lead_lag(_frame([a, b]), max_lag=3, min_obs=6)
    assert lead[0, 1] == 2 and lead[1, 0] == -2
    assert info["n_overlap"][0, 1] >= 6
