"""
Cross-Add UI - Dialog for adding current selection to other profiles.

Allows users to select which profiles should receive a copy of the
currently selected media item or addon.
"""
import xbmc
import xbmcgui

try:
    from . import profiles_mgr
    from . import xmlio
    from .logutil import log_info, log_error, kvfmt
except ImportError:
    import profiles_mgr
    import xmlio
    from logutil import log_info, log_error, kvfmt


def open_for_current_selection():
    """
    Open cross-add dialog for the currently selected item.
    
    Reads current ListItem context, prompts user to select target profiles,
    and adds the item to selected profiles' favourites.xml files.
    """
    dialog = xbmcgui.Dialog()
    
    try:
        # Get current selection
        label = xbmc.getInfoLabel('ListItem.Label')
        path = xbmc.getInfoLabel('ListItem.FolderPath') or xbmc.getInfoLabel('ListItem.FileNameAndPath')
        thumb = xbmc.getInfoLabel('ListItem.Art(thumb)')
        
        if not label or not path:
            dialog.notification("Cross-Add", "No item selected", xbmcgui.NOTIFICATION_WARNING, 2000)
            log_info(kvfmt(event="cross_add_no_selection"))
            return
        
        log_info(kvfmt(event="cross_add_start", label=label, path=path))
        
        # Construct action based on path type
        action = _construct_action(path, label)
        
        # Load profiles configuration
        cfg = profiles_mgr.load_profiles_cfg()
        profiles = cfg.get("profiles", {})
        
        # Filter to profiles with cross_add enabled
        eligible_profiles = []
        preselect = []
        
        source_profile = xbmc.getInfoLabel('System.ProfileName')
        # Kodi's master display name can differ from the canonical directory name.
        if source_profile not in profiles:
            import os
            import xbmcvfs
            current_dir = os.path.normcase(os.path.normpath(xbmcvfs.translatePath('special://profile/')))
            source_profile = next((name for name, directory in profiles_mgr.list_kodi_profiles().items()
                                   if os.path.normcase(os.path.normpath(directory)) == current_dir), '')
        auto_targets = profiles.get(source_profile, {}).get('cross_add', {}).get('auto_targets', [])
        for profile_name, pcfg in sorted(profiles.items()):
            cross_add = pcfg.get("cross_add", {})
            if cross_add.get("enabled", False):
                if profile_name in auto_targets:
                    preselect.append(len(eligible_profiles))
                eligible_profiles.append(profile_name)
        
        if not eligible_profiles:
            dialog.notification("Cross-Add", "No profiles enabled for cross-add", xbmcgui.NOTIFICATION_WARNING, 3000)
            log_info(kvfmt(event="cross_add_no_eligible_profiles"))
            return
        
        # Show multi-select dialog
        selected_indices = dialog.multiselect(
            f"Add '{label}' to profiles:",
            eligible_profiles,
            preselect=preselect
        )
        
        if selected_indices is None or len(selected_indices) == 0:
            log_info(kvfmt(event="cross_add_cancelled"))
            return
        
        # Get selected profile names
        selected_profiles = [eligible_profiles[i] for i in selected_indices]
        
        # Ask if user wants to sync now
        sync_now = dialog.yesno(
            "Cross-Add",
            f"Add to {len(selected_profiles)} profile(s)?",
            nolabel="Add Only",
            yeslabel="Add & Sync Now"
        )
        
        # Add to each selected profile
        success_count = 0
        for profile_name in selected_profiles:
            if xmlio.append_favourite_to_profile(profile_name, label, action, thumb):
                success_count += 1
                log_info(kvfmt(event="cross_add_profile_success", profile=profile_name, label=label))
            else:
                log_error(kvfmt(event="cross_add_profile_failed", profile=profile_name, label=label))
        
        # Sync if requested
        if sync_now:
            try:
                from .sync import run_sync_for_profile
            except ImportError:
                from sync import run_sync_for_profile
            
            sync_success = 0
            for profile_name in selected_profiles:
                try:
                    result = run_sync_for_profile(profile_name, 'bidirectional', skip_profile_reload=True)
                    
                    if result.get("result") == "success":
                        sync_success += 1
                        log_info(kvfmt(event="cross_add_sync_success", profile=profile_name))
                    else:
                        log_error(kvfmt(event="cross_add_sync_failed", profile=profile_name, error=result.get("error")))
                except Exception as e:
                    log_error(kvfmt(event="cross_add_sync_error", profile=profile_name, error=str(e)))
            
            dialog.notification(
                "Cross-Add",
                f"Added to {success_count}/{len(selected_profiles)} profiles, synced {sync_success}",
                xbmcgui.NOTIFICATION_INFO,
                3000
            )
        else:
            dialog.notification(
                "Cross-Add",
                f"Added to {success_count}/{len(selected_profiles)} profiles",
                xbmcgui.NOTIFICATION_INFO,
                2000
            )
        
    except Exception as e:
        log_error(kvfmt(event="cross_add_error", error=str(e)))
        dialog.notification("Cross-Add", f"Error: {str(e)}", xbmcgui.NOTIFICATION_ERROR, 3000)


def _construct_action(path: str, label: str) -> str:
    """
    Construct appropriate action string based on path type.
    
    Args:
        path: Item path/URL
        label: Item label
        
    Returns:
        str: Action string for favourites.xml
    """
    # Plugin URLs
    if path.startswith("plugin://"):
        return f'PlayMedia("{path}")'
    
    # Addon references
    if "addon://" in path or path.startswith("addons://"):
        # Extract addon ID if possible
        import re
        match = re.search(r'plugin\.([^/\?]+)', path)
        if match:
            addon_id = f"plugin.{match.group(1)}"
            return f'RunAddon("{addon_id}")'
        return f'PlayMedia("{path}")'
    
    # Script references
    if path.startswith("script://"):
        return f'RunScript("{path}")'
    
    # Direct media files
    if any(ext in path.lower() for ext in ['.mkv', '.mp4', '.avi', '.m3u', '.strm']):
        return f'PlayMedia("{path}")'
    
    # Fallback: use ActivateWindow with window ID 10025 (Videos)
    return f'ActivateWindow(10025, "{path}", return)'
