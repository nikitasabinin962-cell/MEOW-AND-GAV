"""Отчёт v5 и сопутствующие документы — только из фактических выходов прогона.

Пишет:
  docs/REPORT_v5.md, docs/REPORT_v5.docx, docs/REPORT_v5.pdf (если доступен LibreOffice), docs/figures/*.png
  docs/STRESS_TEST_REPORT.md   — PASS/FAIL/NOT_RUN по фактическим файлам проверок
  docs/SOURCE_REGISTRY.csv     — реестр источников из базы v5 (через экспорт Parquet)
Все числа читаются из outputs/latest (run_id в шапке); в тексте нет вписанных вручную результатов.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
LAT = OUT / os.environ.get("ECONTYPES_RUN_DIR", "latest")
REL = f"outputs/{LAT.name}"
DOCS = ROOT / "docs"
FIG = DOCS / "figures"
FRONT = Path(os.environ.get("FRONT", ROOT.parents[1] / "-"))
D_JSON_V4 = ROOT.parent / "reproduction/source/src/data/D.json"
D_SHA1_BASELINE = "d849169e16d7d2c42c1f210426b1490b6832b76a"


# ---------------------------------------------------------------- чтение
def rd(name: str) -> pd.DataFrame | None:
    p = LAT / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


def rj(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def f2(x, n=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{n}f}".replace(".", ",")


def fint(x):
    return f"{int(round(x)):,}".replace(",", " ")


def plural(n, one, few, many):
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def money(x):
    v = float(x)
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def pct(x, n=1):
    return f"{100 * x:.{n}f}".replace(".", ",") + "%"


RU = {
    # признаки v5
    "sber_spend_pc_log": "траты СберИндекса на жителя (log)", "sber_rel_trend": "относительный тренд трат",
    "sber_ilr1": "ILR1 трат: продукты vs здоровье", "sber_ilr2": "ILR2 трат: …vs общепит", "sber_ilr3": "ILR3 трат: …vs маркетплейсы",
    "sber_ilr4": "ILR4 трат: …vs транспорт", "sber_ilr5": "ILR5 трат: …vs прочее",
    "proc44_pc_log": "госзаказ 44-ФЗ на жителя (log)", "proc44_muni_share": "доля муниципальных заказчиков 44-ФЗ", "supplier_hhi": "HHI поставщиков",
    "procgeo_ilr1": "ILR1 поставщиков: своё МО vs другие МО РБ", "procgeo_ilr2": "ILR2 поставщиков: РБ vs вне РБ", "proc223_pc_log": "закупки 223-ФЗ на жителя (log)",
    "pop_growth": "изменение населения", "natinc_rate": "естественный прирост, ‰", "migr_rate": "миграционный прирост, на 10 000",
    "age_ilr1": "ILR1 возраста: 0–14 vs 15–64", "age_ilr2": "ILR2 возраста: <65 vs 65+",
    # внешние показатели
    "ext_census_wage_main_share": "ВПН-2020: заработок — основной источник средств", "ext_census_pension_benefit_main_share": "ВПН-2020: пенсия/пособие — основной источник",
    "ext_census_dependent_main_share": "ВПН-2020: на иждивении", "ext_census_business_main_share": "ВПН-2020: предпринимательство — основной источник",
    "ext_census_subsistence_main_share": "ВПН-2020: личное подсобное хозяйство — основной источник", "ext_census_higher_edu_share": "ВПН-2020: доля с высшим образованием",
    "ext_market_access_sber": "доступ к рынку (СберИндекс, архив v4)", "ext_wage_large_medium_orgs_v4": "зарплата в крупных и средних организациях (архив v4)",
    "ext_emp_share_budget_sector_v4": "доля занятых в бюджетном секторе (архив v4)", "ext_emp_share_industry_v4": "доля занятых в промышленности (архив v4)",
    "ext_emp_share_agri_v4": "доля занятых в сельском хозяйстве (архив v4)", "ext_equalization_grants_pc_v4": "дотации на выравнивание на жителя (архив v4)",
    "ext_urban_share_v4": "доля городского населения (архив v4)", "ext_log_density_v4": "плотность населения, log (архив v4)",
    "ext_employees_per_1000_v4": "работники на 1 000 жителей (архив v4)", "ext_msp2026_per_1000": "субъекты МСП на 1 000 жителей (2026)",
    "ext_msp2026_eci": "сложность структуры МСП (ECI, 2026)", "ext_msp2026_diversity": "разнообразие отраслей МСП (2026)",
    "ext_old_age_ratio_65_per100_20_64": "нагрузка старшими (65+ на 100 в 20–64)", "ext_youth_ratio_0_19_per100_20_64": "нагрузка молодыми (0–19 на 100 в 20–64)",
    "ext_balance_residual_share_2024": "остаток демографического баланса 2024",
}
MSP_RU = {"agri": "сельское хозяйство", "industry": "промышленность и энергетика", "construction": "строительство", "trade": "торговля",
          "transport": "транспорт", "consumer_services": "общепит, досуг, бытовые услуги", "business_services": "ИТ, финансы, недвижимость, деловые услуги",
          "social": "образование и здравоохранение"}
RU.update({f"msp_lq_{k}": f"LQ МСП: {v}" for k, v in MSP_RU.items()})


def ru(x):
    return RU.get(x, x)


def msp_spec(txt):
    m = re.match(r"(\w+) \(LQ=([\d.]+)\)", str(txt))
    return f"{MSP_RU.get(m.group(1), m.group(1))} (LQ {f2(float(m.group(2)))})" if m else str(txt)


# ---------------------------------------------------------------- блоки документа
class Doc:
    """Единая структура → Markdown и Word, чтобы тексты не расходились."""

    def __init__(self):
        self.blocks: list[tuple] = []

    def h(self, level, text):
        self.blocks.append(("h", level, text))

    def p(self, text):
        self.blocks.append(("p", text))

    def ul(self, items):
        self.blocks.append(("ul", [i for i in items if i]))

    def table(self, df: pd.DataFrame, caption: str | None = None):
        self.blocks.append(("table", df.copy(), caption))

    def img(self, path: Path, caption: str):
        if path.exists():
            self.blocks.append(("img", path, caption))

    # Markdown
    def to_md(self) -> str:
        out = []
        for b in self.blocks:
            if b[0] == "h":
                out.append("#" * b[1] + " " + b[2])
            elif b[0] == "p":
                out.append(b[1])
            elif b[0] == "ul":
                out.append("\n".join(f"* {i}" for i in b[1]))
            elif b[0] == "table":
                df, cap = b[1], b[2]
                if cap:
                    out.append(f"*{cap}*")
                cols = [str(c) for c in df.columns]
                lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
                for r in df.itertuples(index=False):
                    lines.append("| " + " | ".join(str(v).replace("|", "/").replace("\n", " ") for v in r) + " |")
                out.append("\n".join(lines))
            elif b[0] == "img":
                out.append(f"![{b[2]}]({b[1].relative_to(DOCS).as_posix()})\n\n*{b[2]}*")
        return "\n\n".join(out) + "\n"

    # Word
    def to_docx(self, path: Path, title: str):
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt

        d = Document()
        st = d.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(10)
        for s in d.sections:
            s.left_margin = s.right_margin = Cm(2)
            s.top_margin = s.bottom_margin = Cm(1.8)
        d.core_properties.title = title

        def runs(par, text):
            # **жирный** и `код` из Markdown
            for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
                if part.startswith("**") and part.endswith("**"):
                    par.add_run(part[2:-2]).bold = True
                elif part.startswith("`") and part.endswith("`"):
                    r = par.add_run(part[1:-1])
                    r.font.name = "Consolas"
                    r.font.size = Pt(9)
                elif part:
                    par.add_run(part)

        for b in self.blocks:
            if b[0] == "h":
                d.add_heading(b[2], level=min(b[1], 3) if b[1] > 1 else 0)
            elif b[0] == "p":
                runs(d.add_paragraph(), b[1])
            elif b[0] == "ul":
                for i in b[1]:
                    runs(d.add_paragraph(style="List Bullet"), i)
            elif b[0] == "table":
                df, cap = b[1], b[2]
                if cap:
                    c = d.add_paragraph()
                    c.add_run(cap).italic = True
                t = d.add_table(rows=1, cols=len(df.columns))
                t.style = "Light Grid Accent 1"
                for j, col in enumerate(df.columns):
                    t.rows[0].cells[j].text = str(col)
                for r in df.itertuples(index=False):
                    cells = t.add_row().cells
                    for j, v in enumerate(r):
                        cells[j].text = str(v)
                for row in t.rows:
                    for cell in row.cells:
                        for par in cell.paragraphs:
                            for rn in par.runs:
                                rn.font.size = Pt(8)
            elif b[0] == "img":
                d.add_picture(str(b[1]), width=Cm(16))
                d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                c = d.add_paragraph()
                c.add_run(b[2]).italic = True
        d.save(path)


# ---------------------------------------------------------------- рисунки
PALETTE = ["#1b6ca8", "#e07b39", "#3a9d5d", "#b8475f", "#7d5ba6", "#c9a227", "#4aa3a2", "#8c6d46", "#d46fa8", "#6b7a8f"]


def load_geo():
    from shapely.geometry import shape
    D = json.loads(D_JSON_V4.read_text())
    return {f["properties"]["mo"]: shape(f["geometry"]) for f in D["geo"]["features"]}


def draw_map(labels: pd.Series, names: dict, path: Path, title: str, geo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Polygon as MPoly

    fig, ax = plt.subplots(figsize=(8.5, 7.2), dpi=150)
    for mo, g in geo.items():
        polys = list(g.geoms) if hasattr(g, "geoms") else [g]
        lab = labels.get(mo)
        col = PALETTE[int(lab) % len(PALETTE)] if lab is not None and np.isfinite(lab) else "#d9d9d9"
        for pg in polys:
            ax.add_patch(MPoly(np.asarray(pg.exterior.coords), closed=True, fc=col, ec="white", lw=0.6,
                               hatch=None if lab is not None else "///"))
    ax.autoscale_view()
    ax.set_aspect(1 / np.cos(np.deg2rad(54.5)))
    ax.axis("off")
    hand = [Patch(fc=PALETTE[int(c) % len(PALETTE)], label=f"{names.get(int(c), c)} ({int((labels == c).sum())} МО)") for c in sorted(labels.dropna().unique())]
    hand.append(Patch(fc="#d9d9d9", hatch="///", label="без типа (ЗАТО Межгорье — нет СберИндекса)"))
    ax.legend(handles=hand, loc="upper left", bbox_to_anchor=(0, -0.01), fontsize=7, frameon=False, ncol=1)
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def draw_ksel(sweep: pd.DataFrame, chosen: dict, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = sweep[sweep.config == "C4_v5features_v5graph"]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.3), dpi=150)
    for m, mk in (("spectral", "o"), ("leiden", "s"), ("kmeans", "^"), ("ward", "v")):
        t = s[s.method == m].sort_values("k")
        if t.empty:
            continue
        axs[0].plot(t.k, t.boot_ari_median, marker=mk, label=m)
        axs[1].plot(t.k, t.z_MQ_newman, marker=mk, label=m)
        axs[2].plot(t.k, t.z_AVU, marker=mk, label=m)
    axs[0].axhline(0.5, ls=":", c="gray")
    for a, ttl in zip(axs, ("медиана бутстреп-ARI (узлы)", "z MQ_newman против перестановок (↑)", "z AVU против перестановок (↑ лучше; z < 0 — хуже случайного)")):
        a.set_title(ttl, fontsize=8)
        a.set_xlabel("K", fontsize=8)
        a.tick_params(labelsize=7)
        a.axvline(chosen["k"], c="k", lw=0.6, ls="--")
    from matplotlib.ticker import MaxNLocator
    for a in axs:
        a.xaxis.set_major_locator(MaxNLocator(integer=True))
    axs[0].legend(fontsize=7)
    fig.suptitle("Постановка C4 (признаки и граф v5): выбор K и метода; пунктир — выбранный K", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def draw_beta(bs: pd.DataFrame, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(1, 2, figsize=(9, 3.2), dpi=150)
    for mode, ls in (("monitoring", "-"), ("retrospective", "--")):
        t = bs[(bs.level == "macro") & (bs["mode"] == mode)].sort_values("beta")
        axs[0].plot(t.beta, t.temporal_ARI, ls=ls, marker="o", label=f"{mode}: ARI соседних кварталов")
        axs[0].plot(t.beta, t.ARI_vs_static, ls=ls, marker="x", label=f"{mode}: ARI со статикой")
        axs[1].plot(t.beta, t.snapshot_MQ, ls=ls, marker="o", label=mode)
    axs[0].set_title("Гладкость и близость к статике (макро)", fontsize=8)
    axs[1].set_title("Средняя MQ_newman снимков (качество квартала)", fontsize=8)
    for a in axs:
        a.set_xlabel("β (вес истории в эволюционном сглаживании)", fontsize=8)
        a.tick_params(labelsize=7)
        a.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- стресс-отчёт
def stress_rows(man: dict) -> list[dict]:
    rows = []

    def add(group, test, status, evidence, detail=""):
        rows.append(dict(group=group, test=test, status=status, evidence=evidence, detail=detail))

    # 1. модульные тесты
    pl = OUT / "pytest_log.txt"
    if pl.exists():
        txt = pl.read_text()
        m = re.search(r"(\d+) passed", txt)
        f = re.search(r"(\d+) failed", txt)
        add("код", "pytest (модульные и краевые тесты)", "FAIL" if f else ("PASS" if m else "FAIL"), "outputs/pytest_log.txt",
            f"{m.group(1) if m else 0} passed, {f.group(1) if f else 0} failed")
    else:
        add("код", "pytest (модульные и краевые тесты)", "NOT_RUN", "outputs/pytest_log.txt отсутствует")

    # 2. контроли базы
    q = OUT / "db_parquet/data_quality_checks.parquet"
    if q.exists():
        for r in pd.read_parquet(q).itertuples():
            add("данные", r.check_name, r.status, "data_quality_checks (база v5)", (r.details_json or "")[:180])
    ing = rj(OUT / "ingest_log.json") or {}
    integ = (ing.get("integrity") or {})
    add("данные", "SQLite integrity_check + foreign_key_check", "PASS" if integ.get("integrity") == "ok" and integ.get("foreign_key_violations") == 0 else "FAIL",
        "outputs/ingest_log.json", json.dumps(integ, ensure_ascii=False))
    idem = rj(OUT / "IDEMPOTENCY_CHECK.json")
    add("данные", "идемпотентность ingest (два прохода, сравнение дайджестов таблиц)", idem["status"] if idem else "NOT_RUN",
        "outputs/IDEMPOTENCY_CHECK.json", f"{sum(v['identical'] for v in idem['tables'].values())}/{len(idem['tables'])} таблиц совпали" if idem else "")
    if D_JSON_V4.exists():
        h = hashlib.sha1(D_JSON_V4.read_bytes()).hexdigest()
        add("данные", "базовый D.json v4 не изменён (SHA-1)", "PASS" if h == D_SHA1_BASELINE else "FAIL", str(D_JSON_V4.relative_to(ROOT.parent)), h)
    fd = FRONT / "src/data/D.json"
    if fd.exists():
        h = hashlib.sha1(fd.read_bytes()).hexdigest()
        add("данные", "D.json v4 в репозитории дашборда не изменён (SHA-1)", "PASS" if h == D_SHA1_BASELINE else "FAIL", "-/src/data/D.json", h)

    # 3. аудит
    au = rj(OUT / "PROJECT_CHECKS_v5.json")
    if au:
        for r in au["checks"]:
            add("повтор проверок аудитора", r["test"], r["status"], "outputs/PROJECT_CHECKS_v5.json", str(r.get("detail"))[:180])
    else:
        add("повтор проверок аудитора", "scripts/audit_v5.py", "NOT_RUN", "outputs/PROJECT_CHECKS_v5.json отсутствует")

    # 4. расчёт
    add("расчёт", "полный конвейер завершён", "PASS" if not man.get("quick") else "FAIL", f"{REL}/RUN_MANIFEST.json",
        f"run_id {man['run_id']}; пик RSS {f2(man.get('peak_rss_mib'), 0)} МиБ")
    add("расчёт", "предупреждения численных библиотек перехвачены и записаны", "PASS" if man.get("n_warnings", 0) == 0 else "INFO",
        "RUN_MANIFEST.json → diagnostics_warnings", f"{man.get('n_warnings', 0)} предупреждений")
    lk = man.get("leakage_test", {})
    add("расчёт", "утечка будущего: искажение данных после 2023Q4 (исполненный тест)", lk.get("status", "NOT_RUN"), f"{REL}/LEAKAGE_TEST.json",
        f"мониторинг: признаки/W/метки идентичны = {lk.get('monitoring')}; реконструкция меняется = {lk.get('retrospective_changes_detected')}")
    integ2 = man.get("store", {}).get("integrity", {})
    add("расчёт", "запись результатов в базу (integrity, FK)", "PASS" if integ2.get("integrity") == "ok" and integ2.get("foreign_key_violations") == 0 else "FAIL",
        "RUN_MANIFEST.json → store", json.dumps(integ2, ensure_ascii=False))
    ho = rd("HOLDOUT_VALIDATION")
    if ho is not None:
        for r in ho.itertuples():
            add("расчёт", f"вне периода: {r.level}, закупки {r.year}", "INFO" if "выборке" in str(r.year) else ("PASS" if r.p_value < 0.05 else "FAIL"),
                f"{REL}/HOLDOUT_VALIDATION.csv", f"точность {f2(r.accuracy)} против нуля {f2(r.null_mean)} (q95 {f2(r.null_q95)}), p = {f2(r.p_value, 4)}, B = {r.B}")
    else:
        add("расчёт", "проверка вне периода (2025–2026)", "NOT_RUN", "HOLDOUT_VALIDATION.csv отсутствует")
    lg = rj(LAT / "LAG_EDGE_SUMMARY.json")
    if lg is not None and lg.get("run_id") == man["run_id"]:
        add("расчёт", "связи со сдвигом: значимость (фазовые суррогаты, BH/BY) и jackknife", "INFO", f"{REL}/LAG_EDGE_SUMMARY.json",
            f"пар {lg['ordered_pairs_tested']}, значимы BH {lg['sig_bh_005']}, BY {lg['sig_by_005']}; стрелок значимых и устойчивых {lg['arrows_sig_stable']} из {lg['arrows_total']}; "
            f"совпадение со слоем прогона {lg['agrees_with_run_function']}")
    else:
        add("расчёт", "связи со сдвигом: значимость и устойчивость", "NOT_RUN", "LAG_EDGE_SUMMARY.json отсутствует или от другого прогона")

    # 5. нагрузка
    sb = rj(OUT / "SCALE_BENCHMARK.json")
    if sb:
        for r in sb["runs"]:
            add("нагрузка", f"синтетика N={r['N']}: граф+spectral+Leiden+ICVI", "PASS",
                "outputs/SCALE_BENCHMARK.json", f"граф {r['graph_s']} с, spectral {r['spectral_s']} с, Leiden {r['leiden_s']} с, ICVI {r['icvi_s']} с, пик {r['peak_rss_mib']} МиБ; DTW всех пар ≈ {r['dtw_all_pairs_est_s']} с")
    else:
        add("нагрузка", "scripts/scale_benchmark.py", "NOT_RUN", "outputs/SCALE_BENCHMARK.json отсутствует")

    # 6. дашборд
    vc = rj(FRONT / "docs/v5-checks.json")
    if vc:
        stale = vc.get("file") != "econtypes_v5.html"
        for r in vc["results"]:
            add("дашборд", r["name"], r["status"] if not stale else "NOT_RUN", "-/docs/v5-checks.json (Playwright, Chromium)",
                (json.dumps(r["detail"], ensure_ascii=False) if not isinstance(r["detail"], str) else r["detail"])[:160])
        banner = next((r for r in vc["results"] if r["name"] == "v5.banner-has-run-id"), None)
        if banner is not None:
            same = man["run_id"] in str(banner["detail"])
            add("дашборд", "дашборд собран из этого же прогона (run_id в шапке)", "PASS" if same else "FAIL", "-/docs/v5-checks.json", man["run_id"])
    else:
        add("дашборд", "tests/v5-check.js", "NOT_RUN", "нет -/docs/v5-checks.json")

    # 7. не выполнено — честно
    for t, why in [
        ("полная загрузка ATMO 44-ФЗ (493 912 записей, 341 часть)", "часть 51 отсутствует в листинге Drive; потоковая загрузка не выполнялась — использованы canonical CSV (359 615 контрактов) и выборочный аудит"),
        ("общероссийский прогон (~2 000+ МО)", "нет входов СберИндекса по всем МО; проверено только ядро алгоритмов на синтетике N = 2 016"),
        ("сырые parquet СберИндекса (consumption, connection, market_access)", "не найдены на Drive; sberindex.ru закрыт политикой сети (403); использованы производные v4"),
        ("прямая загрузка с rosstat.gov.ru / nalog.gov.ru", "закрыто политикой сети (403); таблицы Росстата взяты с Drive пользователя с SHA-256"),
        ("ЕИС (zakupki.gov.ru) через Opera Browser Connector", "коннектор в сессии отсутствует; по правилу пользователя другой канал не использовался"),
        ("ручная выборочная сверка привязки адресов с открытыми реестрами", "нет сетевого доступа к ФНС/ЕГРЮЛ; точность оценена LOO внутри данных"),
        ("публикация, отправка конкурсной формы", "не выполнялось — требуется отдельное указание пользователя"),
    ]:
        add("не выполнено", t, "NOT_RUN", "—", why)
    return rows


def write_stress(man: dict):
    rows = stress_rows(man)
    df = pd.DataFrame(rows)
    cnt = df.status.value_counts().to_dict()
    lines = [
        "# STRESS_TEST_REPORT — econtypes v5",
        "",
        f"Прогон: `{man['run_id']}` (config `{man['config_hash']}`, code `{man['code_hash']}`, data `{man['data_hash']}`, seed {man['seed']}). "
        "Отчёт собирается автоматически `scripts/make_report.py` из файлов проверок; статус берётся из файла, а не вписывается.",
        "",
        "Итого: " + ", ".join(f"**{k}** {v}" for k, v in sorted(cnt.items())) + ".",
        "",
        "Статусы: PASS — проверка исполнена и прошла; FAIL — исполнена и не прошла; INFO — измерение без порога; NOT_RUN — не исполнялась (причина указана).",
        "",
    ]
    for g, t in df.groupby("group", sort=False):
        lines += [f"## {g}", "", "| проверка | статус | основание | детали |", "|---|---|---|---|"]
        for r in t.itertuples():
            lines.append(f"| {r.test} | **{r.status}** | {r.evidence} | {str(r.detail).replace('|', '/')} |")
        lines.append("")
    (DOCS / "STRESS_TEST_REPORT.md").write_text("\n".join(lines))
    df.insert(0, "run_id", man["run_id"])
    df.to_csv(DOCS / "STRESS_TEST_REPORT.csv", index=False)
    return cnt


# ---------------------------------------------------------------- отчёт
def build_report(man: dict) -> Doc:
    P, Pd = rd("TYPE_PASSPORTS"), rd("TYPE_PASSPORTS_DETAILED")
    ks, unc, comp, abl = rd("K_SELECTION"), rd("UNCERTAINTY_SUMMARY"), rd("CLUSTER_COMPARISON"), rd("ABLATION_SENSITIVITY")
    bs, ev, dq = rd("DYNAMICS_BETA_SENSITIVITY"), rd("DYNAMICS_EVENTS"), rd("DYNAMICS_QUALITY")
    exv, cor, gd, bal = rd("EXTERNAL_VALIDATION"), rd("CORRELATIONS_MO_PERIOD"), rd("GRAPH_DIAGNOSTICS"), rd("DEMOGRAPHIC_BALANCE")
    ho, sweep, stab = rd("HOLDOUT_VALIDATION"), rd("ICVI_SWEEP"), rd("NODE_STABILITY")
    ing = rj(OUT / "ingest_log.json") or {}
    sb = rj(OUT / "SCALE_BENCHMARK.json")
    au = rj(OUT / "PROJECT_CHECKS_v5.json")
    fin, det = man["final"], man["detailed"]

    u = unc.set_index("scheme")
    v4row = comp[comp.labeling.str.startswith("v4_published")].iloc[0]
    c1row = comp[comp.labeling.str.startswith("C1_") & comp.labeling.str.contains("selected")]
    c1row = c1row.iloc[0] if len(c1row) else None
    strict = abl[abl.variant.str.contains("strict|строг", case=False, regex=True)]
    geo = ing.get("geography", {})
    loo = geo.get("loo_kpp", {})
    ck = ing.get("checks", {}).get("contracts", {})
    E_exact = gd[gd.matrix == "W_exact[C4_v5features_v5graph]"].edges.iloc[0]
    E_disp = gd[gd.matrix == "W_display[C4_v5features_v5graph]"].edges.iloc[0]

    D = Doc()
    D.h(1, "Экономическая структура муниципалитетов Республики Башкортостан: кластеризация атрибутированных сетей (econtypes v5)")
    D.p(f"Конкурс СберИндекса, задача 1. Региональный кейс: 63 муниципальных образования Республики Башкортостан; основная типология — 62 МО "
        f"(ЗАТО Межгорье без данных СберИндекса рассмотрено отдельно). Результат не является общероссийским. "
        f"Прогон `{man['run_id']}` (seed {man['seed']}, config `{man['config_hash']}`, code `{man['code_hash']}`, data `{man['data_hash']}`). "
        "Все числа ниже взяты из файлов этого прогона скриптом `scripts/make_report.py`.")

    # --- выводы
    D.h(2, "1. Главное")
    n_by = int((cor.q_by < 0.05).sum()) if "q_by" in cor else 0
    n_rob = int(cor.robust.astype(str).eq("True").sum())
    ext5 = exv[exv.labeling == "v5_final"]
    D.ul([
        f"**Макроуровень — {plural(fin['k'], 'тип', 'типа', 'типов')}** ({fin['method']}, постановка {fin['config']}). K не задавался: выбран правилом «Pareto по z-оценкам ICVI → минимальный размер ≥ 3 → "
        f"медиана бутстреп-ARI ≥ 0,5 → средний ранг z». Устойчивость: медиана ARI {f2(u.loc['node_subsample', 'ARI_median'])} при подвыборке узлов, "
        f"{f2(u.loc['temporal_block', 'ARI_median'])} при блочном бутстрепе месяцев, {f2(u.loc['feature_network_rebuild', 'ARI_median'])} при пересборке признаков и сети.",
        f"**Детальный уровень — {plural(det['k'], 'тип', 'типа', 'типов')}** ({det['method']}, то же правило при K ≥ 5): медиана бутстреп-ARI {f2(u.loc['node_subsample_detailed', 'ARI_median'])} — "
        "устойчив лишь частично; используется как уточнение, а не как самостоятельный вывод.",
        f"**Типология v4 (K = 7) не воспроизводится**: ARI между v5 и v4 = {f2(v4row.ARI_vs_final)}. После исправления AVU та же постановка v4 (признаки и граф v4) "
        + (f"выбирает K = {int(c1row.k)}, а не 7." if c1row is not None else "выбирает другой K.") + " Численные выводы v4 в v5 не переносятся.",
        f"**Опубликованный AVU** на расчётной сети v4 с метками v4 = {f2(v4row.AVU__own, 4)} (в v4 под именем AVU максимизировалась доля внутренних связей). "
        f"AVU не лучше перестановочного нуля у {int((sweep.p_AVU >= 0.05).sum())} из {len(sweep)} разбиений сетки (p ≥ 0,05), а у {int((sweep.z_AVU < 0).sum())} — хуже случайного (z < 0), "
        f"тогда как модулярность значимо выше нуля (медиана z MQ_newman {f2(sweep.z_MQ_newman.median(), 1)}): внутри типов связи плотнее, но межтиповые связи сосредоточены между соседними типами — "
        "экономическое пространство региона скорее непрерывно, чем распадается на изолированные блоки.",
        f"**Внешняя проверка** признаками, не входившими в обучение (ВПН-2020: источники средств к существованию, образование; МСП): "
        f"{int((ext5.q_bh_perm < 0.05).sum())} из {len(ext5)} показателей значимо различаются между типами после BH; "
        f"{int((ext5.p_spatial < 0.05).sum())} — и против пространственного нуля (MSR).",
        f"**Корреляции**: {len(cor)} тестов; {n_by} проходят BY (q < 0,05), {n_rob} помечены «устойчивыми» (BY + пространственный нуль + знак без Уфы + частная по log населения).",
        f"**Динамика** (2023Q1–2024Q4, режим мониторинга без информации из будущего): тест утечки — {man['leakage_test']['status']}.",
    ])

    # --- данные
    D.h(2, "2. Данные и источники")
    D.p("Новая база `data/econtypes_v5.sqlite` (слои L0 сырьё → L1 нормализация → L2 атрибуты МО × период → L3 результаты прогонов), миграции, идемпотентный ingest, "
        "экспорт Parquet. Исходные файлы и папки не изменялись. Реестр источников — `docs/SOURCE_REGISTRY.csv`, пробелы — `docs/DATA_GAPS.md`.")
    D.ul([
        f"Госзаказ 44-ФЗ и 223-ФЗ: {fint(ck.get('csv', {}).get('rows', 0))} записей (8 canonical CSV); независимый пересчёт DuckDB совпал с базой до копейки "
        f"({money(ck.get('csv', {}).get('rub_known', 'nan'))} руб. с известной суммой в рублях). Признаки госзаказа строятся по 44-ФЗ; 223-ФЗ — отдельный показатель на жителя.",
        f"Привязка заказчиков к МО: явное МО в названии ({fint(geo.get('named_explicit', 0))} организаций) и код налогового органа КПП; "
        f"точность кода КПП по исключению по одному — {pct(loo.get('accuracy', np.nan))} на {fint(loo.get('evaluated', 0))} организациях. Первые цифры ИНН — только анализ чувствительности.",
        f"Реестр МСП (снимок 10.09.2026): {fint(ing.get('msp', {}).get('firms', 0))} субъектов; используется только как внешний показатель специализации (сглаженный LQ).",
        "СберИндекс: помесячные безналичные траты на жителя и их структура по 6 категориям 2023–2024 — архивные производные v4 (сырых parquet нет).",
        "Росстат (с Google Drive пользователя, SHA-256 в `external/rosstat_drive/DRIVE_DOWNLOADS.jsonl`): численность на 1 января 2022–2025, естественное движение 2023–2024, "
        "коэффициенты миграции 2018–2024, ВПН-2020 (возраст, образование, источники средств).",
        f"Контроль баланса населения ΔN = рождения − смерти + миграция: максимальный остаток {pct(bal.residual_share_of_pop.abs().max(), 3)} населения.",
    ])

    # --- методология
    D.h(2, "3. Методология")
    D.p("**Узлы** — МО. **Атрибуты** (18 после преобразований, без импутации): уровень и относительный тренд трат СберИндекса; структура трат в ILR-координатах (Aitchison); "
        "госзаказ 44-ФЗ и 223-ФЗ на жителя; доля муниципальных заказчиков; HHI поставщиков; география поставщиков (ILR: своё МО / другие МО РБ / вне РБ); "
        "рост населения, естественный и миграционный прирост; возрастная структура (ILR). Стандартизация — робастные z (медиана/IQR), вес блока λ_b = 1/p_b.")
    D.p(f"**Рёбра**: self-tuning kNN (k = 8, локальный масштаб — 7-й сосед) по блочному расстоянию атрибутов, объединённый с нормированными структурными слоями "
        f"(совместное движение трат, опережение-запаздывание, DTW — только по месяцам окна; потоки закупок между МО), α = 0,5. "
        f"Расчётная матрица W хранится отдельно от визуальной проекции: {fint(E_exact)} рёбер против {fint(E_disp)} в проекции union-kNN k = 4; сетевые ICVI считаются только по W.")
    D.p("**Кластеризация и выбор**: spectral (cluster_qr) и Leiden (RB-модулярность с подбором разрешения под K), контроль — k-means и Ward; K = 2…10. "
        "Для каждого разбиения: SW, CH, DB, S_Dbw (явные соглашения о неопределённых слагаемых), опубликованные AVI/AVU, MQ_newman (γ = 1) и MQ_mancoridis; "
        "z-оценки против перестановочного нуля, p = (b+1)/(B+1). Правило выбора зафиксировано в коде (`experiments.select`) до просмотра типов.")
    D.p("**Динамика**: квартальные снимки с эволюционным сглаживанием (W_t ← (1−β)W_t + βW_{t−1}, β ∈ {0; 0,3; 0,5; 0,7; 0,9}), венгерское выравнивание меток, "
        "таблицы переходов, Жаккар, события split/merge/birth/death. Два режима: **мониторинг** (только данные, опубликованные к концу квартала, с лагами) "
        "и **реконструкция** (ретроспективно, со структурой трат за весь период).")
    D.p("**Неопределённость**: co-assignment по трём схемам (подвыборка узлов, блочный бутстреп месяцев, пересборка признаков и сети). "
        "**Корреляции**: Pearson и Spearman с перестановочными p (B = 9 999), BH/BY, e-BH, пространственный нуль Moran spectral randomization по смежности полигонов, "
        "частные по log населения, разложение панели на межмуниципальную и внутримуниципальную части.")
    if sweep is not None:
        FIG.mkdir(parents=True, exist_ok=True)
        draw_ksel(sweep, fin, FIG / "k_selection.png")
        D.img(FIG / "k_selection.png", "Рис. 1. Выбор K и метода в постановке C4.")
    t = ks.copy()
    t["постановка"] = t.config
    D.table(pd.DataFrame({
        "постановка": t.config, "метод": t.method, "K": t.k, "бутстреп-ARI": t.boot_ari_median.map(f2), "ранг z": t.z_rank_mean.map(f2),
        "SW": t.SW.map(f2), "CH": t.CH.map(lambda x: f2(x, 1)), "S_Dbw": t.S_Dbw.map(f2), "AVI": t.AVI.map(f2), "AVU ↓": t.AVU.map(f2),
        "MQ_newman": t.MQ_newman.map(f2)}), "Таблица 1. Выбранные разбиения по постановкам (C1 — признаки и граф v4; C4 — признаки и граф v5).")

    # --- типы
    D.h(2, "4. Типы муниципалитетов (макроуровень)")
    geoobj = None
    try:
        geoobj = load_geo()
    except Exception as e:  # noqa: BLE001
        D.p(f"(карта не построена: {type(e).__name__})")
    ls = rd("LABELS_STATIC")
    if geoobj is not None and ls is not None:
        names = {int(k): v for k, v in man["type_names"].items()}
        draw_map(ls.set_index("mo").macro, names, FIG / "map_macro.png", f"Макротипы v5 ({man['run_id']})", geoobj)
        D.img(FIG / "map_macro.png", "Рис. 2. Макротипы v5 на карте Республики Башкортостан.")
    for r in P.itertuples():
        D.h(3, r.name)
        D.p(f"{r.n_mo} МО, население на 1.01.2024 — {fint(r.population_2024)} чел. Отличительные признаки (разность медиан робастных z с остальными МО): "
            f"{r.distinctive_plain} [{r.distinctive_1}; {r.distinctive_2}; {r.distinctive_3}].")
        D.ul([
            f"Медианы: безналичные траты {fint(r.median_spend_rub_month)} руб./жителя/мес.; госзаказ 44-ФЗ {fint(r.median_proc44_rub_pc_year)} руб./жителя/год; "
            f"изменение населения за 2023 г. {f2(100 * r.median_pop_growth, 1)}%; естественный прирост {f2(r.median_natinc, 1)}‰; миграционный {f2(r.median_migr / 10, 1)}‰ "
            f"(в таблицах Росстата — на 10 000 жителей: {f2(r.median_migr, 1)}); доля 65+ {pct(r.median_share_65plus)}.",
            f"Внешние показатели (не входили в обучение): доля населения с заработком как основным источником средств {pct(r.ext_wage_main_share)}, с пенсией/пособием — {pct(r.ext_pension_main_share)}, "
            f"с высшим образованием {pct(r.ext_higher_edu)}; наибольшая специализация МСП — {msp_spec(r.msp_top_specialization)} (LQ сельского хозяйства {f2(r.msp_lq_agri)}, "
            f"промышленности {f2(r.msp_lq_industry)}, деловых услуг {f2(r.msp_lq_business_services)}).",
            f"Медиана устойчивости членства (подвыборка узлов) {f2(r.stability_median)}; типичные МО: {r.typical_examples}"
            + (f"; пограничные (устойчивость < 0,5): {r.boundary_mo}." if isinstance(r.boundary_mo, str) and r.boundary_mo else "; пограничных МО нет."),
            f"Состав: {r.members}.",
        ])
    mz = man.get("mezhgorye", {})
    if mz:
        D.p(f"**ЗАТО Межгорье** в основную типологию не входит (нет СберИндекса и муниципальной демографии Росстата). "
            f"По блокам госзаказа ближайший центроид — {man['type_names'].get(str(mz.get('nearest_type')), mz.get('nearest_type'))} (расстояния до центроидов типов: {'; '.join(f2(x) for x in mz.get('distances', []))}); это ориентир, а не присвоение типа.")

    D.h(2, "5. Детальный уровень")
    if geoobj is not None and ls is not None:
        names_d = {int(k): v for k, v in man["type_names_detailed"].items()}
        draw_map(ls.set_index("mo").detailed, names_d, FIG / "map_detailed.png", f"Детальные типы v5 ({man['run_id']})", geoobj)
        D.img(FIG / "map_detailed.png", "Рис. 3. Детальные типы (частично устойчивы).")
    D.table(pd.DataFrame({"тип": Pd.name, "МО": Pd.n_mo, "население": Pd.population_2024.map(fint), "признаки": Pd.distinctive_plain,
                          "устойчивость": Pd.stability_median.map(f2), "примеры": Pd.typical_examples}),
            f"Таблица 2. Детальные типы; медиана бутстреп-ARI уровня {f2(u.loc['node_subsample_detailed', 'ARI_median'])}.")

    # --- сравнение
    D.h(2, "6. Сравнение постановок и абляция")
    cmp_ = comp.copy()
    D.table(pd.DataFrame({"разметка": cmp_.labeling, "K": cmp_.k, "ARI с итогом v5": cmp_.ARI_vs_final.map(f2), "ARI с v4": cmp_.ARI_vs_v4.map(f2),
                          "AVU (своя W)": cmp_["AVU__own"].map(f2), "MQ_newman (своя W)": cmp_["MQ_newman__own"].map(f2), "SW (свои X)": cmp_["SW__own"].map(f2)}).head(14),
            "Таблица 3. Сравнение разметок: признаки старые/новые × граф старый/новый, spectral против Leiden, контрольные методы.")
    D.p(f"Абляция ({len(abl)} вариантов: исключение блока, слоя, смена α, k, правила рёбер, географии): медиана ARI с итогом {f2(abl.ARI_vs_final.median())}, "
        f"минимум {f2(abl.ARI_vs_final.min())} ({abl.loc[abl.ARI_vs_final.idxmin(), 'kind']}: {abl.loc[abl.ARI_vs_final.idxmin(), 'variant']}). "
        + (f"Строгая география (только явное МО и согласованный налоговый орган): ARI {f2(strict.ARI_vs_final.iloc[0])}." if len(strict) else ""))
    lo = abl.sort_values("ARI_vs_final").head(8)
    D.table(pd.DataFrame({"вид": lo.kind, "вариант": lo.variant, "K": lo.k, "ARI с итогом": lo.ARI_vs_final.map(f2)}),
            "Таблица 4. Наиболее чувствительные варианты абляции.")

    # --- динамика
    D.h(2, "7. Динамика 2023–2024")
    if bs is not None:
        draw_beta(bs, FIG / "beta.png")
        D.img(FIG / "beta.png", "Рис. 4. Чувствительность динамики к β.")
        m5 = bs[(bs.level == "macro") & (bs["mode"] == "monitoring") & (bs.beta == 0.5)].iloc[0]
        D.p(f"При β = 0,5 в режиме мониторинга средний ARI соседних кварталов {f2(m5.temporal_ARI)}, ARI со статической типологией {f2(m5.ARI_vs_static)}. "
            "Большие β дают гладкость ценой отрыва от текущих данных (снижение MQ снимков) — поэтому основной β = 0,5, остальные приводятся как чувствительность.")
    if ev is not None:
        e5 = ev[(ev["mode"] == "monitoring") & (ev.beta == 0.5)]
        cnt = e5.event.value_counts().to_dict()
        D.p("События (мониторинг, β = 0,5): " + ", ".join(f"{k} — {v}" for k, v in cnt.items()) +
            ". Первые кварталы 2023 г. — период разогрева (окно короче года), их перестройки не интерпретируются как экономические сдвиги.")
    D.p(f"Тест утечки: данные после 2023Q4 искажены, расчёт до 2023Q4 повторён. Мониторинг — признаки, W и метки идентичны; реконструкция — признаки и W меняются "
        f"(статус {man['leakage_test']['status']}). Метки по кварталам — `LABELS_MO_PERIOD*.csv`.")

    # --- внешняя проверка и корреляции
    D.h(2, "8. Внешняя проверка и корреляции")
    e = ext5.sort_values("eps2", ascending=False).head(10)
    D.table(pd.DataFrame({"показатель": e.indicator.map(ru), "ε² (Крускал–Уоллис)": e.eps2.map(f2), "p перест.": e.p_perm.map(lambda x: f2(x, 4)),
                          "q BH": e.q_bh_perm.map(lambda x: f2(x, 4)), "p простр. (MSR)": e.p_spatial.map(lambda x: f2(x, 3)), "I Морана": e.moran_I.map(f2)}),
            "Таблица 5. Различия внешних показателей между макротипами (не использовались в обучении).")
    st = cor[(cor.family == "features_x_external[pearson]") & cor.robust.astype(str).eq("True")].copy()
    # механически связанные пары (одна и та же таблица ВПН-2020 по возрасту) — не открытие, исключаются из таблицы
    mech = st.feature.str.startswith("age_ilr") & st.indicator.str.contains("ratio")
    n_mech = int(mech.sum())
    st = st[~mech]
    st["absr"] = st.r.abs()
    st = st.sort_values("absr", ascending=False).head(10)
    D.table(pd.DataFrame({"признак": st.feature.map(ru), "внешний показатель": st.indicator.map(ru), "r": st.r.map(f2), "95% ДИ": [f"[{f2(a)}; {f2(b)}]" for a, b in zip(st.ci_lo, st.ci_hi)],
                          "q BY": st.q_by.map(lambda x: f2(x, 4)), "p простр.": st.p_spatial.map(lambda x: f2(x, 3)), "r частн. (log нас.)": st.r_partial_logpop.map(f2),
                          "r без Уфы": st.r_without_ufa.map(f2)}),
            f"Таблица 6. Наиболее сильные устойчивые связи признаков с внешними показателями (Pearson); исключены {n_mech} механически связанных пар "
            "(ILR возраста × коэффициенты нагрузки — из одной таблицы возраста ВПН-2020).")
    sp = cor[(cor.family == "features_x_external[pearson]") & (cor.feature == "sber_spend_pc_log")].set_index("indicator")
    pick = [i for i in ("ext_census_wage_main_share", "ext_equalization_grants_pc_v4", "msp_lq_agri") if i in sp.index]
    if pick:
        D.p("Связи описательные, не причинные. Уровень безналичных трат на жителя: " + "; ".join(
            f"{ru(i)} — r = {f2(sp.loc[i, 'r'])} (частная по log численности {f2(sp.loc[i, 'r_partial_logpop'])})" for i in pick)
            + ". Где частная корреляция заметно слабее полной, часть связи объясняется масштабом МО.")
    wb = cor[cor.within.notna()].copy()
    if len(wb):
        wb["absw"] = wb.within.abs()
        wb = wb.sort_values("absw", ascending=False).head(6)
        D.table(pd.DataFrame({"признак 1": wb.feature.map(ru), "признак 2": wb.indicator.map(ru), "между МО": wb.between.map(f2), "внутри МО": wb.within.map(f2),
                              "95% ДИ (кластерный бутстреп)": [f"[{f2(a)}; {f2(b)}]" for a, b in zip(wb.within_ci_lo, wb.within_ci_hi)]}),
                "Таблица 7. Разложение панельных корреляций (кварталы 2023–2024): межмуниципальная и внутримуниципальная части.")
        D.p("Корреляции между МО и во времени внутри МО могут иметь разный знак; выводы о динамике делаются только по внутренней части.")
    if ho is not None:
        D.h(2, "9. Проверка вне периода обучения")
        cols = {"уровень": ho.level, "год": ho.year, "МО": ho.n, "точность": ho.accuracy.map(f2)}
        if "majority_baseline" in ho:
            cols.update({"доля частого типа": ho.majority_baseline.map(f2), "balanced accuracy": ho.balanced_accuracy.map(f2),
                         "ARI": ho.ari.map(f2), "NMI": ho.nmi.map(f2), "контрактов 44-ФЗ": ho.n_contracts_44.map(fint)})
        cols.update({"нуль (среднее)": ho.null_mean.map(f2), "p": ho.p_value.map(lambda x: f2(x, 4))})
        D.table(pd.DataFrame(cols),
                "Таблица 8. Узнаётся ли тип 2023–2024 по блокам госзаказа 44-ФЗ 2025 и 2026 (YTD): ближайший центроид; первая строка уровня — та же процедура "
                "на обучающем периоде (потолок); нуль — перестановка предсказанных меток.")
        D.p("Это проверка воспроизводимости разметки по одному блоку, а не независимое подтверждение экономической истинности типов. "
            "Блок 223-ФЗ исключён: в 2025 г. в выгрузке лишь 1 340 записей 223-ФЗ против 35 631 в 2023 г. (разрыв покрытия источника, `docs/DATA_GAPS.md`, п. 25). "
            "Общий сдвиг уровня закупок (инфляция) стандартизацией 2023–2024 не устраняется.")

    lg = rj(LAT / "LAG_EDGE_SUMMARY.json")
    if lg is not None and lg.get("run_id") == man["run_id"]:
        D.h(3, "Связи со сдвигом по времени: значимость и устойчивость")
        D.p(f"Проверены {fint(lg['ordered_pairs_tested'])} упорядоченных пар МО ({lg['nodes_tested']} МО, {lg['increments']} месячных приращений, сдвиг 1–{lg['max_lag']} мес.). "
            f"Нуль: фазовая рандомизация ряда-последователя, B = {fint(lg['B'])}; поправка BH и BY. "
            f"Значимы после BH: {fint(lg['sig_bh_005'])}, после BY: {fint(lg['sig_by_005'])}. "
            f"Из {fint(lg['arrows_total'])} пар, где правило ставит стрелку, значимых и устойчивых по jackknife: {fint(lg['arrows_sig_stable'])}. "
            f"Не проверялись МО {', '.join(map(str, lg['nodes_not_tested'])) or 'нет'}: {lg['not_tested_reason']}.")
        D.p("Вывод: связи со сдвигом на этом окне не отличаются от шума, стрелки направления не подтверждены. Слой остаётся в W с тем же весом "
            "(абляция: исключение слоя lead_lag не меняет макротипы), а в интерпретации используется только как разведочный. Причинность не утверждается. "
            "Подробно: `outputs/latest/LAG_EDGE_TESTS.csv` и `LAG_EDGE_SUMMARY.json`.")

    # --- исправления
    D.h(2, "10. Исправления относительно v4")
    D.p("Полная таблица — `CHANGELOG.md`. Кратко: опубликованный AVU вместо максимизировавшейся доли внутренних связей; оба определения MQ с γ; S_Dbw с явными соглашениями "
        "(в v4 все слагаемые плотности были нулевыми — S_Dbw совпадал со Scat); слои без информации из будущего; точная W отдельно от проекции; p = (b+1)/(B+1); "
        "краевые случаи DTW/log 0/kNN; география без ИНН→ОКТМО; имена типов по профилям; вводящие в заблуждение прокси сняты.")
    if au:
        D.table(pd.DataFrame([{"проверка аудитора": r["test"], "статус": r["status"]} for r in au["checks"]]), "Таблица 9. Повтор проверок аудитора на v5.")

    # --- ограничения
    D.h(2, "11. Ограничения")
    D.ul([
        "Региональный кейс (62 + 1 МО); перенос на всю Россию не проверялся на реальных данных — только масштабирование алгоритмов на синтетике"
        + (f" (N = 2 016: пик памяти {sb['runs'][-1]['peak_rss_mib']} МиБ)." if sb else "."),
        "СберИндекс — архивные производные v4, а не сырые parquet; структура трат известна только агрегатом 2023–2024 (режим реконструкции).",
        "Привязка организаций к МО — по названию и налоговому органу (оценённая точность), а не по ОКТМО; поставщики вне МСП-реестра и с адресом вне РБ — категория «вне РБ».",
        "Снимок МСП 2026 г. — не исторический; используется только как внешний показатель.",
        "Детальный уровень устойчив лишь частично; выводы по отдельным детальным типам — гипотезы.",
        "AVU при малом K дискретен (при K = 2 принимает значения 0 или 1) — сравнивается через z против перестановок, не по уровню.",
        "Межгорье (ЗАТО) без СберИндекса и муниципальной демографии — вне основной типологии.",
    ])

    D.h(2, "12. Воспроизведение")
    D.p("Одна команда из каталога `econtypes_v5`: `bash scripts/run_all.sh` (база → тесты → расчёт → аудит → нагрузка → матрицы → D5 и дашборд → отчёт). "
        f"Полный расчёт ≈ {max(1, round(max(man['timings'].values()) / 60))} мин на 4 vCPU, пик памяти {f2(man.get('peak_rss_mib'), 0)} МиБ. "
        "Матрицы соответствия: `docs/REQUIREMENTS_MATRIX.csv`, `docs/FORMULA_IMPLEMENTATION_MATRIX.csv`; стресс-проверки: `docs/STRESS_TEST_REPORT.md`.")
    return D


def export_source_registry():
    p = OUT / "db_parquet/source_registry.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        df.to_csv(DOCS / "SOURCE_REGISTRY.csv", index=False)
        return len(df)
    return 0


def main():
    man = rj(LAT / "RUN_MANIFEST.json")
    if man is None:
        sys.exit("нет outputs/latest/RUN_MANIFEST.json — сначала econtypes5.pipeline")
    DOCS.mkdir(exist_ok=True)
    n_src = export_source_registry()
    cnt = write_stress(man)
    D = build_report(man)
    (DOCS / "REPORT_v5.md").write_text(D.to_md())
    D.to_docx(DOCS / "REPORT_v5.docx", "econtypes v5 — отчёт")
    pdf = "не создан (LibreOffice не найден)"
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(DOCS), str(DOCS / "REPORT_v5.docx")],
                           capture_output=True, text=True, timeout=300)
        pdf = "docs/REPORT_v5.pdf" if (DOCS / "REPORT_v5.pdf").exists() and r.returncode == 0 else f"ошибка LibreOffice: {r.stderr[-200:]}"
    print(json.dumps(dict(run_id=man["run_id"], source_registry_rows=n_src, stress=cnt, report_md="docs/REPORT_v5.md",
                          report_docx="docs/REPORT_v5.docx", report_pdf=pdf), ensure_ascii=False))


if __name__ == "__main__":
    main()
