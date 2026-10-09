"""Лаговые связи прогона: значимость с поправкой на множественность и устойчивость.

Ряды и правило те же, что у слоя lead_lag в прогоне: остатки log-трат СберИндекса за F.MONTHS,
помесячные приращения, сдвиг 1..max_lag, статистика r_ij = max_l corr(Δr_i(t), Δr_j(t+l)).

Нуль: фазовая рандомизация ряда j (спектр и автокорреляция сохраняются, связь с i разрушается),
ряд i не трогаем; p = (b+1)/(B+1). Поправка BH и BY по всем проверенным упорядоченным парам.
Устойчивость: jackknife по месяцам приращений (убираем один месяц из выравнивания), доля
повторов, где совпали лучший сдвиг и направление.

Пары с пропусками внутри ряда (МО 44) не проверяются: фазовая рандомизация требует сплошного ряда.
W, типы и база прогона не меняются: это диагностика того же run_id.

  .venv/bin/python scripts/lag_tests.py            # → outputs/latest/LAG_EDGE_TESTS.csv, LAG_EDGE_SUMMARY.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from econtypes5 import features as F, stats as S, timeseries as TS  # noqa: E402

TOL = 1e-9


def lagged_corr(D: np.ndarray, Dj: np.ndarray, l: int, keep: np.ndarray | None = None) -> np.ndarray:
    """corr(D_i(t), Dj_j(t+l)) для всех пар сразу; строки сплошные. keep — маска позиций t."""
    A, B = D[:, :-l], Dj[:, l:]
    if keep is not None:
        A, B = A[:, keep], B[:, keep]
    za = (A - A.mean(1, keepdims=True)) / A.std(1, keepdims=True)
    zb = (B - B.mean(1, keepdims=True)) / B.std(1, keepdims=True)
    return np.clip(za @ zb.T / A.shape[1], -1, 1)


def best_over_lags(D, Dj, max_lag, drop=None):
    """Максимум по сдвигам, лучший сдвиг и признак ничьей. drop — индекс месяца приращений, который убираем."""
    T = D.shape[1]
    stack = []
    for l in range(1, max_lag + 1):
        keep = None
        if drop is not None:
            t = np.arange(T - l)
            keep = (t != drop) & (t + l != drop)
        stack.append(lagged_corr(D, Dj, l, keep))
    R = np.stack(stack)
    best = R.max(0)
    lag = R.argmax(0) + 1
    tie = (np.abs(R - best) <= TOL).sum(0) > 1
    return best, lag, tie


def direction(best, tie):
    """+1: i раньше j, −1: j раньше i, 0: направления нет (то же правило, что в timeseries.lead_lag)."""
    fwd = (best > best.T + TOL) & (best > 0) & ~tie
    bwd = (best.T > best + TOL) & (best.T > 0) & ~tie.T
    d = np.where(fwd, 1, np.where(bwd, -1, 0))
    np.fill_diagonal(d, 0)
    return d


def phase_surrogate(D: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    n, T = D.shape
    X = np.fft.rfft(D, axis=1)
    ph = rng.uniform(0, 2 * np.pi, size=X.shape)
    ph[:, 0] = 0
    if T % 2 == 0:
        ph[:, -1] = 0
    return np.fft.irfft(np.abs(X) * np.exp(1j * (np.angle(X) + ph)), n=T, axis=1)


def run(R: pd.DataFrame, max_lag: int, min_obs: int, B: int, seed: int) -> tuple[pd.DataFrame, dict]:
    Dfull = R.diff(axis=1).iloc[:, 1:]
    ok = Dfull.notna().all(1).to_numpy()
    ids = np.asarray(R.index)
    D = Dfull.to_numpy(float)[ok]
    n, T = D.shape
    if T - max_lag < min_obs:
        raise SystemExit(f"короткий ряд: {T} приращений при сдвиге до {max_lag}")
    best, lag, tie = best_over_lags(D, D, max_lag)
    dirm = direction(best, tie)

    # сверка с функцией прогона на сплошных рядах: числа должны совпасть
    _, lead_run, info = TS.lead_lag(R.iloc[np.flatnonzero(ok)], max_lag, min_obs)
    rr = info["r"]
    off = ~np.eye(n, dtype=bool)
    agree = bool(np.allclose(rr[off], best[off], atol=1e-9) and np.array_equal(np.sign(lead_run), dirm))

    rng = np.random.default_rng(seed)
    exceed = np.zeros((n, n))
    for _ in range(B):
        sb, _, _ = best_over_lags(D, phase_surrogate(D, rng), max_lag)
        exceed += sb >= best - TOL
    p = (exceed + 1) / (B + 1)

    # jackknife по месяцам приращений
    same_lag = np.zeros((n, n))
    same_dir = np.zeros((n, n))
    for m in range(T):
        bm, lm, tm = best_over_lags(D, D, max_lag, drop=m)
        same_lag += lm == lag
        same_dir += direction(bm, tm) == dirm

    iu = np.where(off)
    pv = p[iu]
    q_bh, q_by = S.fdr(pv, "bh"), S.fdr(pv, "by")
    df = pd.DataFrame(dict(
        mo_i=ids[ok][iu[0]].astype(int), mo_j=ids[ok][iu[1]].astype(int),
        r=best[iu].round(4), lag_months=lag[iu], n_overlap=T - lag[iu], tie=tie[iu],
        direction=dirm[iu], p_perm=pv.round(5), q_bh=q_bh.round(5), q_by=q_by.round(5),
        jk_lag_stability=(same_lag[iu] / T).round(3), jk_dir_stability=(same_dir[iu] / T).round(3)))
    df["status"] = np.select(
        [(df.direction == 1) & (df.q_bh < 0.05) & (df.jk_dir_stability >= 0.8) & (df.jk_lag_stability >= 0.8),
         df.q_bh < 0.05],
        ["стрелка: значима (BH 5%) и устойчива", "связь значима (BH 5%), направление не подтверждено"],
        "разведочно: не значима после поправки")
    skipped = [int(x) for x in ids[~ok]]
    arrows = df[df.direction == 1]
    summ = dict(
        months=list(map(str, R.columns)), increments=T, max_lag=max_lag, B=B, seed=seed,
        null="фазовая рандомизация ряда j, i фиксирован; p=(b+1)/(B+1)",
        nodes_tested=int(n), nodes_not_tested=skipped,
        not_tested_reason="пропуски внутри ряда или нет ряда (фазовая рандомизация требует сплошного ряда)",
        ordered_pairs_tested=int(len(df)), agrees_with_run_function=agree,
        sig_bh_005=int((df.q_bh < 0.05).sum()), sig_by_005=int((df.q_by < 0.05).sum()),
        arrows_total=int(len(arrows)), arrows_sig_bh=int((arrows.q_bh < 0.05).sum()),
        arrows_sig_stable=int((df.status == "стрелка: значима (BH 5%) и устойчива").sum()),
        unordered_pairs_without_direction=int((((dirm == 0) & off).sum()) // 2),
        r_range=[float(best[off].min().round(3)), float(best[off].max().round(3))],
        min_p=float(1 / (B + 1)),
        rule="стрелку показывать как установленную только при q_BH < 0,05, jackknife-устойчивости сдвига и направления ≥ 0,8; иначе «разведочно». Причинность не утверждается в любом случае.")
    return df, summ


def main():
    cfg = yaml.safe_load((ROOT / "config" / "config_v5.yaml").read_text("utf-8"))
    nc = cfg.get("network", cfg)
    max_lag, min_obs = int(nc.get("max_lag", 3)), int(nc.get("min_obs", 6))
    man = json.loads((ROOT / "outputs" / "latest" / "RUN_MANIFEST.json").read_text("utf-8"))
    d = F.Data(str(ROOT / cfg["database"]))
    Y = d.spend[F.MONTHS]
    Y = Y[Y.notna().any(axis=1)]
    R, _ = TS.residual_series(Y)
    df, summ = run(R, max_lag, min_obs, B=int(cfg.get("lag_test_B", 999)), seed=int(man["seed"]))
    names = d.mo.name.to_dict()
    df.insert(1, "name_i", df.mo_i.map(names))
    df.insert(3, "name_j", df.mo_j.map(names))
    out = ROOT / "outputs" / "latest"
    df.insert(0, "run_id", man["run_id"])
    df.to_csv(out / "LAG_EDGE_TESTS.csv", index=False)
    summ = dict(run_id=man["run_id"], script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16], **summ)
    (out / "LAG_EDGE_SUMMARY.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({k: summ[k] for k in ("run_id", "ordered_pairs_tested", "sig_bh_005", "sig_by_005", "arrows_total",
                                           "arrows_sig_bh", "arrows_sig_stable", "agrees_with_run_function", "nodes_not_tested")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
