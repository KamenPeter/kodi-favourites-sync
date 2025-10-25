import os, time, json, hashlib
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

# Try to initialize addon, with fallback for scripts run outside normal context
try:
    ADDON = xbmcaddon.Addon()
except RuntimeError:
    ADDON = xbmcaddon.Addon("plugin.service.favourites-sync")

PROFILE = xbmcvfs.translatePath("special://profile/")
LOCAL_FAV = os.path.join(PROFILE, "favourites.xml")
ADDON_DATA = xbmcvfs.translatePath(f"special://profile/addon_data/{ADDON.getAddonInfo('id')}")
try:
    os.makedirs(ADDON_DATA, exist_ok=True)
except Exception:
    pass

STATUS_JSON = os.path.join(ADDON_DATA, "status.json")
LOCK_FILE = os.path.join(ADDON_DATA, "sync.lock")


def _hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data or b"").hexdigest()


def _xbmcvfs_read(path) -> bytes:
    try:
        if not xbmcvfs.exists(path):
            return b""
        f = xbmcvfs.File(path, 'rb')
        try:
            return f.read()
        finally:
            f.close()
    except Exception:
        return b""


def _xbmcvfs_write_atomic(path, data: bytes):
    tmp = path + ".tmp"
    f = xbmcvfs.File(tmp, 'wb')
    try:
        f.write(data)
    finally:
        f.close()
    try:
        xbmcvfs.delete(path)
    except Exception:
        pass
    xbmcvfs.rename(tmp, path)


def _save_status(d: dict):
    try:
        with open(STATUS_JSON, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        log_error(f"{kvfmt(event='status_write_error', error=str(e))}")


def _load_status() -> dict:
    try:
        with open(STATUS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _backup_local(max_count: int) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    name = f"favourites_{ts}.xml.bak"
    dst = os.path.join(ADDON_DATA, name)
    data = _xbmcvfs_read(LOCAL_FAV)
    if not data:
        return ""
    _xbmcvfs_write_atomic(dst, data)
    # rotate
    try:
        entries = sorted([p for p in os.listdir(ADDON_DATA) if p.startswith("favourites_") and p.endswith(".xml.bak")])
        if len(entries) > max_count:
            for old in entries[0:len(entries)-max_count]:
                try:
                    os.remove(os.path.join(ADDON_DATA, old))
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
    return d


def _backend_from_settings(cfg: dict):
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
    # Other backends can be wired here later
    raise IOError("Selected backend not implemented")


def validate_endpoint() -> dict:
    cfg = _settings_dict()
    try:
        b = _backend_from_settings(cfg)
        st = b.stat()
        ADDON.setSettingBool("endpoint_valid", True)
        msg = kvfmt(event="validate_ok", backend=cfg.get("backend"), etag=st.get("etag", ""), size=st.get("size", 0))
        log_info(msg)
        return {"ok": True, "details": st}
    except Exception as e:
        ADDON.setSettingBool("endpoint_valid", False)
        log_error(kvfmt(event="validate_failed", backend=cfg.get("backend"), error=str(e)))
        return {"ok": False, "error": str(e)}


def _acquire_lock():
    if os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return False


def _release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


def _run(mode: str, dry_run: bool = False) -> dict:
    status = {"last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "last_mode": mode, "result": "error", "changed_items": 0, "endpoint_valid": ADDON.getSettingBool("endpoint_valid"), "error": None}
    if not _acquire_lock():
        status["error"] = "Another sync is running"
        _save_status(status)
        return status
    log_info(kvfmt(event="sync_start", mode=mode))
    try:
        cfg = _settings_dict()
        backend = _backend_from_settings(cfg)
        # Inputs
        remote_meta = backend.stat()
        remote_bytes = backend.download()
        local_bytes = _xbmcvfs_read(LOCAL_FAV)
        local_list = xmlio.load_xml(local_bytes)
        remote_list = xmlio.load_xml(remote_bytes)

        last = _load_status()
        last_hash = last.get("last_synced_hash", "")
        local_hash = _hash(local_bytes)
        remote_hash = _hash(remote_bytes)
        conflict = (local_hash != last_hash and remote_hash != last_hash and mode == "bidirectional")

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
            merged_list, stats = xmlio.merge_sets(local_list, remote_list, prefer=prefer,
                                                  local_mtime=os.path.getmtime(LOCAL_FAV) if os.path.exists(LOCAL_FAV) else 0.0,
                                                  remote_mtime=time.time())
        elif mode == "dryrun":
            # preview bidirectional merge by default
            merged_list, stats = xmlio.merge_sets(local_list, remote_list, prefer="newer",
                                                  local_mtime=os.path.getmtime(LOCAL_FAV) if os.path.exists(LOCAL_FAV) else 0.0,
                                                  remote_mtime=time.time())
        else:
            raise ValueError("Unknown mode")

        if merged_list is None:
            merged_list = []
        output_bytes = xmlio.serialize(xmlio.normalize(merged_list))

        if dry_run or mode == "dryrun":
            status.update({"result": "dryrun", "changed_items": stats.get("added", 0) + stats.get("changed", 0)})
            _save_status(status)
            log_info(kvfmt(event="dry_run", added=stats.get("added", 0), changed=stats.get("changed", 0)))
            return status

        # Backups
        if ADDON.getSettingBool("local_backups"):
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
            _xbmcvfs_write_atomic(LOCAL_FAV, output_bytes)
            changed += 1
        # Upload new content for push/bidirectional
        if mode in ("push", "bidirectional"):
            # Use remote etag for optimistic concurrency
            try:
                backend.upload(output_bytes if mode != "push" else local_bytes or output_bytes,
                               {"etag": remote_meta.get("etag", "")})
                changed += 1
            except Exception as e:
                log_error(kvfmt(event="upload_error", error=str(e)))
                raise

        status.update({
            "result": "success",
            "changed_items": changed if changed else (stats.get("added", 0) + stats.get("changed", 0)),
            "last_synced_hash": _hash(_xbmcvfs_read(LOCAL_FAV)),
            "remote_hash": remote_hash,
            "endpoint_valid": True,
            "error": None,
        })
        _save_status(status)
        log_info(kvfmt(event="sync_success", mode=mode, changed=status["changed_items"]))
        return status
    except Exception as e:
        status["error"] = str(e)
        _save_status(status)
        log_error(kvfmt(event="sync_error", error=str(e)))
        return status
    finally:
        _release_lock()


def run_sync_ui(mode):
    d = xbmcgui.Dialog()
    # Map UI labels to internal modes
    m = mode
    if mode == "dryrun":
        res = _run("dryrun", dry_run=True)
        d.ok(ADDON.getAddonInfo("name"), f"Dry-run: Added: {res.get('added', 0)} Changed: {res.get('changed', 0)}")
        return
    res = _run(m)
    if res.get("result") == "success":
        d.notification("Favourites Sync", f"{mode.capitalize()} completed", xbmcgui.NOTIFICATION_INFO, 3000)
    else:
        d.ok("Favourites Sync", f"Failed: {res.get('error')}")


def run_scheduled_once(cfg, monitor: xbmc.Monitor):
    # Handles interval, fixed time, and startup only
    def wait_seconds(sec):
        # Returns True if aborted
        if sec <= 0:
            return False
        return monitor.waitForAbort(sec)

    # Startup run
    if cfg.on_startup:
        if wait_seconds(cfg.startup_delay_seconds):
            return
        _run(cfg.scheduled_mode)
        # Only once at startup; continue with rest of schedule

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
        # already handled
        return

