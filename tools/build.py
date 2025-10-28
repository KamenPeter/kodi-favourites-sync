#!/usr/bin/env python3
import os
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / 'dist'
REPO_ROOT = ROOT / 'repo-root'
ADDON_SOURCES = [
    ROOT / 'addon',
    ROOT / 'runner',
]


def build_addon(addon_dir: Path) -> None:
    import xml.etree.ElementTree as ET

    addon_xml = ET.parse(addon_dir / 'addon.xml').getroot()
    addon_id = addon_xml.attrib['id']
    version = addon_xml.attrib['version']

    zip_name = f"{addon_id}-{version}.zip"
    zip_path = DIST_DIR / zip_name

    print(f"Building {zip_path} ...")

    # Patterns to exclude
    EXCLUDE_PATTERNS = ['__pycache__', '.pyc', '.pyo', '.git', '.DS_Store', 'Thumbs.db']
    
    def should_exclude(path: Path) -> bool:
        """Check if path should be excluded from ZIP"""
        path_str = str(path)
        for pattern in EXCLUDE_PATTERNS:
            if pattern in path_str:
                return True
        return False

    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        base_folder_name = addon_id  # top-level folder must match addon id
        for path in addon_dir.rglob('*'):
            if path.is_dir():
                continue
            if should_exclude(path):
                continue
            rel = path.relative_to(addon_dir)
            arc = str(Path(base_folder_name) / rel)
            z.write(path, arc)

    print(f"Wrote: {zip_path}")

    addon_repo_dir = REPO_ROOT / addon_id
    addon_repo_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zip_path, addon_repo_dir / zip_name)
    print(f"Copied to: {addon_repo_dir / zip_name}")


def main() -> None:
    DIST_DIR.mkdir(exist_ok=True)
    for source_dir in ADDON_SOURCES:
        if not source_dir.exists():
            continue
        build_addon(source_dir)
    print("Done.")


if __name__ == "__main__":
    main()
