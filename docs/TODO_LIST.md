

# 🧩 FAVOURITES-SYNC-ADDON — DEVELOPER TODO LIST (Fix & Improvement Tasks)

## 1️⃣ misc_add_to_fav two-way state sync  ✅ **COMPLETED** (v1.0.48, v1.0.52)

**Goal:** the "Add this add-on to Favourites" setting (`misc_add_to_fav`) must *reflect* the real presence of the add-on shortcut in `favourites.xml`, and *changing it* must update that file.

### Tasks

* [x] On opening settings (or on `onSettingsChanged` event), **read `favourites.xml`** and check if self shortcut (`RunAddon("plugin.service.favourites-sync")` or legacy `RunScript(special://home/addons/plugin.service.favourites-sync/resources/lib/addon.py)`) exists.
  * ✅ **Implemented in v1.0.48**: `sync_misc_add_to_fav_state()` in `settings_mgr.py`
  * ✅ **Fixed in v1.0.52**: Moved to proper startup location in `service.py` run() function
  * If found → **set `misc_add_to_fav = true`**
  * If not found → **set `misc_add_to_fav = false`**
* [x] When the user **changes** `misc_add_to_fav` in the settings UI:
  * ✅ **Implemented in v1.0.48**: `ensure_self_shortcut()` and `remove_self_shortcuts()` in `reorder.py`
  * If **set to True** → insert self shortcut into `favourites.xml`.
  * If **set to False** → remove any existing self shortcut(s) from `favourites.xml`.
  * Always create a backup before writing.
* [x] Debounce changes: perform update on **OK/Apply**, not on each toggle.
  * ✅ **Implemented in v1.0.48**: `onSettingsChanged()` handler in `service.py`
* [x] Reflect change visually — show toast/log:
  * ✅ **Implemented in v1.0.48**: Toast notifications in `service.py`
  * `"[fav-sync] Add-on added to favourites"` or `"[fav-sync] Add-on removed from favourites"`.
* [x] When change is made, trigger favourites reload (see item 3).
  * ✅ **Implemented in v1.0.49-1.0.52**: Profile reload after changes

---

## 2️⃣ Reorder engine not writing / not reflected ✅ **COMPLETED** (v1.0.48)

**Goal:** The reorder engine must actually update `favourites.xml` when user changes settings or performs “Reorder now”.

### Root cause candidates

* ~~XML parse/serialize may not be writing to the correct **active profile path** (`special://profile/favourites.xml`)~~. ✅ FIXED
* ~~The in-memory list (`entries`) is rebuilt but **write_atomic_with_backup()** never called or fails silently~~. ✅ FIXED
* ~~File handle permission / Kodi locking~~. ✅ RESOLVED
* ~~Missing `manual_context=True` flag → no write triggered~~. ✅ FIXED

### Fix tasks

* [x] Verify `reorder_favourites()` calls **write_atomic_with_backup()** and writes to `special://profile/favourites.xml` (not a cached copy).
  * ✅ **Fixed in v1.0.48**: Confirmed write pipeline works correctly
* [x] Ensure `serialize_favourites(entries)` returns **non-empty bytes** (test with logging before writing).
  * ✅ **Fixed in v1.0.48**: Serialization works correctly
* [x] Add **debug logs** around write:
  * ✅ **Implemented in v1.0.48**: Enhanced logging with `kvfmt(event="writing_favourites"...)`
  ```
  log_info(f"Writing favourites.xml, entries={len(entries)}, changed={changed}")
  ```
* [x] After write, **force Kodi to reload favourites** (see section 3).
  * ✅ **Implemented in v1.0.48-1.0.52**: Profile reload after write
* [x] If `misc_group_addons_top` = OFF, ensure reorder performs **in-place transform** (re-inserts addons where they were) instead of skipping write.
  * ✅ **Fixed in v1.0.48**: In-place reorder logic implemented
* [x] Re-test: manual reorder, A→Z sorting, and manual order dialog should all cause visible reordering.
  * ✅ **Verified in v1.0.48**: All reorder operations work correctly

---

## 3️⃣ Reload favourites after change ✅ **COMPLETED** (v1.0.48-1.0.52)

**Goal:** Once favourites are updated (add/remove or reorder), Kodi UI should show the change immediately.

### Tasks

* [x] After successful write to `favourites.xml`, run one of the following:
  * ✅ **Implemented in v1.0.51**: Created `refresh_kodi_profile()` function
  * ✅ **Enhanced in v1.0.52**: Added `Container.Refresh` before and after `LoadProfile(auto)`
  * Preferred: **`xbmc.executebuiltin("LoadProfile(auto)")`** to reload current profile safely.
  * Or (lighter): **`xbmc.executebuiltin("Container.Refresh")`** if the user is currently viewing favourites.
* [x] Wrap in a safe guard:
  * ✅ **Implemented in v1.0.48**: `reload_favourites()` checks `manual_context` and `skip_reload`
  ```python
  if manual_context and not skip_profile_reload:
      xbmc.executebuiltin("LoadProfile(auto)")
  ```
* [x] Confirm this does **not** create infinite reload loops (re-use the existing skip-reload logic from v1.0.46).
  * ✅ **Fixed in v1.0.50**: Reload flag debounce mechanism prevents infinite loops
  * ✅ **Working correctly**: `_set_reload_flag()` and `_is_recent_reload()` prevent unwanted syncs

---

## 4️⃣ Auto-apply on OK / test-run ✅ **COMPLETED** (v1.0.48-1.0.49)

**Goal:** Changing any of the Misc settings or pressing "Reorder now" applies immediately; user doesn't need to restart Kodi.

### Tasks

* [x] Hook Kodi's `onSettingsChanged` or re-execute on **OK** in Settings:
  * ✅ **Implemented in v1.0.48**: `_Monitor.onSettingsChanged()` in `service.py`
  * When user confirms settings, call `reorder_favourites(manual_context=True)`.
* [x] Include `misc_add_to_fav` logic (add/remove) in the same handler so both reorder and add/remove happen in one pass.
  * ✅ **Implemented in v1.0.48**: Handler calls `reorder_favourites()` which handles add/remove
* [x] Ensure profile reload is executed only once after all operations complete.
  * ✅ **Fixed in v1.0.49**: Simplified flow to avoid duplicate reloads
  * ✅ **Working correctly**: Single reload after all changes applied

---

## 5️⃣ Misc internal polish ✅ **COMPLETED** (v1.0.48)

### Add-on identification improvements

* [x] Treat both forms of self-shortcut (`RunAddon` + `RunScript`) as **equivalent**; de-dupe if both exist.
  * ✅ **Implemented in v1.0.48**: `SELF_ACTIONS` list contains both forms
  * ✅ **Implemented in v1.0.48**: `remove_self_shortcuts()` removes all matching actions
* [x] When adding, always prefer the modern `RunAddon("plugin.service.favourites-sync")` form.
  * ✅ **Implemented in v1.0.48**: `ensure_self_shortcut()` uses `SELF_ACTIONS[0]` (RunAddon form)
* [x] When removing, delete both forms.
  * ✅ **Implemented in v1.0.48**: `remove_self_shortcuts()` checks against `SELF_ACTIONS` list

### Manual-order persistence

* [x] Use compound key `{action, name}` instead of only `action` to avoid duplicates.
  * ✅ **Implemented in v1.0.48**: `entry_key()` returns `f"{entry.action}||{entry.name}"`
* [x] Warn on collisions in logs.
  * ✅ **Implemented in v1.0.48**: Logging throughout reorder operations

### Serialization fidelity

* [x] Preserve `thumb` attributes, BBCode in names, and ordering of unaffected entries.
  * ✅ **Verified in v1.0.48**: XML serialization preserves all attributes
* [x] Confirm re-writes produce a valid XML structure identical to Kodi's expected schema.
  * ✅ **Verified in v1.0.48**: `serialize_favourites()` produces valid Kodi XML

---

## 6️⃣ Regression test plan ✅ **ALL TESTS PASSING** (v1.0.48-1.0.52)

| Test                         | Expected Result                           | Status |
| ---------------------------- | ----------------------------------------- | ------ |
| Toggle `misc_add_to_fav` ON  | Self shortcut added to favourites.xml     | ✅ v1.0.48 |
| Toggle `misc_add_to_fav` OFF | Self shortcut removed                     | ✅ v1.0.48 |
| Change order A→Z / Z→A       | favourites.xml reordered accordingly      | ✅ v1.0.48 |
| Use manual order editor      | Saved order reflected in favourites.xml   | ✅ v1.0.48 |
| Press "Reorder now"          | favourites.xml rewritten + Kodi reloads   | ✅ v1.0.48 |
| Enable "Keep as first"       | Self shortcut moved to position 0         | ✅ v1.0.48 |
| Disable grouping             | Only add-on entries reordered in place    | ✅ v1.0.48 |
| All writes                   | Create timestamped backup, atomic replace | ✅ v1.0.48 |
| Setting checkbox accuracy    | Reflects actual favourites.xml state      | ✅ v1.0.52 |
| Profile refresh visibility   | Changes visible immediately in UI         | ✅ v1.0.52 |
| No infinite loops            | Reload flag prevents unwanted syncs       | ✅ v1.0.50 |

---

# 🔧 Implementation History

1. ✅ Implement **misc_add_to_fav two-way sync** (section 1) - **COMPLETED v1.0.48, v1.0.52**
2. ✅ Fix **write pipeline** in reorder engine (section 2) - **COMPLETED v1.0.48**
3. ✅ Add **safe reload** after write (section 3) - **COMPLETED v1.0.48-1.0.52**
4. ✅ Implement **auto-apply handler** (section 4) - **COMPLETED v1.0.48-1.0.49**
5. ✅ Apply polish and tests (sections 5–6) - **COMPLETED v1.0.48**

---

# ✅ Deliverables checklist - **ALL COMPLETE**

* [x] Updated `settings_mgr.py` (two-way state, event hook).
  * ✅ v1.0.48: Added `sync_misc_add_to_fav_state()` and `misc_set_add_to_fav()`
  * ✅ v1.0.52: Improved import handling and logging
* [x] Updated `sync.py` or `reorder.py` (write + reload).
  * ✅ v1.0.48: Fixed write pipeline in `reorder_favourites()`
  * ✅ v1.0.51: Added `refresh_kodi_profile()` function
  * ✅ v1.0.52: Enhanced with Container.Refresh sequence
* [x] Updated `xmlio.py` (serialize fidelity).
  * ✅ v1.0.48: Verified serialization preserves all attributes
* [x] Logging lines confirming writes and reloads.
  * ✅ v1.0.48-1.0.52: Comprehensive logging throughout all operations
* [x] Verified test cases all pass.
  * ✅ v1.0.48-1.0.52: All regression tests passing

---

# 🎉 PROJECT STATUS: **COMPLETE**

All TODO items have been successfully implemented across versions 1.0.48 through 1.0.52.

**Key Achievements:**
- ✅ Two-way state synchronization for misc_add_to_fav
- ✅ Working reorder engine with proper file writes
- ✅ Profile reload with UI visibility (Container.Refresh + LoadProfile)
- ✅ Auto-apply on settings change
- ✅ Reload flag debounce to prevent infinite loops
- ✅ Compound keys for manual order persistence
- ✅ Comprehensive logging and error handling
- ✅ All regression tests passing

**Final Version:** 1.0.52 (2025-10-28)

