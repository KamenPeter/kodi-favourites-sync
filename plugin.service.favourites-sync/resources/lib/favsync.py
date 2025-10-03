import time
import xml.etree.ElementTree as ET
from xml.dom import minidom

import xbmc
import xbmcvfs

LOGTAG = "[FavSync] "

def log(msg, level=xbmc.LOGINFO, debug=False):
    if debug:
        xbmc.log(LOGTAG + str(msg), level)
    else:
        xbmc.log(LOGTAG + str(msg), xbmc.LOGINFO)

def read_text(path):
    if not xbmcvfs.exists(path):
        return None
    f = xbmcvfs.File(path, 'r')
    try:
        data = f.read().decode('utf-8') if isinstance(f.read(0), bytes) else f.read()
    finally:
        f.close()
    return data

def write_text(path, text):
    # Ensure parent dir exists if VFS supports it (best effort)
    _ = xbmcvfs.mkdirs(path.rsplit('/', 1)[0]) if '/' in path else None
    f = xbmcvfs.File(path, 'w')
    try:
        if isinstance(text, str):
            f.write(bytearray(text, 'utf-8'))
        else:
            f.write(text)
    finally:
        f.close()

def stat_mtime(path):
    try:
        st = xbmcvfs.Stat(path)
        # st_mtime returns seconds since epoch (float)
        return st.st_mtime()
    except Exception:
        return 0.0

def parse_favourites(xml_text):
    """
    Returns: (root_element, list_of_items)
    Each item as a dict:
      {
        "name": attr name or "",
        "thumb": attr thumb or "",
        "type": attr type or "",
        "action": inner text (the Kodi command),
        "raw": original Element
      }
    """
    if not xml_text:
        # empty root
        root = ET.Element("favourites")
        return root, []

    root = ET.fromstring(xml_text)
    items = []
    for fav in root.findall('favourite'):
        items.append({
            "name": fav.get('name', '') or '',
            "thumb": fav.get('thumb', '') or '',
            "type": fav.get('type', '') or '',
            "action": (fav.text or '').strip(),
            "raw": fav
        })
    return root, items

def canonical_key(item):
    # A robust identity for duplicates: Kodi command + type + name (+thumb if present)
    # This balances distinct items with same label but different targets.
    return "||".join([item["action"], item["type"], item["name"], item["thumb"]])

def pretty_xml(elem):
    rough = ET.tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8')

def build_root_from_items(items):
    root = ET.Element("favourites")
    for it in items:
        fav = ET.Element("favourite")
        if it["name"]:
            fav.set("name", it["name"])
        if it["thumb"]:
            fav.set("thumb", it["thumb"])
        if it["type"]:
            fav.set("type", it["type"])
        fav.text = it["action"]
        root.append(fav)
    return root

def merge(local_items, nas_items, local_mtime, nas_mtime):
    """
    Merge rules:
      - Union of keys from both sets.
      - If key appears in both with different bodies, pick the version from the file
        that has the OLDER mtime (as requested).
      - If same, keep either.
    Returns merged_items list (no duplicates), plus booleans indicating whether NAS and Local changed.
    """
    # Map keys
    local_map = {canonical_key(i): i for i in local_items}
    nas_map   = {canonical_key(i): i for i in nas_items}

    all_keys = set(local_map) | set(nas_map)
    merged = []
    for k in sorted(all_keys):  # deterministic order
        l = local_map.get(k)
        n = nas_map.get(k)
        if l and n:
            # Present in both. Compare bodies just in case they differ (extremely rare with our key).
            # If anything differs, choose from OLDER file timestamp
            if (l["action"], l["type"], l["name"], l["thumb"]) != (n["action"], n["type"], n["name"], n["thumb"]):
                pick = l if local_mtime < nas_mtime else n
                merged.append(pick)
            else:
                merged.append(l)
        elif l:
            merged.append(l)
        else:
            merged.append(n)

    # Normalize & remove accidental dupes by key (shouldn’t happen, but safe)
    uniq = {}
    for it in merged:
        uniq[canonical_key(it)] = it
    merged_items = list(uniq.values())

    # Determine if each side needs update
    merged_keys = set(uniq.keys())
    local_keys  = set(local_map.keys())
    nas_keys    = set(nas_map.keys())

    local_changed = (merged_keys != local_keys)
    nas_changed   = (merged_keys != nas_keys)

    return merged_items, local_changed, nas_changed

def sync(nas_path, debug=False, dry_run=False):
    profile_path = "special://profile/favourites.xml"

    # Read both files
    local_xml = read_text(profile_path)
    nas_xml   = read_text(nas_path)

    # If neither exists, nothing to do
    if not local_xml and not nas_xml:
        log("No favourites found on Local or NAS. Creating empty files.", debug=debug)
        if not dry_run:
            empty = pretty_xml(ET.Element("favourites"))
            write_text(profile_path, empty)
            write_text(nas_path, empty)
        return True

    # Parse
    _, local_items = parse_favourites(local_xml or "")
    _, nas_items   = parse_favourites(nas_xml or "")

    local_mtime = stat_mtime(profile_path)
    nas_mtime   = stat_mtime(nas_path)

    log(f"Local items: {len(local_items)}, NAS items: {len(nas_items)}", debug=debug)
    log(f"Local mtime: {local_mtime}, NAS mtime: {nas_mtime}", debug=debug)

    merged_items, local_changed, nas_changed = merge(local_items, nas_items, local_mtime, nas_mtime)

    log(f"Merged items: {len(merged_items)}", debug=debug)
    log(f"Local changed: {local_changed}, NAS changed: {nas_changed}", debug=debug)

    if not (local_changed or nas_changed):
        log("Favourites already in sync.", debug=debug)
        return True

    merged_root = build_root_from_items(merged_items)
    merged_xml  = pretty_xml(merged_root)

    # Always keep local up-to-date
    if local_changed:
        if dry_run:
            log("Dry-run: would write merged favourites to LOCAL", debug=debug)
        else:
            write_text(profile_path, merged_xml)
            log("Wrote merged favourites to LOCAL.")

    # Write back to NAS only if NAS needs new parts/changes
    if nas_changed:
        if dry_run:
            log("Dry-run: would write merged favourites to NAS", debug=debug)
        else:
            write_text(nas_path, merged_xml)
            log("Wrote merged favourites to NAS.")

    return True
