import os, time, json, hashlib
from functools import partial
from datetime import datetime
from email.utils import parsedate_to_datetime
import xbmc, xbmcgui, xbmcvfs, xbmcaddon
try:
    from .logutil import log_info, log_error, log_debug, kvfmt
except Exception:
    from logutil import log_info, log_error, log_debug, kvfmt
try:
    from .version import __version__
except Exception:
    from version import __version__
try:
    from . import xmlio
except Exception:
    import xmlio
try:
    from .storage import atomic_write, acquire_lock, release_lock
    from .backend_config import FIELDS, decrypt_driver_config, profile_driver_config
except ImportError:
    from storage import atomic_write, acquire_lock, release_lock
    from backend_config import FIELDS, decrypt_driver_config, profile_driver_config

# Use the service's settings even when imported by the launcher addon.
ADDON = xbmcaddon.Addon("plugin.service.favourites-sync")

PROFILE = xbmcvfs.translatePath("special://profile/")
LOCAL_FAV = os.path.join(PROFILE, "favourites.xml")
ADDON_DATA = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON.getAddonInfo('id')}")
try:
    os.makedirs(ADDON_DATA, exist_ok=True)
except Exception:
    pass

STATUS_JSON = os.path.join(ADDON_DATA, "status.json")
BASE_SNAPSHOT = os.path.join(ADDON_DATA, "base_snapshot.xml")
LOCK_FILE = os.path.join(ADDON_DATA, "sync.lock")


def _hash(data) -> str:
    """Hash data (bytes or string) with SHA256"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    return "sha256:" + hashlib.sha256(data or b"").hexdigest()


def _xbmcvfs_read(path) -> bytes:
    # All sync paths are translated local filesystem paths. Only absence is empty;
    # permission and I/O failures must abort rather than look like deletions.
    try:
        with open(path, 'rb') as stream:
            return stream.read()
    except FileNotFoundError:
        return b""


def _xbmcvfs_write_atomic(path, data: bytes):
    atomic_write(path, data)


def _save_status(d: dict, path=STATUS_JSON):
    try:
        previous = _load_status(path)
        # Operation status must never erase the last committed sync state.
        for key in ('last_synced_items', 'last_synced_hash', 'remote_hash',
                    'remote_etag', 'remote_modified_at', 'base_hash', 'local_hash', 'commit_id'):
            if key not in d and key in previous:
                d[key] = previous[key]
        atomic_write(path, json.dumps(d, indent=2).encode('utf-8'))
    except Exception as e:
        log_error(f"{kvfmt(event='status_write_error', error=str(e))}")


def _load_status(path=STATUS_JSON) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _read_base(path=BASE_SNAPSHOT) -> bytes:
    """Read BASE snapshot (last known common version for 3-way merge)"""
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return b""
    except Exception as e:
        log_error(kvfmt(event="base_read_error", error=str(e)))
        return b""


def _write_base(data: bytes, path=BASE_SNAPSHOT):
    """Write BASE snapshot atomically"""
    atomic_write(path, data)
    log_info(kvfmt(event="base_snapshot_saved", size=len(data)))


def _load_last_synced_items(status_path=STATUS_JSON, base_path=BASE_SNAPSHOT) -> list:
    """Read the committed snapshot, with migration from legacy status history."""
    if os.path.exists(base_path):
        return xmlio.load_xml(_xbmcvfs_read(base_path))
    status = _load_status(status_path)
    last_synced_items = status.get("last_synced_items", [])
    if not last_synced_items:
        return []
    
    # Convert dict items back to Favourite objects
    favourites = []
    for item in last_synced_items:
        try:
            fav = xmlio.Favourite(
                label=item.get("label", ""),
                path=item.get("path", ""),
                attrib=item.get("attrib", {})
            )
            favourites.append(fav)
        except Exception:
            continue
    return favourites


def _backup_local(max_count: int, local_path=LOCAL_FAV, data_dir=ADDON_DATA) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    name = f"favourites_{ts}.xml.bak"
    dst = os.path.join(data_dir, name)
    data = _xbmcvfs_read(local_path)
    if not data:
        return ""
    _xbmcvfs_write_atomic(dst, data)
    # rotate
    try:
        entries = sorted([p for p in os.listdir(data_dir) if p.startswith("favourites_") and p.endswith(".xml.bak")])
        if len(entries) > max_count:
            for old in entries[0:len(entries)-max_count]:
                try:
                    os.remove(os.path.join(data_dir, old))
                except Exception:
                    pass
    except Exception:
        pass
    log_info(kvfmt(event="backup_saved", file=name))
    return name


def _settings_dict() -> dict:
    # Gather relevant settings into a simple dict for drivers
    d = {}
    def g(id_, default=""):
        try:
            return ADDON.getSetting(id_) or default
        except Exception:
            return default
    def gb(id_, default=False):
        try:
            return ADDON.getSettingBool(id_)
        except Exception:
            return default
    d.update({
        "backend": ["webdav", "s3", "http", "sftp", "smb", "nfs", "local"][int(g("backend", "0"))],
        "webdav_url": g("webdav_url"),
        "webdav_path": g("webdav_path"),
        "webdav_user": g("webdav_user"),
        "webdav_password": g("webdav_password"),
        "tls_verify": gb("tls_verify", True),
        "custom_ca": g("custom_ca"),
        "local_path": g("local_path"),
        "timeout_sec": g("timeout_sec", "15"),
        "retry_count": g("retry_count", "2"),
        "backup_count": g("backup_count", "5"),
        "local_backups": gb("local_backups", True),
        "conflict_policy": ["cloud", "local", "merge", "manual"][int(g("conflict_policy", "0"))],
    })
    for fields in FIELDS.values():
        for key in fields:
            if key not in d:
                d[key] = g(key)
    d['s3_versioning'] = g('s3_versioning', 'true')
    d['sftp_port'] = g('sftp_port', '22')
    d['s3_region'] = g('s3_region', 'us-east-1')
    return d


def _backend_from_settings(cfg: dict):
    try:
        from .profiles_mgr import decrypt_secret
    except ImportError:
        from profiles_mgr import decrypt_secret
    cfg = decrypt_driver_config(cfg, decrypt_secret)
    backend = cfg.get("backend")
    
    if backend == "webdav":
        try:
            from .drivers import webdav
        except Exception:
            from drivers import webdav
        return webdav.Driver(cfg)
    
    elif backend == "local":
        try:
            from .drivers import local
        except Exception:
            from drivers import local
        return local.Driver(cfg)
    
    elif backend == "http":
        try:
            from .drivers import http
        except Exception:
            from drivers import http
        return http.Driver(cfg)
    
    elif backend == "s3":
        try:
            from .drivers import s3
        except Exception:
            from drivers import s3
        return s3.Driver(cfg)
    
    elif backend == "sftp":
        try:
            from .drivers import sftp
        except Exception:
            from drivers import sftp
        return sftp.Driver(cfg)
    
    elif backend == "smb":
        try:
            from .drivers import smb
        except Exception:
            from drivers import smb
        return smb.Driver(cfg)
    
    elif backend == "nfs":
        try:
            from .drivers import nfs
        except Exception:
            from drivers import nfs
        return nfs.Driver(cfg)
    
    raise IOError(f"Backend '{backend}' not recognized")


def validate_endpoint(addon_instance=None) -> dict:
    """Validate endpoint connection.
    
    Args:
        addon_instance: Optional addon instance (unused, kept for compatibility)
    
    Returns:
        dict with "ok" (bool) and either "details" or "error"
    """
    cfg = _settings_dict()
    try:
        b = _backend_from_settings(cfg)
        st = b.stat()
        msg = kvfmt(event="validate_ok", backend=cfg.get("backend"), etag=st.get("etag", ""), size=st.get("size", 0))
        log_info(msg)
        return {"ok": True, "details": st}
    except Exception as e:
        log_error(kvfmt(event="validate_failed", backend=cfg.get("backend"), error=str(e)))
        return {"ok": False, "error": str(e)}


def _acquire_lock(path=LOCAL_FAV + '.lock'):
    try:
        return acquire_lock(path)
    except OSError:
        return None


def _release_lock(handle):
    release_lock(handle)


def _remote_mtime(metadata):
    value = metadata.get('modified_at') or metadata.get('modified')
    if not value:
        return 0.0  # Unknown remote time: prefer local when its time is known.
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except (ValueError, TypeError):
        try:
            return parsedate_to_datetime(str(value)).timestamp()
        except (ValueError, TypeError, OverflowError):
            return 0.0


def _apply_reordering(merged_list: list) -> bytes:
    """
    Apply local reordering rules (grouping, sorting, add-to-fav) to merged favourites.
    This ensures that after sync, the local file respects user's organization preferences.
    
    Args:
        merged_list: List of Favourite objects from sync merge
        
    Returns:
        Serialized XML bytes with reordering applied
    """
    try:
        # Import settings and reorder logic
        try:
            from .settings_mgr import misc_add_to_fav, misc_keep_first, misc_group_addons_top, misc_sort_addons
            from .reorder import ensure_self_shortcut, remove_self_shortcuts, apply_manual_order, load_addon_order, normalize_title, SELF_ACTIONS
            from .xmlio import serialize, normalize, FavEntry
        except ImportError:
            from settings_mgr import misc_add_to_fav, misc_keep_first, misc_group_addons_top, misc_sort_addons
            from reorder import ensure_self_shortcut, remove_self_shortcuts, apply_manual_order, load_addon_order, normalize_title, SELF_ACTIONS
            from xmlio import serialize, normalize, FavEntry
        
        # Convert Favourite objects to FavEntry objects for reordering
        entries = []
        for fav in merged_list:
            entry = FavEntry(
                name=fav.label,
                action=fav.path,
                thumb=fav.attrib.get("thumb") if fav.attrib else None
            )
            # Classify the entry
            from xmlio import classify
            entry.type = classify(entry)
            entries.append(entry)
        
        # Get settings
        add_to_fav = misc_add_to_fav()
        keep_first = misc_keep_first()
        group_top = misc_group_addons_top()
        sort_mode = misc_sort_addons()
        
        log_info(kvfmt(event="sync_reorder_start", add_to_fav=add_to_fav, keep_first=keep_first, 
                      group_top=group_top, sort=sort_mode, entries=len(entries)))
        
        # Handle add/remove self shortcut
        if add_to_fav:
            ensure_self_shortcut(entries)
        else:
            remove_self_shortcuts(entries)
        
        # Classify entries
        addons = [e for e in entries if e.type == "addon"]
        others = [e for e in entries if e.type != "addon"]
        
        # Sort addons according to sort mode
        if sort_mode == "az":
            addons = sorted(addons, key=lambda e: normalize_title(e.name))
        elif sort_mode == "za":
            addons = sorted(addons, key=lambda e: normalize_title(e.name), reverse=True)
        elif sort_mode == "manual":
            order = load_addon_order()
            if order:
                addons = apply_manual_order(addons, order)
        
        # Reconstruct list based on grouping setting
        if group_top:
            # Group all addons at top
            final_entries = addons + others
        else:
            # In-place reorder: maintain original positions
            final_entries = []
            addon_idx = 0
            other_idx = 0
            
            for entry in entries:
                if entry.type == "addon":
                    if addon_idx < len(addons):
                        final_entries.append(addons[addon_idx])
                        addon_idx += 1
                else:
                    if other_idx < len(others):
                        final_entries.append(others[other_idx])
                        other_idx += 1
            
            # Add any remaining
            while addon_idx < len(addons):
                final_entries.append(addons[addon_idx])
                addon_idx += 1
            while other_idx < len(others):
                final_entries.append(others[other_idx])
                other_idx += 1
        
        # Move self to first if enabled
        if keep_first and add_to_fav:
            # Find self and move to first
            self_idx = None
            for i, e in enumerate(final_entries):
                if e.action in SELF_ACTIONS:
                    self_idx = i
                    break
            if self_idx is not None and self_idx > 0:
                self_entry = final_entries.pop(self_idx)
                final_entries.insert(0, self_entry)
        
        # Convert FavEntry back to Favourite for serialization
        reordered_list = []
        for entry in final_entries:
            attrib = {}
            if entry.thumb:
                attrib["thumb"] = entry.thumb
            fav = xmlio.Favourite(label=entry.name, path=entry.action, attrib=attrib)
            reordered_list.append(fav)
        
        log_info(kvfmt(event="sync_reorder_complete", addons=len(addons), others=len(others)))
        
        return serialize(normalize(reordered_list))
        
    except Exception as e:
        log_error(kvfmt(event="sync_reorder_error", error=str(e)))
        # Fallback to simple serialization if reordering fails
        return xmlio.serialize(xmlio.normalize(merged_list))


def _run(mode: str, dry_run: bool = False, skip_profile_reload: bool = False,
         config=None, local_path=None, data_dir=None, profile_name=None) -> dict:
    LOCAL_FAV = local_path or globals()['LOCAL_FAV']
    data_dir = data_dir or ADDON_DATA
    os.makedirs(data_dir, exist_ok=True)
    status_path = os.path.join(data_dir, 'status.json')
    base_path = os.path.join(data_dir, 'base_snapshot.xml')
    # Bind operation state locally; concurrent profiles never mutate module globals.
    _save_status = partial(globals()['_save_status'], path=status_path)
    _load_status = partial(globals()['_load_status'], path=status_path)
    _write_base = partial(globals()['_write_base'], path=base_path)
    _load_last_synced_items = partial(globals()['_load_last_synced_items'], status_path, base_path)
    _backup_local = partial(globals()['_backup_local'], local_path=LOCAL_FAV, data_dir=data_dir)
    status = {"last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "last_mode": mode, "result": "error", "changed_items": 0, "error": None}
    lock = _acquire_lock(LOCAL_FAV + '.lock')
    if lock is None:
        status["error"] = "Another sync is running"
        return status
    log_info(kvfmt(event="sync_start", mode=mode, skip_reload=skip_profile_reload, profile=profile_name))
    try:
        cfg = dict(config) if config is not None else _settings_dict()
        backend = _backend_from_settings(cfg)
        
        # CRITICAL: Try to access cloud BEFORE reading/modifying local file
        # If cloud is unavailable, preserve local favourites.xml and abort
        try:
            remote_meta = backend.stat()
            remote_bytes = backend.download()
        except Exception as e:
            # Cloud unavailable - preserve local file and abort sync
            # Extract user-friendly error message
            error_str = str(e)
            backend_type = cfg.get("backend", "cloud")
            
            # Simplify common error messages
            if "network path was not found" in error_str.lower() or "cannot access path" in error_str.lower():
                user_msg = f"Network path not accessible ({backend_type})"
            elif "connection" in error_str.lower() and "refused" in error_str.lower():
                user_msg = f"Connection refused ({backend_type})"
            elif "timeout" in error_str.lower():
                user_msg = f"Connection timeout ({backend_type})"
            elif "401" in error_str or "unauthorized" in error_str.lower():
                user_msg = f"Authentication failed ({backend_type})"
            elif "403" in error_str or "forbidden" in error_str.lower():
                user_msg = f"Access denied ({backend_type})"
            elif "404" in error_str or "not found" in error_str.lower():
                user_msg = f"File or path not found ({backend_type})"
            elif "50" in error_str[:3]:  # 500, 502, 503, 504
                user_msg = f"Server error ({backend_type})"
            else:
                # Generic message for other errors
                user_msg = f"Cannot reach {backend_type} storage"
            
            log_error(kvfmt(event="cloud_unavailable", error=str(e), mode=mode, backend=backend_type))
            status["error"] = user_msg
            status["error_detail"] = str(e)  # Keep full error for logs
            status["result"] = "cloud_unavailable"
            _save_status(status)
            return status
        
        # Cloud is accessible - safe to proceed with sync
        local_bytes = _xbmcvfs_read(LOCAL_FAV)
        local_list = xmlio.load_xml(local_bytes)
        remote_list = xmlio.load_xml(remote_bytes)

        last = _load_status()
        last_hash = last.get("last_synced_hash", "")
        last_remote_etag = last.get("remote_etag", "")
        current_remote_etag = remote_meta.get("etag", "")
        
        # Detect remote changes using ETag
        remote_changed_externally = (last_remote_etag != "" and 
                                     current_remote_etag != "" and 
                                     last_remote_etag != current_remote_etag)
        
        if remote_changed_externally:
            log_info(kvfmt(event="remote_changed_externally", 
                          last_etag=last_remote_etag, 
                          current_etag=current_remote_etag))
        
        local_hash = _hash(local_bytes)
        remote_hash = _hash(remote_bytes)
        local_changed = (local_hash != last_hash)
        remote_changed = (remote_hash != last.get("remote_hash", ""))
        
        # Conflict: both local and remote changed since last sync
        conflict = (local_changed and remote_changed and mode in ("bidirectional", "dryrun"))
        
        if conflict:
            log_info(kvfmt(event="conflict_detected", 
                          local_changed=local_changed, 
                          remote_changed=remote_changed,
                          remote_etag_changed=remote_changed_externally))
        
        # Load last synced items for three-way merge
        last_synced_list = _load_last_synced_items()

        changed = 0
        output_bytes = None
        merged_list = None
        stats = {"added": 0, "changed": 0, "removed": 0}

        if mode == "pull":
            merged_list = remote_list
        elif mode == "push":
            merged_list = local_list
        elif mode == "bidirectional":
            if conflict and cfg.get("conflict_policy") == "manual":
                raise IOError("Conflict requires manual review")
            prefer = "newer"
            if cfg.get("conflict_policy") == "cloud":
                prefer = "cloud"
            elif cfg.get("conflict_policy") == "local":
                prefer = "local"
            # Three-way merge with last_synced_list for proper deletion handling
            merged_list, stats = xmlio.merge_sets(local_list, remote_list, last_synced_list, prefer=prefer,
                                                  local_mtime=os.path.getmtime(LOCAL_FAV) if os.path.exists(LOCAL_FAV) else 0.0,
                                                  remote_mtime=_remote_mtime(remote_meta))
        elif mode == "dryrun":
            # Preview bidirectional merge with conflict detection and three-way merge
            if conflict:
                prefer = "newer"
                if cfg.get("conflict_policy") == "cloud":
                    prefer = "cloud"
                elif cfg.get("conflict_policy") == "local":
                    prefer = "local"
            else:
                prefer = "newer"
            merged_list, stats = xmlio.merge_sets(local_list, remote_list, last_synced_list, prefer=prefer,
                                                  local_mtime=os.path.getmtime(LOCAL_FAV) if os.path.exists(LOCAL_FAV) else 0.0,
                                                  remote_mtime=_remote_mtime(remote_meta))
        else:
            raise ValueError("Unknown mode")

        if merged_list is None:
            merged_list = []
        
        # Apply local reordering rules to merged result before finalizing
        # This ensures grouping/sorting settings are respected after sync
        # Inactive profiles must not inherit the active profile's ordering settings.
        output_bytes = (xmlio.serialize(xmlio.normalize(merged_list)) if profile_name
                        else _apply_reordering(merged_list))

        if dry_run or mode == "dryrun":
            status.update({
                "result": "dryrun", 
                "changed_items": stats.get("added", 0) + stats.get("changed", 0) + stats.get("removed", 0),
                "added": stats.get("added", 0),
                "changed": stats.get("changed", 0),
                "removed": stats.get("removed", 0),
                "conflict_detected": conflict,
                "added_items": stats.get("added_items", []),
                "changed_items_list": stats.get("changed_items", []),
                "removed_items": stats.get("removed_items", [])
            })
            _save_status(status)
            log_info(kvfmt(event="dry_run", added=stats.get("added", 0), changed=stats.get("changed", 0), removed=stats.get("removed", 0), conflict=conflict))
            return status

        # Backups
        if cfg.get('local_backups', True):
            try:
                _backup_local(int(cfg.get("backup_count") or 5))
            except Exception as e:
                log_error(kvfmt(event="backup_error", error=str(e)))
        try:
            # Optional remote backup
            backup_name = f"favourites_{time.strftime('%Y%m%d-%H%M%S')}.xml.bak"
            try:
                backend.copy_backup(backup_name)
            except Exception:
                pass
        except Exception:
            pass

        # Write local atomically for pull/bidirectional
        if mode in ("pull", "bidirectional"):
            # Check if content actually changed before writing
            old_local_bytes = _xbmcvfs_read(LOCAL_FAV) if os.path.exists(LOCAL_FAV) else b""
            content_changed = (output_bytes != old_local_bytes)
            
            if content_changed:
                _xbmcvfs_write_atomic(LOCAL_FAV, output_bytes)
                changed += 1
                
                # Reload favourites in Kodi UI ONLY if content changed AND not skipped
                # Skip reload during scheduled syncs to prevent infinite loop (LoadProfile restarts services)
                if not skip_profile_reload:
                    try:
                        # Set flag to prevent startup sync from running after reload
                        try:
                            from service import _set_reload_flag
                            _set_reload_flag()
                        except Exception:
                            try:
                                from .service import _set_reload_flag
                                _set_reload_flag()
                            except:
                                pass  # Flag setting is optional
                        
                        import json
                        
                        # Get current profile name
                        current_profile = xbmc.getInfoLabel('System.ProfileName')
                        log_info(f"Favourites changed, reloading profile: {current_profile}")
                        
                        # Use LoadProfile to reload current profile
                        # This forces Kodi to reload favourites.xml from disk
                        xbmc.executebuiltin(f'LoadProfile({current_profile})')
                        log_info(f"Profile reloaded: {current_profile}")
                        
                        # Notify user
                        xbmc.executebuiltin('Notification(Favourites Sync, Favourites updated - profile reloaded, 5000, DefaultIconInfo.png)')
                        log_info("Notification shown")
                        
                    except Exception as e:
                        log_error(kvfmt(event="reload_error", error=str(e)))
                else:
                    log_info("Favourites changed but profile reload skipped (scheduled sync)")
            else:
                log_info("No changes to favourites, skipping profile reload")
                
        # Upload new content for push/bidirectional
        if mode in ("push", "bidirectional"):
            # Use remote etag for optimistic concurrency
            try:
                backend.upload(output_bytes if mode != "push" else local_bytes or output_bytes,
                               {"etag": remote_meta.get("etag", "")})
                changed += 1
            except Exception as e:
                # Upload failed - cloud unavailable
                # Extract user-friendly error message (same logic as download)
                error_str = str(e)
                backend_type = cfg.get("backend", "cloud")
                
                # Simplify common error messages
                if "network path was not found" in error_str.lower() or "cannot write to" in error_str.lower():
                    user_msg = f"Network path not accessible ({backend_type})"
                elif "connection" in error_str.lower() and "refused" in error_str.lower():
                    user_msg = f"Connection refused ({backend_type})"
                elif "timeout" in error_str.lower():
                    user_msg = f"Connection timeout ({backend_type})"
                elif "401" in error_str or "unauthorized" in error_str.lower():
                    user_msg = f"Authentication failed ({backend_type})"
                elif "403" in error_str or "forbidden" in error_str.lower():
                    user_msg = f"Access denied ({backend_type})"
                elif "404" in error_str or "not found" in error_str.lower():
                    user_msg = f"File or path not found ({backend_type})"
                elif "50" in error_str[:3]:  # 500, 502, 503, 504
                    user_msg = f"Server error ({backend_type})"
                else:
                    # Generic message for other errors
                    user_msg = f"Cannot reach {backend_type} storage"
                
                log_error(kvfmt(event="upload_error", error=str(e)))
                
                # For bidirectional mode, local changes are saved even if upload fails
                # This is acceptable - local favourites are safe
                if mode == "bidirectional":
                    status["error"] = user_msg + " (local changes saved, upload failed)"
                    status["error_detail"] = str(e)
                    status["result"] = "partial_success"  # Local OK, cloud upload failed
                    log_error(kvfmt(event="upload_failed_but_local_saved", mode=mode, error=user_msg))
                else:
                    # Push mode - upload is critical, must fail
                    status["error"] = user_msg
                    status["error_detail"] = str(e)
                    status["result"] = "cloud_unavailable"
                    _save_status(status)
                    return status
                # Neither status history nor BASE is committed after upload failure.
                _save_status(status)
                return status

        # Calculate hashes for 3-way merge tracking
        final_local_bytes = _xbmcvfs_read(LOCAL_FAV)
        final_local_hash = _hash(final_local_bytes)
        committed_bytes = (local_bytes or output_bytes) if mode == 'push' else output_bytes
        
        # Generate commit_id for this sync operation
        import uuid
        commit_id = str(uuid.uuid4())[:8]
        
        status.update({
            "result": "success",
            "changed_items": changed if changed else (stats.get("added", 0) + stats.get("changed", 0) + stats.get("removed", 0)),
            "added": stats.get("added", 0),
            "changed": stats.get("changed", 0),
            "removed": stats.get("removed", 0),
            "added_items": stats.get("added_items", []),
            "changed_items_list": stats.get("changed_items", []),
            "removed_items": stats.get("removed_items", []),
            "last_synced_hash": final_local_hash,
            "remote_hash": _hash(committed_bytes) if mode in ('push', 'bidirectional') else remote_hash,
            "error": None,
            # Extended schema for 3-way merge and conflict detection
            "remote_etag": remote_meta.get("etag", "") if mode == 'pull' else "",
            "remote_modified_at": remote_meta.get("modified_at", ""),
            "base_hash": _hash(committed_bytes),
            "local_hash": final_local_hash,
            "commit_id": commit_id,
            # Save last synced items for three-way merge in next sync
            "last_synced_items": [
                {"label": f.label, "path": f.path, "attrib": f.attrib}
                for f in xmlio.load_xml(committed_bytes)
            ]
        })
        # Commit even an empty baseline: deleting the final item is a real sync.
        _write_base(committed_bytes)
        _save_status(status)
        log_info(kvfmt(event="base_updated", commit_id=commit_id))
        
        # Log detailed changes (requirement #2 from 1.0.33)
        log_info(kvfmt(event="sync_success", mode=mode, changed=status["changed_items"], commit_id=commit_id))
        
        # Log merge decisions for debugging
        if stats.get("merge_decisions"):
            log_info(f"Merge decisions ({len(stats.get('merge_decisions', []))}):")
            for decision in stats.get("merge_decisions", [])[:20]:  # Log first 20
                log_info(f"  {decision}")
            if len(stats.get("merge_decisions", [])) > 20:
                log_info(f"  ... and {len(stats.get('merge_decisions', [])) - 20} more decisions")
        
        if stats.get("added_items"):
            log_info(f"Added items ({len(stats.get('added_items', []))}):")
            for item in stats.get("added_items", []):
                log_info(f"  + {item}")
        if stats.get("changed_items", []):
            log_info(f"Changed items ({len(stats.get('changed_items', []))}):")
            for item in stats.get("changed_items", []):
                log_info(f"  ~ {item}")
        if stats.get("removed_items"):
            log_info(f"Removed items ({len(stats.get('removed_items', []))}):")
            for item in stats.get("removed_items", []):
                log_info(f"  - {item}")
        
        return status
    except Exception as e:
        status['result'] = 'error'
        for key in ('last_synced_items', 'last_synced_hash', 'remote_hash', 'remote_etag',
                    'remote_modified_at', 'base_hash', 'local_hash', 'commit_id'):
            status.pop(key, None)
        status["error"] = str(e)
        _save_status(status)
        log_error(kvfmt(event="sync_error", error=str(e)))
        return status
    finally:
        _release_lock(lock)


def run_sync_ui(mode):
    d = xbmcgui.Dialog()
    # Map UI labels to internal modes
    m = mode
    if mode == "dryrun":
        res = _run("dryrun", dry_run=True)
        conflict_msg = " [CONFLICT DETECTED]" if res.get("conflict_detected") else ""
        msg = f"Bidirectional Preview{conflict_msg}\n\n"
        msg += f"Added: {res.get('added', 0)}\n"
        if res.get('added_items'):
            for item in res.get('added_items', [])[:5]:  # Show first 5
                msg += f"  • {item}\n"
            if len(res.get('added_items', [])) > 5:
                msg += f"  ... and {len(res.get('added_items', [])) - 5} more\n"
        msg += f"\nChanged: {res.get('changed', 0)}\n"
        if res.get('changed_items_list'):
            for item in res.get('changed_items_list', [])[:5]:
                msg += f"  • {item}\n"
            if len(res.get('changed_items_list', [])) > 5:
                msg += f"  ... and {len(res.get('changed_items_list', [])) - 5} more\n"
        msg += f"\nRemoved: {res.get('removed', 0)}\n"
        if res.get('removed_items'):
            for item in res.get('removed_items', [])[:5]:
                msg += f"  • {item}\n"
            if len(res.get('removed_items', [])) > 5:
                msg += f"  ... and {len(res.get('removed_items', [])) - 5} more\n"
        msg += f"\nTotal changes: {res.get('changed_items', 0)}"
        d.ok(ADDON.getAddonInfo("name"), msg)
        return
    res = _run(m)
    if res.get("result") == "success":
        # Show detailed sync results (requirement #1)
        msg = f"{mode.capitalize()} Sync Completed\n\n"
        msg += f"Added: {res.get('added', 0)}\n"
        if res.get('added_items'):
            for item in res.get('added_items', [])[:5]:
                msg += f"  • {item}\n"
            if len(res.get('added_items', [])) > 5:
                msg += f"  ... and {len(res.get('added_items', [])) - 5} more\n"
        msg += f"\nChanged: {res.get('changed', 0)}\n"
        if res.get('changed_items_list'):
            for item in res.get('changed_items_list', [])[:5]:
                msg += f"  • {item}\n"
            if len(res.get('changed_items_list', [])) > 5:
                msg += f"  ... and {len(res.get('changed_items_list', [])) - 5} more\n"
        msg += f"\nRemoved: {res.get('removed', 0)}\n"
        if res.get('removed_items'):
            for item in res.get('removed_items', [])[:5]:
                msg += f"  • {item}\n"
            if len(res.get('removed_items', [])) > 5:
                msg += f"  ... and {len(res.get('removed_items', [])) - 5} more\n"
        msg += f"\nTotal changes: {res.get('changed_items', 0)}"
        d.ok(ADDON.getAddonInfo("name"), msg)
    elif res.get("result") == "partial_success":
        # Local changes saved but cloud upload failed
        error_msg = res.get('error', 'Upload failed')
        d.ok("Favourites Sync - Partial Success", 
             f"Your local favourites were updated successfully.\n\n{error_msg}\n\nYour changes will sync to cloud when the storage is accessible.")
    elif res.get("result") == "cloud_unavailable":
        # Cloud is down - local favourites preserved
        error_msg = res.get('error', 'Cloud unavailable')
        d.ok("Favourites Sync - Cloud Unavailable", 
             f"Your local favourites are safe and unchanged.\n\n{error_msg}\n\nSync will work again when the storage is accessible.")
    else:
        d.ok("Favourites Sync", f"Failed: {res.get('error')}")


def run_sync_for_profile(profile_name: str, mode: str = "bidirectional",
                         skip_profile_reload: bool = True) -> dict:
    """Synchronize using the target profile's configuration and state directory."""
    try:
        try:
            from . import profiles_mgr
        except ImportError:
            import profiles_mgr
        profiles = profiles_mgr.list_kodi_profiles()
        if profile_name not in profiles:
            raise ValueError("Unknown Kodi profile: " + profile_name)
        pcfg = profiles_mgr.get_profile_cfg(profiles_mgr.load_profiles_cfg(), profile_name)
        if not pcfg or not pcfg.get('backend'):
            raise ValueError("No backend configured for profile: " + profile_name)
        directory = profiles[profile_name]
        return _run(mode, skip_profile_reload=skip_profile_reload,
                    config=profile_driver_config(pcfg),
                    local_path=os.path.join(directory, 'favourites.xml'),
                    data_dir=os.path.join(directory, 'addon_data', 'plugin.service.favourites-sync', 'profile_sync'),
                    profile_name=profile_name)
    except Exception as exc:
        log_error(kvfmt(event='profile_sync_error', profile=profile_name, error=str(exc)))
        return {'result': 'error', 'error': str(exc)}


def run_scheduled_once(cfg, monitor: xbmc.Monitor):
    # Handles interval, fixed time, and startup only
    def wait_seconds(sec):
        # Returns True if aborted
        if sec <= 0:
            return False
        return monitor.waitForAbort(sec)

    # Note: Startup sync is now handled in service.py before entering the loop
    # This function only handles periodic schedules

    if cfg.mode == "interval":
        if wait_seconds(int(cfg.interval_minutes) * 60):
            return
        _run(cfg.scheduled_mode)
    elif cfg.mode == "fixed":
        # compute seconds until next fixed time today/tomorrow
        hh, mm = [int(x) for x in (cfg.fixed_time_local or "03:30").split(":", 1)]
        now = time.localtime()
        next_ts = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, hh, mm, 0, now.tm_wday, now.tm_yday, now.tm_isdst))
        if next_ts <= time.mktime(now):
            next_ts += 86400
        wait = int(next_ts - time.mktime(now))
        if wait_seconds(wait):
            return
        _run(cfg.scheduled_mode)
    elif cfg.mode == "startup":
        # Startup-only mode - no periodic sync
        # Just wait indefinitely
        monitor.waitForAbort()
