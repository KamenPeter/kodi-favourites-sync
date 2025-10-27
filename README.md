# Kodi Favourites Sync (Cloud)

Add-on ID: `plugin.service.favourites-sync` (service) + `plugin.program.favourites-sync` (launcher)  
Version: 1.0.47

Synchronise the active profile's `favourites.xml` with a cloud or network location. Supports on-demand and scheduled sync, bidirectional merging, backups, and multiple backend types (WebDAV, HTTP, S3, SFTP, SMB, NFS, Local).

## Features

- **Pull, Push, and Bidirectional** merge (by label+path)
- **Multiple Backends**: WebDAV, HTTP(S), S3, SFTP, SMB/NAS, NFS, Local Path
- **Security**: HTTPS required, ETag support, redacted logs
- **Scheduler**: Startup and/or shutdown triggers (no more interval/fixed time)
- **Three-way merge**: Tracks last synced state for proper deletion detection
- **Daily log rotation**: Configurable retention (1-30 days)
- **Local JSON-RPC** for automation (127.0.0.1:8765)
- **Two-addon architecture**: Service (background) + Launcher (RUN button)

## Quick install

### Full Installation (Recommended)

1. **Service Addon** (background sync):
   ```
   Settings → Add-ons → Install from zip
   Choose: dist/plugin.service.favourites-sync-1.0.47.zip
   ```

2. **Launcher Addon** (RUN button + manual sync):
   ```
   Settings → Add-ons → Install from zip
   Choose: dist/plugin.program.favourites-sync-1.0.46.zip
   ```

3. **Configure**:
   - Open service addon Settings → Cloud Location
   - Configure your backend (WebDAV, Local, etc.)
   - Press "Validate endpoint"
   - Enable automatic sync and choose schedule mode

4. **Access**:
   - Go to **Programs** → **Favourites Sync Launcher**
   - Or use RUN button in addon info
   - Choose Pull/Push/Bidirectional sync

### Background-Only Installation
If you only want automatic scheduled syncs:
- Install only `dist/plugin.service.favourites-sync-1.0.47.zip`

## Architecture

**Service Addon** (`plugin.service.favourites-sync`)
- Background service for automatic scheduled syncs
- Runs on Kodi startup and shutdown  
- No user-facing UI (service-type addons can't have RUN buttons)
- Configure via addon settings

**Launcher Addon** (`plugin.program.favourites-sync`)
- User interface for manual sync operations
- Appears in Programs menu with working RUN button
- Depends on service addon
- Imports sync functions from service

This two-addon design solves Kodi's limitation where service-type addons don't have enabled RUN buttons.

## OTA repository (optional)

- Host the `repo-root/` directory at `https://example.org/repo-root/` (placeholder)
- Install `repo-root/repository.kamen/repository.kamen-1.0.0.zip` in Kodi to receive updates automatically

## Build

Run build scripts from the repo root (requires Python 3):

```powershell
python tools/build.py
python tools/make_addons_xml.py
python tools/build_repo.py
```

Artifacts:

- `dist/plugin.service.favourites-sync-1.0.47.zip`
- `dist/plugin.program.favourites-sync-1.0.46.zip`
- `repo-root/addons.xml`, `repo-root/addons.xml.md5`
- `repo-root/plugin.service.favourites-sync/plugin.service.favourites-sync-1.0.47.zip`
- `repo-root/plugin.program.favourites-sync/plugin.program.favourites-sync-1.0.46.zip`
- `repo-root/repository.kamen/repository.kamen-1.0.0.zip`

## Publish (OTA hosting)

Option A — copy to your web root served at `https://example.org/repo-root/`:

```powershell
# Adjust this path to your web server root
$WEBROOT = "C:\\inetpub\\wwwroot\\repo-root"
robocopy ".\\repo-root" $WEBROOT /E
```

Option B — publish to a `gh-pages` branch (serving `repo-root/` at https://<user>.github.io/<repo>/repo-root/):

```powershell
git checkout gh-pages
robocopy ".\\repo-root" ".\\" /E
git add -A
git commit -m "Update OTA index and zips for v1.0.0"
git push origin gh-pages
```

## JSON-RPC (local)

POST to `http://127.0.0.1:8765/` with a JSON body:

```json
{ "method": "FavouritesSync.Run", "params": {"mode": "pull", "dry_run": false} }
```

Other methods: `FavouritesSync.Status`, `FavouritesSync.Validate`, `FavouritesSync.ListBackups`.

Override port via env var `FAVSYNC_RPC_PORT`.

## Security

- Only HTTPS/SFTP backends are supported (WebDAV requires HTTPS)
- Secrets are redacted in logs
- Custom CA bundle is supported for self-signed certificates

## License

MIT

