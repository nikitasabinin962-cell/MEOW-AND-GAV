"""Панель признаков «МО × период».

Два блока атрибутов узла:
  A. Потребление (СберИндекс): уровень безналичных трат на человека и структура трат
     по категориям (доли), включая «прочее».
  B. Бюджетный спрос (ЕИС, 44-ФЗ): госзаказ на душу населения, кто его исполняет
     (местные поставщики / Уфа / другие регионы), доля закупок у единственного
     поставщика и отраслевая структура по ОКПД2.
Плюс статические признаки: численность и доля городского населения.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import region as R


def sber_panel(cons: pd.DataFrame, id_map: pd.DataFrame, categories: list[str], freq: str) -> pd.DataFrame:
    """cons — consumption.parquet (territory_id, date, category, value)."""
    s = cons.merge(id_map[["territory_id", "mo"]], on="territory_id")
    s["period"] = pd.to_datetime(s["date"]).dt.to_period(freq)
    w = s.pivot_table(index=["mo", "period"], columns="category", values="value", aggfunc="mean")
    out = pd.DataFrame(index=w.index)
    out["spend_total"] = w["Все категории"]
    for c in categories:
        out["sh_" + c] = w[c] / w["Все категории"]
    out["sh_прочее"] = 1 - out[[f"sh_{c}" for c in categories]].sum(axis=1)
    return out


def sber_monthly(cons: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    """Помесячный ряд общих трат: строки — МО, столбцы — месяцы (для корреляций и DTW)."""
    s = cons[cons.category == "Все категории"].merge(id_map[["territory_id", "mo"]], on="territory_id")
    return s.pivot_table(index="mo", columns="date", values="value")


def attach_mo(contracts: pd.DataFrame, prefix_map: pd.DataFrame) -> pd.DataFrame:
    pm = prefix_map.dropna(subset=["mo"]).set_index("prefix")["mo"]
    c = contracts.copy()
    c["customer_mo"] = c["customer_inn"].str[:4].map(pm)
    c["supplier_mo"] = c["supplier_inn"].str[:4].map(pm)
    c["supplier_outside"] = ~c["supplier_inn"].str[:2].eq(R.INN_CODE)
    return c


def procurement_panel(c: pd.DataFrame, positions: pd.DataFrame, pop: pd.DataFrame,
                      groups: dict[str, list[str]], freq: str, exclude_rep_ufa: bool) -> pd.DataFrame:
    c = c.dropna(subset=["customer_mo"]).copy()
    if exclude_rep_ufa:
        c = c[~((c.customer_mo == R.CAPITAL) & c.republican)]
    c["period"] = c["date"].dt.to_period(freq)
    c["v_local"] = c.price * (c.supplier_mo == c.customer_mo)
    c["v_ufa"] = c.price * ((c.supplier_mo == R.CAPITAL) & (c.customer_mo != R.CAPITAL))
    c["v_out"] = c.price * c.supplier_outside
    c["v_single"] = c.price * c.single_supplier
    g = c.groupby(["customer_mo", "period"])
    out = g[["price", "v_local", "v_ufa", "v_out", "v_single"]].sum()
    out.index.names = ["mo", "period"]
    popm = pop.set_index("mo")["pop"]
    out["proc_pc"] = out["price"] / out.index.get_level_values("mo").map(popm).values
    for k in ["local", "ufa", "out", "single"]:
        out[f"proc_{k}_sh"] = out[f"v_{k}"] / out["price"].replace(0, np.nan)

    # отраслевая структура: доля цены контракта, приходящаяся на группу ОКПД2
    p = positions.merge(c[["contract_id", "customer_mo", "period", "price"]], on="contract_id")
    p["v"] = p["weight"] * p["price"]
    for name, codes in groups.items():
        p[name] = p["v"] * p["okpd2_2"].isin(codes)
    og = p.groupby(["customer_mo", "period"])[list(groups)].sum()
    og.index.names = ["mo", "period"]
    og = og.div(out["price"].reindex(og.index).replace(0, np.nan), axis=0)
    og.columns = [f"okpd_{x}_sh" for x in og.columns]
    out = out.join(og)

    # роль МО как поставщика для других муниципалитетов (экспорт услуг/товаров госсектору)
    c2 = c[(c.supplier_mo.notna()) & (c.supplier_mo != c.customer_mo)]
    sup = c2.groupby(["supplier_mo", "period"])["price"].sum()
    sup.index.names = ["mo", "period"]
    out["supply_out_pc"] = sup.reindex(out.index).fillna(0) / out.index.get_level_values("mo").map(popm).values
    keep = ["proc_pc", "proc_local_sh", "proc_ufa_sh", "proc_out_sh", "proc_single_sh", "supply_out_pc"] + list(og.columns)
    return out[keep]


def flows(c: pd.DataFrame, exclude_rep_ufa: bool, freq: str = "Q") -> pd.DataFrame:
    """Потоки госзаказа между МО: поставщик (MO_i) → заказчик (MO_j), руб., по периодам."""
    c = c.dropna(subset=["customer_mo", "supplier_mo"]).copy()
    c["period"] = c["date"].dt.to_period(freq)
    if exclude_rep_ufa:
        c = c[~((c.customer_mo == R.CAPITAL) & c.republican)]
    return c.groupby(["period", "supplier_mo", "customer_mo"])["price"].sum().rename("rub").reset_index()


def build_panel(sber_p: pd.DataFrame, proc_p: pd.DataFrame, pop: pd.DataFrame, market_access: pd.Series) -> pd.DataFrame:
    panel = proc_p.join(sber_p, how="outer")
    st = pop.set_index("mo")[["pop", "urban_share"]].join(market_access.rename("market_access"))
    panel = panel.join(st, on="mo")
    panel["log_pop"] = np.log(panel["pop"])
    return panel.drop(columns="pop").sort_index()
