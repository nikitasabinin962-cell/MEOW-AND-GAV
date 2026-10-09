"""Идемпотентная сборка базы econtypes v5.

  python -m econtypes5.ingest --research ../econtypes_research_20261009.sqlite --out data/econtypes_v5.sqlite

Входы не изменяются. Повторный запуск на той же базе даёт идентичное содержимое
(INSERT OR REPLACE по естественным ключам; проверка — хеши таблиц до/после второго прохода).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import numpy as np
import pandas as pd

from . import db as DB
from . import geography as GE
from . import rosstat as R

ROOT = Path(__file__).resolve().parents[1]          # econtypes_v5/
PKG = ROOT.parent                                   # MEOW-AND-GAV/
REPRO = PKG / "reproduction"
EXT = ROOT / "external" / "rosstat_drive"
RESEARCH_SHA256 = "9a4758254578d007e536c8520a4b0965aba4433ceeee6ce5c4b2ca306eab1a5e"

OKVED_SECTIONS = [("A", 1, 3), ("B", 5, 9), ("C", 10, 33), ("D", 35, 35), ("E", 36, 39), ("F", 41, 43), ("G", 45, 47),
                  ("H", 49, 53), ("I", 55, 56), ("J", 58, 63), ("K", 64, 66), ("L", 68, 68), ("M", 69, 75), ("N", 77, 82),
                  ("O", 84, 84), ("P", 85, 85), ("Q", 86, 88), ("R", 90, 93), ("S", 94, 96), ("T", 97, 98), ("U", 99, 99)]


def okved_section(code: str | None) -> str | None:
    if not code:
        return None
    m = re.match(r"^(\d{2})", str(code))
    if not m:
        return None
    d = int(m.group(1))
    for s, lo, hi in OKVED_SECTIONS:
        if lo <= d <= hi:
            return s
    return None


def inn_valid(s) -> bool:
    if s is None or not str(s).isdigit() or len(str(s)) not in (10, 12):
        return False
    ns = list(map(int, str(s)))
    ck = lambda co: sum(a * b for a, b in zip(ns, co)) % 11 % 10
    if len(ns) == 10:
        return ck([2, 4, 10, 3, 5, 9, 4, 6, 8]) == ns[9]
    return ck([7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == ns[10] and ck([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == ns[11]


def rub_to_kopecks(v) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    return int((Decimal(str(v).replace(" ", "").replace(",", ".")) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ L0: источники
def register_sources(con, research: Path) -> None:
    rs = sqlite3.connect(f"file:{research}?mode=ro", uri=True)
    src = pd.read_sql("SELECT * FROM sources", rs)
    for r in src.itertuples():
        con.execute("""INSERT OR REPLACE INTO source_registry(source_id,title,relative_path,storage_location,url,sha256,size_bytes,
            retrieved_at,observation_period,territory,role,status,limitations,license_terms,completeness)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r.source_id, r.original_name, "reproduction/" + r.relative_path, "git:MEOW-AND-GAV/reproduction (копия входа)",
                     r.source_url, r.sha256, r.size_bytes, "2026-10-09 (handoff package)", r.observation_period,
                     "Республика Башкортостан" if "national" not in (r.role or "") else "РФ (отбор поставщиков)", r.role,
                     "imported_via_research_db", r.limitations,
                     "Росстат: ссылка на источник обязательна" if r.source_id.startswith("rosstat") else
                     ("ФНС открытые данные" if r.source_id.startswith("fns") else None),
                     "full_file"))
    con.execute("""INSERT OR REPLACE INTO source_registry(source_id,title,relative_path,storage_location,sha256,size_bytes,retrieved_at,
        observation_period,role,status,limitations) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                ("research_db_20261009", "econtypes_research_20261009.sqlite", "econtypes_research_20261009.sqlite",
                 "git LFS MEOW-AND-GAV", DB.sha256_file(research), research.stat().st_size, now(), "mixed (см. исходные source_id)",
                 "seed_database", "verified_sha256", "Используется только как источник нормализации; сам не изменяется."))
    # Росстат с Google Drive пользователя: исходные байты и SHA-256
    meta = {
        "Estestvennoe-dvizhenie-naseleniya-municipalnyh-obrazovanij-RB-yanvar-dekabr-2024.pdf":
            ("rosstat_edn_mo_2024", "2023-01/2024-12 (годовые итоги, оперативные данные)", "persons; per 1000", "МО×год", None),
        "Dinamika-koefficientov-migracionnogo-prirosta-(ubyli)-naseleniya-municipalnyh-obrazovanij-Respubliki-Bashkortostan.pdf":
            ("rosstat_migr_mo_2018_2023", "2018–2023", "per 10000", "МО×год", "по МО 2018–2021 без учёта ВПН-2020 (сноска таблицы)"),
        "Koefficient-migracionnogo-prirosta(ubyli)-naseleniya-Respubliki-Bashkortostan-12-2024_1044551.pdf":
            ("rosstat_migr_mo_2024", "2023-01/2024-12", "per 10000", "МО×год", None),
        "8. Население муниципальных районов и городских округов РБ по основному источнику средств к существованию.doc":
            ("vpn2020_livelihood_mo", "2021-10-01 (критический момент ВПН-2020)", "persons", "МО", "значения взяты из транскрипции census2020_main_livelihood_mo.md"),
        "Население по возрастным группам и полу по  муниципальным районам  и городским округам РБ.xlsx":
            ("vpn2020_age_mo", "2021-10-01", "persons", "МО×5-летняя группа", None),
        "Население по возрасту, полу и уровню образования по  муниципальным районам  и городским округам РБ .xlsx":
            ("vpn2020_education_mo", "2021-10-01", "persons (6 лет и старше)", "МО", None),
        "Perechen-pokazatelej-dlya-zagruzki-v-BD-PMO_2025.pdf":
            ("rosstat_bdpmo_perechen_2025", "перечень 2025 (не наблюдения)", None, "справочник показателей", None),
    }
    for line in (EXT / "DRIVE_DOWNLOADS.jsonl").read_text().splitlines():
        d = json.loads(line)
        sid, period, units, grain, lim = meta.get(d["file"], ("drive_" + d["drive_id"], None, None, None, None))
        p = EXT / d["file"]
        assert DB.sha256_file(p) == d["sha256"], f"SHA-256 mismatch {p}"
        con.execute("""INSERT OR REPLACE INTO source_registry(source_id,title,relative_path,storage_location,url,drive_id,sha256,size_bytes,
            retrieved_at,observation_period,publication_date,territory,units,grain,license_terms,completeness,role,status,limitations)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, d["file"], str(p.relative_to(PKG)), "git:MEOW-AND-GAV/econtypes_v5/external + Google Drive пользователя",
                     f"https://drive.google.com/file/d/{d['drive_id']}/view", d["drive_id"], d["sha256"], d["size_bytes"],
                     d["retrieved_at_utc"], period, "не указана в файле (Башкортостанстат); дата загрузки ≠ период наблюдения",
                     "Республика Башкортостан, МО (ЗАТО Межгорье отдельно не публикуется)", units, grain,
                     "Росстат/Башкортостанстат: при опубликовании ссылка обязательна", "full_table", "official_statistics",
                     "downloaded_original_bytes", lim))
    for fn, sid, desc in [("census2020_main_livelihood_mo.md", "vpn2020_livelihood_mo_transcript",
                           "Транскрипция текстового представления Drive исходного .doc (служебные строки удалены)")]:
        p = EXT / fn
        con.execute("""INSERT OR REPLACE INTO source_registry(source_id,title,relative_path,storage_location,sha256,size_bytes,retrieved_at,
            observation_period,role,status,limitations) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, fn, str(p.relative_to(PKG)), "git", DB.sha256_file(p), p.stat().st_size, now(), "2021-10-01",
                     "transcription", "derived_from_original", desc))
    arch = [
        ("archive_features_raw_v4", REPRO / "calculation_source/outputs/tables/features_raw_2023_2024.csv",
         "2023-01/2024-12 агрегат", "Архивные 32 признака v4 (производные; исходные parquet СберИндекса/ЕИС отсутствуют). market_access, wage, emp_* — только отсюда."),
        ("archive_network_edges_v4", REPRO / "calculation_source/outputs/tables/network_edges.csv",
         "2023-01/2024-12", "Рёбра слоёв v4 после kNN; fused — повторно разрежён для показа (310 рёбер), не расчётная W."),
        ("archive_clusters_v4", REPRO / "calculation_source/outputs/tables/clusters_final.csv", "2023-01/2024-12", "Метки v4 (до исправлений)."),
        ("archive_D_json_v4", REPRO / "source/src/data/D.json", "2023-01/2024-12",
         "Блок данных дашборда v4, SHA-1 d849169e…; помесячные траты на жителя 'sp' 63×24, геометрия МО."),
    ]
    for sid, p, period, lim in arch:
        con.execute("""INSERT OR REPLACE INTO source_registry(source_id,title,relative_path,storage_location,sha256,size_bytes,retrieved_at,
            observation_period,role,status,limitations) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, p.name, str(p.relative_to(PKG)), "git", DB.sha256_file(p), p.stat().st_size, "2026-10-09 (handoff package)",
                     period, "archived_results", "archived_derived", lim))


# ------------------------------------------------------------------ L1: МО, население, Росстат
def load_mo(con, research: Path) -> dict[str, int]:
    rs = sqlite3.connect(f"file:{research}?mode=ro", uri=True)
    m = pd.read_sql("SELECT * FROM municipalities ORDER BY mo_id", rs)
    for r in m.itertuples():
        con.execute("INSERT OR REPLACE INTO mo VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r.mo_id, r.name, r.kind, None, "not_available: проверенный ОКТМО не загружен (см. DATA_GAPS)",
                     None if pd.isna(r.territory_id) else int(r.territory_id), r.sber_mapping_status,
                     "2022-01-01", None, "границы 63 МО неизменны в 2022–2025 по составу таблиц Росстата; официальный crosswalk не загружен"))
        con.execute("INSERT OR REPLACE INTO mo_alias VALUES (?,?,?)", (r.name, r.mo_id, "research_db_20261009"))
    return dict(zip(m.name, m.mo_id))


def load_population(con, research: Path) -> None:
    rs = sqlite3.connect(f"file:{research}?mode=ro", uri=True)
    p = pd.read_sql("SELECT * FROM population", rs)
    for r in p.itertuples():
        con.execute("INSERT OR REPLACE INTO fact_mo VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (r.mo_id, "population", r.observation_date, float(r.value), "persons", "observed", r.source_id,
                     None, None, "постоянное население на 1 января"))


def load_rosstat(con, mo_ids: dict[str, int]) -> dict:
    res = {}

    def put(df, sid, status="observed", note=None):
        miss = sorted(set(df.mo) - set(mo_ids))
        if miss:
            raise ValueError(f"{sid}: неизвестные МО {miss}")
        for r in df.itertuples():
            con.execute("INSERT OR REPLACE INTO fact_mo VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (mo_ids[r.mo], r.indicator, str(r.period), float(r.value), r.unit, status, sid, None, None, note))
        return sorted(set(mo_ids) - set(df.mo))

    def ctrl(d: dict, sid, unit):
        for k, v in d.items():
            ind, per = (k.rsplit("_", 1) if "_" in k and k.rsplit("_", 1)[1].isdigit() else (k, "-"))
            con.execute("INSERT OR REPLACE INTO fact_region_control VALUES (?,?,?,?,?)", (ind, per, float(v), unit, sid))

    df, c = R.parse_edn_2024(EXT / "Estestvennoe-dvizhenie-naseleniya-municipalnyh-obrazovanij-RB-yanvar-dekabr-2024.pdf")
    res["edn"] = dict(missing_mo=put(df, "rosstat_edn_mo_2024", note="оперативные данные Башкортостанстата"), rows=len(df))
    ctrl(c, "rosstat_edn_mo_2024", "mixed")
    df, c = R.parse_migr_dynamics(EXT / "Dinamika-koefficientov-migracionnogo-prirosta-(ubyli)-naseleniya-municipalnyh-obrazovanij-Respubliki-Bashkortostan.pdf")
    res["migr_2018_2023"] = dict(missing_mo=put(df, "rosstat_migr_mo_2018_2023"), rows=len(df))
    for k, v in c.items():
        con.execute("INSERT OR REPLACE INTO fact_region_control VALUES (?,?,?,?,?)", ("migr_rate", k, v, "per_10000", "rosstat_migr_mo_2018_2023"))
    df, c = R.parse_migr_2024(EXT / "Koefficient-migracionnogo-prirosta(ubyli)-naseleniya-Respubliki-Bashkortostan-12-2024_1044551.pdf")
    res["migr_2024"] = dict(missing_mo=put(df, "rosstat_migr_mo_2024"), rows=len(df))
    for k, v in c.items():
        con.execute("INSERT OR REPLACE INTO fact_region_control VALUES (?,?,?,?,?)", ("migr_rate", k, v, "per_10000", "rosstat_migr_mo_2024"))
    df, c = R.parse_census_livelihood_md(EXT / "census2020_main_livelihood_mo.md")
    res["livelihood"] = dict(missing_mo=put(df, "vpn2020_livelihood_mo", note="транскрипция; исходный .doc в source_registry"), rows=len(df))
    for k, v in c.items():
        con.execute("INSERT OR REPLACE INTO fact_region_control VALUES (?,?,?,?,?)", (k, "2021-10-01", v, "persons", "vpn2020_livelihood_mo"))
    ag, c = R.parse_census_age(EXT / "Население по возрастным группам и полу по  муниципальным районам  и городским округам РБ.xlsx")
    ag = ag.assign(indicator="census_age_" + ag.group, period="2021-10-01", unit="persons")
    res["age"] = dict(missing_mo=put(ag, "vpn2020_age_mo"), rows=len(ag))
    for k, v in c.items():
        con.execute("INSERT OR REPLACE INTO fact_region_control VALUES (?,?,?,?,?)", ("census_age_" + k, "2021-10-01", v, "persons", "vpn2020_age_mo"))
    ed, c = R.parse_census_education(EXT / "Население по возрасту, полу и уровню образования по  муниципальным районам  и городским округам РБ .xlsx")
    ed = ed.assign(period="2021-10-01", unit="persons")
    res["education"] = dict(missing_mo=put(ed, "vpn2020_education_mo"), rows=len(ed))
    for k, v in c.items():
        con.execute("INSERT OR REPLACE INTO fact_region_control VALUES (?,?,?,?,?)", ("census_edu_" + k, "2021-10-01", float(v), "persons", "vpn2020_education_mo"))
    return res


def load_archive_sber(con, mo_ids: dict[str, int]) -> dict:
    """Архивные производные СберИндекса из D.json v4 (помесячные траты на жителя) и features_raw v4.
    Статус 'archived_derived': исходный consumption.parquet отсутствует; повторный ingest невозможен."""
    D = json.loads((REPRO / "source/src/data/D.json").read_text())
    months = D["months"]
    n_rows = 0
    for nd in D["nodes"]:
        for mth, v in zip(months, nd["sp"]):
            con.execute("INSERT OR REPLACE INTO fact_mo VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (mo_ids[nd["mo"]], "sber_spend_pc_month", mth, None if v is None else float(v), "rub_per_person_per_month",
                         "archived_derived", "archive_D_json_v4", None, None, "безналичные траты на жителя (Все категории), из D.json v4"))
            n_rows += 1
    fr = pd.read_csv(REPRO / "calculation_source/outputs/tables/features_raw_2023_2024.csv")
    for r in fr.itertuples(index=False):
        for col in fr.columns[1:]:
            v = getattr(r, col) if col.isidentifier() else r[fr.columns.get_loc(col)]
            con.execute("INSERT OR REPLACE INTO fact_mo VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (mo_ids[r[0]], "v4_" + col, "2023-01/2024-12", None if pd.isna(v) else float(v), "v4_units",
                         "archived_derived", "archive_features_raw_v4", None, None, "агрегат v4; см. labels.py v4 для единиц"))
    imp = pd.read_csv(REPRO / "calculation_source/outputs/tables/clusters_final.csv")[["mo", "imputed_sber"]]
    return dict(monthly_rows=n_rows, features=len(fr.columns) - 1, imputed_sber=imp[imp.imputed_sber].mo.tolist())


# ------------------------------------------------------------------ контракты и география
def load_contracts(con, research: Path) -> dict:
    rs = sqlite3.connect(f"file:{research}?mode=ro", uri=True)
    c = pd.read_sql("""SELECT canonical_contract_id, law, contract_number, sign_date, amount, amount_cents, currency, financial_status,
        identity_basis, customer_inn, customer_kpp, customer, supplier_inn, supplier_kpp, supplier, subject, status_variants,
        source_file, import_source_id FROM processed_contracts""", rs)
    c["budget_level"] = np.where((c.law == "44-ФЗ") & (c.contract_number.str.len() == 19), c.contract_number.str[0], None)
    c["reestr_inn_agrees"] = np.where(c.contract_number.str.len() == 19, (c.contract_number.str[1:11] == c.customer_inn).astype(int), None)
    # независимая проверка копеек: amount (строка, руб.) → копейки Decimal; сверка с amount_cents
    kop = c.amount.map(rub_to_kopecks)
    mism = int(((kop.notna()) & (c.amount_cents.notna()) & (kop != c.amount_cents)).sum())
    c["customer_inn_valid"] = c.customer_inn.map(inn_valid).astype(int)
    c["supplier_inn_valid"] = c.supplier_inn.map(inn_valid).astype(int)
    rows = c[["canonical_contract_id", "law", "contract_number", "budget_level", "sign_date", "amount_cents", "currency",
              "financial_status", "identity_basis", "customer_inn", "customer_kpp", "customer", "supplier_inn", "supplier_kpp",
              "supplier", "subject", "status_variants", "source_file", "import_source_id", "customer_inn_valid",
              "supplier_inn_valid", "reestr_inn_agrees"]]
    con.executemany("INSERT OR REPLACE INTO contract VALUES (" + ",".join("?" * 22) + ")",
                    [tuple(None if (isinstance(v, float) and np.isnan(v)) else (int(v) if isinstance(v, (np.integer,)) else v) for v in r)
                     for r in rows.itertuples(index=False)])
    return dict(rows=len(c), kopeck_mismatch=mism)


def build_geography(con, mo_ids: dict[str, int], research: Path) -> dict:
    mos = sorted(mo_ids, key=lambda m: mo_ids[m])
    pats = GE.build_patterns(mos)
    cu = pd.read_sql("""SELECT customer_inn inn, customer_kpp kpp, MIN(customer_name) name, COUNT(*) n
                        FROM contract WHERE customer_inn IS NOT NULL GROUP BY customer_inn, customer_kpp""", con)
    ev = cu.name.map(lambda s: GE.name_evidence(s, pats))
    cu["mo"], cu["method"], cu["st"] = [e[0] for e in ev], [e[1] for e in ev], [e[2] for e in ev]
    cu["kpp4"], cu["inn4"] = cu.kpp.str[:4], cu.inn.str[:4]
    named = cu[cu.method == "name_explicit_mo"]
    tab = GE.tax_office_table(named, "kpp4")
    loo_kpp = GE.loo_accuracy(named, "kpp4")
    loo_inn = GE.loo_accuracy(named, "inn4")
    for r in tab.itertuples():
        con.execute("INSERT OR REPLACE INTO tax_office_map VALUES (?,?,?,?,?,?)",
                    (r.kpp4, mo_ids[r.mo], int(r.n_code), float(r.purity), int(r.usable), "customers with explicit MO name"))
    kmap = tab[tab.usable].set_index("kpp4").mo
    itab = GE.tax_office_table(named, "inn4")
    imap = itab[itab.usable].set_index("inn4").mo
    cu["kmo"] = cu.kpp4.map(kmap)
    cu["imo"] = cu.inn4.map(imap)
    # проверка сёл-центров: метод отключается для центра, если согласие с кодом < 0.9
    bad_centers = []
    for mo, g in cu[cu.method == "name_district_center"].groupby("mo"):
        g = g[g.kmo.notna()]
        if len(g) >= 3 and (g.mo == g.kmo).mean() < 0.9:
            bad_centers.append(mo)
    for r in cu.itertuples():
        kpp = r.kpp if isinstance(r.kpp, str) else ""
        if r.mo is not None and not (r.method == "name_district_center" and r.mo in bad_centers):
            con.execute("INSERT OR REPLACE INTO org_geo_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                        (r.inn, kpp, "customer", mo_ids[r.mo], r.method, {"name_explicit_mo": .99, "name_district_town": .97, "name_district_center": .95}[r.method],
                         r.name[:200], "name at contract record", "research_db_20261009"))
        if isinstance(r.kmo, str):
            con.execute("INSERT OR REPLACE INTO org_geo_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                        (r.inn, kpp, "customer", mo_ids[r.kmo], "tax_office_hypothesis", round(loo_kpp["accuracy"], 4),
                         f"КПП {r.kpp4}", "КПП в записи контракта", "research_db_20261009"))
        if isinstance(r.imo, str):
            con.execute("INSERT OR REPLACE INTO org_geo_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                        (r.inn, kpp, "customer", mo_ids[r.imo], "inn_prefix_hypothesis", round(loo_inn["accuracy"], 4),
                         f"ИНН {r.inn4}", "код инспекции, выдавшей ИНН (слабая гипотеза; только чувствительность)", "research_db_20261009"))
        name_ok = r.mo is not None and not (r.method == "name_district_center" and r.mo in bad_centers)
        if name_ok:
            mo, q = r.mo, ("name_and_tax_office_agree" if r.kmo == r.mo else ("name_tax_office_conflict" if isinstance(r.kmo, str) else "name_only"))
        elif isinstance(r.kmo, str):
            mo, q = r.kmo, "tax_office_hypothesis"
        elif isinstance(r.kpp, str) and not r.kpp.startswith("02"):
            mo, q = None, "outside_region"
        else:
            mo, q = None, "unresolved"
        con.execute("INSERT OR REPLACE INTO org_geo_resolved VALUES (?,?,?,?,?,?,?)",
                    (r.inn, kpp, "customer", None if mo is None else mo_ids[mo], (r.kpp or "")[:2] or None, q,
                     None if not (name_ok and isinstance(r.kmo, str)) else int(r.kmo == r.mo)))
    # ---- поставщики: регион по КПП (ЮЛ) / ИНН (ИП, слабее); МО — реестр МСП (адрес, 2026) или код налогового органа
    rs = sqlite3.connect(f"file:{research}?mode=ro", uri=True)
    msp = pd.read_sql("""SELECT r.inn, c.mo_id_candidate, c.status FROM msp_snapshot_rows r JOIN msp_municipality_candidates c USING(row_id)""", rs)
    msp = msp[msp.status.isin(["district_text_candidate", "city_text_candidate"])].dropna(subset=["mo_id_candidate"]).drop_duplicates("inn")
    mspm = msp.set_index("inn").mo_id_candidate.astype(int)
    su = pd.read_sql("""SELECT supplier_inn inn, supplier_kpp kpp, COUNT(*) n FROM contract WHERE supplier_inn IS NOT NULL
                        GROUP BY supplier_inn, supplier_kpp""", con)
    inv = {v: k for k, v in mo_ids.items()}
    stats = {}
    for r in su.itertuples():
        kpp = r.kpp if isinstance(r.kpp, str) else ""
        reg_kpp = kpp[:2] if kpp else None
        reg = reg_kpp or (str(r.inn)[:2] if len(str(r.inn)) == 12 else None)
        reg_method = "kpp_region" if reg_kpp else ("inn_region_weak" if reg else None)
        mo_id, q = None, None
        if r.inn in mspm.index:
            mo_id, q = int(mspm[r.inn]), "msp_registry_address_2026"
            con.execute("INSERT OR REPLACE INTO org_geo_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                        (r.inn, kpp, "supplier", mo_id, "msp_registry_address", None, "реестр МСП, район/город", "2026-09-10", "fns_msp_20260910"))
        k4 = kpp[:4]
        if k4 in kmap.index:
            tmo = mo_ids[kmap[k4]]
            con.execute("INSERT OR REPLACE INTO org_geo_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                        (r.inn, kpp, "supplier", tmo, "tax_office_hypothesis", round(loo_kpp["accuracy"], 4), f"КПП {k4}", "КПП в записи контракта", "research_db_20261009"))
            if mo_id is None:
                mo_id, q = tmo, "tax_office_hypothesis"
            elif mo_id != tmo:
                q = "msp_address_vs_tax_office_conflict"
        if mo_id is None:
            q = "outside_region" if (reg and reg != "02") else ("region_02_mo_unresolved" if reg == "02" else "unresolved")
        con.execute("INSERT OR REPLACE INTO org_geo_resolved VALUES (?,?,?,?,?,?,?)", (r.inn, kpp, "supplier", mo_id, reg, q, None))
        stats[q] = stats.get(q, 0) + 1
    return dict(customers=len(cu), named_explicit=len(named), loo_kpp=loo_kpp, loo_inn=loo_inn,
                disabled_district_centers=bad_centers, name_conflicts=int(cu.st.str.startswith("conflict").sum()),
                customer_quality=pd.read_sql("SELECT quality, COUNT(*) n FROM org_geo_resolved WHERE role='customer' GROUP BY 1", con).set_index("quality").n.to_dict(),
                supplier_quality=stats, tax_codes_usable=int(tab.usable.sum()), tax_codes_total=len(tab))


def load_msp(con, research: Path) -> dict:
    rs = sqlite3.connect(f"file:{research}?mode=ro", uri=True)
    m = pd.read_sql("""SELECT r.inn, r.snapshot_date, r.category_code, r.okved_main, r.region_code, r.headcount_raw,
                       c.mo_id_candidate, c.status FROM msp_snapshot_rows r JOIN msp_municipality_candidates c USING(row_id)""", rs)
    m["okved_section"] = m.okved_main.map(okved_section)
    m["headcount"] = pd.to_numeric(m.headcount_raw.replace("", np.nan), errors="coerce")
    con.executemany("INSERT OR REPLACE INTO msp_firm VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [(r.inn, r.snapshot_date, r.category_code, r.okved_main, r.okved_section, r.region_code,
                      None if pd.isna(r.mo_id_candidate) else int(r.mo_id_candidate), r.status,
                      None if pd.isna(r.headcount) else int(r.headcount), "fns_msp_20260910") for r in m.itertuples()])
    idx = pd.read_sql("SELECT inn, snapshot_date, MIN(region_code) region_code, MIN(category_raw) category_raw FROM msp_supplier_index_snapshot GROUP BY inn, snapshot_date", rs)
    con.executemany("INSERT OR REPLACE INTO msp_index_firm VALUES (?,?,?,?,?)",
                    [(r.inn, r.snapshot_date, r.region_code, r.category_raw, "fns_msp_relevant_suppliers_20260910") for r in idx.itertuples()])
    return dict(firms=len(m), with_candidate=int(m.mo_id_candidate.notna().sum()), no_section=int(m.okved_section.isna().sum()),
                missing_headcount=int(m.headcount.isna().sum()), index_firms=len(idx))


# ------------------------------------------------------------------ проверки
def independent_contract_recount(con) -> dict:
    """Независимый пересчёт по исходным 8 CSV (DuckDB, без участия research DB) и сравнение с v5."""
    import duckdb
    files = sorted((REPRO / "materials").glob("contracts_unique_eis_atmo_00[1-8].csv"))
    q = duckdb.sql(f"""SELECT COUNT(*) n, COUNT(DISTINCT canonical_contract_id) ids,
            SUM(CASE WHEN currency='RUB' AND financial_status='known' THEN CAST(amount AS DECIMAL(20,2)) END) rub_known,
            COUNT(DISTINCT supplier_inn) supp_inn, SUM(CASE WHEN supplier_inn IS NULL OR supplier_inn='' THEN 1 ELSE 0 END) no_supp_inn,
            COUNT(DISTINCT customer_inn) cust_inn
        FROM read_csv({[str(f) for f in files]}, all_varchar=true, header=true)""").fetchone()
    v5 = con.execute("""SELECT COUNT(*), COUNT(DISTINCT canonical_contract_id),
            SUM(CASE WHEN currency='RUB' AND financial_status='known' THEN amount_kopecks END),
            COUNT(DISTINCT supplier_inn), SUM(supplier_inn IS NULL), COUNT(DISTINCT customer_inn) FROM contract""").fetchone()
    msp_join = con.execute("""SELECT SUM(c.supplier_inn IS NULL), SUM(c.supplier_inn IS NOT NULL AND m.inn IS NOT NULL),
            SUM(c.supplier_inn IS NOT NULL AND m.inn IS NULL) FROM contract c LEFT JOIN msp_index_firm m ON m.inn=c.supplier_inn""").fetchone()
    return dict(files=len(files), csv=dict(rows=q[0], ids=q[1], rub_known=str(q[2]), distinct_supplier_inn=q[3], missing_supplier_inn=q[4], distinct_customer_inn=q[5]),
                v5=dict(rows=v5[0], ids=v5[1], rub_known_kopecks=v5[2], distinct_supplier_inn=v5[3], missing_supplier_inn=v5[4], distinct_customer_inn=v5[5]),
                msp_join=dict(supplier_inn_unavailable=msp_join[0], found_in_snapshot=msp_join[1], not_found_in_snapshot=msp_join[2]))


def run_checks(con, info: dict) -> dict:
    out = {}
    # население: сумма 63 МО = республиканский контроль PDF (перенесено из research DB) — пересчёт здесь
    pop = pd.read_sql("SELECT period, SUM(value) s, COUNT(*) n FROM fact_mo WHERE indicator='population' GROUP BY period", con)
    exp = {"2022-01-01": 4091621, "2023-01-01": 4077600, "2024-01-01": 4064361, "2025-01-01": 4042377}
    ok = all(int(r.s) == exp[r.period] and r.n == 63 for r in pop.itertuples())
    DB.check(con, "population_sum_equals_region_control", ok, pop.to_dict("records")); out["population"] = ok
    # ЕДН: Σ62 МО и остаток (Межгорье не публикуется отдельно)
    e = pd.read_sql("SELECT indicator, period, SUM(value) s, COUNT(*) n FROM fact_mo WHERE source_id='rosstat_edn_mo_2024' AND unit='persons' GROUP BY 1,2", con)
    ctl = pd.read_sql("SELECT indicator, period, value FROM fact_region_control WHERE source_id='rosstat_edn_mo_2024'", con)
    e = e.merge(ctl, on=["indicator", "period"], how="left")
    e["residual_mezhgorye"] = e.value - e.s
    nat_ok = bool(((e.indicator.isin(["births", "deaths", "natinc"])) & (e.n == 62)).sum() == 6)
    # внутренняя тождественность: естественный прирост = рождения − смерти по каждому МО
    f = pd.read_sql("SELECT mo_id, indicator, period, value FROM fact_mo WHERE source_id='rosstat_edn_mo_2024' AND unit='persons'", con)
    pv = f.pivot_table(index=["mo_id", "period"], columns="indicator", values="value")
    ident = float((pv.births - pv.deaths - pv.natinc).abs().max())
    DB.check(con, "edn_identity_births_minus_deaths", ident == 0 and nat_ok, dict(max_abs_violation=ident, residual_vs_region=e.to_dict("records")))
    out["edn_identity"] = ident
    # миграция: 2023 в двух публикациях совпадает до округления
    m = pd.read_sql("""SELECT a.mo_id, a.value v1, b.value v2 FROM fact_mo a JOIN fact_mo b ON a.mo_id=b.mo_id AND a.indicator='migr_rate' AND b.indicator='migr_rate'
                       AND a.period='2023' AND b.period='2023' AND a.source_id='rosstat_migr_mo_2018_2023' AND b.source_id='rosstat_migr_mo_2024'""", con)
    dmax = float((m.v1 - m.v2).abs().max())
    DB.check(con, "migration_2023_consistent_between_publications", dmax <= 0.05 + 1e-9, dict(max_abs_diff=dmax, n=len(m), note="разные округления: 2 и 1 знак"))
    # перепись: возрастные группы в сумме = итог по каждому МО; Σ62 и остаток
    a = pd.read_sql("SELECT mo_id, indicator, value FROM fact_mo WHERE source_id='vpn2020_age_mo'", con)
    tot = a[a.indicator == "census_age_total"].set_index("mo_id").value
    grp = a[a.indicator != "census_age_total"].groupby("mo_id").value.sum()
    agemax = float((tot - grp).abs().max())
    rc = con.execute("SELECT value FROM fact_region_control WHERE indicator='census_age_total'").fetchone()[0]
    DB.check(con, "census_age_groups_sum_to_total", agemax == 0, dict(max_abs=agemax, region_total=rc, sum_62=float(tot.sum()), residual_mezhgorye=rc - float(tot.sum())))
    # контракты: независимый пересчёт
    rc = independent_contract_recount(con)
    okc = (rc["csv"]["rows"] == rc["v5"]["rows"] == 359615 and rc["csv"]["ids"] == rc["v5"]["ids"]
           and int(Decimal(rc["csv"]["rub_known"]) * 100) == rc["v5"]["rub_known_kopecks"]
           and rc["msp_join"] == dict(supplier_inn_unavailable=82063, found_in_snapshot=173892, not_found_in_snapshot=103660))
    DB.check(con, "contracts_independent_recount_csv_vs_v5", okc, rc); out["contracts"] = rc
    DB.check(con, "contracts_kopecks_reconcile_decimal", info["contracts"]["kopeck_mismatch"] == 0, info["contracts"])
    inv = con.execute("SELECT SUM(customer_inn_valid=0 AND customer_inn IS NOT NULL), SUM(supplier_inn_valid=0 AND supplier_inn IS NOT NULL) FROM contract").fetchone()
    DB.check(con, "contract_inn_checksums", "INFO", dict(invalid_customer_inn=inv[0], invalid_supplier_inn=inv[1]))
    agree = con.execute("SELECT SUM(reestr_inn_agrees=1), SUM(reestr_inn_agrees=0) FROM contract WHERE reestr_inn_agrees IS NOT NULL").fetchone()
    DB.check(con, "reestr_number_embeds_customer_inn", "INFO", dict(agree=agree[0], disagree=agree[1],
             note="44-ФЗ: 19-значный реестровый номер = уровень бюджета (1 цифра) + ИНН заказчика (10) + год + №; расхождения оставлены как есть"))
    DB.check(con, "customer_geography_loo_accuracy", "INFO", info["geography"])
    idn = con.execute("SELECT identity_basis, COUNT(*) FROM contract GROUP BY 1").fetchall()
    conf = dict(idn)
    DB.check(con, "identity_basis_reconcile_upstream_357156_2459", (sum(v for k, v in conf.items() if k != "exact_representation_only") == 357156
                                                                  and conf.get("exact_representation_only") == 2459), conf)
    return out


def build(research: Path, out: Path) -> dict:
    t0 = time.time()
    if DB.sha256_file(research) != RESEARCH_SHA256:
        raise SystemExit("research DB SHA-256 не совпадает с PACKAGE_CHECKS.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    con = DB.connect(out)
    DB.migrate(con)
    register_sources(con, research)
    mo_ids = load_mo(con, research)
    load_population(con, research)
    info = dict(rosstat=load_rosstat(con, mo_ids), sber=load_archive_sber(con, mo_ids))
    info["contracts"] = load_contracts(con, research)
    con.commit()
    info["msp"] = load_msp(con, research)
    con.commit()
    info["geography"] = build_geography(con, mo_ids, research)
    con.commit()
    info["checks"] = run_checks(con, info)
    con.commit()
    info["integrity"] = DB.integrity(con)
    info["seconds"] = round(time.time() - t0, 1)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--research", default=str(PKG / "econtypes_research_20261009.sqlite"))
    ap.add_argument("--out", default=str(ROOT / "data" / "econtypes_v5.sqlite"))
    a = ap.parse_args()
    info = build(Path(a.research), Path(a.out))
    print(json.dumps(info, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
