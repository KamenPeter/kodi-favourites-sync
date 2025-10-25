# Kodi Favourites Sync (Cloud)

Add-on ID: `plugin.service.favourites-sync`

Synchronise the active profile's `favourites.xml` with a cloud or network location. Supports on-demand and scheduled sync, bidirectional merging, backups, and a WebDAV backend.

## Features

- Pull, Push, and Bidirectional merge (by label+path)
- WebDAV backend (HTTPS, Basic/Bearer, ETag, COPY for backups)
- Atomic writes and local backup rotation
- Scheduler (interval, fixed time, on startup)
- Local JSON-RPC for automation (127.0.0.1:8765)
- Logs with redacted secrets written to addon_data/log.txt

## Quick install

1. In Kodi, Settings → Add-ons → Install from zip
2. Choose the built zip: `dist/plugin.service.favourites-sync-1.0.2.zip`
3. Open the add-on's Settings → Cloud Location, configure WebDAV and press "Validate endpoint" (or simply close Settings to auto-validate)
4. Run the add-on and choose a sync action

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

- `dist/plugin.service.favourites-sync-1.0.2.zip`
- `repo-root/addons.xml`, `repo-root/addons.xml.md5`
- `repo-root/plugin.service.favourites-sync/plugin.service.favourites-sync-1.0.2.zip`
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

