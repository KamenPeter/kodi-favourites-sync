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
    
    # Check if this is a recent profile reload (triggered by our addon)
    is_reload = _is_recent_reload()
    
    if not is_reload and not monitor.waitForAbort(cfg.startup_delay_seconds):
        _run_scheduled_event('on_start', cfg)
    elif is_reload:
        log_info(kvfmt(event='startup_sync_skipped', reason='recent_profile_reload'))

    # No file-watch or periodic synchronization.
    while not monitor.abortRequested():
        if monitor.waitForAbort(10):
            break
    _run_scheduled_event('on_shutdown', schedule_config())
    
    # Stop RPC server before exiting
    try:
        rpc.stop_server()
    except Exception as e:
        log_error(kvfmt(event="rpc_stop_failed", error=str(e)))
    
    log_info("Service stopped")


def _run_scheduled_event(event, cfg):
    try:
        from .sync import _run, run_sync_for_profile
        from . import profiles_mgr
    except ImportError:
        from sync import _run, run_sync_for_profile
        import profiles_mgr
    active_enabled = cfg.on_startup if event == 'on_start' else cfg.on_shutdown
    if cfg.enabled and active_enabled:
        try:
            if is_endpoint_valid():
                _run(cfg.scheduled_mode, skip_profile_reload=True)
        except Exception as exc:
            log_error(kvfmt(event='scheduled_sync_failed', error=str(exc)))
    # Profile flags are independent of the active profile's global settings.
    try:
        profiles = profiles_mgr.load_profiles_cfg().get('profiles', {})
        for name, profile in profiles.items():
            schedule = profile.get('schedule', {})
            if schedule.get(event):
                result = run_sync_for_profile(name, schedule.get('mode', 'bidirectional'),
                                              skip_profile_reload=True)
                log_info(kvfmt(event='profile_scheduled_sync', profile=name, result=result.get('result')))
    except Exception as exc:
        log_error(kvfmt(event='profile_schedule_failed', error=str(exc)))


def _misc_settings_snapshot():
    try:
        from .settings_mgr import misc_add_to_fav, misc_keep_first, misc_group_addons_top, misc_sort_addons
    except ImportError:
        from settings_mgr import misc_add_to_fav, misc_keep_first, misc_group_addons_top, misc_sort_addons
    return {'add_to_fav': misc_add_to_fav(), 'keep_first': misc_keep_first(),
            'group_top': misc_group_addons_top(), 'sort': misc_sort_addons()}


class _Monitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self._last_validate_time = 0
        self._last_settings_state = _misc_settings_snapshot()
    
    def onSettingsChanged(self):
        """Handle settings changes - auto-apply reorder when user clicks OK"""
        try:
            # Small delay to ensure Kodi has saved settings to XML
            xbmc.sleep(200)
            
            # Force reload addon to pick up fresh settings from XML
            addon = xbmcaddon.Addon()
            
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
            
            log_info(kvfmt(event="settings_read", state=current_state))
            
            # Skip if this is the first time (no previous state to compare)
            if self._last_settings_state is None:
                log_info(kvfmt(event="settings_first_read_skipping_reorder"))
                self._last_settings_state = current_state
                return
            
            # Check if misc settings actually changed
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
