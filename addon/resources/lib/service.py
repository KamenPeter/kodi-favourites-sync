import xbmc, xbmcaddon
try:
    from .logutil import log_info, log_error, kvfmt
except Exception:
    from logutil import log_info, log_error, kvfmt
try:
    from .settings_mgr import is_endpoint_valid, schedule_config
except Exception:
    from settings_mgr import is_endpoint_valid, schedule_config
try:
    from . import rpc
except Exception:
    import rpc

def run():
    monitor = _Monitor()
    addon = xbmcaddon.Addon()
    
    # Check if this is first run (show welcome dialog)
    first_run = addon.getSetting("first_run_done") != "true"
    if first_run:
        # Wait a bit for Kodi to fully start
        if not monitor.waitForAbort(3):
            import xbmcgui
            dialog = xbmcgui.Dialog()
            
            # Show welcome message and offer to configure
            if dialog.yesno(
                addon.getAddonInfo("name"),
                "Thank you for installing Favourites Sync!\n\nWould you like to configure your cloud storage connection now?",
                nolabel="Later",
                yeslabel="Configure Now"
            ):
                # Open settings to cloud category
                addon.openSettings()
            
            # Mark first run as done
            addon.setSetting("first_run_done", "true")
    
    # Try start JSON-RPC server (localhost-only)
    try:
        rpc.start_server()
    except Exception as e:
        log_error(kvfmt(event="rpc_start_failed", error=str(e)))

    cfg = schedule_config()
    log_info(kvfmt(event="service_start", mode=cfg.mode, enabled=cfg.enabled, startup=cfg.on_startup, shutdown=cfg.on_shutdown))
    
    # Startup sync (runs if enabled, independent of schedule_enabled for periodic syncs)
    if cfg.enabled and cfg.on_startup and is_endpoint_valid():
        log_info(f"Waiting {cfg.startup_delay_seconds} seconds before startup sync...")
        if not monitor.waitForAbort(cfg.startup_delay_seconds):
            log_info("Running startup sync...")
            try:
                from .sync import _run
            except Exception:
                from sync import _run
            try:
                _run(cfg.scheduled_mode)
                log_info("Startup sync completed")
            except Exception as e:
                log_error(kvfmt(event="startup_sync_failed", error=str(e)))
        else:
            log_info("Startup sync cancelled - Kodi is shutting down during startup delay")
    
    # Main service loop - just wait for shutdown now (no periodic syncs)
    while not monitor.abortRequested():
        # Just wait, no periodic syncs
        if monitor.waitForAbort(10):
            break
    
    # Shutdown sync if enabled
    cfg = schedule_config()
    if cfg.enabled and cfg.on_shutdown and is_endpoint_valid():
        log_info("Running shutdown sync...")
        try:
            # Import sync function
            try:
                from .sync import _run
            except Exception:
                from sync import _run
            
            try:
                _run(cfg.scheduled_mode)
                log_info("Shutdown sync completed")
            except Exception as e:
                log_error(kvfmt(event="shutdown_sync_failed", error=str(e)))
        except Exception as e:
            log_error(kvfmt(event="shutdown_sync_import_failed", error=str(e)))
    
    log_info("Service stopped")


class _Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self._last_validate_time = 0
    
    def onSettingsChanged(self):
        # Don't auto-validate here - it causes the settings dialog to close
        # Validation will happen on-demand when user opens the addon
        pass

if __name__ == "__main__":
    run()
