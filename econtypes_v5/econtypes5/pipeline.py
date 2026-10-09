"""Полный расчёт econtypes v5 одной командой:  python -m econtypes5.pipeline [--quick]

Выходы: outputs/run_<run_id>/ (все таблицы) и outputs/latest/ (копия), таблицы run_* в базе.
Каждая таблица содержит run_id; экономические выводы отчёта ссылаются на run_id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import re
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from . import clustering as CL
from . import db as DB
from . import dynamics as DY
from . import experiments as EX
from . import extra_methods as EM
from . import features as F
from . import graphs as G
from . import icvi as I
from . import networks as NW
from . import stability as ST
from . import stats as S
from . import timeseries as TS

ROOT = Path(__file__).resolve().parents[1]
DIAG: list[dict] = []   # диагностики вместо глобального подавления предупреждений


def _capture_warnings():
    def handler(message, category, filename, lineno, file=None, line=None):
        DIAG.append(dict(category=category.__name__, message=str(message)[:300], where=f"{Path(filename).name}:{lineno}"))
    warnings.showwarning = handler


def hash_paths(paths) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


class Run:
    def __init__(self, cfg: dict, quick: bool = False):
        self.cfg = cfg
        self.quick = quick
        self.t0 = time.time()
        self.timings = {}
        cfg_bytes = json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode()
        self.config_hash = hashlib.sha256(cfg_bytes).hexdigest()[:16]
        self.code_hash = hash_paths((ROOT / "econtypes5").glob("*.py"))
        self.db_path = str(ROOT / cfg["database"])
        con = DB.connect(self.db_path)
        # только содержательные поля реестра: retrieved_at меняется при каждой сборке базы
        self.data_hash = DB.table_digest(con, "(SELECT source_id, sha256, size_bytes, relative_path, row_count FROM source_registry)", "source_id")[:16]
        con.close()
        self.run_id = f"v5-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{self.config_hash[:6]}{'-quick' if quick else ''}"
        self.out = ROOT / "outputs" / f"run_{self.run_id}"
        self.out.mkdir(parents=True, exist_ok=True)
        self.seed = int(cfg["seed"])

    def tic(self, name):
        self.timings[name] = round(time.time() - self.t0, 1)
        print(f"[{self.timings[name]:7.1f}s] {name}", flush=True)

    def save(self, df: pd.DataFrame, name: str, parquet: bool = False):
        df = df.copy()
        df.insert(0, "run_id", self.run_id)
        df.to_csv(self.out / f"{name}.csv", index=False)
        if parquet:
            df.to_parquet(self.out / f"{name}.parquet", index=False)
        return df


# ====================================================================== этапы
def stage_panel(R: Run, d: F.Data) -> pd.DataFrame:
    geo = F.CUSTOMER_GEO_INCLUSIVE if R.cfg["features"]["customer_geography"] == "inclusive" else F.CUSTOMER_GEO_STRICT
    panel, meta = F.build_panel(d, geo)
    panel["mo_name"] = panel.mo_id.map(d.mo.name)
    R.panel_meta = meta
    out = R.save(panel, "FORMULA_FEATURES_MO_PERIOD", parquet=True)
    con = DB.connect(R.db_path)
    con.execute("DELETE FROM attribute_mo_period")
    con.executemany("INSERT INTO attribute_mo_period VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(int(r.mo_id), r.period, r.feature, r.mode, r.value, r.unit, r.block,
                      "robust_z в модели; здесь — исходная шкала" if r.block != "descriptive" else None,
                      r.coverage, int(r.imputed), r.source, r.window, r.available_by) for r in panel.itertuples()])
    con.commit()
    con.close()
    # стратегия «строгая география» для чувствительности
    strict, _ = F.build_panel(d, F.CUSTOMER_GEO_STRICT)
    R.panel_strict = strict
    ext = F.external_indicators(d)
    lq, lqmeta = F.msp_lq(d, F.MSP_GROUPS, seed=R.seed)
    R.lq_meta = lqmeta
    ext = ext.join(lq)
    # экономическая сложность и плотность связанности по МСП (снимок 2026, адресные кандидаты МО)
    msp = d.msp[d.msp.geo_status.isin(["district_text_candidate", "city_text_candidate"])].dropna(subset=["okved_section", "mo_id_candidate"])
    counts = msp.groupby(["mo_id_candidate", "okved_section"]).size().unstack(fill_value=0)
    counts.index = counts.index.astype(int)
    eci, pci, einfo = EM.economic_complexity(counts)
    dens = EM.relatedness_density(counts)
    ext["ext_msp2026_eci"] = eci.reindex(ext.index)
    ext["ext_msp2026_diversity"] = pd.Series(einfo["diversity"]).reindex(ext.index)
    R.save(pd.DataFrame(dict(section=pci.index, pci=pci.values, ubiquity=[einfo["ubiquity"][x] for x in pci.index])), "MSP_SECTION_COMPLEXITY")
    R.save(dens.rename_axis("mo_id").reset_index(), "MSP_RELATEDNESS_DENSITY")
    agef = d.facts[d.facts.source_id == "vpn2020_age_mo"]
    dep = EM.age_dependency(agef)
    ext["ext_old_age_ratio_65_per100_20_64"] = dep["old_age_ratio_65_20_64"].reindex(ext.index)
    ext["ext_youth_ratio_0_19_per100_20_64"] = dep["youth_ratio_0_19_20_64"].reindex(ext.index)
    bal = pd.concat([EM.demographic_balance(d.pop, d.facts, y) for y in (2023, 2024)])
    bal.insert(0, "mo_name", bal.index.map(d.mo.name))
    R.save(bal.rename_axis("mo_id").reset_index(), "DEMOGRAPHIC_BALANCE")
    ext["ext_balance_residual_share_2024"] = bal[bal.year == 2024]["residual_share_of_pop"].reindex(ext.index)
    ext.insert(0, "mo_name", d.mo.name)
    R.ext = ext
    R.save(ext.reset_index(), "EXTERNAL_INDICATORS_MO")
    json.dump({str(k): v for k, v in meta.items()} | {"msp_lq": lqmeta, "assumed_availability": F.ASSUMED_AVAILABILITY},
              open(R.out / "panel_meta.json", "w"), ensure_ascii=False, indent=1, default=str)
    return panel


def build_static(R: Run, d: F.Data, panel: pd.DataFrame, nodes: list[int]) -> dict:
    nc = R.cfg["network"]
    names = [d.mo.name[m] for m in nodes]
    Xo, cols_o = NW.x_old(d, nodes)
    Xn, cols_n, infon = NW.x_new(panel, nodes, "static", "retrospective")
    sn, sinfo = NW.struct_layers_new(d, nodes, F.MONTHS, F.QUARTERS, nc)
    so = NW.struct_layers_old(names)
    k, ks = nc["knn"], nc["k_scale"]
    An, ainfo = NW.attr_new_rule(Xn, k, ks, nc["knn_mode"])
    cfgs = {
        "C1_v4features_v4graph": dict(X=Xo, W=NW.fuse_graph(NW.attr_old_rule(Xo, k), so, k, nc["alpha_attr"]), feat="v4", graph="v4"),
        "C2_v5features_v4graph": dict(X=Xn, W=NW.fuse_graph(NW.attr_old_rule(Xn, k), so, k, nc["alpha_attr"]), feat="v5", graph="v4"),
        "C3_v4features_v5graph": dict(X=Xo, W=NW.fuse_graph(NW.attr_new_rule(Xo, k, ks, nc["knn_mode"])[0], sn, k, nc["alpha_attr"]), feat="v4", graph="v5"),
        "C4_v5features_v5graph": dict(X=Xn, W=NW.fuse_graph(An, sn, k, nc["alpha_attr"]), feat="v5", graph="v5"),
    }
    R.save(pd.DataFrame([dict(config=c, feature_columns=";".join(cols_o if v["feat"] == "v4" else cols_n), n_features=v["X"].shape[1])
                         for c, v in cfgs.items()]), "CONFIG_FEATURES")
    return dict(nodes=nodes, names=names, Xo=Xo, Xn=Xn, cols_o=cols_o, cols_n=cols_n, sn=sn, so=so, sinfo=sinfo, An=An,
                ainfo=ainfo, cfgs=cfgs)


def stage_graph_diagnostics(R: Run, S0: dict) -> pd.DataFrame:
    nc = R.cfg["network"]
    rows = []
    for c, v in S0["cfgs"].items():
        rows.append(dict(matrix=f"W_exact[{c}]", role="расчётная W (кластеризация и сетевые ICVI)", **{k: v2 for k, v2 in G.diagnostics(v["W"]).items()}))
        rows.append(dict(matrix=f"W_display[{c}]", role="визуальная проекция (union-kNN k=4); ICVI по ней не считаются",
                         **G.diagnostics(NW.display_projection(v["W"]))))
    for name, L in S0["sn"].items():
        rows.append(dict(matrix=f"layer_v5[{name}] (полная)", role="структурный слой v5 до kNN", **G.diagnostics(L)))
    for name, L in S0["so"].items():
        rows.append(dict(matrix=f"layer_v4[{name}]", role="структурный слой v4 (архив, после kNN)", **G.diagnostics(L)))
    # сравнение правил атрибутивного ребра при равной плотности
    Xn = S0["Xn"]
    D = np.sqrt(G.pairwise_sq_dist(Xn))
    rules = {
        "cosine_union_kNN (v4)": G.cosine_knn(Xn, nc["knn"]),
        "self_tuning_union_kNN": G.self_tuning_affinity(D, nc["knn"], nc["k_scale"], "union")[0],
        "self_tuning_mutual_kNN": G.self_tuning_affinity(D, nc["knn"], nc["k_scale"], "mutual")[0],
    }
    full_st = G.self_tuning_affinity(D, len(D) - 1, nc["k_scale"], "union")[0]
    rules["self_tuning_threshold (равное число рёбер)"] = G.threshold_graph(full_st, n_edges=G.diagnostics(rules["self_tuning_union_kNN"])["edges"])[0]
    R.edge_rules = rules
    for name, W in rules.items():
        rows.append(dict(matrix=f"attr_rule[{name}]", role="сравнение правил ребра (атрибуты v5)", **G.diagnostics(W)))
    df = pd.DataFrame(rows)
    df["laplacian_eigs"] = df["laplacian_eigs"].map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else ";".join(map(str, v)))
    return R.save(df, "GRAPH_DIAGNOSTICS")


def stage_sweeps(R: Run, S0: dict) -> dict:
    cc = R.cfg["clustering"]
    nb = 9 if R.quick else cc["null_B"]
    bb = 5 if R.quick else cc["bootstrap_B"]
    ks = [3, 5, 7] if R.quick else cc["k_range"]
    allrows, labels = [], {}
    for c, v in S0["cfgs"].items():
        df, lab = EX.sweep(c, v["X"], v["W"], R.cfg, R.seed, ks=ks, null_B=nb, boot_B=bb)
        allrows.append(df)
        for (m, k), l in lab.items():
            labels[(c, m, k)] = l
    sw = pd.concat(allrows, ignore_index=True)
    sw["pareto_within_config"] = False
    for c in sw.config.unique():
        m = sw.config == c
        sw.loc[m, "pareto_within_config"] = EX.pareto_mask(sw[m])
    R.save(sw, "ICVI_SWEEP")
    # выбор: только сетевые методы на совмещённой W (кластеризация атрибутированной сети)
    sel = {}
    for c in S0["cfgs"]:
        sub = sw[(sw.config == c) & sw.method.isin(cc["methods_graph"])].reset_index(drop=True)
        best = EX.select(sub, R.cfg)
        sel[c] = best
    final_cfg = "C4_v5features_v5graph"
    fb = sel[final_cfg]
    R.final = dict(config=final_cfg, method=fb.method, k=int(fb.k), k_target=int(fb.k_target),
                   labels=labels[(final_cfg, fb.method, int(fb.k_target))])
    # детальный уровень: то же правило, ограниченное K ≥ k_detail_min (по умолчанию 5)
    kmin = cc.get("k_detail_min", 5)
    sub = sw[(sw.config == final_cfg) & sw.method.isin(cc["methods_graph"]) & (sw.k >= kmin)].reset_index(drop=True)
    db_ = EX.select(sub, R.cfg)
    R.detailed = dict(config=final_cfg, method=db_.method, k=int(db_.k), k_target=int(db_.k_target),
                      labels=labels[(final_cfg, db_.method, int(db_.k_target))])
    R.macro = dict(k=int(fb.k), labels=R.final["labels"])
    sel[final_cfg + " [детальный уровень K≥%d]" % kmin] = db_
    seltab = pd.DataFrame([dict(config=c, method=b.method, k=int(b.k), boot_ari_median=b.boot_ari_median, z_rank_mean=b.z_rank_mean,
                                SW=b.SW, CH=b.CH, S_Dbw=b.S_Dbw, S_Dbw_floor1=b.S_Dbw_floor1, AVI=b.AVI, AVU=b.AVU, MQ_newman=b.MQ_newman,
                                MQ_mancoridis=b.MQ_mancoridis) for c, b in sel.items()])
    R.save(seltab, "K_SELECTION")
    R.sel, R.labels_all, R.sweep = sel, labels, sw
    return sel


def stage_comparison(R: Run, S0: dict, d: F.Data) -> pd.DataFrame:
    """CLUSTER_COMPARISON: выбранные решения постановок, сравнения при общем K, перекрёстная оценка в общих пространствах."""
    fin = R.final
    v4lab = pd.read_csv(NW.REPRO / "outputs/tables/clusters_final.csv").set_index("mo").cluster.reindex(S0["names"]).to_numpy()
    labs = {"v4_published_labels(K=7)": v4lab}
    for c, b in R.sel.items():
        cc_ = c.split(" [")[0]
        tag = "detailed" if "детальный" in c else "selected"
        labs[f"{cc_}|{b.method}|K={int(b.k)}|{tag}"] = R.labels_all[(cc_, b.method, int(b.k_target))]
    for c in S0["cfgs"]:
        for m in R.cfg["clustering"]["methods_graph"]:
            key = (c, m, fin["k_target"])
            if key in R.labels_all:
                labs[f"{c}|{m}|K={fin['k']}|common_K"] = R.labels_all[key]
            key7 = (c, m, 7)
            if key7 in R.labels_all:
                labs[f"{c}|{m}|K=7|v4_K"] = R.labels_all[key7]
        for m in R.cfg["clustering"]["methods_attr"]:
            key = (c, m, fin["k_target"])
            if key in R.labels_all:
                labs[f"{c}|{m}|K={fin['k']}|attributes_only"] = R.labels_all[key]
    final_lab = fin["labels"]
    rows = []
    C1, C4 = S0["cfgs"]["C1_v4features_v4graph"], S0["cfgs"]["C4_v5features_v5graph"]
    for name, lab in labs.items():
        cfg_name = name.split("|")[0].split(" [")[0]
        own = S0["cfgs"].get(cfg_name)
        r_own = I.all_indices(own["X"], own["W"], lab) if own else I.all_indices(C1["X"], C1["W"], lab)
        r_c4 = I.all_indices(C4["X"], C4["W"], lab)
        r_c1 = I.all_indices(C1["X"], C1["W"], lab)
        row = dict(labeling=name, k=len(np.unique(lab)), min_size=int(np.bincount(pd.factorize(lab)[0]).min()),
                   ARI_vs_final=adjusted_rand_score(final_lab, lab), VI_vs_final=DY.variation_of_information(final_lab, lab),
                   ARI_vs_v4=adjusted_rand_score(v4lab, lab))
        for tag, r in [("own", r_own), ("C4space", r_c4), ("C1space", r_c1)]:
            for k in ["SW", "CH", "S_Dbw", "S_Dbw_floor1", "AVI", "AVU", "MQ_newman", "MQ_mancoridis"]:
                row[f"{k}__{tag}"] = r[k]
        rows.append(row)
    df = pd.DataFrame(rows)
    sw = R.sweep
    def boot(name):
        p = name.split("|")
        if len(p) < 3:
            return np.nan
        m = sw[(sw.config == p[0].split(" [")[0]) & (sw.method == p[1]) & (sw.k == int(p[2].split("=")[1]))]
        return float(m.boot_ari_median.iloc[0]) if len(m) else np.nan
    df["boot_ari_median_own"] = df.labeling.map(boot)
    R.v4lab = v4lab
    R.comparison_labels = labs
    return R.save(df, "CLUSTER_COMPARISON")


def recluster_c4(R: Run, X: np.ndarray, struct: dict, k: int, method: str, alpha=None, knn=None, k_scale=None, mode=None,
                 weights=None, attr_W=None, seed=None):
    nc = R.cfg["network"]
    knn = knn or nc["knn"]
    A = attr_W if attr_W is not None else NW.attr_new_rule(X, knn, k_scale or nc["k_scale"], mode or nc["knn_mode"])[0]
    W = NW.fuse_graph(A, struct, knn, nc["alpha_attr"] if alpha is None else alpha, weights or nc["layer_weights"]) if struct else A
    lab, _ = EX.cluster(method, k, X, W, seed or R.seed)
    return lab, W


def stage_ablation(R: Run, S0: dict, panel: pd.DataFrame) -> pd.DataFrame:
    fin = R.final
    k, m = fin["k_target"], fin["method"]
    base = fin["labels"]
    nodes = S0["nodes"]
    rows = []

    def add(kind, name, lab, X, W, note=""):
        r = I.all_indices(X, W, lab)
        C4 = S0["cfgs"]["C4_v5features_v5graph"]
        rc = I.all_indices(C4["X"], C4["W"], lab)
        rows.append(dict(kind=kind, variant=name, k=len(np.unique(lab)), ARI_vs_final=adjusted_rand_score(base, lab),
                         VI_vs_final=DY.variation_of_information(base, lab), note=note,
                         **{f"{x}__own": r[x] for x in ["SW", "CH", "S_Dbw_floor1", "AVI", "AVU", "MQ_newman"]},
                         **{f"{x}__C4space": rc[x] for x in ["SW", "CH", "S_Dbw_floor1", "AVI", "AVU", "MQ_newman"]}))

    blocks = list(F.BLOCKS)
    for b in blocks:   # исключение блока
        bl = [x for x in blocks if x != b]
        X, _, _ = NW.x_new(panel, nodes, "static", "retrospective", bl)
        lab, W = recluster_c4(R, X, S0["sn"], k, m)
        add("drop_block", f"−{b}", lab, X, W)
    acc = ["sber_level"]
    for b in ["sber_structure", "proc_budget", "proc_geo", "proc_corp", "demography", "age_structure"]:   # последовательное добавление
        X, _, _ = NW.x_new(panel, nodes, "static", "retrospective", acc)
        lab, W = recluster_c4(R, X, S0["sn"], k, m)
        add("forward_add", "+".join(acc), lab, X, W)
        acc = acc + [b]
    X = S0["Xn"]
    for layer in R.cfg["network"]["layer_weights"]:
        st = {kk: v for kk, v in S0["sn"].items() if kk != layer}
        w = {kk: v for kk, v in R.cfg["network"]["layer_weights"].items() if kk != layer}
        lab, W = recluster_c4(R, X, st, k, m, weights=w)
        add("drop_layer", f"−{layer}", lab, X, W)
    for a in [0.0, 0.25, 0.5, 0.75, 1.0]:
        lab, W = recluster_c4(R, X, S0["sn"], k, m, alpha=a)
        add("alpha", f"α={a}", lab, X, W, "α=1 — только атрибуты; α=0 — только структурные слои")
    for kn in [5, 8, 12]:
        for ksc in [5, 7, 9]:
            lab, W = recluster_c4(R, X, S0["sn"], k, m, knn=kn, k_scale=ksc)
            add("knn_kscale", f"k={kn}, k_scale={ksc}", lab, X, W)
    lab, W = recluster_c4(R, X, S0["sn"], k, m, mode="mutual")
    add("mask", "mutual-kNN", lab, X, W)
    for name, Wr in R.edge_rules.items():
        lab, W = recluster_c4(R, X, S0["sn"], k, m, attr_W=Wr)
        add("edge_rule", name, lab, X, W)
    # SNF против линейного слияния
    snf_in = [S0["An"]] + [S0["sn"][kk] for kk in ["comovement", "dtw", "procurement_flow"]]
    Wsnf = G.snf(snf_in, k=R.cfg["network"]["knn"], t=20)
    lab, _ = EX.cluster(m, k, X, Wsnf, R.seed)
    add("fusion", "SNF(attr, comovement, dtw, flow)", lab, X, Wsnf, "экспериментальное сравнение")
    # строгая география заказчиков
    Xs, _, _ = NW.x_new(R.panel_strict, nodes, "static", "retrospective")
    lab, W = recluster_c4(R, Xs, S0["sn"], k, m)
    add("geography", "customer geography strict (только название)", lab, Xs, W)
    # S_Dbw: область плотности
    df = pd.DataFrame(rows)
    df["S_Dbw_own_scope_C4"] = [I.s_dbw(S0["Xn"], base, "own", "floor1")["value"]] + [np.nan] * (len(df) - 1)
    return R.save(df, "ABLATION_SENSITIVITY")


def time_layers(d: F.Data, nodes: list[int], months: list[str], quarters: list[str], nc: dict):
    st, info = NW.struct_layers_new(d, nodes, months, quarters, nc)
    return {k: v for k, v in st.items()}


def stage_uncertainty(R: Run, S0: dict, d: F.Data, panel: pd.DataFrame) -> dict:
    fin = R.final
    k, m = fin["k_target"], fin["method"]
    X, W = S0["cfgs"]["C4_v5features_v5graph"]["X"], S0["cfgs"]["C4_v5features_v5graph"]["W"]
    n = len(X)
    U = R.cfg["uncertainty"]
    q = R.quick
    res = {}
    info = {"resolution": None}
    if m == "leiden":
        _, info = CL.leiden_k(W, k, R.seed)
    aris, co = EX.boot_ari(m, k, X, W, fin["labels"], info, 20 if q else U["node_B"], 0.8, R.seed)
    res["node_subsample"] = (aris, co)
    # бутстреп временных блоков: месяцы пересобираются блоками → пересчёт уровня/тренда трат и слоёв
    nc = R.cfg["network"]
    rng_months = F.MONTHS

    def rebuild_temporal(rng):
        ms = ST.moving_block_months(rng_months, U["temporal_block_len"], rng)
        Y = d.spend.loc[S0["nodes"], ms]
        Y.columns = [f"b{i:02d}" for i in range(len(ms))]
        Rr, _ = TS.residual_series(Y)
        lay = dict(S0["sn"])
        lay["comovement"], _ = TS.comovement(Rr, nc["min_obs"])
        lay["lead_lag"], _, _ = TS.lead_lag(Rr, nc["max_lag"], nc["min_obs"])
        lay["dtw"], _ = TS.dtw_similarity(Rr, nc["dtw_window"], nc["min_obs"])
        lab, _ = recluster_c4(R, X, lay, k, m)
        return lab

    r = ST.full_rebuild_bootstrap(rebuild_temporal, n, fin["labels"], B=5 if q else U["temporal_block_B"], seed=R.seed, scheme="temporal_block")
    res["temporal_block"] = (r["ari"], r["co"])

    def rebuild_params(rng):
        kn = int(rng.choice([6, 7, 8, 9, 10]))
        ks = int(rng.choice([5, 6, 7, 8, 9]))
        a = float(rng.choice([0.4, 0.5, 0.6]))
        Xj = X + rng.normal(0, 0.05, X.shape) * X.std(axis=0, keepdims=True)
        lab, _ = recluster_c4(R, Xj, S0["sn"], k, m, alpha=a, knn=kn, k_scale=ks)
        return lab

    r = ST.full_rebuild_bootstrap(rebuild_params, n, fin["labels"], B=5 if q else U["rebuild_B"], seed=R.seed + 1, scheme="feature_network_rebuild")
    res["feature_network_rebuild"] = (r["ari"], r["co"])
    dl = R.detailed
    dinfo = {"resolution": None}
    if dl["method"] == "leiden":
        _, dinfo = CL.leiden_k(W, dl["k_target"], R.seed)
    aris_d, co_d = EX.boot_ari(dl["method"], dl["k_target"], X, W, dl["labels"], dinfo, 20 if q else U["node_B"], 0.8, R.seed)
    res["node_subsample_detailed"] = (aris_d, co_d)
    rows, co_rows = [], []
    stab = pd.DataFrame(index=S0["names"])
    for scheme, (a, c) in res.items():
        rows.append(dict(scheme=scheme, B=len(a), ARI_median=float(np.median(a)), ARI_q05=float(np.quantile(a, .05)), ARI_q95=float(np.quantile(a, .95))))
        stab[scheme] = c.node_stability(dl["labels"] if scheme.endswith("_detailed") else fin["labels"])
        P = c.matrix()
        for i in range(n):
            for j in range(n):
                if i < j:
                    co_rows.append(dict(scheme=scheme, i=S0["names"][i], j=S0["names"][j], p=P[i, j], n_joint=int(c.obs[i, j])))
    R.uncert = res
    R.node_stability = stab
    R.save(pd.DataFrame(rows), "UNCERTAINTY_SUMMARY")
    R.save(stab.rename_axis("mo").reset_index(), "NODE_STABILITY")
    R.save(pd.DataFrame(co_rows), "COASSIGNMENT", parquet=True)
    return res


def stage_dynamics(R: Run, d: F.Data, panel: pd.DataFrame, nodes: list[int], level: str = "macro") -> pd.DataFrame:
    fin = R.final if level == "macro" else R.detailed
    k, m = fin["k_target"], fin["method"]
    nc, dc = R.cfg["network"], R.cfg["dynamics"]
    names = {mm: d.mo.name[mm] for mm in nodes}
    label_rows, q_rows, ev_rows, prof_rows = [], [], [], []
    Wt_cache = {}
    for mode in ("monitoring", "retrospective"):
        Xs, Ws, nset = {}, {}, {}
        for t in F.QUARTERS:
            qs = F.window_quarters(t, dc["window_quarters"])
            months = [mm for q in qs for mm in F.quarter_months(q)]
            X, cols, info = NW.x_new(panel, nodes, t, mode)
            keep = [i for i, mm in enumerate(nodes) if not any(mm in v for v in info["nodes_missing"].values())]
            ns = [nodes[i] for i in keep]
            X = X[keep]
            lay = time_layers(d, ns, months, qs, nc)
            A, _ = NW.attr_new_rule(X, nc["knn"], nc["k_scale"], nc["knn_mode"])
            Xs[t], Ws[t], nset[t] = X, NW.fuse_graph(A, lay, nc["knn"], nc["alpha_attr"]), ns
            Wt_cache[(mode, t)] = (X, Ws[t], ns, info, cols)
        for beta in (dc["beta_grid"] if (not R.quick and level == "macro") else [0.0, dc["beta_main"]]):
            prev_W, prev_nodes, prev_lab = None, None, None
            for t in F.QUARTERS:
                ns, W = nset[t], Ws[t]
                if prev_W is not None and beta > 0:
                    common = [x for x in ns if x in prev_nodes]
                    ia = [ns.index(x) for x in common]
                    ib = [prev_nodes.index(x) for x in common]
                    Wsm = W.copy()
                    Wsm[np.ix_(ia, ia)] = (1 - beta) * W[np.ix_(ia, ia)] + beta * prev_W[np.ix_(ib, ib)]
                else:
                    Wsm = W
                lab, _ = EX.cluster(m, k, Xs[t], Wsm, R.seed)
                cur = pd.Series(lab, index=[names[x] for x in ns])
                if prev_lab is not None:
                    cur = DY.hungarian_align(cur, prev_lab)
                else:
                    ref = pd.Series(fin["labels"], index=R.S0["names"])
                    cur = DY.hungarian_align(cur, ref)
                r = I.all_indices(Xs[t], W, cur.to_numpy())
                q_rows.append(dict(level=level, mode=mode, beta=beta, period=t, n=len(ns), warm_up=t in F.QUARTERS[:3], k=len(cur.unique()),
                                   SW=r["SW"], CH=r["CH"], S_Dbw_floor1=r["S_Dbw_floor1"], AVI=r["AVI"], AVU=r["AVU"], MQ_newman=r["MQ_newman"],
                                   ARI_vs_static_final=adjusted_rand_score(pd.Series(fin["labels"], index=R.S0["names"]).reindex(cur.index), cur),
                                   ARI_vs_prev=np.nan if prev_lab is None else adjusted_rand_score(prev_lab.reindex(cur.index).dropna(), cur.reindex(prev_lab.index).dropna()),
                                   VI_vs_prev=np.nan if prev_lab is None else DY.variation_of_information(prev_lab.reindex(cur.index).dropna(), cur.reindex(prev_lab.index).dropna())))
                for mo_name, l in cur.items():
                    label_rows.append(dict(level=level, mode=mode, beta=beta, period=t, mo=mo_name, label=int(l)))
                if prev_lab is not None and beta == dc["beta_main"]:
                    for e in DY.events(prev_lab, cur, dc["event_theta"]):
                        ev_rows.append(dict(level=level, mode=mode, beta=beta, from_period=prev_t, to_period=t, **{kk: json.dumps(v) if isinstance(v, list) else v for kk, v in e.items()}))
                    Xp = pd.DataFrame(Xs[prev_t], index=[names[x] for x in nset[prev_t]])
                    Xc = pd.DataFrame(Xs[t], index=[names[x] for x in ns])
                    if list(Xp.columns) == list(Xc.columns):
                        ps = DY.profile_shift(Xp, prev_lab, Xc, cur)
                        for pr in ps.to_dict("records"):
                            prof_rows.append(dict(level=level, mode=mode, from_period=prev_t, to_period=t, cluster=pr["cluster"], l2_shift=pr["l2_shift"]))
                prev_W, prev_nodes, prev_lab, prev_t = Wsm, ns, cur, t
    R.Wt_cache = Wt_cache
    sfx = "" if level == "macro" else "_DETAILED"
    lab = R.save(pd.DataFrame(label_rows), "LABELS_MO_PERIOD" + sfx, parquet=True)
    qdf = pd.DataFrame(q_rows)
    R.save(qdf, "DYNAMICS_QUALITY" + sfx)
    R.save(pd.DataFrame(ev_rows), "DYNAMICS_EVENTS" + sfx)
    R.save(pd.DataFrame(prof_rows), "DYNAMICS_PROFILE_SHIFT" + sfx)
    summ = qdf[~qdf.warm_up].groupby(["level", "mode", "beta"]).agg(snapshot_MQ=("MQ_newman", "mean"), snapshot_AVU=("AVU", "mean"),
                                                            temporal_ARI=("ARI_vs_prev", "mean"), temporal_VI=("VI_vs_prev", "mean"),
                                                            ARI_vs_static=("ARI_vs_static_final", "mean")).reset_index()
    R.save(summ, "DYNAMICS_BETA_SENSITIVITY" + sfx)
    if level == "macro":
        R.labels_period = pd.DataFrame(label_rows)
    else:
        R.labels_period_detailed = pd.DataFrame(label_rows)
    return qdf


def stage_leakage_test(R: Run, d: F.Data, nodes: list[int]) -> dict:
    """Исполняемый тест отсутствия будущей информации: данные после t=2023Q4 искажаются, и в режиме
    monitoring X_t, W_t и метки для t ≤ 2023Q4 должны совпасть побитно. В режиме retrospective
    (реконструкция) то же искажение меняет признаки — это подтверждает разницу режимов."""
    import copy
    cut = "2023Q4"
    cut_month = "2023-12"
    rng = np.random.default_rng(R.seed)
    d2 = copy.copy(d)
    d2.spend = d.spend.copy()
    fut = [c for c in d2.spend.columns if c > cut_month]
    d2.spend[fut] = d2.spend[fut] * rng.uniform(0.5, 1.5, size=(len(d2.spend), len(fut)))
    d2.contracts = d.contracts.copy()
    late = d2.contracts.quarter > cut
    d2.contracts.loc[late, "rub"] = d2.contracts.loc[late, "rub"] * rng.uniform(0, 3, late.sum())
    d2.pop = d.pop.copy()
    d2.pop["2025-01-01"] = d2.pop["2025-01-01"] * 1.1
    d2.pop["2024-01-01"] = d2.pop["2024-01-01"] * 1.05
    p1, _ = F.build_panel(d)
    p2, _ = F.build_panel(d2)
    nc = R.cfg["network"]
    res = {}
    for mode in ("monitoring", "retrospective"):
        same_feat, same_W, same_lab = True, True, True
        for t in F.QUARTERS[: F.QUARTERS.index(cut) + 1]:
            a = p1[(p1["mode"] == mode) & (p1.period == t)].sort_values(["mo_id", "feature"]).value.to_numpy(dtype=float)
            b = p2[(p2["mode"] == mode) & (p2.period == t)].sort_values(["mo_id", "feature"]).value.to_numpy(dtype=float)
            same_feat &= bool(np.allclose(a, b, equal_nan=True, rtol=0, atol=0))
            qs = F.window_quarters(t)
            months = [mm for q in qs for mm in F.quarter_months(q)]
            outs = []
            for dd, pp in ((d, p1), (d2, p2)):
                X, _, info = NW.x_new(pp, nodes, t, mode)
                lay = time_layers(dd, nodes, months, qs, nc)
                A, _ = NW.attr_new_rule(X, nc["knn"], nc["k_scale"], nc["knn_mode"])
                W = NW.fuse_graph(A, lay, nc["knn"], nc["alpha_attr"])
                lab, _ = EX.cluster(R.final["method"], R.final["k_target"], X, W, R.seed)
                outs.append((W, lab))
            same_W &= bool(np.array_equal(outs[0][0], outs[1][0]))
            same_lab &= bool(np.array_equal(outs[0][1], outs[1][1]))
        res[mode] = dict(features_identical=same_feat, W_identical=same_W, labels_identical=same_lab)
    res["status"] = "PASS" if all(res["monitoring"].values()) else "FAIL"
    res["retrospective_changes_detected"] = not all(res["retrospective"].values())
    json.dump(res, open(R.out / "LEAKAGE_TEST.json", "w"), indent=1, ensure_ascii=False)
    return res


# ---------------------------------------------------------------------- интерпретация
FEATURE_RU = {
    "sber_spend_pc_log": "безналичные траты на жителя (log)", "sber_rel_trend": "относительный тренд трат",
    "proc44_pc_log": "госзаказ 44-ФЗ на жителя (log)", "proc44_muni_share": "доля муниципального уровня в 44-ФЗ",
    "supplier_hhi": "концентрация поставщиков (HHI)", "procgeo_ilr1": "ILR1 география поставщиков [свой МО vs другие МО РБ]",
    "procgeo_ilr2": "ILR2 география поставщиков [РБ vs вне РБ]", "proc223_pc_log": "закупки 223-ФЗ на жителя (log)",
    "pop_growth": "темп изменения населения", "natinc_rate": "естественный прирост, ‰", "migr_rate": "миграционный прирост, ‱",
    "age_ilr1": "ILR1 возраст [0–14 vs 15–64]", "age_ilr2": "ILR2 возраст [0–64 vs 65+]",
    "sber_ilr1": "ILR1 трат [продукты vs здоровье]", "sber_ilr2": "ILR2 трат [прод.+здор. vs общепит]",
    "sber_ilr3": "ILR3 трат [... vs маркетплейсы]", "sber_ilr4": "ILR4 трат [... vs транспорт]", "sber_ilr5": "ILR5 трат [... vs прочее]",
}
# Словесное описание направления признака (для имени типа; ILR — пивотный базис Эгозкуэ: ilr_k ∝ среднее log первых k частей − log (k+1)-й)
PLAIN = {
    "sber_spend_pc_log": ("высокие безналичные траты на жителя", "низкие безналичные траты на жителя"),
    "sber_rel_trend": ("опережающий рост трат", "отставание роста трат"),
    "sber_ilr1": ("продукты важнее здоровья в тратах", "выше доля трат на здоровье"),
    "sber_ilr2": ("ниже доля общепита", "выше доля общепита"),
    "sber_ilr3": ("ниже доля маркетплейсов", "выше доля маркетплейсов"),
    "sber_ilr4": ("ниже доля транспорта", "выше доля транспорта в тратах"),
    "sber_ilr5": ("ниже доля прочих трат", "выше доля прочих трат"),
    "proc44_pc_log": ("высокий госзаказ на жителя", "низкий госзаказ на жителя"),
    "proc44_muni_share": ("преобладают муниципальные заказчики", "велика доля региональных/федеральных заказчиков"),
    "supplier_hhi": ("концентрированные поставщики", "раздробленные поставщики"),
    "procgeo_ilr1": ("больше местных поставщиков", "поставщики из других МО РБ"),
    "procgeo_ilr2": ("поставщики внутри РБ", "поставщики из-за пределов РБ"),
    "proc223_pc_log": ("заметные закупки госкомпаний (223-ФЗ)", "почти нет закупок госкомпаний (223-ФЗ)"),
    "pop_growth": ("рост населения", "быстрое сокращение населения"),
    "natinc_rate": ("естественный прирост выше", "сильная естественная убыль"),
    "migr_rate": ("миграционный приток", "миграционный отток"),
    "age_ilr1": ("много детей", "мало детей"),
    "age_ilr2": ("молодое население", "старшее население (65+)"),
}
# для знаковых показателей формулировка учитывает знак медианы типа, а не только отличие от остальных:
# «миграционный приток» — только если медиана сальдо > 0; иначе «меньший миграционный отток»
SIGNED = {
    "pop_growth": (("рост населения", "медленное сокращение населения"), ("слабый рост населения", "быстрое сокращение населения")),
    "natinc_rate": (("естественный прирост", "меньшая естественная убыль"), ("низкий естественный прирост", "сильная естественная убыль")),
    "migr_rate": (("миграционный приток", "меньший миграционный отток"), ("слабый миграционный приток", "сильный миграционный отток")),
}


def plain(f: str, diff: float, median_raw: float | None = None) -> str:
    if f in SIGNED and median_raw is not None and np.isfinite(median_raw):
        hi, lo = SIGNED[f]
        return (hi if diff > 0 else lo)[0 if median_raw > 0 else 1]
    return PLAIN[f][0 if diff > 0 else 1]


DESCR = ["share_local_suppliers", "share_outside_rb_suppliers", "ufa_share_of_other_rb", "msp2026_supplier_value_share"]


def stage_passports(R: Run, d: F.Data, panel: pd.DataFrame, S0: dict, level: str = "macro") -> pd.DataFrame:
    fin = R.final if level == "macro" else R.detailed
    lab = pd.Series(fin["labels"], index=S0["nodes"])
    feats = sum(F.BLOCKS.values(), [])
    wide = F.wide(panel, "static", "retrospective", feats + DESCR).reindex(S0["nodes"])
    raw = wide.copy()
    raw["spend_rub_month"] = np.exp(raw["sber_spend_pc_log"])
    raw["proc44_rub_pc_year"] = np.expm1(raw["proc44_pc_log"])
    raw["share_65plus"] = R.ext_age["share_65plus"].reindex(S0["nodes"])
    pop = d.pop["2024-01-01"].reindex(S0["nodes"])
    z = NW.robust_z(wide[feats])
    ext = R.ext.reindex(S0["nodes"])
    stab = R.node_stability.set_index(pd.Index(S0["nodes"]))
    rows, names = [], {}
    for c in sorted(lab.unique()):
        mem = lab.index[lab == c]
        diff = (z.loc[mem].median() - z.drop(mem).median()).sort_values(key=np.abs, ascending=False)
        top = diff.index[:3].tolist()
        # имя по отличительным признакам (без якорных МО)
        medraw = {f: float(wide.loc[mem, f].median()) for f in top}
        parts = [plain(f, diff[f], medraw[f]) for f in top[:2]]
        lqc = [x for x in ext.columns if x.startswith("msp_lq_") and not x.startswith("msp_lq_raw")]
        spec = ext.loc[mem, lqc].median().sort_values(ascending=False)
        names[c] = f"Тип {c + 1}: " + "; ".join(parts)
        st = stab.loc[mem, "node_subsample" if level == "macro" else "node_subsample_detailed"]
        rows.append(dict(cluster=int(c), name=names[c], n_mo=len(mem), population_2024=int(pop.loc[mem].sum()),
                         members=", ".join(d.mo.name[mm] for mm in mem),
                         distinctive_1=f"{top[0]} ({diff[top[0]]:+.2f} IQR-z)", distinctive_2=f"{top[1]} ({diff[top[1]]:+.2f})",
                         distinctive_3=f"{top[2]} ({diff[top[2]]:+.2f})",
                         median_spend_rub_month=float(raw.loc[mem, "spend_rub_month"].median()),
                         median_proc44_rub_pc_year=float(raw.loc[mem, "proc44_rub_pc_year"].median()),
                         median_pop_growth=float(raw.loc[mem, "pop_growth"].median()),
                         median_natinc=float(raw.loc[mem, "natinc_rate"].median()), median_migr=float(raw.loc[mem, "migr_rate"].median()),
                         median_share_local_suppliers=float(raw.loc[mem, "share_local_suppliers"].median()),
                         median_share_65plus=float(raw.loc[mem, "share_65plus"].median()),
                         ext_wage_main_share=float(ext.loc[mem, "ext_census_wage_main_share"].median()),
                         ext_pension_main_share=float(ext.loc[mem, "ext_census_pension_benefit_main_share"].median()),
                         ext_higher_edu=float(ext.loc[mem, "ext_census_higher_edu_share"].median()),
                         ext_urban_share_v4=float(ext.loc[mem, "ext_urban_share_v4"].median()),
                         msp_lq_agri=float(ext.loc[mem, "msp_lq_agri"].median()), msp_lq_industry=float(ext.loc[mem, "msp_lq_industry"].median()),
                         msp_lq_business_services=float(ext.loc[mem, "msp_lq_business_services"].median()),
                         msp_top_specialization=f"{spec.index[0].replace('msp_lq_', '')} (LQ={spec.iloc[0]:.2f})",
                         distinctive_plain="; ".join(plain(f, diff[f], medraw[f]) for f in top),
                         stability_median=float(st.median()),
                         boundary_mo=", ".join(d.mo.name[mm] for mm in st.index[st < 0.5]),
                         typical_examples=", ".join(d.mo.name[mm] for mm in st.sort_values(ascending=False).index[:3])))
    if level == "macro":
        R.type_names = names
        return R.save(pd.DataFrame(rows), "TYPE_PASSPORTS")
    R.type_names_detailed = names
    return R.save(pd.DataFrame(rows), "TYPE_PASSPORTS_DETAILED")


def stage_external_validation(R: Run, S0: dict) -> pd.DataFrame:
    fin = R.final
    cr = R.cfg["correlations"]
    Wsp = NW.spatial_weights(S0["names"])
    R.Wsp = Wsp
    ext = R.ext.reindex(S0["nodes"])
    rows = []
    for col in [c for c in ext.columns if c.startswith(("ext_", "msp_lq_")) and not c.startswith("msp_lq_raw")]:
        y = ext[col].to_numpy(dtype=float)
        m = np.isfinite(y)
        sur = None
        if m.sum() > 5:   # пространственные суррогаты по подграфу наблюдаемых МО
            sur = np.full((499 if not R.quick else 49, len(y)), np.nan)
            sur[:, m] = S.msr_surrogates(y[m], Wsp[np.ix_(m, m)], sur.shape[0], R.seed)
        for labname, lab in [("v5_final", fin["labels"]), ("v5_detailed", R.detailed["labels"]), ("v4_published", R.v4lab)]:
            r = S.cluster_vs_external(lab, y, B=1999 if not R.quick else 99, seed=R.seed, surrogate_y=sur)
            rows.append(dict(indicator=col, labeling=labname, used_in_v5_training="no",
                             used_in_v4_training="yes" if col.endswith("_v4") or col == "ext_market_access_sber" else "no",
                             moran_I=S.moran_I(y[m], Wsp[np.ix_(m, m)]) if m.sum() > 3 else np.nan, **{k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in r.items()}))
    df = pd.DataFrame(rows)
    for lb in df.labeling.unique():
        mm = df.labeling == lb
        df.loc[mm, "q_bh_perm"] = S.fdr(df.loc[mm, "p_perm"].to_numpy(), "bh")
        df.loc[mm, "q_by_perm"] = S.fdr(df.loc[mm, "p_perm"].to_numpy(), "by")
        if "p_spatial" in df:
            df.loc[mm, "q_bh_spatial"] = S.fdr(df.loc[mm, "p_spatial"].to_numpy(), "bh")
    return R.save(df, "EXTERNAL_VALIDATION")


def stage_correlations(R: Run, panel: pd.DataFrame, S0: dict) -> pd.DataFrame:
    cr = R.cfg["correlations"]
    feats = sum(F.BLOCKS.values(), [])
    W = F.wide(panel, "static", "retrospective", feats).reindex(S0["nodes"])
    ext = R.ext.reindex(S0["nodes"])
    ext_cols = [c for c in ext.columns if c.startswith(("ext_", "msp_lq_")) and not c.startswith("msp_lq_raw")]
    Wsp = R.Wsp
    logpop = np.log(R.pop2024.reindex(S0["nodes"]).to_numpy(dtype=float))
    rows = []
    Bp = 999 if R.quick else cr["B_perm"]
    for f in feats:
        x = W[f].to_numpy(dtype=float)
        for e in ext_cols:
            y = ext[e].to_numpy(dtype=float)
            m = np.isfinite(x) & np.isfinite(y)
            sur = S.msr_surrogates(y[m], Wsp[np.ix_(m, m)], 199 if R.quick else cr["B_spatial"], R.seed) if m.sum() > 5 else None
            for meth in ("pearson", "spearman"):
                r = S.corr_test(x, y, meth, B=Bp, seed=R.seed, ci_B=200 if R.quick else cr["ci_B"])
                rs = S.corr_test(x[m], y[m], meth, seed=R.seed, ci_B=10, null_y=sur) if sur is not None else {}
                # контроль масштаба: частная корреляция по остаткам на log(население)
                xr = x[m] - np.polyval(np.polyfit(logpop[m], x[m], 1), logpop[m])
                yr = y[m] - np.polyval(np.polyfit(logpop[m], y[m], 1), logpop[m])
                rp = S.corr_test(xr, yr, meth, B=999, seed=R.seed, ci_B=10)
                # без Уфы (влияние крупнейшего выброса)
                keep = np.array([nm != "ГО Уфа" for nm in S0["names"]])
                ru = S.corr_test(x[keep], y[keep], meth, B=999, seed=R.seed, ci_B=10)
                rows.append(dict(family=f"features_x_external[{meth}]", feature=f, indicator=e, method=meth, period="static 2023-01…2024-12 (retrospective)",
                                 r=r["r"], n=r["n"], n_missing=r["n_missing"], ci_lo=r["ci_lo"], ci_hi=r["ci_hi"], p_asym=r["p_asym"], p_perm=r.get("p_perm"),
                                 B=r.get("B"), seed=r.get("seed"), p_spatial=rs.get("p_perm"), r_partial_logpop=rp["r"], p_partial_logpop=rp.get("p_perm"),
                                 r_without_ufa=ru["r"]))
    df = pd.DataFrame(rows)
    for fam in df.family.unique():
        mm = df.family == fam
        df.loc[mm, "q_bh"] = S.fdr(df.loc[mm, "p_perm"].to_numpy(), "bh")
        df.loc[mm, "q_by"] = S.fdr(df.loc[mm, "p_perm"].to_numpy(), "by")
        df.loc[mm, "q_bh_spatial"] = S.fdr(df.loc[mm, "p_spatial"].to_numpy(), "bh")
        df.loc[mm, "ebh_reject_0.05"] = EM.e_bh(df.loc[mm, "p_perm"].to_numpy(), 0.05)
    df["robust"] = (df.q_by < 0.05) & (df.q_bh_spatial < 0.05) & (np.sign(df.r) == np.sign(df.r_partial_logpop)) & (np.sign(df.r) == np.sign(df.r_without_ufa)) & (df.ci_lo * df.ci_hi > 0)
    # панель: between/within для изменяющихся во времени признаков (мониторинг, кварталы после warm-up)
    tv = ["sber_spend_pc_log", "sber_rel_trend", "proc44_pc_log", "supplier_hhi", "procgeo_ilr1", "proc223_pc_log"]
    p = panel[(panel["mode"] == "monitoring") & panel.period.isin(F.QUARTERS[3:]) & panel.feature.isin(tv)]
    pw = p.pivot_table(index=["mo_id", "period"], columns="feature", values="value").reset_index().rename(columns={"mo_id": "mo"})
    pw = pw[pw.mo.isin(S0["nodes"])]
    wrows = []
    for i, a in enumerate(tv):
        for b in tv[i + 1:]:
            r = S.within_between(pw, a, b, "mo", B=200 if R.quick else 2000, seed=R.seed)
            wrows.append(dict(family="panel_within_between[pearson]", feature=a, indicator=b, method="pearson",
                              period="2023Q4…2024Q4 скользящие окна (monitoring)", **{k: v for k, v in r.items() if k != "status"}))
    wb = pd.DataFrame(wrows)
    # дублирующие признаки (|r| > 0.8 между признаками модели)
    C = W.corr(method="spearman")
    dup = [dict(family="feature_redundancy[spearman]", feature=a, indicator=b, method="spearman", r=float(C.loc[a, b]))
           for i, a in enumerate(feats) for b in feats[i + 1:] if abs(C.loc[a, b]) > 0.8]
    out = pd.concat([df, wb, pd.DataFrame(dup)], ignore_index=True)
    R.save(C.reset_index().rename(columns={"index": "feature"}), "FEATURE_CORR_MATRIX")
    return R.save(out, "CORRELATIONS_MO_PERIOD", parquet=True)


def stage_holdout(R: Run, d: F.Data, S0: dict) -> pd.DataFrame:
    """Проверка вне периода обучения (п. 3.6): узнаётся ли тип 2023–2024 по одному блоку закупок 2025 и 2026 гг.
    Ближайший центроид блоков proc_budget+proc_geo (223-ФЗ — разрыв покрытия в 2025), стандартизация — по 2023–2024.
    Нуль: случайная перестановка ПРЕДСКАЗАННЫХ меток при фиксированных референтных (сохраняет фактическое
    распределение обеих разметок); p = (b+1)/(B+1). Проверяет воспроизводимость разметки по закупкам,
    а не независимую экономическую истинность типов."""
    from . import networks as NW2
    # блок 223-ФЗ исключён: в 2025 г. в выгрузке 1 340 записей против 35 631 в 2023 г. — разрыв покрытия источника, не экономики
    cols = F.BLOCKS["proc_budget"] + F.BLOCKS["proc_geo"]
    nodes = S0["nodes"]
    # число контрактов 44-ФЗ — ровно по тем кварталам, что вошли в блок (2026: январь–сентябрь, без октября)
    n44 = lambda qs: int(((d.contracts.law == "44-ФЗ") & d.contracts.quarter.isin(qs)).sum())

    def block(quarters, pop):
        pr = F.procurement(d, quarters, pop, F.CUSTOMER_GEO_INCLUSIVE)
        return NW2.transform(pr[cols].reindex(nodes))

    base = block(F.QUARTERS, d.pop["2024-01-01"])
    med, iqr = base.median(), (base.quantile(.75) - base.quantile(.25)).replace(0, np.nan) / 1.349
    z = lambda df: ((df - med) / iqr).clip(-4, 4)
    Zb = z(base).to_numpy()
    rows, preds, conf = [], [], []
    rng = np.random.default_rng(R.seed)
    for lvl, lab in (("macro", R.final["labels"]), ("detailed", R.detailed["labels"])):
        ks = np.unique(lab)
        okb = np.isfinite(Zb).all(1)
        cent = np.array([Zb[okb & (lab == k)].mean(0) for k in ks])
        # первая строка — та же процедура на обучающем периоде (потолок точности ближайшего центроида по одному блоку)
        for year, qs, pref in (("2023–2024 (в выборке)", F.QUARTERS, "2024-01-01"), ("2025", [f"2025Q{q}" for q in range(1, 5)], "2025-01-01"),
                               ("2026", [f"2026Q{q}" for q in range(1, 4)], "2025-01-01")):
            Zy = z(block(qs, d.pop[pref])).to_numpy()
            ok = np.isfinite(Zy).all(1)
            pred = ks[np.argmin(((Zy[ok][:, None, :] - cent[None]) ** 2).sum(-1), axis=1)]
            ref = lab[ok]
            acc = float((pred == ref).mean())
            # accuracy одна мало что говорит: рядом доля самого частого типа и balanced accuracy
            maj = float(np.bincount(ref).max() / len(ref))
            bal = float(np.mean([(pred[ref == k] == k).mean() for k in np.unique(ref)]))
            for r_, p_ in zip(*np.unique(np.c_[ref, pred], axis=0, return_counts=True)):
                conf.append(dict(level=lvl, year=year, reference=int(r_[0]), predicted=int(r_[1]), n=int(p_)))
            B = 9999
            null = np.array([(rng.permutation(pred) == ref).mean() for _ in range(B)])
            b = int((null >= acc - 1e-12).sum())
            rows.append(dict(level=lvl, year=year, n=int(ok.sum()), accuracy=acc, majority_baseline=maj, balanced_accuracy=bal,
                             ari=float(adjusted_rand_score(ref, pred)), nmi=float(normalized_mutual_info_score(ref, pred)),
                             null_mean=float(null.mean()),
                             null_q95=float(np.quantile(null, .95)), p_value=S.mc_p(b, B), B=B, seed=R.seed,
                             features=";".join(cols), n_contracts_44=n44(qs), quarters=f"{qs[0]}–{qs[-1]}",
                             null="перестановка предсказанных меток при фиксированных референтных",
                             period_note={"2026": "январь–сентябрь (YTD), не полный год", "2025": "полный год"}.get(year, "обучающий период: потолок точности")))
            preds += [dict(level=lvl, year=year, mo=S0["names"][i], reference=int(r_), predicted=int(p_))
                      for i, r_, p_ in zip(np.flatnonzero(ok), ref, pred)]
    R.save(pd.DataFrame(preds), "HOLDOUT_PREDICTIONS")
    R.save(pd.DataFrame(conf), "HOLDOUT_CONFUSION")
    return R.save(pd.DataFrame(rows), "HOLDOUT_VALIDATION")


def stage_mezhgorye(R: Run, d: F.Data, panel: pd.DataFrame, S0: dict) -> dict:
    """ЗАТО Межгорье: нет наблюдаемого блока СберИндекса и муниципальной демографии Росстата.
    Тип не присваивается основной моделью; приводится ближайший центроид по доступным блокам (статус отдельный)."""
    mz = int(d.mo.index[d.mo.name == "ГО Межгорье"][0])
    avail = ["proc_budget", "proc_geo", "proc_corp"]
    X, cols, info = NW.x_new(panel, S0["nodes"] + [mz], "static", "retrospective", avail)
    lab = R.final["labels"]
    cents = np.array([X[:-1][lab == c].mean(0) for c in np.unique(lab)])
    dist = np.sqrt(((cents - X[-1]) ** 2).sum(1))
    res = dict(mo="ГО Межгорье", status="assigned_on_partial_blocks_without_sberindex", blocks_used=avail,
               nearest_type=int(np.unique(lab)[dist.argmin()]), distances=dist.round(3).tolist(),
               note="Траты СберИндекса для ЗАТО отсутствуют (в v4 были KNN-импутированы); муниципальные таблицы Росстата ЗАТО не включают.")
    json.dump(res, open(R.out / "MEZHGORYE_STATUS.json", "w"), ensure_ascii=False, indent=1)
    return res


def stage_store(R: Run, S0: dict, d: F.Data):
    fm, fd = R.final["labels"], R.detailed["labels"]
    R.save(pd.DataFrame({"mo": S0["names"], "macro": fm, "macro_name": [R.type_names[c] for c in fm],
                         "detailed": fd, "detailed_name": [R.type_names_detailed[c] for c in fd],
                         "v4_published": R.v4lab}), "LABELS_STATIC")
    con = DB.connect(R.db_path)
    con.execute("INSERT OR REPLACE INTO run VALUES (?,?,?,?,?,?,?,?)", (R.run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                                       R.config_hash, R.code_hash, R.data_hash, "full" if not R.quick else "quick", R.seed,
                                                                       json.dumps(dict(final=dict(config=R.final["config"], method=R.final["method"], k=R.final["k"])))))
    ids = {d.mo.name[m]: m for m in d.mo.index}
    rows = []
    for r in R.labels_period.itertuples():
        rows.append((R.run_id, f"dynamic|{r.mode}|beta={r.beta}", r.period, ids[r.mo], int(r.label)))
    for name, lab in R.comparison_labels.items():
        for nm, l in zip(S0["names"], lab):
            rows.append((R.run_id, name[:200], "static", ids[nm], int(l)))
    for r in getattr(R, "labels_period_detailed", pd.DataFrame()).itertuples():
        rows.append((R.run_id, f"dynamic_detailed|{r.mode}|beta={r.beta}", r.period, ids[r.mo], int(r.label)))
    con.executemany("INSERT OR REPLACE INTO run_labels VALUES (?,?,?,?,?)", rows)
    er = []
    layers = {"attr_self_tuning": S0["An"], **S0["sn"]}
    for lname, M in layers.items():
        iu = np.triu_indices(len(M), 1)
        for i, j in zip(*iu):
            if M[i, j] > 0:
                er.append((R.run_id, f"C4_v5features_v5graph|layer:{lname}", int(S0["nodes"][i]), int(S0["nodes"][j]), float(M[i, j])))
    for c, v in S0["cfgs"].items():
        for tag, M in (("exact", v["W"]), ("display_k4", NW.display_projection(v["W"]))):
            iu = np.triu_indices(len(M), 1)
            for i, j in zip(*iu):
                if M[i, j] > 0:
                    er.append((R.run_id, f"{c}|{tag}", int(S0["nodes"][i]), int(S0["nodes"][j]), float(M[i, j])))
    con.executemany("INSERT OR REPLACE INTO run_matrix_edges VALUES (?,?,?,?,?)", er)
    ic = []
    for r in R.sweep.itertuples():
        for k in ["SW", "CH", "DB", "S_Dbw", "S_Dbw_floor1", "AVI", "AVU", "MQ_newman", "MQ_mancoridis", "intra_inter_density_ratio"]:
            ic.append((R.run_id, r.config, "static", r.method, int(r.k), k, getattr(r, k), I.DIRECTION.get(k), I.SPACE.get(k),
                       f"W_exact[{r.config}]" if I.SPACE.get(k) == "network" else f"X[{r.config}]", None))
    con.executemany("INSERT OR REPLACE INTO run_icvi VALUES (?,?,?,?,?,?,?,?,?,?,?)", ic)
    co = []
    for scheme, (a, c) in R.uncert.items():
        P = c.matrix()
        for i in range(len(P)):
            for j in range(i + 1, len(P)):
                co.append((R.run_id, scheme, int(S0["nodes"][i]), int(S0["nodes"][j]), None if np.isnan(P[i, j]) else float(P[i, j]), int(c.obs[i, j])))
    con.executemany("INSERT OR REPLACE INTO run_coassign VALUES (?,?,?,?,?,?)", co)
    con.commit()
    integ = DB.integrity(con)
    exp = DB.export_parquet(con, ["mo", "source_registry", "fact_mo", "fact_region_control", "tax_office_map", "org_geo_resolved",
                                  "attribute_mo_period", "run", "run_labels", "run_icvi", "run_matrix_edges", "run_coassign",
                                  "data_quality_checks"], ROOT / "outputs" / "db_parquet")
    con.close()
    return dict(integrity=integ, parquet=exp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="уменьшенные B/K для проверки работоспособности")
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    _capture_warnings()
    cfg = NW.load_config(Path(a.config) if a.config else None)
    R = Run(cfg, a.quick)
    print("run_id", R.run_id, flush=True)
    d = F.Data(R.db_path)
    R.tic("load")
    panel = stage_panel(R, d)
    R.ext_age, _ = F.age_structure(d)
    R.pop2024 = d.pop["2024-01-01"]
    R.tic("panel")
    nodes = [m for m in d.mo.index if d.mo.name[m] not in cfg["features"]["exclude_nodes_main"]]
    S0 = build_static(R, d, panel, nodes)
    R.S0 = S0
    stage_graph_diagnostics(R, S0)
    R.tic("graphs")
    stage_sweeps(R, S0)
    R.tic("sweeps")
    stage_comparison(R, S0, d)
    R.tic("comparison")
    stage_ablation(R, S0, panel)
    R.tic("ablation")
    stage_uncertainty(R, S0, d, panel)
    R.tic("uncertainty")
    stage_dynamics(R, d, panel, nodes, "macro")
    stage_dynamics(R, d, panel, nodes, "detailed")
    R.tic("dynamics")
    leak = stage_leakage_test(R, d, nodes)
    R.tic("leakage_test")
    stage_passports(R, d, panel, S0, "macro")
    stage_passports(R, d, panel, S0, "detailed")
    stage_external_validation(R, S0)
    R.tic("passports_validation")
    stage_correlations(R, panel, S0)
    R.tic("correlations")
    stage_holdout(R, d, S0)
    R.tic("holdout")
    mz = stage_mezhgorye(R, d, panel, S0)
    store = stage_store(R, S0, d)
    R.tic("store")
    import resource
    manifest = dict(run_id=R.run_id, config_hash=R.config_hash, code_hash=R.code_hash, data_hash=R.data_hash, seed=R.seed,
                    quick=R.quick, final=dict(config=R.final["config"], method=R.final["method"], k=R.final["k"]),
                    macro=dict(k=R.macro["k"]), detailed=dict(config=R.detailed["config"], method=R.detailed["method"], k=R.detailed["k"]),
                    type_names={int(k): v for k, v in R.type_names.items()},
                    type_names_detailed={int(k): v for k, v in R.type_names_detailed.items()},
                    leakage_test=leak, mezhgorye=mz, store=store, timings=R.timings,
                    peak_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
                    N=len(nodes), T_months=len(F.MONTHS), T_quarters=len(F.QUARTERS),
                    E_exact_C4=int(G.diagnostics(S0["cfgs"]["C4_v5features_v5graph"]["W"])["edges"]),
                    diagnostics_warnings=DIAG[:200], n_warnings=len(DIAG))
    json.dump(manifest, open(R.out / "RUN_MANIFEST.json", "w"), ensure_ascii=False, indent=1, default=str)
    latest = ROOT / "outputs" / ("latest_quick" if R.quick else "latest")
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(R.out, latest)
    print(json.dumps(dict(run_id=R.run_id, final=manifest["final"], leakage=leak["status"], seconds=R.timings), ensure_ascii=False))


if __name__ == "__main__":
    main()
