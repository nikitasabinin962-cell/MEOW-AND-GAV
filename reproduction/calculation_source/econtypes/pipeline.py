"""Полный пайплайн: данные из базы → признаки → сети → кластеризация → ICVI → динамика → результаты.

Запуск:  econtypes run   (или python -m econtypes.pipeline --config config/config.yaml)
Результаты: outputs/tables/*.csv, outputs/results.json (для лендинга), outputs/figures/*.png
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import adjusted_rand_score

from econtypes import region as REG
from econtypes import clustering as C, db, dynamics as Dy, features as F, icvi as I, networks as N, prepare as P

warnings.filterwarnings("ignore")


def build_layers(cfg, raw, nodes, months=None):
    """Долгосрочные слои по рядам трат + расстояние."""
    nc = cfg["network"]
    n = len(nodes)
    Y = F.sber_monthly(raw["cons"], raw["id_map"]).reindex(nodes)
    if months is not None:
        Y = Y[[c for c in Y.columns if c in months]]
    Y = Y.dropna()
    R = N.residual_series(Y)
    idx = [nodes.index(m) for m in R.index]

    def embed(S):
        M = np.zeros((n, n))
        M[np.ix_(idx, idx)] = S
        return M

    ll, lead = N.lead_lag(R, nc["max_lag"])
    lead_full = np.zeros((n, n), dtype=int)
    lead_full[np.ix_(idx, idx)] = lead
    layers = {
        "comovement": embed(N.comovement(R)),
        "lead_lag": embed(ll),
        "dtw": embed(N.dtw_similarity(R, nc["dtw_window"])),
    }
    D = N.road_distance(raw["connection"], raw["id_map"], nodes)
    layers["distance"] = N.distance_similarity(D)
    return layers, lead_full, D, R


def select_k(res: pd.DataFrame, method: str, min_size: int) -> int:
    """k с максимальным средним нормированным (на случайную базовую линию) ICVI."""
    r = res[(res.method == method) & (res.minsize >= min_size)]
    return int(r.sort_values("z_mean", ascending=False).iloc[0]["k"])


def name_clusters(final: np.ndarray, nodes: list[str], anchors: dict, tab: pd.DataFrame | None = None) -> dict:
    """Имена кластеров задаются в config через «якорные» МО: кластер, содержащий якорь,
    получает соответствующее название (метки кластеров от запуска к запуску могут
    переставляться, якоря — нет). Для кластеров без якоря (новый регион, первый запуск)
    имя строится автоматически по двум признакам, сильнее всего отличающим тип от остальных МО."""
    from .labels import label
    names = {}
    for mo, name in (anchors or {}).items():
        if mo in nodes:
            c = int(final[nodes.index(mo)])
            names.setdefault(c, name)
    for c in np.unique(final):
        c = int(c)
        if c in names:
            continue
        if tab is not None and len(tab):
            t = tab.reindex(nodes).select_dtypes("number")
            iqr = (t.quantile(.75) - t.quantile(.25)).replace(0, np.nan)
            d = ((t[final == c].median() - t[final != c].median()) / iqr).dropna()
            top = d.abs().sort_values(ascending=False).index[:2]
            low = lambda x: x[:1].lower() + x[1:]
            names[c] = f"Тип {c + 1}: " + ", ".join(("выше " if d[k] > 0 else "ниже ") + low(label(k)) for k in top)
        else:
            names[c] = f"Тип {c + 1}"
    return names


def run(cfg: dict, eng) -> dict:
    nc, cc = cfg["network"], cfg["clustering"]
    out = Path(cfg["paths"]["outputs"]); (out / "tables").mkdir(parents=True, exist_ok=True)
    interim = Path(cfg["paths"]["interim"]); interim.mkdir(parents=True, exist_ok=True)

    print("1/7 загрузка данных")
    raw = db.load_raw(eng)
    raw["prefix_map"].to_csv(out / "tables/inn_prefix_to_mo.csv", index=False)
    raw["id_map"].to_csv(out / "tables/sberindex_id_to_mo.csv", index=False)

    print("2/7 признаки")
    pq = P.panel(cfg, raw, cfg["data"]["window"])
    tab = pq.groupby("mo").mean()
    t, imputed, X = P.design_matrix(tab, cfg)
    nodes = list(t.index)
    tab.to_csv(out / "tables/features_raw_2023_2024.csv")

    print("3/7 сети")
    layers, lead, D, R = build_layers(cfg, raw, nodes)
    fl = F.flows(raw["contracts"], cfg["data"]["exclude_republican_customers_from_ufa"], cfg["data"]["window"])
    Fm, layers["procurement_flow"] = N.flow_matrix(fl, nodes, nc["flow_min_rub"])
    layers["attr"] = N.attr_similarity(X)
    K = {k: N.knn_sparsify(v, nc["knn"]) for k, v in layers.items()}
    struct_layers = {k: K[k] for k in nc["layer_weights"]}
    Ws = N.fuse(np.zeros_like(K["attr"]), struct_layers, nc["layer_weights"], 0.0)
    Wf = N.fuse(K["attr"], struct_layers, nc["layer_weights"], nc["alpha_attr"])

    print("4/7 сравнение методов и выбор k")
    rows, labels = [], {}
    for k in cc["k_range"]:
        for m in cc["methods"]:
            lab = C.run(m, X, Ws, Wf, k, cc)
            labels[(m, k)] = lab
            r = I.all_indices(X, Wf, lab)
            r.update(I.baseline_normalized(X, Wf, lab, cc["null_perms"], cc["random_state"]))
            r.update(method=m, k=k, k_real=len(set(lab)), minsize=int(np.bincount(lab).min()))
            rows.append(r)
    res = pd.DataFrame(rows)
    res["z_mean"] = res[[c for c in res.columns if c.startswith("z_")]].mean(axis=1)
    res.to_csv(out / "tables/icvi_methods_by_k.csv", index=False)
    k_final = cc["k_final"] or select_k(res, cc["final_method"], cc["min_cluster_size"])
    at_k = res[res.k == k_final].set_index("method")
    rank = pd.DataFrame({ix: at_k["z_" + ix].rank(ascending=False) for ix in I.HIGHER_BETTER})
    at_k["mean_rank"] = rank.mean(axis=1)
    at_k = at_k.sort_values("z_mean", ascending=False)
    at_k.to_csv(out / "tables/icvi_methods_at_k.csv")
    print(f"   k = {k_final}")
    print(at_k.round(3).to_string())

    # согласованность методов между собой
    ms = cc["methods"]
    ari_m = pd.DataFrame([[adjusted_rand_score(labels[(a, k_final)], labels[(b, k_final)]) for b in ms] for a in ms], index=ms, columns=ms)
    ari_m.to_csv(out / "tables/ari_between_methods.csv")

    final = labels[(cc["final_method"], k_final)]

    print("5/7 влияние способа построения рёбер")
    edge_rows, edge_lab = [], {}
    for name in ["attr", "comovement", "lead_lag", "dtw", "procurement_flow", "distance"]:
        lab = C.spectral(K[name], k_final, cc["random_state"])
        edge_lab[name] = lab
        r = I.all_indices(X, K[name], lab)
        r.update(edges=name, ARI_vs_final=adjusted_rand_score(final, lab), minsize=int(np.bincount(lab).min()))
        edge_rows.append(r)
    edge_lab["fused (итог)"] = final
    edges = pd.DataFrame(edge_rows)
    edges.to_csv(out / "tables/edge_construction_comparison.csv", index=False)
    en = list(edge_lab)
    pd.DataFrame([[adjusted_rand_score(edge_lab[a], edge_lab[b]) for b in en] for a in en], index=en, columns=en)\
        .to_csv(out / "tables/ari_between_edge_types.csv")
    print(edges.round(3).to_string())

    # чувствительность к α (вес атрибутов)
    sens = []
    for a in [0.0, 0.25, 0.5, 0.75, 1.0]:
        W_a = N.fuse(K["attr"], struct_layers, nc["layer_weights"], a)
        lab = C.spectral(W_a, k_final, cc["random_state"])
        r = I.all_indices(X, Wf, lab); r.update(alpha=a, ARI_vs_final=adjusted_rand_score(final, lab))
        sens.append(r)
    pd.DataFrame(sens).to_csv(out / "tables/alpha_sensitivity.csv", index=False)

    # чувствительность к весам слоёв: исключение слоя, равные веса, случайные возмущения
    lw = nc["layer_weights"]
    schemes = {"итоговые веса": dict(lw), "равные веса": {k: 1.0 for k in lw}}
    for drop in lw:
        schemes[f"без слоя {drop}"] = {k: v for k, v in lw.items() if k != drop}
    rng_w = np.random.default_rng(cc["random_state"])
    keys, base = list(lw), np.array(list(lw.values()))
    for t in range(cfg["clustering"].get("weight_perturbations", 50)):
        schemes[f"возмущение {t + 1}"] = dict(zip(keys, rng_w.dirichlet(base * 20)))
    wrows = []
    for name, w in schemes.items():
        W_w = N.fuse(K["attr"], {k: struct_layers[k] for k in w}, w, nc["alpha_attr"])
        lab = C.spectral(W_w, k_final, cc["random_state"])
        r = I.all_indices(X, W_w, lab)
        r.update(scheme=name, ARI_vs_final=adjusted_rand_score(final, lab), minsize=int(np.bincount(lab).min()),
                 **{"w_" + k: w.get(k, 0.0) / sum(w.values()) for k in keys})
        wrows.append(r)
    pd.DataFrame(wrows).to_csv(out / "tables/layer_weight_sensitivity.csv", index=False)

    print("6/7 устойчивость (бутстреп узлов) и пространственная проверка")
    rng = np.random.default_rng(cc["random_state"])
    n = len(nodes)
    co, cnt, aris = np.zeros((n, n)), np.zeros((n, n)), []
    for _ in range(cfg["dynamics"]["bootstrap"]):
        s = np.sort(rng.choice(n, int(0.8 * n), replace=False))
        lab = C.spectral(Wf[np.ix_(s, s)], k_final, int(rng.integers(1e6)))
        aris.append(adjusted_rand_score(final[s], lab))
        same = lab[:, None] == lab[None, :]
        co[np.ix_(s, s)] += same
        cnt[np.ix_(s, s)] += 1
    P_co = co / np.maximum(cnt, 1)
    node_stab = np.array([P_co[i, final == final[i]].mean() for i in range(n)])
    # пространственная связность: среднее расстояние внутри кластера vs случайные разбиения
    def within_dist(lab):
        v = [np.nanmean(D[np.ix_(lab == c, lab == c)][np.triu_indices((lab == c).sum(), 1)]) for c in np.unique(lab) if (lab == c).sum() > 1]
        return float(np.nanmean(v))
    obs = within_dist(final)
    null = [within_dist(rng.permutation(final)) for _ in range(1000)]
    spatial = dict(within_km=obs, random_mean_km=float(np.mean(null)), p_value=float(np.mean(np.array(null) <= obs)))
    print("   бутстреп ARI:", np.round(np.mean(aris), 3), " пространство:", spatial)

    print("7/7 динамика по кварталам")
    periods = sorted(pq.index.get_level_values("period").unique())
    # признаки квартала t = среднее за скользящее окно из последних dyn_window кварталов:
    # гасит сезонность бюджетного цикла (годовые контракты в I квартале) и разовые крупные контракты
    pq_roll = pq.groupby(level="mo", group_keys=False).apply(
        lambda g: g.rolling(cfg["dynamics"]["rolling_quarters"], min_periods=1).mean())
    W_q = {}
    for p in periods:
        tq = pq_roll.xs(p, level="period").reindex(nodes)
        _, _, Xq = P.design_matrix(tq, cfg)
        Aq = N.knn_sparsify(N.attr_similarity(Xq), nc["knn"])
        win = [x for x in periods if x <= p][-cfg["dynamics"]["rolling_quarters"]:]
        _, Fq = N.flow_matrix(fl[fl.period.isin(win)], nodes, nc["flow_min_rub"])
        lq = dict(struct_layers); lq["procurement_flow"] = N.knn_sparsify(Fq, nc["knn"])
        W_q[p] = N.fuse(Aq, lq, nc["layer_weights"], nc["alpha_attr"])

    def evolve(beta):
        W_prev, dyn, q = None, {}, []
        for p in periods:
            W_s = W_q[p] if W_prev is None else (1 - beta) * W_q[p] + beta * W_prev
            W_prev = W_s
            lab = C.spectral(W_s, k_final, cc["random_state"])
            q.append(I.modularity(W_q[p], lab))      # качество относительно «сырой» сети квартала
            dyn[str(p)] = Dy.align(lab, final)
        return dyn, float(np.mean(q))

    beta_rows = []
    for b in cfg["dynamics"]["beta_grid"]:
        d_b, q_b = evolve(b)
        lb = pd.DataFrame(d_b, index=nodes)
        beta_rows.append(dict(beta=b, snapshot_MQ=q_b, temporal_ARI=float(Dy.stability(lb).ARI.mean()),
                              ARI_vs_static=float(np.mean([adjusted_rand_score(final, lb[c]) for c in lb]))))
    beta_df = pd.DataFrame(beta_rows)
    beta_df.to_csv(out / "tables/dynamics_beta_sensitivity.csv", index=False)
    print(beta_df.round(3).to_string())
    dyn, _ = evolve(cfg["dynamics"]["smoothing_beta"])
    lab_df = pd.DataFrame(dyn, index=nodes)
    stab_t = Dy.stability(lab_df)
    trans = Dy.transitions(lab_df)
    switches = (lab_df.diff(axis=1).iloc[:, 1:] != 0).sum(axis=1)
    print(stab_t.round(3).to_string())

    # профили и имена кластеров
    prof = tab.assign(cl=final).groupby("cl").mean()
    names = name_clusters(final, nodes, cfg["viz"].get("cluster_anchors"), tab)
    macro = labels[(cc["final_method"], cc["macro_k"])] if (cc["final_method"], cc.get("macro_k")) in labels else final
    macro_names = name_clusters(macro, nodes, cfg["viz"].get("macro_anchors"), tab)
    nest = pd.crosstab(pd.Series([names[c] for c in final], name="detailed"), pd.Series([macro_names[c] for c in macro], name="macro"))
    nest.to_csv(out / "tables/macro_vs_detailed.csv")
    rngm = np.random.default_rng(cc["random_state"])
    macro_boot = []
    for _ in range(cfg["dynamics"]["bootstrap"]):
        s_ = np.sort(rngm.choice(n, int(0.8 * n), replace=False))
        macro_boot.append(adjusted_rand_score(macro[s_], C.spectral(Wf[np.ix_(s_, s_)], cc["macro_k"], int(rngm.integers(1e6)))))
    print("   макро-уровень k =", cc["macro_k"], "бутстреп ARI:", round(float(np.mean(macro_boot)), 3))
    summary = pd.DataFrame({
        "mo": nodes, "cluster": final, "cluster_name": [names[c] for c in final],
        "macro": macro, "macro_name": [macro_names[c] for c in macro],
        "bootstrap_stability": node_stab.round(3), "quarter_switches": switches.values,
        "imputed_sber": imputed.values,
    }).merge(tab.reset_index(), on="mo")
    summary.to_csv(out / "tables/clusters_final.csv", index=False)
    prof.assign(name=[names[c] for c in prof.index], size=np.bincount(final)).to_csv(out / "tables/cluster_profiles.csv")
    lab_df.to_csv(out / "tables/clusters_by_quarter.csv")
    stab_t.to_csv(out / "tables/quarter_ari.csv", index=False)
    trans.to_csv(out / "tables/quarter_transitions.csv")

    # лидеры по лаговой связи: пары с наибольшей лаговой корреляцией
    LL = layers["lead_lag"]
    iu = np.triu_indices(n, 1)
    order = np.argsort(-LL[iu])[:30]
    ll_rows = []
    for o in order:
        i, j = iu[0][o], iu[1][o]
        lg = lead[i, j]
        a, b = (nodes[i], nodes[j]) if lg > 0 else (nodes[j], nodes[i])
        ll_rows.append(dict(leader=a, follower=b, lag_months=abs(int(lg)), strength=float(LL[i, j])))
    pd.DataFrame(ll_rows).to_csv(out / "tables/lead_lag_top.csv", index=False)

    # данные для лендинга
    XY = N.road_map_layout(D, nodes, REG.ENCLAVES)  # МО без расстояний СберИндекса (config: region.enclaves)
    pd.DataFrame(XY, index=nodes, columns=["x", "y"]).to_csv(out / "tables/road_map_layout.csv")
    pos = {m: i for i, m in enumerate(nodes)}
    edges_json = []
    Wv = N.knn_sparsify(Wf, 4)
    for i, j in zip(*np.nonzero(np.triu(Wv))):
        edges_json.append(dict(s=nodes[i], t=nodes[j], w=round(float(Wv[i, j]), 3)))
    flows_top = fl.groupby(["supplier_mo", "customer_mo"])["rub"].sum().reset_index()
    flows_top = flows_top[(flows_top.supplier_mo != flows_top.customer_mo) & flows_top.supplier_mo.isin(pos) & flows_top.customer_mo.isin(pos)]
    flows_top = flows_top.sort_values("rub", ascending=False).head(150)
    Y = F.sber_monthly(raw["cons"], raw["id_map"]).reindex(nodes)
    results = dict(
        k=k_final, method=cc["final_method"], names={int(k): v for k, v in names.items()},
        nodes=[dict(mo=m, cluster=int(final[i]), x=round(float(XY[i, 0]), 4), y=round(float(XY[i, 1]), 4), stab=float(node_stab[i]), switches=int(switches.iloc[i]),
                    pop=float(raw["pop"].set_index("mo").loc[m, "pop"]),
                    quarters=[int(x) for x in lab_df.loc[m].values],
                    feats={c: (None if pd.isna(tab.loc[m, c]) else round(float(tab.loc[m, c]), 4)) for c in tab.columns},
                    spend=[None if pd.isna(v) else float(v) for v in Y.loc[m].values])
               for i, m in enumerate(nodes)],
        months=list(Y.columns), quarters=[str(p) for p in periods],
        edges=edges_json,
        flows=[dict(s=r.supplier_mo, t=r.customer_mo, rub=float(r.rub)) for r in flows_top.itertuples()],
        profiles={int(c): {k: round(float(v), 4) for k, v in prof.loc[c].items()} for c in prof.index},
        icvi_at_k=at_k.reset_index().round(4).to_dict(orient="records"),
        icvi_by_k=res.round(4).to_dict(orient="records"),
        edges_cmp=edges.round(4).to_dict(orient="records"),
        quarter_ari=stab_t.round(4).to_dict(orient="records"),
        transitions={int(a): {int(b): int(v) for b, v in row.items()} for a, row in trans.to_dict(orient="index").items()},
        beta_sensitivity=beta_df.round(4).to_dict(orient="records"), spatial=spatial, bootstrap_ari=float(np.mean(aris)), macro_k=cc["macro_k"],
        macro_names={int(k): v for k, v in macro_names.items()}, macro_bootstrap_ari=float(np.mean(macro_boot)),
        macro=[int(x) for x in macro],
        lead_lag=ll_rows[:15],
        distances={f"{nodes[i]}|{nodes[j]}": (None if np.isnan(D[i, j]) else float(D[i, j])) for i in range(n) for j in range(i + 1, n)},
    )
    json.dump(results, open(out / "results.json", "w"), ensure_ascii=False)
    pickle.dump(dict(X=X, t=t, nodes=nodes, layers=layers, K=K, Wf=Wf, Ws=Ws, final=final, lab_df=lab_df, D=D, Fm=Fm,
                     names=names, P_co=P_co, res=res, R=R), open(interim / "model.pkl", "wb"))
    # рёбра всех слоёв сети (после kNN-разрежения) + направленные денежные потоки
    erows = []
    for lname, M in list(K.items()) + [("fused", N.knn_sparsify(Wf, nc["knn"]))]:
        for i, j in zip(*np.nonzero(np.triu(M, 1))):
            lg = int(lead[i, j]) if lname == "lead_lag" else 0
            s_, t_ = (nodes[j], nodes[i]) if lg < 0 else (nodes[i], nodes[j])
            erows.append(dict(layer=lname, source=s_, target=t_, weight=round(float(M[i, j]), 4),
                              lag=abs(lg), directed=lname == "lead_lag", rub=None))
    fr = fl.groupby(["supplier_mo", "customer_mo"])["rub"].sum().reset_index()
    fr = fr[(fr.supplier_mo != fr.customer_mo) & fr.supplier_mo.isin(pos) & fr.customer_mo.isin(pos)]
    for r in fr.itertuples():
        erows.append(dict(layer="flow_rub", source=r.supplier_mo, target=r.customer_mo, weight=None,
                          lag=0, directed=True, rub=float(r.rub)))
    res_edges = pd.DataFrame(erows)
    res_edges.to_csv(out / "tables/network_edges.csv", index=False)
    # результаты — в базу (слой res_*)
    for name, df in {"res_edges": res_edges, "res_bootstrap_coassign": pd.DataFrame(P_co, index=nodes, columns=nodes).rename_axis("mo").reset_index(),
                     "res_macro_nesting": nest.reset_index(),"res_clusters": summary, "res_features": tab.reset_index(), "res_icvi": res,
                     "res_clusters_by_quarter": lab_df.rename_axis("mo").reset_index(),
                     "res_edge_comparison": edges}.items():
        db.write(eng, name, df)
    print("готово:", out)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.yaml")
    a = ap.parse_args()
    c = yaml.safe_load(open(a.config))
    run(c, db.engine(c["database"]["url"]))
