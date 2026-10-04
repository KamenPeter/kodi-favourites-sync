"""
Manage Profiles WindowXML Dialog - Modern UI implementation.

Replaces the basic Dialog().select() approach with proper Estuary-style WindowXML.
"""
import xbmcgui
import xbmc
import xbmcaddon

try:
    from . import profiles_mgr
    from . import ui_profile_edit
    from .logutil import log_info, log_error, kvfmt
except ImportError:
    import profiles_mgr
    import ui_profile_edit
    from logutil import log_info, log_error, kvfmt


class ManageProfilesWindow(xbmcgui.WindowXMLDialog):
    """WindowXML dialog for managing Kodi profile configurations."""
    
    # Control IDs from DialogManageProfiles.xml
    LIST_ID = 50
    BTN_EDIT = 60
    BTN_VALIDATE = 61
    BTN_ADD = 62
    BTN_DELETE = 63
    BTN_OK = 100
    BTN_CANCEL = 101
    
    def __init__(self, *args, **kwargs):
        super(ManageProfilesWindow, self).__init__(*args, **kwargs)
        self.cfg = None
        self.list_ctrl = None
    
    def onInit(self):
        """Initialize the dialog - load config and populate list."""
        xbmc.log("[favourites-sync] DialogManageProfiles initialized", xbmc.LOGINFO)
        log_info(kvfmt(event="ui_profiles_manage_init"))
        
        try:
            self.list_ctrl = self.getControl(self.LIST_ID)
            self.cfg = profiles_mgr.load_profiles_cfg()
            self.refresh_list()
        except Exception as e:
            log_error(kvfmt(event="ui_profiles_manage_init_error", error=str(e)))
            xbmcgui.Dialog().notification(
                "Favourites Sync",
                f"Failed to initialize: {str(e)}",
                xbmcgui.NOTIFICATION_ERROR,
                3000
            )
    
    def refresh_list(self):
        """Refresh the profiles list display."""
        if not self.list_ctrl:
            return
        
        log_info(kvfmt(event="ui_profiles_manage_refresh_list"))
        
        self.list_ctrl.reset()
        
        # Get view models (profile_name, status_text) for display
        view_models = profiles_mgr.get_view_models(self.cfg)
        
        for profile_name, status_text in view_models:
            li = xbmcgui.ListItem(label=profile_name)
            li.setProperty('status', status_text)
            self.list_ctrl.addItem(li)
        
        log_info(kvfmt(
            event="ui_profiles_manage_list_refreshed",
            profile_count=len(view_models)
        ))
    
    def get_selected_profile(self):
        """Get the currently selected profile name."""
        if not self.list_ctrl:
            return None
        
        li = self.list_ctrl.getSelectedItem()
        return li.getLabel() if li else None
    
    def onClick(self, controlId):
        """Handle button clicks."""
        prof = self.get_selected_profile()
        
        log_info(kvfmt(
            event="ui_profiles_manage_click",
            control_id=controlId,
            profile=prof
        ))
        
        if controlId == self.BTN_EDIT:
            if not prof:
                xbmcgui.Dialog().notification(
                    "Favourites Sync",
                    "Please select a profile first",
                    xbmcgui.NOTIFICATION_WARNING,
                    2000
                )
                return
            
            # Open edit dialog
            log_info(kvfmt(event="ui_profiles_manage_edit_open", profile=prof))
            updated_cfg = ui_profile_edit.open_edit_dialog(prof, self.cfg)
            
            if updated_cfg:
                self.cfg = updated_cfg
                self.refresh_list()
                log_info(kvfmt(event="ui_profiles_manage_edit_saved", profile=prof))
        
        elif controlId == self.BTN_VALIDATE:
            if not prof:
                xbmcgui.Dialog().notification(
                    "Favourites Sync",
                    "Please select a profile first",
                    xbmcgui.NOTIFICATION_WARNING,
                    2000
                )
                return
            
            # Validate endpoint
            log_info(kvfmt(event="ui_profiles_manage_validate", profile=prof))
            success, message = profiles_mgr.validate_profile_endpoint(
                self.cfg.get("profiles", {}).get(prof, {})
            )
            
            if success:
                xbmcgui.Dialog().notification(
                    "Favourites Sync",
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
        
        elif controlId == self.BTN_ADD:
            # Add new profile
            new_name = xbmcgui.Dialog().input(
                "New Profile Name",
                type=xbmcgui.INPUT_ALPHANUM
            )
            
            if new_name:
                log_info(kvfmt(event="ui_profiles_manage_add", profile=new_name))
                self.cfg = profiles_mgr.add_empty_profile(self.cfg, new_name)
                self.refresh_list()
        
        elif controlId == self.BTN_DELETE:
            if not prof:
                xbmcgui.Dialog().notification(
                    "Favourites Sync",
                    "Please select a profile first",
                    xbmcgui.NOTIFICATION_WARNING,
                    2000
                )
                return
            
            # Confirm deletion
            if xbmcgui.Dialog().yesno(
                "Delete Profile Configuration",
                f"Remove sync configuration for profile '{prof}'?",
                "This will not delete the profile itself,",
                "only its sync settings."
            ):
                log_info(kvfmt(event="ui_profiles_manage_delete", profile=prof))
                self.cfg = profiles_mgr.delete_profile(self.cfg, prof)
                self.refresh_list()
        
        elif controlId == self.BTN_OK:
            # Save and close
            log_info(kvfmt(event="ui_profiles_manage_save"))
            try:
                profiles_mgr.save_profiles_cfg(self.cfg)
                xbmcgui.Dialog().notification(
                    "Favourites Sync",
                    "Configuration saved successfully",
                    xbmcgui.NOTIFICATION_INFO,
                    2000
                )
                self.close()
            except Exception as e:
                log_error(kvfmt(event="ui_profiles_manage_save_error", error=str(e)))
                xbmcgui.Dialog().notification(
                    "Save Failed",
                    str(e),
                    xbmcgui.NOTIFICATION_ERROR,
                    3000
                )
        
        elif controlId == self.BTN_CANCEL:
            # Close without saving
            log_info(kvfmt(event="ui_profiles_manage_cancel"))
            self.close()


def open_manage_dialog():
    """
    Open the Manage Profiles dialog.
    
    This is the main entry point called from settings or addon menu.
    Shows explicit error if WindowXML fails to load.
    """
    log_info(kvfmt(event="ui_profiles_manage_open"))
    
    addon_path = None
    try:
        # Try to get addon instance - pass ID explicitly for RunScript calls
        try:
            addon = xbmcaddon.Addon('plugin.service.favourites-sync')
        except:
            addon = xbmcaddon.Addon()
        
        addon_path = addon.getAddonInfo('path')
        
        # Log the XML path for troubleshooting
        xml_file = 'DialogManageProfiles.xml'
        xbmc.log(f"[favourites-sync] Opening WindowXMLDialog: {xml_file} from {addon_path}", xbmc.LOGINFO)
        xbmc.log(f"[favourites-sync] Resolution folder: 1080i (will fallback to 720p if needed)", xbmc.LOGINFO)
        
        w = ManageProfilesWindow(
            xml_file,
            addon_path,
            'default',
            '1080i'
        )
        w.doModal()
        del w
        
        log_info(kvfmt(event="ui_profiles_manage_closed"))
    
    except Exception as e:
        log_error(kvfmt(event="ui_profiles_manage_error", error=str(e)))
        
        # Build error message with safe addon_path handling
        if addon_path:
            path_info = f"Path: {addon_path}/resources/skins/default/"
        else:
            path_info = "Path: [Could not determine addon path]"
        
        error_msg = (
            f"Failed to load WindowXML dialog:\n\n{str(e)}\n\n"
            f"XML: DialogManageProfiles.xml\n"
            f"{path_info}\n\n"
            f"Expected locations:\n"
            f"- 1080i/DialogManageProfiles.xml\n"
            f"- 720p/DialogManageProfiles.xml"
        )
        xbmc.log(f"[favourites-sync] WindowXML ERROR: {error_msg}", xbmc.LOGERROR)
        
        # Show error dialog
        xbmcgui.Dialog().ok(
            "Favourites Sync - UI Error",
            error_msg
        )
        
        # Fallback to legacy dialog only if user confirms
        if xbmcgui.Dialog().yesno(
            "Favourites Sync",
            "WindowXML dialog failed to load.\n\nUse legacy list dialog instead?",
            nolabel="Cancel",
            yeslabel="Use Legacy"
        ):
            log_info(kvfmt(event="ui_profiles_manage_fallback_legacy"))
            try:
                from . import ui_profiles
                ui_profiles.open_dialog()
            except ImportError:
                import ui_profiles
                ui_profiles.open_dialog()


if __name__ == "__main__":
    log_info(kvfmt(event="ui_profiles_manage_main_invoked"))
    try:
        open_manage_dialog()
    except Exception as e:
        log_error(kvfmt(event="ui_profiles_manage_main_error", error=str(e)))
        import traceback
        log_error(kvfmt(event="ui_profiles_manage_traceback", traceback=traceback.format_exc()))
