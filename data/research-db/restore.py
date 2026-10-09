"""Restore the original research SQLite without Git LFS; Python stdlib only."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import tempfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=root / manifest['database'])
a = parser.parse_args()
destination = a.out.resolve()
if destination.exists():
    with destination.open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    if actual == manifest['sqlite_sha256']:
        print('Already restored:', destination)
        raise SystemExit(0)
    raise SystemExit('Existing output differs; choose another --out path')
for entry in manifest['files']:
    path = root / entry['file']
    with path.open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    if path.stat().st_size != entry['bytes'] or actual != entry['sha256']:
        raise SystemExit('Archive checksum mismatch: ' + entry['file'])
destination.parent.mkdir(parents=True, exist_ok=True)
# Temporary files are in the output filesystem so the final rename is atomic.
compressed = tempfile.NamedTemporaryFile(dir=destination.parent, delete=False)
output = tempfile.NamedTemporaryFile(dir=destination.parent, delete=False)
try:
    with compressed:
        for entry in manifest['files']:
            with (root / entry['file']).open('rb') as f:
                for block in iter(lambda: f.read(1 << 20), b''):
                    compressed.write(block)
    digest = hashlib.sha256()
    with output, gzip.open(compressed.name, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)
            output.write(block)
    if digest.hexdigest() != manifest['sqlite_sha256'] or Path(output.name).stat().st_size != manifest['sqlite_bytes']:
        raise SystemExit('Restored database checksum mismatch')
    os.replace(output.name, destination)
    print('Restored:', destination)
    print('SHA-256:', digest.hexdigest())
finally:
    compressed.close()
    output.close()
    Path(compressed.name).unlink(missing_ok=True)
    Path(output.name).unlink(missing_ok=True)
