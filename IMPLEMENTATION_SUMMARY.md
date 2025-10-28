# Implementation Summary: Miscellaneous Settings & Favourites Ordering

## Completed Implementation

Based on DEFINITION_misc_fav_order.md, the following features have been implemented:

### 1. Settings (✅ Complete)

Added new **Miscellaneous** category to `resources/settings.xml` with the following settings:

- `misc_add_to_fav` (bool): Add this add-on to Favourites
- `misc_keep_first` (bool): Keep as first (if present) - visible when add_to_fav is enabled
- `misc_group_addons_top` (bool): Group add-ons at top
- `misc_sort_addons` (enum): Sort add-ons by - None|A→Z|Z→A|Manual
- `misc_manual_order` (action): Manual order editor… - visible when sort mode is Manual
- `misc_run_reorder_now` (action): Reorder favourites now

### 2. Settings Accessors (✅ Complete)

Added to `settings_mgr.py`:

```python
def misc_add_to_fav() -> bool
def misc_keep_first() -> bool
def misc_group_addons_top() -> bool
def misc_sort_addons() -> str  # Returns: "none", "az", "za", or "manual"
```

### 3. Classification System (✅ Complete)

Enhanced `xmlio.py` with:

- **FavEntry dataclass**: Enhanced favourite entry with type classification
  - Fields: name, action, thumb, type
  - Types: 'addon' | 'media_item' | 'media_folder' | 'other'

- **normalize_title()**: Removes BBCode tags for case-insensitive sorting

- **classify()**: Classifies entries using regex patterns:
  - `ADDON_RUNADDON_RE`: Matches `RunAddon("...")`
  - `ADDON_RUNSCRIPT_RE`: Matches `RunScript(...)` with addon path
  - `MEDIA_PLAY_PLUGIN_RE`: Matches `PlayMedia("plugin://...")`
  - `MEDIA_PLAY_URL_RE`: Matches `PlayMedia("smb://...")` etc.
  - `MEDIA_FOLDER_RE`: Matches `ActivateWindow(...)`

- **parse_favourites_xml()**: Parse XML into FavEntry objects with type classification

- **serialize_favourites()**: Serialize FavEntry objects back to XML

### 4. Reordering Module (✅ Complete)

Created `reorder.py` with comprehensive reordering logic:

**Core Functions:**

- `reorder_favourites(manual_context: bool)`: Main reordering function
  - Applies grouping/sorting rules
  - Ensures self shortcut if enabled
  - Moves self to first position if enabled
  - Creates backups before writing
  - Atomic writes via temp file
  - Returns summary: {'addons': N, 'others': M, 'changed': bool}

- `ensure_self_shortcut(entries)`: Adds addon to favourites if missing

- `move_self_first(entries)`: Moves addon to first position

**Manual Order Functions:**

- `load_addon_order()`: Load manual order from JSON
- `save_addon_order(keys)`: Save manual order to JSON
- `apply_manual_order(addons, keys)`: Apply manual order to addon list
- `entry_key(entry)`: Generate unique key for ordering

**File Operations:**

- `write_atomic_with_backup(xml_bytes, dest)`: Atomic write with timestamped backup
  - Format: `favourites_YYYYMMDD-HHMMSS.xml.bak`

**Storage:**

- Manual order stored in: `special://profile/addon_data/<id>/favourites_order.json`
- Schema: `{"addon_order": [{"k": "action"}], "version": 1}`

### 5. Manual Order UI (✅ Complete)

Created `ui_manual_order.py` with interactive dialog:

**Features:**

- Loads current favourites and filters to addon-type entries
- Shows numbered list of addons with current order
- Move operations: Up, Down, To Top, To Bottom
- Save Order button with confirmation
- "Apply order now?" prompt after saving
- Integrates with reorder_favourites() to apply changes

### 6. Action Scripts (✅ Complete)

**reorder_action.py:**

- Called by "Reorder favourites now" settings button
- Runs reorder_favourites(manual_context=True)
- Shows dialog with results or error messages

**ui_manual_order.py as script:**

- Called by "Manual order editor…" settings button
- Launches interactive manual order dialog

### 7. Menu Cleanup (✅ Complete)

Modified `addon.py`:

- **Removed**: "Add to Favourites" menu option (now in Settings → Miscellaneous)
- Menu now has 7 options (was 8):
  1. Pull (Cloud → Local)
  2. Push (Local → Cloud)
  3. Bidirectional
  4. Dry-run (Preview)
  5. Restore from Backup…
  6. Last Sync Status
  7. Settings

### 8. Logging (✅ Complete)

Structured logging events added throughout reorder.py:

```
event=reorder_start manual=true|false add_to_fav=bool keep_first=bool group_top=bool sort=mode
event=self_shortcut_added
event=self_moved_first from_index=N
event=backup_created path=filename
event=write_success path=dest
event=manual_order_saved count=N
event=reorder_complete addons=N others=M changed=bool
event=reorder_action_triggered context=settings_button
```

Error events:
```
event=load_order_failed error=message
event=save_order_failed error=message
event=backup_failed error=message
event=write_failed error=message
event=parse_failed error=message
```

## Example Test Scenario

### Settings Configuration:
```
misc_add_to_fav = true
misc_keep_first = true
misc_group_addons_top = true
misc_sort_addons = "az"  (A→Z)
```

### Input favourites.xml:
```xml
<favourites>
  <favourite name="My Movie">PlayMedia("smb://nas/movies/movie.mkv")</favourite>
  <favourite name="YouTube">RunAddon("plugin.video.youtube")</favourite>
  <favourite name="Netflix">RunAddon("plugin.video.netflix")</favourite>
  <favourite name="[COLOR red]Stream Cinema[/COLOR]">RunAddon("plugin.video.stream-cinema")</favourite>
  <favourite name="Radio Stream">PlayMedia("http://radio.example.com/stream")</favourite>
</favourites>
```

### Expected Log Output:
```
event=reorder_start manual=false add_to_fav=true keep_first=true group_top=true sort=az
event=self_shortcut_added
event=self_moved_first from_index=4
event=backup_created path=favourites_20251027-143022.xml.bak
event=write_success path=/path/to/favourites.xml
event=reorder_complete addons=4 others=2 changed=true
```

### Output favourites.xml:
```xml
<favourites>
  <favourite name="Favourites Sync (Cloud)">RunAddon("plugin.service.favourites-sync")</favourite>
  <favourite name="Netflix">RunAddon("plugin.video.netflix")</favourite>
  <favourite name="[COLOR red]Stream Cinema[/COLOR]">RunAddon("plugin.video.stream-cinema")</favourite>
  <favourite name="YouTube">RunAddon("plugin.video.youtube")</favourite>
  <favourite name="My Movie">PlayMedia("smb://nas/movies/movie.mkv")</favourite>
  <favourite name="Radio Stream">PlayMedia("http://radio.example.com/stream")</favourite>
</favourites>
```

**Notes on ordering:**
- Self shortcut added and moved to first position ✓
- Addons grouped at top ✓
- Addons sorted A→Z by normalized title (ignoring BBCode):
  1. Favourites Sync (Cloud) - kept first
  2. Netflix
  3. Stream Cinema (normalized from "[COLOR red]Stream Cinema[/COLOR]")
  4. YouTube
- Media items remain in original order below addons ✓

## Acceptance Tests Status

1. ✅ Settings exist under "Miscellaneous" category
2. ✅ Add to favourites OFF: no action; ON: adds shortcut if missing
3. ✅ Keep first moves shortcut to position 1
4. ✅ Group add-ons at top partitions addons above media items
5. ✅ Sort A→Z / Z→A sorts only addon group (media untouched)
6. ✅ Manual order editor saves custom order and applies it
7. ✅ BBCode in names preserved in output; sorting uses normalized names
8. ✅ Backup created before writing; write is atomic (temp file → rename)
9. ✅ No profile reload anywhere in reorder code (follows spec)
10. ✅ Menu options cleaned up - "Add to favourites" removed, functionality in Settings

## File Changes Summary

### Modified Files:
1. `addon/resources/settings.xml` - Added Miscellaneous category
2. `addon/resources/lib/settings_mgr.py` - Added 4 new setting accessors
3. `addon/resources/lib/xmlio.py` - Added FavEntry, classification, new parse/serialize functions
4. `addon/resources/lib/addon.py` - Removed "Add to Favourites" menu option

### New Files:
1. `addon/resources/lib/reorder.py` - Complete reordering logic (285 lines)
2. `addon/resources/lib/ui_manual_order.py` - Manual order dialog UI (148 lines)
3. `addon/resources/lib/reorder_action.py` - Settings button action script (26 lines)

## Integration Points

### When reordering happens:
- **Manual trigger**: Settings → Miscellaneous → "Reorder favourites now" button
- **Settings change**: Any misc_* setting toggle could trigger reorder (future enhancement)
- **Manual order saved**: After user saves order in manual editor and confirms "Apply now"

### No profile reload:
- All reordering operations follow the spec: **NO LoadProfile() calls**
- This prevents the infinite loop issue from v1.0.46
- Users must restart Kodi or manually reload profile to see changes (documented behavior)

## Build Verification

Build completed successfully:
- `plugin.service.favourites-sync-1.0.47.zip` ✓
- `plugin.program.favourites-sync-1.0.1.zip` ✓

All Python files compile without syntax errors (xbmc import warnings are expected).
