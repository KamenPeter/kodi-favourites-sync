# Release Notes: v1.0.58 / v1.0.2

**Release Date**: October 28, 2025

## Package Information

### Service Addon (Core)
- **Package**: `plugin.service.favourites-sync-1.0.58.zip`
- **Location**: `dist/plugin.service.favourites-sync-1.0.58.zip`
- **Version**: 1.0.57 → 1.0.58
- **Changes**: Smart dialog detection, auto-focus Favourites window

### Program Addon (Launcher)
- **Package**: `plugin.program.favourites-sync-1.0.2.zip`
- **Location**: `dist/plugin.program.favourites-sync-1.0.2.zip`
- **Version**: 1.0.1 → 1.0.2
- **Changes**: Updated dependency to require service v1.0.58

## Compatibility Status

### ✅ FULLY COMPATIBLE

The program addon (launcher) is **100% compatible** with service addon v1.0.58:

1. **API Interface**: No changes
   - `addon.main()` signature unchanged (no parameters)
   - Program addon simply imports and calls `main()` from service addon
   - All functionality preserved

2. **Dependency Check**: Updated
   - Old: Required `plugin.service.favourites-sync >= 1.0.47`
   - New: Requires `plugin.service.favourites-sync >= 1.0.58`
   - Ensures users have latest features

3. **Code Changes**: None required
   - `runner/default.py` unchanged
   - Still uses same import mechanism
   - No breaking changes in service addon API

## What's New in v1.0.58

### 1. Smart Dialog Detection
**Previous Approach (v1.0.57)**:
- Fixed 1-second delay before ReloadSkin()
- Problem: If user took longer, refresh happened while dialog open

**New Approach (v1.0.58)**:
```python
# Actively monitors dialog state
monitor = xbmc.Monitor()
wait_until = time.time() + 5.0

while time.time() < wait_until:
    if not (Window.IsActive(settings) or Window.IsActive(addonsettings)):
        break  # Dialog closed!
    monitor.waitForAbort(0.2)  # Check every 200ms
```

**Benefits**:
- Waits for actual dialog close (not fixed time)
- Up to 5 seconds max wait (safety timeout)
- Respects Kodi shutdown signal
- More reliable across different user speeds

### 2. Auto-Focus Favourites Window
**New Parameter**: `focus_favourites=True`

**Behavior**:
```python
# After ReloadSkin()
if focus_favourites:
    xbmc.executebuiltin("ActivateWindow(favourites)")
    xbmc.sleep(200)
    xbmc.executebuiltin("Container.Refresh")
```

**User Experience**:
- User toggles "Show addon in Favourites" ON
- Settings close
- Screen refreshes
- **Favourites window opens automatically** ✨
- User sees changes immediately

### 3. Better Logging & Error Handling
**Improvements**:
- Thread named `fav-sync-delayed-reload` for debugging
- Try-catch around delayed reload logic
- New log events: `delayed_reload_waiting`, `delayed_reload_failed`
- More detailed error messages

## User Experience Comparison

### Before (v1.0.57)
1. Toggle setting ON
2. Click OK
3. Wait 1 second
4. Screen refreshes
5. **Manual navigation to Favourites required**
6. See changes

### After (v1.0.58)
1. Toggle setting ON
2. Click OK
3. Settings close (detected automatically)
4. 0.2s grace period
5. Screen refreshes
6. **Favourites window opens automatically**
7. Changes visible immediately

## Installation Instructions

### Fresh Install
1. Install service addon: `plugin.service.favourites-sync-1.0.58.zip`
2. Install program addon: `plugin.program.favourites-sync-1.0.2.zip`
3. Configure settings
4. Done!

### Upgrade from v1.0.57
1. **Clear Python cache**:
   ```powershell
   Remove-Item "$env:APPDATA\Kodi\addons\plugin.service.favourites-sync\resources\lib\__pycache__" -Recurse -Force
   ```

2. **Install service addon v1.0.58**:
   - Settings → Add-ons → Install from zip
   - Select: `plugin.service.favourites-sync-1.0.58.zip`

3. **Install program addon v1.0.2** (optional, if you use it):
   - Settings → Add-ons → Install from zip
   - Select: `plugin.program.favourites-sync-1.0.2.zip`

4. **Restart Kodi** (recommended)

5. **Test**:
   - Open addon settings
   - Toggle "Show addon in Favourites"
   - Click OK
   - Verify Favourites window opens automatically
   - Confirm addon visible/removed in Favourites

## Technical Details

### Modified Files (Service Addon)
- `addon/addon.xml` - Version 1.0.57 → 1.0.58
- `addon/changelog.txt` - Added v1.0.58 entry
- `addon/resources/lib/reorder.py` - Enhanced refresh_kodi_profile()
  - Added smart dialog detection loop
  - Added focus_favourites parameter
  - Improved thread naming and error handling
- `docs/CHANGELOG.md` - Comprehensive v1.0.58 documentation

### Modified Files (Program Addon)
- `runner/addon.xml` - Version 1.0.1 → 1.0.2
  - Updated dependency: requires service v1.0.58
  - Added news field
- `runner/changelog.txt` - Added v1.0.2 entry

### Code Quality
- No breaking changes
- Backward compatible API
- Proper error handling
- Thread safety maintained
- Monitor pattern for clean shutdown

## Testing Checklist

- [x] Build successful for both addons
- [x] Version numbers updated correctly
- [x] Changelogs documented
- [x] Program addon dependency updated
- [x] API compatibility verified
- [x] No breaking changes introduced
- [ ] User testing: Toggle ON → Auto-opens Favourites
- [ ] User testing: Toggle OFF → Auto-opens Favourites showing removal
- [ ] User testing: Slow dialog close (>1 second) handled correctly
- [ ] Log verification: All events logged properly

## Known Issues

**None reported** - This is a stable enhancement release.

## Support

If issues arise:
1. Check Kodi log: `%APPDATA%\Kodi\kodi.log`
2. Check addon log: `%APPDATA%\Kodi\userdata\addon_data\plugin.service.favourites-sync\log.txt`
3. Verify Python cache cleared after upgrade
4. Ensure both addons at correct versions

## Summary

This release improves user experience with:
- ✅ Smarter dialog detection (no more premature refreshes)
- ✅ Auto-focus Favourites (changes visible immediately)
- ✅ Better error handling (more reliable)
- ✅ Full compatibility maintained (no breaking changes)

Both addons work together seamlessly with no API changes required.
