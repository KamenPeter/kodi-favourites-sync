#!/usr/bin/env python3
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_DIR = ROOT / 'repository.kamen'
REPO_ROOT = ROOT / 'repo-root' / 'repository.kamen'
REPO_ROOT.mkdir(parents=True, exist_ok=True)

zip_path = REPO_ROOT / 'repository.kamen-1.0.0.zip'
print(f"Building {zip_path} ...")
with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    base = 'repository.kamen'
    for path in REPO_DIR.rglob('*'):
        if path.is_dir():
            continue
        rel = path.relative_to(REPO_DIR)
        z.write(path, f"{base}/{rel}")
print("Done.")
