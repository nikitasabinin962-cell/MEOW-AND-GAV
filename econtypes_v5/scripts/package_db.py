"""Полный снимок базы v5 для скачивания: data/econtypes_v5.sqlite.gz + data/DB_MANIFEST.json.

Снимок делается через backup API SQLite (не копированием открытого WAL-файла), режим журнала
переводится в DELETE, чтобы файл открывался без -wal/-shm. Затем архив распаковывается в
отдельную папку и сверяется: integrity_check, foreign_key_check, число строк в каждой таблице.

  .venv/bin/python scripts/package_db.py                      # снимок и manifest
  .venv/bin/python scripts/package_db.py --url-sha <commit>   # дописать публичные ссылки на этот коммит
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "nikitasabinin962-cell/MEOW-AND-GAV"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def inventory(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    q = lambda s: con.execute(s).fetchall()
    tables = [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    inv = dict(
        integrity_check=q("PRAGMA integrity_check")[0][0],
        foreign_key_violations=len(q("PRAGMA foreign_key_check")),
        journal_mode=q("PRAGMA journal_mode")[0][0],
        schema_version=q("SELECT max(version) FROM schema_migrations")[0][0],
        table_counts={t: q(f'SELECT count(*) FROM "{t}"')[0][0] for t in tables},
        views=[r[0] for r in q("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")],
        indexes=len(q("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")),
        triggers=len(q("SELECT name FROM sqlite_master WHERE type='trigger'")),
        runs=[dict(zip(("run_id", "created_at", "code_hash", "mode"), r)) for r in q("SELECT run_id, created_at, code_hash, mode FROM run ORDER BY created_at")],
    )
    con.close()
    return inv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "econtypes_v5.sqlite"))
    ap.add_argument("--out", default=str(ROOT / "data" / "econtypes_v5.sqlite.gz"))
    ap.add_argument("--manifest", default=str(ROOT / "data" / "DB_MANIFEST.json"))
    ap.add_argument("--url-sha", help="коммит публичного репозитория, где лежит архив; только дописывает ссылки")
    a = ap.parse_args()
    out, mpath = Path(a.out), Path(a.manifest)

    if a.url_sha:
        m = json.loads(mpath.read_text("utf-8"))
        if sha256(out) != m["sha256"]:
            raise SystemExit("архив не совпадает с manifest: сначала пересоберите снимок")
        rel = out.resolve().relative_to(ROOT.parent).as_posix()
        m["url"] = f"https://raw.githubusercontent.com/{REPO}/{a.url_sha}/{rel}"
        m["dictionary_url"] = f"https://github.com/{REPO}/blob/{a.url_sha}/econtypes_v5/docs/DATA_DICTIONARY.md"
        m["published_commit"] = a.url_sha
        mpath.write_text(json.dumps(m, ensure_ascii=False, indent=1), "utf-8")
        print(json.dumps({k: m[k] for k in ("url", "dictionary_url")}, ensure_ascii=False, indent=1))
        return

    run = json.loads((ROOT / "outputs" / "latest" / "RUN_MANIFEST.json").read_text("utf-8"))
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "econtypes_v5.sqlite"
        src = sqlite3.connect(a.db)
        dst = sqlite3.connect(snap)
        src.backup(dst)          # согласованный снимок даже при открытом WAL
        src.close()
        dst.execute("PRAGMA journal_mode=DELETE")
        dst.execute("VACUUM")
        dst.close()
        inv = inventory(snap)
        if inv["integrity_check"] != "ok" or inv["foreign_key_violations"]:
            raise SystemExit(f"снимок не прошёл проверку: {inv['integrity_check']}, FK {inv['foreign_key_violations']}")
        sq_bytes, sq_sha = snap.stat().st_size, sha256(snap)
        with open(snap, "rb") as fi, gzip.GzipFile(out, "wb", compresslevel=9, mtime=0) as fo:
            shutil.copyfileobj(fi, fo, 1 << 20)
        # восстановление в отдельной папке и сверка с исходным снимком
        back = Path(td) / "restored" / "econtypes_v5.sqlite"
        back.parent.mkdir()
        with gzip.open(out, "rb") as fi, open(back, "wb") as fo:
            shutil.copyfileobj(fi, fo, 1 << 20)
        inv_back = inventory(back)
        restore_ok = sha256(back) == sq_sha and inv_back["table_counts"] == inv["table_counts"] and inv_back["integrity_check"] == "ok"
        if not restore_ok:
            raise SystemExit("восстановленная копия не совпала со снимком")

    run_ids = [r["run_id"] for r in inv["runs"]]
    if run["run_id"] not in run_ids:
        raise SystemExit(f"в базе нет прогона {run['run_id']} из outputs/latest")
    m = dict(
        file=out.name, bytes=out.stat().st_size, sha256=sha256(out), compression="gzip -9",
        sqlite_bytes=sq_bytes, sqlite_sha256=sq_sha,
        run_id=run["run_id"], code_hash=run["code_hash"], config_hash=run["config_hash"], data_hash=run["data_hash"], seed=run["seed"],
        schema_version=inv["schema_version"], tables=len(inv["table_counts"]), rows_total=sum(inv["table_counts"].values()),
        table_counts=inv["table_counts"], views=inv["views"], indexes=inv["indexes"], triggers=inv["triggers"],
        integrity_check=inv["integrity_check"], foreign_key_violations=inv["foreign_key_violations"], journal_mode=inv["journal_mode"],
        restore_check="PASS: распаковано в отдельную папку, SHA-256, число строк и integrity_check совпали",
        runs_in_db=inv["runs"], period="контракты 01.01.2023–06.10.2026; типология 2023–2024; проверка вне периода 2025 и 2026 (январь–сентябрь)",
        scope="63 МО Республики Башкортостан, типология 62 МО (ЗАТО Межгорье отдельно)",
        local_path=f"data/{out.name}", url=None, dictionary_url=None,
        restore="gunzip -k econtypes_v5.sqlite.gz  # затем sqlite3 econtypes_v5.sqlite 'PRAGMA integrity_check'",
        not_included="Сырые parquet СберИндекса (в среде отсутствуют), страницы ЕИС, исходные архивы Drive больше 10 МБ; см. docs/DATA_GAPS.md",
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    mpath.write_text(json.dumps(m, ensure_ascii=False, indent=1), "utf-8")
    (out.parent / "SHA256SUMS").write_text(f"{sq_sha}  data/econtypes_v5.sqlite\n{m['sha256']}  data/{out.name}\n", "utf-8")
    print(json.dumps({k: m[k] for k in ("run_id", "bytes", "sha256", "tables", "rows_total", "integrity_check")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
