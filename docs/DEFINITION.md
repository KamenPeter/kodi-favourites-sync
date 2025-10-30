# 🧠 AI DEVELOPER PROMPT — Conflict-Safe 3-Way Sync for `plugin.service.favourites-sync`

**Role:** Senior Kodi add-on engineer
**Project:** `plugin.service.favourites-sync`
**Goal:** Implement robust, conflict-safe bidirectional sync so multiple devices can safely edit the same `favourites.xml` (e.g., shared on NAS). Prevent “removed item reappears” by adding **remote ETag/hash checks** and a **3-way merge** using a **BASE** snapshot.

---

## 0) Scope

* Modify **sync pipeline** to:

  1. Read **REMOTE** (NAS/cloud), **LOCAL** (current profile file), and **BASE** (last common snapshot).
  2. Use **remote ETag/hash** to detect external changes and trigger 3-way merge.
  3. Apply conflict policies: **Prefer Remote**, **Prefer Local**, **Bidirectional Merge** (with deterministic rules).
  4. Commit changes atomically; update metadata (`status.json`) and **BASE** snapshot.

* Non-goals: GUI redesign; per-profile UI (that’s Part 2); backend drivers beyond required hash/etag reporting.

---

## 1) File locations & names

* Local favourites:
  `LOCAL = special://profile/favourites.xml`

* Add-on data dir (create if missing):
  `DATA = special://profile/addon_data/plugin.service.favourites-sync/`

* Files inside `DATA`:

  * `status.json` — per device metadata (see schema below)
  * `base_snapshot.xml` — last known common version (**BASE**)
  * `log.txt` — existing log file (already present)
  * backups like `favourites_YYYYMMDD-HHMMSS.xml.bak` (existing)

* Remote path: provided by active backend driver (SMB/WebDAV/etc.), as configured.

---

## 2) Metadata schema changes

### `status.json` (extend if exists)

```json
{
  "last_run": "2025-10-25T09:00:00Z",
  "last_mode": "pull|push|bidirectional",
  "result": "success|error|skipped",
  "endpoint_valid": true,
  "changed_items": 5,

  "remote_etag": "sha256:abcd...",        // NEW: last known remote hash/etag at successful sync
  "remote_modified_at": "2025-10-25T09:00:00Z", // optional, if driver provides

  "base_hash": "sha256:...",              // NEW: hash of base_snapshot.xml for sanity
  "local_hash": "sha256:...",             // NEW: local favourites hash at last success
  "commit_id": "deviceA-20251025-090000"  // NEW: informational, last writer ID (hostname + time)
}
```

* **remote_etag** must be compared before any push.
* **base_hash** helps sanity-check that BASE exists and is consistent.

---

## 3) Backend driver contract (minimal additions)

Ensure each driver (SMB/WebDAV/S3/…) provides a **remote hash/etag** via `stat()` and returns bytes via `download()`:

```python
class BackendBase:
    def stat(self) -> dict:
        """
        Returns metadata, minimally:
          {
            "etag": "sha256:...." or an ETag-like value (opaque string),
            "modified_at": "2025-10-25T09:00:00Z",  # optional
            "size": 1234                             # optional
          }
        Must raise on unreachable.
        """
        ...

    def download(self) -> bytes: ...
    def upload(self, data: bytes, metadata: dict) -> None: ...
    def copy_backup(self, backup_name: str) -> None: pass
```

* If native ETag unavailable (e.g., SMB), compute `sha256` of remote bytes after download and surface as `etag`.

---

## 4) Function signatures & modules to implement/modify

### `resources/lib/sync.py` (core orchestrator)

```python
def run_sync(mode: str, policy: str, monitor=None) -> dict:
    """
    mode: 'pull' | 'push' | 'bidirectional'
    policy (for conflicts): 'prefer_remote' | 'prefer_local' | 'merge'
    Returns summary dict: {
      'result': 'success'|'skipped'|'error',
      'changed': bool,
      'added': int, 'removed': int, 'modified': int,
      'remote_etag': str, 'local_hash': str
    }
    """

def _compute_hash(data: bytes) -> str:
    """sha256:... helper."""

def _load_status() -> dict: ...
def _save_status(d: dict) -> None: ...

def _read_local() -> bytes: ...
def _write_local_atomic_with_backup(data: bytes) -> None: ...

def _read_base() -> bytes|None: ...
def _write_base(data: bytes) -> None: ...

def _fetch_remote(driver) -> tuple[bytes, dict]:
    """Returns (remote_bytes, remote_stat) where remote_stat['etag'] exists."""

def _commit(remote_bytes: bytes|None, local_bytes: bytes|None, driver, manual_context: bool, skip_profile_reload: bool) -> None:
    """
    Writes chosen final 'local_bytes' to LOCAL and uploads 'remote_bytes' if needed.
    Ensures atomic writes, remote backup if available, and optional profile reload.
    """
```

### `resources/lib/xmlio.py` (entry model & merge helpers)

```python
from dataclasses import dataclass
@dataclass(frozen=True)
class FavItem:
    label: str    # raw 'name' (BBCode preserved)
    action: str   # inner text
    thumb: str|None

def parse_favourites_xml(xml_bytes: bytes) -> list[FavItem]: ...
def serialize_favourites(items: list[FavItem]) -> bytes: ...

def normalize_key(item: FavItem) -> tuple[str, str]:
    """Return a stable key for item identity, e.g. (clean_label, action).
       clean_label may strip BB tags for identity; keep raw label in FavItem."""
```

### New merge utilities (in `sync.py` or `xmlio.py`)

```python
@dataclass
class Diff3:
    added_local: set
    removed_local: set
    added_remote: set
    removed_remote: set
    changed_local: set     # if you later support “changed” semantics
    changed_remote: set

def diff3(base: list[FavItem], local: list[FavItem], remote: list[FavItem]) -> Diff3: ...

def merge3(base: list[FavItem], local: list[FavItem], remote: list[FavItem], policy: str) -> tuple[list[FavItem], dict]:
    """
    policy: 'prefer_remote' | 'prefer_local' | 'merge'
    Returns (merged_items, metrics_dict)
    """
```

---

## 5) Sync algorithm (step by step)

```text
1) Load config & driver
2) Read LOCAL bytes; compute local_hash
3) Load BASE snapshot (if missing, set BASE := LOCAL, base_hash := local_hash)
4) Fetch REMOTE stat.etag; download REMOTE bytes; compute remote_hash (if etag is not strong)
5) Compare against status.remote_etag:
   - If etag changed since last success => remote changed externally

6) Choose flow by mode:
   a) pull:
       final := REMOTE
   b) push:
       if remote changed since last success:
           if policy == 'prefer_local': upload LOCAL; else: pull first (or merge)
       else:
           upload LOCAL
   c) bidirectional:
       Run 3-way merge with BASE, LOCAL, REMOTE
       (see rules below)

7) Write LOCAL (atomic + backup) if changed; Upload REMOTE if needed
8) Update BASE := final merged version
9) Update status.json: remote_etag (new), base_hash, local_hash, last_run, last_mode, result
10) Optionally reload profile (manual_context guard)
```

---

## 6) 3-way merge rules (policy handling)

Use **identity key** = `normalize_key(item) → (clean_label, action)`.

### Compute changes

* `A := set(keys(base))`
* `L := set(keys(local))`
* `R := set(keys(remote))`

For now treat items as **added/removed** by key; (changed) can be added later if you track per-item label/action edits.

### Policy: **Prefer Remote**

* Any **conflict** (same key present in one side removed in the other): choose **REMOTE** state.
* Result keys = `R ∪ (L \ (conflicting_with_R_removals))`, but in practice simpler:

  * Start from `R`
  * Include any **local additions** that do **not** conflict with remote removals?
    For **strict** prefer-remote: **do not include** local-only adds if remote concurrently removed the same key.
* Ordering:

  * Preserve REMOTE order; append non-conflicting local-only additions at end (optional).
* Metrics: count adds/removes relative to BASE.

### Policy: **Prefer Local**

* Mirror of above; choose **LOCAL** on conflicts.
* Ordering: preserve LOCAL order; append remote-only adds at end (optional).

### Policy: **Bidirectional Merge** (default)

* **Additions**: union `L ∪ R`.

* **Removals**: if an item is **removed in either LOCAL or REMOTE** relative to BASE, and not re-added on the other side, it must be **removed**.

* **Conflicts**:

  * If **A contains k**, and `k ∉ L` (local removed) but `k ∈ R` (remote kept/added):

    * If remote changed since last success (**etag changed**): **REMOTE wins removal only if policy says prefer remote on scheduled runs**; otherwise **remove** (remote removal dominates because it’s a deliberate delete) — pick one rule and keep it consistent.
  * For simplicity adopt rule: **a removal beats a non-change** (i.e., if BASE had it and one side removes while the other side didn’t edit it, treat as removed).
  * If **both sides add different entries with same key** (rare with our key): choose by `scheduled_conflict` setting, or prefer **newer modified_at** if you track per-item timestamps later.

* **Ordering** strategy (deterministic):

  1. Start from BASE order.
  2. Remove keys that are removed by either side.
  3. Insert NEW keys:

     * If present in REMOTE-only: insert at **remote’s relative position** if known; else append.
     * If present in LOCAL-only: insert at **local’s relative position** if known; else append.
  4. If both sides introduce different insert positions for the **same** key, break ties by **REMOTE first** (documented rule).

Return:

```python
merged_items, metrics = {
    'added': n, 'removed': m, 'kept': k, 'conflicts': c
}
```

---

## 7) Locking (optional but recommended for shared NAS)

Before writing to REMOTE:

* Try to create `favourites.xml.lock` (or backend equivalent), containing `{hostname, pid, timestamp}`.
* If exists and **fresh (<60s)**, **retry later** (skip write).
* After upload, **remove lock**.

Implement best-effort; do not block forever.

---

## 8) Commit & reload

* Use existing atomic write for LOCAL: write to `tmp`, then `os.replace`.
* For REMOTE: if backend supports server-side copy/backup, call `copy_backup()` **before** upload.
* After successful commit:

  * Update `status.json` fields (`remote_etag`, `base_hash`, `local_hash`, `last_run`, `commit_id`).
  * If `manual_context=True` and not `skip_profile_reload`, do `xbmc.executebuiltin("LoadProfile(auto)")`; fallback to `Container.Refresh` on failure.

---

## 9) Logging (add lines)

Examples (key=value, single line):

```
event=sync_start mode=bidirectional policy=merge
event=remote_stat etag=E2 size=1234
event=diff3 added_local=1 removed_local=0 added_remote=0 removed_remote=1
event=merge_result added=0 removed=1 kept=45 conflicts=0
event=commit local_changed=true remote_changed=true
event=sync_success new_remote_etag=E3 local_hash=H3
```

On detected external change:

```
event=remote_changed prev_etag=E1 new_etag=E2 action=merge3
```

---

## 10) Tests (must pass)

1. **Readd bug scenario (your case)**

   * A adds movie X; A syncs (E1)
   * B pulls; B removes X; B syncs (E2)
   * A syncs: **must NOT** reintroduce X; result should remove X locally and update BASE/etag.

2. **Simultaneous additions (different items)**

   * A adds X (no remote change), B adds Y (no remote change), then both sync in any order: final has X+Y.

3. **Add vs Remove conflict (same item)**

   * From BASE, A adds X (local-only), B removes X (remote removed) → policy:

     * Prefer Remote → final **without** X
     * Prefer Local → final **with** X
     * Merge → **removal wins** (document this; consistent rule)

4. **Ordering determinism**

   * Same content, different insert positions on A vs B → final order deterministic (REMOTE priority).

5. **Lock respected**

   * With lock present & fresh: writer backs off and retries/returns skipped.

6. **Status and BASE maintained**

   * After success: `status.remote_etag` equals new etag; `base_snapshot.xml` equals merged content; hashes updated.

---

## 11) Deliverables

* Updated `sync.py`, `xmlio.py`, and (if needed) drivers’ `stat()` to provide etag/hash.
* New/updated `status.json` and `base_snapshot.xml` handling.
* Unit/integration test snippets or logs proving scenarios above.
* Log excerpts showing 3-way merge decisions.

---

## 12) Implementation hints

* If backend can’t provide strong ETag, compute `sha256(remote_bytes)` and use it as `etag`.
* Keep **FavItem.label** as raw (with BBCode) and use **normalize_key()** for identity (strip BBCode + casefold on label).
* For performance, cache parsed lists and key sets; XML files are small, so clarity > micro-perf.