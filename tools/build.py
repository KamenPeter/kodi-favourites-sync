#!/usr/bin/env python3
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / 'addon'
DIST_DIR = ROOT / 'dist'
REPO_ROOT = ROOT / 'repo-root'

# Read version from addon.xml
import xml.etree.ElementTree as ET
addon_xml = ET.parse(ADDON_DIR / 'addon.xml').getroot()
addon_id = addon_xml.attrib['id']
version = addon_xml.attrib['version']

zip_name = f"{addon_id}-{version}.zip"
DIST_DIR.mkdir(exist_ok=True)

zip_path = DIST_DIR / zip_name

# Create zip with top-level folder named after addon dir (plugin.service.favourites-sync)

print(f"Building {zip_path} ...")

with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    # Kodi requires the top-level folder in the zip to be the add-on ID
    base_folder_name = addon_id
    for path in ADDON_DIR.rglob('*'):
        if path.is_dir():
            continue
        rel = path.relative_to(ADDON_DIR)
        arc = str(Path(base_folder_name) / rel)
        z.write(path, arc)

print(f"Wrote: {zip_path}")

# Copy to repo-root/plugin.service.favourites-sync/
addon_repo_dir = REPO_ROOT / addon_id
addon_repo_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(zip_path, addon_repo_dir / zip_name)
print(f"Copied to: {addon_repo_dir / zip_name}")

print("Done.")
