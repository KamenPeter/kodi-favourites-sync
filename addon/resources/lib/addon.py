import os
import xbmcaddon, xbmcgui
try:
    from .settings_mgr import is_endpoint_valid, open_settings
except Exception:
    from settings_mgr import is_endpoint_valid, open_settings
try:
    from .sync import run_sync_ui
except Exception:
    from sync import run_sync_ui
try:
    from .logutil import log_info
except Exception:
    from logutil import log_info

def main():
    # Initialize addon with fallback for script context
    try:
        addon = xbmcaddon.Addon()
    except RuntimeError:
        addon = xbmcaddon.Addon("plugin.service.favourites-sync")
    
    dialog = xbmcgui.Dialog()
    
    log_info("===== ADDON MAIN() CALLED - RUN BUTTON SHOULD BE ENABLED =====")
    log_info(f"addon.py main() - addon id: {addon.getAddonInfo('id')}")
    log_info(f"addon.py main() - addon version: {addon.getAddonInfo('version')}")
    
    # Log current configuration
    try:
        backend_idx = int(addon.getSetting("backend") or "0")
        backend_names = ["WebDAV", "S3", "HTTP(S)", "SFTP", "SMB/NAS", "NFS", "Local Path"]
        backend = backend_names[backend_idx]
        log_info(f"addon.py main() - configured backend: {backend}")
        
        if backend == "WebDAV":
            url = addon.getSetting("webdav_url") or ""
            path = addon.getSetting("webdav_path") or ""
            user = addon.getSetting("webdav_user") or ""
            log_info(f"addon.py main() - WebDAV URL: {url}, Path: {path}, User: {user}")
        elif backend == "Local Path":
            path = addon.getSetting("local_path") or ""
            log_info(f"addon.py main() - Local path: {path}")
    except Exception as e:
        log_info(f"addon.py main() - error reading config: {e}")
    
    # Always show menu - check configuration only when user tries to sync
    options = [
        "Pull (Cloud → Local)",
        "Push (Local → Cloud)",
        "Bidirectional",
        "Dry-run (Preview)",
        "Restore from Backup…",
        "Last Sync Status",
        "Add to Favourites",
        "Settings",
    ]
    
    log_info("addon.py main() - showing menu dialog")
    choice = dialog.select("Favourites Sync", options)
    log_info(f"addon.py main() - user selected option: {choice}")
    
    if choice == -1:
        log_info("addon.py main() - user cancelled menu")
        return
    
    # Check if endpoint is valid only when user tries to sync
    if choice in (0, 1, 2, 3):  # Pull, Push, Bidirectional, Dry-run
        log_info(f"addon.py main() - validating endpoint for sync operation {choice}")
        is_valid = is_endpoint_valid()
        log_info(f"addon.py main() - endpoint validation result: {is_valid}")
        
        if not is_valid:
            log_info("addon.py main() - endpoint not valid, showing configuration dialog")
            dialog.ok(addon.getAddonInfo("name"),
                      "Cloud favourites location is not configured or unreachable.\n\nPlease go to Settings → Cloud Location to configure it.")
            open_settings(category_id="cloud")
            return
    
    if choice == 0:
        run_sync_ui("pull")
    elif choice == 1:
        run_sync_ui("push")
    elif choice == 2:
        run_sync_ui("bidirectional")
    elif choice == 3:
        run_sync_ui("dryrun")
    elif choice == 4:
        # restore from backup
        try:
            from .sync import ADDON_DATA, _xbmcvfs_write_atomic
        except ImportError:
            from sync import ADDON_DATA, _xbmcvfs_write_atomic
        import xbmc, xbmcvfs
        profile = xbmcvfs.translatePath("special://profile/")
        fav = os.path.join(profile, "favourites.xml")
        backups = [f for f in os.listdir(ADDON_DATA) if f.endswith('.xml.bak')]
        backups.sort(reverse=True)
        if not backups:
            dialog.ok("Restore", "No backups found.")
            return
        idx = dialog.select("Choose backup", backups)
        if idx == -1:
            return
        path = os.path.join(ADDON_DATA, backups[idx])
        with open(path, 'rb') as f:
            data = f.read()
        _xbmcvfs_write_atomic(fav, data)
        
        # Reload favourites after restore - use LoadProfile to force reload
        try:
            current_profile = xbmc.getInfoLabel('System.ProfileName')
            xbmc.executebuiltin(f'LoadProfile({current_profile})')
        except Exception:
            pass
        
        dialog.notification("Restore", "Favourites restored - profile reloaded", xbmcgui.NOTIFICATION_INFO, 3000)
    elif choice == 5:
        try:
            from .sync import _load_status
        except ImportError:
            from sync import _load_status
        st = _load_status()
        msg = f"Last: {st.get('last_run','-')}\nResult: {st.get('result','-')}\nChanged: {st.get('changed_items',0)}"
        dialog.ok("Last Sync Status", msg)
    elif choice == 6:
        # Add to Favourites
        import xbmc
        addon_id = addon.getAddonInfo('id')
        addon_name = addon.getAddonInfo('name')
        
        # Build the favourite entry - just the script path
        script_path = f"special://home/addons/{addon_id}/resources/lib/addon.py"
        
        # Manually edit favourites.xml to include thumb attribute
        # (JSON-RPC doesn't support thumb parameter)
        try:
            import xbmcvfs
            profile = xbmcvfs.translatePath("special://profile/")
            fav_file = os.path.join(profile, "favourites.xml")
            
            # Get absolute path to addon icon
            addon_home = xbmcvfs.translatePath(f"special://home/addons/{addon_id}/")
            addon_icon = os.path.join(addon_home, "icon.png")
            
            # Read existing favourites
            if os.path.exists(fav_file):
                with open(fav_file, 'r', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n<favourites>\n</favourites>'
            
            # Check if already exists
            if addon_name in content:
                dialog.notification("Add to Favourites", "Already in favourites!", xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                # Add new favourite before </favourites>
                favourite_cmd = f"RunScript({script_path})"
                new_fav = f'    <favourite name="{addon_name}" thumb="{addon_icon}">{favourite_cmd}</favourite>\n'
                content = content.replace('</favourites>', new_fav + '</favourites>')
                
                # Write atomically
                tmp = fav_file + ".tmp"
                with open(tmp, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.replace(tmp, fav_file)
                
                dialog.notification("Add to Favourites", "Added successfully!", xbmcgui.NOTIFICATION_INFO, 3000)
        except Exception as e:
            dialog.ok("Error", f"Failed to add to favourites:\n{str(e)}")
    elif choice == 7:
        open_settings()
        log_info("settings_opened")

if __name__ == "__main__":
    main()
