"""Паспорта МО из Базы данных показателей муниципальных образований Росстата (БД ПМО).

Экспорт «Паспорт МО» в формате Word — это HTML с таблицами по разделам. Из каждого паспорта
берём (январь–декабрь, среднее за 2023–2024):
  * среднесписочную численность работников организаций — всего и по разделам ОКВЭД;
  * среднемесячную заработную плату работников организаций — всего.
Признаки МО: уровень формальной занятости (работники на 1000 жителей), средняя зарплата,
доли занятых по укрупнённым разделам ОКВЭД (отраслевая структура занятости).
"""
from __future__ import annotations

import glob
import io
import re

import pandas as pd

from .mo_directory import mo_key

EMP = "Среднесписочная численность работников организаций (без субъектов малого"
WAGE = "Среднемесячная заработная плата работников организаций (без субъектов малого"
SECTIONS = {  # раздел ОКВЭД → укрупнённая группа
    "А": "agri", "A": "agri", "В": "industry", "B": "industry", "C": "industry", "С": "industry",
    "D": "industry", "E": "industry", "F": "construction", "G": "trade", "H": "transport",
    "I": "services", "J": "services", "K": "services", "L": "services", "M": "services", "N": "services",
    "O": "public", "P": "education", "Q": "health", "R": "services", "S": "services",
}


def _mo_name(html: str) -> str | None:
    """Имя МО — заголовок сразу после типа («Муниципальный район» / «Городской округ»)."""
    heads = [re.sub(r"\s+", " ", x).strip() for x in re.findall(r"<(?:h\d|p|div|b)[^>]*>([^<]{3,160})</", html)]
    for i, h in enumerate(heads[:-1]):
        if h in ("Муниципальный район", "Городской округ"):
            name = heads[i + 1]
            if "округа Республики" in name:      # сводный паспорт по всем ГО — не МО
                return None
            if h == "Городской округ":
                return "городской округ " + name
            return name
    return None


def parse_passport(path: str, years=("2023", "2024")) -> dict | None:
    raw = open(path, "rb").read()
    html = None
    for enc in ("utf-8", "cp1251"):
        try:
            html = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if not html or "<table" not in html.lower():
        return None
    name = _mo_name(html)
    if not name:
        return None
    rec = {"mo": mo_key(name), "source_file": path}
    for t in pd.read_html(io.StringIO(html)):
        first = t.iloc[:, 0].astype(str)
        if not first.str.contains("Среднесписочная численность работников организаций|Среднемесячная заработная плата работников организаций").any():
            continue
        block, section = None, None
        for _, row in t.iterrows():
            label = str(row.iloc[0]).strip()
            if label.startswith(EMP[:60]):
                block = "emp" if "муниципальной формы" not in label else None
                section = None
                continue
            if label.startswith(WAGE[:60]):
                block = "wage" if "муниципальной формы" not in label else None
                section = None
                continue
            if label.startswith("Среднесписочная") or label.startswith("Среднемесячная") or label.startswith("Фонд"):
                block = None
                continue
            if block is None:
                continue
            if label.startswith("Всего по обследуемым"):
                section = "total"
                continue
            m = re.match(r"Раздел\s+(\S)", label)
            if m:
                letter = m.group(1).translate(str.maketrans("АВЕКМНОРСТХ", "ABEKMHOPCTX"))
                section = SECTIONS.get(letter, "other")
                continue
            if label == "январь-декабрь" and section:
                vals = [pd.to_numeric(row.get(y), errors="coerce") for y in years]
                vals = [v for v in vals if pd.notna(v)]
                if vals:
                    key = f"{block}_{section}"
                    v = sum(vals) / len(vals)
                    rec[key] = rec.get(key, 0) + v if block == "emp" and section != "total" else v
    return rec


COMPACT = True   # укрупнение: промышленность, бюджетный сектор, сельское хозяйство (меньше шума малых разделов)


def _features(d: pd.DataFrame, pop: pd.DataFrame) -> pd.DataFrame:
    popm = pop.set_index("mo")["pop"]
    out = pd.DataFrame(index=d.index)
    out["wage"] = d.get("wage_total")
    out["emp_per_1000"] = d["emp_total"] / d.index.map(popm) * 1000
    sh = lambda cols: sum(d.get(f"emp_{c}", 0).fillna(0) if hasattr(d.get(f"emp_{c}", 0), "fillna") else 0 for c in cols) / d["emp_total"]
    out["emp_sh_industry"] = sh(["industry", "construction"])
    out["emp_sh_budget"] = sh(["public", "education", "health"])
    out["emp_sh_agri"] = sh(["agri"])
    return out


def load_dir(pattern: str, pop: pd.DataFrame) -> pd.DataFrame:
    """Все паспорта из папки → признаки МО. Нет файлов → пустая таблица (признаки не используются)."""
    recs = [r for f in sorted(glob.glob(pattern)) if (r := parse_passport(f))]
    if not recs:
        return pd.DataFrame()
    d = pd.DataFrame(recs).drop_duplicates("mo", keep="last").set_index("mo")
    if COMPACT:
        return _features(d, pop)
    popm = pop.set_index("mo")["pop"]
    out = pd.DataFrame(index=d.index)
    out["wage"] = d.get("wage_total")
    out["emp_per_1000"] = d.get("emp_total") / d.index.map(popm) * 1000
    groups = ["agri", "industry", "construction", "trade", "transport", "public", "education", "health", "services"]
    for g in groups:
        if f"emp_{g}" in d:
            out[f"emp_sh_{g}"] = d[f"emp_{g}"].fillna(0) / d["emp_total"]
    return out


def load_csv(path: str, pop: pd.DataFrame, year: int = 2023) -> pd.DataFrame:
    """Плоская выгрузка паспортов (oktmo;municipality;section;indicator;unit;year;value).

    В выгрузке у показателя нет родителя: «Всего … — январь-декабрь» встречается в трёх блоках.
    Блок различаем по единице: человек — численность работников, рублей — средняя зарплата,
    тысяча рублей — фонд оплаты труда. Первое вхождение — все организации, следующее —
    организации муниципальной формы собственности (его не берём).
    """
    d = pd.read_csv(path, sep=";", dtype={"oktmo": str})
    d = d[(d.section == "Занятость и заработная плата") & (d.year == year)
          & d.indicator.str.endswith("январь-декабрь")].copy()
    d = d.drop_duplicates(["municipality", "indicator", "unit"], keep="first")
    d["mo"] = d.municipality.map(lambda n: mo_key(n.replace("город ", "городской округ город ")))
    d["head"] = d.indicator.str.split(" — ").str[0]
    rows = {}
    for (mo, unit), g in d.groupby(["mo", "unit"]):
        r = rows.setdefault(mo, {})
        for h, v in zip(g["head"], g["value"]):
            if h.startswith("Всего"):
                key = "total"
            else:
                m = re.match(r"Раздел\s+(\S)", h)
                if not m:
                    continue
                key = SECTIONS.get(m.group(1).translate(str.maketrans("АВЕКМНОРСТХ", "ABEKMHOPCTX")), "other")
            if unit == "человек":
                r[f"emp_{key}"] = r.get(f"emp_{key}", 0) + v if key != "total" else v
            elif unit == "рублей" and key == "total":
                r["wage_total"] = v
    b = pd.DataFrame.from_dict(rows, orient="index")
    return _features(b, pop)
