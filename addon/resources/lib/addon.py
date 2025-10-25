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
                  "Cloud favourites location is not configured.",
                  "Open Settings → Cloud Location to set it up.")
        open_settings(category_id="cloud")
        return
    options = [
        "Pull (Cloud → Local)",
        "Push (Local → Cloud)",
        "Bidirectional",
        "Dry-run (Preview)",
        "Restore from Backup…",
        "Last Sync Status",
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
        open_settings()
        log_info("settings_opened")

if __name__ == "__main__":
    main()
