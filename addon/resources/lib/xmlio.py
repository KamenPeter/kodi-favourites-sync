import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional


class Favourite:
	def __init__(self, label: str, path: str, attrib: Dict[str, str]):
		self.label = (label or "").strip()
		self.path = (path or "").strip()
		# remove name attr duplication if present
		self.attrib = {k: v for k, v in (attrib or {}).items() if k not in {"name"}}

	@property
	def key(self) -> Tuple[str, str]:
		return (self.label, self.path)

	def to_element(self) -> ET.Element:
		el = ET.Element("favourite", attrib={**self.attrib, "name": self.label})
		el.text = self.path
		return el


@dataclass
class FavEntry:
	"""Enhanced favourite entry with type classification"""
	name: str            # raw display name (keep BBCode)
	action: str          # inner text of <favourite>…</favourite>
	thumb: Optional[str] # optional thumb attribute
	type: Optional[str] = None  # 'addon' | 'media_item' | 'media_folder' | 'other'


# BBCode tag removal for normalized comparison
BB_TAG_RE = re.compile(r"\[(?:/?(?:COLOR|B|I|LIGHT)[^\]]*)\]", re.I)

def normalize_title(name: str) -> str:
	"""Remove BBCode tags and normalize for case-insensitive sorting"""
	s = BB_TAG_RE.sub("", name or "").strip()
	return s.casefold()


# Classification regexes
ADDON_RUNADDON_RE  = re.compile(r'^RunAddon\("([^"]+)"\)$', re.I)
ADDON_RUNSCRIPT_RE = re.compile(r'^RunScript\(([^)]+)\)$', re.I)
MEDIA_PLAY_PLUGIN_RE = re.compile(r'^PlayMedia\("plugin://[^"]+"\)$', re.I)
MEDIA_PLAY_URL_RE    = re.compile(r'^PlayMedia\("(?:(?:smb|nfs|ftp|http|https|file)://)[^"]+"\)$', re.I)
MEDIA_FOLDER_RE      = re.compile(r'^ActivateWindow\(\d+,\s*"plugin://[^"]+"[^)]*\)$', re.I)

def classify(entry: FavEntry) -> str:
	"""Classify a favourite entry by its action type"""
	a = entry.action.strip()
	if ADDON_RUNADDON_RE.match(a):
		return "addon"
	if ADDON_RUNSCRIPT_RE.match(a):
		# must reference an addon path to be an addon shortcut
		if "special://home/addons/" in a or "special://xbmc/addons/" in a:
			return "addon"
	if MEDIA_PLAY_PLUGIN_RE.match(a) or MEDIA_PLAY_URL_RE.match(a):
		return "media_item"
	if MEDIA_FOLDER_RE.match(a):
		return "media_folder"
	return "other"


def parse_favourites_xml(xml_bytes: bytes) -> List[FavEntry]:
	"""Parse favourites.xml into FavEntry objects with type classification"""
	if not xml_bytes:
		return []
	root = ET.fromstring(xml_bytes)
	validate_root(root)
	entries: List[FavEntry] = []
	for fav in root.findall("favourite"):
		name = fav.attrib.get("name", "").strip()
		action = (fav.text or "").strip()
		thumb = fav.attrib.get("thumb")
		entry = FavEntry(name=name, action=action, thumb=thumb)
		entry.type = classify(entry)
		entries.append(entry)
	return entries


def serialize_favourites(entries: List[FavEntry]) -> bytes:
	"""Serialize FavEntry objects back to XML format"""
	root = ET.Element("favourites")
	for entry in entries:
		attribs = {"name": entry.name}
		if entry.thumb:
			attribs["thumb"] = entry.thumb
		el = ET.Element("favourite", attrib=attribs)
		el.text = entry.action
		root.append(el)
	return ET.tostring(root, encoding="utf-8")



def validate_root(root: ET.Element) -> None:
	if root.tag != "favourites":
		raise ValueError("Invalid favourites.xml: root must be <favourites>")


def load_xml(data: bytes) -> List[Favourite]:
	if not data:
		return []
	root = ET.fromstring(data)
	validate_root(root)
	favs: List[Favourite] = []
	for fav in root.findall("favourite"):
		label = fav.attrib.get("name", "").strip()
		path = (fav.text or "").strip()
		favs.append(Favourite(label, path, fav.attrib))
	return favs


def serialize(favs: List[Favourite]) -> bytes:
	root = ET.Element("favourites")
	
	# Ensure "Favourites Sync (Cloud)" is always first
	sync_addon = None
	other_favs = []
	
	for f in favs:
		if f.label == "Favourites Sync (Cloud)":
			sync_addon = f
		else:
			other_favs.append(f)
	
	# Add sync addon first if it exists
	if sync_addon:
		root.append(sync_addon.to_element())
	
	# Then add all other favorites
	for f in other_favs:
		root.append(f.to_element())
	
	return ET.tostring(root, encoding="utf-8")


def normalize(favs: List[Favourite]) -> List[Favourite]:
	# dedup by key while preserving first occurrence order
	seen = set()
	out: List[Favourite] = []
	for f in favs:
		if f.key in seen:
			continue
		seen.add(f.key)
		out.append(f)
	return out


def merge_sets(local: List[Favourite], remote: List[Favourite], last_synced: List[Favourite] = None,
			   prefer: str = "newer", local_mtime: float = 0.0, remote_mtime: float = 0.0) -> Tuple[List[Favourite], Dict[str, Any]]:
	"""
	Three-way merge: local, remote, and last_synced states.
	
	prefer can be:
	  - "cloud"  → prefer remote on conflicts
	  - "local"  → prefer local on conflicts
	  - "newer"  → pick source with newer file mtime

	Returns: (merged_list, stats={'added':int,'changed':int,'removed':int, 'added_items':list, 'changed_items':list, 'removed_items':list})
	"""
	stats = {"added": 0, "changed": 0, "removed": 0, "added_items": [], "changed_items": [], "removed_items": []}
	
	# Build indices for all three states
	idx_local = {f.key: f for f in local}
	idx_remote = {f.key: f for f in remote}
	idx_last = {f.key: f for f in (last_synced or [])}
	
	# Get union of ALL keys from all three sources
	all_keys = set(idx_local.keys()) | set(idx_remote.keys()) | set(idx_last.keys())

	merged: List[Favourite] = []
	
	for key in all_keys:
		in_last = key in idx_last
		in_local = key in idx_local
		in_remote = key in idx_remote
		
		# Decision matrix for three-way merge
		
		if in_last and not in_local and in_remote:
			# DELETION DETECTED: Item was synced before, deleted locally, still on remote
			# Propagate the deletion (don't add to merged list)
			stats["removed"] += 1
			stats["removed_items"].append(key[0])  # label/name
			continue
		
		if in_last and in_local and not in_remote:
			# Remote deleted, local kept - keep local (will be pushed to remote)
			merged.append(idx_local[key])
			stats["added"] += 1
			stats["added_items"].append(key[0])
			continue
		
		if in_last and not in_local and not in_remote:
			# Both deleted - nothing to do
			continue
		
		if not in_last and in_local and in_remote:
			# New item on both sides - resolve conflict
			if (idx_local[key].attrib != idx_remote[key].attrib):
				chosen = idx_remote[key]
				if prefer == "local":
					chosen = idx_local[key]
				elif prefer == "newer":
					chosen = idx_remote[key] if remote_mtime >= local_mtime else idx_local[key]
				stats["changed"] += 1
				stats["changed_items"].append(key[0])
				merged.append(chosen)
			else:
				merged.append(idx_local[key])  # identical
			continue
		
		if not in_last and in_local and not in_remote:
			# New item added locally
			merged.append(idx_local[key])
			stats["added"] += 1
			stats["added_items"].append(key[0])
			continue
		
		if not in_last and not in_local and in_remote:
			# New item added remotely
			merged.append(idx_remote[key])
			stats["added"] += 1
			stats["added_items"].append(key[0])
			continue
		
		if in_last and in_local and in_remote:
			# Item exists in all three - check for modifications
			if (idx_local[key].attrib != idx_remote[key].attrib):
				# Conflict: both modified
				chosen = idx_remote[key]
				if prefer == "local":
					chosen = idx_local[key]
				elif prefer == "newer":
					chosen = idx_remote[key] if remote_mtime >= local_mtime else idx_local[key]
				stats["changed"] += 1
				stats["changed_items"].append(key[0])
				merged.append(chosen)
			else:
				# No changes or identical
				merged.append(idx_local[key])
			continue
	
	# Dedup and stable order by label/path
	merged = normalize(merged)
	return merged, stats

