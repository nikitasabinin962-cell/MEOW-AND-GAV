"""Справочник муниципальных образований Республики Башкортостан.

Связывает три источника, у которых нет общего ключа:
  * ЕИС — у заказчика и поставщика есть только ИНН. Первые 4 цифры ИНН — код налоговой
    инспекции, выдавшей ИНН. В РБ коды 0201–0279 исторически соответствуют районам и
    городам, поэтому префикс ИНН = муниципалитет регистрации организации.
    Соответствие «префикс → МО» восстанавливаем из данных: для каждого префикса берём
    самый частый топоним в наименованиях заказчиков (администрации, школы, больницы).
  * СберИндекс — только название МО.
  * Росстат — ОКТМО, название, численность населения на 01.01.2024.
"""
from __future__ import annotations

import re
import pandas as pd

from . import region as R

_TOKEN = re.compile(
    r"([А-ЯЁ][А-ЯЁ\-]+(?:СКИЙ|ЦКИЙ|СКОГО|ЦКОГО|СКОМ|ЦКОМ)) РАЙОН"
    r"|ГОРОД(?:А|Е|СКОГО ОКРУГА|СКОЙ ОКРУГ|СКОМ ОКРУГЕ)?\s+(?:ГОРОД\s+)?([А-ЯЁ][А-ЯЁ\-]+)"
    r"|Г\.\s?([А-ЯЁ][А-ЯЁ\-]+)"
)


def _toponym(name: str | None) -> str | None:
    m = _TOKEN.search(name or "")
    if not m:
        return None
    if m.group(1):
        t = re.sub(r"(СКОГО|СКОМ)$", "СКИЙ", m.group(1))
        return "R:" + re.sub(r"(ЦКОГО|ЦКОМ)$", "ЦКИЙ", t)
    return "G:" + (m.group(2) or m.group(3))


def mo_key(name: str) -> str:
    """Единый ключ МО: «МР Белебеевский» / «ГО Уфа» — из названий Росстата и СберИндекса."""
    n = name.replace("ё", "е").replace("Ё", "Е")
    if "ородской округ" in n:
        return "ГО " + re.findall(r"([А-Я][а-я\-]+)", n)[-1]
    m = re.search(r"([А-Я][а-я\-]+(?:ский|цкий))", n)
    return "МР " + m.group(1) if m else n


def load_population(path: str) -> pd.DataFrame:
    p = pd.read_csv(path, dtype={"oktmo": str})
    p = p[p.oktmo.str.endswith("00000") & ~p.name.str.contains("поселение")].copy()
    p["mo"] = p["name"].map(mo_key)
    p["urban_share"] = p["urban"] / p["pop"]
    return p[["mo", "oktmo", "name", "pop", "urban_share"]].reset_index(drop=True)


def build_prefix_map(customers: pd.DataFrame, mo_list: list[str]) -> pd.DataFrame:
    """customers: колонки inn, name. Возвращает prefix → mo с долей подтверждения."""
    d = customers.copy()
    d["prefix"] = d["inn"].str[:4]
    d = d[d.prefix.str.startswith(R.INN_CODE)]
    d["tok"] = d["name"].map(_toponym)
    stem2mo = {}
    for mo in mo_list:
        kind, word = mo.split(" ", 1)
        stem2mo[("R:" if kind == "МР" else "G:") + word.upper()] = mo
    rows = []
    for pref, g in d.groupby("prefix"):
        if pref in R.CAPITAL_PREFIXES:
            rows.append((pref, R.CAPITAL, 1.0, len(g), "rule: инспекции регионального центра"))
            continue
        if pref in R.MANUAL_PREFIXES:
            rows.append((pref, R.MANUAL_PREFIXES[pref], 1.0, len(g), "rule: задано в конфиге"))
            continue
        vc = g.tok.dropna().value_counts()
        hit = [(t, c) for t, c in vc.items() if t in stem2mo]
        if not hit:
            rows.append((pref, None, 0.0, len(g), "не определён"))
            continue
        t, c = hit[0]
        rows.append((pref, stem2mo[t], c / max(vc.sum(), 1), len(g), "data: топоним заказчиков"))
    return pd.DataFrame(rows, columns=["prefix", "mo", "confidence", "n_customers", "method"])


def match_sber_ids(consumption: pd.DataFrame, sber_named: pd.DataFrame, connection: pd.DataFrame,
                   mo_list: list[str], anchor: str | None = None) -> pd.DataFrame:
    """territory_id официального набора хакатона ↔ МО Республики Башкортостан.

    В наборе хакатона (consumption.parquet) есть territory_id, но нет названий; в открытой
    выгрузке с сайта СберИндекса есть названия, но нет id. Значения трат в обоих наборах
    совпадают построчно, поэтому сопоставляем id и название по «отпечатку» ряда
    (дата, категория, значение). Одноимённые МО разных регионов (Федоровский, Благовещенский
    районы) различаем по автодорожному расстоянию до Уфы из connection.parquet.
    """
    sn = sber_named.rename(columns={"category_15": "category"}).copy()
    sn["date"] = sn["period"].astype(str).str[:7]
    sn["value"] = sn["value"].round().astype(int)
    m = consumption.merge(sn[["date", "category", "value", "mo"]], on=["date", "category", "value"])
    g = m.groupby(["territory_id", "mo"]).size().reset_index(name="n")
    g = g.sort_values("n", ascending=False).drop_duplicates("territory_id")
    g["key"] = g["mo"].map(mo_key)
    # для ГО оставляем только варианты «город X», муниципальные округа других регионов отбрасываем
    g = g[~(g.key.str.startswith("ГО") & ~g.mo.str.contains("город")) & ~g.mo.str.contains("муниципальный округ")]
    g = g[g.key.isin(mo_list)]
    road = connection[connection.type == "highway"]
    road = pd.concat([road, road.rename(columns={"territory_id_x": "territory_id_y", "territory_id_y": "territory_id_x"})])
    anchor = anchor or R.CAPITAL
    anchor_id = int(g.loc[g.key == anchor, "territory_id"].iloc[0])
    dist = road[road.territory_id_x == anchor_id].set_index("territory_id_y")["distance"]
    g["dist_anchor_km"] = g["territory_id"].map(dist).fillna(0)
    g = g.sort_values("dist_anchor_km").drop_duplicates("key")
    return g.rename(columns={"mo": "sber_name", "key": "mo"})[["mo", "territory_id", "sber_name", "dist_anchor_km"]].reset_index(drop=True)
