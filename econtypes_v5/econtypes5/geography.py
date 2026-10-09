"""Муниципальная привязка организаций с уровнями доказательности (без подмены ОКТМО).

Проверенного ИНН/КПП → ОКТМО с датой действия в доступных данных нет (ЕГРЮЛ/ГАР недоступны из
контейнера; см. DATA_GAPS.md). Поэтому каждая привязка несёт метод и уровень качества:

  name_explicit_mo        — в наименовании заказчика явно названо МО: «МР X район», «X района»,
                            «ГО г. Y», «г. Y» (Y — город-ГО), «Администрация СП ... МР X»;
  name_district_town      — названо поселение-центр МР из официальной иерархии Росстата
                            (г. Баймак → МР Баймакский и т.п., подстроки таблиц Башкортостанстата);
  name_district_center    — село — административный центр района (список в коде; каждый центр
                            проверяется по согласию с налоговым кодом, несогласованные отключаются);
  msp_registry_address    — адрес (район/город) из реестра МСП ФНС на 10.09.2026 — только для фирм МСП,
                            состояние на дату снимка, не на дату контракта;
  tax_office_hypothesis   — первые 4 цифры КПП (код налогового органа постановки на учёт) → МО по
                            эмпирической таблице, построенной на организациях с явным названием МО;
                            точность оценивается leave-one-out и публикуется. Это слабая гипотеза.
  unresolved / outside_region.
Первые 4 цифры ИНН (код инспекции, выдавшей ИНН) используются только в анализе
чувствительности (``inn_prefix_hypothesis``), как требует аудит (п. 3.8).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

GO_CITIES = {  # ГО: словоформы названия города → МО
    "Уф(?:а|ы|е|ой|у)": "ГО Уфа", "Агидел(?:ь|и|ью)": "ГО Агидель", "Кумертау": "ГО Кумертау",
    "Межгорь(?:е|я|ем|ю)": "ГО Межгорье", "Нефтекамск(?:а|е|ом|у)?": "ГО Нефтекамск",
    "Октябрьск(?:ий|ого|ом|ому)": "ГО Октябрьский", "Салават(?:а|е|ом|у)?": "ГО Салават",
    "Сиба(?:й|я|е|ем|ю)": "ГО Сибай", "Стерлитамак(?:а|е|ом|у)?": "ГО Стерлитамак",
}
# поселения-центры внутри МР — подстроки таблиц Башкортостанстата (EDN/миграция)
DISTRICT_TOWNS = {
    "Баймак": "МР Баймакский", "Белебе": "МР Белебеевский", "Приютово": "МР Белебеевский",
    "Белорецк": "МР Белорецкий", "Бирск": "МР Бирский", "Благовещенск": "МР Благовещенский",
    "Давлеканово": "МР Давлекановский", "Дюртюли": "МР Дюртюлинский", "Ишимба": "МР Ишимбайский",
    "Мелеуз": "МР Мелеузовский", "Туймаз": "МР Туймазинский", "Учал": "МР Учалинский",
    "Янаул": "МР Янаульский", "Чишм": "МР Чишминский",
}
# сёла — центры районов (общеизвестные; проверяются по согласию с налоговым кодом)
DISTRICT_CENTERS = {
    "Аскарово": "МР Абзелиловский", "Раевский": "МР Альшеевский", "Архангельское": "МР Архангельский",
    "Аскино": "МР Аскинский", "Толбазы": "МР Аургазинский", "Бакалы": "МР Бакалинский",
    "Старобалтачево": "МР Балтачевский", "Новобелокатай": "МР Белокатайский", "Бижбуляк": "МР Бижбулякский",
    "Языково": "МР Благоварский", "Буздяк": "МР Буздякский", "Бураево": "МР Бураевский",
    "Старосубхангулово": "МР Бурзянский", "Красноусольский": "МР Гафурийский", "Месягутово": "МР Дуванский",
    "Ермекеево": "МР Ермекеевский", "Исянгулово": "МР Зианчуринский", "Зилаир": "МР Зилаирский",
    "Иглино": "МР Иглинский", "Верхнеяркеево": "МР Илишевский", "Калтасы": "МР Калтасинский",
    "Караидель": "МР Караидельский", "Кармаскалы": "МР Кармаскалинский", "Верхние Киги": "МР Кигинский",
    "Николо-Березовка": "МР Краснокамский", "Мраково": "МР Кугарчинский", "Кушнаренково": "МР Кушнаренковский",
    "Ермолаево": "МР Куюргазинский", "Большеустьикинское": "МР Мечетлинский", "Мишкино": "МР Мишкинский",
    "Киргиз-Мияки": "МР Миякинский", "Красная Горка": "МР Нуримановский", "Малояз": "МР Салаватский",
    "Стерлибашево": "МР Стерлибашевский", "Верхние Татышлы": "МР Татышлинский", "Акъяр": "МР Хайбуллинский",
    "Чекмагуш": "МР Чекмагушевский", "Шаран": "МР Шаранский",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("ё", "е").replace("Ё", "Е")).strip()


def build_patterns(mo_names: list[str]) -> list[tuple[re.Pattern, str, str]]:
    pats = []
    for mo in mo_names:
        kind, word = mo.split(" ", 1)
        if kind == "МР":
            stem = word[:-2]  # Абзелиловск(ий)
            pats.append((re.compile(rf"\b{stem}(?:ий|ого|ому|ом|ая|ой)\s+(?:муниципальн\w*\s+)?район", re.I), mo, "name_explicit_mo"))
            pats.append((re.compile(rf"\bМР\s+{stem}ий\b", re.I), mo, "name_explicit_mo"))
            pats.append((re.compile(rf"\bМуниципальн\w+\s+Район\w*\s+{stem}ий", re.I), mo, "name_explicit_mo"))
    for form, mo in GO_CITIES.items():
        rx = rf"(?:\bг\.\s?|\bгород\w*\s+(?:округ\w*\s+)?(?:город\w*\s+)?|\bГО\s+(?:г\.\s?)?|\bЗАТО\s+(?:г\.\s?)?){form}\b(?!ск)"
        pats.append((re.compile(rx, re.I), mo, "name_explicit_mo"))
    for stem, mo in DISTRICT_TOWNS.items():
        pats.append((re.compile(rf"(?:\bг\.\s?|\bрп\.?\s?|\bгород\w*\s+|\bпос\w*\s+)(?:{stem})\w*", re.I), mo, "name_district_town"))
    for stem, mo in DISTRICT_CENTERS.items():
        pats.append((re.compile(rf"(?:\bс\.\s?|\bсело\w*\s+|\bСела\s+){re.escape(stem)}\w*", re.I), mo, "name_district_center"))
    return pats


RANK = {"name_explicit_mo": 3, "name_district_town": 2, "name_district_center": 1}


def name_evidence(name: str, pats) -> tuple[str | None, str | None, str]:
    """Возвращает (МО, метод, статус). Если найдено несколько разных МО одного (лучшего) уровня — конфликт."""
    s = _norm(name)
    hits = {}
    for rx, mo, method in pats:
        if rx.search(s):
            hits.setdefault(method, set()).add(mo)
    if not hits:
        return None, None, "no_toponym"
    best = max(hits, key=lambda m: RANK[m])
    mos = hits[best]
    if len(mos) > 1:
        # «Администрация СП X сельсовет МР Y район» — может упоминать и город Y; приоритет у явного МР
        return None, best, "conflict:" + "|".join(sorted(mos))
    return next(iter(mos)), best, "ok"


def tax_office_table(df: pd.DataFrame, code_col: str, min_n: int = 5, min_purity: float = 0.8) -> pd.DataFrame:
    """df: организации с известным МО по названию (inn, code, mo). Возвращает code → mo, n, purity, usable."""
    g = df.dropna(subset=[code_col, "mo"]).groupby([code_col, "mo"]).size().rename("n").reset_index()
    tot = g.groupby(code_col).n.transform("sum")
    g["purity"] = g.n / tot
    g["n_code"] = tot
    top = g.sort_values(["n"], ascending=False).drop_duplicates(code_col)
    top["usable"] = (top.n_code >= min_n) & (top.purity >= min_purity)
    return top.rename(columns={"n": "n_top"}).reset_index(drop=True)


def loo_accuracy(df: pd.DataFrame, code_col: str, min_n: int = 5, min_purity: float = 0.8) -> dict:
    """Leave-one-out: для каждой организации с известным МО строим таблицу кода без неё и сверяем."""
    d = df.dropna(subset=[code_col, "mo"])
    cnt = d.groupby([code_col, "mo"]).size()
    tot = d.groupby(code_col).size()
    hit = miss = abstain = 0
    for code, mo in zip(d[code_col], d["mo"]):
        c = cnt.loc[code].copy()
        c[mo] -= 1
        n = tot[code] - 1
        if n < min_n:
            abstain += 1
            continue
        top_mo, top_n = c.idxmax(), c.max()
        if top_n / n < min_purity:
            abstain += 1
            continue
        if top_mo == mo:
            hit += 1
        else:
            miss += 1
    cov = hit + miss
    return dict(code=code_col, evaluated=len(d), assigned=cov, abstained=abstain, correct=hit,
                accuracy=hit / cov if cov else np.nan, coverage=cov / len(d) if len(d) else np.nan)
