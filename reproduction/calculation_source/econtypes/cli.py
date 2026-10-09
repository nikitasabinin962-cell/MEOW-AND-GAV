"""Командная строка econtypes.

    econtypes ingest                 загрузить исходные файлы из config.yaml в базу (raw_*)
    econtypes add-eis ПАПКА ГОД      склеить новую выгрузку ЕИС и подключить её (обучение или --holdout)
    econtypes run                    сети, кластеризация, ICVI, динамика → res_*
    econtypes validate               проверка типов на закупках вне периода обучения
    econtypes metrics                индексы МО (локализация, конкуренция, хаб, ...)
    econtypes explain                ML-объяснение типов, аналоги и ориентиры
    econtypes correlate              корреляции, частные корреляции, лаги
    econtypes report                 выводы по региону и карточки МО с рекомендациями
    econtypes geo                    границы МО для карты (geoBoundaries / OSM)
    econtypes dashboard              интерактивный дашборд с картой (outputs/dashboard.html)
    econtypes figures | landing      рисунки и лендинг
    econtypes all                    всё по порядку (ingest → … → dashboard)
    econtypes db                     список таблиц базы и число строк
    econtypes sql "SELECT ..."       произвольный запрос к базе

Общие флаги: --config (по умолчанию config/config.yaml), --db (строка подключения SQLAlchemy).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

import pandas as pd
import yaml

from . import db

STEPS = ["ingest", "run", "validate", "metrics", "explain", "correlate", "report", "geo", "figures", "landing", "dashboard"]


def _do(step: str, cfg: dict, eng, a) -> None:
    t0 = time.time()
    print(f"== {step}")
    if step == "ingest":
        from .ingest import ingest
        print(ingest(cfg, eng).to_string(index=False))
    elif step == "run":
        from .pipeline import run
        run(cfg, eng)
    elif step == "validate":
        from .validate import validate
        r = validate(cfg, eng)
        print(json.dumps({y: round(h["accuracy"], 3) for y, h in r["holdout"].items()}, ensure_ascii=False),
              "случайно:", round(r["chance_mean"], 3))
    elif step == "metrics":
        from .metrics import compute
        m = compute(cfg, eng)
        print(m.filter(like="_pct").describe().loc[["mean", "min", "max"]].round(1).to_string())
    elif step == "explain":
        from .explain import run
        r = run(cfg, eng)
        print(f"LOO-точность {r['loo_accuracy']:.2f} (базовая {r['majority_baseline']:.2f})")
    elif step == "correlate":
        from .correlations import run
        r = run(cfg, eng)
        print(f"пар {r['n_pairs']}, значимых после FDR {r['n_sig']}, устойчивых к контролю размера {r['n_partial_sig']}")
    elif step == "report":
        from .report import run
        c = run(cfg, eng)
        print(f"карточек МО: {len(c)} → {cfg['paths']['outputs']}/mo_reports.md, conclusions.md")
    elif step == "geo":
        from .geo import build
        print(build(cfg, db.read(eng, "res_clusters").mo.tolist()))
    elif step == "figures":
        from .figures import make
        make(cfg)
    elif step == "landing":
        from .landing import build
        build(cfg)
    elif step == "dashboard":
        from .dashboard import build
        print(build(cfg, eng))
    print(f"   {time.time() - t0:.0f} с")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="econtypes", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config/config.yaml")
    ap.add_argument("--db", default=None, help="строка подключения SQLAlchemy (перекрывает config)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for s in STEPS + ["all", "db"]:
        sub.add_parser(s)
    p = sub.add_parser("add-eis"); p.add_argument("folder"); p.add_argument("year")
    p.add_argument("--holdout", action="store_true", help="использовать год только для проверки")
    p = sub.add_parser("sql"); p.add_argument("query")
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    from . import region
    region.configure(cfg)
    if a.db:
        cfg["database"]["url"] = a.db
    eng = db.engine(cfg["database"]["url"])

    if a.cmd == "all":
        for s in STEPS:
            _do(s, cfg, eng, a)
    elif a.cmd == "db":
        print(db.summary(eng).to_string(index=False))
    elif a.cmd == "sql":
        pd.set_option("display.width", 200)
        print(pd.read_sql(a.query, eng).to_string(index=False))
    elif a.cmd == "add-eis":
        from .ingest import merge_eis_folder
        path = f"{cfg['paths']['raw']}/eis_{a.year}.parquet"
        print(merge_eis_folder(a.folder, path).to_string())
        if a.holdout:
            cfg["data"].setdefault("eis_holdout", {})[str(a.year)] = path
        elif path not in cfg["data"]["eis_files"]:
            cfg["data"]["eis_files"].append(path)
        yaml.safe_dump(cfg, open(a.config, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
        print(f"добавлено в {a.config}; дальше: econtypes all")
    else:
        _do(a.cmd, cfg, eng, a)


if __name__ == "__main__":
    sys.exit(main())
