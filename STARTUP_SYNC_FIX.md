# Startup Sync Fix - Prevent Unwanted Sync on Profile Reload

## Problem
When toggling the `misc_add_to_fav` setting (or any operation that calls `LoadProfile(auto)`), the service restarts and triggers the startup sync logic even when `schedule_enabled=false`.

**Root Cause:**
1. Service is configured with `start="startup"` in `addon.xml`
2. This means the service starts both on Kodi startup AND on profile reload
3. When `LoadProfile(auto)` is called (to refresh favourites UI), it reloads the profile
4. Profile reload triggers service restart
5. Service restart runs startup sync logic
6. User sees unexpected sync messages even with scheduling disabled

## Solution
Implemented a flag-based debounce mechanism to detect when a profile reload is triggered by the addon itself:

### 1. Reload Flag File
Created `.profile_reload_flag` file in addon data directory:
- Written **before** calling `LoadProfile()`
- Contains timestamp of when reload was initiated
- Checked on service startup to determine if this is a reload

### 2. Service Startup Logic
Modified `service.py` to check for recent reload:

```python
def _is_recent_reload():
    """Check if profile was reloaded recently (within last 10 seconds)"""
    flag_path = _get_reload_flag_path()
    if os.path.exists(flag_path):
        mtime = os.path.getmtime(flag_path)
        age = time.time() - mtime
        if age < 10:  # Within last 10 seconds
            return True
    return False

# In run():
is_reload = _is_recent_reload()

# Startup sync only runs if NOT a recent reload
if cfg.enabled and cfg.on_startup and is_endpoint_valid() and not is_reload:
    # Run startup sync
elif is_reload:
    log_info(kvfmt(event="startup_sync_skipped", reason="recent_profile_reload"))
```

### 3. Set Flag Before LoadProfile
Updated all code that calls `LoadProfile()` to set the flag first:

**Files Modified:**
- `reorder.py` - `reload_favourites()` function
- `sync.py` - Profile reload after sync
- `addon.py` - Profile reload after backup restore

**Example:**
```python
def reload_favourites(manual_context: bool = False, skip_reload: bool = False):
    # Set flag to prevent startup sync from running after reload
    try:
        from service import _set_reload_flag
        _set_reload_flag()
    except:
        pass  # Flag setting is optional
    
    # Now safe to reload profile
    xbmc.executebuiltin("LoadProfile(auto)")
```

## How It Works

### Normal Kodi Startup (schedule_enabled=true)
1. Kodi starts → Service starts
2. No reload flag exists (or > 10 seconds old)
3. `is_reload = False`
4. Startup sync runs as configured ✅

### Normal Kodi Startup (schedule_enabled=false)
1. Kodi starts → Service starts
2. No reload flag exists
3. `is_reload = False`
4. `cfg.enabled = False`
5. Startup sync skipped ✅

### Toggle misc_add_to_fav (schedule_enabled=false)
1. User toggles setting → `onSettingsChanged()` fires
2. `reorder_favourites()` called
3. `_set_reload_flag()` called (creates flag file with current timestamp)
4. `LoadProfile(auto)` executed
5. Profile reloads → **Service restarts**
6. Service checks: `is_reload = _is_recent_reload()` → **True** (flag < 10 seconds old)
7. Startup sync skipped with log: `event=startup_sync_skipped reason=recent_profile_reload` ✅
8. No unwanted sync runs!

### Manual Sync with Profile Reload
1. User runs manual sync
2. Sync modifies `favourites.xml`
3. `_set_reload_flag()` called
4. `LoadProfile(auto)` executed
5. Service restarts
6. Detects recent reload, skips startup sync ✅

## Time Window
- Flag is considered "recent" for **10 seconds**
- This is more than enough for profile reload cycle
- After 10 seconds, flag expires (normal startup sync can run)

## Benefits
✅ No unwanted syncs when toggling misc settings  
✅ No unwanted syncs after manual operations  
✅ Scheduled startup sync still works when enabled  
✅ Simple, file-based flag (no complex state management)  
✅ Degrades gracefully (if flag fails, worst case is one extra sync)  

## Edge Cases Handled
- **Flag creation fails**: Sync may run once extra (harmless)
- **Flag file deleted**: Old flag ignored, acts like normal startup
- **Multiple rapid reloads**: Each sets flag, all skipped within 10s window
- **Service crash**: Old flag becomes stale, normal startup resumes

## Log Messages
- `event=reload_flag_set` - Flag created before LoadProfile
- `event=recent_reload_detected age_seconds=X` - Flag found and recent
- `event=startup_sync_skipped reason=recent_profile_reload` - Sync skipped due to reload

## Version
Fixed in: **v1.0.50**
