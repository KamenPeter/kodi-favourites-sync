# Installation Guide

## For Kodi Users

### Quick Install (Recommended)

1. **Download the plugin**:
   - Navigate to: `dist/plugin.service.favourites-sync-1.0.2.zip`
   - Or from repo-root: `repo-root/plugin.service.favourites-sync/plugin.service.favourites-sync-1.0.2.zip`

2. **Install in Kodi**:
   - Open Kodi
   - Settings → Add-ons → Install from zip file
   - Navigate to and select `plugin.service.favourites-sync-1.0.2.zip`
   - Wait for "Add-on installed" notification

3. **Configure**:
   - Go to Add-ons → My add-ons → Services → Favourites Sync (Cloud)
   - Select "Configure"
   - Under "Cloud Location (Required)":
     - Set Backend Type to "WebDAV"
     - Enter WebDAV URL (e.g., `https://cloud.example.com`)
     - Enter Path (e.g., `/kodi/favourites/{profile}/favourites.xml`)
     - Enter Username and Password
     - Click "Validate endpoint"
   - Enable scheduling if desired

4. **Run**:
   - Go to Add-ons → Program add-ons → Favourites Sync (Cloud)
   - Choose sync mode: Pull / Push / Bidirectional / Dry-run

### Install with OTA Updates (Advanced)

1. **Install repository**:
   - Install from zip: `repo-root/repository.kamen/repository.kamen-1.0.0.zip`
   - This enables automatic updates when you host the repo

2. **Host the repo** (optional):
   - Upload entire `repo-root/` folder to your web server
   - Edit `repository.kamen/addon.xml` to point to your URL
   - Users will receive automatic updates

## For Developers

### Build from Source

```powershell
# Build plugin
python tools/build.py

# Build repository
python tools/build_repo.py

# Generate OTA index
python tools/make_addons_xml.py
```

### Output Artifacts

- `dist/plugin.service.favourites-sync-1.0.2.zip` - Installable plugin
- `repo-root/plugin.service.favourites-sync/` - Plugin for OTA
- `repo-root/repository.kamen/` - Repository installer
- `repo-root/addons.xml` + `addons.xml.md5` - OTA manifest

## Troubleshooting

### "Failed to unpack archive"
- Make sure you're using version 1.0.2 or later
- Delete any old cached ZIP files
- The ZIP top-level folder MUST be `plugin.service.favourites-sync/`

### Import errors on startup
- Version 1.0.2 fixes relative import issues
- Service should start cleanly and log to addon_data/log.txt

### Icon decode warning
- Cosmetic only, doesn't affect functionality
- Will be fixed in next release with proper PNG

## Status

✅ **Ready for Installation**
- Version: 1.0.2
- Kodi Compatibility: Matrix (19) - Omega (21)
- Python: 3.x
- Working backend: WebDAV (HTTPS)
- Other backends: Stubs provided for future implementation
