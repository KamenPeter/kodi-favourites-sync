import xbmcaddon, xbmc, json, os, datetime
try:
    from .logutil import log_info
except Exception:
    from logutil import log_info

ADDON = xbmcaddon.Addon()

def _get(id_, default=None):
    return ADDON.getSetting(id_) or default

def is_endpoint_valid():
    return ADDON.getSettingBool("endpoint_valid")

def open_settings(category_id=None):
    if category_id:
        try:
            ADDON.openSettings()
        except Exception:
            ADDON.openSettings()
    else:
        ADDON.openSettings()

class ScheduleCfg:
    def __init__(self, enabled, mode, interval, fixed_time, on_start, delay, scheduled_mode):
        self.enabled = enabled
        self.mode = mode
        self.interval_minutes = interval
        self.fixed_time_local = fixed_time
        self.on_startup = on_start
        self.startup_delay_seconds = delay
        self.scheduled_mode = scheduled_mode

def schedule_config():
    enabled = ADDON.getSettingBool("schedule_enabled")
    mode_idx = int(ADDON.getSetting("schedule_mode") or 0)
    mode = ["interval", "fixed", "startup"][mode_idx]
    interval = int(ADDON.getSetting("interval_minutes") or 60)
    fixed_time = ADDON.getSetting("fixed_time_local") or "03:30"
    on_start = ADDON.getSettingBool("run_on_startup")
    delay = int(ADDON.getSetting("startup_delay_seconds") or 20)
    scheduled_mode_idx = int(ADDON.getSetting("scheduled_mode") or 0)
    scheduled_mode = ["pull","push","bidirectional"][scheduled_mode_idx]
    return ScheduleCfg(enabled, mode, interval, fixed_time, on_start, delay, scheduled_mode)
