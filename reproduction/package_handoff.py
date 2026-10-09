"""Pack the verified handoff without changing source files."""
from pathlib import Path
import hashlib,json,zipfile

root=Path(__file__).resolve().parent.parent
out=root.parent/(root.name+'.zip')
if out.exists():raise FileExistsError(f'Archive already exists: {out}')
files=[]
for p in sorted(root.rglob('*')):
    if not p.is_file():continue
    rel=p.relative_to(root)
    if any(x in {'__pycache__','.pytest_cache'} for x in rel.parts):continue
    if rel.parts[0].startswith('.econtypes_research_20261009.sqlite.'):continue
    files.append(p)
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
    for p in files:z.write(p,Path(root.name)/p.relative_to(root))
with zipfile.ZipFile(out) as z:
    bad=z.testzip()
    if bad:raise RuntimeError(f'CRC check failed: {bad}')
    assert root.name+'/econtypes_research_20261009.sqlite' in z.namelist()
    assert root.name+'/ECONTYPES_Audit_and_Methods_20261009.docx' in z.namelist()
print(json.dumps({'archive':str(out),'files':len(files),'bytes':out.stat().st_size,'uncompressed_bytes':sum(p.stat().st_size for p in files),'CRC':'PASS'},ensure_ascii=False),flush=True)
