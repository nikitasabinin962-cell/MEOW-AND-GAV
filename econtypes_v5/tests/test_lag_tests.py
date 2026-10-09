"""scripts/lag_tests.py: совпадение с функцией прогона, нуль без сигнала, найденный сдвиг при сигнале."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location("lag_tests", Path(__file__).resolve().parents[1] / "scripts" / "lag_tests.py")
LT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LT)

COLS = [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 13)]


def test_pure_noise_gives_no_significant_pairs():
    rng = np.random.default_rng(11)
    R = pd.DataFrame(rng.normal(size=(12, 24)).cumsum(1), index=range(12), columns=COLS)
    df, s = LT.run(R, max_lag=3, min_obs=6, B=199, seed=1)
    assert s["agrees_with_run_function"]
    assert s["sig_bh_005"] == 0
    assert len(df) == 12 * 11 and df.p_perm.between(1 / 200, 1).all()


def test_planted_shift_is_found_with_right_lag_and_direction():
    rng = np.random.default_rng(3)
    x = rng.normal(size=40).cumsum()
    rows = [x[5:29], x[3:27]] + [rng.normal(size=24).cumsum() for _ in range(6)]  # ряд 0 раньше ряда 1 на 2 мес.
    R = pd.DataFrame(rows, index=range(8), columns=COLS)
    df, s = LT.run(R, max_lag=3, min_obs=6, B=499, seed=2)
    e = df[(df.mo_i == 0) & (df.mo_j == 1)].iloc[0]
    assert e.lag_months == 2 and e.direction == 1 and e.r > 0.99
    assert e.p_perm <= 0.01 and e.jk_dir_stability >= 0.9


def test_series_with_gap_is_not_tested():
    rng = np.random.default_rng(4)
    R = pd.DataFrame(rng.normal(size=(5, 24)).cumsum(1), index=[10, 11, 12, 13, 44], columns=COLS)
    R.iloc[4, [7, 8]] = np.nan
    df, s = LT.run(R, max_lag=3, min_obs=6, B=99, seed=0)
    assert s["nodes_not_tested"] == [44] and 44 not in set(df.mo_i) | set(df.mo_j)
