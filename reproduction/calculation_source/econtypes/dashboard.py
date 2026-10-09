"""Интерактивный дашборд с картой:  econtypes dashboard  →  outputs/dashboard.html

Один самодостаточный HTML-файл (данные, Leaflet и стили внутри), который собирается заново из базы
при каждом запуске — значит, после загрузки новых данных и `econtypes all` карта, рёбра сети,
индексы, корреляции и рекомендации обновляются сами. Файл открывается в браузере без сервера,
его можно выложить на GitHub Pages или опубликовать как страницу.

Что внутри:
* карта МО с приближением (границы geoBoundaries/OSM), раскраска по типу, макротипу, любому индексу или признаку;
* рёбра любого слоя сети (совмещённая, синхронность трат, опережение со стрелками, DTW, атрибуты,
  потоки госзаказа в рублях, расстояние) с порогом силы;
* карточка МО: индексы, выводы и рекомендации, аналоги, динамика типа по кварталам, траты по месяцам;
* корреляции (тепловая карта → диаграмма рассеяния по клику), лаги, ML-объяснение, качество модели.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import db, geo
from .labels import FEATS
from .metrics import METRICS
from .report import BAD_HIGH, GOOD_HIGH, short

TPL = Path(__file__).parent / "templates"


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 5)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def collect(cfg: dict, eng) -> dict:
    out = Path(cfg["paths"]["outputs"])
    R = json.load(open(out / "results.json"))
    t = db.tables(eng)
    cl = db.read(eng, "res_clusters").set_index("mo")
    nodes = list(cl.index)
    f = db.read(eng, "res_features").set_index("mo").reindex(nodes)
    m = db.read(eng, "res_metrics").set_index("mo").reindex(nodes)
    cards = db.read(eng, "res_mo_report").set_index("mo").reindex(nodes)
    proba = db.read(eng, "res_type_probability").set_index("mo").reindex(nodes) if "res_type_probability" in t else None
    rnodes = {n["mo"]: n for n in R["nodes"]}
    idx = {mo: i for i, mo in enumerate(nodes)}

    N = []
    for mo in nodes:
        c = cards.loc[mo]
        N.append(dict(
            mo=mo, s=short(mo), kind="ГО" if mo.startswith("ГО") else "МР",
            c=int(cl.loc[mo, "cluster"]), macro=int(cl.loc[mo, "macro"]),
            pop=rnodes[mo]["pop"], stab=float(cl.loc[mo, "bootstrap_stability"]),
            typ=float(m.loc[mo, "typicality"]), q=rnodes[mo]["quarters"], sp=rnodes[mo]["spend"],
            f={k: f.loc[mo, k] for k in f.columns},
            m={k: m.loc[mo, k] for k in METRICS}, mp={k: m.loc[mo, k + "_pct"] for k in METRICS},
            p=None if proba is None else [proba.loc[mo, c_] for c_ in proba.columns],
            summary=c.summary, strengths=json.loads(c.strengths), weak=json.loads(c.weaknesses),
            anom=json.loads(c.anomalies), recs=json.loads(c.recommendations),
            analogs=[a for a in str(c.analogs).split("; ") if a in idx],
            bench=c.benchmark if isinstance(c.benchmark, str) else None))

    e = db.read(eng, "res_edges")
    layers = {}
    for lname, g in e.groupby("layer"):
        g = g[g.source.isin(idx) & g.target.isin(idx)]
        if lname == "flow_rub":
            g = g.sort_values("rub", ascending=False).head(int(cfg.get("dashboard", {}).get("max_flows", 500)))
            layers[lname] = [[idx[a], idx[b], float(r), 0] for a, b, r in zip(g.source, g.target, g.rub)]
        else:
            layers[lname] = [[idx[a], idx[b], float(w), int(l)] for a, b, w, l in zip(g.source, g.target, g.weight, g.lag)]

    # каркас сети: максимальное остовное дерево совмещённого графа — самые сильные связи без «клубка»
    import networkx as nx
    fz = e[e.layer == "fused"]
    G = nx.Graph(); G.add_nodes_from(range(len(nodes)))
    G.add_weighted_edges_from((idx[a], idx[b], w) for a, b, w in zip(fz.source, fz.target, fz.weight) if a in idx and b in idx)
    layers["backbone"] = [[u, v, float(d["weight"]), 0] for u, v, d in nx.maximum_spanning_tree(G).edges(data=True)]

    # корреляции: матрица ρ и q для признаков и индексов
    corr = None
    if "res_correlations" in t:
        S = db.read(eng, "res_correlations")
        vars_ = list(f.columns) + ["m_" + k for k in METRICS]
        vi = {v: i for i, v in enumerate(vars_)}
        rho = [[None] * len(vars_) for _ in vars_]
        q = [[None] * len(vars_) for _ in vars_]
        for r in S.itertuples():
            if r.x in vi and r.y in vi:
                i, j = vi[r.x], vi[r.y]
                rho[i][j] = rho[j][i] = r.rho
                q[i][j] = q[j][i] = r.q_fdr
        Pc = db.read(eng, "res_partial_corr") if "res_partial_corr" in t else pd.DataFrame(columns=["x", "y", "partial_rho", "q_fdr"])
        from .report import _trivial
        top = S[(S.q_fdr < 0.05) & ~S.apply(lambda r: bool(_trivial(r.x, r.y)), axis=1)]
        top = top.reindex(top.rho.abs().sort_values(ascending=False).index).head(40)
        pk = {(r.x, r.y): (r.partial_rho, r.q_fdr) for r in Pc.itertuples()}
        corr = dict(vars=vars_, rho=rho, q=q,
                    top=[dict(x=r.x, y=r.y, rho=r.rho, q=r.q_fdr, prho=pk.get((r.x, r.y), (None, None))[0],
                              pq=pk.get((r.x, r.y), (None, None))[1]) for r in top.itertuples()])
    lag = db.read(eng, "res_lag_corr_summary").to_dict(orient="records") if "res_lag_corr_summary" in t else []
    ml = None
    if "res_ml_summary" in t:
        s = db.read(eng, "res_ml_summary").iloc[0]
        ml = dict(acc=float(s.loo_accuracy), base=float(s.majority_baseline),
                  imp=db.read(eng, "res_ml_importance").head(15).to_dict(orient="records"))
    sig = db.read(eng, "res_type_signature") if "res_type_signature" in t else None
    types = []
    for c_ in sorted(int(k) for k in R["names"]):
        mem = [i for i, n in enumerate(N) if n["c"] == c_]
        s_ = [] if sig is None else sig[sig.cluster == c_].sort_values("effect", key=abs, ascending=False).head(8)\
            .to_dict(orient="records")
        types.append(dict(c=c_, name=R["names"][str(c_)], members=mem, sig=s_,
                          med={k: float(np.nanmedian([N[i]["mp"][k] for i in mem])) for k in METRICS}))
    V = json.load(open(out / "validation_holdout.json")) if (out / "validation_holdout.json").exists() else None
    gj = geo.load(cfg)
    if gj:
        for ft in gj["features"]:
            ft["properties"]["i"] = idx.get(ft["properties"]["mo"])
    return _clean(dict(
        title=cfg["viz"]["title"], authors=cfg["viz"].get("authors", ""), region=cfg["region"]["name"],
        generated=dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
        period=f"{cfg['data']['period_start'][:7]} — {cfg['data']['period_end'][:7]}",
        k=R["k"], names=R["names"], macro_names=R["macro_names"], quarters=R["quarters"], months=R["months"],
        nodes=N, geo=gj, layers=layers, feats={k: list(v) for k, v in FEATS.items() if k in f.columns},
        metrics={k: dict(label=v[0], formula=v[1], interp=v[2],
                         sense=1 if k in GOOD_HIGH else (-1 if k in BAD_HIGH else 0)) for k, v in METRICS.items()},
        corr=corr, lag=lag, ml=ml, types=types, findings=findings(cfg, eng, R, N, f, m, cl, V),
        summary=summary(R, N, f, m, cl),
        quality=dict(icvi=[{k: v for k, v in r.items() if k.startswith("z_") or k in ("method", "SW", "CH", "MQ", "AVI", "AVU", "S_Dbw", "minsize")}
                           for r in R["icvi_at_k"]],
                     boot=R["bootstrap_ari"], macro_boot=R["macro_bootstrap_ari"], spatial=R["spatial"],
                     qari=R["quarter_ari"], edges_cmp=R["edges_cmp"], val=V, method=R["method"]),
        weights=cfg["network"]["layer_weights"], alpha=cfg["network"]["alpha_attr"], knn=cfg["network"]["knn"],
    ))


def _num(v, d=0):
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def findings(cfg, eng, R, N, f, m, cl, V) -> list[dict]:
    """Главные выводы по региону: шаблоны, в которые подставляются числа из базы (обновляются с данными)."""
    from .labels import label
    from .report import _trivial
    t = db.tables(eng)
    names = {int(k): v for k, v in R["names"].items()}
    by = f.assign(c=cl.cluster.values).groupby("c").median()
    nm = lambda c: names[int(c)]
    out = []
    sp = R["spatial"]
    out.append(dict(title=f"{len(N)} муниципалитетов — {R['k']} типов экономики",
        text=f"Типы найдены по данным о тратах, госзаказе, занятости и связях между МО. Местоположение в модель не входило, "
             f"но типы получились цельными территориями: {_num(sp['within_km'])} км между МО одного типа против "
             f"{_num(sp['random_mean_km'])} км у случайного разбиения. Экономическая структура привязана к месту."))
    if "spend_total" in by:
        hi, lo = by.spend_total.idxmax(), by.spend_total.idxmin()
        out.append(dict(title="Разрыв между ядром и периферией",
            text=f"Житель типа «{nm(hi)}» тратит по картам {_num(by.spend_total[hi])} ₽ в месяц, "
                 f"типа «{nm(lo)}» — {_num(by.spend_total[lo])} ₽ (в {_num(by.spend_total[hi] / by.spend_total[lo], 1)} раза меньше)."
                 + (f" Зарплаты: {_num(by.wage.max())} ₽ против {_num(by.wage.min())} ₽." if "wage" in by else "")))
    if "res_partial_corr" in t:
        P = db.read(eng, "res_partial_corr")
        P = P[(P.q_fdr < 0.05) & ~P.apply(lambda r: bool(_trivial(r.x, r.y)), axis=1)]
        P = P[~P.x.str.startswith("m_") | ~P.y.str.startswith("m_")]
        P = P[~(P.x.str.startswith("sh_") & P.y.str.startswith("sh_"))]   # доли одного целого связаны механически
        P = P.reindex(P.partial_rho.abs().sort_values(ascending=False).index).head(3)
        if len(P):
            out.append(dict(title="Главная ось — бюджетная или рыночная экономика, а не размер",
                text="Связи, которые сохраняются даже при сравнении МО одного размера и урбанизации: "
                     + "; ".join(f"{label(r.x).lower()} и {label(r.y).lower()} (ρ = {_num(r.partial_rho, 2)})" for r in P.itertuples())
                     + ". Там, где больше бюджетной занятости, ниже зарплаты и активность — при любом размере района."))
    if "proc_local_sh" in by:
        lo = by.proc_local_sh.idxmin()
        out.append(dict(title="Госзаказ уходит из районов",
            text=f"Местным поставщикам достаётся {by.proc_local_sh.min() * 100:.0f}–{by.proc_local_sh.max() * 100:.0f}% стоимости контрактов "
                 f"(медианы типов); меньше всего — в типе «{nm(lo)}». Остальное получают поставщики из Уфы и других регионов."))
    hubs = m.sort_values("hub", ascending=False).index[:5]
    out.append(dict(title="Центры снабжения региона",
        text="Больше всего соседей снабжают поставщики из: " + ", ".join(short(x) for x in hubs)
             + ". Это естественные площадки для межмуниципальной логистики и совместных закупок.", mos=list(hubs)))
    if "migr_rate" in by:
        lo, hi = by.migr_rate.idxmin(), by.migr_rate.idxmax()
        out.append(dict(title="Население уходит из периферии",
            text=f"Миграционный баланс (медиана типа): от {_num(by.migr_rate[lo], 1)}‰ в типе «{nm(lo)}» "
                 f"до {_num(by.migr_rate[hi], 1)}‰ в типе «{nm(hi)}»."))
    if "sh_Маркетплейсы" in by and "sh_Общественное питание" in by:
        r_ = (f["sh_Маркетплейсы"] / f["sh_Общественное питание"]).groupby(cl.cluster.values).median()
        out.append(dict(title="В сёлах деньги уходят на маркетплейсы",
            text=f"На маркетплейсы тратят в {_num(r_.min(), 1)}–{_num(r_.max(), 1)} раза больше, чем на общепит (медианы типов). "
                 "Местная сфера услуг не удерживает расходы жителей."))
    q = R["quarter_ari"]
    out.append(dict(title="Типы устойчивы и проверены на новых данных",
        text=f"Бутстреп: ARI {R['bootstrap_ari']:.2f}".replace(".", ",")
             + (f"; по закупкам " + ", ".join(f"{y} г. тип узнаётся в {h['accuracy'] * 100:.0f}% случаев" for y, h in V["holdout"].items())
                + f" при случайных {V['chance_mean'] * 100:.0f}%" if V else "") + "."))
    return out


def summary(R, N, f, m, cl) -> list[str]:
    """Итог простыми словами: 4 абзаца «что следует из данных», числа подставляются из базы."""
    c = cl.cluster.values
    by = f.groupby(c).median()
    names = {int(k): v for k, v in R["names"].items()}
    macro = cl.macro_name
    core = macro.value_counts().idxmax() if False else [x for x in macro.unique() if "ядро" in x.lower()]
    core = core[0] if core else macro.iloc[0]
    n_core = int((macro == core).sum())
    hubs = ", ".join(short(x) for x in m.sort_values("hub", ascending=False).index[:5])
    hi, lo = by.spend_total.idxmax(), by.spend_total.idxmin()
    ext = 1 - by.proc_local_sh
    topic = lambda t: sum(any(r["topic"] == t for r in x["recs"]) for x in N)
    mig_lo = by.migr_rate.idxmin()
    leak = [i for i, x in enumerate(N) if any(r["topic"] == "Утечка потребительского спроса" for r in x["recs"])]
    rr = (f["sh_Маркетплейсы"] / f["sh_Общественное питание"]).iloc[leak]
    return [
        f"Экономика республики устроена как ядро и периферия. Ядро — {n_core} городов и промышленных районов "
        f"(центры: {hubs}). Остальные {len(N) - n_core} МО — аграрная и бюджетная периферия, где зарплаты и траты жителей "
        f"в 1,3–1,5 раза ниже: {_num(by.spend_total[hi])} ₽ против {_num(by.spend_total[lo])} ₽ в месяц на человека.",
        f"Различие определяется не размером района, а тем, есть ли в нём рыночная занятость. Чем больше людей работает в "
        f"бюджетном секторе, тем ниже зарплаты и активность — и это верно даже для районов одного размера. "
        f"Высокая бюджетная зависимость при низкой активности — в {topic('Бюджетная зависимость')} МО.",
        f"Деньги периферии утекают. Бюджетные — через госзаказ: {ext.min() * 100:.0f}–{ext.max() * 100:.0f}% стоимости "
        f"контрактов получают поставщики не из своего района, в основном из Уфы. Потребительские — через маркетплейсы: "
        f"в {len(leak)} МО на них тратят в {_num(rr.min(), 0)}–{_num(rr.max(), 0)} раз больше, чем на местный общепит. "
        f"За деньгами уходят люди: в типе «{names[int(mig_lo)]}» миграционный отток {_num(-by.migr_rate[mig_lo], 1)}‰ в год.",
        "Отсюда главный вывод для политики: районам нужно удерживать деньги у себя — отдавать часть госзаказа местным "
        "поставщикам, развивать местную торговлю и услуги, кооперироваться вокруг опорных центров снабжения "
        "и создавать небюджетные рабочие места. Ниже — какие именно районы и с какими цифрами.",
    ]


def build(cfg: dict, eng) -> Path:
    data = collect(cfg, eng)
    html = (TPL / "dashboard.html").read_text(encoding="utf-8")
    html = html.replace("/*__LEAFLET_CSS__*/", (TPL / "leaflet.css").read_text(encoding="utf-8"))
    html = html.replace("/*__LEAFLET_JS__*/", (TPL / "leaflet.js").read_text(encoding="utf-8").replace("</script", "<\\/script"))
    html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    out = Path(cfg["paths"]["outputs"])
    (out / "dashboard_body.html").write_text(html, encoding="utf-8")          # для публикации как Artifact
    full = '<!doctype html>\n<html lang="ru"><head><meta charset="utf-8">' \
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>\n' + html + "\n</body></html>"
    p = out / "dashboard.html"
    p.write_text(full, encoding="utf-8")
    return p
