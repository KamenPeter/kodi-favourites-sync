import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Any


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
	for f in favs:
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


def merge_sets(local: List[Favourite], remote: List[Favourite], prefer: str = "newer",
			   local_mtime: float = 0.0, remote_mtime: float = 0.0) -> Tuple[List[Favourite], Dict[str, Any]]:
	"""
	Merge by key=(label,path). prefer can be:
	  - "cloud"  → prefer remote on conflicts
	  - "local"  → prefer local on conflicts
	  - "newer"  → pick source with newer file mtime

	Returns: (merged_list, stats={'added':int,'changed':int,'removed':int, 'added_items':list, 'changed_items':list, 'removed_items':list})
	"""
	stats = {"added": 0, "changed": 0, "removed": 0, "added_items": [], "changed_items": [], "removed_items": []}
	idx_local = {f.key: f for f in local}
	idx_remote = {f.key: f for f in remote}
	keys = list(dict.fromkeys([*idx_local.keys(), *idx_remote.keys()]).keys())  # stable union

	merged: List[Favourite] = []
	for k in keys:
		l = idx_local.get(k)
		r = idx_remote.get(k)
		if l and r:
			# If attribs differ, resolve by policy
			if (l.attrib != r.attrib):
				chosen = r
				if prefer == "local":
					chosen = l
				elif prefer == "newer":
					chosen = r if remote_mtime >= local_mtime else l
				stats["changed"] += 1
				stats["changed_items"].append(k[0])  # label/name
				merged.append(chosen)
			else:
				merged.append(l)  # identical
		elif l and not r:
			merged.append(l)
			stats["added"] += 1
			stats["added_items"].append(k[0])  # label/name
		elif r and not l:
			merged.append(r)
			stats["added"] += 1
			stats["added_items"].append(k[0])  # label/name
	# Dedup and stable order by label/path
	merged = normalize(merged)
	return merged, stats

