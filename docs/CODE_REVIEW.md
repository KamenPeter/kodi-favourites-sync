# Code review findings

Review date: 2026-10-04

Scope: Current repository working tree, including existing uncommitted changes. Goals were assessed against `docs/DEFINITION.md`, `docs/TODO_LIST.md`, the README, and implementation/release documentation.

## Assessment

The goals are partially achieved. Fixes are required before the project can be considered complete.

Basic profile discovery, editing dialogs, cross-add writing, reorder controls, and event-based scheduling are present. End-to-end multi-profile sync, credential handling, deletion tracking, and safe writes do not meet the documented acceptance criteria.

## Findings

### 1. High — Multi-profile sync crashes and does not use isolated profile state

References: `addon/resources/lib/sync.py:845`, `:933`, `:936`, and `:30`.

Saved profiles use a string backend, such as `"backend": "local"`, with settings in `"config"`. The sync wrapper treats `backend` as a dictionary, producing `AttributeError: 'str' object has no attribute 'get'`. This was reproduced in an isolated check.

Even after correcting the schema access, the wrapper creates a profile backend but calls `_run()`, which constructs another backend from global settings. It overrides only `LOCAL_FAV`; status, merge baseline, lock, and backup storage remain associated with the active profile. This prevents correct independent synchronization and can mix deletion history between profiles.

Required fix: Pass the profile configuration, local path, and separate state paths into the sync engine rather than changing module globals. Support profiles whose favourites file has not yet been created.

### 2. High — Failed uploads are reported as success and advance merge history

References: `addon/resources/lib/sync.py:661`, `:683`, and `:705`.

A bidirectional upload failure sets `partial_success`, but subsequent code overwrites the result with `success`, clears the error, and advances merge history despite the failed upload. An isolated check confirmed a failed upload returned success with no error and updated BASE.

An addition that never reached the remote can then be interpreted as a remote deletion on a subsequent sync.

Required fix: Preserve the upload failure and advance the common baseline only when synchronization succeeds. Retain enough state to retry pending changes safely.

### 3. High — File writes described as atomic can delete the original

References: `addon/resources/lib/drivers/local.py:80`, `addon/resources/lib/xmlio.py:363`, `addon/resources/lib/profiles_mgr.py:167`, `addon/resources/lib/reorder.py:292`, and `addon/resources/lib/sync.py:67`.

Several writers delete the destination before renaming the temporary file. Simulating a rename failure in the local driver confirmed that the original file disappeared. The same pattern occurs in profile configuration, favourites append/reorder, snapshots, and filesystem backend writes. VFS write/rename return values are not consistently checked.

Required fix: Replace without prior deletion, check operation results, and coordinate concurrent writers. Use unique temporary files and a reliable locking strategy. Preserve the original when replacement fails.

### 4. High — Preview and error runs erase deletion history

References: `addon/resources/lib/sync.py:118`, `:417`, `:458`, `:555`, and `:740`.

Three-way merging loads its baseline from `last_synced_items` in `status.json`. Preview and error paths replace that file with an operation status that omits the baseline. An isolated preview check confirmed the saved status no longer contained merge history.

Without the baseline, the next merge can resurrect deleted favourites.

Required fix: Store durable merge history separately from operation status, or preserve it on every noncommitting operation and failure path.

### 5. High — Validation mutates encrypted credentials to plaintext

References: `addon/resources/lib/profiles_mgr.py:371`, `:375`, and `:385`; `addon/resources/lib/ui_profiles.py:373`, `:411`, and `:425`.

Endpoint validation decrypts the original configuration dictionary in place. Saving after validation can persist the plaintext password. The mutation was reproduced in an isolated check.

Credential keys also differ between the profile UI and backend drivers. For example, profile passwords are stored as `password`, whereas WebDAV and SFTP drivers expect `webdav_password` and `sftp_password`. Validation decrypts only `password`, leaving encrypted S3 secrets and HTTP auth headers unusable. Encryption also has an exception path that returns plaintext (`profiles_mgr.py:310`).

Required fix: Validate using a copied configuration, centralize driver/credential mapping, decrypt every supported secret only at the driver boundary, and fail safely instead of silently storing plaintext.

### 6. High — Normal sync omits configuration for five advertised backends

Reference: `addon/resources/lib/sync.py:163`.

`_settings_dict()` collects WebDAV and local fields but omits HTTP, S3, SFTP, SMB, and NFS configuration fields required by their drivers. An isolated check confirmed that HTTP settings containing valid GET/PUT URLs still produced `HTTP GET URL not configured` when passed through this function.

Required fix: Include all supported backend fields and share the mapping between normal sync, profile sync, and endpoint validation.

### 7. Medium — Merge order and newer-conflict resolution are incorrect

References: `addon/resources/lib/xmlio.py:176` and `:180`; `addon/resources/lib/sync.py:519` and `:532`.

Merging iterates an unordered set of keys, so unchanged favourites can move unexpectedly. Remote modification time is passed as `time.time()` rather than the backend's modification timestamp, biasing newer-conflict resolution toward remote content.

Required fix: Preserve existing order while appending new items deterministically. Parse and use actual backend modification timestamps, with an explicit fallback when unavailable.

### 8. Medium — Profile schedules and initial settings application are incomplete

References: `addon/resources/lib/service.py:89`, `:158`, `:230`, and `:269`.

Multi-profile startup/shutdown sync is nested inside the active profile's global schedule and endpoint checks. Independently configured profile schedules do not run when those global checks fail or the corresponding global trigger is disabled.

The settings monitor initializes its previous state to `None` and skips reordering on the first settings-change event. The first user change after service startup can therefore remain unapplied.

Required fix: Evaluate profile schedule flags independently of active-profile endpoint settings. Initialize the settings snapshot when the monitor starts.

### 9. Medium — Cross-add invocation and default selections are incomplete

References: `addon/resources/lib/context_cross_add.py:32`, `addon/resources/lib/ui_cross_add.py:58`, and `addon/resources/lib/ui_profiles.py:207`.

The script accepts `cross_add`, while the documented command uses `action=cross_add_current`. Default targets are checked against each target profile's own configuration rather than the source profile's defaults. Selection indices are calculated before filtering eligible profiles, so defaults can point to the wrong row or outside the displayed list.

The currently wired standard profile editor supports enabling cross-add but lacks default-target editing.

Required fix: Support the documented invocation, derive defaults from the source profile, calculate indices against the filtered list, and expose default-target editing in the active UI.

## Validation performed

- Syntax compilation passed for all Python files under `addon/`, `runner/`, and `tools/` using Python 3.12 in WSL.
- Isolated checks used extracted functions, mocked Kodi dependencies, and temporary files. They confirmed the profile schema crash, deletion of the original after failed replacement, false success and BASE advancement after failed upload, preview erasure of merge history, and plaintext credential mutation during validation.
- A separate isolated driver check confirmed missing HTTP configuration after `_settings_dict()` processing.
- These checks demonstrate the specified failures; they do not constitute full end-to-end regression coverage.
- The two existing root-level test scripts are manual Kodi UI launchers, not automated regression tests with assertions.
- Live Kodi UI, startup/shutdown behavior, and actual backend connections were not verified.
- No source files were changed during the review. Temporary bytecode generated by review checks was removed, preserving the existing working-tree changes.

## Recommended sequence

1. Correct safe replacement and durable merge-state handling.
2. Refactor sync to accept explicit configuration and isolated profile state.
3. Unify backend settings and credential conversion.
4. Correct scheduling, initial settings application, and cross-add defaults/invocation.
5. Add regression tests for the confirmed failures and perform live Kodi acceptance checks before updating completion claims.
