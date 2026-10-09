"""Повтор 12 проверок аудитора (reproduction/audit_project.py) против исправленного пакета econtypes5 (+1 сверка на матрице C1 v5).
Результат: outputs/PROJECT_CHECKS_v5.json. Каждая проверка исполняется; статус — фактический."""
import json
import resource
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPRO = ROOT.parent / "reproduction" / "calculation_source"
sys.path.insert(0, str(ROOT))
from econtypes5 import dynamics as DY, graphs as G, icvi as I, stats as S, timeseries as TS  # noqa: E402

results = []


def check(name, fn):
    t = time.perf_counter()
    try:
        detail = fn()
        results.append(dict(test=name, status="PASS", detail=detail, seconds=round(time.perf_counter() - t, 4)))
    except Exception as e:  # noqa: BLE001
        results.append(dict(test=name, status="FAIL", detail=f"{type(e).__name__}: {e}", seconds=round(time.perf_counter() - t, 4)))


def lit(W, lab):  # независимая формула аудитора (Shalileh et al., eq. 20–21)
    cs = np.unique(lab)
    E = np.array([[W[np.ix_(lab == a, lab == b)].sum() for b in cs] for a in cs])
    out = E.sum(1) - np.diag(E)
    den = out[:, None] + out[None, :] - E
    U = np.divide(E, den, out=np.zeros_like(E), where=den > 0)
    np.fill_diagonal(U, 0)
    return float(U.sum() / len(cs))


def avu_formula():
    rng = np.random.default_rng(0)
    A = rng.random((20, 20)); W = np.triu(A, 1); W = W + W.T
    lab = rng.integers(0, 4, 20)
    v = I.avi_avu(W, lab)["AVU"]
    assert abs(v - lit(W, lab)) < 1e-12 and I.DIRECTION["AVU"] == "min"
    return dict(v5=v, reference=lit(W, lab), direction=I.DIRECTION["AVU"])


def cliques():
    lab = np.repeat(np.arange(3), 4); A = (lab[:, None] == lab[None, :]).astype(float); np.fill_diagonal(A, 0)
    r = I.avi_avu(A, lab)
    assert r["AVU"] == 0 and r["AVI"] == 1
    return dict(AVU=r["AVU"], AVI=r["AVI"], old_ratio_metric=I.intra_inter_density_ratio(A, lab))


def pvals():
    assert S.mc_p(0, 999) > 0
    hold = ROOT / "outputs/latest/HOLDOUT_VALIDATION.csv"
    det = {"mc_p(0,999)": S.mc_p(0, 999)}
    if hold.exists():
        h = pd.read_csv(hold)
        assert (h.p_value > 0).all()
        det["holdout_min_p"] = float(h.p_value.min())
    return det


def dtw_const():
    R, _ = TS.residual_series(pd.DataFrame(np.ones((6, 24))))
    Sm, info = TS.dtw_similarity(R, 2)
    assert np.isfinite(Sm).all()
    return info["status"]


def logzero():
    R, st = TS.residual_series(pd.DataFrame([[0, 1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6, 7]], dtype=float))
    assert np.isnan(R.iloc[0, 0]) and np.isfinite(R.iloc[1]).all() and st == {0: "nonpositive_values"}
    return "log(0) не вычисляется: NaN + статус 'nonpositive_values'"


def kbig():
    try:
        G.knn_mask(np.ones((5, 5)), 6)
    except ValueError as e:
        return str(e)
    raise AssertionError("k>N не отклонён")


def leakage():
    p = ROOT / "outputs/latest/LEAKAGE_TEST.json"
    r = json.loads(p.read_text())
    assert r["status"] == "PASS" and all(r["monitoring"].values())
    return r


def scale():
    rng = np.random.default_rng(42); n = 2016
    X = rng.normal(size=(n, 18))
    t = time.perf_counter()
    W, _ = G.self_tuning_affinity(np.sqrt(G.pairwise_sq_dist(X)), 8, 7)
    return dict(N=n, seconds=round(time.perf_counter() - t, 3), edges=int(np.count_nonzero(np.triu(W, 1))))


def relabel():
    ref = pd.Series([0, 0, 1, 1, 2, 2]); cur = pd.Series([8, 8, 3, 3, 7, 7])
    assert DY.hungarian_align(cur, ref).tolist() == ref.tolist()
    return "ok"


def kn():
    r = I.all_indices(np.eye(5), np.ones((5, 5)) - np.eye(5), np.arange(5))
    assert np.isnan(r["SW"]) and r["_status"]["SW"] == "undefined_K_ge_N"
    return r["_status"]


LATEST = ROOT / "outputs/latest"


def _exact_W(matrix: str):
    """Точная W прогона из выгрузки базы (run_matrix_edges), узлы — по mo_id."""
    rid = json.loads((LATEST / "RUN_MANIFEST.json").read_text())["run_id"]
    e = pd.read_parquet(ROOT / "outputs/db_parquet/run_matrix_edges.parquet")
    e = e[(e.run_id == rid) & (e.matrix == matrix)]
    nodes = sorted(set(e.i) | set(e.j))
    pos = {m: k for k, m in enumerate(nodes)}
    W = np.zeros((len(nodes), len(nodes)))
    for r in e.itertuples():
        W[pos[r.i], pos[r.j]] = W[pos[r.j], pos[r.i]] = r.weight
    names = pd.read_parquet(ROOT / "outputs/db_parquet/mo.parquet").set_index("mo_id").name.reindex(nodes).tolist()
    return W, names, e


def baseline_dimensions():
    """Аналог baseline_dimensions_and_finite для v5: размеры, конечность признаков, свойства точной W."""
    from scipy.sparse.csgraph import connected_components
    man = json.loads((LATEST / "RUN_MANIFEST.json").read_text())
    W, names, e = _exact_W("C4_v5features_v5graph|exact")
    assert len(names) == man["N"] == 62 and "ГО Межгорье" not in names
    assert (e.i != e.j).all() and np.isfinite(e.weight).all() and (e.weight > 0).all()
    ncomp = connected_components(W > 0, directed=False)[0]
    assert ncomp == 1
    feats = pd.read_csv(LATEST / "CONFIG_FEATURES.csv").set_index("config").loc["C4_v5features_v5graph", "feature_columns"].split(";")
    ff = pd.read_parquet(LATEST / "FORMULA_FEATURES_MO_PERIOD.parquet")
    st = ff[(ff.period == "static") & (ff["mode"] == "retrospective") & ff.feature.isin(feats)].pivot_table(index="mo_name", columns="feature", values="value")
    st = st.reindex(index=names, columns=feats)
    nonfinite = int((~np.isfinite(st.to_numpy(dtype=float))).sum())
    assert nonfinite == 0
    labels = pd.read_csv(LATEST / "LABELS_STATIC.csv")
    assert len(labels) == 62 and labels.macro.nunique() == man["final"]["k"]
    return dict(N=len(names), features=len(feats), nonfinite_cells=nonfinite, exact_edges=len(e), components=int(ncomp), K=man["final"]["k"])


def v4_matrix_reproduces_auditor():
    """Матрица v4 так же, как у аудитора (экспортированные слои network_edges.csv с 4 знаками, правило слияния v4),
    оценена исправленным icvi v5: опубликованный AVU = 0,5358312305, старый показатель v4 = 0,8017049076."""
    import yaml
    raw = pd.read_csv(REPRO / "outputs/tables/features_raw_2023_2024.csv").set_index("mo")
    edges = pd.read_csv(REPRO / "outputs/tables/network_edges.csv")
    cfg = yaml.safe_load((REPRO / "config/config.yaml").read_text())["network"]
    idx = {m: i for i, m in enumerate(raw.index)}
    layers = {}
    for key in ["attr", *cfg["layer_weights"]]:
        A = np.zeros((len(raw), len(raw)))
        for r in edges[edges.layer == key].itertuples():
            A[idx[r.source], idx[r.target]] = A[idx[r.target], idx[r.source]] = r.weight
        layers[key] = A

    def unit(M):  # как networks._unit v4
        M = np.clip(M, 0, None)
        np.fill_diagonal(M, 0)
        return M / M.max() if M.max() > 0 else M
    tot = sum(cfg["layer_weights"].values())
    struct = sum(w / tot * layers[k] for k, w in cfg["layer_weights"].items())
    W = unit(cfg["alpha_attr"] * layers["attr"] + (1 - cfg["alpha_attr"]) * unit(struct))
    lab = pd.read_csv(REPRO / "outputs/tables/clusters_final.csv").set_index("mo").reindex(raw.index)["cluster"].to_numpy()
    r = I.avi_avu(W, lab)
    old = I.intra_inter_density_ratio(W, lab)
    assert int((W > 0).sum() // 2) == 1065
    assert abs(r["AVU"] - 0.5358312305) < 1e-9 and abs(old - 0.8017049076) < 1e-9 and abs(r["AVU"] - lit(W, lab)) < 1e-12
    # MQ на расчётной W и на показанной проекции (слой fused, 310 рёбер) — п. 3.5
    D = np.zeros_like(W)
    for e in edges[edges.layer == "fused"].itertuples():
        D[idx[e.source], idx[e.target]] = D[idx[e.target], idx[e.source]] = e.weight
    mq_w, mq_d = I.newman_modularity(W, lab)["value"], I.newman_modularity(D, lab)["value"]
    assert int((D > 0).sum() // 2) == 310 and abs(mq_w - 0.2441383345) < 1e-9 and abs(mq_d - 0.3725325796) < 1e-9
    # S_Dbw v4: X как у аудитора; все слагаемые плотности нулевые → S_Dbw = Scat — п. 3.3
    from sklearn.impute import KNNImputer
    from sklearn.preprocessing import RobustScaler
    t = raw.copy()
    for c in ["proc_pc", "spend_total"]:
        t[c] = np.log(t[c].clip(lower=1))
    t["supply_out_pc"] = np.log1p(t["supply_out_pc"])
    t = t.fillna({c: 0 for c in t if c.startswith(("okpd_", "proc_"))})
    X = np.clip(RobustScaler().fit_transform(KNNImputer(n_neighbors=5).fit_transform(t)), -4, 4)
    sd = I.s_dbw(X, lab, density_scope="union", undefined_terms="v4_zero")
    assert sd["n_zero_den_terms"] == 42 == 7 * 6 and sd["dens_bw"] == 0.0 and abs(sd["value"] - sd["scat"]) < 1e-15
    return dict(edges=1065, AVU_published=r["AVU"], AVI=r["AVI"], old_v4_metric=old, MQ_newman_W=mq_w, MQ_newman_display_310=mq_d,
                S_Dbw=sd["value"], Scat=sd["scat"], zero_density_terms=sd["n_zero_den_terms"])


def baseline_rescore():
    """AVU v4-меток на точной W постановки C1 (признаки и граф v4) — независимой формулой аудитора по рёбрам из базы."""
    W, names, _ = _exact_W("C1_v4features_v4graph|exact")
    v4 = pd.read_csv(REPRO / "outputs/tables/clusters_final.csv").set_index("mo").cluster.reindex(names).to_numpy()
    avu = lit(W, v4)
    c = pd.read_csv(LATEST / "CLUSTER_COMPARISON.csv")
    row = c[c.labeling.str.startswith("v4_published")].iloc[0]
    assert abs(avu - row["AVU__C1space"]) < 1e-9, (avu, row["AVU__C1space"])
    old = I.intra_inter_density_ratio(W, v4)
    return dict(AVU_published_independent=avu, AVU_pipeline=row["AVU__C1space"], old_v4_metric_intra_inter=old,
                MQ_C1space=row["MQ_newman__C1space"], SW_C1space=row["SW__C1space"])


with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    check("baseline_dimensions_and_finite_v5", baseline_dimensions)
    check("v4_matrix_reproduces_auditor_AVU_MQ_SDbw", v4_matrix_reproduces_auditor)
    check("v4_labels_rescored_on_v5_C1_matrix_independent", baseline_rescore)
    check("AVU_formula_and_optimization_direction", avu_formula)
    check("AVU_disconnected_three_cliques", cliques)
    check("finite_permutation_pvalues_are_positive", pvals)
    check("DTW_all_constant_series", dtw_const)
    check("zero_monthly_expenditure", logzero)
    check("kNN_k_above_N", kbig)
    check("historical_layers_do_not_use_future_EXECUTED", leakage)
    check("actual_self_tuning_kNN_N_2016", scale)
    check("label_permutation_invariance", relabel)
    check("ICVI_K_equals_N_rejected_with_status", kn)
    diag = [dict(category=x.category.__name__, message=str(x.message)[:200]) for x in w]
out = dict(checked_at=time.strftime("%Y-%m-%d"), package="econtypes5", checks=results,
           pass_=sum(r["status"] == "PASS" for r in results), fail=sum(r["status"] == "FAIL" for r in results),
           warnings_captured=diag[:20], peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
(ROOT / "outputs/PROJECT_CHECKS_v5.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps({k: v for k, v in out.items() if k != "checks"}, ensure_ascii=False), [(r["test"], r["status"]) for r in results])
