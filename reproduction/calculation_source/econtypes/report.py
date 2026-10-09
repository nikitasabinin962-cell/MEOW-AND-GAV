"""Автоматические выводы и рекомендации:  econtypes report

* outputs/conclusions.md  — выводы по региону: типы, значимые связи, лаги, ML-объяснение, проверка;
* outputs/mo_reports.md   — карточка каждого МО: тип, сильные/слабые стороны, аномалии,
                            рекомендации с числовым обоснованием, аналоги и ориентир;
* таблица res_mo_report   — то же для дашборда и внешних систем.

Рекомендации формируются правилами над процентилями индексов (econtypes metrics) и сравнением
с медианой своего типа; каждое правило указывает, на каких числах оно сработало. Пороги — в
config.yaml (раздел report), так что правила можно настраивать без правки кода.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import db
from .labels import FEATS, fmt, label
from .metrics import METRICS

GOOD_HIGH = ["localization", "competition", "activity", "demo_resilience", "hub", "supply_reach"]
BAD_HIGH = ["external_dep", "budget_dep", "online_leakage"]
DERIVED = {"m_localization": ["proc_local_sh"], "m_external_dep": ["proc_ufa_sh", "proc_out_sh"],
           "m_competition": ["proc_single_sh"], "m_budget_dep": ["grants_pc", "emp_sh_budget"],
           "m_online_leakage": ["sh_Маркетплейсы", "sh_Общественное питание"],
           "m_activity": ["spend_total", "wage", "emp_per_1000"], "m_demo_resilience": ["birth_rate", "death_rate", "migr_rate"],
           "m_hub": ["supply_out_pc", "m_supply_reach"], "m_supply_reach": ["supply_out_pc"]}
OKPD = {k: v[0].replace("Госзаказ: ", "") for k, v in FEATS.items() if k.startswith("okpd_")}
DEFAULT_TH = dict(low=25, high=75, very_high=85)



def _sg(v: float) -> str:
    """Силуэт со знаком; около нуля — три знака, чтобы не печатать «-0.00»."""
    return "≈ 0 (на границе двух типов)" if abs(v) < 0.005 else f"{v:+.2f}"

def short(mo: str) -> str:
    return mo.replace("МР ", "").replace("ГО ", "г. ")


def _trivial(a: str, b: str) -> bool:
    return b in DERIVED.get(a, []) or a in DERIVED.get(b, []) or \
        (a.startswith("m_") and b.startswith("m_") and set(DERIVED.get(a, [])) & set(DERIVED.get(b, [])))


def mo_cards(cfg: dict, eng) -> pd.DataFrame:
    th = {**DEFAULT_TH, **cfg.get("report", {})}
    lo, hi, vhi = th["low"], th["high"], th["very_high"]
    m = db.read(eng, "res_metrics").set_index("mo")
    f = db.read(eng, "res_features").set_index("mo").reindex(m.index)
    an = db.read(eng, "res_analogs").set_index("mo") if "res_analogs" in db.tables(eng) else None
    e = db.read(eng, "res_edges")
    flows = e[e.layer == "flow_rub"]
    lead = e[(e.layer == "lead_lag") & (e.lag > 0)]
    names = m.groupby("cluster").cluster_name.first()
    med_t = f.groupby(m.cluster).median()
    med_r = f.median()
    rows = []
    for mo, r in m.iterrows():
        x, c = f.loc[mo], r.cluster
        P = {k: r[k + "_pct"] for k in METRICS}
        strengths = [f"{METRICS[k][0]} — {P[k]:.0f}-й процентиль" for k in GOOD_HIGH if P[k] >= hi] + \
                    [f"{METRICS[k][0]} низкая — {P[k]:.0f}-й процентиль" for k in BAD_HIGH if P[k] <= lo]
        weak = [f"{METRICS[k][0]} — {P[k]:.0f}-й процентиль" for k in GOOD_HIGH if P[k] <= lo] + \
               [f"{METRICS[k][0]} высокая — {P[k]:.0f}-й процентиль" for k in BAD_HIGH if P[k] >= hi]
        rec = []
        inflow = flows[(flows.target == mo) & (flows.source != mo)].sort_values("rub", ascending=False)
        top_sup = ", ".join(short(s) for s in inflow.source.head(3))
        okpd = x[[k for k in OKPD if k in x]].dropna().sort_values(ascending=False)
        top_okpd = ", ".join(f"{OKPD[k]} ({v * 100:.0f}%)" for k, v in okpd.head(2).items())

        if P["localization"] <= lo + 5 and P["external_dep"] >= hi - 15:
            rec.append(("Локализация госзаказа",
                        f"у местных поставщиков {fmt('proc_local_sh', x.proc_local_sh)} стоимости контрактов "
                        f"(медиана типа {fmt('proc_local_sh', med_t.loc[c, 'proc_local_sh'])}); внешним поставщикам — "
                        f"{fmt('proc_ufa_sh', x.proc_ufa_sh + x.proc_out_sh)}" + (f", крупнейшие поставщики из МО: {top_sup}" if top_sup else ""),
                        f"Поддержать местных поставщиков в группах с наибольшей долей заказа ({top_okpd}): "
                        "малые закупки у СМСП, совместные закупки с соседями, реестр местных производителей."))
        if P["competition"] <= lo:
            rec.append(("Конкуренция в закупках",
                        f"у единственного поставщика {fmt('proc_single_sh', x.proc_single_sh)} (медиана региона "
                        f"{fmt('proc_single_sh', med_r.proc_single_sh)})",
                        "Перевести повторяющиеся закупки у единственного поставщика в конкурентные процедуры; "
                        "проверить дробление закупок; укрупнять лоты совместно с соседними МО."))
        if P["budget_dep"] >= hi and P["activity"] <= 50:
            rec.append(("Бюджетная зависимость",
                        f"дотации {fmt('grants_pc', x.grants_pc)} на жителя"
                        + ("" if pd.isna(x.emp_sh_budget) else f", в бюджетном секторе {fmt('emp_sh_budget', x.emp_sh_budget)} занятых")
                        + f"; активность — {P['activity']:.0f}-й процентиль",
                        "Диверсифицировать занятость: поддержка МСП и переработки местного сырья, "
                        "оценивать новые проекты по доле налогов, остающихся в бюджете МО."))
        if P["online_leakage"] >= hi:
            rec.append(("Утечка потребительского спроса",
                        f"маркетплейсы {fmt('sh_Маркетплейсы', x['sh_Маркетплейсы'])} трат против "
                        f"{fmt('sh_Общественное питание', x['sh_Общественное питание'])} на общепит",
                        "Развивать местную сферу услуг и торговлю (ярмарки, общепит, бытовые услуги у пунктов выдачи заказов); "
                        "местным производителям — выход на маркетплейсы, чтобы деньги возвращались в район."))
        if P["demo_resilience"] <= lo:
            rec.append(("Демография",
                        f"миграция {fmt('migr_rate', x.migr_rate)}, рождаемость {fmt('birth_rate', x.birth_rate)}, "
                        f"смертность {fmt('death_rate', x.death_rate)}",
                        "Удержание молодёжи: жильё и рабочие места для специалистов, программы «Земский учитель/доктор», "
                        "транспортная доступность к центрам занятости."))
        if P["activity"] >= hi and P["demo_resilience"] <= 40:
            rec.append(("Рост без людей",
                        f"активность {P['activity']:.0f}-й процентиль, демографическая устойчивость {P['demo_resilience']:.0f}-й",
                        "Направить часть доходов экономики на качество среды (жильё, социальная инфраструктура), "
                        "иначе рабочие места будут заполняться за счёт маятниковой миграции."))
        n_cust = int((flows[(flows.source == mo) & (flows.target != mo)].rub >= cfg["network"]["flow_min_rub"]).sum())
        if P["hub"] >= vhi or P["supply_reach"] >= vhi:
            rec.append(("Опорный центр снабжения",
                        f"поставщики МО продают госзаказчикам {n_cust} других МО; хаб-индекс {P['hub']:.0f}-й процентиль",
                        "Развивать как межмуниципальный центр: логистика, совместные закупки и сервисные центры для соседних районов."))
        if P["bridge"] >= vhi:
            rec.append(("Связующее звено сети",
                        f"мостовой индекс {P['bridge']:.0f}-й процентиль",
                        "Подходит для пилотов межмуниципальных проектов: изменения здесь быстрее распространяются на разные типы МО."))
        n_lead = int(lead[lead.source == mo].shape[0])
        if P["leadership"] >= vhi:
            rec.append(("Опережающий индикатор",
                        f"динамика трат опережает {n_lead} МО на 1–3 мес.",
                        "Использовать как ранний сигнал в мониторинге региона: просадка здесь предупреждает о спаде у соседей."))
        mixed = an is not None and bool(an.loc[mo, "mixed_type"])
        if r.typicality < 0 or r.bootstrap_stability < 0.5 or mixed:
            alt = names.get(int(an.loc[mo, "second_type"])) if an is not None else None
            rec.append(("Переходный профиль",
                        f"типичность {_sg(r.typicality)}, устойчивость в бутстрепе {r.bootstrap_stability:.2f}"
                        + (f"; второй по вероятности тип — «{alt}»" if alt else ""),
                        "Меры подбирать с учётом обоих типов и отслеживать ежеквартально: МО может сменить тип."))
        bench = an.loc[mo, "benchmark"] if an is not None else None
        if isinstance(bench, str):
            rec.append(("Ориентир",
                        f"похожий по структуре и связям МО с более высокой активностью — {short(bench)}",
                        f"Сравнить практики {short(bench)}: структуру госзаказа, поддержку МСП, работу с поставщиками."))
        if not rec:
            rec.append(("Без выраженных рисков", "индексы близки к медиане типа", "Сохранять текущую модель, мониторить ежеквартально."))

        anom = []
        if isinstance(r.anomalies, str) and r.anomalies:
            for part in r.anomalies.split("; "):
                k, z = part.rsplit(":", 1)
                anom.append(f"{label(k)}: {fmt(k, x.get(k))} ({'выше' if float(z) > 0 else 'ниже'} типичного для типа на {abs(float(z)):.1f} IQR)")
        summary = (f"{short(mo)} относится к типу «{r.cluster_name}» (макротип «{r.macro_name}»). "
                   f"Типичность для своего типа {_sg(r.typicality)}, устойчивость отнесения {r.bootstrap_stability:.2f}.")
        rows.append(dict(mo=mo, summary=summary, strengths=json.dumps(strengths, ensure_ascii=False),
                         weaknesses=json.dumps(weak, ensure_ascii=False), anomalies=json.dumps(anom, ensure_ascii=False),
                         recommendations=json.dumps([dict(topic=a, evidence=b, action=c_) for a, b, c_ in rec], ensure_ascii=False),
                         analogs=(an.loc[mo, "analogs"] if an is not None else ""), benchmark=bench if isinstance(bench, str) else None))
    return pd.DataFrame(rows)


def conclusions(cfg: dict, eng, cards: pd.DataFrame) -> str:
    out = Path(cfg["paths"]["outputs"])
    R = json.load(open(out / "results.json"))
    m = db.read(eng, "res_metrics").set_index("mo")
    L = [f"# Выводы: {cfg['viz']['title']}", "",
         f"Сформировано автоматически командой `econtypes report` по данным базы `{cfg['database']['url']}`.", ""]
    L += ["## 1. Типология", "",
          f"Совмещённая сеть (атрибуты + синхронность трат + опережение + DTW + потоки госзаказа) разбита методом "
          f"`{R['method']}` на k = {R['k']} типов (k выбран автоматически по нормированным ICVI). Устойчивость в бутстрепе: "
          f"ARI = {R['bootstrap_ari']:.2f}; макроуровень (k = {R['macro_k']}) — ARI = {R['macro_bootstrap_ari']:.2f}. "
          f"Типы территориально связны: среднее расстояние внутри типа {R['spatial']['within_km']:.0f} км против "
          f"{R['spatial']['random_mean_km']:.0f} км у случайного разбиения (p = {R['spatial']['p_value']:.3f}).", ""]
    sig = db.read(eng, "res_type_signature") if "res_type_signature" in db.tables(eng) else None
    for c, g in m.groupby("cluster"):
        line = f"- **{g.cluster_name.iloc[0]}** ({len(g)} МО): {', '.join(short(x) for x in g.index)}."
        if sig is not None:
            s = sig[sig.cluster == c].sort_values("effect", key=abs, ascending=False).head(4)
            line += " Отличия от остальных: " + "; ".join(f"{label(r.feature)} {'↑' if r.effect > 0 else '↓'}" for r in s.itertuples()) + "."
        L.append(line)
    L.append("")
    if "res_ml_summary" in db.tables(eng):
        ms = db.read(eng, "res_ml_summary").iloc[0]
        imp = db.read(eng, "res_ml_importance").head(6)
        L += ["## 2. Машинное обучение: воспроизводимость типов", "",
              f"Случайный лес, обученный на метках типов, восстанавливает тип МО по признакам на скользящем контроле "
              f"(leave-one-out) с точностью {ms.loo_accuracy:.0%} против {ms.majority_baseline:.0%} у правила «самый крупный класс». "
              "Главные признаки, различающие типы (важность в случайном лесе, MDI): "
              + ", ".join(f"{label(r.feature)} ({r.importance:.3f})" for r in imp.itertuples()) + ".", ""]
    V = out / "validation_holdout.json"
    if V.exists():
        v = json.load(open(V))
        L += ["## 3. Проверка на новых данных", "",
              "Типы, обученные на 2023–2024 гг., проверены на закупках следующих лет (ближайший центроид типа): "
              + "; ".join(f"{y} — точность {h['accuracy']:.0%} (p = {h['p_value']:.3f})" for y, h in v["holdout"].items())
              + f"; случайное угадывание — {v['chance_mean']:.0%}.", ""]
    if "res_correlations" in db.tables(eng):
        S = db.read(eng, "res_correlations")
        S = S[(S.q_fdr < 0.05) & ~S.apply(lambda r: bool(_trivial(r.x, r.y)), axis=1)]
        S = S.reindex(S.rho.abs().sort_values(ascending=False).index).head(15)
        Pc = db.read(eng, "res_partial_corr") if "res_partial_corr" in db.tables(eng) else pd.DataFrame()
        pk = {(r.x, r.y): r for r in Pc.itertuples()} if len(Pc) else {}
        L += ["## 4. Значимые связи (ρ Спирмена, FDR < 5%)", "",
              "| Показатель 1 | Показатель 2 | ρ | q (FDR) | ρ при контроле размера и урбанизации |", "|---|---|---|---|---|"]
        for r in S.itertuples():
            p = pk.get((r.x, r.y))
            ps = f"{p.partial_rho:+.2f}{' *' if p.q_fdr < 0.05 else ''}" if p is not None else "—"
            L.append(f"| {label(r.x)} | {label(r.y)} | {r.rho:+.2f} | {r.q_fdr:.3f} | {ps} |")
        L += ["", "\\* связь сохраняется и после исключения эффекта размера/урбанизации.", ""]
    if "res_lag_corr_summary" in db.tables(eng):
        Lg = db.read(eng, "res_lag_corr_summary")
        best = Lg.iloc[Lg["median"].abs().idxmax()]
        L += ["## 5. Опережение: госзаказ и потребительские траты", "",
              "Медианная по МО корреляция месячных приростов госзаказа и трат при сдвиге (лаг > 0 — госзаказ впереди): "
              + ", ".join(f"{int(r.lag):+d} мес.: {r['median']:+.2f}" for _, r in Lg.iterrows()) + ". "
              f"Самая сильная связь при лаге {int(best.lag):+d} мес.", ""]
    L += ["## 6. Где нужны меры", ""]
    recs = cards.assign(n=cards.recommendations.map(lambda s: len(json.loads(s))))
    topics = pd.Series([r["topic"] for s in cards.recommendations for r in json.loads(s)]).value_counts()
    L += ["Сколько МО получили рекомендацию по каждой теме:", ""] + [f"- {t}: {n}" for t, n in topics.items()] + [""]
    an = m[m.anomalies.fillna("") != ""]
    L += [f"Заметно отличаются от своего типа хотя бы по одному признаку (> 2 межквартильных размахов): {len(an)} МО — подробнее в mo_reports.md.", ""]
    text = "\n".join(L)
    (out / "conclusions.md").write_text(text, encoding="utf-8")
    return text


def run(cfg: dict, eng) -> pd.DataFrame:
    out = Path(cfg["paths"]["outputs"])
    cards = mo_cards(cfg, eng)
    db.write(eng, "res_mo_report", cards)
    md = ["# Карточки муниципальных образований", ""]
    for r in cards.itertuples():
        md += [f"## {short(r.mo)}", "", r.summary, ""]
        for title, key in (("Сильные стороны", "strengths"), ("Слабые места", "weaknesses"), ("Отличия от своего типа", "anomalies")):
            items = json.loads(getattr(r, key))
            if items:
                md += [f"**{title}:**", ""] + [f"- {i}" for i in items] + [""]
        md += ["**Выводы и рекомендации:**", ""]
        for rec in json.loads(r.recommendations):
            md.append(f"- *{rec['topic']}.* {rec['evidence'].rstrip('.')}. → {rec['action']}")
        md += ["", f"Ближайшие аналоги: {', '.join(short(a) for a in str(r.analogs).split('; ') if a)}", ""]
    (out / "mo_reports.md").write_text("\n".join(md), encoding="utf-8")
    cards.to_csv(out / "tables/mo_report.csv", index=False)
    conclusions(cfg, eng, cards)
    return cards
