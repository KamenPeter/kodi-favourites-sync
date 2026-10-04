# Release v1.0.74 - WindowXML UI Reliability Improvements

**Date:** November 1, 2025  
**Type:** Enhancement  
**Focus:** Ensure WindowXML dialogs load reliably across all devices

---

## Overview

v1.0.74 focuses on making the **Manage Profiles** and **Edit Profile** WindowXML dialogs (introduced in v1.0.72) work reliably on all Kodi devices, especially those running 720p UI scaling (Android TV, CoreELEC, low-res devices).

## What's New

### 1. 720p UI Support

**Problem:** Devices running 720p UI scaling couldn't load the WindowXML dialogs because only 1080i versions existed.

**Solution:** Created 720p copies of both dialogs:
```
resources/skins/default/
├── 1080i/
│   ├── DialogManageProfiles.xml
│   └── DialogEditProfile.xml
└── 720p/
    ├── DialogManageProfiles.xml  ← NEW
    └── DialogEditProfile.xml     ← NEW
```

Kodi automatically selects the correct resolution based on active skin settings.

### 2. Detailed Initialization Logging

**Added clear log markers:**

```python
# ui_profiles_manage.py - onInit()
xbmc.log("[favourites-sync] DialogManageProfiles initialized", xbmc.LOGINFO)

# ui_profile_edit.py - onInit()
xbmc.log(f"[favourites-sync] DialogEditProfile initialized for profile: {profile_name}", xbmc.LOGINFO)
```

**QA Verification:** Check Kodi logs for these entries to confirm dialogs are loading.

### 3. XML Path Logging

**Before opening dialogs, log the exact path:**

```python
# ui_profiles_manage.py - open_manage_dialog()
xbmc.log(f"[favourites-sync] Opening WindowXMLDialog: {xml_file} from {addon_path}", xbmc.LOGINFO)
xbmc.log(f"[favourites-sync] Resolution folder: 1080i (will fallback to 720p if needed)", xbmc.LOGINFO)

# ui_profile_edit.py - open_edit_dialog()
xbmc.log(f"[favourites-sync] Opening WindowXMLDialog: {xml_file} for profile: {profile_name}", xbmc.LOGINFO)
xbmc.log(f"[favourites-sync] Path: {addon_path}, Resolution: 1080i", xbmc.LOGINFO)
```

**Troubleshooting:** If dialogs don't appear, check logs for path mismatches or missing files.

### 4. Explicit Error Messages

**Before v1.0.74:** Silent fallback to legacy dialog - user doesn't know what failed.

**After v1.0.74:** Detailed error dialog showing:
- What failed (WindowXML load error)
- Which XML file (DialogManageProfiles.xml / DialogEditProfile.xml)
- Expected locations (1080i/ and 720p/)
- Full error message

**Example Error Dialog:**
```
┌─────────────────────────────────────────────────┐
│    Favourites Sync - UI Error                   │
├─────────────────────────────────────────────────┤
│ Failed to load WindowXML dialog:                │
│                                                 │
│ [Error details]                                 │
│                                                 │
│ XML: DialogManageProfiles.xml                   │
│ Path: /path/to/addon/resources/skins/default/  │
│                                                 │
│ Expected locations:                             │
│ - 1080i/DialogManageProfiles.xml                │
│ - 720p/DialogManageProfiles.xml                 │
│                                                 │
│                   [ OK ]                        │
└─────────────────────────────────────────────────┘
```

**After error, user is asked:**
```
┌─────────────────────────────────────────────────┐
│    Favourites Sync                              │
├─────────────────────────────────────────────────┤
│ WindowXML dialog failed to load.                │
│                                                 │
│ Use legacy list dialog instead?                 │
│                                                 │
│         [ Cancel ]      [ Use Legacy ]          │
└─────────────────────────────────────────────────┘
```

### 5. Verified Entry Points

**Confirmed both entry points call the correct WindowXML dialog:**

✅ **settings.xml** (Settings → Profiles → Manage Profiles...):
```xml
<setting id="profiles_manage" type="action" label="Manage Profiles…" 
         action="RunScript(.../ui_profiles_manage.py)" option="close"/>
```

✅ **addon.py** (Favourites → Run → option 4):
```python
ui_profiles_manage.open_manage_dialog()
```

## Files Modified

### New Files
- `addon/resources/skins/default/720p/DialogManageProfiles.xml`
- `addon/resources/skins/default/720p/DialogEditProfile.xml`

### Modified Files
- `addon/resources/lib/ui_profiles_manage.py`
  - Added initialization logging in `onInit()`
  - Added XML path logging in `open_manage_dialog()`
  - Replaced silent fallback with detailed error dialogs
  - Added user choice: cancel or use legacy dialog

- `addon/resources/lib/ui_profile_edit.py`
  - Added initialization logging in `onInit()`
  - Added XML path logging in `open_edit_dialog()`
  - Improved error messages with context

- `addon/addon.xml`
  - Version: 1.0.73.1 → 1.0.74
  - News updated

- `addon/changelog.txt`
  - v1.0.74 entry added with full details

## Acceptance Criteria (Testing)

| Test Case | Expected Result | Status |
|-----------|----------------|--------|
| **Version Check** | Settings → Add-ons → Services → Favourites Sync shows v1.0.74 | ⏳ Pending |
| **1080p Device** | Settings → Manage Profiles opens Estuary-style dialog | ⏳ Pending |
| **720p Device** | Settings → Manage Profiles opens Estuary-style dialog | ⏳ Pending |
| **Addon Menu** | Favourites → Run → Manage Profiles opens WindowXML | ⏳ Pending |
| **Edit Button** | Click Edit opens DialogEditProfile.xml | ⏳ Pending |
| **Button Functions** | Edit/Validate/Add/Delete/OK/Cancel all work | ⏳ Pending |
| **Navigation** | Left/Right/Up/Down focus navigation works | ⏳ Pending |
| **Log Verification** | `grep -i "DialogManageProfiles initialized" kodi.log` shows entry | ⏳ Pending |
| **Path Logging** | `grep -i "Opening WindowXMLDialog" kodi.log` shows paths | ⏳ Pending |
| **Error Handling** | If XML missing, shows detailed error (not silent fallback) | ⏳ Pending |
| **Legacy Fallback** | User can choose legacy dialog if WindowXML fails | ⏳ Pending |

## Log Verification Commands

**Check dialog initialization:**
```bash
grep -i "favourites-sync.*DialogManageProfiles initialized" ~/.kodi/temp/kodi.log
grep -i "favourites-sync.*DialogEditProfile initialized" ~/.kodi/temp/kodi.log
```

**Check XML loading:**
```bash
grep -i "favourites-sync.*Opening WindowXMLDialog" ~/.kodi/temp/kodi.log
```

**Check for errors:**
```bash
grep -i "favourites-sync.*WindowXML ERROR" ~/.kodi/temp/kodi.log
```

**Windows PowerShell:**
```powershell
Get-Content "$env:APPDATA\Kodi\kodi.log" | Select-String "favourites-sync.*Dialog"
```

## Known Limitations

1. **XML files identical** - 720p and 1080i versions are exact copies. Future releases could optimize 720p layout for smaller screens.

2. **No automatic XML repair** - If XML files are missing or corrupted, addon shows error but doesn't attempt auto-repair.

3. **Legacy fallback optional** - User must explicitly choose to use legacy dialog; no automatic fallback.

## Backwards Compatibility

✅ **Fully compatible with v1.0.73.1**
- All cloud protection features intact
- No configuration changes required
- Existing profiles.json works unchanged
- Settings structure unchanged

## Upgrade Path

**From v1.0.73.1:**
1. Install v1.0.74 (overwrite existing)
2. Restart Kodi
3. Test: Settings → Manage Profiles
4. Check logs for initialization messages

**No data migration needed.**

## Troubleshooting

### Issue: Dialogs don't appear (blank screen)

**Check logs:**
```bash
tail -f ~/.kodi/temp/kodi.log | grep favourites-sync
```

**Look for:**
- `Opening WindowXMLDialog: DialogManageProfiles.xml from [path]`
- `DialogManageProfiles initialized`

**If missing:** XML files not in correct location.

**Fix:**
```bash
ls -la ~/.kodi/addons/plugin.service.favourites-sync/resources/skins/default/
# Should show 1080i/ and 720p/ folders

ls -la ~/.kodi/addons/plugin.service.favourites-sync/resources/skins/default/1080i/
# Should show DialogManageProfiles.xml and DialogEditProfile.xml

ls -la ~/.kodi/addons/plugin.service.favourites-sync/resources/skins/default/720p/
# Should show DialogManageProfiles.xml and DialogEditProfile.xml
```

### Issue: Still seeing basic list dialog

**Cause:** settings.xml or addon.py calling old ui_profiles.py

**Fix:** Already fixed in v1.0.74 - check version is actually 1.0.74:
```python
import xbmcaddon
addon = xbmcaddon.Addon('plugin.service.favourites-sync')
print(addon.getAddonInfo('version'))  # Should show 1.0.74
```

### Issue: Error dialog appears

**Expected behavior in v1.0.74** - errors are now explicit.

**Check error message** for:
- Missing XML files → Reinstall addon
- Permission issues → Check addon_data folder permissions
- Skin issues → Try switching to default skin temporarily

## Next Steps

### Immediate (v1.0.74)
- [x] 720p UI support
- [x] Initialization logging
- [x] XML path verification
- [x] Explicit error messages
- [x] Entry point verification

### Future (v1.0.75+)
- [ ] Optimize 720p layouts for smaller screens
- [ ] Add visual consistency checks (match Estuary theme exactly)
- [ ] Auto-detect and suggest skin resolution
- [ ] Add "Reload UI" button in error dialogs
- [ ] Performance metrics logging (dialog load time)

---

## Summary

v1.0.74 ensures the modern WindowXML UI works reliably across all Kodi devices by:

1. ✅ Adding 720p support (Android TV, CoreELEC compatible)
2. ✅ Adding detailed logging for troubleshooting
3. ✅ Showing explicit errors instead of silent failures
4. ✅ Verifying all entry points use WindowXML
5. ✅ Giving users control over fallback behavior

**Status:** ✅ Built and installed  
**Testing:** ⏳ Pending user verification  
**Stability:** Based on v1.0.73.1 (stable, tested)
