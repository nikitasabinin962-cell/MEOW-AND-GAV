"""Внешняя проверка типов: рейтинг МО по открытости бюджетных данных (Минфин РБ).

Показатель в модель не входит. Проверяем, различаются ли по нему типы (Краскел–Уоллис)
и как он связан с индексами МО (Спирмен). Запуск: python scripts/openness_check.py
Результат: outputs/tables/openness_check.csv, outputs/openness_check.json
"""
import json
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from econtypes.mo_directory import mo_key  # noqa: E402


def load(path):
    d = pd.read_excel(path, header=None, engine="openpyxl").iloc[7:70, [1, 11]].dropna()
    d.columns = ["name", "score"]
    d["mo"] = [mo_key(s.replace("город ", "городской округ город ")) if s.startswith("город") else mo_key(s)
               for s in d.name.astype(str).str.strip()]
    return d.set_index("mo").score.astype(float)


def main():
    raw = ROOT / "data/raw/minfin_openness"
    years = {y: load(raw / f"rating_{y}.xlsx") for y in (2023, 2024, 2025) if (raw / f"rating_{y}.xlsx").exists()}
    tab = pd.DataFrame(years)
    tab["open_2023_2024"] = tab[[2023, 2024]].mean(axis=1)
    m = pd.read_csv(ROOT / "outputs/tables/metrics.csv").set_index("mo")
    j = m.join(tab, how="inner")
    res = {"n_mo": int(len(j)), "max_score": 144}
    for col, key in (("open_2023_2024", "train"), (2025, "y2025")):
        if col not in j:
            continue
        groups = [g[col].dropna().values for _, g in j.groupby("cluster")]
        h, p = stats.kruskal(*groups)
        res[key] = dict(kruskal_H=round(float(h), 2), kruskal_p=round(float(p), 4),
                        by_type={k: round(float(v), 1) for k, v in j.groupby("cluster_name")[col].median().items()},
                        spearman={c: dict(zip(("rho", "p"), [round(float(x), 3) for x in stats.spearmanr(j[c], j[col], nan_policy="omit")]))
                                  for c in ("activity", "budget_dep", "demo_resilience", "competition", "localization")})
    tab.rename_axis("mo").round(1).to_csv(ROOT / "outputs/tables/openness_check.csv")
    json.dump(res, open(ROOT / "outputs/openness_check.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
