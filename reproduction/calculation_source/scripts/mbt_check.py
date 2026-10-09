"""Внешняя проверка: межбюджетные трансферты (МБТ) из бюджета РБ бюджетам МО.

Источник: Минфин РБ, «Информация о предоставленных межбюджетных трансфертах бюджетам МО»
за 9 месяцев 2023, 2024, 2025 гг. Берётся уточнённый годовой план. Трансферты поселениям
суммируются с трансфертами своему району (консолидированный бюджет района).
В модель не входит: проверяем, согласуется ли индекс «Бюджетная зависимость» и типы МО
с фактическими объёмами помощи из бюджета республики.

Запуск: python scripts/mbt_check.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import numpy as np, pandas as pd, openpyxl
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/minfin_mbt"
BLOCKS = {"ВСЕГО": "mbt_total", "Дотации (510)": "mbt_dot", "Субсидии (520)": "mbt_sub",
          "Субвенции (530)": "mbt_subv", "Иные межбюджетные трансферты (540)": "mbt_other"}


def stem(word: str) -> str:
    w = word.lower().replace("ё", "е")
    return re.sub(r"(ский|ского|скому|ском|ская|ское|цкий|цкого)$", "", w)


def to_mo(name: str, mo_list: list[str]) -> str | None:
    s = re.sub(r"\s+", " ", name.replace("Бюджет", "")).strip()
    if re.search(r"итого|нераспредел", s, re.I):
        return None
    ms = [w for w in re.findall(r"(\w+)\s+район", s) if not w.lower().startswith("муниципальн")]
    if ms:                                     # «…Абзелиловский район», «… Абзелиловского района»
        st = stem(ms[-1])
        for mo in mo_list:
            if mo.startswith("МР ") and stem(mo[3:]) == st:
                return mo
    m = re.search(r"город\w*\s+(?:округ\s+)?(?:город\s+)?([А-ЯЁ][\w-]+)", s)
    if m:
        for mo in mo_list:
            if mo.startswith("ГО ") and mo[3:].lower() == m.group(1).lower():
                return mo
    return None


def read(path: Path, mo_list: list[str]) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        h = next(i for i, r in enumerate(rows[:12]) if "ВСЕГО" in [str(c).strip() if c else "" for c in r])
        cols = {BLOCKS[str(c).strip()]: j + 2 for j, c in enumerate(rows[h]) if c and str(c).strip() in BLOCKS}  # +2 = уточнённый план
        for r in rows[h + 1:]:
            if not r or not isinstance(r[1], str) or not isinstance(r[cols["mbt_total"]], (int, float)):
                continue
            mo = to_mo(r[1], mo_list)
            if mo:
                out.append({"mo": mo, **{k: float(r[j] or 0) for k, j in cols.items()}})
    return pd.DataFrame(out).groupby("mo").sum()


def main():
    feats = pd.read_csv(ROOT / "outputs/tables/features_raw_2023_2024.csv").set_index("mo")
    clusters = pd.read_csv(ROOT / "outputs/tables/clusters_final.csv")
    clusters = clusters.set_index(clusters.columns[0])
    metrics = pd.read_csv(ROOT / "outputs/tables/metrics.csv").set_index("mo")
    mo_list = list(feats.index)
    pop = np.exp(feats["log_pop"])
    years = {}
    for y in (2023, 2024, 2025):
        d = read(RAW / f"mbt_9m_{y}.xlsx", mo_list)
        years[y] = d
        print(y, "МО найдено:", len(d), "из", len(mo_list), "; не найдены:", sorted(set(mo_list) - set(d.index)))
    tr = (years[2023] + years[2024]) / 2                      # среднее за период модели
    pc = tr.div(pop, axis=0).dropna()
    pc["sub_share"] = tr["mbt_sub"] / tr["mbt_total"]
    pc["mbt_nodot"] = (tr["mbt_total"] - tr["mbt_dot"]) / pop        # без дотаций: они частично входят в модель (grants_pc)
    pc["mbt_pc_2025"] = years[2025]["mbt_total"] / pop
    ccol = [c for c in clusters.columns if "name" in c][0]
    pc["type"] = clusters[ccol]
    pc.to_csv(ROOT / "outputs/tables/mbt_check.csv")
    res = {"n": int(len(pc))}
    for col in ["mbt_total", "mbt_nodot", "mbt_dot", "mbt_sub", "mbt_subv", "sub_share", "mbt_pc_2025"]:
        g = [v[col].dropna().values for _, v in pc.groupby("type")]
        h, p = stats.kruskal(*g)
        res[col] = {"kruskal_p": float(f"{p:.2g}"),
                    "by_type": pc.groupby("type")[col].median().round(3 if col == "sub_share" else 0).to_dict()}
    j = pc.join(metrics[[c for c in ["budget_dep", "activity", "demo_resilience"] if c in metrics]], how="inner")
    res["spearman"] = {}
    for a in ["mbt_total", "mbt_nodot", "mbt_dot", "mbt_pc_2025"]:
        for b in ["budget_dep", "activity"]:
            r, p = stats.spearmanr(j[a], j[b], nan_policy="omit")
            res["spearman"][f"{a}~{b}"] = {"rho": round(float(r), 2), "p": float(f"{p:.2g}")}
    json.dump(res, open(ROOT / "outputs/mbt_check.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
