# 🧠 AI DEVELOPER PROMPT — Multi-Profile Awareness & Cross-Profile Add

**Role:** Senior Kodi add-on engineer
**Project:** `plugin.service.favourites-sync`
**Goal:** Add **multi-profile awareness** and a **user-prompted cross-add to other profiles** (Option B). No file-watch loops. No cross-removal automation (parked for later). Keep the existing 3-way sync logic intact.

---

## 🔭 Scope (Phases)

* **Phase 1 — Profiles Manager (backend only)**

  * Discover Kodi profiles, manage a `profiles.json` map, provide secure (optional) credential storage for each profile’s backend.

* **Phase 2 — “Manage Profiles…” UI**

  * One Settings → action opens a custom dialog to edit profiles (backend, endpoint, credentials, schedule flags), and validate endpoints.

* **Phase 3 — Cross-Add to Other Profiles (Option B)**

  * A user-triggered action that, for the currently selected media item, prompts which profiles to add it to, then writes to those profiles’ `favourites.xml`.
  * No polling. No automatic removals.
  * Optional “Sync now” after add.

> (A later Phase 4 will hook startup/shutdown multi-profile sync by iterating the profiles map, but you may implement it now if trivial.)

---

## 🗂 Files to create / modify

```
resources/lib/
  profiles_mgr.py        # NEW: profile discovery, profiles.json R/W, encryption helpers
  ui_profiles.py         # NEW: “Manage Profiles” dialog (edit per-profile config)
  ui_cross_add.py        # NEW: cross-add prompt for picking target profiles
  context_cross_add.py   # NEW: entry to run cross-add flow (read current selection → dialog)
  settings_mgr.py        # MODIFY: add “Manage Profiles…” action wiring
  xmlio.py               # MODIFY: helper to write favourite entry to a given profile path
  sync.py                # MODIFY: add thin wrapper run_sync_for_profile(profile_name, ...)
  logutil.py             # MODIFY: add profile=<name> to log helpers (optional convenience)
```

Also:

* `addon.xml` — add a **script entry-point** (to run cross-add) and a **settings action hook** (see wiring below).
* `resources/settings.xml` — add a Settings category action: **“Manage Profiles…”** (opens `ui_profiles.py`).

---

## 🧱 Data & security

### 1) `profiles.json` schema (stored per active Kodi profile)

Path:
`special://profile/addon_data/plugin.service.favourites-sync/profiles.json`

```json
{
  "version": 1,
  "profiles": {
    "M":  {
      "backend": "webdav",
      "config": {
        "url": "https://cloud.example.com/remote.php/dav/files/user/favourites.xml",
        "user": "user",
        "password": "ENC:base64-blob"   // optional, encrypted (see crypto helpers)
      },
      "schedule": { "on_start": true, "on_shutdown": false, "mode": "bidirectional" },
      "conflict_policy": "merge",
      "cross_add": { "enabled": true, "auto_targets": ["M1","M2"] }  // used by UI; no automation here
    },
    "M1": { "backend": "smb", "config": { "path": "\\\\nas\\m1\\favourites.xml", "user": "nasuser", "password": "" }, ... },
    "M2": { ... },
    "T":  { ... }
  }
}
```

Notes:

* `password` is **optional** and stored **encrypted** on this device (see below).
* A profile **exists** if a folder is under `special://userdata/profiles/<ProfileName>/`.

### 2) Crypto helpers (device-local)

* Create `keystore.json` in addon_data with:

  ```json
  { "salt": "<random-16-bytes-base64>" }
  ```
* Derive a local key (e.g., `SHA256(addon_id + machine_id + salt)` → 32 bytes → use Fernet or AES-GCM).
* Provide:

  ```python
  def encrypt_secret(plain: str) -> str:  # returns "ENC:<b64>"
  def decrypt_secret(enc: str) -> str:    # accepts "ENC:...", returns plain
  ```
* If crypto lib unavailable, fall back to XOR+base64 with salt (still obfuscation). Document clearly.

---

## 🧰 Phase 1 — `profiles_mgr.py` (backend)

### Functions

```python
def list_kodi_profiles() -> dict[str, str]:
    """
    Returns { profile_name: absolute_profile_dir }
    Example: { "M": "/.../profiles/M", "M1": "/.../profiles/M1" }
    """

def profile_favourites_path(profile_name: str) -> str:
    """Return full path to that profile's favourites.xml."""

def load_profiles_cfg() -> dict:
    """Load profiles.json (create default structure if missing)."""

def save_profiles_cfg(cfg: dict) -> None:
    """Atomic write of profiles.json."""

def get_profile_cfg(cfg: dict, profile_name: str) -> dict:
    """Return cfg for one profile (may be empty dict if not configured)."""

def set_profile_cfg(cfg: dict, profile_name: str, new_cfg: dict) -> dict:
    """Insert/update profile config; returns modified cfg."""

def encrypt_secret(plain: str) -> str: ...
def decrypt_secret(maybe_enc: str) -> str: ...
```

### Validation helper (reuse existing driver factory)

```python
def validate_profile_endpoint(pcfg: dict) -> tuple[bool, str]:
    """
    Instantiate backend driver from pcfg['backend'], pcfg['config'].
    Try stat()/download head. Return (ok, message).
    """
```

---

## 🧩 Phase 2 — “Manage Profiles…” UI (`ui_profiles.py`)

### Settings wiring

In `resources/settings.xml`, add in a suitable category (e.g., Cloud or Advanced):

```xml
<setting id="profiles_manage" type="action" label="Manage Profiles…" option="close"/>
```

In `settings_mgr.py`, on this action, run:

```python
import xbmc
xbmc.executebuiltin(f'RunScript({addon_id}, action=manage_profiles)')
```

And in `addon.py` (or a small router), parse `sys.argv` / plugin params:

* if `action=manage_profiles` → call `ui_profiles.open_dialog()`.

### Dialog behavior

* List discovered Kodi profiles in a table:

  ```
  Name   Backend   OnStart   OnShutdown   Policy    [Edit]
  M      WebDAV    ✓         –            Merge     [Edit]
  M1     SMB       –         ✓            Merge     [Edit]
  M2     S3        ✓         ✓            PreferLocal [Edit]
  T      WebDAV    –         –            Merge     [Edit]
  ```
* Buttons:

  * **Edit** → open sub-dialog (fields below)
  * **Validate** (per profile)
  * **Save** and **Close**

**Edit profile** sub-dialog fields (dynamic by backend):

* Backend type (enum): WebDAV | S3 | HTTP(S) | SFTP | SMB/NAS | NFS | Local Path
* Endpoint fields (url/path/bucket/etc.)
* Credentials (user / password text boxes; mask password; store encrypted if not empty)
* Schedule: on_start (bool), on_shutdown (bool), mode (enum pull/push/bidirectional)
* Conflict policy (enum): prefer_remote / prefer_local / merge
* Cross-add (enabled bool), default auto_targets (multi-select) — affects the prompt defaults only
* **Validate** button → calls `profiles_mgr.validate_profile_endpoint()`, shows toast
* Save → writes to `profiles.json` (atomic), toast success

> Do not run any sync here; only validate and save.

---

## ➕ Phase 3 — Cross-Add to Other Profiles (Option B)

### UX & flow

* User is browsing any media list in Kodi.
* User triggers **“Add to favourites (for other profiles)…”**.
* Dialog lists `profiles.json` entries with `cross_add.enabled = true`.
* User selects targets and clicks OK.
* Add-on **appends** a `<favourite>` entry to each selected profile’s favourites.xml (atomic, with backup).
* Optional checkbox “Sync selected profiles now” → if checked, call `run_sync_for_profile()` for each target with `skip_profile_reload=True`.

### Invocation options (choose at least one)

**A. Program Add-on entry**

* Inside the add-on’s own menu, add: **“Add to favourites for other profiles…”**
* When clicked while a list item is focused, use:

  ```python
  label = xbmc.getInfoLabel('ListItem.Label')
  path  = xbmc.getInfoLabel('ListItem.FolderPath') or xbmc.getInfoLabel('ListItem.FileNameAndPath')
  thumb = xbmc.getInfoLabel('ListItem.Art(thumb)')
  ```

  (If no selection context, show a helpful message.)

**B. Script entry (for context mapping / keymap)**

* In `addon.xml`, add a `xbmc.python.script` entry point so users (or skins) can bind it to context menu / keymap:

  ```xml
  <extension point="xbmc.python.script" library="resources/lib/context_cross_add.py">
    <provides>executable</provides>
  </extension>
  ```
* Running `RunScript(plugin.service.favourites-sync, action=cross_add_current)` calls `ui_cross_add.open_for_current_selection()`.

> We avoid relying on Kodi’s skin-specific context menu hooks; the script route plus keymap binding is portable.

### `ui_cross_add.py` (dialog)

```python
def open_for_current_selection():
    # 1) Read current ListItem.* labels → build FavItem(label, action/path, thumb)
    # 2) Load profiles.json → build checkbox list (respect cross_add.enabled, preselect auto_targets)
    # 3) On OK → for each selected profile:
    #    - xmlio.append_favourite(profile_name, fav_item)
    #    - if "sync now" is checked → sync.run_sync_for_profile(profile_name, mode='bidirectional', skip_profile_reload=True)
    # 4) Toast summary
```

**Fav entry construction**

* If you can get a plugin URL (e.g., `plugin://...`) prefer:

  ```
  <favourite name="Label">PlayMedia("plugin://...")</favourite>
  ```
* Else if it’s an add-on, use:

  ```
  RunAddon("addon.id")
  ```
* Else fallback to:

  ```
  ActivateWindow(10025, "plugin://...", return)
  ```
* Keep `thumb` if available.

### `xmlio.py` additions

```python
def append_favourite_to_profile(profile_name: str, item: FavItem) -> None:
    """
    Load that profile's favourites.xml → append FavItem → serialize → backup + atomic write.
    Avoid duplicates: if an entry with same key exists, skip or update.
    """
```

Use a stable key `(normalized_label, action)` to detect duplicates.

---

Context Menu Integration (Universal Configuration)

To make the “Add to favourites (for other profiles)…” action globally accessible from any list item in Kodi:

1. Script entry point in addon.xml

Add a standard Kodi script extension so the command can be called from any skin or keymap:

<extension point="xbmc.python.script" library="resources/lib/context_cross_add.py">
  <provides>executable</provides>
</extension>


Kodi then recognises:

RunScript(plugin.service.favourites-sync, action=cross_add_current)


as a valid command.

2. Optional skin integration (for universal context menu support)

Skins can expose the command by including an item in their context-menu XML
(e.g. DialogContextMenu.xml):

<item>
    <label>Add to favourites (for other profiles)</label>
    <onclick>RunScript(plugin.service.favourites-sync, action=cross_add_current)</onclick>
</item>


This lets any Kodi skin surface the option without code changes to other add-ons.

3. Keymap binding (optional user shortcut)

Users may also bind a keyboard or remote key to the same script for instant access:

<keymap>
  <global>
    <keyboard>
      <c>RunScript(plugin.service.favourites-sync, action=cross_add_current)</c>
    </keyboard>
  </global>
</keymap>


This universal approach avoids dependencies on specific add-ons and makes the command
available system-wide.

4. Behaviour (summary)

When invoked, Kodi passes the currently focused ListItem to the script.

The script retrieves ListItem.Label, ListItem.FileNameAndPath, and ListItem.Art(thumb)
to construct the new favourite entry.

## 🔁 (Optional) Phase 4 — Startup/Shutdown multi-profile sync

In `service.py`, at startup/shutdown events:

```python
cfg = profiles_mgr.load_profiles_cfg()
for prof, pcfg in cfg["profiles"].items():
    if pcfg["schedule"].get("on_start"):    run_sync_for_profile(prof, pcfg["schedule"].get("mode","bidirectional"), skip_profile_reload=True)
# likewise for on_shutdown
```

### `sync.py` small wrapper

```python
def run_sync_for_profile(profile_name: str, mode: str, skip_profile_reload: bool=True) -> dict:
    """
    1) Build LOCAL path = that profile's favourites.xml
    2) Read its backend config from profiles.json
    3) Instantiate driver and call existing run_sync(mode, policy=pcfg['conflict_policy'], ...)
    4) Return summary
    """
```

---

## 🔗 addon.xml changes (summary)

* Ensure your service entry remains.
* Add a **script** entry for cross-add (Phase 3B):

```xml
<extension point="xbmc.python.script" library="resources/lib/context_cross_add.py">
  <provides>executable</provides>
</extension>
```

* No need to add a special “context item” extension (varies by skin). The script can be bound via **keymap** or invoked from add-on menu.

---

## ✅ Acceptance tests

1. **Profiles discovery**

* `profiles.json` created with discovered profiles (at least names + empty configs).
* “Manage Profiles…” shows all profiles with Edit buttons.

2. **Edit & validate**

* Saving WebDAV/SMB/S3 config stores credentials (password encrypted as `ENC:...`).
* “Validate” shows success/failure messages.

3. **Cross-add prompt**

* From a focused movie/episode/add-on item, run: “Add to favourites (for other profiles)…”
* Dialog lists M1/M2/T with default selections per `auto_targets`.
* After OK, those profiles’ `favourites.xml` contain the new `<favourite>` (no duplicates).
* If “Sync now” checked, run immediate bidirectional sync for selected profiles.

4. **No polling**

* No idle loops in logs; actions occur only on user commands or schedule events.

5. **Atomic write & backup**

* Each write creates a timestamped backup and uses `os.replace`.
* Broken writes never corrupt `favourites.xml`.

6. **Security**

* `profiles.json` stores passwords as `ENC:...`.
* Decrypt works transparently when invoking backends.

7. **Logging**

* Key log lines include `profile=<name>` and action summaries (added/validated/written).

---

## 🧑‍💻 Implementation tips

* Use existing `FavItem` dataclass from `xmlio.py`.
* Normalize keys with “strip BBCode + casefold(label), plus action string” to detect duplicates.
* UI dialogs can be simple `xbmcgui.Dialog().multiselect()` for profile selection, and `xbmcgui.Dialog().ok()` toasts/alerts.
* For selection context, rely on `xbmc.getInfoLabel('ListItem.*')`. If no selection, show a helpful message and exit gracefully.

---

## 📦 Deliverables

* New/modified Python modules listed above.
* Updated `addon.xml`, `resources/settings.xml`.
* A short run log demonstrating:

  ```
  event=profiles_discovered count=4
  event=cross_add start item="The Batman" targets=M1,M2
  event=append_favourite profile=M1 action="PlayMedia("plugin://...")"
  event=append_favourite profile=M2 action="PlayMedia("plugin://...")"
  event=sync_now profiles=M1,M2 result=success
  ```
* Screenshots (optional) of “Manage Profiles…” and the cross-add selection dialog.

---

**End of developer prompt.**
