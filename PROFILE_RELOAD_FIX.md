# Profile Reload Fix - Immediate Feedback for misc_add_to_fav Toggle

## Problem
When toggling the `misc_add_to_fav` setting, the changes to `favourites.xml` weren't immediately visible to the user. They had to restart Kodi or manually refresh to see the addon appear/disappear from favourites.

## Root Cause
The profile reload was being triggered correctly in `reorder_favourites()` → `reload_favourites()`, but there was a timing/flow issue in the `onSettingsChanged()` handler.

## Solution
Simplified the `onSettingsChanged()` handler in `service.py` to rely on the existing reload mechanism:

1. **500ms delay** after settings change detection
   - Ensures settings are fully committed to disk

2. **Call reorder_favourites(manual_context=True, skip_profile_reload=False)**
   - `manual_context=True` enables profile reload
   - `skip_profile_reload=False` doesn't skip it

3. **Inside reorder_favourites():**
   - Adds or removes self-shortcuts based on `misc_add_to_fav`
   - Writes changes to `favourites.xml` with atomic backup
   - Calls `reload_favourites(manual_context=True, skip_reload=False)`

4. **Inside reload_favourites():**
   - Executes `xbmc.executebuiltin("LoadProfile(auto)")`
   - This reloads the entire profile, refreshing all favourites
   - Fallback to `Container.Refresh` if LoadProfile fails

5. **300ms delay** before showing toast notification
   - Ensures reload completes before notification appears

## Call Chain
```
User toggles misc_add_to_fav
  ↓
onSettingsChanged() detects change
  ↓
xbmc.sleep(500) - wait for settings to save
  ↓
reorder_favourites(manual_context=True, skip_profile_reload=False)
  ↓
ensure_self_shortcut() or remove_self_shortcuts()
  ↓
write_atomic_with_backup() - writes favourites.xml
  ↓
reload_favourites(manual_context=True, skip_reload=False)
  ↓
xbmc.executebuiltin("LoadProfile(auto)") - RELOAD!
  ↓
xbmc.sleep(300) - small delay
  ↓
Show toast notification
```

## User Experience
**Before Fix:**
- Toggle setting → Click OK
- No visible change
- Must restart Kodi or manually refresh
- Confusing and frustrating

**After Fix:**
- Toggle setting → Click OK
- **Immediate profile reload** (UI flickers briefly)
- Addon appears/disappears from favourites instantly
- Toast notification confirms: "Favourites updated: X addons, Y others"
- Clear, immediate feedback

## Technical Details

### Modified File
- `addon/resources/lib/service.py`

### Key Changes
1. Removed duplicate `LoadProfile(auto)` call from `onSettingsChanged()`
2. Added 300ms delay before notification
3. Relies on existing `reload_favourites()` mechanism

### Flow Control Parameters
- `manual_context=True`: Indicates user-initiated action, enables reload
- `skip_profile_reload=False`: Don't skip the reload step
- `skip_reload=False`: Internal parameter to `reload_favourites()`

## Testing
1. Open Settings → Miscellaneous
2. Toggle "Show addon in Favourites" to **ON**
3. Click OK
4. **Result:** Addon shortcut appears immediately in favourites
5. Toggle to **OFF**
6. Click OK
7. **Result:** Addon shortcut disappears immediately from favourites

## Compatibility
- Works with both `LoadProfile(auto)` (preferred) and `Container.Refresh` (fallback)
- Kodi Matrix (19) through Omega (21)
- No breaking changes to existing code

## Version
Fixed in: **v1.0.48** (pending)
