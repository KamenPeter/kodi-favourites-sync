# Installation Guide

## For Kodi Users

### Quick Install (Recommended)

1. **Download the ZIPs**:
   - Service: `dist/plugin.service.favourites-sync-1.0.48.zip`
   - Launcher: `dist/plugin.program.favourites-sync-1.0.1.zip`
   - OTA equivalents live under `repo-root/<addon id>/`

2. **Install the service in Kodi**:
   - Settings → Add-ons → Install from zip file
   - Select `plugin.service.favourites-sync-1.0.48.zip`
   - Wait for "Add-on installed" notification

3. **Install the launcher**:
   - Settings → Add-ons → Install from zip file
   - Select `plugin.program.favourites-sync-1.0.46.zip`
   - This provides a RUN button under Programs menu

4. **Configure the service**:
   - Add-ons → My add-ons → Services → Favourites Sync (Cloud)
   - Select "Configure"
   - Fill in Cloud Location details and click "Validate endpoint"
   - Adjust scheduling (startup/shutdown) as desired

5. **Run a sync**:
   - Programs → Favourites Sync Launcher
   - Choose Pull / Push / Bidirectional
   - Or use the RUN button in addon info

### Install with OTA Updates (Advanced)

1. **Install repository**:
   - Install from zip: `repo-root/repository.kamen/repository.kamen-1.0.0.zip`
   - Enables automatic updates when you host the repo

2. **Host the repo** (optional):
   - Upload the entire `repo-root/` folder to your web server
   - Update `repository.kamen/addon.xml` with your URL
   - Kodi clients receive updates for both service and launcher

## For Developers

### Build from Source

```powershell
# Build add-on ZIPs (service + launcher)
python tools/build.py

# Generate OTA manifest
python tools/make_addons_xml.py

# Package repository add-on
python tools/build_repo.py
```

### Output Artifacts

- `dist/plugin.service.favourites-sync-1.0.48.zip`
- `dist/plugin.program.favourites-sync-1.0.46.zip`
- `repo-root/plugin.service.favourites-sync/` (service ZIPs)
- `repo-root/plugin.program.favourites-sync/` (launcher ZIPs)
- `repo-root/repository.kamen/` (repository installer)
- `repo-root/addons.xml` + `addons.xml.md5`

## Troubleshooting

### "Failed to unpack archive"
- Verify you are installing version 1.0.48 (service) or 1.0.46 (launcher) or later
- Delete cached ZIPs before reinstalling
- Service ZIP must contain top-level folder `plugin.service.favourites-sync/`

### Launcher missing from Programs
- Ensure `plugin.program.favourites-sync` is installed
- Launcher depends on the service add-on (Kodi will prompt if missing)

### No sync after installing
- Confirm endpoint validation succeeded in service settings
- Check `Kodi/userdata/addon_data/plugin.service.favourites-sync/log.txt` for errors

## Status

✅ **Ready for Installation**
- Service version: 1.0.48
- Launcher version: 1.0.46
- Kodi Compatibility: Matrix (19) - Omega (21)
- Python: 3.x
- Implemented backends: WebDAV, Local Path, HTTP(S), SMB/NAS, NFS, S3, SFTP
