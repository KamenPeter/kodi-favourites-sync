# Changelog

## 1.0.17 (2025-10-26)

**DEBUGGING AND FIX:**
- Changed: Extension point from xbmc.python.script to xbmc.python.pluginsource (may fix RUN button)
- Added: TEST button in settings to manually trigger addon menu (test if RUN button issue is Kodi-side)
- Added: Comprehensive debug logging in addon.py main() to trace execution
- Added: Logging shows when addon is called, menu displayed, choices made, validation results
- Debug: Every step now logged to help identify why RUN button stays disabled

## 1.0.16 (2025-10-26)

**MAJOR UX IMPROVEMENT:**
- Changed: RUN button now ALWAYS enabled - no more blocking the UI
- Changed: Menu shows immediately when addon is opened
- Changed: Configuration check only happens when user tries to sync (Pull/Push/Bidirectional/Dry-run)
- Fixed: User can now access Settings, Restore, Status, and other features without validation
- Improved: Better user experience - don't block access, handle gracefully when needed

## 1.0.15 (2025-10-26)

- Fixed: validate_endpoint() call in settings_mgr.py - removed non-existent save_result parameter
- Added: Better error logging in is_endpoint_valid() to diagnose validation failures
- Improved: Exception handling shows actual error message in logs for troubleshooting

## 1.0.14 (2025-10-25)

**BREAKING CHANGE - Complete redesign of validation approach:**
- Removed: endpoint_valid hidden setting that was causing persistence issues
- Changed: is_endpoint_valid() now validates on-demand every time it's called
- Fixed: Validation now works correctly - checks settings and validates connection
- Fixed: Settings window no longer closes unexpectedly
- Fixed: RUN button now appears when endpoint is actually reachable
- Simplified: No more trying to save validation state - just validate when needed
- Reverted versions 1.0.10-1.0.13 which attempted to fix a fundamentally flawed approach

## 1.0.13 (2025-10-25) - DEPRECATED

- Fixed: Settings window closing unexpectedly after validation
- Fixed: Removed auto-validation from onSettingsChanged() that was causing settings dialog to close
- Added: On-demand validation when opening addon - automatically validates and enables RUN button
- Changed: Validation workflow - validate button shows feedback, opening addon saves the validation result
- Improved: User experience - settings stay open until user clicks OK

## 1.0.12 (2025-10-25)

- Added: Debug logging for endpoint_valid flag to diagnose persistence issues
- Added: Logging in service.py onSettingsChanged() to track validation results
- Added: Logging in addon.py to track endpoint validation checks

## 1.0.11 (2025-10-25)

- Fixed: Validation button now doesn't save endpoint_valid flag (only shows feedback)
- Changed: Auto-validation moved to service.py onSettingsChanged() callback
- Changed: endpoint_valid flag saved only when user clicks OK in settings
- Added: save_result parameter to validate_endpoint() function for better control

## 1.0.10 (2025-10-25)

- Fixed: endpoint_valid setting not persisting after validation
- Changed: validate_endpoint() now accepts optional addon_instance parameter
- Fixed: validate_action.py now passes properly initialized addon instance to validation
- Improved: Settings persistence by using same addon instance for reading and writing

## 1.0.9 (2025-10-25)

- Added: Local Path backend driver - supports local files and Windows UNC paths (\\server\share)
- Added: Full implementation of Local Path driver with stat(), download(), upload(), copy_backup()
- Fixed: Atomic writes for local files (write to .tmp then rename)
- Fixed: Auto-create parent directories if they don't exist
- Updated: Settings note now shows "WebDAV and Local Path are currently implemented"
- Now supports: Network shares (\\NAS\share\path) and local paths (C:\sync\path)

## 1.0.8 (2025-10-25)

- Fixed: Validate endpoint button crash - "No valid addon id could be obtained" error
- Fixed: logutil.py now handles being called from RunScript context without proper addon ID
- Fixed: sync.py now initializes with explicit addon ID fallback
- Fixed: validate_action.py properly initializes addon context before importing modules
- All modules now handle scripts run outside normal Kodi addon execution context

## 1.0.7 (2025-10-25)

- Fixed: Settings visibility conditions broken in 1.0.5 - backend-specific fields now show/hide correctly
- Fixed: Removed profile_subfolder field that was breaking visibility offset calculations
- Changed: Renamed "Backend Type" to "Type" for cleaner UI
- Fixed: All backend fields (WebDAV, S3, HTTP, SFTP, SMB, NFS, Local) now properly conditional based on Type selection

## 1.0.6 (2025-10-25)

- Added: Welcome dialog on first install offering to configure cloud storage immediately
- Added: "Add to Favourites" menu option for easy access from Kodi favourites menu
- Added: First-run detection using hidden setting to show welcome dialog only once
- Improved: User experience for new installations with guided setup

## 1.0.5 (2025-10-25)

- Fixed: Infinite loop in settings validation that caused hundreds of errors
- Fixed: Removed auto-validation on every settings change (now only validates when button clicked)
- Added: Separate validate_action.py script for proper action button handling
- Added: Note in settings that only WebDAV backend is currently implemented
- Updated: settings.xml validate button now uses RunScript action

## 1.0.4 (2025-10-25)

- Fixed: Enum settings now use `values` attribute instead of deprecated `lvalues` for Kodi v19+ compatibility
- Fixed: All 6 enum dropdowns (backend, schedule_mode, scheduled_mode, conflict_policy, scheduled_conflict, log_level) now display correct options instead of "Programs"

## 1.0.3 (2025-10-25)

- Fixed: Settings.xml password fields now use `type="text" option="hidden"` instead of deprecated `type="password"` for Kodi v19+ compatibility
- Fixed: dialog.ok() calls updated to use 2-argument format (title, message with newlines) instead of deprecated 3-4 argument format

## 1.0.2 (2025-10-25)

- Fixed: Deprecated `xbmc.translatePath()` replaced with `xbmcvfs.translatePath()` for Kodi v19+ compatibility
- Updated: All modules (sync.py, addon.py, logutil.py) now use correct xbmcvfs API

## 1.0.1 (2025-10-25)

- Fixed: ZIP packaging structure for Kodi compatibility (tFop-level folder must be add-on ID)
- Fixed: Import errors by adding fallback to absolute imports when run as Kodi script
- Fixed: Repository naming aligned with DEFINITION.md (repository.kamen instead of repository.yourname)
- Updated: Build scripts to ensure correct structure
- Updated: Provider name set to "Kamen" per specification

## 1.0.0 (2025-10-25)

- Initial release of `plugin.service.favourites-sync`
- On-demand Pull/Push/Bidirectional (with merge)
- WebDAV backend with HTTPS, auth, ETag
- Backups with rotation and atomic writes
- Scheduler with interval/fixed-time/startup modes
- Local JSON-RPC on 127.0.0.1:8765 for Run/Status/Validate/ListBackups
- English and Slovak localisations
- OTA repository skeleton and build scripts
