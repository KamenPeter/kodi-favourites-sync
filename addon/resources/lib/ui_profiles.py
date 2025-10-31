"""
Manage Profiles UI - Dialog for editing per-profile sync configuration.

Allows users to configure backend, credentials, schedule, and conflict
policy for each discovered Kodi profile.
"""
import xbmcgui
import xbmc
import xbmcaddon

try:
    from . import profiles_mgr
    from .logutil import log_info, log_error, kvfmt
except ImportError:
    import profiles_mgr
    from logutil import log_info, log_error, kvfmt


BACKEND_NAMES = ["WebDAV", "S3", "HTTP(S)", "SFTP", "SMB/NAS", "NFS", "Local Path"]
BACKEND_IDS = ["webdav", "s3", "http", "sftp", "smb", "nfs", "local"]
CONFLICT_POLICIES = ["Prefer Remote (cloud)", "Prefer Local", "Merge (3-way)"]
CONFLICT_POLICY_IDS = ["cloud", "local", "merge"]
SYNC_MODES = ["Pull (Cloud → Local)", "Push (Local → Cloud)", "Bidirectional"]
SYNC_MODE_IDS = ["pull", "push", "bidirectional"]


def _load_base_settings_defaults():
    """
    Load default values from the base addon settings.
    
    Returns:
        dict: Default configuration with backend, schedule, and conflict_policy
    """
    try:
        addon = xbmcaddon.Addon()
        
        # Load backend settings
        backend_idx = int(addon.getSetting("backend") or "0")
        backend = BACKEND_IDS[backend_idx] if backend_idx < len(BACKEND_IDS) else "webdav"
        
        # Load backend-specific config
        backend_config = {}
        if backend == "webdav":
            backend_config["webdav_url"] = addon.getSetting("webdav_url") or ""
            backend_config["webdav_path"] = addon.getSetting("webdav_path") or ""
            backend_config["webdav_user"] = addon.getSetting("webdav_user") or ""
            # Don't load password - let user configure per-profile
        elif backend == "local":
            backend_config["local_path"] = addon.getSetting("local_path") or ""
        elif backend == "s3":
            backend_config["s3_endpoint"] = addon.getSetting("s3_endpoint") or ""
            backend_config["s3_region"] = addon.getSetting("s3_region") or "us-east-1"
            backend_config["s3_bucket"] = addon.getSetting("s3_bucket") or ""
            backend_config["s3_key"] = addon.getSetting("s3_key") or ""
            backend_config["s3_access"] = addon.getSetting("s3_access") or ""
        elif backend == "http":
            backend_config["http_get"] = addon.getSetting("http_get") or ""
            backend_config["http_put"] = addon.getSetting("http_put") or ""
        elif backend == "sftp":
            backend_config["sftp_host"] = addon.getSetting("sftp_host") or ""
            backend_config["sftp_port"] = addon.getSetting("sftp_port") or "22"
            backend_config["sftp_user"] = addon.getSetting("sftp_user") or ""
            backend_config["sftp_path"] = addon.getSetting("sftp_path") or ""
        elif backend == "smb":
            backend_config["smb_path"] = addon.getSetting("smb_path") or ""
        elif backend == "nfs":
            backend_config["nfs_path"] = addon.getSetting("nfs_path") or ""
        
        # Load schedule settings
        schedule_enabled = addon.getSettingBool("schedule_enabled")
        schedule_mode_idx = int(addon.getSetting("schedule_mode") or "0")
        schedule_modes = ["startup", "shutdown", "both"]
        schedule_mode = schedule_modes[schedule_mode_idx] if schedule_mode_idx < len(schedule_modes) else "both"
        
        on_start = schedule_mode in ["startup", "both"]
        on_shutdown = schedule_mode in ["shutdown", "both"]
        
        scheduled_mode_idx = int(addon.getSetting("scheduled_mode") or "0")
        scheduled_mode = SYNC_MODE_IDS[scheduled_mode_idx] if scheduled_mode_idx < len(SYNC_MODE_IDS) else "bidirectional"
        
        # Load conflict policy
        conflict_policy_idx = int(addon.getSetting("conflict_policy") or "0")
        conflict_policy = CONFLICT_POLICY_IDS[conflict_policy_idx] if conflict_policy_idx < len(CONFLICT_POLICY_IDS) else "merge"
        
        return {
            "backend": backend,
            "config": backend_config,
            "schedule": {
                "on_start": on_start and schedule_enabled,
                "on_shutdown": on_shutdown and schedule_enabled,
                "mode": scheduled_mode
            },
            "conflict_policy": conflict_policy,
            "cross_add": {
                "enabled": False,
                "auto_targets": []
            }
        }
    except Exception as e:
        log_error(kvfmt(event="load_base_settings_error", error=str(e)))
        # Return safe defaults
        return {
            "backend": "",
            "config": {},
            "schedule": {"on_start": False, "on_shutdown": False, "mode": "bidirectional"},
            "conflict_policy": "merge",
            "cross_add": {"enabled": False, "auto_targets": []}
        }



def open_dialog():
    """
    Open the Manage Profiles dialog.
    
    Shows list of all discovered Kodi profiles with their sync configuration.
    User can edit, validate, and save settings for each profile.
    """
    log_info(kvfmt(event="ui_profiles_open"))
    dialog = xbmcgui.Dialog()
    
    try:
        # Load current configuration
        cfg = profiles_mgr.load_profiles_cfg()
        profiles = profiles_mgr.list_kodi_profiles()
        
        while True:
            # Build menu items
            items = []
            log_info(kvfmt(event="ui_profiles_building_menu", profile_count=len(profiles)))
            
            for profile_name in sorted(profiles.keys()):
                pcfg = profiles_mgr.get_profile_cfg(cfg, profile_name)
                log_info(kvfmt(event="ui_profiles_profile_config", profile=profile_name, config_keys=list(pcfg.keys())))
                
                backend = pcfg.get("backend", "")
                if backend and backend in BACKEND_IDS:
                    backend_idx = BACKEND_IDS.index(backend)
                    backend_display = BACKEND_NAMES[backend_idx]
                else:
                    backend_display = "Not configured"
                
                schedule = pcfg.get("schedule", {})
                on_start = "✓" if schedule.get("on_start") else "–"
                on_shutdown = "✓" if schedule.get("on_shutdown") else "–"
                
                policy = pcfg.get("conflict_policy", "merge")
                if policy in CONFLICT_POLICY_IDS:
                    policy_idx = CONFLICT_POLICY_IDS.index(policy)
                    policy_display = CONFLICT_POLICIES[policy_idx].split("(")[0].strip()
                else:
                    policy_display = policy
                
                item_label = f"{profile_name:12s} | {backend_display:12s} | Start:{on_start} Shutdown:{on_shutdown} | {policy_display}"
                items.append(item_label)
                log_info(kvfmt(event="ui_profiles_menu_item", label=item_label))
            
            log_info(kvfmt(event="ui_profiles_menu_built", item_count=len(items)))
            
            # Add action buttons
            items.extend([
                "",
                "[B]Save & Close[/B]",
                "[B]Close without Saving[/B]"
            ])
            
            log_info(kvfmt(event="ui_profiles_showing_select", total_items=len(items)))
            choice = dialog.select("Manage Profiles - Select profile to edit", items)
            log_info(kvfmt(event="ui_profiles_select_result", choice=choice, total_items=len(items)))
            
            if choice == -1 or choice == len(items) - 1:
                # Cancel or Close without saving
                log_info(kvfmt(event="ui_profiles_cancelled"))
                break
            
            if choice == len(items) - 2:
                # Save & Close
                try:
                    profiles_mgr.save_profiles_cfg(cfg)
                    dialog.notification("Profiles", "Configuration saved", xbmcgui.NOTIFICATION_INFO, 2000)
                    log_info(kvfmt(event="ui_profiles_saved"))
                    break
                except Exception as e:
                    dialog.notification("Profiles", f"Save failed: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 3000)
                    log_error(kvfmt(event="ui_profiles_save_error", error=str(e)))
                continue
            
            if choice >= len(profiles):
                # Action button (empty line or action)
                continue
            
            # Edit selected profile
            profile_name = sorted(profiles.keys())[choice]
            pcfg = profiles_mgr.get_profile_cfg(cfg, profile_name)
            
            # Open edit dialog
            updated_pcfg = _edit_profile_dialog(profile_name, pcfg)
            
            if updated_pcfg is not None:
                cfg = profiles_mgr.set_profile_cfg(cfg, profile_name, updated_pcfg)
        
    except Exception as e:
        log_error(kvfmt(event="ui_profiles_error", error=str(e)))
        dialog.notification("Profiles", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 3000)


def _edit_profile_dialog(profile_name: str, pcfg: dict) -> dict:
    """
    Edit configuration for a single profile.
    
    Args:
        profile_name: Name of the profile being edited
        pcfg: Current profile configuration
        
    Returns:
        dict: Updated configuration, or None if cancelled
    """
    dialog = xbmcgui.Dialog()
    log_info(kvfmt(event="ui_profile_edit", profile=profile_name))
    
    # Make a copy to edit
    import copy
    new_cfg = copy.deepcopy(pcfg)
    
    # If profile is not configured (empty or minimal config), load defaults from base settings
    is_unconfigured = not new_cfg.get("backend") or not new_cfg.get("config")
    if is_unconfigured:
        log_info(kvfmt(event="ui_profile_loading_defaults", profile=profile_name))
        defaults = _load_base_settings_defaults()
        # Merge defaults with existing config (existing takes precedence)
        for key in ["backend", "config", "schedule", "conflict_policy"]:
            if key not in new_cfg or not new_cfg[key]:
                new_cfg[key] = defaults[key]
    
    if "schedule" not in new_cfg:
        new_cfg["schedule"] = {"on_start": False, "on_shutdown": False, "mode": "bidirectional"}
    if "cross_add" not in new_cfg:
        new_cfg["cross_add"] = {"enabled": False, "auto_targets": []}
    
    while True:
        # Build menu
        backend = new_cfg.get("backend", "")
        backend_display = BACKEND_NAMES[BACKEND_IDS.index(backend)] if backend in BACKEND_IDS else "Not configured"
        
        schedule = new_cfg.get("schedule", {})
        on_start_display = "✓" if schedule.get("on_start") else "✗"
        on_shutdown_display = "✓" if schedule.get("on_shutdown") else "✗"
        
        mode = schedule.get("mode", "bidirectional")
        mode_display = SYNC_MODES[SYNC_MODE_IDS.index(mode)] if mode in SYNC_MODE_IDS else mode
        
        policy = new_cfg.get("conflict_policy", "merge")
        policy_display = CONFLICT_POLICIES[CONFLICT_POLICY_IDS.index(policy)] if policy in CONFLICT_POLICY_IDS else policy
        
        cross_add = new_cfg.get("cross_add", {})
        cross_add_display = "✓" if cross_add.get("enabled") else "✗"
        
        menu_items = [
            f"[B]Profile:[/B] {profile_name}",
            "",
            f"Backend: {backend_display}",
            "Configure Backend Endpoint...",
            "",
            f"Sync on Startup: {on_start_display}",
            f"Sync on Shutdown: {on_shutdown_display}",
            f"Sync Mode: {mode_display}",
            f"Conflict Policy: {policy_display}",
            "",
            f"Enable Cross-Add: {cross_add_display}",
            "",
            "[B]Validate Endpoint[/B]",
            "[B]Save[/B]",
            "[B]Cancel[/B]"
        ]
        
        choice = dialog.select(f"Edit Profile: {profile_name}", menu_items)
        
        if choice == -1 or choice == len(menu_items) - 1:
            # Cancel
            return None
        
        if choice == len(menu_items) - 2:
            # Save
            return new_cfg
        
        if choice == len(menu_items) - 3:
            # Validate
            success, message = profiles_mgr.validate_profile_endpoint(new_cfg)
            if success:
                dialog.notification("Validation", message, xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                dialog.notification("Validation Failed", message, xbmcgui.NOTIFICATION_ERROR, 3000)
            continue
        
        if choice == 2:
            # Change backend
            backend_choice = dialog.select("Select Backend Type", BACKEND_NAMES)
            if backend_choice != -1:
                new_cfg["backend"] = BACKEND_IDS[backend_choice]
                # Reset config when backend changes
                new_cfg["config"] = {}
            continue
        
        if choice == 3:
            # Configure endpoint
            new_cfg["config"] = _configure_backend_dialog(new_cfg.get("backend", ""), new_cfg.get("config", {}))
            continue
        
        if choice == 5:
            # Toggle on_startup
            new_cfg["schedule"]["on_start"] = not schedule.get("on_start", False)
            continue
        
        if choice == 6:
            # Toggle on_shutdown
            new_cfg["schedule"]["on_shutdown"] = not schedule.get("on_shutdown", False)
            continue
        
        if choice == 7:
            # Change sync mode
            mode_choice = dialog.select("Sync Mode", SYNC_MODES)
            if mode_choice != -1:
                new_cfg["schedule"]["mode"] = SYNC_MODE_IDS[mode_choice]
            continue
        
        if choice == 8:
            # Change conflict policy
            policy_choice = dialog.select("Conflict Resolution Policy", CONFLICT_POLICIES)
            if policy_choice != -1:
                new_cfg["conflict_policy"] = CONFLICT_POLICY_IDS[policy_choice]
            continue
        
        if choice == 10:
            # Toggle cross-add
            new_cfg["cross_add"]["enabled"] = not cross_add.get("enabled", False)
            continue


def _configure_backend_dialog(backend: str, config: dict) -> dict:
    """
    Configure backend-specific settings.
    
    Args:
        backend: Backend type (webdav, s3, http, sftp, smb, nfs, local)
        config: Current backend configuration
        
    Returns:
        dict: Updated configuration
    """
    dialog = xbmcgui.Dialog()
    
    import copy
    new_config = copy.deepcopy(config)
    
    # Decrypt password for editing
    if "password" in new_config:
        new_config["password"] = profiles_mgr.decrypt_secret(new_config["password"])
    
    if backend == "webdav":
        # WebDAV configuration
        url = dialog.input("WebDAV URL", new_config.get("webdav_url", ""), type=xbmcgui.INPUT_ALPHANUM)
        if url:
            new_config["webdav_url"] = url
        
        path = dialog.input("Remote Path", new_config.get("webdav_path", "/favourites.xml"))
        if path:
            new_config["webdav_path"] = path
        
        user = dialog.input("Username (optional)", new_config.get("webdav_user", ""))
        new_config["webdav_user"] = user
        
        if user:
            password = dialog.input("Password (optional)", new_config.get("password", ""), type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
            if password:
                new_config["password"] = profiles_mgr.encrypt_secret(password)
            elif not password and "password" in new_config:
                del new_config["password"]
    
    elif backend == "local":
        # Local/UNC path
        path = dialog.input("Local or UNC Path", new_config.get("local_path", ""), type=xbmcgui.INPUT_ALPHANUM)
        if path:
            new_config["local_path"] = path
    
    elif backend == "smb":
        # SMB configuration
        path = dialog.input("SMB Path (\\\\server\\share\\path)", new_config.get("smb_path", ""), type=xbmcgui.INPUT_ALPHANUM)
        if path:
            new_config["smb_path"] = path
    
    elif backend == "s3":
        # S3 configuration
        endpoint = dialog.input("S3 Endpoint", new_config.get("s3_endpoint", ""))
        if endpoint:
            new_config["s3_endpoint"] = endpoint
        
        bucket = dialog.input("Bucket Name", new_config.get("s3_bucket", ""))
        if bucket:
            new_config["s3_bucket"] = bucket
        
        key = dialog.input("Object Key", new_config.get("s3_key", "favourites.xml"))
        if key:
            new_config["s3_key"] = key
        
        access = dialog.input("Access Key", new_config.get("s3_access", ""))
        if access:
            new_config["s3_access"] = access
        
        secret = dialog.input("Secret Key", new_config.get("s3_secret", ""), type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if secret:
            new_config["s3_secret"] = profiles_mgr.encrypt_secret(secret)
    
    elif backend == "http":
        # HTTP configuration
        get_url = dialog.input("GET URL", new_config.get("http_get", ""))
        if get_url:
            new_config["http_get"] = get_url
        
        put_url = dialog.input("PUT URL", new_config.get("http_put", ""))
        if put_url:
            new_config["http_put"] = put_url
        
        auth = dialog.input("Auth Header (optional)", new_config.get("http_auth_header", ""))
        if auth:
            new_config["http_auth_header"] = profiles_mgr.encrypt_secret(auth)
    
    elif backend == "sftp":
        # SFTP configuration
        host = dialog.input("SFTP Host", new_config.get("sftp_host", ""))
        if host:
            new_config["sftp_host"] = host
        
        port = dialog.input("Port", new_config.get("sftp_port", "22"))
        if port:
            new_config["sftp_port"] = port
        
        user = dialog.input("Username", new_config.get("sftp_user", ""))
        if user:
            new_config["sftp_user"] = user
        
        password = dialog.input("Password", new_config.get("password", ""), type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if password:
            new_config["password"] = profiles_mgr.encrypt_secret(password)
        
        path = dialog.input("Remote Path", new_config.get("sftp_path", "/favourites.xml"))
        if path:
            new_config["sftp_path"] = path
    
    elif backend == "nfs":
        # NFS configuration
        path = dialog.input("NFS Path", new_config.get("nfs_path", ""))
        if path:
            new_config["nfs_path"] = path
    
    return new_config


if __name__ == "__main__":
    log_info(kvfmt(event="ui_profiles_main_invoked"))
    try:
        open_dialog()
    except Exception as e:
        log_error(kvfmt(event="ui_profiles_main_error", error=str(e)))
        import traceback
        log_error(kvfmt(event="ui_profiles_traceback", traceback=traceback.format_exc()))
