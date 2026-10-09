"""Индексы муниципальной экономики: из признаков, сети и результатов кластеризации.

Все индексы считаются из таблиц базы (res_features, res_clusters, res_edges), поэтому пересчитываются
автоматически после каждого `econtypes run` на новых данных:  econtypes metrics

Каждый индекс приведён к шкале 0–100 (процентиль среди МО региона), исходное значение тоже сохраняется.
Описание формул — в METRICS и docs/METHODOLOGY.md.
"""
from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import silhouette_samples

from . import db, prepare as P

# имя → (подпись, формула для документации, «чем больше, тем…»)
METRICS = {
    "localization":   ("Локализация госзаказа", "доля стоимости контрактов муниципальных заказчиков у поставщиков из того же МО", "выше — больше денег остаётся в местной экономике"),
    "external_dep":   ("Внешняя зависимость снабжения", "доля контрактов у поставщиков из Уфы и из-за пределов РБ", "выше — сильнее зависимость от внешних поставщиков"),
    "competition":    ("Конкурентность закупок", "1 − доля стоимости контрактов с единственным поставщиком", "выше — больше конкуренции"),
    "budget_dep":     ("Бюджетная зависимость", "средний процентиль: дотации на выравнивание на жителя, доля занятых в бюджетном секторе", "выше — экономика сильнее держится на бюджете"),
    "online_leakage": ("Утечка спроса в онлайн", "маркетплейсы / (маркетплейсы + общепит) в тратах по картам", "выше — локальная сфера услуг слабее"),
    "activity":       ("Экономическая активность", "средний процентиль: траты на жителя, зарплата, занятые на 1000 жителей", "выше — активнее экономика"),
    "demo_resilience": ("Демографическая устойчивость", "средний процентиль: рождаемость, −смертность, миграционный прирост", "выше — устойчивее население"),
    "hub":            ("Индекс хаба снабжения", "PageRank в направленной сети денежных потоков заказчик → поставщик", "выше — больше соседей покупают у этого МО"),
    "supply_reach":   ("Охват поставок", "доля МО региона, которым поставщики МО продали ≥ порога", "выше — шире рынок сбыта"),
    "bridge":         ("Мостовой индекс", "посредническая центральность (betweenness) в совмещённой сети", "выше — МО связывает разные части региона"),
    "sync":           ("Синхронность с регионом", "взвешенная степень в слое сопряжённости трат", "выше — экономика МО движется вместе с соседями"),
    "leadership":     ("Опережение", "число МО, траты которых МО опережает на 1–3 мес. (лаговая корреляция)", "выше — МО раньше реагирует на шоки"),
    "typicality":     ("Типичность", "силуэт МО в своём кластере (−1…1)", "низкая — переходный/смешанный профиль"),
}


def pct(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def _graph(edges: pd.DataFrame, layer: str, nodes: list[str], directed=False, w="weight"):
    G = nx.DiGraph() if directed else nx.Graph()
    G.add_nodes_from(nodes)
    e = edges[edges.layer == layer]
    G.add_weighted_edges_from(e[["source", "target", w]].itertuples(index=False, name=None))
    return G


def compute(cfg: dict, eng) -> pd.DataFrame:
    tab = db.read(eng, "res_features").set_index("mo")
    cl = db.read(eng, "res_clusters").set_index("mo")
    edges = db.read(eng, "res_edges")
    nodes = list(cl.index)
    tab = tab.reindex(nodes)
    m = pd.DataFrame(index=pd.Index(nodes, name="mo"))
    g = lambda c: tab[c] if c in tab else pd.Series(np.nan, index=tab.index)

    m["localization"] = g("proc_local_sh")
    m["external_dep"] = g("proc_ufa_sh") + g("proc_out_sh")
    m["competition"] = 1 - g("proc_single_sh")
    m["budget_dep"] = pd.concat([pct(g("grants_pc")), pct(g("emp_sh_budget"))], axis=1).mean(axis=1)
    mp, cat = g("sh_Маркетплейсы"), g("sh_Общественное питание")
    m["online_leakage"] = mp / (mp + cat)
    m["activity"] = pd.concat([pct(g("spend_total")), pct(g("wage")), pct(g("emp_per_1000"))], axis=1).mean(axis=1)
    m["demo_resilience"] = pd.concat([pct(g("birth_rate")), pct(-g("death_rate")), pct(g("migr_rate"))], axis=1).mean(axis=1)

    # сеть денежных потоков: ребро заказчик → поставщик (деньги идут к поставщику)
    fl = edges[edges.layer == "flow_rub"]
    Gm = nx.DiGraph(); Gm.add_nodes_from(nodes)
    Gm.add_weighted_edges_from(fl[["target", "source", "rub"]].itertuples(index=False, name=None))
    m["hub"] = pd.Series(nx.pagerank(Gm, weight="weight"))
    thr = cfg["network"]["flow_min_rub"]
    m["supply_reach"] = fl[fl.rub >= thr].groupby("source").target.nunique().reindex(nodes).fillna(0) / (len(nodes) - 1)

    Gf = _graph(edges, "fused", nodes)
    for u, v, d in Gf.edges(data=True):
        d["dist"] = 1.0 / max(d["weight"], 1e-9)
    m["bridge"] = pd.Series(nx.betweenness_centrality(Gf, weight="dist"))
    m["sync"] = pd.Series(dict(_graph(edges, "comovement", nodes).degree(weight="weight")))
    ll = edges[edges.layer == "lead_lag"]
    m["leadership"] = ll[ll.lag > 0].groupby("source").size().reindex(nodes).fillna(0)

    _, _, X = P.design_matrix(tab, cfg)
    m["typicality"] = silhouette_samples(X, cl.cluster.values)

    # процентили 0–100
    for c in list(METRICS):
        m[c + "_pct"] = pct(m[c]).round(1)

    # аномалии: отклонение от медианы своего типа в единицах межквартильного размаха по региону
    # (X уже робастно нормирован на регион, 1 ед. ≈ 1.35σ); порог config.report.anomaly_iqr
    thr_a = cfg.get("report", {}).get("anomaly_iqr", 2.0)
    Xd = pd.DataFrame(X, index=nodes, columns=tab.columns)
    an = []
    for mo in nodes:
        med = Xd[cl.cluster == cl.loc[mo, "cluster"]].median()
        z = (Xd.loc[mo] - med)
        z = z[z.abs() > thr_a].sort_values(key=abs, ascending=False).head(5)
        an.append("; ".join(f"{k}:{v:+.1f}" for k, v in z.items()))
    m["anomalies"] = an
    m = m.join(cl[["cluster", "cluster_name", "macro_name", "bootstrap_stability"]])
    out = Path(cfg["paths"]["outputs"]) / "tables"
    out.mkdir(parents=True, exist_ok=True)
    m.round(4).to_csv(out / "metrics.csv")
    db.write(eng, "res_metrics", m.reset_index())
    db.write(eng, "res_metric_defs", pd.DataFrame([(k, *v) for k, v in METRICS.items()],
                                                  columns=["metric", "label", "formula", "interpretation"]))
    return m
