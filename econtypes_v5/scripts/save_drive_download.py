"""Декодирует сохранённый ответ Google Drive MCP download_file_content (JSON с base64) в исходный файл
и дописывает запись в манифест внешних источников (SHA-256 исходных байтов, размер, Drive id, время).
Использование: python scripts/save_drive_download.py PERSISTED_JSON OUT_DIR [--expected-size N] [--note TEXT]
"""
import argparse, base64, datetime as dt, hashlib, json, pathlib

ap = argparse.ArgumentParser()
ap.add_argument("persisted")
ap.add_argument("outdir")
ap.add_argument("--expected-size", type=int)
ap.add_argument("--note", default="")
a = ap.parse_args()
d = json.loads(pathlib.Path(a.persisted).read_text())
raw = base64.b64decode(d["content"])
if a.expected_size is not None and len(raw) != a.expected_size:
    raise SystemExit(f"size mismatch: {len(raw)} != {a.expected_size}")
out = pathlib.Path(a.outdir)
out.mkdir(parents=True, exist_ok=True)
name = d["title"].replace("/", "_")
p = out / name
if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() != hashlib.sha256(raw).hexdigest():
    raise SystemExit(f"{p} exists with different content; not overwriting")
p.write_bytes(raw)
man = out / "DRIVE_DOWNLOADS.jsonl"
rec = dict(file=name, drive_id=d["id"], mime=d.get("mimeType"), size_bytes=len(raw),
           sha256=hashlib.sha256(raw).hexdigest(), retrieved_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           channel="Google Drive MCP download_file_content (base64), owner nikitasabinin962@gmail.com", note=a.note)
existing = [json.loads(l) for l in man.read_text().splitlines()] if man.exists() else []
if not any(r["sha256"] == rec["sha256"] and r["file"] == rec["file"] for r in existing):
    with man.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(json.dumps(rec, ensure_ascii=False))
