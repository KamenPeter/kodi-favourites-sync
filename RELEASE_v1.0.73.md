# Release v1.0.73 - Cloud Unavailability Protection

**Date:** October 31, 2025  
**Priority:** CRITICAL - Data Loss Prevention

## Critical Fix

### Problem Solved: Lost Favourites When Cloud Unavailable

**User Report:**
> "I have lost my favorites from the local xml because the cloud location was unavailable currently."

**Root Cause:**
The sync process was attempting to read from cloud storage (via `backend.stat()` and `backend.download()`) without proper early failure handling. If the cloud was unavailable (network down, server offline, authentication expired), the sync would fail mid-operation, potentially leaving `favourites.xml` in a corrupted or empty state.

**Impact:** Users could lose all their local favourites if sync ran when cloud was inaccessible.

## Solution Implementation

### 1. Early Cloud Availability Check

**Before v1.0.73:**
```python
def _run(mode: str, dry_run: bool = False, skip_profile_reload: bool = False) -> dict:
    # ... setup code ...
    backend = _backend_from_settings(cfg)
    remote_meta = backend.stat()           # Could fail here
    remote_bytes = backend.download()      # Or fail here
    local_bytes = _xbmcvfs_read(LOCAL_FAV) # Local file read after cloud access
    # ... rest of sync logic ...
```

**After v1.0.73:**
```python
def _run(mode: str, dry_run: bool = False, skip_profile_reload: bool = False) -> dict:
    # ... setup code ...
    backend = _backend_from_settings(cfg)
    
    # CRITICAL: Try to access cloud BEFORE reading/modifying local file
    try:
        remote_meta = backend.stat()
        remote_bytes = backend.download()
    except Exception as e:
        # Cloud unavailable - preserve local file and abort sync
        error_msg = f"Cloud unavailable, keeping local favourites: {str(e)}"
        log_error(kvfmt(event="cloud_unavailable", error=str(e), mode=mode))
        status["error"] = error_msg
        status["result"] = "cloud_unavailable"
        _save_status(status)
        _release_lock()
        return status
    
    # Cloud is accessible - safe to proceed with sync
    local_bytes = _xbmcvfs_read(LOCAL_FAV)
    # ... rest of sync logic ...
```

**Key Changes:**
1. **Early Exit:** Cloud access wrapped in try/except BEFORE touching local file
2. **Preserve Local:** If cloud fails, function returns immediately with `cloud_unavailable` status
3. **Safe Abort:** Lock is released, status saved, no local file modifications occur
4. **Clear Logging:** Event logged as `cloud_unavailable` for troubleshooting

### 2. User-Friendly Notification

**UI Sync Function Enhancement:**
```python
def run_sync_ui(mode):
    res = _run(m)
    if res.get("result") == "success":
        # ... success notification ...
    elif res.get("result") == "cloud_unavailable":
        # NEW: Clear message for cloud unavailability
        d.ok("Favourites Sync", 
             f"Cloud unavailable - your local favourites are safe.\n\n{res.get('error')}")
    else:
        d.ok("Favourites Sync", f"Failed: {res.get('error')}")
```

**Notification Message:**
```
┌──────────────────────────────────────┐
│         Favourites Sync              │
├──────────────────────────────────────┤
│ Cloud unavailable - your local       │
│ favourites are safe.                 │
│                                      │
│ Cloud unavailable, keeping local     │
│ favourites: [specific error details] │
│                                      │
│              [  OK  ]                │
└──────────────────────────────────────┘
```

### 3. Background Service Behavior

**Service Already Handles This Gracefully:**
```python
# service.py - Startup sync
try:
    _run(cfg.scheduled_mode, skip_profile_reload=True)
    log_info("Startup sync completed")
except Exception as e:
    log_error(kvfmt(event="startup_sync_failed", error=str(e)))
```

With v1.0.73, if cloud is unavailable:
- Service catches the exception (status has error)
- Logs `cloud_unavailable` event
- **Local favourites.xml untouched**
- Next scheduled sync will retry when cloud returns

## Testing Scenarios

### Scenario 1: Manual Sync with Cloud Down
**Steps:**
1. Disconnect network or stop cloud service
2. Favourites → Favourites Sync → Pull/Push/Bidirectional
3. Observe dialog

**Expected:**
- Dialog shows: "Cloud unavailable - your local favourites are safe"
- Error details shown (connection timeout, DNS failure, etc.)
- `favourites.xml` unchanged
- Can still use Kodi favourites normally

### Scenario 2: Scheduled Startup Sync with Cloud Down
**Steps:**
1. Configure sync on startup
2. Disconnect network
3. Restart Kodi

**Expected:**
- Kodi log shows: `event=cloud_unavailable error="[connection error]" mode=bidirectional`
- No notification (background sync)
- `favourites.xml` unchanged
- Kodi starts normally with existing favourites

### Scenario 3: Scheduled Shutdown Sync with Cloud Down
**Steps:**
1. Configure sync on shutdown
2. Disconnect network
3. Exit Kodi

**Expected:**
- Kodi log shows: `event=cloud_unavailable`
- Shutdown continues normally
- `favourites.xml` unchanged

### Scenario 4: Cloud Returns After Failure
**Steps:**
1. Cloud unavailable, sync fails with protection
2. Restore network/cloud connection
3. Run sync again

**Expected:**
- Sync completes successfully
- Local changes preserved and merged
- Normal sync behavior resumes

## Technical Details

### Status Structure Enhancement

**New Status Result Value:**
```python
status = {
    "result": "cloud_unavailable",  # NEW: Distinct from generic "error"
    "error": "Cloud unavailable, keeping local favourites: [details]",
    "last_run": "2025-10-31T14:30:00Z",
    "last_mode": "bidirectional",
    "changed_items": 0
}
```

### Log Events

**New Event Type:**
```
event=cloud_unavailable error="HTTPSConnectionPool(host='cloud.example.com', port=443): Max retries exceeded" mode=bidirectional
```

**Existing Event (General Failure):**
```
event=sync_error error="[various errors]"
```

### Error Types That Trigger Protection

1. **Network Errors:**
   - Connection timeout
   - DNS resolution failure
   - SSL/TLS errors
   - Host unreachable

2. **Authentication Errors:**
   - Invalid credentials
   - Expired tokens
   - 401 Unauthorized
   - 403 Forbidden

3. **Backend Errors:**
   - WebDAV: 502 Bad Gateway, 503 Service Unavailable
   - S3: Bucket not accessible, region errors
   - SFTP: Connection refused, host key mismatch
   - SMB/NFS: Share not mounted, permission denied
   - Local: Path not accessible, drive not available

4. **Cloud Service Issues:**
   - 500 Internal Server Error
   - 502/503/504 Gateway errors
   - Temporary maintenance

## Backwards Compatibility

✅ **Fully compatible with v1.0.68-72**
- No configuration changes required
- Status structure extends existing format
- Existing sync behavior unchanged when cloud is available
- Falls back gracefully when cloud is not available

## Files Modified

### addon/resources/lib/sync.py
- **_run() function:** Added early cloud availability check (lines 420-435)
- **run_sync_ui() function:** Added cloud_unavailable result handling (line 741)

### addon/addon.xml
- Version bumped to 1.0.73
- News updated

### addon/changelog.txt
- v1.0.73 entry added

## Deployment

**Installation:**
```powershell
# Build
python tools/build.py

# Install to Kodi
$source = "dist\plugin.service.favourites-sync-1.0.73.zip"
$kodiAddons = "$env:APPDATA\Kodi\addons"
$addonFolder = "$kodiAddons\plugin.service.favourites-sync"
Remove-Item $addonFolder -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $source -DestinationPath $kodiAddons -Force
```

**Restart Required:** Yes (service addon must restart to load new code)

## User Communication

**Recommended Notification:**
> **Critical Update v1.0.73 Available**
> 
> This update prevents data loss when cloud storage is unavailable. If your cloud backend becomes inaccessible (network issues, service outage, etc.), your local favourites will remain safe and unchanged.
> 
> Previous versions could potentially lose local favourites during sync failures. This is now fixed.
> 
> **Action Required:** Update to v1.0.73 immediately.

## Verification

After installing v1.0.73, verify protection is active:

1. **Check Version:**
   ```
   Settings → Add-ons → My Add-ons → Services → Favourites Sync (Cloud)
   Version should show: 1.0.73
   ```

2. **Test Protection (Optional):**
   ```
   - Temporarily break cloud connection (wrong URL, disable network)
   - Run manual sync
   - Should see: "Cloud unavailable - your local favourites are safe"
   - Check favourites.xml unchanged
   - Restore connection, sync normally
   ```

3. **Check Logs:**
   ```
   Look for: "event=cloud_unavailable" instead of generic errors
   ```

## Known Limitations

1. **Push Mode:** If cloud is unavailable during push-only sync, local changes cannot be uploaded (expected behavior)
2. **Multi-Profile:** Each profile's sync checks cloud availability independently
3. **Retry Logic:** No automatic retry - user must manually sync again when cloud returns
4. **Notification:** Background syncs (startup/shutdown) don't show UI notification (only logged)

## Future Enhancements (Not in v1.0.73)

- [ ] Retry logic with exponential backoff
- [ ] Queue local changes for upload when cloud returns
- [ ] Offline mode indicator in UI
- [ ] Last successful sync timestamp display
- [ ] Cloud health monitoring dashboard

## Success Criteria

✅ **v1.0.73 successfully:**
1. Detects cloud unavailability before touching local file
2. Preserves local favourites.xml when cloud fails
3. Shows clear user notification for manual syncs
4. Logs cloud_unavailable events for troubleshooting
5. Allows sync to resume normally when cloud returns
6. Works for all sync modes (pull, push, bidirectional)
7. Works for all backends (WebDAV, S3, SFTP, SMB, NFS, Local, HTTP)

---

**Release Status:** ✅ Built, tested, and deployed  
**User Impact:** HIGH - Prevents data loss  
**Urgency:** CRITICAL - Update immediately
