"""Проверка ICVI против независимых реализаций (циклы по узлам) и аналитических случаев."""
import itertools

import numpy as np
import pytest

from econtypes5 import icvi


# ---------- независимая «наивная» реализация AVI/AVU (по определению, через циклы) ----------
def naive_avi_avu(W, lab):
    ks = sorted(set(lab.tolist()))
    n = len(lab)
    E = {}
    for a in ks:
        for b in ks:
            s = 0.0
            for i in range(n):
                for j in range(n):
                    if lab[i] == a and lab[j] == b:
                        s += W[i][j]
            E[a, b] = s
    B = {a: sum(E[a, b] for b in ks if b != a) for a in ks}
    iso = [E[a, a] / (E[a, a] + B[a]) for a in ks if E[a, a] + B[a] > 0]
    U = 0.0
    for a in ks:
        for b in ks:
            if a != b:
                den = B[a] + B[b] - E[a, b]
                U += E[a, b] / den if den > 0 else 0.0
    return sum(iso) / len(iso), U / len(ks)


def rand_graph(n, p, rng):
    A = (rng.random((n, n)) < p) * rng.random((n, n))
    A = np.triu(A, 1)
    return A + A.T


@pytest.mark.parametrize("seed", range(8))
def test_avi_avu_matches_naive(seed):
    rng = np.random.default_rng(seed)
    n = int(rng.integers(6, 15))
    W = rand_graph(n, 0.5, rng)
    K = int(rng.integers(2, min(5, n)))
    lab = rng.integers(0, K, n)
    if len(set(lab)) < 2:
        lab[0], lab[1] = 0, 1
    r = icvi.avi_avu(W, lab)
    a, u = naive_avi_avu(W, lab)
    assert r["AVI"] == pytest.approx(a, abs=1e-12)
    assert r["AVU"] == pytest.approx(u, abs=1e-12)


def test_label_permutation_invariance():
    rng = np.random.default_rng(1)
    W = rand_graph(12, 0.6, rng)
    lab = np.repeat([0, 1, 2], 4)
    perm = {0: 7, 1: 3, 2: 5}
    lab2 = np.array([perm[x] for x in lab])
    r1, r2 = icvi.avi_avu(W, lab), icvi.avi_avu(W, lab2)
    assert r1["AVI"] == pytest.approx(r2["AVI"]) and r1["AVU"] == pytest.approx(r2["AVU"])
    # перенумерация узлов (одновременная перестановка W и меток) тоже не меняет индексы
    p = rng.permutation(12)
    r3 = icvi.avi_avu(W[np.ix_(p, p)], lab[p])
    assert r1["AVU"] == pytest.approx(r3["AVU"])


def test_three_isolated_cliques():
    lab = np.repeat(np.arange(3), 4)
    A = (lab[:, None] == lab[None, :]).astype(float)
    np.fill_diagonal(A, 0)
    r = icvi.avi_avu(A, lab)
    assert r["AVI"] == 1.0 and r["AVU"] == 0.0
    # старый авторский показатель даёт 1 — именно поэтому он не является AVU
    assert icvi.intra_inter_density_ratio(A, lab) == 1.0
    assert r["n_zero_den_pairs"] == 3  # три пары кластеров без внешних связей: соглашение 0/0 → 0


@pytest.mark.parametrize("K,s", [(2, 3), (3, 4), (4, 5)])
def test_complete_graph_analytic(K, s):
    n = K * s
    W = np.ones((n, n)) - np.eye(n)
    lab = np.repeat(np.arange(K), s)
    r = icvi.avi_avu(W, lab)
    assert r["AVI"] == pytest.approx(s * (s - 1) / (s * (s - 1) + (K - 1) * s * s))
    assert r["AVU"] == pytest.approx((K - 1) / (2 * K - 3))


def test_avu_direction_and_better_partition_lower():
    # планted partition: внутри 1, между 0.05 → правильное разбиение имеет меньший AVU, чем случайное
    rng = np.random.default_rng(3)
    lab = np.repeat(np.arange(3), 6)
    W = np.where(lab[:, None] == lab[None, :], 1.0, 0.05)
    np.fill_diagonal(W, 0)
    good = icvi.avi_avu(W, lab)
    bad = icvi.avi_avu(W, rng.permutation(lab))
    assert icvi.DIRECTION["AVU"] == "min" and icvi.DIRECTION["AVI"] == "max"
    assert good["AVU"] < bad["AVU"] and good["AVI"] > bad["AVI"]


def test_K1_and_singletons():
    W = np.ones((5, 5)) - np.eye(5)
    assert icvi.avi_avu(W, np.zeros(5, int))["status"] == "undefined_K_lt_2"
    r = icvi.avi_avu(W, np.arange(5))
    assert r["AVI"] == 0.0 and np.isfinite(r["AVU"])
    res = icvi.all_indices(np.random.default_rng(0).normal(size=(5, 2)), W, np.arange(5))
    assert np.isnan(res["SW"]) and res["_status"]["SW"] == "undefined_K_ge_N"


def test_isolated_singleton_isolability_excluded_and_counted():
    W = np.zeros((5, 5))
    W[0, 1] = W[1, 0] = 1
    W[2, 3] = W[3, 2] = 1
    lab = np.array([0, 0, 1, 1, 2])  # узел 4 — изолят-синглтон
    r = icvi.avi_avu(W, lab)
    assert r["n_empty_clusters_isolability"] == 1
    assert r["AVI"] == pytest.approx(1.0)
    rz = icvi.avi_avu(W, lab, empty_isolability="zero")
    assert rz["AVI"] == pytest.approx(2 / 3)


def test_invalid_W_rejected():
    with pytest.raises(ValueError):
        icvi.avi_avu(np.array([[0, -1], [-1, 0.]]), np.array([0, 1]))
    with pytest.raises(ValueError):
        icvi.avi_avu(np.array([[1, 1], [1, 0.]]), np.array([0, 1]))
    with pytest.raises(ValueError):
        icvi.avi_avu(np.array([[0, np.nan], [np.nan, 0.]]), np.array([0, 1]))


# ---------- модулярность ----------
def naive_modularity(W, lab, gamma=1.0):
    n = len(lab)
    m2 = W.sum()
    k = W.sum(1)
    return sum((W[i, j] - gamma * k[i] * k[j] / m2) for i in range(n) for j in range(n) if lab[i] == lab[j]) / m2


@pytest.mark.parametrize("gamma", [0.5, 1.0, 2.0])
def test_modularity_matches_naive_and_networkx(gamma):
    import networkx as nx
    rng = np.random.default_rng(5)
    W = rand_graph(14, 0.4, rng)
    lab = rng.integers(0, 3, 14)
    q = icvi.newman_modularity(W, lab, gamma)["value"]
    assert q == pytest.approx(naive_modularity(W, lab, gamma), abs=1e-12)
    G = nx.from_numpy_array(W)
    comms = [set(np.where(lab == c)[0]) for c in np.unique(lab)]
    assert q == pytest.approx(nx.community.modularity(G, comms, weight="weight", resolution=gamma), abs=1e-10)


def test_mancoridis_bounds_and_cliques():
    lab = np.repeat(np.arange(3), 4)
    A = (lab[:, None] == lab[None, :]).astype(float)
    np.fill_diagonal(A, 0)
    r = icvi.mancoridis_mq(A, lab)
    assert r["value"] == pytest.approx(12 / 16)  # A_i = s(s−1)/s² = 0.75, E_ij = 0
    W = np.ones((12, 12)) - np.eye(12)
    r2 = icvi.mancoridis_mq(W, lab)
    assert -1 <= r2["value"] <= 1 and r2["value"] < r["value"]


# ---------- S_Dbw: независимая реализация по формулам Halkidi & Vazirgiannis 2001 ----------
def naive_sdbw(X, lab, scope="union"):
    ks = sorted(set(lab.tolist()))
    K = len(ks)
    pts = {a: [X[i] for i in range(len(X)) if lab[i] == a] for a in ks}

    def var(P):
        P = np.array(P)
        return np.array([np.mean((P[:, d] - P[:, d].mean()) ** 2) for d in range(P.shape[1])])

    norm = lambda v: float(np.sqrt(sum(x * x for x in v)))
    v = {a: np.mean(pts[a], axis=0) for a in ks}
    sig = {a: norm(var(pts[a])) for a in ks}
    scat = sum(sig.values()) / K / norm(var(list(X)))
    stdev = np.sqrt(sum(sig.values())) / K

    def dens(u, P):
        return sum(1 for x in P if norm(x - u) <= stdev)

    tot = 0.0
    for a, b in itertools.permutations(ks, 2):
        P = pts[a] + pts[b]
        u = (v[a] + v[b]) / 2
        if scope == "union":
            d = max(dens(v[a], P), dens(v[b], P))
        else:
            d = max(dens(v[a], pts[a]), dens(v[b], pts[b]))
        num = dens(u, P)
        if d == 0:
            if num == 0:
                continue
            return float("nan")  # строгое определение: отношение не ограничено
        tot += num / d
    return scat + tot / (K * (K - 1))


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("scope", ["union", "own"])
def test_sdbw_matches_naive(seed, scope):
    rng = np.random.default_rng(seed)
    X = np.vstack([rng.normal(c, 1.0, size=(10, 3)) for c in (0, 3, 6)])
    lab = np.repeat([0, 1, 2], 10)
    r = icvi.s_dbw(X, lab, scope)
    ref = naive_sdbw(X, lab, scope)
    if np.isnan(ref):
        assert np.isnan(r["value"]) and r["status"] == "undefined_density_ratio"
    else:
        assert r["value"] == pytest.approx(ref, abs=1e-12)


def test_sdbw_undefined_conventions():
    # 3D-гауссианы, seed 9: у центроида нет точек в радиусе stdev, у середины есть
    rng = np.random.default_rng(9)
    X = np.vstack([rng.normal(c, 1.0, size=(10, 3)) for c in (0, 2, 4)])
    lab = np.repeat([0, 1, 2], 10)
    strict = icvi.s_dbw(X, lab, "union", "nan")
    f1 = icvi.s_dbw(X, lab, "union", "floor1")
    v4 = icvi.s_dbw(X, lab, "union", "v4_zero")
    assert strict["n_undefined_terms"] > 0 and np.isnan(strict["value"])
    assert f1["value"] > v4["value"]  # v4 занижает (поощряет) неопределённые слагаемые


def test_sdbw_separated_better_than_overlapping():
    rng = np.random.default_rng(0)
    sep = np.vstack([rng.normal(c, 0.3, size=(20, 2)) for c in (0, 10)])
    ov = np.vstack([rng.normal(c, 3.0, size=(20, 2)) for c in (0, 1)])
    lab = np.repeat([0, 1], 20)
    assert icvi.s_dbw(sep, lab)["value"] < icvi.s_dbw(ov, lab)["value"]


def test_sdbw_degenerate_cases():
    X = np.ones((6, 2))
    assert icvi.s_dbw(X, np.repeat([0, 1], 3))["status"] == "undefined_zero_total_variance"
    # точечные кластеры (σ_i = 0): stdev = 0, допускается
    X2 = np.repeat(np.array([[0., 0.], [5., 5.]]), 3, axis=0)
    r = icvi.s_dbw(X2, np.repeat([0, 1], 3))
    assert r["status"] == "ok" and r["value"] == pytest.approx(0.0)
    # синглтоны
    X3 = np.array([[0., 0.], [0.1, 0.], [5., 5.]])
    assert np.isfinite(icvi.s_dbw(X3, np.array([0, 0, 1]))["value"])


def test_avu_binary_at_K2():
    # свойство опубликованной формулы: при K=2 B_a = B_b = E_ab, поэтому U_ab = 1 при E_ab > 0
    rng = np.random.default_rng(0)
    W = rand_graph(10, 0.7, rng)
    for _ in range(5):
        lab = rng.integers(0, 2, 10)
        if len(set(lab)) == 2:
            assert icvi.avi_avu(W, lab)["AVU"] == pytest.approx(1.0)


def test_permutation_null_pvalue_positive():
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(c, 0.2, size=(8, 2)) for c in (0, 5, 10)])
    lab = np.repeat([0, 1, 2], 8)
    W = np.where(lab[:, None] == lab[None, :], 1.0, 0.0)
    np.fill_diagonal(W, 0)
    res = icvi.permutation_null(X, W, lab, B=49, seed=1)
    for k, v in res.items():
        if np.isfinite(v["p"]):
            assert v["p"] >= 1 / (v["B"] + 1) and v["B"] <= 49 and v["B_requested"] == 49
    assert res["AVU"]["z"] > 0  # знак выровнен: больше = лучше
