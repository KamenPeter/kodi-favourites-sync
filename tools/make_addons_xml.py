#!/usr/bin/env python3
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT / 'repo-root'

# Scan repo-root/*/*.zip and embed addon.xml content for each zip
addons = []

SOURCE_MAP = {
    'plugin.service.favourites-sync': ROOT / 'addon' / 'addon.xml',
    'plugin.program.favourites-sync': ROOT / 'runner' / 'addon.xml',
    'repository.kamen': ROOT / 'repository.kamen' / 'addon.xml',
}

for addon_dir in sorted(REPO_ROOT.iterdir()):
    if not addon_dir.is_dir():
        continue
    zips = sorted(addon_dir.glob('*.zip'))
    if not zips:
        continue
    src_addon_xml = SOURCE_MAP.get(addon_dir.name)
    if not src_addon_xml:
        continue
    if not src_addon_xml.exists():
        continue
    addons.append(src_addon_xml.read_text(encoding='utf-8'))

addons_xml = "<?xml version='1.0' encoding='UTF-8'?>\n<addons>\n" + "\n".join(addons) + "\n</addons>\n"

(REPO_ROOT / 'addons.xml').write_text(addons_xml, encoding='utf-8')
md5 = hashlib.md5(addons_xml.encode('utf-8')).hexdigest()
(REPO_ROOT / 'addons.xml.md5').write_text(md5 + "\n", encoding='utf-8')

print("Generated:", REPO_ROOT / 'addons.xml')
print("Generated:", REPO_ROOT / 'addons.xml.md5')
