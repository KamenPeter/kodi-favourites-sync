**Part 1** (Misc settings + favourites reordering, and removing duplicate menu options). 

---

# 0) Scope (what to build now)

* Add **Settings → Miscellaneous** with new options.
* Implement **detection & ordering** of all **add-on shortcuts** in `favourites.xml`.
* Ensure this add-on can be **added to favourites** and optionally **kept first**.
* **Remove menu options** that duplicated these features.
* Safe writes (backup + atomic), no profile reload in automatic contexts.
* Provide a **Manual order editor** for add-ons only.

---

# 1) Files to touch / create

* `addon/resources/settings.xml` (add new settings)
* `addon/resources/lib/settings_mgr.py` (expose new settings)
* `addon/resources/lib/xmlio.py` (parse, classify, serialize favourites)
* `addon/resources/lib/sync.py` (reorder pipeline + ensure-first logic + backups)
* `addon/resources/lib/addon.py` (remove menu items, optionally add “Reorder now” action)
* `addon/resources/lib/logutil.py` (log events)
* **NEW**: `addon/resources/lib/ui_manual_order.py` (manual order dialog)
* **NEW**: `special://profile/addon_data/<id>/favourites_order.json` (persist manual order)

> Keep the **no profile reload** rule in automatic/scheduled contexts.

---

# 2) Settings — concrete schema (insert into `resources/settings.xml`)

Add a **new category** after Logging:

```xml
<category id="misc" label="Miscellaneous">
  <setting id="misc_add_to_fav" type="bool" label="Add this add-on to Favourites" default="false"/>
  <setting id="misc_keep_first" type="bool" label="Keep as first (if present)" default="false" visible="eq(-1,true)"/>
  <setting id="misc_group_addons_top" type="bool" label="Group add-ons at top" default="false"/>
  <setting id="misc_sort_addons" type="enum" label="Sort add-ons by" lvalues="None|A→Z|Z→A|Manual" default="0"/>
  <setting id="misc_manual_order" type="action" label="Manual order editor…" visible="eq(-1,3)" option="close"/>
  <!-- Optional: run once -->
  <setting id="misc_run_reorder_now" type="action" label="Reorder favourites now" option="close"/>
</category>
```

---

# 3) Settings accessors (`settings_mgr.py`)

Add getters:

```python
def misc_add_to_fav() -> bool: return ADDON.getSettingBool("misc_add_to_fav")
def misc_keep_first() -> bool: return ADDON.getSettingBool("misc_keep_first")
def misc_group_addons_top() -> bool: return ADDON.getSettingBool("misc_group_addons_top")

def misc_sort_addons() -> str:
    # 0 None, 1 A→Z, 2 Z→A, 3 Manual
    return ["none", "az", "za", "manual"][int(ADDON.getSetting("misc_sort_addons") or 0)]
```

Wire **action** settings:

* `misc_manual_order` → open `ui_manual_order.py` dialog
* `misc_run_reorder_now` → call `reorder_favourites(manual_context=True)`

---

# 4) Classification rules (implement in `xmlio.py`)

Define a `FavEntry` dataclass and parser:

```python
from dataclasses import dataclass
@dataclass
class FavEntry:
    name: str            # raw display name (keep BBCode)
    action: str          # inner text of <favourite>…</favourite>
    thumb: str|None      # optional
    type: str|None = None  # 'addon' | 'media_item' | 'media_folder' | 'other'

BB_TAG_RE = re.compile(r"\[(?:/?(?:COLOR|B|I|LIGHT)[^\]]*)\]", re.I)

def normalize_title(name: str) -> str:
    s = BB_TAG_RE.sub("", name or "").strip()
    return s.casefold()

# Classification
ADDON_RUNADDON_RE  = re.compile(r'^RunAddon\("([^"]+)"\)$', re.I)
ADDON_RUNSCRIPT_RE = re.compile(r'^RunScript\(([^)]+)\)$', re.I)
MEDIA_PLAY_PLUGIN_RE = re.compile(r'^PlayMedia\("plugin://[^"]+"\)$', re.I)
MEDIA_PLAY_URL_RE    = re.compile(r'^PlayMedia\("(?:(?:smb|nfs|ftp|http|https|file)://)[^"]+"\)$', re.I)
MEDIA_FOLDER_RE      = re.compile(r'^ActivateWindow\(\d+,\s*"plugin://[^"]+"[^)]*\)$', re.I)

def classify(entry: FavEntry) -> str:
    a = entry.action.strip()
    if ADDON_RUNADDON_RE.match(a): return "addon"
    if ADDON_RUNSCRIPT_RE.match(a):
        # must reference an addon path to be an addon shortcut
        if "special://home/addons/" in a or "special://xbmc/addons/" in a: return "addon"
    if MEDIA_PLAY_PLUGIN_RE.match(a) or MEDIA_PLAY_URL_RE.match(a): return "media_item"
    if MEDIA_FOLDER_RE.match(a): return "media_folder"
    return "other"
```

Parsing/serializing XML (keep attributes, comments intact as much as possible, but you can round-trip):

```python
def parse_favourites_xml(xml_bytes: bytes) -> list[FavEntry]:
    # parse <favourites> and child <favourite> nodes; capture name/action/text + thumb attribute if present
    ...

def serialize_favourites(entries: list[FavEntry]) -> bytes:
    # build <favourites> with <favourite> nodes, preserving name + action text + thumb attrs
    ...
```

---

# 5) Reorder algorithm (`sync.py` or new `reorder.py`)

Add the core function:

```python
def reorder_favourites(manual_context: bool) -> dict:
    """
    Applies grouping/sorting rules + ensure-self/keep-first.
    Returns summary: {'addons': N, 'others': M, 'changed': bool}
    """
```

Implementation steps:

1. **Load** `favourites.xml` (profile path) → parse into `FavEntry[]`.
2. **Classify** each entry → `entry.type`.
3. If `settings.misc_group_addons_top()`:

   * Partition: `addons = [e for e in entries if e.type=='addon']`, `others = rest`.
4. Sort **addons** according to `misc_sort_addons()`:

   * `none` → keep original order.
   * `az` → `sorted(addons, key=lambda e: normalize_title(e.name))`
   * `za` → same, reversed.
   * `manual` → apply **manual order** (see §6). Unknown/new addons append at end.
5. **Ensure self is in favourites** if `misc_add_to_fav()`:

   * If missing, append **self shortcut entry** (see §7).
6. If `misc_keep_first()`:

   * Move **self shortcut entry** to **index 0** of the final list.
   * If `misc_group_addons_top()` is **off**, still place self first overall.
7. **Merge** back final ordered list:

   * If grouping enabled: `final = addons + others`
   * Else: start from original list and **locally reorder** only the subset that are `addon` entries in-place (stable transform).
8. If changed:

   * **Backup** current XML: `favourites_YYYYMMDD-HHMMSS.xml.bak`.
   * **Write atomic**: temp file → replace.
   * **Reload profile?** Only if `manual_context is True` and a setting toggle enabled (default: **do not reload** here).
9. Return summary.

> All writes must **avoid** profile reload in automatic contexts to prevent `LoadProfile()` loops.

---

# 6) Manual order persistence (new file)

**Path:** `special://profile/addon_data/<id>/favourites_order.json`

Schema (add-ons only):

```json
{
  "addon_order": [
    {"k":"RunAddon(\"plugin.video.stream-cinema\")"},
    {"k":"RunScript(special://home/addons/plugin.service.favourites-sync/resources/lib/addon.py)"}
  ],
  "version": 1
}
```

Helpers:

```python
def load_addon_order() -> list[str]: ...
def save_addon_order(keys: list[str]) -> None: ...
def entry_key(entry: FavEntry) -> str: return entry.action  # unique enough
```

Applying manual order:

```python
def apply_manual_order(addons: list[FavEntry], keys: list[str]) -> list[FavEntry]:
    index = {k:i for i,k in enumerate(keys)}
    known = [e for e in addons if entry_key(e) in index]
    unknown = [e for e in addons if entry_key(e) not in index]
    known.sort(key=lambda e: index[entry_key(e)])
    return known + unknown
```

---

# 7) Ensure self shortcut & keep-first

Define a helper in `sync.py`:

```python
SELF_ACTIONS = [
  f'RunAddon("{__addon_id__}")',
  # optional fallback if you prefer a script entry:
  # 'RunScript(special://home/addons/plugin.service.favourites-sync/resources/lib/addon.py)'
]

def ensure_self_shortcut(entries: list[FavEntry]) -> None:
    if not any(e.action in SELF_ACTIONS for e in entries):
        entries.insert(0, FavEntry(
            name="Favourites Sync (Cloud)",
            action=SELF_ACTIONS[0],
            thumb=None,
            type="addon"
        ))

def move_self_first(entries: list[FavEntry]) -> None:
    for i,e in enumerate(entries):
        if e.action in SELF_ACTIONS:
            if i != 0:
                entries.insert(0, entries.pop(i))
            break
```

---

# 8) Manual order UI (`ui_manual_order.py`)

Simple dialog with **Up/Down/Save/Cancel**:

Behavior:

* Load current favourites → filter `type=='addon'`.
* Show a list of **display titles** (use `entry.name`, but show a normalized preview aside).
* Up/Down to reorder (`list.index` swap).
* On Save → `save_addon_order([entry_key(e) for e in addons])`.
* Ask “Apply order now?” → if yes, call `reorder_favourites(manual_context=True)`.

---

# 9) Integrations (when to reorder)

* When **user toggles** any `misc_*` setting → run `reorder_favourites(manual_context=True)`.
* When **Validate endpoint** succeeds (optional) → no reorder unless settings changed.
* **Program menu**:

  * **Remove** old menu actions for “Add to favourites / Keep first”.
  * Optionally keep **“Reorder favourites now”** that calls `reorder_favourites(manual_context=True)`.

---

# 10) Backups & atomic write

Utility:

```python
def write_atomic_with_backup(xml_bytes: bytes, dest: str) -> None:
    backup = dest.replace("favourites.xml", f"favourites_{datetime.now():%Y%m%d-%H%M%S}.xml.bak")
    copy_file(dest, backup)
    tmp = dest + ".tmp"
    write_file(tmp, xml_bytes)
    os_replace(tmp, dest)
```

---

# 11) Logging (examples)

* `event=reorder_start group_top=true sort=az`
* `event=self_shortcut_added`
* `event=self_moved_first`
* `event=write_success changed=true`
* `event=error stage=parse detail="..."`

---

# 12) Acceptance tests (must pass)

1. **Settings exist** under “Miscellaneous”.
2. **Add to favourites** OFF: do nothing; ON: add a shortcut if missing.
3. **Keep first** moves the shortcut to position 1.
4. **Group add-ons at top** partitions add-ons above media items.
5. **Sort A→Z / Z→A** sorts only the **add-on group** (media untouched).
6. **Manual order editor** saves custom order and applies it.
7. Existing **BBCode** in names is preserved in output; sorting uses normalized names.
8. A **backup** is created before writing; write is **atomic**.
9. No **profile reload** on automatic contexts; OK to skip reload entirely for now.
10. Removing menu options doesn’t remove functionality (it’s in Settings only).

---

# 13) Rollback strategy

* The user can restore from `favourites_*.xml.bak` via your existing “Restore from backup…” path.
* Turning OFF “Group add-ons at top” + setting “Sort add-ons by: None” stops further reorders; you don’t auto-restore old order, but no new transformations will be applied.

---

# 14) Copy-paste prompt for AI developer

**PROMPT TO RUN:**

> Implement Part 1 for `plugin.service.favourites-sync` as follows:
>
> 1. Add the **Miscellaneous** settings (IDs, defaults, visibility) exactly as specified in section **2**.
> 2. Add getters in `settings_mgr.py` (section **3**).
> 3. In `xmlio.py`, implement `FavEntry`, `normalize_title`, classification regexes, `classify`, `parse_favourites_xml`, `serialize_favourites` (section **4**).
> 4. In `sync.py` (or new `reorder.py`), implement `reorder_favourites(manual_context)` using steps in **5**, including `ensure_self_shortcut` and `move_self_first` (section **7**).
> 5. Create `ui_manual_order.py` (section **8**) with Up/Down/Save behavior and apply-now prompt.
> 6. Wire Settings actions: `misc_manual_order` opens the dialog; `misc_run_reorder_now` calls `reorder_favourites(manual_context=True)`.
> 7. Remove prior **menu options** for “Add to favourites / Keep first” from `addon.py`. Optionally add a single “Reorder favourites now” entry that calls the same function.
> 8. Ensure writes are **backed up and atomic** (section **10**) and do **not** call `LoadProfile()` anywhere in this feature.
> 9. Add structured logs per **11**, and verify **Acceptance tests** in **12**.
>
> Provide: modified files, any new files, and a short test log showing a reorder run with `group_top=true sort=az`.

