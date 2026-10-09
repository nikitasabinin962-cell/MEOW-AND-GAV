"""Граничные случаи: kNN, self-tuning, композиции, ряды, динамика, устойчивость, статистика."""
import numpy as np
import pandas as pd
import pytest

from econtypes5 import compositional as CO, dynamics as DY, graphs as G, stability as ST, stats as S, timeseries as TS


# ---------- kNN / affinity ----------
@pytest.mark.parametrize("n", [1, 2, 5, 63])
def test_knn_k_bounds(n):
    rng = np.random.default_rng(0)
    D = np.sqrt(G.pairwise_sq_dist(rng.normal(size=(n, 3))))
    assert G.knn_mask(D, 0).sum() == 0
    if n >= 2:
        M = G.knn_mask(D, 1)
        assert M.sum() >= n and np.array_equal(M, M.T)
        full = G.knn_mask(D, n - 1)
        assert full.sum() == n * (n - 1)
    with pytest.raises(ValueError, match="N−1"):
        G.knn_mask(D, n)
    with pytest.raises(ValueError):
        G.knn_mask(D, n + 1)
    with pytest.raises(ValueError):
        G.knn_mask(D, 1.5)


def test_mutual_subset_of_union_and_isolates_reported():
    rng = np.random.default_rng(1)
    Z = np.vstack([rng.normal(0, 1, (20, 2)), [[30, 30]]])
    D = np.sqrt(G.pairwise_sq_dist(Z))
    U, Mu = G.knn_mask(D, 3, "union"), G.knn_mask(D, 3, "mutual")
    assert (Mu <= U).all()
    assert G.diagnostics(Mu.astype(float))["isolates"] >= 1  # выброс не входит ни в чей mutual-kNN


def test_self_tuning_duplicates_and_identical():
    Z = np.array([[0, 0], [0, 0], [0, 0], [1, 0], [2, 0.]])
    D = np.sqrt(G.pairwise_sq_dist(Z))
    S, info = G.self_tuning_affinity(D, k_nn=2, k_scale=2)
    assert np.isfinite(S).all() and np.allclose(S, S.T) and (np.diag(S) == 0).all()
    assert any(f[1] == "sigma_fallback_min_positive" for f in info["sigma_fallback"])
    with pytest.raises(ValueError, match="совпадают"):
        G.self_tuning_affinity(np.zeros((4, 4)), 2, 2)


def test_self_tuning_formula():
    rng = np.random.default_rng(2)
    Z = rng.normal(size=(10, 2))
    D = np.sqrt(G.pairwise_sq_dist(Z))
    S, _ = G.self_tuning_affinity(D, k_nn=9, k_scale=3)
    srt = np.sort(D + np.diag([np.inf] * 10), axis=1)
    sig = srt[:, 2]
    i, j = 1, 7
    assert S[i, j] == pytest.approx(np.exp(-D[i, j] ** 2 / (sig[i] * sig[j])))


def test_block_distance_missing_block():
    a = np.array([[0., 0.], [1., 0.], [np.nan, np.nan]])
    b = np.array([[0.], [0.], [5.]])
    D, info = G.block_distance({"a": a, "b": b})
    assert np.isfinite(D[0, 2]) and D[0, 2] == pytest.approx(np.sqrt(25 * 2))  # только блок b, перенормирован
    assert info["observed_per_block"]["a"] == 2


def test_threshold_graph_edge_count():
    rng = np.random.default_rng(3)
    S = rng.random((10, 10))
    S = (S + S.T) / 2
    T, tau = G.threshold_graph(S, n_edges=12)
    assert G.diagnostics(T)["edges"] == 12


def test_diagnostics_disconnected():
    W = np.zeros((6, 6))
    W[0, 1] = W[1, 0] = 1
    d = G.diagnostics(W)
    assert d["components"] == 5 and d["isolates"] == 4


def test_snf_runs_symmetric():
    rng = np.random.default_rng(4)
    A = [G.unit_max(np.exp(-G.pairwise_sq_dist(rng.normal(size=(15, 2))))) for _ in range(3)]
    F = G.snf(A, k=4, t=10)
    assert np.allclose(F, F.T) and (np.diag(F) == 0).all() and np.isfinite(F).all()


# ---------- композиции ----------
def test_ilr_isometry_and_identities():
    rng = np.random.default_rng(5)
    P = CO.closure(rng.random((7, 5)) + 0.01)
    V = CO.helmert_basis(5)
    assert np.allclose(V.T @ V, np.eye(4)) and np.allclose(V.T @ np.ones(5), 0)
    Z = CO.ilr(P, V)
    DZ = np.sqrt(G.pairwise_sq_dist(Z))
    assert np.allclose(DZ, CO.aitchison_distance(P))
    assert np.allclose(CO.ilr_inv(Z, V), P)
    # масштабная инвариантность: доли и исходные суммы дают одинаковые координаты
    assert np.allclose(CO.ilr(CO.closure(P * 1234.5), V), Z)


def test_zeros_handling():
    P = np.array([[0.5, 0.5, 0.0], [0.2, 0.8, 0.0], [0.3, 0.6, 0.1]])
    z = CO.detect_zeros(P)
    assert z["structural_zero_parts"] == [] and z["sample_zero_cells"] == 2
    P2 = np.array([[0.5, 0.5, 0.0], [0.2, 0.8, 0.0]])
    r = CO.ilr_coordinates(P2, ["a", "b", "c"])
    assert r["diagnostics"]["dropped_structural"] == ["c"] and r["Z"].shape == (2, 1)
    with pytest.raises(FloatingPointError):
        CO.clr(np.array([[0.5, 0.5, 0.0]]))
    Pn = np.array([[np.nan] * 3, [0.2, 0.3, 0.5]])
    Pr, nrep = CO.multiplicative_replacement(Pn)
    assert np.isnan(Pr[0]).all() and nrep == 0


# ---------- ряды ----------
def test_residuals_zero_spending_not_log():
    Y = pd.DataFrame([[0, 1, 2, 3, 4, 5, 6, 7], [1, 2, 3, 4, 5, 6, 7, 8]], index=["a", "b"], dtype=float)
    R, st = TS.residual_series(Y)
    assert st == {"a": "nonpositive_values"} and np.isnan(R.loc["a"].iloc[0])
    assert np.isfinite(R.loc["b"]).all()


def test_constant_series_no_nan_layers():
    Y = pd.DataFrame(np.ones((6, 24)), index=list("abcdef"))
    R, _ = TS.residual_series(Y)
    S, info = TS.dtw_similarity(R, 2)
    assert np.isfinite(S).all() and (S == 0).all()
    C, i2 = TS.comovement(R)
    assert np.isfinite(C).all()


def test_restrict_window():
    Y = pd.DataFrame(np.arange(12).reshape(1, 12) + 1.0, columns=[f"2023-{m:02d}" for m in range(1, 13)])
    assert list(TS.restrict(Y, end="2023-06").columns)[-1] == "2023-06"


# ---------- динамика ----------
def test_hungarian_renaming_and_split_merge():
    prev = pd.Series([0, 0, 0, 0, 1, 1, 1, 1], index=list("abcdefgh"))
    cur = pd.Series([5, 5, 9, 9, 7, 7, 7, 7], index=list("abcdefgh"))
    al = DY.hungarian_align(cur, prev)
    assert al["e"] == 1 and set(al[["a", "b", "c", "d"]]) == {0, 2}
    ev = DY.events(prev, cur, theta=0.3)
    kinds = {e["event"] for e in ev}
    assert "split" in kinds
    ev2 = DY.events(cur, prev, theta=0.3)
    assert "merge" in {e["event"] for e in ev2}


def test_node_entry_exit_and_vi():
    prev = pd.Series([0, 0, 1], index=["a", "b", "c"])
    cur = pd.Series([0, 1, 1], index=["b", "c", "d"])
    f = DY.node_flux(prev, cur)
    assert f == dict(entered=["d"], exited=["a"])
    assert DY.variation_of_information([0, 0, 1, 1], [5, 5, 3, 3]) == pytest.approx(0.0, abs=1e-12)


# ---------- устойчивость ----------
def test_coassignment_joint_observation_and_self_excluded():
    co = ST.CoAssignment(4)
    co.add(np.array([0, 1, 2]), np.array([0, 0, 1]))
    co.add(np.array([0, 1, 3]), np.array([1, 1, 1]))
    P = co.matrix()
    assert P[0, 1] == 1.0 and P[0, 2] == 0.0 and np.isnan(P[2, 3])
    final = np.array([0, 0, 1, 1])
    stab = co.node_stability(final)
    assert stab[0] == 1.0 and np.isnan(stab[2])  # пара (2,3) не наблюдалась совместно


def test_moving_block():
    rng = np.random.default_rng(0)
    m = [f"m{i}" for i in range(24)]
    out = ST.moving_block_months(m, 3, rng)
    assert len(out) == 24 and set(out) <= set(m)


# ---------- статистика ----------
def test_mc_p_never_zero():
    assert S.mc_p(0, 999) == pytest.approx(1 / 1000)


def test_spearman_perm_matches_scipy_permutation_test():
    from scipy import stats as ss
    rng = np.random.default_rng(0)
    x = rng.normal(size=30)
    y = x + rng.normal(size=30)
    r = S.corr_test(x, y, "spearman", B=4999, seed=1, ci_B=200)
    ref = ss.permutation_test((x,), lambda a: ss.spearmanr(a, y).statistic, permutation_type="pairings",
                              n_resamples=4999, random_state=2)
    assert r["r"] == pytest.approx(ss.spearmanr(x, y).statistic)
    assert abs(r["p_perm"] - ref.pvalue) < 0.01
    assert r["p_perm"] > 0


def test_fdr_bh_by():
    p = np.array([0.001, 0.01, 0.02, 0.5, np.nan])
    bh, by = S.fdr(p, "bh"), S.fdr(p, "by")
    assert np.isnan(bh[-1]) and (by[:4] >= bh[:4]).all()


def test_msr_preserves_moran():
    rng = np.random.default_rng(0)
    n = 25
    xy = rng.random((n, 2))
    D = np.sqrt(G.pairwise_sq_dist(xy))
    Wsp = G.knn_mask(D, 4).astype(float)
    y = xy[:, 0] * 3 + rng.normal(0, 0.1, n)
    sur = S.msr_surrogates(y, Wsp, 50, 1)
    I0 = S.moran_I(y, Wsp)
    Is = [S.moran_I(v, Wsp) for v in sur]
    assert np.allclose(Is, I0, atol=1e-8)
    assert np.allclose(sur.mean(1), y.mean()) and np.allclose(sur.var(1), y.var())


def test_cluster_vs_external_nominal():
    rng = np.random.default_rng(0)
    lab = np.repeat([0, 1, 2], 10)
    y = lab * 1.0 + rng.normal(0, 0.3, 30)
    r1 = S.cluster_vs_external(lab, y, B=999)
    relab = np.array([{0: 2, 1: 0, 2: 1}[v] for v in lab])
    r2 = S.cluster_vs_external(relab, y, B=999)
    assert r1["H"] == pytest.approx(r2["H"]) and r1["p_perm"] < 0.01


def test_within_between():
    rng = np.random.default_rng(0)
    rows = []
    for u in range(20):
        a = 3 * rng.normal()
        for t in range(4):
            e = rng.normal()
            rows.append(dict(mo=u, x=a + e, y=-a + e))
    r = S.within_between(pd.DataFrame(rows), "x", "y", B=200)
    assert r["between"] < 0 < r["within"]
