"""Парсеры официальных таблиц Башкортостанстата/ВПН-2020 по МО (исходные PDF/XLSX из папки
пользователя на Google Drive; байты и SHA-256 — external/rosstat_drive/DRIVE_DOWNLOADS.jsonl).

Каждый парсер возвращает длинную таблицу: mo_name_raw, indicator, period, value, unit — и
контрольные итоги по республике, если они есть в таблице. Сопоставление названий с mo_id — в
``mo_key``. ЗАТО Межгорье в опубликованных муниципальных таблицах Росстата отсутствует — это
фиксируется как пропуск (не ноль, не импутация).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pandas as pd

NUM = r"-?\d[\d ]*(?:,\d+)?"


def to_float(s: str) -> float:
    s = str(s).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in {"-", "\\-", "–", "—", ""}:
        return 0.0 if s else float("nan")
    return float(s)


def mo_key(raw: str) -> str | None:
    """Нормализованный ключ МО в нотации v4 ('МР Абзелиловский', 'ГО Уфа')."""
    s = str(raw).replace("ё", "е").replace("Ё", "Е").replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    if "поселение" in s:
        return None
    m = re.search(r"(?:ГО|Городской округ)\s*(?:г\.|город)?\s*([А-ЯЁ][а-яё\-]+)", s)
    if m:
        return "ГО " + m.group(1)
    m = re.match(r"^г\.\s*([А-ЯЁ][а-яё\-]+)$", s)
    if m:
        return "ГО " + m.group(1)
    m = re.match(r"^([А-ЯЁ][а-яё\-]+(?:ский|цкий))(?: муниципальный район)?$", s)
    if m:
        return "МР " + m.group(1)
    return None


def pdf_text(path: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout


def _top_rows(text: str, ncols: int) -> list[tuple[str, list[float]]]:
    """Строки верхнего уровня (без отступа): название + ncols чисел. Подстроки поселений
    (с отступом: 'г. Баймак', 'сельские поселения') пропускаются — они не являются МО верхнего уровня."""
    rows = []
    pat = re.compile(r"^(\S[^\d\-]*?)\s+((?:-?\d+(?:,\d+)?\s+){%d}-?\d+(?:,\d+)?)\s*$" % (ncols - 1))
    for line in text.splitlines():
        if not line or line[0] == " ":
            continue
        m = pat.match(line.rstrip())
        if m:
            rows.append((m.group(1).strip(), [to_float(x) for x in m.group(2).split()]))
    return rows


def parse_edn_2024(path: Path) -> tuple[pd.DataFrame, dict]:
    """Естественное движение по МО, январь–декабрь 2024 и 2023 (оперативные данные)."""
    cols = ["births_2024", "births_2023", "deaths_2024", "deaths_2023", "natinc_2024", "natinc_2023",
            "birth_rate_2024", "birth_rate_2023", "death_rate_2024", "death_rate_2023", "natinc_rate_2024", "natinc_rate_2023"]
    rows = _top_rows(pdf_text(path), 12)
    out, control = [], {}
    for name, vals in rows:
        if name.startswith("Всего"):
            control = dict(zip(cols, vals))
            continue
        key = mo_key(name)
        if key is None:
            continue
        for c, v in zip(cols, vals):
            ind, yr = c.rsplit("_", 1)
            unit = "persons" if ind in ("births", "deaths", "natinc") else "per_1000"
            out.append(dict(mo=key, mo_name_raw=name, indicator=ind, period=yr, value=v, unit=unit))
    return pd.DataFrame(out), control


def parse_migr_dynamics(path: Path) -> tuple[pd.DataFrame, dict]:
    """Коэффициенты миграционного прироста по МО 2018–2023 (на 10 тыс.). Сноска таблицы:
    по МО за 2018–2021 — без учёта итогов ВПН-2020."""
    years = ["2018", "2019", "2020", "2021", "2022", "2023"]
    rows = _top_rows(pdf_text(path), 6)
    out, control = [], {}
    for name, vals in rows:
        if name.startswith("Всего"):
            control = dict(zip(years, vals))
            continue
        key = mo_key(name)
        if key is None:
            continue
        for y, v in zip(years, vals):
            out.append(dict(mo=key, mo_name_raw=name, indicator="migr_rate", period=y, value=v, unit="per_10000"))
    return pd.DataFrame(out), control


def parse_migr_2024(path: Path) -> tuple[pd.DataFrame, dict]:
    rows = _top_rows(pdf_text(path), 2)
    out, control = [], {}
    for name, vals in rows:
        if name.startswith("Всего"):
            control = {"2024": vals[0], "2023": vals[1]}
            continue
        key = mo_key(name)
        if key is None:
            continue
        for y, v in zip(["2024", "2023"], vals):
            out.append(dict(mo=key, mo_name_raw=name, indicator="migr_rate", period=y, value=v, unit="per_10000"))
    return pd.DataFrame(out), control


def parse_census_livelihood_md(path: Path) -> tuple[pd.DataFrame, dict]:
    """ВПН-2020 (по состоянию на 01.10.2021): население по основному источнику средств к существованию.
    Источник — исходный .doc на Drive (SHA-256 в манифесте); таблица транскрибирована из текстового
    представления Drive (служебные строки 'в том числе'/'Продолжение' удалены)."""
    blocks, cur_names = [], None
    for line in Path(path).read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells[0].startswith(("Население", "заработ", "предприн", "производ", "пенси", "стипенд", "сбереж", "сдача", "доход", "обеспеч", "иной")):
            cur_names = [c for c in cells if c]
            continue
        label = cells[0]
        vals = [to_float(c.replace("\\", "")) for c in cells[1:1 + len(cur_names)]]
        for nm, v in zip(cur_names, vals):
            blocks.append(dict(mo_name_raw=nm, label=label, value=v))
    df = pd.DataFrame(blocks)
    lab = {"Население": "census_livelihood_total", "заработ": "census_main_wage", "предприн": "census_main_business",
           "производ": "census_main_subsistence", "пенси": "census_main_pensions_benefits", "стипенд": "census_main_stipend",
           "сбереж": "census_main_savings", "сдача": "census_main_rent", "доход": "census_main_royalty",
           "обеспеч": "census_main_dependent", "иной": "census_main_other"}
    df["indicator"] = df.label.map(lambda s: next(v for k, v in lab.items() if s.startswith(k)))
    df["mo"] = df.mo_name_raw.map(mo_key)
    control = df[df.mo_name_raw.str.startswith("Республика")].set_index("indicator").value.to_dict()
    df = df[df.mo.notna()].assign(period="2021-10-01", unit="persons")
    return df[["mo", "mo_name_raw", "indicator", "period", "value", "unit"]], control


def _xlsx_blocks(path: Path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Муниципальные образования"]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def parse_census_age(path: Path) -> tuple[pd.DataFrame, dict]:
    """ВПН-2020: население по 5-летним возрастным группам (оба пола) по МО."""
    rows = _xlsx_blocks(path)
    out, control, cur = [], {}, None
    for r in rows:
        if len(r) < 5:
            continue
        label = r[3]
        if isinstance(label, str) and "поселение" in label:
            cur = None
            continue
        if isinstance(label, str) and (("муниципальный район" in label) or ("Городской округ" in label) or label.startswith("Республика")):
            cur = label.strip()
            if isinstance(r[4], (int, float)):
                rec = dict(mo_name_raw=cur, group="total", value=float(r[4]))
                if cur.startswith("Республика"):
                    control["total"] = float(r[4])
                else:
                    out.append(rec)
            continue
        if cur and isinstance(label, str) and re.match(r"^\s*\d+\s*[–-]\s*\d+\s*$|^\s*\d+\s*(и более|и старше)", label.strip()):
            g = re.sub(r"\s+", "", label.replace("–", "-"))
            if isinstance(r[4], (int, float)):
                if cur.startswith("Республика"):
                    control[g] = float(r[4])
                else:
                    out.append(dict(mo_name_raw=cur, group=g, value=float(r[4])))
    df = pd.DataFrame(out)
    df["mo"] = df.mo_name_raw.map(mo_key)
    return df, control


def parse_census_education(path: Path) -> tuple[pd.DataFrame, dict]:
    """ВПН-2020: уровень образования населения 6+ по МО — берём строки 'Мужчины и женщины в возрасте 6 лет и более'
    (всего, указавшие уровень, высшее (вкл. кадры высшей квалификации? — нет, отдельная колонка), СПО)."""
    rows = _xlsx_blocks(path)
    out, control, cur = [], {}, None
    for r in rows:
        vals = [c for c in r if c is not None]
        if not vals:
            continue
        first = vals[0]
        if isinstance(first, str) and (("муниципальный район" in first) or ("Городской округ" in first) or first.startswith("Республика")) and len(vals) == 1:
            cur = first.strip()
            continue
        if cur and isinstance(first, str) and first.startswith("Мужчины и женщины в возрасте 6 лет"):
            nums = [v for v in vals[1:]]
            rec = dict(total_6p=nums[0], indicated=nums[1], postgrad=nums[2], higher=nums[3], spo=nums[8] if len(nums) > 8 else None)
            if cur.startswith("Республика"):
                control = rec
            else:
                for k, v in rec.items():
                    out.append(dict(mo_name_raw=cur, indicator=f"census_edu_{k}", value=float(v) if isinstance(v, (int, float)) else float("nan")))
            cur = None
    df = pd.DataFrame(out)
    df["mo"] = df.mo_name_raw.map(mo_key)
    return df, control
