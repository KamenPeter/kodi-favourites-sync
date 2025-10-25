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
    addon = xbmcaddon.Addon()
    dialog = xbmcgui.Dialog()
    if not is_endpoint_valid():
        dialog.ok(addon.getAddonInfo("name"),
                  "Cloud favourites location is not configured.\nOpen Settings → Cloud Location to set it up.")
        open_settings(category_id="cloud")
        return
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
    choice = dialog.select("Favourites Sync", options)
    if choice == -1:
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
        from .sync import ADDON_DATA, _xbmcvfs_write_atomic
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
        dialog.notification("Restore", "Favourites restored", xbmcgui.NOTIFICATION_INFO, 3000)
    elif choice == 5:
        from .sync import _load_status
        st = _load_status()
        msg = f"Last: {st.get('last_run','-')}\nResult: {st.get('result','-')}\nChanged: {st.get('changed_items',0)}"
        dialog.ok("Last Sync Status", msg)
    elif choice == 6:
        # Add to Favourites
        import xbmc
        addon_id = addon.getAddonInfo('id')
        addon_name = addon.getAddonInfo('name')
        
        # Build the favourite entry
        favourite_cmd = f"RunScript(special://home/addons/{addon_id}/resources/lib/addon.py)"
        
        # Use JSON-RPC to add to favourites
        json_query = {
            "jsonrpc": "2.0",
            "method": "Favourites.AddFavourite",
            "params": {
                "title": addon_name,
                "type": "script",
                "path": favourite_cmd
            },
            "id": 1
        }
        
        try:
            import json
            result = xbmc.executeJSONRPC(json.dumps(json_query))
            result_dict = json.loads(result)
            
            if "error" in result_dict:
                # Fallback: manually edit favourites.xml
                import xbmcvfs
                profile = xbmcvfs.translatePath("special://profile/")
                fav_file = os.path.join(profile, "favourites.xml")
                
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
                    new_fav = f'    <favourite name="{addon_name}">{favourite_cmd}</favourite>\n'
                    content = content.replace('</favourites>', new_fav + '</favourites>')
                    
                    # Write atomically
                    tmp = fav_file + ".tmp"
                    with open(tmp, 'w', encoding='utf-8') as f:
                        f.write(content)
                    os.replace(tmp, fav_file)
                    
                    dialog.notification("Add to Favourites", "Added successfully!", xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                dialog.notification("Add to Favourites", "Added successfully!", xbmcgui.NOTIFICATION_INFO, 3000)
        except Exception as e:
            dialog.ok("Error", f"Failed to add to favourites:\n{str(e)}")
    elif choice == 7:
        open_settings()
        log_info("settings_opened")

if __name__ == "__main__":
    main()
