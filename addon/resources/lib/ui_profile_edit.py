"""
Edit Profile WindowXML Dialog - Modern UI implementation for profile configuration.

Provides form-style editing interface with proper field labels and input controls.
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


# Backend types
BACKEND_IDS = ["webdav", "s3", "http", "sftp", "smb", "nfs", "local"]
BACKEND_NAMES = ["WebDAV", "S3", "HTTP(S)", "SFTP", "SMB/NAS", "NFS", "Local Path"]

# Sync modes
SYNC_MODE_IDS = ["pull", "push", "bidirectional"]
SYNC_MODE_NAMES = ["Pull (Cloud → Local)", "Push (Local → Cloud)", "Bidirectional"]

# Conflict policies
CONFLICT_POLICY_IDS = ["cloud", "local", "merge"]
CONFLICT_POLICY_NAMES = ["Prefer Remote (cloud)", "Prefer Local", "Merge (3-way)"]


class EditProfileWindow(xbmcgui.WindowXMLDialog):
    """WindowXML dialog for editing a single profile's configuration."""
    
    # Control IDs from DialogEditProfile.xml
    BTN_BACKEND = 200
    BTN_ENDPOINT = 201
    BTN_USERNAME = 202
    BTN_PASSWORD = 203
    TOGGLE_STARTUP = 210
    TOGGLE_SHUTDOWN = 211
    BTN_SYNC_MODE = 212
    BTN_CONFLICT_POLICY = 213
    TOGGLE_CROSS_ADD = 214
    BTN_DEFAULT_TARGETS = 215
    BTN_VALIDATE = 220
    BTN_OK = 300
    BTN_CANCEL = 301
    
    def __init__(self, *args, **kwargs):
        super(EditProfileWindow, self).__init__(*args, **kwargs)
        self.profile_name = kwargs.get('profile')
        self.cfg = kwargs.get('cfg')
        self.pc = None  # Profile config dict
        self.changed = False
    
    def onInit(self):
        """Initialize the dialog - load profile config and populate fields."""
        xbmc.log(f"[favourites-sync] DialogEditProfile initialized for profile: {self.profile_name}", xbmc.LOGINFO)
        log_info(kvfmt(event="ui_profile_edit_init", profile=self.profile_name))
        
        try:
            # Get or create profile config
            import copy
            self.pc = copy.deepcopy(profiles_mgr.get_profile_cfg(self.cfg, self.profile_name))
            
            if not self.pc or not self.pc.get("backend"):
                # Load defaults from base settings for unconfigured profiles
                log_info(kvfmt(event="ui_profile_edit_loading_defaults", profile=self.profile_name))
                self.pc = profiles_mgr.new_default_profile(self.profile_name)
            
            # Set profile name in header
            self.setProperty('profile_name', self.profile_name)
            
            # Refresh all display properties
            self._refresh_props()
            
            log_info(kvfmt(event="ui_profile_edit_init_success", profile=self.profile_name))
        
        except Exception as e:
            log_error(kvfmt(event="ui_profile_edit_init_error", error=str(e), profile=self.profile_name))
            xbmcgui.Dialog().notification(
                "Favourites Sync",
                f"Failed to initialize: {str(e)}",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
    
    def _refresh_props(self):
        """Refresh all window properties from profile config."""
        # Backend
        backend = self.pc.get("backend", "")
        if backend and backend in BACKEND_IDS:
            backend_label = BACKEND_NAMES[BACKEND_IDS.index(backend)]
        else:
            backend_label = "Not configured"
        self.setProperty('backend_label', backend_label)
        
        # Endpoint display
        endpoint = profiles_mgr.get_endpoint_display(self.pc)
        self.setProperty('endpoint_display', endpoint or "(not set)")
        
        # Username
        config = self.pc.get("config", {})
        username = config.get("webdav_user") or config.get("sftp_user") or config.get("smb_user") or ""
        self.setProperty('username_display', username or "(not set)")
        
        # Sync mode
        schedule = self.pc.get("schedule", {})
        mode = schedule.get("mode", "bidirectional")
        if mode in SYNC_MODE_IDS:
            mode_label = SYNC_MODE_NAMES[SYNC_MODE_IDS.index(mode)]
        else:
            mode_label = mode.title()
        self.setProperty('sync_mode_label', mode_label)
        
        # Conflict policy
        policy = self.pc.get("conflict_policy", "merge")
        if policy in CONFLICT_POLICY_IDS:
            policy_label = CONFLICT_POLICY_NAMES[CONFLICT_POLICY_IDS.index(policy)]
        else:
            policy_label = policy.replace("_", " ").title()
        self.setProperty('conflict_policy_label', policy_label)
        
        # Default targets
        cross_add = self.pc.get("cross_add", {})
        targets = cross_add.get("auto_targets", [])
        targets_label = ", ".join(targets) if targets else "(none)"
        self.setProperty('default_targets_label', targets_label)
        
        # Toggle states
        try:
            self.getControl(self.TOGGLE_STARTUP).setSelected(schedule.get("on_start", False))
            self.getControl(self.TOGGLE_SHUTDOWN).setSelected(schedule.get("on_shutdown", False))
            self.getControl(self.TOGGLE_CROSS_ADD).setSelected(cross_add.get("enabled", True))
        except Exception as e:
            log_error(kvfmt(event="ui_profile_edit_toggle_error", error=str(e)))
    
    def onClick(self, controlId):
        """Handle button clicks and form interactions."""
        log_info(kvfmt(event="ui_profile_edit_click", control_id=controlId, profile=self.profile_name))
        
        if controlId == self.BTN_BACKEND:
            # Select backend type
            current = self.pc.get("backend", "")
            preselect = BACKEND_IDS.index(current) if current in BACKEND_IDS else 0
            
            idx = xbmcgui.Dialog().select("Backend Type", BACKEND_NAMES, preselect=preselect)
            if idx >= 0:
                self.pc["backend"] = BACKEND_IDS[idx]
                # Reset config when backend changes
                self.pc["config"] = {}
                self.changed = True
                self._refresh_props()
                log_info(kvfmt(event="ui_profile_edit_backend_changed", backend=BACKEND_IDS[idx]))
        
        elif controlId == self.BTN_ENDPOINT:
            # Edit endpoint/path
            backend = self.pc.get("backend", "")
            config = self.pc.setdefault("config", {})
            
            if backend == "webdav":
                current = config.get("webdav_url", "")
                new_value = xbmcgui.Dialog().input("WebDAV URL", defaultt=current, type=xbmcgui.INPUT_ALPHANUM)
                if new_value is not None:
                    config["webdav_url"] = new_value
                    self.changed = True
                    
                path = config.get("webdav_path", "/kodi/favourites/{profile}/favourites.xml")
                new_path = xbmcgui.Dialog().input("WebDAV Path", defaultt=path)
                if new_path is not None:
                    config["webdav_path"] = new_path
                    self.changed = True
            
            elif backend == "local":
                current = config.get("local_path", "")
                new_value = xbmcgui.Dialog().input("Local Path", defaultt=current)
                if new_value is not None:
                    config["local_path"] = new_value
                    self.changed = True
            
            elif backend == "smb":
                current = config.get("smb_path", "")
                new_value = xbmcgui.Dialog().input("SMB Path (\\\\server\\share\\...)", defaultt=current)
                if new_value is not None:
                    config["smb_path"] = new_value
                    self.changed = True
            
            elif backend == "nfs":
                current = config.get("nfs_path", "")
                new_value = xbmcgui.Dialog().input("NFS Path", defaultt=current)
                if new_value is not None:
                    config["nfs_path"] = new_value
                    self.changed = True
            
            elif backend == "s3":
                # S3 has multiple fields
                endpoint = config.get("s3_endpoint", "")
                new_endpoint = xbmcgui.Dialog().input("S3 Endpoint", defaultt=endpoint)
                if new_endpoint is not None:
                    config["s3_endpoint"] = new_endpoint
                    self.changed = True
                
                bucket = config.get("s3_bucket", "")
                new_bucket = xbmcgui.Dialog().input("Bucket Name", defaultt=bucket)
                if new_bucket is not None:
                    config["s3_bucket"] = new_bucket
                    self.changed = True
                
                key = config.get("s3_key", "favourites.xml")
                new_key = xbmcgui.Dialog().input("Object Key", defaultt=key)
                if new_key is not None:
                    config["s3_key"] = new_key
                    self.changed = True
            
            elif backend == "http":
                get_url = config.get("http_get", "")
                new_get = xbmcgui.Dialog().input("GET URL", defaultt=get_url)
                if new_get is not None:
                    config["http_get"] = new_get
                    self.changed = True
                
                put_url = config.get("http_put", "")
                new_put = xbmcgui.Dialog().input("PUT URL", defaultt=put_url)
                if new_put is not None:
                    config["http_put"] = new_put
                    self.changed = True
            
            elif backend == "sftp":
                host = config.get("sftp_host", "")
                new_host = xbmcgui.Dialog().input("SFTP Host", defaultt=host)
                if new_host is not None:
                    config["sftp_host"] = new_host
                    self.changed = True
                
                port = config.get("sftp_port", "22")
                new_port = xbmcgui.Dialog().input("Port", defaultt=str(port))
                if new_port is not None:
                    config["sftp_port"] = new_port
                    self.changed = True
                
                path = config.get("sftp_path", "")
                new_path = xbmcgui.Dialog().input("Remote Path", defaultt=path)
                if new_path is not None:
                    config["sftp_path"] = new_path
                    self.changed = True
            
            self._refresh_props()
        
        elif controlId == self.BTN_USERNAME:
            # Edit username (backend-specific field name)
            backend = self.pc.get("backend", "")
            config = self.pc.setdefault("config", {})
            
            if backend == "webdav":
                current = config.get("webdav_user", "")
                new_value = xbmcgui.Dialog().input("Username", defaultt=current)
                if new_value is not None:
                    config["webdav_user"] = new_value
                    self.changed = True
            elif backend == "sftp":
                current = config.get("sftp_user", "")
                new_value = xbmcgui.Dialog().input("Username", defaultt=current)
                if new_value is not None:
                    config["sftp_user"] = new_value
                    self.changed = True
            elif backend == "smb":
                current = config.get("smb_user", "")
                new_value = xbmcgui.Dialog().input("Username", defaultt=current)
                if new_value is not None:
                    config["smb_user"] = new_value
                    self.changed = True
            elif backend == "s3":
                current = config.get("s3_access", "")
                new_value = xbmcgui.Dialog().input("Access Key", defaultt=current)
                if new_value is not None:
                    config["s3_access"] = new_value
                    self.changed = True
            
            self._refresh_props()
        
        elif controlId == self.BTN_PASSWORD:
            # Edit password (masked input)
            backend = self.pc.get("backend", "")
            
            new_password = xbmcgui.Dialog().input(
                "Password",
                type=xbmcgui.INPUT_ALPHANUM,
                option=xbmcgui.ALPHANUM_HIDE_INPUT
            )
            
            if new_password:
                # Encrypt and store password
                encrypted = profiles_mgr.encrypt_secret(new_password)
                config = self.pc.setdefault("config", {})
                config["password"] = encrypted
                self.changed = True
                log_info(kvfmt(event="ui_profile_edit_password_set", profile=self.profile_name))
        
        elif controlId == self.TOGGLE_STARTUP:
            # Handle toggle state change
            schedule = self.pc.setdefault("schedule", {})
            schedule["on_start"] = self.getControl(self.TOGGLE_STARTUP).isSelected()
            self.changed = True
            log_info(kvfmt(event="ui_profile_edit_startup_toggled", value=schedule["on_start"]))
        
        elif controlId == self.TOGGLE_SHUTDOWN:
            # Handle toggle state change
            schedule = self.pc.setdefault("schedule", {})
            schedule["on_shutdown"] = self.getControl(self.TOGGLE_SHUTDOWN).isSelected()
            self.changed = True
            log_info(kvfmt(event="ui_profile_edit_shutdown_toggled", value=schedule["on_shutdown"]))
        
        elif controlId == self.BTN_SYNC_MODE:
            # Select sync mode
            schedule = self.pc.setdefault("schedule", {})
            current = schedule.get("mode", "bidirectional")
            preselect = SYNC_MODE_IDS.index(current) if current in SYNC_MODE_IDS else 2
            
            idx = xbmcgui.Dialog().select("Sync Mode", SYNC_MODE_NAMES, preselect=preselect)
            if idx >= 0:
                schedule["mode"] = SYNC_MODE_IDS[idx]
                self.changed = True
                self._refresh_props()
                log_info(kvfmt(event="ui_profile_edit_mode_changed", mode=SYNC_MODE_IDS[idx]))
        
        elif controlId == self.BTN_CONFLICT_POLICY:
            # Select conflict policy
            current = self.pc.get("conflict_policy", "merge")
            preselect = CONFLICT_POLICY_IDS.index(current) if current in CONFLICT_POLICY_IDS else 2
            
            idx = xbmcgui.Dialog().select("Conflict Resolution Policy", CONFLICT_POLICY_NAMES, preselect=preselect)
            if idx >= 0:
                self.pc["conflict_policy"] = CONFLICT_POLICY_IDS[idx]
                self.changed = True
                self._refresh_props()
                log_info(kvfmt(event="ui_profile_edit_policy_changed", policy=CONFLICT_POLICY_IDS[idx]))
        
        elif controlId == self.TOGGLE_CROSS_ADD:
            # Handle toggle state change
            cross_add = self.pc.setdefault("cross_add", {})
            cross_add["enabled"] = self.getControl(self.TOGGLE_CROSS_ADD).isSelected()
            self.changed = True
            log_info(kvfmt(event="ui_profile_edit_cross_add_toggled", value=cross_add["enabled"]))
        
        elif controlId == self.BTN_DEFAULT_TARGETS:
            # Multi-select default target profiles
            all_profiles = profiles_mgr.get_profile_names(self.cfg, exclude=self.profile_name)
            
            if not all_profiles:
                xbmcgui.Dialog().notification(
                    "Favourites Sync",
                    "No other profiles available",
                    xbmcgui.NOTIFICATION_INFO,
                    2000
                )
                return
            
            cross_add = self.pc.setdefault("cross_add", {})
            current_targets = cross_add.get("auto_targets", [])
            preselect = [i for i, name in enumerate(all_profiles) if name in current_targets]
            
            selected = xbmcgui.Dialog().multiselect("Default Target Profiles", all_profiles, preselect=preselect)
            
            if selected is not None:
                cross_add["auto_targets"] = [all_profiles[i] for i in selected]
                self.changed = True
                self._refresh_props()
                log_info(kvfmt(event="ui_profile_edit_targets_changed", targets=cross_add["auto_targets"]))
        
        elif controlId == self.BTN_VALIDATE:
            # Validate endpoint configuration
            log_info(kvfmt(event="ui_profile_edit_validate", profile=self.profile_name))
            success, message = profiles_mgr.validate_profile_endpoint(self.pc)
            
            if success:
                xbmcgui.Dialog().notification(
                    "Validation Success",
                    message,
                    xbmcgui.NOTIFICATION_INFO,
                    3000
                )
            else:
                xbmcgui.Dialog().notification(
                    "Validation Failed",
                    message,
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
        
        elif controlId == self.BTN_OK:
            # Save and close
            log_info(kvfmt(event="ui_profile_edit_save", profile=self.profile_name, changed=self.changed))
            
            # Update config in parent
            self.cfg = profiles_mgr.set_profile_cfg(self.cfg, self.profile_name, self.pc)
            
            # Note: actual save to profiles.json happens in ManageProfilesWindow when user clicks OK there
            self.close()
        
        elif controlId == self.BTN_CANCEL:
            # Close without saving
            log_info(kvfmt(event="ui_profile_edit_cancel", profile=self.profile_name))
            self.close()


def open_edit_dialog(profile_name, cfg):
    """
    Open the Edit Profile dialog for a specific profile.
    
    Args:
        profile_name: Name of the profile to edit
        cfg: Current profiles configuration dict
        
    Returns:
        dict: Updated configuration (or original if cancelled)
    """
    log_info(kvfmt(event="ui_profile_edit_open", profile=profile_name))
    
    addon_path = None
    try:
        # Try to get addon instance - pass ID explicitly for RunScript calls
        try:
            addon = xbmcaddon.Addon('plugin.service.favourites-sync')
        except:
            addon = xbmcaddon.Addon()
        
        addon_path = addon.getAddonInfo('path')
        
        # Log the XML path for troubleshooting
        xml_file = 'DialogEditProfile.xml'
        xbmc.log(f"[favourites-sync] Opening WindowXMLDialog: {xml_file} for profile: {profile_name}", xbmc.LOGINFO)
        xbmc.log(f"[favourites-sync] Path: {addon_path}, Resolution: 1080i", xbmc.LOGINFO)
        
        w = EditProfileWindow(
            xml_file,
            addon_path,
            'default',
            '1080i',
            profile=profile_name,
            cfg=cfg
        )
        w.doModal()
        
        # Get updated config
        updated_cfg = w.cfg
        del w
        
        log_info(kvfmt(event="ui_profile_edit_closed", profile=profile_name))
        return updated_cfg
    
    except Exception as e:
        log_error(kvfmt(event="ui_profile_edit_error", error=str(e), profile=profile_name))
        
        # Build error message with safe addon_path handling
        if addon_path:
            path_info = f"Path: {addon_path}"
        else:
            path_info = "Path: [Could not determine addon path]"
        
        error_msg = (
            f"Failed to load Edit Profile dialog:\n\n{str(e)}\n\n"
            f"Profile: {profile_name}\n"
            f"XML: DialogEditProfile.xml\n"
            f"{path_info}\n\n"
            f"Check that XML exists in:\n"
            f"- resources/skins/default/1080i/\n"
            f"- resources/skins/default/720p/"
        )
        xbmc.log(f"[favourites-sync] WindowXML ERROR: {error_msg}", xbmc.LOGERROR)
        
        xbmcgui.Dialog().ok(
            "Favourites Sync - UI Error",
            error_msg
        )
        return cfg  # Return original on error


if __name__ == "__main__":
    log_info(kvfmt(event="ui_profile_edit_main_invoked"))
    try:
        # For testing, load config and edit Master profile
        import profiles_mgr
        cfg = profiles_mgr.load_profiles_cfg()
        open_edit_dialog("Master user", cfg)
    except Exception as e:
        log_error(kvfmt(event="ui_profile_edit_main_error", error=str(e)))
        import traceback
        log_error(kvfmt(event="ui_profile_edit_traceback", traceback=traceback.format_exc()))
