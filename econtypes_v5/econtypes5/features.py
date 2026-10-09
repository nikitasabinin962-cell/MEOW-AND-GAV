"""Панель признаков МО × период × режим (FORMULA_FEATURES_MO_PERIOD) и внешние показатели.

Режимы:
  retrospective — реконструкция: окно t может использовать статические характеристики, опубликованные
                  позже t (перепись 2021 г., агрегированная структура трат 2023–2024, рост населения
                  за год окна). Каждая такая колонка помечена hindsight=1.
  monitoring    — только информация, доступная на конец окна t: помесячные траты ≤ t, контракты с
                  датой заключения ≤ t, демография с учётом лага публикации (ASSUMED_AVAILABILITY).
Окно квартала t — скользящие 4 квартала, заканчивающиеся t (warm-up: 2023Q1–Q3 короче 4 кварталов).
Окно 'static' — 2023-01…2024-12.

Блоки (роль — признак узла; рёбра, ICVI и co-assignment считаются отдельно и в признаки не входят):
  sber_level      log среднемесячных безналичных трат на жителя; относительный тренд (наклон остатка)
  sber_structure  ILR 6 частей структуры трат (агрегат 2023–2024, только retrospective)
  proc_budget     log госзаказа 44-ФЗ на жителя в год; доля муниципального уровня; HHI поставщиков
  proc_geo        ILR {свой МО, другие МО РБ, вне РБ} по стоимости с известной географией поставщика
  proc_corp       log закупок 223-ФЗ на жителя в год (присутствие госкомпаний)
  demography      темп роста населения; естественный прирост ‰; миграционный прирост ‱
  age_structure   ILR {0–14, 15–64, 65+} по ВПН-2020
"""
from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from . import compositional as CO

QUARTERS = [f"{y}Q{q}" for y in (2023, 2024) for q in (1, 2, 3, 4)]
MONTHS = [f"{y}-{m:02d}" for y in (2023, 2024) for m in range(1, 13)]
SBER_PARTS = ["Продовольствие", "Здоровье", "Общественное питание", "Маркетплейсы", "Транспорт", "прочее"]
CUSTOMER_GEO_INCLUSIVE = ("name_and_tax_office_agree", "name_only", "name_tax_office_conflict", "tax_office_hypothesis")
CUSTOMER_GEO_STRICT = ("name_and_tax_office_agree", "name_only")

# Допущения о доступности (фактические даты публикации в файлах отсутствуют; выбраны консервативно)
ASSUMED_AVAILABILITY = {
    "population_jan1": "Y-06-30",        # численность на 01.01.Y — не раньше 30.06.Y
    "edn_year": "(Y+1)-03-31",           # естественное движение за год Y
    "migration_year": "(Y+1)-04-30",     # миграционный прирост за год Y
    "census_2021": "2023-12-31",         # таблицы ВПН-2020 по МО (возраст, образование, источники средств)
    "sber_month": "конец месяца",        # помесячные траты (ряд СберИндекса публикуется с лагом; в мониторинге принят 0)
    "contract": "дата заключения",       # реестровая запись появляется в ЕИС в течение нескольких дней
}

BLOCKS = {
    "sber_level": ["sber_spend_pc_log", "sber_rel_trend"],
    "sber_structure": [f"sber_ilr{k}" for k in range(1, 6)],
    "proc_budget": ["proc44_pc_log", "proc44_muni_share", "supplier_hhi"],
    "proc_geo": ["procgeo_ilr1", "procgeo_ilr2"],
    "proc_corp": ["proc223_pc_log"],
    "demography": ["pop_growth", "natinc_rate", "migr_rate"],
    "age_structure": ["age_ilr1", "age_ilr2"],
}
UNITS = {
    "sber_spend_pc_log": "log(руб./жителя/мес.)", "sber_rel_trend": "лог-пункты/год относительно среднего МО",
    "proc44_pc_log": "log(1+руб./жителя/год)", "proc44_muni_share": "доля стоимости", "supplier_hhi": "индекс Херфиндаля (0–1]",
    "procgeo_ilr1": "ILR", "procgeo_ilr2": "ILR", "proc223_pc_log": "log(1+руб./жителя/год)",
    "pop_growth": "доля за год", "natinc_rate": "‰", "migr_rate": "‱ (на 10 тыс.)", "age_ilr1": "ILR", "age_ilr2": "ILR",
    **{f"sber_ilr{k}": "ILR" for k in range(1, 6)},
}
SOURCES = {
    "sber_level": "archive_D_json_v4 (СберИндекс, производный)", "sber_structure": "archive_features_raw_v4 (СберИндекс, производный)",
    "proc_budget": "processed_contracts_part_001…008 + org_geo_resolved", "proc_geo": "processed_contracts + org_geo_resolved + msp_firm",
    "proc_corp": "processed_contracts_part_001…008", "demography": "rosstat_population_20xx, rosstat_edn_mo_2024, rosstat_migr_mo_*",
    "age_structure": "vpn2020_age_mo",
}


def quarter_months(q: str) -> list[str]:
    y, k = int(q[:4]), int(q[-1])
    return [f"{y}-{m:02d}" for m in range(3 * k - 2, 3 * k + 1)]


def window_quarters(t: str, length: int = 4) -> list[str]:
    i = QUARTERS.index(t)
    return QUARTERS[max(0, i - length + 1): i + 1]


def quarter_end(q: str) -> str:
    y, k = int(q[:4]), int(q[-1])
    return {1: f"{y}-03-31", 2: f"{y}-06-30", 3: f"{y}-09-30", 4: f"{y}-12-31"}[k]


class Data:
    """Загрузка фактов из базы v5 один раз."""

    def __init__(self, db_path: str):
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.mo = pd.read_sql("SELECT mo_id, name, kind FROM mo ORDER BY mo_id", con).set_index("mo_id")
        f = pd.read_sql("SELECT mo_id, indicator, period, value, source_id FROM fact_mo", con)
        self.facts = f
        sp = f[f.indicator == "sber_spend_pc_month"].pivot(index="mo_id", columns="period", values="value")
        self.spend = sp.reindex(self.mo.index)[MONTHS]
        self.pop = f[f.indicator == "population"].pivot(index="mo_id", columns="period", values="value").reindex(self.mo.index)
        self.v4 = f[f.indicator.str.startswith("v4_")].pivot(index="mo_id", columns="indicator", values="value").reindex(self.mo.index)
        self.contracts = pd.read_sql("""
            SELECT c.canonical_contract_id id, c.law, c.budget_level, c.sign_date, c.amount_kopecks, c.currency, c.financial_status,
                   c.customer_inn, c.supplier_inn, rc.mo_id cmo, rc.quality cq, rs.mo_id smo, rs.region_code sreg, rs.quality sq,
                   (mi.inn IS NOT NULL) supplier_in_msp_index_2026
            FROM contract c
            LEFT JOIN org_geo_resolved rc ON rc.inn=c.customer_inn AND rc.kpp=IFNULL(c.customer_kpp,'') AND rc.role='customer'
            LEFT JOIN org_geo_resolved rs ON rs.inn=c.supplier_inn AND rs.kpp=IFNULL(c.supplier_kpp,'') AND rs.role='supplier'
            LEFT JOIN msp_index_firm mi ON mi.inn=c.supplier_inn""", con)
        c = self.contracts
        c["rub"] = c.amount_kopecks / 100.0
        c["month"] = c.sign_date.str[:7]
        c["quarter"] = pd.PeriodIndex(c.sign_date, freq="Q").astype(str)
        self.msp = pd.read_sql("SELECT inn, okved_section, mo_id_candidate, geo_status, category_code FROM msp_firm", con)
        self.ufa = int(self.mo.index[self.mo.name == "ГО Уфа"][0])
        con.close()


# ------------------------------------------------------------------ отдельные блоки
def sber_level(d: Data, months: list[str]) -> pd.DataFrame:
    Y = d.spend[months]
    obs = Y.notna().sum(axis=1)
    lvl = np.log(Y.mean(axis=1, skipna=True).where(obs > 0))
    L = np.log(Y.where(Y > 0))
    R = L.sub(L.mean(axis=0), axis=1)
    x = np.arange(len(months)) / 12.0
    tr = []
    for _, row in R.iterrows():
        m = row.notna().to_numpy()
        tr.append(np.polyfit(x[m], row.to_numpy()[m], 1)[0] if m.sum() >= 6 else np.nan)
    return pd.DataFrame({"sber_spend_pc_log": lvl, "sber_rel_trend": tr, "_coverage_sber": obs / len(months)}, index=Y.index)


def sber_structure(d: Data) -> tuple[pd.DataFrame, dict]:
    cols = ["v4_sh_" + p for p in SBER_PARTS]
    P = d.v4[cols].to_numpy(dtype=float)
    r = CO.ilr_coordinates(P, SBER_PARTS)
    df = pd.DataFrame(r["Z"], index=d.v4.index, columns=[f"sber_ilr{k}" for k in range(1, r["Z"].shape[1] + 1)])
    return df, dict(labels=r["labels"], diagnostics=r["diagnostics"])


def procurement(d: Data, quarters: list[str], pop: pd.Series, geo: tuple, exclude_ufa_regional: bool = True) -> pd.DataFrame:
    c = d.contracts
    c = c[c.quarter.isin(quarters) & (c.currency == "RUB") & (c.financial_status == "known") & c.cq.isin(geo)]
    years = len(quarters) / 4.0
    c44 = c[c.law == "44-ФЗ"]
    if exclude_ufa_regional:  # республиканские/федеральные заказчики в Уфе обслуживают всю республику
        c44 = c44[~((c44.cmo == d.ufa) & c44.budget_level.isin(["1", "2"]))]
    tot44 = c44.groupby("cmo").rub.sum()
    muni = c44[c44.budget_level == "3"].groupby("cmo").rub.sum()
    out = pd.DataFrame(index=d.mo.index)
    out["proc44_rub"] = tot44.reindex(out.index).fillna(0.0)
    out["proc44_pc_log"] = np.log1p(out.proc44_rub / years / pop)
    out["proc44_muni_share"] = (muni.reindex(out.index).fillna(0) / out.proc44_rub).where(out.proc44_rub > 0)
    # HHI поставщиков (по контрактам с ИНН поставщика)
    s = c44[c44.supplier_inn.notna()]
    by = s.groupby(["cmo", "supplier_inn"]).rub.sum()
    share = by / by.groupby(level=0).transform("sum")
    out["supplier_hhi"] = (share ** 2).groupby(level=0).sum().reindex(out.index)
    out["_cov_supplier_inn"] = (s.groupby("cmo").rub.sum() / tot44).reindex(out.index)
    # география поставщиков: свой МО / другие МО РБ / вне РБ; неизвестное исключается (покрытие отдельно)
    g = c44.copy()
    g["cat"] = np.select([g.sreg.notna() & (g.sreg != "02"),
                          (g.sreg == "02") & g.smo.notna() & (g.smo == g.cmo),
                          (g.sreg == "02") & g.smo.notna() & (g.smo != g.cmo)],
                         ["outside", "local", "other_rb"], default="unknown")
    pv = g.pivot_table(index="cmo", columns="cat", values="rub", aggfunc="sum").reindex(out.index).fillna(0.0)
    for k in ["local", "other_rb", "outside", "unknown"]:
        if k not in pv:
            pv[k] = 0.0
    known = pv[["local", "other_rb", "outside"]].sum(axis=1)
    out["_cov_supplier_geo"] = (known / (known + pv.unknown)).where(known + pv.unknown > 0)
    P = pv[["local", "other_rb", "outside"]].div(known.where(known > 0), axis=0)
    P[out["_cov_supplier_geo"] < 0.5] = np.nan
    P, nrep = CO.multiplicative_replacement(P.to_numpy(), delta=1e-3)
    Z = CO.ilr(P)
    out["procgeo_ilr1"], out["procgeo_ilr2"] = Z[:, 0], Z[:, 1]
    out["share_local_suppliers"] = pv.local / known.where(known > 0)
    out["share_outside_rb_suppliers"] = pv.outside / known.where(known > 0)
    ufa_ext = g[(g.cat == "other_rb") & (g.smo == d.ufa)].groupby("cmo").rub.sum()
    out["ufa_share_of_other_rb"] = (ufa_ext.reindex(out.index).fillna(0) / pv.other_rb.where(pv.other_rb > 0)).where(out.index != d.ufa)
    out["_procgeo_zero_replaced"] = nrep
    msp = c44[c44.supplier_inn.notna()]
    out["msp2026_supplier_value_share"] = (msp[msp.supplier_in_msp_index_2026 == 1].groupby("cmo").rub.sum() / msp.groupby("cmo").rub.sum()).reindex(out.index)
    c223 = c[c.law == "223-ФЗ"].groupby("cmo").rub.sum()
    out["proc223_pc_log"] = np.log1p(c223.reindex(out.index).fillna(0.0) / years / pop)
    out["n_contracts_44"] = c44.groupby("cmo").size().reindex(out.index).fillna(0).astype(int)
    # нет ни одного привязанного контракта 44-ФЗ — это пропуск наблюдения (неразрешённая география), а не нулевой спрос
    none = out.n_contracts_44 == 0
    out.loc[none, ["proc44_pc_log", "proc44_muni_share", "supplier_hhi", "procgeo_ilr1", "procgeo_ilr2", "proc223_pc_log"]] = np.nan
    return out


def population_for(d: Data, t_end: str, mode: str) -> tuple[pd.Series, str]:
    """Знаменатель на душу: retrospective — 01.01 года окна; monitoring — последнее опубликованное."""
    y = int(t_end[:4])
    if mode == "retrospective":
        return d.pop[f"{y}-01-01"], f"{y}-01-01"
    for yy in range(y, 2021, -1):
        if f"{yy}-06-30" <= t_end and f"{yy}-01-01" in d.pop:
            return d.pop[f"{yy}-01-01"], f"{yy}-01-01"
    return d.pop["2022-01-01"] * np.nan, "unavailable"


def demography(d: Data, t_end: str, mode: str) -> tuple[pd.DataFrame, dict]:
    y = int(t_end[:4])
    f = d.facts
    out = pd.DataFrame(index=d.mo.index)
    meta = {}
    if mode == "retrospective":
        a, b = f"{y}-01-01", f"{y + 1}-01-01"
        yr = y
    else:
        cand = [yy for yy in range(y, 2021, -1) if f"{yy + 1}-06-30" <= t_end]
        a, b = (f"{cand[0]}-01-01", f"{cand[0] + 1}-01-01") if cand else (None, None)
        yr = None
    out["pop_growth"] = (d.pop[b] / d.pop[a] - 1) if a and b in d.pop else np.nan
    meta["pop_growth"] = f"{a}→{b}" if a else "unavailable"

    def ind(name, unit_avail_year):
        sel = f[(f.indicator == name) & (f.source_id.isin(["rosstat_edn_mo_2024", "rosstat_migr_mo_2024", "rosstat_migr_mo_2018_2023"]))]
        if mode == "retrospective":
            yy = str(y)
        else:
            ys = sorted({int(p) for p in sel.period if unit_avail_year(int(p)) <= t_end}, reverse=True)
            yy = str(ys[0]) if ys else None
        if yy is None:
            return pd.Series(np.nan, index=out.index), "unavailable"
        s = sel[sel.period == yy]
        # для 2023 есть две публикации миграции — берём более позднюю (2024 г.) как ревизию
        s = s.sort_values("source_id").drop_duplicates("mo_id", keep="first")
        return s.set_index("mo_id").value.reindex(out.index), yy

    out["natinc_rate"], meta["natinc_rate"] = ind("natinc_rate", lambda Y: f"{Y + 1}-03-31")
    out["migr_rate"], meta["migr_rate"] = ind("migr_rate", lambda Y: f"{Y + 1}-04-30")
    return out, meta


def age_structure(d: Data) -> tuple[pd.DataFrame, dict]:
    f = d.facts[d.facts.source_id == "vpn2020_age_mo"]
    pv = f.pivot(index="mo_id", columns="indicator", values="value").reindex(d.mo.index)
    kids = pv[["census_age_0-4", "census_age_5-9", "census_age_10-14"]].sum(axis=1, min_count=3)
    old = pv[["census_age_65-69", "census_age_70-74", "census_age_75-79", "census_age_80-84", "census_age_85иболее"]].sum(axis=1, min_count=5)
    work = pv["census_age_total"] - kids - old
    P = np.column_stack([kids, work, old])
    r = CO.ilr_coordinates(P / P.sum(axis=1, keepdims=True), ["0–14", "15–64", "65+"])
    df = pd.DataFrame(r["Z"], index=d.mo.index, columns=["age_ilr1", "age_ilr2"])
    df["share_65plus"] = old / pv["census_age_total"]
    df["share_0_14"] = kids / pv["census_age_total"]
    return df, dict(labels=r["labels"])


def external_indicators(d: Data) -> pd.DataFrame:
    """Внешние показатели для интерпретации/валидации — НЕ входят в обучение v5."""
    f = d.facts
    out = pd.DataFrame(index=d.mo.index)
    lv = f[f.source_id == "vpn2020_livelihood_mo"].pivot(index="mo_id", columns="indicator", values="value").reindex(d.mo.index)
    tot = lv["census_livelihood_total"]
    out["ext_census_wage_main_share"] = lv["census_main_wage"] / tot
    out["ext_census_pension_benefit_main_share"] = lv["census_main_pensions_benefits"] / tot
    out["ext_census_dependent_main_share"] = lv["census_main_dependent"] / tot
    out["ext_census_business_main_share"] = lv["census_main_business"] / tot
    out["ext_census_subsistence_main_share"] = lv["census_main_subsistence"] / tot
    ed = f[f.source_id == "vpn2020_education_mo"].pivot(index="mo_id", columns="indicator", values="value").reindex(d.mo.index)
    out["ext_census_higher_edu_share"] = (ed["census_edu_higher"] + ed["census_edu_postgrad"]) / ed["census_edu_indicated"]
    for c, newc in [("v4_market_access", "ext_market_access_sber"), ("v4_wage", "ext_wage_large_medium_orgs_v4"),
                    ("v4_emp_sh_budget", "ext_emp_share_budget_sector_v4"), ("v4_emp_sh_industry", "ext_emp_share_industry_v4"),
                    ("v4_emp_sh_agri", "ext_emp_share_agri_v4"), ("v4_grants_pc", "ext_equalization_grants_pc_v4"),
                    ("v4_urban_share", "ext_urban_share_v4"), ("v4_log_density", "ext_log_density_v4"),
                    ("v4_emp_per_1000", "ext_employees_per_1000_v4")]:
        out[newc] = d.v4[c]
    msp = d.msp[d.msp.geo_status.isin(["district_text_candidate", "city_text_candidate"])]
    cnt = msp.groupby("mo_id_candidate").size()
    out["ext_msp2026_per_1000"] = cnt.reindex(d.mo.index) / d.pop["2025-01-01"] * 1000
    return out


# ------------------------------------------------------------------ сглаженный LQ МСП
def msp_lq(d: Data, groups: dict[str, list[str]], kappa: float | None = None, seed: int = 0) -> tuple[pd.DataFrame, dict]:
    """p̂_ms = (n_ms + κ π_s)/(n_m + κ), LQ_ms = p̂_ms/π_s, π — доля группы в РБ (эталон — регион).
    κ подбирается по предсказательному правдоподобию: фирмы каждого МО случайно делятся пополам,
    p̂ по половине A оценивается при разных κ, лог-правдоподобие считается на половине B."""
    sec2g = {s: g for g, ss in groups.items() for s in ss}
    m = d.msp[d.msp.geo_status.isin(["district_text_candidate", "city_text_candidate"])].copy()
    m["g"] = m.okved_section.map(sec2g)
    m = m.dropna(subset=["g", "mo_id_candidate"])
    N = m.groupby(["mo_id_candidate", "g"]).size().unstack(fill_value=0).reindex(d.mo.index).fillna(0)
    pi = N.sum() / N.sum().sum()
    rng = np.random.default_rng(seed)
    m["half"] = rng.integers(0, 2, len(m))
    A = m[m.half == 0].groupby(["mo_id_candidate", "g"]).size().unstack(fill_value=0).reindex(index=N.index, columns=N.columns).fillna(0)
    B = m[m.half == 1].groupby(["mo_id_candidate", "g"]).size().unstack(fill_value=0).reindex(index=N.index, columns=N.columns).fillna(0)
    grid = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    ll = {}
    for k in grid:
        ph = (A.to_numpy() + k * pi.to_numpy()) / (A.sum(1).to_numpy()[:, None] + k)
        with np.errstate(divide="ignore"):
            ll[k] = float(np.nansum(B.to_numpy() * np.log(np.where(ph > 0, ph, np.nan))))
        if not np.isfinite(ll[k]) or np.isnan(ll[k]):
            ll[k] = -np.inf
    kbest = max(ll, key=ll.get) if kappa is None else kappa
    ph = (N.to_numpy() + kbest * pi.to_numpy()) / (N.sum(1).to_numpy()[:, None] + kbest)
    LQ = pd.DataFrame(ph / pi.to_numpy(), index=N.index, columns=[f"msp_lq_{c}" for c in N.columns])
    LQ0 = pd.DataFrame((N.to_numpy() / N.sum(1).to_numpy()[:, None]) / pi.to_numpy(), index=N.index, columns=[f"msp_lq_raw_{c}" for c in N.columns])
    LQ["msp_firms_n"] = N.sum(1)
    return LQ.join(LQ0), dict(kappa=kbest, heldout_loglik=ll, pi=pi.round(4).to_dict(), firms=int(N.sum().sum()))


MSP_GROUPS = {"agri": ["A"], "industry": ["B", "C", "D", "E"], "construction": ["F"], "trade": ["G"], "transport": ["H"],
              "consumer_services": ["I", "R", "S"], "business_services": ["J", "K", "L", "M", "N"], "social": ["P", "Q"]}


# ------------------------------------------------------------------ сборка панели
def build_panel(d: Data, geo: tuple = CUSTOMER_GEO_INCLUSIVE) -> tuple[pd.DataFrame, dict]:
    """Длинная панель: mo_id, period, mode, feature, value, unit, block, coverage, imputed, hindsight, source, window."""
    rows, meta = [], {}
    st, st_meta = sber_structure(d)
    age, age_meta = age_structure(d)
    meta.update(sber_structure=st_meta, age_structure=age_meta)
    periods = QUARTERS + ["static"]
    for mode in ("retrospective", "monitoring"):
        for t in periods:
            qs = QUARTERS if t == "static" else window_quarters(t)
            t_end = quarter_end(qs[-1])
            months = [m for q in qs for m in quarter_months(q)]
            warm = t != "static" and len(qs) < 4
            pop, pop_ref = population_for(d, t_end, mode)
            parts = {"sber_level": sber_level(d, months)}
            pr = procurement(d, qs, pop, geo)
            parts["proc_budget"] = pr[BLOCKS["proc_budget"]]
            parts["proc_geo"] = pr[BLOCKS["proc_geo"]]
            parts["proc_corp"] = pr[BLOCKS["proc_corp"]]
            dem, dmeta = demography(d, t_end, mode)
            parts["demography"] = dem
            census_ok = mode == "retrospective" or t_end >= "2023-12-31"
            parts["age_structure"] = age[BLOCKS["age_structure"]] if census_ok else age[BLOCKS["age_structure"]] * np.nan
            parts["sber_structure"] = st if mode == "retrospective" else st * np.nan
            meta[(mode, t)] = dict(window=f"{qs[0]}…{qs[-1]}", warm_up=warm, population_ref=pop_ref, demography=dmeta)
            cov = {"sber_level": parts["sber_level"]["_coverage_sber"], "proc_geo": pr["_cov_supplier_geo"], "proc_budget": pr["_cov_supplier_inn"]}
            for b, cols in BLOCKS.items():
                df = parts[b]
                hindsight = int(mode == "retrospective" and b in ("sber_structure", "age_structure", "demography"))
                for c in cols:
                    for mo_id, v in df[c].items():
                        rows.append(dict(mo_id=mo_id, period=t, mode=mode, feature=c, value=None if pd.isna(v) else float(v),
                                         unit=UNITS[c], block=b, coverage=None if b not in cov or pd.isna(cov[b].get(mo_id)) else float(cov[b][mo_id]),
                                         imputed=0, hindsight=hindsight, warm_up=int(warm), source=SOURCES[b],
                                         window=meta[(mode, t)]["window"], available_by=t_end))
            # описательные (не признаки модели)
            for c in ["share_local_suppliers", "share_outside_rb_suppliers", "ufa_share_of_other_rb", "msp2026_supplier_value_share", "n_contracts_44", "proc44_rub"]:
                for mo_id, v in pr[c].items():
                    rows.append(dict(mo_id=mo_id, period=t, mode=mode, feature=c, value=None if pd.isna(v) else float(v),
                                     unit="descriptive", block="descriptive", coverage=None, imputed=0,
                                     hindsight=int(c.startswith("msp2026")), warm_up=int(warm), source=SOURCES["proc_geo"],
                                     window=meta[(mode, t)]["window"], available_by=t_end))
    return pd.DataFrame(rows), meta


def wide(panel: pd.DataFrame, period: str, mode: str, features: list[str]) -> pd.DataFrame:
    p = panel[(panel.period == period) & (panel["mode"] == mode) & panel.feature.isin(features)]
    return p.pivot(index="mo_id", columns="feature", values="value")[features]
