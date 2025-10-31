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
	Three-way merge: local, remote, and last_synced (BASE) states.
	
	This implements proper 3-way merge to handle deletions correctly:
	- If item exists in BASE but deleted locally → propagate deletion to remote
	- If item exists in BASE but deleted remotely → propagate deletion to local
	- If item added on both sides → merge (no conflict)
	- If item modified on both sides → resolve using prefer policy
	
	prefer can be:
	  - "cloud"  → prefer remote on conflicts
	  - "local"  → prefer local on conflicts
	  - "newer"  → pick source with newer file mtime

	Returns: (merged_list, stats={'added':int,'changed':int,'removed':int, 'added_items':list, 'changed_items':list, 'removed_items':list})
	"""
	stats = {"added": 0, "changed": 0, "removed": 0, "added_items": [], "changed_items": [], "removed_items": [], "merge_decisions": []}
	
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
		
		label = key[0]  # Extract label for logging
		
		# Decision matrix for three-way merge
		
		if in_last and not in_local and in_remote:
			# DELETION DETECTED: Item was synced before, deleted locally, still on remote
			# Propagate the deletion (don't add to merged list)
			stats["removed"] += 1
			stats["removed_items"].append(label)
			stats["merge_decisions"].append(f"DELETE: {label} (deleted locally, removing from remote)")
			continue
		
		if in_last and in_local and not in_remote:
			# Remote deleted, local kept - propagate remote deletion
			# This prevents deleted items from reappearing
			stats["removed"] += 1
			stats["removed_items"].append(label)
			stats["merge_decisions"].append(f"DELETE: {label} (deleted remotely, removing from local)")
			continue
		
		if in_last and not in_local and not in_remote:
			# Both deleted - nothing to do
			stats["merge_decisions"].append(f"SKIP: {label} (deleted on both sides)")
			continue
		
		if not in_last and in_local and in_remote:
			# New item on both sides - check if identical or conflict
			if (idx_local[key].attrib != idx_remote[key].attrib):
				# Different attributes - resolve conflict
				chosen = idx_remote[key]
				if prefer == "local":
					chosen = idx_local[key]
				elif prefer == "newer":
					chosen = idx_remote[key] if remote_mtime >= local_mtime else idx_local[key]
				stats["changed"] += 1
				stats["changed_items"].append(label)
				stats["merge_decisions"].append(f"CONFLICT: {label} (added on both, chose {prefer})")
				merged.append(chosen)
			else:
				# Identical additions
				merged.append(idx_local[key])
				stats["added"] += 1
				stats["added_items"].append(label)
				stats["merge_decisions"].append(f"ADD: {label} (added identically on both sides)")
			continue
		
		if not in_last and in_local and not in_remote:
			# New item added locally only
			merged.append(idx_local[key])
			stats["added"] += 1
			stats["added_items"].append(label)
			stats["merge_decisions"].append(f"ADD: {label} (new local item)")
			continue
		
		if not in_last and not in_local and in_remote:
			# New item added remotely only
			merged.append(idx_remote[key])
			stats["added"] += 1
			stats["added_items"].append(label)
			stats["merge_decisions"].append(f"ADD: {label} (new remote item)")
			continue
		
		if in_last and in_local and in_remote:
			# Item exists in all three - check for modifications
			local_changed = (idx_local[key].attrib != idx_last[key].attrib)
			remote_changed = (idx_remote[key].attrib != idx_last[key].attrib)
			
			if local_changed and remote_changed:
				# Both modified - conflict
				chosen = idx_remote[key]
				if prefer == "local":
					chosen = idx_local[key]
				elif prefer == "newer":
					chosen = idx_remote[key] if remote_mtime >= local_mtime else idx_local[key]
				stats["changed"] += 1
				stats["changed_items"].append(label)
				stats["merge_decisions"].append(f"CONFLICT: {label} (modified on both, chose {prefer})")
				merged.append(chosen)
			elif local_changed:
				# Only local modified
				merged.append(idx_local[key])
				stats["changed"] += 1
				stats["changed_items"].append(label)
				stats["merge_decisions"].append(f"UPDATE: {label} (local modification)")
			elif remote_changed:
				# Only remote modified
				merged.append(idx_remote[key])
				stats["changed"] += 1
				stats["changed_items"].append(label)
				stats["merge_decisions"].append(f"UPDATE: {label} (remote modification)")
			else:
				# No changes - keep as is
				merged.append(idx_local[key])
				stats["merge_decisions"].append(f"KEEP: {label} (unchanged)")
			continue
	
	# Dedup and stable order by label/path
	merged = normalize(merged)
	return merged, stats


def append_favourite_to_profile(profile_name: str, label: str, action: str, thumb: str = None) -> bool:
	"""
	Append a favourite entry to a specific profile's favourites.xml.
	
	Args:
		profile_name: Name of the Kodi profile
		label: Display name for the favourite
		action: Action string (e.g., PlayMedia(...), RunAddon(...))
		thumb: Optional thumbnail URL
		
	Returns:
		bool: True if successful, False otherwise
	"""
	try:
		# Import profiles_mgr to get profile path
		try:
			from .profiles_mgr import profile_favourites_path
			from .logutil import log_info, log_error, kvfmt
		except ImportError:
			from profiles_mgr import profile_favourites_path
			from logutil import log_info, log_error, kvfmt
		
		import os
		import time
		
		fav_path = profile_favourites_path(profile_name)
		
		# Load existing favourites
		if os.path.exists(fav_path):
			with open(fav_path, "rb") as f:
				xml_bytes = f.read()
			existing = load_xml(xml_bytes)
		else:
			existing = []
		
		# Create new favourite
		attrib = {}
		if thumb:
			attrib["thumb"] = thumb
		
		new_fav = Favourite(label=label, path=action, attrib=attrib)
		
		# Check for duplicates (same key)
		key = new_fav.key
		for fav in existing:
			if fav.key == key:
				log_info(kvfmt(event="append_favourite_duplicate", profile=profile_name, label=label))
				return True  # Already exists, no need to add
		
		# Append to list
		existing.append(new_fav)
		
		# Serialize
		updated_xml = serialize(normalize(existing))
		
		# Create backup
		if os.path.exists(fav_path):
			backup_name = f"favourites_{time.strftime('%Y%m%d-%H%M%S')}.xml.bak"
			backup_dir = os.path.dirname(fav_path)
			# Use addon_data for backups
			addon_data_backup_dir = fav_path.replace("favourites.xml", "addon_data/plugin.service.favourites-sync/")
			if not os.path.exists(addon_data_backup_dir):
				os.makedirs(addon_data_backup_dir, exist_ok=True)
			backup_path = os.path.join(addon_data_backup_dir, backup_name)
			
			try:
				import shutil
				shutil.copy2(fav_path, backup_path)
			except Exception:
				pass  # Backup is optional
		
		# Atomic write
		tmp_path = fav_path + ".tmp"
		with open(tmp_path, "wb") as f:
			f.write(updated_xml)
		
		if os.path.exists(fav_path):
			os.remove(fav_path)
		os.rename(tmp_path, fav_path)
		
		log_info(kvfmt(event="append_favourite_success", profile=profile_name, label=label, action=action))
		return True
		
	except Exception as e:
		try:
			from .logutil import log_error, kvfmt
		except ImportError:
			from logutil import log_error, kvfmt
		log_error(kvfmt(event="append_favourite_error", profile=profile_name, error=str(e)))
		return False
