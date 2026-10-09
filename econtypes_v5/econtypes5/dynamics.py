"""Динамика типов: выравнивание меток, переходы, события split/merge/birth/death.

Для периодов t−1 и t и общего множества МО V_c = V_{t−1} ∩ V_t:
  N_ab = |C_a^{(t−1)} ∩ C_b^{(t)} ∩ V_c|
  T_ab = N_ab / |C_a^{(t−1)} ∩ V_c|                 — доля типа a, перешедшая в b;
  J_ab = N_ab / |(C_a^{(t−1)} ∪ C_b^{(t)}) ∩ V_c|  — Jaccard-перекрытие.
Выравнивание номеров — венгерский алгоритм на матрице N (максимум суммарного пересечения).
Событие (порог θ, по умолчанию T ≥ 0.3 и не менее 2 МО):
  continuation — a имеет ровно одного преемника b, и b имеет ровно одного предшественника a;
  split        — у a не менее двух преемников;
  merge        — у b не менее двух предшественников;
  death        — у a нет преемника; birth — у b нет предшественника.
Выравнивание номера не означает сохранения экономического содержания: изменение профиля
типа возвращается отдельно (profile_shift).
Приход/выход МО (V_t ∖ V_{t−1}, V_{t−1} ∖ V_t) перечисляется отдельно.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score, mutual_info_score


def contingency(prev: pd.Series, cur: pd.Series) -> tuple[pd.DataFrame, list]:
    common = prev.index.intersection(cur.index)
    p, c = prev.loc[common], cur.loc[common]
    return pd.crosstab(p.rename("from"), c.rename("to")), list(common)


def hungarian_align(cur: pd.Series, ref: pd.Series) -> pd.Series:
    """Переименовать метки cur так, чтобы максимизировать совпадение с ref на общих МО.
    Новые кластеры без пары получают номера после максимального номера ref."""
    N, _ = contingency(ref, cur)
    ref_ids, cur_ids = list(N.index), list(N.columns)
    r, c = linear_sum_assignment(-N.to_numpy())
    mp = {cur_ids[j]: ref_ids[i] for i, j in zip(r, c)}
    nxt = (int(ref.max()) + 1) if len(ref) else 0
    for x in sorted(cur.unique()):
        if x not in mp:
            mp[x] = nxt
            nxt += 1
    return cur.map(mp)


def variation_of_information(a, b) -> float:
    """VI (Meilă 2007) в натах: H(A) + H(B) − 2 I(A;B)."""
    a, b = np.asarray(a), np.asarray(b)

    def H(x):
        _, c = np.unique(x, return_counts=True)
        p = c / c.sum()
        return float(-(p * np.log(p)).sum())
    return H(a) + H(b) - 2 * float(mutual_info_score(a, b))


def transition_tables(prev: pd.Series, cur: pd.Series) -> dict:
    N, common = contingency(prev, cur)
    rows = N.sum(axis=1)
    cols = N.sum(axis=0)
    T = N.div(rows, axis=0)
    J = N / (rows.to_numpy()[:, None] + cols.to_numpy()[None, :] - N.to_numpy())
    return dict(N=N, T=T, J=pd.DataFrame(J, index=N.index, columns=N.columns), common=common)


def events(prev: pd.Series, cur: pd.Series, theta: float = 0.3, min_nodes: int = 2) -> list[dict]:
    tt = transition_tables(prev, cur)
    N, T = tt["N"], tt["T"]
    succ = {a: [b for b in N.columns if T.loc[a, b] >= theta and N.loc[a, b] >= min_nodes] for a in N.index}
    pred = {b: [a for a in N.index if b in succ[a]] for b in N.columns}
    ev = []
    for a, bs in succ.items():
        if len(bs) == 0:
            ev.append(dict(event="death", from_cluster=int(a), to_cluster=None, size=int(N.loc[a].sum())))
        elif len(bs) >= 2:
            ev.append(dict(event="split", from_cluster=int(a), to_cluster=[int(b) for b in bs], size=int(N.loc[a].sum())))
    for b, as_ in pred.items():
        if len(as_) == 0:
            ev.append(dict(event="birth", from_cluster=None, to_cluster=int(b), size=int(N[b].sum())))
        elif len(as_) >= 2:
            ev.append(dict(event="merge", from_cluster=[int(a) for a in as_], to_cluster=int(b), size=int(N[b].sum())))
    for a, bs in succ.items():
        if len(bs) == 1 and len(pred[bs[0]]) == 1:
            ev.append(dict(event="continuation", from_cluster=int(a), to_cluster=int(bs[0]),
                           size=int(N.loc[a, bs[0]]), jaccard=float(tt["J"].loc[a, bs[0]])))
    return ev


def node_flux(prev: pd.Series, cur: pd.Series) -> dict:
    return dict(entered=sorted(set(cur.index) - set(prev.index)), exited=sorted(set(prev.index) - set(cur.index)))


def profile_shift(X_prev: pd.DataFrame, lab_prev: pd.Series, X_cur: pd.DataFrame, lab_cur: pd.Series) -> pd.DataFrame:
    """Сдвиг медианного профиля выровненного типа между периодами (в единицах признаков)."""
    rows = []
    for c in sorted(set(lab_prev) & set(lab_cur)):
        a = X_prev.loc[lab_prev[lab_prev == c].index].median()
        b = X_cur.loc[lab_cur[lab_cur == c].index].median()
        d = (b - a)
        rows.append(dict(cluster=int(c), l2_shift=float(np.sqrt((d ** 2).sum())), **{f"d_{k}": float(v) for k, v in d.items()}))
    return pd.DataFrame(rows)


def sequence_summary(labels: pd.DataFrame, theta: float = 0.3) -> dict:
    """labels: МО × периоды (уже выровненные). ARI/VI между соседними периодами и события."""
    cols = list(labels.columns)
    out = []
    for a, b in zip(cols[:-1], cols[1:]):
        pa, pb = labels[a].dropna().astype(int), labels[b].dropna().astype(int)
        common = pa.index.intersection(pb.index)
        out.append(dict(from_period=str(a), to_period=str(b), n_common=len(common),
                        ARI=float(adjusted_rand_score(pa[common], pb[common])),
                        VI=variation_of_information(pa[common], pb[common]),
                        switches=int((pa[common] != pb[common]).sum()),
                        events=events(pa, pb, theta), **node_flux(pa, pb)))
    return dict(pairs=out)
