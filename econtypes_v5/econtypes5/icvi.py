"""Внутренние индексы качества кластеризации (ICVI) v5 — исправленная версия.

Каждый индекс считается в явно названном пространстве:
  * пространство признаков X (n×p): SW, CH, DB, S_Dbw;
  * пространство сети W (n×n, неотрицательная, диагональ 0): AVI, AVU, MQ.

Отличия от econtypes v4 (reproduction/calculation_source/econtypes/icvi.py):
  1. AVU — опубликованный Average Unifiability (Biswas & Biswas 2017, ESWA 71:1–17,
     DOI 10.1016/j.eswa.2016.11.011; формулы 20–21 в Shalileh, Tsyplakova, Antonov,
     DOI 10.1134/S1064562425700589). Минимизируется. Прежний показатель
     d_in/(d_in+d_out) сохранён под именем ``intra_inter_density_ratio`` (авторский, ↑).
  2. MQ: считаются оба распространённых значения сокращения — модулярность Ньюмана
     (``MQ_newman``, γ указывается) и Modularization Quality Манкоридиса и др. 1998
     (``MQ_mancoridis``). Какой из них имеет в виду организатор, по доступным материалам
     не подтверждено — см. docs/METHODOLOGY_v5.md §ICVI.
  3. S_Dbw: реализация по Halkidi & Vazirgiannis (ICDM 2001) с явным выбором области
     подсчёта плотности центроидов (``density_scope``) и явными соглашениями для
     вырожденных случаев; вырожденные слагаемые считаются и возвращаются.
  4. Ни один индекс не возвращает «тихий» ноль на неопределённом входе: возвращается NaN
     и текстовый статус.

Обозначения для сетевых индексов. Для разбиения на K кластеров
  E_ab = Σ_{i∈C_a} Σ_{j∈C_b} W_ij,   B_a = Σ_{b≠a} E_ab.
При симметричной W внутренний вес E_aa учитывает каждую пару дважды (i,j) и (j,i).
  isolability_a = E_aa / (E_aa + B_a),                 AVI = mean_a isolability_a  (↑)
  U_ab = E_ab / (B_a + B_b − E_ab), a≠b,               AVU = (1/K) Σ_a Σ_{b≠a} U_ab (↓)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

# направление оптимизации каждого индекса
DIRECTION: dict[str, str] = {
    "SW": "max", "CH": "max", "DB": "min", "S_Dbw": "min",
    "AVI": "max", "AVU": "min", "MQ_newman": "max", "MQ_mancoridis": "max",
    "intra_inter_density_ratio": "max", "S_Dbw_floor1": "min",
}
SPACE: dict[str, str] = {
    "SW": "attributes", "CH": "attributes", "DB": "attributes", "S_Dbw": "attributes",
    "AVI": "network", "AVU": "network", "MQ_newman": "network", "MQ_mancoridis": "network",
    "intra_inter_density_ratio": "network", "S_Dbw_floor1": "attributes",
}
CORE = ["SW", "CH", "S_Dbw", "AVI", "AVU", "MQ_newman"]  # набор критерия конкурса (MQ = Newman по умолчанию)


@dataclass
class IndexResult:
    value: float
    status: str = "ok"
    details: dict = field(default_factory=dict)


def _labels(labels, n: int) -> tuple[np.ndarray, np.ndarray]:
    lab = np.asarray(labels)
    if lab.ndim != 1 or len(lab) != n:
        raise ValueError(f"labels: ожидался вектор длины {n}, получено {lab.shape}")
    classes, inv = np.unique(lab, return_inverse=True)
    return classes, inv


def _check_W(W: np.ndarray) -> np.ndarray:
    W = np.asarray(W, dtype=float)
    if W.ndim != 2 or W.shape[0] != W.shape[1]:
        raise ValueError(f"W должна быть квадратной, получено {W.shape}")
    if not np.isfinite(W).all():
        raise ValueError("W содержит NaN/inf: отсутствующие связи должны быть 0, неизвестные — исключены заранее")
    if (W < 0).any():
        raise ValueError("W содержит отрицательные веса; AVI/AVU/MQ определены для неотрицательных весов")
    if np.any(np.diag(W) != 0):
        raise ValueError("диагональ W должна быть нулевой (петли не являются экономической связью)")
    return W


def block_weights(W: np.ndarray, labels) -> tuple[np.ndarray, np.ndarray]:
    """Матрица E (K×K) сумм весов между кластерами и вектор классов."""
    W = _check_W(W)
    classes, inv = _labels(labels, len(W))
    K = len(classes)
    Z = np.zeros((len(W), K))
    Z[np.arange(len(W)), inv] = 1.0
    E = Z.T @ W @ Z
    return E, classes


def avi_avu(W: np.ndarray, labels, empty_isolability: str = "exclude") -> dict:
    """Опубликованные AVI (↑) и AVU (↓).

    Соглашения для нулевых знаменателей (возвращаются счётчики, ничего не скрывается):
      * isolability_a при E_aa + B_a = 0 (кластер без единого ребра — изолированные узлы):
        'exclude' — кластер исключается из среднего AVI (по умолчанию), 'zero' — считается 0.
      * U_ab при B_a + B_b − E_ab = 0. Знаменатель равен весу рёбер, инцидентных C_a или C_b
        и уходящих из пары. Он нулевой только при E_ab = 0 и отсутствии внешних связей у обоих
        кластеров; предел 0/0 доопределяем U_ab = 0 («пара не объединена»).
    K < 2: индексы не определены (NaN, status='undefined_K_lt_2').
    """
    E, classes = block_weights(W, labels)
    K = len(classes)
    out = dict(K=K, n_empty_clusters_isolability=0, n_zero_den_pairs=0)
    if K < 2:
        return dict(AVI=np.nan, AVU=np.nan, status="undefined_K_lt_2", **out)
    inside = np.diag(E).copy()
    outside = E.sum(axis=1) - inside
    incident = inside + outside
    iso = np.full(K, np.nan)
    ok = incident > 0
    iso[ok] = inside[ok] / incident[ok]
    out["n_empty_clusters_isolability"] = int((~ok).sum())
    if empty_isolability == "zero":
        iso[~ok] = 0.0
    elif empty_isolability != "exclude":
        raise ValueError("empty_isolability: 'exclude' | 'zero'")
    den = outside[:, None] + outside[None, :] - E
    U = np.zeros((K, K))
    off = ~np.eye(K, dtype=bool)
    pos = off & (den > 0)
    U[pos] = E[pos] / den[pos]
    out["n_zero_den_pairs"] = int((off & (den <= 0)).sum() // 2) if np.allclose(E, E.T) else int((off & (den <= 0)).sum())
    avi = float(np.nanmean(iso)) if np.isfinite(iso).any() else np.nan
    avu = float(U.sum() / K)
    status = "ok"
    if out["n_empty_clusters_isolability"] or out["n_zero_den_pairs"]:
        status = "ok_with_degenerate_terms"
    return dict(AVI=avi, AVU=avu, status=status, isolability=iso.tolist(), U=U.tolist(), **out)


def intra_inter_density_ratio(W: np.ndarray, labels) -> float:
    """Авторский показатель econtypes v4 (ранее ошибочно назывался AVU):
    mean_a d_in/(d_in + d_out), d_in = W(C_a,C_a)/(n_a(n_a−1)), d_out = W(C_a,V∖C_a)/(n_a(n−n_a)). ↑.
    Сохранён для сравнения; это НЕ Average Unifiability."""
    W = _check_W(W)
    classes, inv = _labels(labels, len(W))
    n = len(W)
    vals = []
    for a in range(len(classes)):
        s = inv == a
        na = int(s.sum())
        w_in = W[np.ix_(s, s)].sum()
        w_out = W[np.ix_(s, ~s)].sum()
        d_in = w_in / (na * (na - 1)) if na > 1 else np.nan
        d_out = w_out / (na * (n - na)) if n > na else np.nan
        if np.isfinite(d_in) and np.isfinite(d_out) and d_in + d_out > 0:
            vals.append(d_in / (d_in + d_out))
    return float(np.mean(vals)) if vals else np.nan


def newman_modularity(W: np.ndarray, labels, gamma: float = 1.0) -> dict:
    """Взвешенная модулярность Ньюмана (Newman 2004, Phys. Rev. E 70:056131; γ — Reichardt & Bornholdt 2006):
        Q = (1/2m) Σ_ij [W_ij − γ k_i k_j / (2m)] δ(c_i, c_j),  2m = Σ_ij W_ij, k_i = Σ_j W_ij.
    Предполагается неориентированный граф (симметричная W). Для несимметричной W используется
    ориентированная форма Leicht & Newman (2008): Q = (1/m) Σ_ij [W_ij − γ k_i^out k_j^in / m] δ."""
    W = _check_W(W)
    _, inv = _labels(labels, len(W))
    tot = W.sum()
    if tot <= 0:
        return dict(value=np.nan, status="undefined_empty_graph", gamma=gamma, symmetric=True)
    same = inv[:, None] == inv[None, :]
    if np.allclose(W, W.T):
        k = W.sum(1)
        Q = ((W - gamma * np.outer(k, k) / tot) * same).sum() / tot
        return dict(value=float(Q), status="ok", gamma=gamma, symmetric=True)
    kout, kin = W.sum(1), W.sum(0)
    Q = ((W - gamma * np.outer(kout, kin) / tot) * same).sum() / tot
    return dict(value=float(Q), status="ok_directed", gamma=gamma, symmetric=False)


def mancoridis_mq(W: np.ndarray, labels) -> dict:
    """Modularization Quality (Mancoridis, Mitchell, Rorres, Chen, Gansner, IWPC 1998), взвешенная форма:
        A_i = μ_i / N_i²,   E_ij = ε_ij / (2 N_i N_j),
        MQ = (1/K) Σ_i A_i − (1/(K(K−1)/2)) Σ_{i<j} E_ij  (K>1);  MQ = A_1 (K=1).
    μ_i — суммарный вес ориентированных внутренних пар (для симметричной W = E_ii),
    ε_ij — суммарный вес пар между кластерами в обе стороны (E_ij + E_ji). Диапазон [−1, 1] при весах ≤ 1."""
    E, classes = block_weights(W, labels)
    _, inv = _labels(labels, len(W))
    sizes = np.bincount(inv).astype(float)
    K = len(classes)
    A = np.diag(E) / sizes ** 2
    if K == 1:
        return dict(value=float(A[0]), status="K_eq_1")
    iu = np.triu_indices(K, 1)
    eps = (E + E.T)[iu]
    Eij = eps / (2 * sizes[iu[0]] * sizes[iu[1]])
    return dict(value=float(A.mean() - Eij.sum() / (K * (K - 1) / 2)), status="ok")


def s_dbw(X: np.ndarray, labels, density_scope: str = "union", undefined_terms: str = "nan") -> dict:
    """S_Dbw (Halkidi & Vazirgiannis 2001, Proc. IEEE ICDM, pp. 187–194). ↓.

        σ(·) — вектор покомпонентных дисперсий, ‖x‖ = (xᵀx)^{1/2};
        Scat = (1/K) Σ_i ‖σ(v_i)‖ / ‖σ(S)‖;
        stdev = (1/K) (Σ_i ‖σ(v_i)‖)^{1/2}  — общий радиус окрестности;
        density(u; P) = #{x ∈ P : ‖x − u‖ ≤ stdev};
        Dens_bw = (1/(K(K−1))) Σ_i Σ_{j≠i} density(u_ij; C_i∪C_j) / max(density(v_i; ·), density(v_j; ·)),
        u_ij — середина отрезка между центроидами v_i и v_j;  S_Dbw = Scat + Dens_bw.

    density_scope:
      'union' — плотность центроидов v_i и v_j считается по точкам C_i ∪ C_j (так записано
                в оригинальной публикации: n_ij — число точек обоих кластеров; так же считала v4);
      'own'   — плотность центроида v_i считается только по точкам собственного кластера C_i
                (вариант, встречающийся в пересказах; оставлен для чувствительности).
    Вырожденные случаи (возвращаются в details):
      ‖σ(S)‖ = 0 — все точки совпадают → NaN, status 'undefined_zero_total_variance';
      stdev = 0 (все кластеры — точки) допускается: окрестность включает только совпадающие точки;
      знаменатель 0 и числитель 0 → слагаемое 0; знаменатель 0 и числитель > 0 — отношение не
      ограничено (середина плотнее центроидов, т.е. разделение плохое). undefined_terms:
        'nan'     — индекс NaN, status 'undefined_density_ratio' (строгое определение, по умолчанию);
        'floor1'  — знаменатель max(den, 1): ограниченный вариант, помечается в status;
        'v4_zero' — слагаемое 0, как в econtypes v4 (воспроизведение; ошибочно поощряет плохое разделение).
      Радиус stdev убывает как 1/K, поэтому в многомерном X нулевая плотность у центроида —
      частый, а не экзотический случай; число таких слагаемых всегда возвращается.
    Синглтоны допустимы: σ(v_i) = 0.
    """
    X = np.asarray(X, dtype=float)
    if not np.isfinite(X).all():
        raise ValueError("X содержит NaN/inf: импутация/исключение должны быть сделаны до расчёта ICVI")
    classes, inv = _labels(labels, len(X))
    K = len(classes)
    det = dict(K=K, density_scope=density_scope, n_zero_den_terms=0, n_undefined_terms=0)
    if K < 2:
        return dict(value=np.nan, status="undefined_K_lt_2", **det)
    tot = np.linalg.norm(X.var(axis=0))
    if tot == 0:
        return dict(value=np.nan, status="undefined_zero_total_variance", **det)
    cents = np.array([X[inv == a].mean(axis=0) for a in range(K)])
    sig = np.array([np.linalg.norm(X[inv == a].var(axis=0)) for a in range(K)])
    scat = float(sig.mean() / tot)
    stdev = float(np.sqrt(sig.sum()) / K)

    def density(u, mask):
        return int(np.sum(np.linalg.norm(X[mask] - u, axis=1) <= stdev))

    terms = []
    for i in range(K):
        for j in range(K):
            if i == j:
                continue
            m = (inv == i) | (inv == j)
            num = density((cents[i] + cents[j]) / 2, m)
            if density_scope == "union":
                di, dj = density(cents[i], m), density(cents[j], m)
            elif density_scope == "own":
                di, dj = density(cents[i], inv == i), density(cents[j], inv == j)
            else:
                raise ValueError("density_scope: 'union' | 'own'")
            den = max(di, dj)
            if den == 0:
                det["n_zero_den_terms"] += 1
                if num == 0:
                    terms.append(0.0)
                else:
                    det["n_undefined_terms"] += 1
                    if undefined_terms == "nan":
                        terms.append(np.nan)
                    elif undefined_terms == "floor1":
                        terms.append(float(num))
                    elif undefined_terms == "v4_zero":
                        terms.append(0.0)
                    else:
                        raise ValueError("undefined_terms: 'nan' | 'floor1' | 'v4_zero'")
            else:
                terms.append(num / den)
    if det["n_undefined_terms"] and undefined_terms == "nan":
        return dict(value=np.nan, status="undefined_density_ratio", scat=scat, stdev=stdev, **det)
    dens = float(np.sum(terms) / (K * (K - 1)))
    status = "ok" if det["n_zero_den_terms"] == 0 else "ok_with_zero_density_terms"
    if det["n_undefined_terms"]:
        status = f"convention_{undefined_terms}_applied"
    return dict(value=scat + dens, status=status, scat=scat, dens_bw=dens, stdev=stdev, **det)


def _sk(fn, X, inv, K, n):
    if K < 2:
        return np.nan, "undefined_K_lt_2"
    if K > n - 1:
        return np.nan, "undefined_K_ge_N"
    return float(fn(X, inv)), "ok"


def all_indices(X: np.ndarray | None, W: np.ndarray | None, labels, gamma: float = 1.0,
                sdbw_scope: str = "union", sdbw_undefined: str = "nan") -> dict:
    """Все индексы с указанием пространства. X или W может быть None — тогда индексы этого
    пространства не считаются (NaN, status 'not_computed_no_input')."""
    lab = np.asarray(labels)
    out: dict = {}
    status: dict = {}
    if X is not None:
        X = np.asarray(X, dtype=float)
        classes, inv = _labels(lab, len(X))
        K, n = len(classes), len(X)
        for name, fn in (("SW", silhouette_score), ("CH", calinski_harabasz_score), ("DB", davies_bouldin_score)):
            out[name], status[name] = _sk(fn, X, inv, K, n)
        r = s_dbw(X, inv, sdbw_scope, sdbw_undefined)
        out["S_Dbw"], status["S_Dbw"] = r["value"], r["status"]
        out["S_Dbw_floor1"] = s_dbw(X, inv, sdbw_scope, "floor1")["value"] if r["n_undefined_terms"] else r["value"]
        status["S_Dbw_floor1"] = "floor1_variant" if r["n_undefined_terms"] else r["status"]
        out["S_Dbw_undefined_terms"] = r["n_undefined_terms"]
    else:
        for name in ("SW", "CH", "DB", "S_Dbw", "S_Dbw_floor1"):
            out[name], status[name] = np.nan, "not_computed_no_input"
    if W is not None:
        r = avi_avu(W, lab)
        out["AVI"], out["AVU"] = r["AVI"], r["AVU"]
        status["AVI"] = status["AVU"] = r["status"]
        q = newman_modularity(W, lab, gamma)
        out["MQ_newman"], status["MQ_newman"] = q["value"], q["status"]
        mq = mancoridis_mq(W, lab)
        out["MQ_mancoridis"], status["MQ_mancoridis"] = mq["value"], mq["status"]
        out["intra_inter_density_ratio"] = intra_inter_density_ratio(W, lab)
        status["intra_inter_density_ratio"] = "authorial_v4_metric"
    else:
        for name in ("AVI", "AVU", "MQ_newman", "MQ_mancoridis", "intra_inter_density_ratio"):
            out[name], status[name] = np.nan, "not_computed_no_input"
    out["_status"] = status
    return out


def permutation_null(X, W, labels, B: int = 199, seed: int = 0, indices: list[str] | None = None) -> dict:
    """Нулевое распределение ICVI при случайной перестановке меток с теми же размерами кластеров.

    Возвращает для каждого индекса: наблюдаемое значение, среднее/sd нуля, z со знаком
    «больше = лучше» и одностороннее эмпирическое p = (b+1)/(B+1), где b — число
    перестановок не хуже наблюдаемого в направлении оптимизации. Сохраняются B и seed.
    z не является p-значением и не является универсальной мерой качества."""
    indices = indices or [k for k in DIRECTION if k != "intra_inter_density_ratio"]
    rng = np.random.default_rng(seed)
    lab = np.asarray(labels)
    obs = all_indices(X, W, lab)
    null = {k: [] for k in indices}
    for _ in range(B):
        r = all_indices(X, W, rng.permutation(lab))
        for k in indices:
            null[k].append(r[k])
    res = {}
    for k in indices:
        v = np.asarray(null[k], dtype=float)
        o = obs[k]
        if not np.isfinite(o) or np.isfinite(v).sum() < 2:
            res[k] = dict(observed=o, null_mean=np.nan, null_sd=np.nan, z=np.nan, p=np.nan, B=B, seed=seed,
                          direction=DIRECTION[k])
            continue
        v = v[np.isfinite(v)]
        sd = v.std(ddof=1)
        sign = 1.0 if DIRECTION[k] == "max" else -1.0
        z = sign * (o - v.mean()) / sd if sd > 0 else np.nan
        b = int(np.sum(sign * v >= sign * o))
        res[k] = dict(observed=float(o), null_mean=float(v.mean()), null_sd=float(sd), z=float(z) if np.isfinite(z) else np.nan,
                      p=(b + 1) / (len(v) + 1), B=int(len(v)), B_requested=B, seed=seed, direction=DIRECTION[k],
                      null_q025=float(np.quantile(v, 0.025)), null_q975=float(np.quantile(v, 0.975)))
    return res
