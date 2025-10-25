\# DEFINITION.md



\### Kodi Favourites Sync (Cloud)



\*\*Add-on ID:\*\* `plugin.service.favourites-sync`

\*\*Version:\*\* `1.0.0`

\*\*Provider:\*\* `Kamen`

\*\*Date:\*\* 2025-10-25

\*\*License:\*\* MIT



---



\## 1️⃣ GOALS



The purpose of this Kodi add-on is to \*\*synchronize the active profile’s favourites\*\* (`favourites.xml`) between Kodi and a user-defined \*\*cloud or network location\*\*.



Users can:



\* Sync \*\*on demand\*\* or \*\*automatically on a schedule\*\*

\* Choose \*\*pull, push, or bidirectional merge\*\*

\* Store favourites on \*\*cloud storage, NAS, or network share\*\*

\* Control \*\*conflict resolution\*\*, \*\*backups\*\*, and \*\*logging\*\*



The add-on must be robust, user-friendly, and secure.

It should gracefully handle missing configuration, network failures, and concurrent edits.



---



\## 2️⃣ FEATURES OVERVIEW



| Feature                    | Description                                                   |

| -------------------------- | ------------------------------------------------------------- |

| \*\*On-demand sync\*\*         | Manual trigger via Program Add-on UI                          |

| \*\*Scheduled sync\*\*         | Automatic sync at intervals or fixed times                    |

| \*\*Backend drivers\*\*        | Modular adapters (WebDAV, S3, HTTP(S), SFTP, SMB, NFS, Local) |

| \*\*Conflict policies\*\*      | Prefer Cloud / Prefer Local / Merge / Manual                  |

| \*\*Local \& remote backups\*\* | Timestamped XML backups                                       |

| \*\*Endpoint validation\*\*    | Mandatory before any sync runs                                |

| \*\*Atomic writes\*\*          | Always write to temporary file, then replace                  |

| \*\*Hash tracking\*\*          | Use SHA-256 to detect changes and conflicts                   |

| \*\*JSON-RPC API\*\*           | Remote trigger and status query                               |

| \*\*Multilingual UI\*\*        | English \& Slovak localization                                 |

| \*\*OTA repository ready\*\*   | Supports Kodi’s update mechanism via hosted repo              |



---



\## 3️⃣ DIRECTORY STRUCTURE



```

plugin.service.favourites-sync/

├── addon.xml

├── changelog.txt

├── icon.png

├── fanart.jpg

├── README.md

├── resources/

│   ├── settings.xml

│   ├── language/

│   │   ├── resource.language.en\_gb/strings.po

│   │   └── resource.language.sk\_sk/strings.po

│   └── lib/

│       ├── addon.py

│       ├── service.py

│       ├── sync.py

│       ├── xmlio.py

│       ├── settings\_mgr.py

│       ├── rpc.py

│       ├── logutil.py

│       ├── version.py

│       └── drivers/

│           ├── webdav.py

│           ├── s3.py

│           ├── http.py

│           ├── sftp.py

│           ├── smb.py

│           └── local.py

```



---



\## 4️⃣ SETTINGS SCHEMA



\### Categories



| Category                      | Key                            | Type        | Description                                                       |

| ----------------------------- | ------------------------------ | ----------- | ----------------------------------------------------------------- |

| \*\*Cloud Location (Required)\*\* | `backend`                      | enum        | `WebDAV`, `S3`, `HTTP(S)`, `SFTP`, `SMB/NAS`, `NFS`, `Local Path` |

|                               | `endpoint` / `path` / `bucket` | text        | Remote target                                                     |

|                               | `username`, `password`         | credentials | Auth for WebDAV/SFTP/SMB                                          |

|                               | `validate\_button`              | action      | Runs endpoint test                                                |

|                               | `endpoint\_valid`               | bool        | Read-only, must be true to enable sync                            |

| \*\*Scheduling\*\*                | `schedule\_enabled`             | bool        | Enables background service                                        |

|                               | `schedule\_mode`                | enum        | `Interval`, `Fixed time`, `On startup only`                       |

|                               | `interval\_minutes`             | number      | e.g. 60                                                           |

|                               | `fixed\_time\_local`             | time        | e.g. 03:30                                                        |

|                               | `run\_on\_startup`               | bool        | Run at Kodi start                                                 |

|                               | `startup\_delay\_seconds`        | number      | Delay before run                                                  |

|                               | `scheduled\_mode`               | enum        | Default sync direction for scheduler                              |

| \*\*Conflict Policy\*\*           | `conflict\_policy`              | enum        | Default for manual sync                                           |

|                               | `scheduled\_conflict`           | enum        | Behaviour for conflicts in scheduled runs                         |

| \*\*Backups\*\*                   | `local\_backups`                | bool        | Enable local backups                                              |

|                               | `backup\_count`                 | number      | Max backup files                                                  |

| \*\*Advanced\*\*                  | `timeout\_sec`, `retry\_count`   | number      | Networking controls                                               |

| \*\*Logging\*\*                   | `log\_level`, `log\_network`     | enum/bool   | INFO/DEBUG, trace toggle                                          |



\*\*Note:\*\* Add-on must refuse operation if `endpoint\_valid = false`.



---



\## 5️⃣ BACKEND DRIVER INTERFACE



Every backend must inherit the same interface.

Drivers live in `resources/lib/drivers/`.



```python

class BackendBase:

&nbsp;   """Abstract interface for cloud storage backends."""



&nbsp;   def stat(self) -> dict:

&nbsp;       """Return metadata: {'etag': str, 'modified\_at': str, 'size': int}.

&nbsp;       Should raise IOError if unreachable."""

&nbsp;       raise NotImplementedError



&nbsp;   def download(self) -> bytes:

&nbsp;       """Return raw bytes of remote favourites.xml."""

&nbsp;       raise NotImplementedError



&nbsp;   def upload(self, data: bytes, metadata: dict) -> None:

&nbsp;       """Upload new data to remote path. Should overwrite existing file safely."""

&nbsp;       raise NotImplementedError



&nbsp;   def copy\_backup(self, backup\_name: str) -> None:

&nbsp;       """Optionally copy current remote file to backup (timestamped) name."""

&nbsp;       pass

```



\### Example: WebDAV driver



Implements:



\* HTTP GET/PUT

\* Basic Auth or Bearer token

\* TLS validation

\* ETag headers (`If-None-Match`)

\* Returns metadata for caching/conflict detection



---



\## 6️⃣ SYNC LOGIC FLOW



\### Core Steps (for any run)



1\. \*\*Validate endpoint\*\*

2\. \*\*Download remote XML\*\* → `remote.xml`

3\. \*\*Read local XML\*\* → `local.xml`

4\. \*\*Compute hashes\*\*

5\. \*\*Compare hashes vs last\_sync metadata\*\*

6\. \*\*Resolve conflicts per policy\*\*

7\. \*\*Write backup (local + optional remote)\*\*

8\. \*\*Write updated file atomically\*\*

9\. \*\*Upload to remote (if push or merge)\*\*

10\. \*\*Update metadata file (`status.json`)\*\*

11\. \*\*Notify user (UI or log)\*\*



\### Atomic write pattern



```python

tmp = path + ".tmp"

with open(tmp, "wb") as f:

&nbsp;   f.write(data)

os.replace(tmp, path)

```



---



\## 7️⃣ CONFLICT POLICIES



| Policy                  | Description                                              |

| ----------------------- | -------------------------------------------------------- |

| \*\*Prefer Cloud\*\*        | Always replace local file with remote version            |

| \*\*Prefer Local\*\*        | Always upload local file to cloud                        |

| \*\*Bidirectional Merge\*\* | Parse both XMLs, merge favourites by `(label, path)` key |

| \*\*Manual Review\*\*       | Stop, show preview of differences, ask user              |



Conflict detection logic:



```python

if local\_hash != last\_synced\_hash and remote\_hash != last\_synced\_hash:

&nbsp;   conflict = True

```



---



\## 8️⃣ BACKUP STRATEGY



\### Local backup



\* File: `favourites\_YYYYMMDD-HHMMSS.xml.bak`

\* Stored in `special://profile/addon\_data/plugin.service.favourites-sync/`

\* Controlled by `backup\_count`



\### Remote backup



\* Supported by S3 versioning or WebDAV `COPY` command



---



\## 9️⃣ JSON-RPC CONTRACT



Expose RPC interface for integration with other tools.



| Method                       | Params         | Returns               |                                   |                                                   |

| ---------------------------- | -------------- | --------------------- | --------------------------------- | ------------------------------------------------- |

| `FavouritesSync.Run`         | `{"mode":"pull | push                  | bidirectional", "dry\_run":false}` | Result JSON (`status`, `changed\_items`, `errors`) |

| `FavouritesSync.Status`      | none           | Last sync status JSON |                                   |                                                   |

| `FavouritesSync.Validate`    | none           | Validation result     |                                   |                                                   |

| `FavouritesSync.ListBackups` | none           | List of local backups |                                   |                                                   |



\*\*Error codes\*\*



\* 400 → Missing endpoint

\* 401 → Unauthorized

\* 500 → Generic sync failure



---



\## 🔁 EXAMPLE FLOWS



\### Example 1 — On-Demand Pull



```

User selects “Sync Now → Pull”

&nbsp;→ Validate endpoint

&nbsp;→ Download cloud favourites.xml

&nbsp;→ Backup local file

&nbsp;→ Replace local file

&nbsp;→ Update status.json

&nbsp;→ Notify user: “Sync completed successfully.”

```



\### Example 2 — Scheduled Bidirectional Merge



```

Service timer triggers (03:30)

&nbsp;→ Load config, check endpoint\_valid

&nbsp;→ Download remote + load local

&nbsp;→ Compute hashes, detect conflict

&nbsp;→ Merge XML (union of favourites)

&nbsp;→ Write new local file, upload merged result

&nbsp;→ Update last\_sync metadata

&nbsp;→ Log summary

```



\### Example 3 — Manual Review Conflict



```

Detected change on both sides

&nbsp;→ Open preview dialog:

&nbsp;     Added: 3   Changed: 2   Removed: 0

&nbsp;→ User picks “Apply Merge”

&nbsp;→ Perform merge, save backups, upload merged XML

```



---



\## 🔐 SECURITY REQUIREMENTS



\* Use \*\*HTTPS/SFTP\*\* only for remote communication

\* Validate TLS certificates

\* Store credentials in Kodi settings (plaintext warning in docs)

\* Redact passwords in logs

\* Support custom CA path for self-signed certificates



---



\## 🧩 FILES AND MODULES



\### `addon.py`



\* Main Program Add-on entry point.

\* Displays menu:



&nbsp; \* Pull / Push / Bidirectional / Dry-run

\* Checks endpoint validity before allowing sync.



\### `service.py`



\* Background service loop.

\* Reads scheduling configuration.

\* Triggers sync periodically or at startup.



\### `settings\_mgr.py`



\* Wraps `xbmcaddon.Addon()`

\* Exposes `is\_endpoint\_valid()`, `schedule\_config()`

\* Opens Kodi settings window on request



\### `sync.py`



\* Core synchronization logic.

\* Imports backend dynamically:



&nbsp; ```python

&nbsp; from .drivers import webdav, s3, http, sftp, smb, local

&nbsp; backend = webdav.Driver(cfg)

&nbsp; ```

\* Handles merge, backups, metadata.



\### `xmlio.py`



\* Utility to parse, validate, and merge favourites XMLs.

\* Normalization (ignore whitespace, order).

\* Element-wise merge:



&nbsp; ```python

&nbsp; key = (label, path)

&nbsp; ```



\### `logutil.py`



\* Unified logging with prefixes `\[fav-sync]`.



\### `rpc.py`



\* JSON-RPC methods for external integration.



\### `version.py`



\* Stores static version info.



\### `drivers/`



\* Contains one module per backend implementing `BackendBase`.



---



\## 🧠 JSON STRUCTURE: STATUS \& METADATA



`status.json`

Saved under `special://profile/addon\_data/plugin.service.favourites-sync/`



```json

{

&nbsp; "last\_run": "2025-10-25T09:00:00Z",

&nbsp; "last\_mode": "pull",

&nbsp; "result": "success",

&nbsp; "changed\_items": 5,

&nbsp; "endpoint\_valid": true,

&nbsp; "error": null

}

```



---



\## 🧭 UI LOGIC



\### Main Menu



```

▶ Sync Now

▶ Restore from Backup…

▶ Last Sync Status

▶ Settings

```



\### Dialog messages



\* Missing endpoint:



&nbsp; > “Cloud favourites location is not configured.

&nbsp; > Open Settings → Cloud Location to set it up.”



\* Dry-run summary:



&nbsp; > Added: 3 | Changed: 2 | Removed: 0



---



\## 🧾 LOGGING FORMAT



All logs are key=value format:



```

event=sync\_start mode=pull

event=cloud\_stat etag=abc123 modified\_at=2025-10-25T08:00Z

event=backup\_saved file=favourites\_20251025-0800.xml.bak

event=sync\_success duration\_ms=1245 changed=5

event=error type=network timeout=10s retry=1/3

```



Stored at:



```

special://profile/addon\_data/plugin.service.favourites-sync/log.txt

```



---



\## ⚙️ OTA REPOSITORY STRUCTURE



```

repo-root/

&nbsp; addons.xml

&nbsp; addons.xml.md5

&nbsp; plugin.service.favourites-sync/

&nbsp;   plugin.service.favourites-sync-1.0.0.zip

&nbsp; repository.kamen/

&nbsp;   repository.kamen-1.0.0.zip

```



\### Repository Add-on



```xml

<addon id="repository.kamen" name="Kamen Repo" version="1.0.0">

&nbsp; <extension point="xbmc.addon.repository" name="Kamen Repo">

&nbsp;   <info>https://your.domain/repo-root/addons.xml</info>

&nbsp;   <checksum>https://your.domain/repo-root/addons.xml.md5</checksum>

&nbsp;   <datadir>https://your.domain/repo-root/</datadir>

&nbsp; </extension>

</addon>

```



When hosted, Kodi auto-updates the add-on by reading `addons.xml`.



---



\## ⚙️ EXAMPLE BUILD FLOW



1\. `tools/build.py` zips `/addon` → `/dist/plugin.service.favourites-sync-x.y.z.zip`

2\. Copy zip to `repo-root/plugin.service.favourites-sync/`

3\. `tools/make\_addons\_xml.py` regenerates `addons.xml` \& `addons.xml.md5`

4\. Commit \& push to OTA hosting branch (`gh-pages` or S3)



---



\## 🧩 GIT STRUCTURE RECOMMENDATION



```

kodi-favourites-sync/

├─ addon/                # Source code

├─ dist/                 # Build artifacts

├─ repo-root/            # OTA index

├─ repository.kamen/  # Repository add-on

├─ tools/                # Build scripts

├─ docs/                 # Documentation

└─ .github/workflows/    # CI/CD (optional)

```



\* Tag releases as `vX.Y.Z`

\* Version bump = edit `addon/addon.xml` + `resources/lib/version.py`

\* CI builds zips, updates repo-root, and publishes OTA index



---



\## 🧪 TEST CASES



| Type         | Test                                        |

| ------------ | ------------------------------------------- |

| Validation   | Missing endpoint → no sync allowed          |

| Pull         | Download cloud version to local             |

| Push         | Upload local version to remote              |

| Merge        | Bidirectional merge with duplicates         |

| Conflict     | Detected change both sides → policy applied |

| Schedule     | Interval and fixed-time triggers            |

| Backup       | Rotation beyond configured limit            |

| Remote       | S3 and WebDAV upload success                |

| Security     | TLS cert rejection works                    |

| Localization | EN/SK UI displayed correctly                |



---



\## 🔚 SUMMARY



This add-on’s architecture allows:



\* Modular backend extensibility

\* Transparent user control

\* Safe synchronization

\* Multi-device compatibility

\* OTA update capability



Deliverables include:



\* Source structure

\* Localizations (EN/SK)

\* Configurable settings

\* JSON-RPC API

\* Versioning \& repository model



---



✅ \*\*Next Step for AI Developer\*\*

Implement:



\* WebDAV backend (requests-based GET/PUT with ETag)

\* XML merge utility (`xmlio.py`)

\* Core sync orchestration (`sync.py`)

\* JSON-RPC server (`rpc.py`)

\* Proper log handling and backup rotation



All other scaffolding (settings, UI, service, structure) already defined here.



---



> \*\*End of Definition File — `DEFINITION.md`\*\*



