"""Объяснение типов моделью с учителем и поиск аналогов:  econtypes explain

Кластеризация (обучение без учителя) даёт метки типов. Чтобы проверить, что типы
воспроизводимы и понять, *какие признаки их определяют*, поверх меток обучается
случайный лес (обучение с учителем):

* точность по скользящему контролю (leave-one-out) — насколько тип восстанавливается
  по признакам МО, которых модель не видела;
* перестановочная важность признаков — вклад каждого признака в различение типов;
* «подпись» типа — стандартизованная разница медианы типа и остальных МО;
* аналоги МО — ближайшие соседи в совмещённой сети (атрибуты + связи), а для каждого МО
  «ориентир» — аналог с более высокой экономической активностью.

Новые МО (или те же МО на новых данных) классифицируются обученной моделью: `predict()`.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import LeaveOneOut, cross_val_predict

from . import db, prepare as P


def run(cfg: dict, eng) -> dict:
    out = Path(cfg["paths"]["outputs"])
    tab = db.read(eng, "res_features").set_index("mo")
    cl = db.read(eng, "res_clusters").set_index("mo")
    nodes = list(cl.index)
    tab = tab.reindex(nodes)
    _, _, X = P.design_matrix(tab, cfg)
    y = cl.cluster.values
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, random_state=cfg["clustering"]["random_state"],
                                class_weight="balanced")
    pred = cross_val_predict(rf, X, y, cv=LeaveOneOut())
    acc = float((pred == y).mean())
    chance = float(max(np.bincount(y)) / len(y))
    rf.fit(X, y)
    pi = permutation_importance(rf, X, y, n_repeats=30, random_state=0)
    # главная мера — снижение неоднородности (MDI); перестановочная — дополнительно (при коррелированных
    # признаках она занижена: лес подменяет переставленный признак его «двойником»)
    imp = pd.DataFrame({"feature": tab.columns, "importance": rf.feature_importances_,
                        "perm_importance": pi.importances_mean, "perm_std": pi.importances_std})\
        .sort_values("importance", ascending=False)
    proba = pd.DataFrame(rf.predict_proba(X), index=nodes, columns=[f"p_{c}" for c in rf.classes_])

    Xd = pd.DataFrame(X, index=nodes, columns=tab.columns)
    sig = []
    for c in np.unique(y):
        diff = Xd[y == c].median() - Xd[y != c].median()
        for f, v in diff.items():
            sig.append(dict(cluster=int(c), cluster_name=cl.cluster_name[y == c].iloc[0], feature=f, effect=float(v)))
    sig = pd.DataFrame(sig)

    # аналоги по совмещённой сети
    e = db.read(eng, "res_edges")
    fz = e[e.layer == "fused"]
    W = pd.DataFrame(0.0, index=nodes, columns=nodes)
    for r in fz.itertuples():
        W.loc[r.source, r.target] = W.loc[r.target, r.source] = r.weight
    met = db.read(eng, "res_metrics").set_index("mo") if "res_metrics" in db.tables(eng) else None
    an = []
    for mo in nodes:
        nb = W.loc[mo].drop(mo).sort_values(ascending=False)
        nb = nb[nb > 0].head(5)
        bench = None
        if met is not None:
            better = [m for m in nb.index if met.loc[m, "activity"] > met.loc[mo, "activity"] + 5]
            bench = better[0] if better else None
        an.append(dict(mo=mo, analogs="; ".join(nb.index[:3]), benchmark=bench,
                       mixed_type=bool(proba.loc[mo].max() < 0.5),
                       second_type=int(proba.loc[mo].drop(f"p_{cl.loc[mo, 'cluster']}").idxmax()[2:])))
    an = pd.DataFrame(an)

    (out / "tables").mkdir(parents=True, exist_ok=True)
    imp.to_csv(out / "tables/ml_feature_importance.csv", index=False)
    sig.to_csv(out / "tables/ml_type_signature.csv", index=False)
    an.to_csv(out / "tables/analogs.csv", index=False)
    proba.round(3).to_csv(out / "tables/ml_type_probability.csv")
    db.write(eng, "res_ml_importance", imp)
    db.write(eng, "res_type_signature", sig)
    db.write(eng, "res_analogs", an)
    db.write(eng, "res_type_probability", proba.round(4).rename_axis("mo").reset_index())
    Path(cfg["paths"]["interim"]).mkdir(parents=True, exist_ok=True)
    pickle.dump(dict(model=rf, columns=list(tab.columns), tab=tab), open(Path(cfg["paths"]["interim"]) / "type_classifier.pkl", "wb"))
    res = dict(loo_accuracy=acc, majority_baseline=chance, top_features=imp.head(10).round(4).to_dict(orient="records"))
    db.write(eng, "res_ml_summary", pd.DataFrame([dict(loo_accuracy=acc, majority_baseline=chance)]))
    return res


def predict(cfg: dict, new_features: pd.DataFrame) -> pd.DataFrame:
    """Отнести МО к типам по новой таблице признаков (те же столбцы, что res_features)."""
    m = pickle.load(open(Path(cfg["paths"]["interim"]) / "type_classifier.pkl", "rb"))
    tab = pd.concat([m["tab"], new_features[m["columns"]].add_suffix("")]).loc[:, m["columns"]]
    _, _, X = P.design_matrix(tab, cfg)
    Xn = X[-len(new_features):]
    return pd.DataFrame(m["model"].predict_proba(Xn), index=new_features.index,
                        columns=[f"p_{c}" for c in m["model"].classes_]).assign(type=m["model"].predict(Xn))
