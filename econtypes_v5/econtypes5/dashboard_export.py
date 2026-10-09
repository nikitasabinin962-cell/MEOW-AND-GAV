"""Экспорт данных v5 для автономного дашборда (D5.json): только читаемые числа из outputs/latest и базы.

  python -m econtypes5.dashboard_export --out ../../-/src/v5/D5.json
Геометрия МО не дублируется: вкладка v5 использует D.geo базовой версии (тот же набор 63 МО).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from . import features as F

ROOT = Path(__file__).resolve().parents[1]


def r(x, nd=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    if isinstance(x, (np.floating, float)):
        return round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def build(latest: Path, db: Path, manifest: Path | None = None) -> dict:
    man = json.loads((latest / "RUN_MANIFEST.json").read_text())
    rd = lambda n: pd.read_csv(latest / f"{n}.csv")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    mo = pd.read_sql("SELECT mo_id, name, kind FROM mo ORDER BY mo_id", con)
    pop = pd.read_sql("SELECT mo_id, value FROM fact_mo WHERE indicator='population' AND period='2024-01-01'", con).set_index("mo_id").value
    run_id = man["run_id"]
    comp = rd("CLUSTER_COMPARISON")
    final_key = [l for l in comp.labeling if l.startswith(man["final"]["config"]) and l.endswith("|selected")][0]
    det_key = [l for l in comp.labeling if l.startswith(man["final"]["config"]) and l.endswith("|detailed")][0]
    labels = pd.read_sql("SELECT config, period, mo_id, label FROM run_labels WHERE run_id=?", con, params=[run_id])
    fin = labels[(labels.config == final_key)].set_index("mo_id").label
    det = labels[(labels.config == det_key)].set_index("mo_id").label
    v4 = labels[labels.config == "v4_published_labels(K=7)"].set_index("mo_id").label
    stab = rd("NODE_STABILITY").set_index("mo")
    pas = rd("TYPE_PASSPORTS")
    panel = pd.read_parquet(latest / "FORMULA_FEATURES_MO_PERIOD.parquet")
    st = panel[(panel.period == "static") & (panel["mode"] == "retrospective")]
    ext = rd("EXTERNAL_INDICATORS_MO").set_index("mo_id")
    feats = sum(F.BLOCKS.values(), []) + ["share_local_suppliers", "share_outside_rb_suppliers", "ufa_share_of_other_rb", "msp2026_supplier_value_share"]
    fmeta = st.drop_duplicates("feature").set_index("feature")[["unit", "block", "source", "window", "hindsight"]]
    nodes = []
    for m in mo.itertuples():
        fv = st[st.mo_id == m.mo_id].set_index("feature").value
        e = ext.loc[m.mo_id] if m.mo_id in ext.index else None
        nodes.append(dict(id=int(m.mo_id), name=m.name, kind=m.kind, pop2024=r(pop.get(m.mo_id), 0),
                          type=None if m.mo_id not in fin.index else int(fin[m.mo_id]),
                          dtype=None if m.mo_id not in det.index else int(det[m.mo_id]), v4type=None if m.mo_id not in v4.index else int(v4[m.mo_id]),
                          stab={k: r(stab.loc[m.name, k], 3) for k in stab.columns if k != "run_id"} if m.name in stab.index else None,
                          f={k: r(fv.get(k), 4) for k in feats},
                          ext={k: r(e[k], 4) for k in ext.columns if k.startswith(("ext_", "msp_lq_")) and not k.startswith("msp_lq_raw")} if e is not None else {}))
    dyn = pd.concat([pd.read_csv(latest / "LABELS_MO_PERIOD.csv"), pd.read_csv(latest / "LABELS_MO_PERIOD_DETAILED.csv")])
    dq = pd.concat([rd("DYNAMICS_QUALITY"), rd("DYNAMICS_QUALITY_DETAILED")])
    evs = [rd(n) for n in ("DYNAMICS_EVENTS", "DYNAMICS_EVENTS_DETAILED") if (latest / f"{n}.csv").stat().st_size > 50]
    ev = pd.concat(evs) if evs else pd.DataFrame()
    name2id = dict(zip(mo.name, mo.mo_id))
    dynamics = {}
    for (level, mode, beta), g in dyn.groupby(["level", "mode", "beta"]):
        piv = g.pivot(index="mo", columns="period", values="label")
        dynamics[f"{level}|{mode}|{beta}"] = {str(name2id[nm]): [None if pd.isna(v) else int(v) for v in row] for nm, row in piv.iterrows()}
    periods = sorted(dyn.period.unique())
    co = pd.read_parquet(latest / "COASSIGNMENT.parquet")
    co = co[co.scheme == "node_subsample"]
    co_rows = [[name2id[a], name2id[b], r(p, 3)] for a, b, p in zip(co.i, co.j, co.p)]
    edges = pd.read_sql("SELECT matrix, i, j, weight FROM run_matrix_edges WHERE run_id=? AND matrix LIKE ?", con,
                        params=[run_id, man["final"]["config"] + "|%"])
    lay = edges[edges.matrix.str.contains("|layer:", regex=False)].copy()
    lay["layer"] = lay.matrix.str.split("layer:").str[1]
    comp_by_edge = {}
    for r_ in lay.itertuples():
        comp_by_edge.setdefault((int(r_.i), int(r_.j)), {})[r_.layer] = round(float(r_.weight), 3)
    sw = rd("ICVI_SWEEP")
    sw4 = sw[sw.config == man["final"]["config"]]
    icvi_cols = ["method", "k", "min_size", "SW", "CH", "S_Dbw", "S_Dbw_floor1", "S_Dbw_undefined_terms", "AVI", "AVU", "MQ_newman",
                 "MQ_mancoridis", "intra_inter_density_ratio", "z_SW", "z_CH", "z_S_Dbw_floor1", "z_AVI", "z_AVU", "z_MQ_newman",
                 "p_AVU", "p_MQ_newman", "boot_ari_median", "pareto_within_config"]
    src = pd.read_sql("SELECT source_id, title, observation_period, status, role, sha256, size_bytes, limitations FROM source_registry ORDER BY role, source_id", con)
    chk = pd.read_sql("SELECT check_name, status FROM data_quality_checks", con)
    cov = []
    for b, cols in F.BLOCKS.items():
        sub = st[st.feature.isin(cols)].groupby("mo_id").value.apply(lambda v: int(v.notna().all()))
        cov.append(dict(block=b, observed=[int(sub.get(m, 0)) for m in mo.mo_id]))
    D5 = dict(
        version="5.0.0", run_id=run_id, config_hash=man["config_hash"], code_hash=man["code_hash"], data_hash=man["data_hash"],
        scope="Региональный кейс: 63 МО Республики Башкортостан; основная типология — 62 МО с наблюдаемым блоком СберИндекса. Национальный результат не заявляется.",
        final=man["final"], macro=man["macro"], detailed=man["detailed"],
        type_names={str(k): v for k, v in man["type_names"].items()},
        type_names_detailed={str(k): v for k, v in man["type_names_detailed"].items()},
        leakage=man["leakage_test"], mezhgorye=man["mezhgorye"], timings=man["timings"], N=man["N"],
        nodes=nodes, feature_meta={k: dict(unit=fmeta.loc[k, "unit"] if k in fmeta.index else "", block=fmeta.loc[k, "block"] if k in fmeta.index else "",
                                          source=fmeta.loc[k, "source"] if k in fmeta.index else "", window=fmeta.loc[k, "window"] if k in fmeta.index else "",
                                          hindsight=int(fmeta.loc[k, "hindsight"]) if k in fmeta.index else 0) for k in feats},
        passports=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in pas.to_dict("records")],
        passports_detailed=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in rd("TYPE_PASSPORTS_DETAILED").to_dict("records")],
        periods=periods, dynamics=dynamics,
        dyn_quality=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in dq.to_dict("records")],
        dyn_events=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in ev.to_dict("records")] if len(ev) else [],
        beta_sens=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in pd.concat([rd("DYNAMICS_BETA_SENSITIVITY"), rd("DYNAMICS_BETA_SENSITIVITY_DETAILED")]).to_dict("records")],
        coassign=co_rows,
        edges_exact=[[int(i), int(j), r(w, 4)] for mtx, i, j, w in edges.itertuples(index=False) if mtx.endswith("|exact")],
        edges_display=[[int(i), int(j), r(w, 4), comp_by_edge.get((int(i), int(j)), comp_by_edge.get((int(j), int(i)), {}))]
                       for mtx, i, j, w in edges.itertuples(index=False) if mtx.endswith("|display_k4")],
        icvi=[{k: r(row.get(k), 4) for k in icvi_cols} for row in sw4.to_dict("records")],
        k_selection=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in rd("K_SELECTION").to_dict("records")],
        comparison=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in comp.to_dict("records")],
        ablation=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in rd("ABLATION_SENSITIVITY").to_dict("records")],
        uncertainty=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in rd("UNCERTAINTY_SUMMARY").to_dict("records")],
        validation=[{k: r(v, 4) for k, v in row.items() if k in ("indicator", "labeling", "H", "eps2", "p_perm", "p_spatial", "q_bh_perm", "q_by_perm", "n", "moran_I")}
                    for row in rd("EXTERNAL_VALIDATION").to_dict("records")],
        sources=[{k: r(v, 4) for k, v in row.items()} for row in src.to_dict("records")],
        checks=chk.to_dict("records"), coverage=cov, mo_ids=[int(x) for x in mo.mo_id],
        holdout=[{k: r(v, 4) for k, v in row.items() if k != "run_id"} for row in rd("HOLDOUT_VALIDATION").to_dict("records")],
    )
    # ссылка на полную базу: берём из DB_MANIFEST.json того же прогона, в UI ничего не пересчитываем
    if manifest is not None and manifest.exists():
        m = json.loads(manifest.read_text("utf-8"))
        if m.get("run_id") != D5["run_id"]:
            raise SystemExit(f"DB_MANIFEST.json от другого прогона: {m.get('run_id')} ≠ {D5['run_id']}")
        D5["download"] = {k: m.get(k) for k in ("file", "bytes", "sha256", "sqlite_bytes", "sqlite_sha256", "url", "local_path",
                                                 "dictionary_url", "schema_version", "tables", "rows_total", "created_at")}
    return D5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default=str(ROOT / "outputs" / "latest"))
    ap.add_argument("--db", default=str(ROOT / "data" / "econtypes_v5.sqlite"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", default=str(ROOT / "data" / "DB_MANIFEST.json"))
    a = ap.parse_args()
    D5 = build(Path(a.latest), Path(a.db), Path(a.manifest))
    txt = json.dumps(D5, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    p = Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, "utf-8")
    print(dict(out=str(p), bytes=len(txt.encode()), sha1=hashlib.sha1(txt.encode()).hexdigest(), run_id=D5["run_id"]))


if __name__ == "__main__":
    main()
