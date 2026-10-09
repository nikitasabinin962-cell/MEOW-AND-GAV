"""Региональные открытые источники (пример — Республика Башкортостан; для другого региона — свои файлы в config).

* Демографические показатели по городам и районам РБ (Башкортостанстат, PDF):
  рождаемость и смертность на 1000 жителей, миграционный прирост.
* Законы о бюджете РБ на 2023 и 2024 гг. (docx, КонсультантПлюс): распределение дотаций на
  выравнивание бюджетной обеспеченности муниципальных районов и городских округов.
  Дотация на жителя — мера бюджетной зависимости МО от республики.
"""
from __future__ import annotations

import re
import subprocess

import docx
import pandas as pd

from .mo_directory import mo_key


def _mo_from_short(name: str) -> str | None:
    n = name.strip().replace("ё", "е")
    if n.startswith(("г.", "город")):
        return "ГО " + re.findall(r"([А-Я][а-я\-]+)", n)[-1]
    m = re.match(r"([А-Я][а-я\-]+(?:ский|цкий))", n)
    return "МР " + m.group(1) if m else None


def demography(pdf_path: str) -> pd.DataFrame:
    txt = subprocess.run(["pdftotext", "-layout", pdf_path, "-"], capture_output=True, text=True).stdout
    rows = []
    for line in txt.splitlines():
        if not line or line.startswith(" "):        # строки с отступом — города/поселения внутри района
            continue
        m = re.match(r"^(г\. [А-Яа-я\-]+|[А-Я][а-я\-]+(?:ский|цкий))\s+(.*)$", line.strip())
        if not m:
            continue
        nums = re.findall(r"-?\d+(?:,\d+)?", m.group(2))
        if len(nums) < 9:
            continue
        v = [float(x.replace(",", ".")) for x in nums[:9]]
        rows.append(dict(mo=_mo_from_short(m.group(1)), birth_rate=v[1], death_rate=v[3],
                         natural_rate=v[5], migr_net=v[8]))
    return pd.DataFrame(rows).dropna(subset=["mo"]).drop_duplicates("mo").set_index("mo")


def _find_table(doc: docx.Document, keyword: str):
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    last = []
    for el in doc.element.body.iterchildren():
        if el.tag.endswith("}p"):
            t = Paragraph(el, doc).text.strip()
            if t:
                last = (last + [t.upper()])[-6:]
        elif el.tag.endswith("}tbl") and keyword in " ".join(last):
            tb = Table(el, doc)
            if any("Абзелилов" in r.cells[0].text for r in tb.rows):
                return tb
    raise ValueError(keyword)


def _rub(s: str) -> float | None:
    s = s.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def equalization_grants(docx_path: str, year: int) -> pd.Series:
    """Дотации на выравнивание бюджетной обеспеченности по МО за указанный год (руб.)."""
    tb = _find_table(docx.Document(docx_path), "ВЫРАВНИВАНИЕ БЮДЖЕТНОЙ")
    # колонка: первая, в заголовке которой встречается год (или вторая — итоговая)
    col = 1
    for r in tb.rows[:5]:
        for j, c in enumerate(r.cells[1:], 1):
            if str(year) in c.text:
                col = j
                break
    out = {}
    for r in tb.rows:
        name = r.cells[0].text.strip()
        mo = _mo_from_short(name) if ("район" in name or name.startswith("город")) else None
        v = _rub(r.cells[col].text)
        if mo and v is not None:
            out[mo] = v
    return pd.Series(out, name=f"grants_{year}")


def areas(html_path: str) -> pd.Series:
    """Площадь территории МО, км² (страница «Мой Город»: административно-территориальное деление РБ)."""
    import numpy as np
    h = open(html_path, encoding="utf-8", errors="ignore").read()
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    out = {}
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", h, flags=re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).replace("&nbsp;", "").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, flags=re.S)]
        if len(cells) == 8 and re.match(r"^\d+$", cells[0]) and re.search(r"муниципальный район|городской округ|^город ", cells[1], re.I):
            name = cells[1] if "округ" in cells[1] or "район" in cells[1] else "городской округ " + cells[1]
            try:
                out[mo_key(name)] = float(cells[6].replace(" ", "").replace(",", "."))
            except ValueError:
                pass
    return pd.Series(out, name="area_km2")


def load_external(cfg: dict, pop: pd.DataFrame) -> pd.DataFrame:
    """Региональные источники. Каждый необязателен: если файла нет в конфиге, признак пропускается,
    а модель строится на остальных (траты СберИндекса, госзаказ ЕИС, БД ПМО есть для всех регионов)."""
    from . import region as R
    e = cfg["data"].get("external", {}) or {}
    popm = pop.set_index("mo")["pop"]
    out = pd.DataFrame(index=pd.Index(pop.mo, name="mo"))
    if e.get("demography_pdf"):
        dem = demography(e["demography_pdf"])
        dem["migr_rate"] = dem["migr_net"] / dem.index.map(popm) * 1000
        out = out.join(dem[["birth_rate", "death_rate", "migr_rate"]], how="outer")
    if e.get("budget_laws"):
        g = pd.concat([equalization_grants(p, y) for y, p in e["budget_laws"].items()], axis=1)
        g["grants_pc"] = g.mean(axis=1) / g.index.map(popm)
        # МО, отсутствующие в таблице дотаций (региональный центр), дотаций не получают — 0;
        # МО из region.manual_inn_prefixes (ЗАТО) финансируются иначе — пропуск (импутация)
        for mo in pop.mo:
            if mo not in g.index and mo not in R.MANUAL_PREFIXES.values():
                g.loc[mo, "grants_pc"] = 0.0
        out = out.join(g[["grants_pc"]], how="outer")
    if e.get("areas_html"):
        import numpy as np
        a = areas(e["areas_html"])
        out["log_density"] = np.log(out.index.map(pop.set_index("mo")["pop"]) / out.index.map(a))
    # Паспорта БД ПМО (занятость по ОКВЭД, зарплата): подключаются, когда покрыта большая часть МО,
    # иначе признаки почти целиком состояли бы из импутированных значений
    if e.get("bdpmo_glob") or e.get("bdpmo_csv"):
        from pathlib import Path
        from .bdpmo import load_csv, load_dir
        parts = []
        if e.get("bdpmo_glob"):                      # паспорта (полные) — приоритет
            parts.append(load_dir(e["bdpmo_glob"], pop))
        if e.get("bdpmo_csv") and Path(e["bdpmo_csv"]).exists():   # плоская выгрузка — для недостающих МО
            parts.append(load_csv(e["bdpmo_csv"], pop))
        parts = [p for p in parts if len(p)]
        b = pd.concat(parts) if parts else pd.DataFrame()
        b = b[~b.index.duplicated(keep="first")]
        if len(b) >= e.get("bdpmo_min_mo", 50):
            out = out.join(b, how="left")
    return out
