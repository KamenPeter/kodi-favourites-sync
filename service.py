import time
import xbmc
import xbmcaddon

from resources.lib.favsync import sync, log

ADDON = xbmcaddon.Addon()
LOG_DEBUG = ADDON.getSettingBool("log_debug")
DRY_RUN   = ADDON.getSettingBool("dry_run")

def get_settings():
    nas_path = ADDON.getSettingString("nas_path").strip()
    try:
        interval_min = int(ADDON.getSettingString("interval_minutes") or "10")
        interval_min = max(1, interval_min)
    except Exception:
        interval_min = 10
    return nas_path, interval_min

def run_once():
    nas_path, _ = get_settings()
    if not nas_path:
        log("NAS path not set. Open add-on settings.", debug=True)
        return
    try:
        sync(nas_path, debug=LOG_DEBUG, dry_run=DRY_RUN)
    except Exception as e:
        log(f"Sync failed: {e}", debug=True)

if __name__ == "__main__":
    monitor = xbmc.Monitor()

    # First sync right after login
    run_once()

    # Periodic sync loop
    while not monitor.abortRequested():
        nas_path, interval_min = get_settings()
        # Sleep in small chunks so we can abort quickly
        for _ in range(interval_min * 60):
            if monitor.abortRequested():
                break
            if monitor.waitForAbort(1):
                break
        if monitor.abortRequested():
            break
        run_once()
