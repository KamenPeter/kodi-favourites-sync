import xbmcaddon, xbmc, json, os, datetime
try:
    from .logutil import log_info
except Exception:
    from logutil import log_info

# Don't create ADDON at module level - defer until needed
_ADDON = None

def _get_addon():
    global _ADDON
    if _ADDON is None:
        try:
            _ADDON = xbmcaddon.Addon()
        except RuntimeError:
            _ADDON = xbmcaddon.Addon("plugin.service.favourites-sync")
    return _ADDON

def _get(id_, default=None):
    return _get_addon().getSetting(id_) or default

def is_endpoint_valid():
    """Check if endpoint is configured by trying to validate it"""
    # Check if basic settings are configured
    backend_idx = int(_get_addon().getSetting("backend") or "0")
    backend = ["webdav", "s3", "http", "sftp", "smb", "nfs", "local"][backend_idx]
    
    if backend == "webdav":
        url = _get_addon().getSetting("webdav_url") or ""
        if not url or not url.startswith("https://"):
            return False
    
    elif backend == "local":
        path = _get_addon().getSetting("local_path") or ""
        if not path:
            return False
    
    elif backend == "http":
        get_url = _get_addon().getSetting("http_get") or ""
        put_url = _get_addon().getSetting("http_put") or ""
        if not get_url or not put_url:
            return False
    
    elif backend == "s3":
        endpoint = _get_addon().getSetting("s3_endpoint") or ""
        bucket = _get_addon().getSetting("s3_bucket") or ""
        key = _get_addon().getSetting("s3_key") or ""
        access = _get_addon().getSetting("s3_access") or ""
        if not endpoint or not bucket or not key or not access:
            return False
    
    elif backend == "sftp":
        host = _get_addon().getSetting("sftp_host") or ""
        user = _get_addon().getSetting("sftp_user") or ""
        path = _get_addon().getSetting("sftp_path") or ""
        if not host or not user or not path:
            return False
    
    elif backend == "smb":
        path = _get_addon().getSetting("smb_path") or ""
        if not path:
            return False
    
    elif backend == "nfs":
        path = _get_addon().getSetting("nfs_path") or ""
        if not path:
            return False
    
    else:
        return False
    
    # Settings look configured, now try a quick validation
    try:
        from sync import validate_endpoint
        result = validate_endpoint()
        return result.get("ok", False)
    except Exception as e:
        # Log the error but don't fail
        try:
            from logutil import log_error, kvfmt
            log_error(kvfmt(event="endpoint_check_failed", error=str(e)))
        except Exception:
            pass
        return False

def open_settings(category_id=None):
    if category_id:
        try:
            _get_addon().openSettings()
        except Exception:
            _get_addon().openSettings()
    else:
        _get_addon().openSettings()

class ScheduleCfg:
    def __init__(self, enabled, mode, on_startup, on_shutdown, delay, scheduled_mode):
        self.enabled = enabled
        self.mode = mode
        self.on_startup = on_startup
        self.on_shutdown = on_shutdown
        self.startup_delay_seconds = delay
        self.scheduled_mode = scheduled_mode

def schedule_config():
    enabled = _get_addon().getSettingBool("schedule_enabled")
    mode_idx = int(_get_addon().getSetting("schedule_mode") or 0)
    mode = ["startup", "shutdown", "both"][mode_idx]
    
    # Determine startup and shutdown flags based on mode
    on_startup = (mode == "startup" or mode == "both")
    on_shutdown = (mode == "shutdown" or mode == "both")
    
    delay = int(_get_addon().getSetting("startup_delay_seconds") or 5)
    scheduled_mode_idx = int(_get_addon().getSetting("scheduled_mode") or 0)
    scheduled_mode = ["pull","push","bidirectional"][scheduled_mode_idx]
    
    return ScheduleCfg(enabled, mode, on_startup, on_shutdown, delay, scheduled_mode)

# Miscellaneous settings
def misc_add_to_fav():
    """Whether to add this addon to favourites"""
    return _get_addon().getSettingBool("misc_add_to_fav")

def misc_set_add_to_fav(value: bool):
    """Set the misc_add_to_fav setting"""
    _get_addon().setSettingBool("misc_add_to_fav", value)

def misc_keep_first():
    """Whether to keep this addon as first in favourites"""
    return _get_addon().getSettingBool("misc_keep_first")

def misc_group_addons_top():
    """Whether to group all addon shortcuts at the top"""
    return _get_addon().getSettingBool("misc_group_addons_top")

def misc_sort_addons():
    """How to sort addon shortcuts: none, az, za, or manual"""
    sort_idx = int(_get_addon().getSetting("misc_sort_addons") or "0")
    return ["none", "az", "za", "manual"][sort_idx]

def sync_misc_add_to_fav_state():
    """Sync misc_add_to_fav setting with actual favourites.xml state"""
    try:
        import xbmcvfs
        import os
        try:
            from .xmlio import parse_favourites_xml
            from .reorder import SELF_ACTIONS
        except ImportError:
            from xmlio import parse_favourites_xml
            from reorder import SELF_ACTIONS
        
        profile_path = xbmcvfs.translatePath("special://profile")
        fav_path = os.path.join(profile_path, "favourites.xml")
        
        if not os.path.exists(fav_path):
            # No favourites file, set to False
            if misc_add_to_fav():
                misc_set_add_to_fav(False)
                log_info("Synced misc_add_to_fav: False (no file)")
            return
        
        # Read and check if self shortcut exists
        with open(fav_path, 'rb') as f:
            xml_bytes = f.read()
        
        entries = parse_favourites_xml(xml_bytes)
        
        has_self = any(e.action in SELF_ACTIONS for e in entries)
        current_setting = misc_add_to_fav()
        
        # Sync setting to match reality
        if has_self != current_setting:
            misc_set_add_to_fav(has_self)
            log_info(f"Synced misc_add_to_fav: setting={current_setting} -> actual={has_self}")
        else:
            log_info(f"misc_add_to_fav already in sync: {current_setting}")
    
    except Exception as e:
        try:
            from .logutil import log_error, kvfmt
        except ImportError:
            from logutil import log_error, kvfmt
        log_error(kvfmt(event="sync_add_to_fav_failed", error=str(e)))
