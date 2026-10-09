"""Идемпотентность ingest: два прохода сборки по одной базе дают одинаковое содержимое таблиц L0–L1.
Результат: outputs/IDEMPOTENCY_CHECK.json (PASS/FAIL по каждой таблице)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from econtypes5 import db as DB, ingest as ING  # noqa: E402

TABLES = {"source_registry": "source_id", "mo": "mo_id", "fact_mo": "mo_id, indicator, period, source_id",
          "fact_region_control": "indicator, period, source_id", "contract": "canonical_contract_id",
          "tax_office_map": "code", "org_geo_resolved": "inn, kpp, role", "org_geo_evidence": "inn, kpp, role, method",
          "msp_firm": "inn, snapshot_date", "msp_index_firm": "inn, snapshot_date"}
VOLATILE = {"source_registry"}  # retrieved_at для research DB = время сборки; сравниваем без него

research = ROOT.parent / "econtypes_research_20261009.sqlite"
tmp = Path(tempfile.mkdtemp(dir=ROOT / "data"))
db = tmp / "idem.sqlite"
try:
    ING.build(research, db)
    con = DB.connect(db)
    d1 = {t: DB.table_digest(con, t if t not in VOLATILE else "(SELECT source_id, sha256, size_bytes, relative_path FROM source_registry)", o) for t, o in TABLES.items()}
    n1 = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    con.close()
    ING.build(research, db)   # второй проход по той же базе
    con = DB.connect(db)
    d2 = {t: DB.table_digest(con, t if t not in VOLATILE else "(SELECT source_id, sha256, size_bytes, relative_path FROM source_registry)", o) for t, o in TABLES.items()}
    n2 = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    con.close()
    res = {t: dict(rows_first=n1[t], rows_second=n2[t], identical=d1[t] == d2[t]) for t in TABLES}
    out = dict(status="PASS" if all(v["identical"] for v in res.values()) else "FAIL", tables=res)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
(ROOT / "outputs/IDEMPOTENCY_CHECK.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(out["status"], {t: v["identical"] for t, v in res.items()})
