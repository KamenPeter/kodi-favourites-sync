import xbmc, xbmcaddon, xbmcvfs
import os
import time
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


def _get_reload_flag_path():
    """Get path to reload flag file"""
    addon = xbmcaddon.Addon()
    addon_data = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
    return os.path.join(addon_data, ".profile_reload_flag")


def _is_recent_reload():
    """Check if profile was reloaded recently (within last 10 seconds)"""
    flag_path = _get_reload_flag_path()
    if os.path.exists(flag_path):
        try:
            mtime = os.path.getmtime(flag_path)
            age = time.time() - mtime
            if age < 10:  # Within last 10 seconds
                log_info(kvfmt(event="recent_reload_detected", age_seconds=age))
                return True
        except Exception as e:
            log_error(kvfmt(event="reload_flag_check_failed", error=str(e)))
    return False


def _set_reload_flag():
    """Set flag indicating profile reload is about to happen"""
    flag_path = _get_reload_flag_path()
    try:
        os.makedirs(os.path.dirname(flag_path), exist_ok=True)
        with open(flag_path, 'w') as f:
            f.write(str(time.time()))
        log_info(kvfmt(event="reload_flag_set"))
    except Exception as e:
        log_error(kvfmt(event="reload_flag_set_failed", error=str(e)))

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
    
    # Sync misc_add_to_fav state with actual file after service starts
    try:
        try:
            from .settings_mgr import sync_misc_add_to_fav_state
        except Exception:
            from settings_mgr import sync_misc_add_to_fav_state
        
        # Small delay to ensure Kodi is fully ready
        if not monitor.waitForAbort(2):
            sync_misc_add_to_fav_state()
    except Exception as e:
        log_error(kvfmt(event="initial_sync_failed", error=str(e)))
    
    # Check if this is a recent profile reload (triggered by our addon)
    is_reload = _is_recent_reload()
    
    # Startup sync (runs if enabled and NOT a recent reload)
    if cfg.enabled and cfg.on_startup and is_endpoint_valid() and not is_reload:
        log_info(f"Waiting {cfg.startup_delay_seconds} seconds before startup sync...")
        if not monitor.waitForAbort(cfg.startup_delay_seconds):
            log_info("Running startup sync...")
            try:
                from .sync import _run
            except Exception:
                from sync import _run
            try:
                # Skip profile reload for scheduled sync to prevent infinite loop
                _run(cfg.scheduled_mode, skip_profile_reload=True)
                log_info("Startup sync completed")
            except Exception as e:
                log_error(kvfmt(event="startup_sync_failed", error=str(e)))
        else:
            log_info("Startup sync cancelled - Kodi is shutting down during startup delay")
    elif is_reload:
        log_info(kvfmt(event="startup_sync_skipped", reason="recent_profile_reload"))
    
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
                # Skip profile reload for scheduled sync to prevent infinite loop
                _run(cfg.scheduled_mode, skip_profile_reload=True)
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
        self._last_settings_state = None
    
    def onSettingsChanged(self):
        """Handle settings changes - auto-apply reorder when user clicks OK"""
        try:
            # Get current misc settings
            try:
                from .settings_mgr import (
                    misc_add_to_fav,
                    misc_keep_first,
                    misc_group_addons_top,
                    misc_sort_addons,
                    sync_misc_add_to_fav_state,
                )
            except Exception:
                from settings_mgr import (
                    misc_add_to_fav,
                    misc_keep_first,
                    misc_group_addons_top,
                    misc_sort_addons,
                    sync_misc_add_to_fav_state,
                )
            
            current_state = {
                'add_to_fav': misc_add_to_fav(),
                'keep_first': misc_keep_first(),
                'group_top': misc_group_addons_top(),
                'sort': misc_sort_addons()
            }
            
            # Check if misc settings changed
            if self._last_settings_state != current_state:
                log_info(kvfmt(event="misc_settings_changed", prev=self._last_settings_state, current=current_state))
                
                # Auto-apply reorder with the new settings
                try:
                    from reorder import reorder_favourites
                except Exception:
                    try:
                        from .reorder import reorder_favourites
                    except:
                        log_error(kvfmt(event="reorder_import_failed"))
                        return
                
                # Small delay to ensure settings are fully saved
                xbmc.sleep(500)
                
                # Reorder favourites - this will write changes and reload profile
                result = reorder_favourites(manual_context=True, skip_profile_reload=False)
                
                # Ensure misc_add_to_fav matches actual favourites.xml contents after applying changes
                try:
                    sync_misc_add_to_fav_state()
                except Exception as e:
                    log_error(kvfmt(event="sync_add_to_fav_resync_failed", error=str(e)))
                
                if result.get('changed'):
                    log_info(kvfmt(event="auto_reorder_success", result=result))
                    
                    # Additional small delay before notification to ensure reload completes
                    xbmc.sleep(300)
                    
                    # Show notification
                    try:
                        import xbmcgui
                        xbmcgui.Dialog().notification(
                            "[fav-sync]",
                            f"Favourites updated: {result['addons']} addons, {result['others']} others",
                            xbmcgui.NOTIFICATION_INFO,
                            3000
                        )
                    except:
                        pass
                else:
                    log_info(kvfmt(event="auto_reorder_no_changes"))
                
                # Snapshot latest settings for future diff checks (reflects any sync adjustments)
                try:
                    self._last_settings_state = {
                        'add_to_fav': misc_add_to_fav(),
                        'keep_first': misc_keep_first(),
                        'group_top': misc_group_addons_top(),
                        'sort': misc_sort_addons()
                    }
                except Exception as e:
                    log_error(kvfmt(event="settings_snapshot_failed", error=str(e)))
                    self._last_settings_state = current_state
            else:
                self._last_settings_state = current_state
            
        except Exception as e:
            log_error(kvfmt(event="settings_changed_handler_failed", error=str(e)))

if __name__ == "__main__":
    run()
