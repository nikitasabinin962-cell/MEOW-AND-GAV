"""Сборка интерактивного лендинга из результатов пайплайна.

    python build_landing.py
→ outputs/landing/index.html   (самодостаточная страница, открывается в браузере / GitHub Pages)
→ outputs/landing/artifact.html (то же содержимое без <html>/<head>/<body> — для публикации как Artifact)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

def build(cfg: dict) -> None:
    out = Path(cfg["paths"]["outputs"])
    R = json.load(open(out / "results.json"))
    V = json.load(open(out / "validation_holdout.json"))
    T = out / "tables"

    nodes = pd.DataFrame(R["nodes"]).set_index("mo")
    # раздвигаем совпадающие центры только для отображения (как в make_figures.py)
    xy = nodes[["x", "y"]].values + np.random.default_rng(0).normal(0, 1e-3, (len(nodes), 2))
    for _ in range(200):
        d = xy[:, None, :] - xy[None, :, :]
        r = np.sqrt((d ** 2).sum(-1)) + np.eye(len(xy)) + 1e-9
        xy += 0.25 * (np.clip(0.16 - r, 0, None)[..., None] * d / r[..., None]).sum(1)

    FEATS = {"spend_total": ("Безналичные траты на жителя", "₽/мес"), "sh_Продовольствие": ("Доля трат на продукты", "%"),
             "sh_Общественное питание": ("Доля трат на общепит", "%"), "sh_Маркетплейсы": ("Доля трат на маркетплейсах", "%"),
             "sh_Транспорт": ("Доля трат на транспорт", "%"), "sh_Здоровье": ("Доля трат на здоровье", "%"),
             "proc_pc": ("Госзаказ на жителя за квартал", "₽"), "proc_local_sh": ("Госзаказ у местных поставщиков", "%"),
             "proc_ufa_sh": ("Госзаказ у поставщиков из Уфы", "%"), "proc_out_sh": ("Госзаказ у поставщиков из других регионов", "%"),
             "proc_single_sh": ("Закупки у единственного поставщика", "%"), "okpd_construction_sh": ("Госзаказ: строительство", "%"),
             "okpd_fuel_transport_sh": ("Госзаказ: топливо и транспорт", "%"), "okpd_health_sh": ("Госзаказ: медицина", "%"),
             "urban_share": ("Доля горожан", "%"), "market_access": ("Индекс доступности рынков", ""),
             "birth_rate": ("Рождаемость", "‰"), "death_rate": ("Смертность", "‰"), "migr_rate": ("Миграционный прирост", "‰"),
             "grants_pc": ("Дотации на выравнивание на жителя", "₽/год"),
             "wage": ("Средняя зарплата (крупные и средние орг.)", "₽/мес"), "emp_per_1000": ("Работники организаций на 1000 жителей", "чел."),
             "emp_sh_industry": ("Занятые в промышленности и стройке", "%"), "emp_sh_budget": ("Занятые в бюджетном секторе", "%"),
             "emp_sh_agri": ("Занятые в сельском хозяйстве", "%"), "log_density": ("Плотность населения (лог)", "")}
    f = pd.read_csv(T / "features_raw_2023_2024.csv", index_col=0)
    mean, std = f[list(FEATS)].mean(), f[list(FEATS)].std()
    prof = []
    for c in sorted(int(k) for k in R["names"]):
        members = nodes.index[nodes.cluster == c]
        z = ((f.loc[members, list(FEATS)].mean() - mean) / std)
        top = z.abs().sort_values(ascending=False).index[:5]
        prof.append(dict(c=c, name=R["names"][str(c)], n=len(members), members=list(members),
                         z={k: round(float(z[k]), 2) for k in FEATS},
                         top=[dict(f=k, z=round(float(z[k]), 2), v=round(float(f.loc[members, k].mean()), 4)) for k in top]))

    data = dict(
        k=R["k"], names=R["names"], quarters=R["quarters"], months=R["months"],
        macro_names=R["macro_names"], macro_boot=R["macro_bootstrap_ari"],
        nodes=[dict(mo=m, s=m.replace("МР ", "").replace("ГО ", "г. "), kind="ГО" if m.startswith("ГО") else "МР",
                    macro=int(R["macro"][i]),
                    c=int(r.cluster), x=round(float(xy[i, 0]), 4), y=round(float(xy[i, 1]), 4), pop=int(r["pop"]),
                    stab=round(float(r.stab), 2), sw=int(r.switches), q=r.quarters,
                    f={k: (None if r.feats.get(k) is None else r.feats[k]) for k in FEATS},
                    sp=[None if v is None else round(v) for v in r.spend])
               for i, (m, r) in enumerate(nodes.iterrows())],
        mean={k: round(float(mean[k]), 4) for k in FEATS}, feats={k: list(v) for k, v in FEATS.items()},
        edges=R["edges"], flows=R["flows"][:80], prof=prof,
        icvi=[{k: v for k, v in r.items() if k.startswith("z_") or k in ("method", "SW", "CH", "DB", "S_Dbw", "MQ", "AVI", "AVU", "minsize")} for r in R["icvi_at_k"]],
        icvi_k=[dict(method=r["method"], k=r["k"], z=r["z_mean"]) for r in R["icvi_by_k"]],
        edges_cmp=R["edges_cmp"], trans=R["transitions"], qari=R["quarter_ari"], beta=R["beta_sensitivity"],
        spatial=R["spatial"], boot=R["bootstrap_ari"], val=V,
    )
    # текст о динамике — из данных, без привязки к номерам меток
    tr = pd.read_csv(T / "quarter_transitions.csv", index_col=0)
    tr.index = tr.index.astype(int); tr.columns = tr.columns.astype(int)
    stay = (np.diag(tr.values) / tr.values.sum(1))
    st_order = [int(tr.index[i]) for i in np.argsort(-stay)]
    sym = tr.values + tr.values.T
    np.fill_diagonal(sym, 0)
    i, j = np.unravel_index(np.argmax(sym), sym.shape)
    a, b = int(tr.index[i]), int(tr.index[j])
    q = pd.read_csv(T / "clusters_by_quarter.csv", index_col=0)
    q23, q24 = [c for c in q.columns if c.startswith("2023")], [c for c in q.columns if c.startswith("2024")]
    movers = [m for m in q.index if (q.loc[m, q23].isin([a, b]).all() and q.loc[m, q24].isin([a, b]).all()
              and q.loc[m, q23].mode()[0] != q.loc[m, q24].mode()[0])]
    dyn = dict(stay_share=float(np.trace(tr.values) / tr.values.sum()), most_stable=st_order[:2], pair=[a, b],
               pair_n=int(sym[i, j]), movers=[dict(mo=m, s=m.replace("МР ", "").replace("ГО ", "г. "),
               frm=int(q.loc[m, q23].mode()[0]), to=int(q.loc[m, q24].mode()[0])) for m in movers])
    data["dyn"] = dyn
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    tpl = (Path(__file__).parent / "templates/landing.html").read_text()
    body = tpl.replace("/*__DATA__*/null", payload)
    (out / "landing").mkdir(parents=True, exist_ok=True)
    (out / "landing/artifact.html").write_text(body)
    (out / "landing/index.html").write_text(
        '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "</head><body>" + body + "</body></html>")
    print("лендинг:", out / "landing/index.html", f"{len(body) / 1024:.0f} КБ")
